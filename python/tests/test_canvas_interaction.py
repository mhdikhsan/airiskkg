"""Can the canvas actually be clicked?

The companion to test_canvas_renders.py, and the harder half. That file proved
the diagram is drawn; this one proves it responds - and the two are genuinely
different questions, because the bug that prompted it drew a perfect diagram
nobody could interact with.

Why this goes through the DevTools protocol rather than dispatching events.
`element.dispatchEvent(new MouseEvent("click"))` lands on whatever element you
name, always. A real click is routed by the browser, and pointer capture changes
where it lands: `#canvas-wrap` captured the pointer for the architecture pan, so
every real click on the business canvas retargeted to the wrap and the BPMN
handlers never ran. A synthetic-click test was green throughout - it was testing
the listener, which was fine, and never the interaction, which was not.

So: real mouse input, at real coordinates, read back from the real page.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request

import pytest

from tests.conftest import *  # noqa: F401,F403 - shared example lookup

pytest.importorskip("websockets")

from test_canvas_renders import STATIC, _browser, _free_port, served  # noqa: E402,F401

CDP_PORT_TRIES = 6


def _load_example_probe() -> str:
    """A copy of the app that loads the whole scene on its own - two
    architectures and the process that runs both - so the driver only clicks."""
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <script>
  window.addEventListener("load", async () => {
    const nl = String.fromCharCode(10,10);
    const a = await (await fetch("/api/examples/simple_graph_rag")).json();
    const m = await (await fetch("/api/examples/meter_anomaly_scoring")).json();
    const p = await (await fetch("/api/examples/energy_customer_service")).json();
    window.PairAI.Editor.setValue(a.ttl + nl + m.ttl + nl + p.ttl);
  });
  </script>
"""
    return source.replace("</body>", driver + "</body>")


class _Page:
    """The smallest CDP client that can press a mouse button and read the DOM."""

    def __init__(self, ws):
        self._ws = ws
        self._id = 0

    async def send(self, method, params=None):
        import json as _json

        self._id += 1
        await self._ws.send(_json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            message = _json.loads(await self._ws.recv())
            if message.get("id") == self._id:
                if "error" in message:
                    raise AssertionError(f"{method}: {message['error']}")
                return message.get("result", {})

    async def js(self, expression):
        result = await self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        return result.get("result", {}).get("value")

    async def click(self, x, y):
        import asyncio

        for kind in ("mousePressed", "mouseReleased"):
            await self.send(
                "Input.dispatchMouseEvent",
                {
                    "type": kind,
                    "x": x,
                    "y": y,
                    "button": "left",
                    "clickCount": 1,
                    "buttons": 1 if kind == "mousePressed" else 0,
                },
            )
            await asyncio.sleep(0.12)
        await asyncio.sleep(0.7)

    async def drag(self, x1, y1, x2, y2):
        """A press, a real move, and a release - which is what makes the browser
        treat it as a drag rather than a click."""
        import asyncio

        await self.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x1, "y": y1,
                                                     "button": "left", "clickCount": 1, "buttons": 1})
        for step in range(1, 5):
            await self.send("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": round(x1 + (x2 - x1) * step / 4),
                "y": round(y1 + (y2 - y1) * step / 4),
                "button": "left", "buttons": 1,
            })
            await asyncio.sleep(0.05)
        await self.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x2, "y": y2,
                                                     "button": "left", "clickCount": 1, "buttons": 0})
        await asyncio.sleep(0.7)


@pytest.fixture(scope="module")
def page(served):
    """A headless browser on the business level of the real app, driveable with
    real input."""
    import asyncio

    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to drive")

    probe = STATIC / "_cdp_probe.html"
    probe.write_text(_load_example_probe(), encoding="utf-8")

    port = _free_port()
    process = subprocess.Popen(
        [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
         f"--remote-debugging-port={port}", "--window-size=1400,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    else:
        process.terminate()
        probe.unlink(missing_ok=True)
        pytest.skip("the browser did not expose a debugging port")

    async def open_page():
        import websockets

        tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
        target = next(tab for tab in tabs if tab["type"] == "page")
        connection = await websockets.connect(target["webSocketDebuggerUrl"], max_size=None)
        handle = _Page(connection)
        await handle.send("Page.navigate", {"url": f"http://127.0.0.1:{served}/static/_cdp_probe.html"})
        await asyncio.sleep(7)
        await handle.js('document.querySelector("#level-business").click()')
        await asyncio.sleep(3)
        return connection, handle

    loop = asyncio.new_event_loop()
    connection, handle = loop.run_until_complete(open_page())
    yield loop, handle
    loop.run_until_complete(connection.close())
    loop.close()
    process.terminate()
    probe.unlink(missing_ok=True)


def _box(loop, handle):
    return loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('.pc-activity.refined .pc-box');
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return { left: r.left, top: r.top, width: r.width, height: r.height };
    })()"""))


def _on_architecture(loop, handle):
    return loop.run_until_complete(
        handle.js('document.querySelector("#level-architecture").classList.contains("active")')
    )


def _settle(loop, handle, expression, unwanted, tries=20):
    """Wait for the page to finish, rather than guessing how long it takes.

    Descending fires a round trip, and a fixed sleep either wastes time or reads
    the previous render - which is how this test first reported a canvas that
    had narrowed correctly as one that had not."""
    for _ in range(tries):
        value = loop.run_until_complete(handle.js(expression))
        if value != unwanted:
            return value
        time.sleep(0.4)
    return loop.run_until_complete(handle.js(expression))


def _back_to_business(loop, handle):
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(1.5)


def test_a_real_click_on_the_subprocess_opens_the_architecture(page) -> None:
    """The bug: #canvas-wrap captured the pointer for the architecture pan, so a
    real click on the business canvas retargeted to the wrap and never reached
    the activity. Synthetic clicks could not see it."""
    loop, handle = page
    box = _box(loop, handle)
    assert box, "no refined activity was drawn to click"

    loop.run_until_complete(handle.click(round(box["left"] + 30), round(box["top"] + 12)))
    assert _on_architecture(loop, handle), "clicking the sub-process did nothing"
    _back_to_business(loop, handle)


def test_clicking_empty_canvas_does_not_open_anything(page) -> None:
    """The other half of the same claim: the box means something, the space
    around it does not."""
    loop, handle = page
    box = _box(loop, handle)

    loop.run_until_complete(
        handle.click(round(box["left"] + box["width"] / 2), round(box["top"] + box["height"] + 60))
    )
    assert not _on_architecture(loop, handle), "empty canvas opened the architecture"


def test_dragging_the_canvas_is_not_a_click(page) -> None:
    """Panning ends in a click the reader did not mean. Letting go over an
    activity must not open it, or the diagram moves and then jumps a level."""
    loop, handle = page
    box = _box(loop, handle)
    target_x = round(box["left"] + 30)
    target_y = round(box["top"] + 12)

    loop.run_until_complete(handle.drag(target_x - 140, target_y, target_x, target_y))
    assert not _on_architecture(loop, handle), "a drag was treated as a click"


def test_the_risk_badge_folds_the_findings_it_counts(page) -> None:
    """A count alone is a number nobody can act on; the whole list at once is a
    wall. The badge folds, so a reader opens the one activity they are asking
    about - and the box grows to hold it rather than the list spilling over the
    diagram."""
    loop, handle = page

    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    time.sleep(9)
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(2)

    badge = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('.pc-risk .pc-risk-box');
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert badge, "no activity reported any candidate risk"

    before = loop.run_until_complete(handle.js('document.querySelectorAll(".pc-risk-item").length'))
    loop.run_until_complete(handle.click(badge["x"], badge["y"]))
    after = loop.run_until_complete(handle.js('document.querySelectorAll(".pc-risk-item").length'))

    assert after != before, "the badge did not fold or unfold anything"
    assert max(before, after) > 0, "unfolding showed no findings"


def test_descending_narrows_the_canvas_to_that_activitys_architecture(page) -> None:
    """"Open this activity" means the architecture behind it, not the other tab.

    A document that carries two architectures - which is the normal case once a
    business process runs more than one AI system - used to draw both, so
    descending from either activity showed the same picture. The relation is
    already in the graph, so narrowing is a query and nothing needs storing:
    pair:refinedBy names the system, beam:hasProcess and beam:hasResource say
    what it holds."""
    loop, handle = page

    # Widen first, deliberately. Picking the architecture level by hand clears
    # any scope a previous descent left behind, and measuring without doing so
    # compares a narrowed canvas against itself.
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(2)
    whole = loop.run_until_complete(handle.js('document.querySelectorAll(".node").length'))
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(2)

    def spot(index):
        """Fresh coordinates each time: going back to the business level refits
        the canvas, so positions read before a round trip are stale."""
        return loop.run_until_complete(handle.js(f"""(() => {{
            const boxes = document.querySelectorAll('.pc-activity.refined .pc-box');
            if (boxes.length <= {index}) return null;
            const r = boxes[{index}].getBoundingClientRect();
            return {{ x: Math.round(r.left + 30), y: Math.round(r.top + 12), count: boxes.length }};
        }})()"""))

    first = spot(0)
    assert first and first["count"] >= 2, "the scene should carry two AI activities"

    seen = []
    for index in range(2):
        at = spot(index)
        loop.run_until_complete(handle.click(at["x"], at["y"]))
        nodes = _settle(loop, handle, 'document.querySelectorAll(".node").length', whole)
        seen.append({
            "nodes": nodes,
            "badge": loop.run_until_complete(
                handle.js('document.querySelector("#system-badge").textContent')
            ),
        })
        _back_to_business(loop, handle)

    narrowed = [view["nodes"] for view in seen]
    assert max(narrowed) < whole, (
        f"descending did not narrow the canvas: showed {narrowed} against {whole} unscoped"
    )
    assert seen[0]["badge"] != seen[1]["badge"], (
        f"both activities showed the same architecture: {seen}"
    )


def test_a_pan_does_not_eat_the_click_after_it(page) -> None:
    """The "it gets stuck" report, reduced.

    A pan produces a click nobody meant, so one click is swallowed. That flag
    used to be cleared only by a handler on an activity - so panning and then
    releasing over empty canvas left it armed, and the next real click, whenever
    it came, vanished. Here: pan over nothing, then click the sub-process, and
    it must open."""
    loop, handle = page
    _back_to_business(loop, handle)

    at = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('.pc-activity.refined .pc-box');
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + 30), y: Math.round(r.top + 12),
                 emptyY: Math.round(r.bottom + 90) };
    })()"""))

    # A pan that ends over empty canvas, so no activity handler sees its click.
    loop.run_until_complete(handle.drag(at["x"] - 150, at["emptyY"], at["x"], at["emptyY"]))
    assert not _on_architecture(loop, handle), "the pan itself opened something"

    # The pan moved everything, so read the box again rather than clicking where
    # it used to be - which is a mistake this test made first.
    moved = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('.pc-activity.refined .pc-box');
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + 30), y: Math.round(r.top + 12) };
    })()"""))
    loop.run_until_complete(handle.click(moved["x"], moved["y"]))
    assert _on_architecture(loop, handle), (
        "the click after a pan was swallowed - the flag outlived the pan"
    )
    _back_to_business(loop, handle)


def test_the_findings_list_follows_the_architecture_on_screen(page) -> None:
    """The assessment stays whole - the business process is what carries data
    and controls between systems, so assessing one architecture alone would lose
    the context the layer exists to supply. What narrows is the reading: someone
    who opened one activity is asking about that activity."""
    loop, handle = page
    # Widen first: an earlier test may have left the canvas on one architecture,
    # and a narrowed count compared against itself proves nothing.
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(2)

    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    time.sleep(9)
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(2)

    everything = loop.run_until_complete(
        handle.js('Number(document.querySelector("#findings-count").textContent || 0)')
    )
    assert everything > 0, "nothing was found to narrow"

    at = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('.pc-activity.refined .pc-box');
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + 30), y: Math.round(r.top + 12) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    narrowed = _settle(
        loop, handle,
        'Number(document.querySelector("#findings-count").textContent || 0)',
        everything,
    )

    assert narrowed < everything, (
        f"the findings list showed {narrowed} of {everything} - it did not follow the canvas"
    )
    _back_to_business(loop, handle)


def test_a_version_can_be_read_without_being_restored(page) -> None:
    """Restore replaces the graph on screen, which is a commitment. Asking what
    a past assessment found should not require making it the present one."""
    loop, handle = page

    # Self-sufficient: a version only exists once something has been assessed,
    # and depending on another test having done it makes this one pass or fail
    # by ordering rather than by behaviour.
    recorded = loop.run_until_complete(handle.js("window.PairAI.VersionHistory.list().length"))
    if not recorded:
        loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
        time.sleep(9)

    opened = loop.run_until_complete(handle.js("""(() => {
        const tab = document.querySelector('[data-drawer-tab="history"]');
        if (!tab) return { error: "no history tab" };
        tab.click();
        const row = document.querySelector('.hist-row');
        if (!row) return { error: "no version rows" };
        const before = window.PairAI.Editor.getValue().length;
        /* A listener that throws reports as an uncaught error, not to the
         * caller, so try/catch around .click() sees nothing. Trap it. */
        window.__err = null;
        const onError = (e) => { window.__err = e.message; };
        window.addEventListener("error", onError);
        row.click();
        window.removeEventListener("error", onError);
        return {
            error: window.__err,
            before: before,
            after: window.PairAI.Editor.getValue().length,
            preview: !document.querySelector('#history-preview').classList.contains('hidden'),
        };
    })()"""))

    assert opened, "the page returned nothing"
    assert not opened["error"], f"reading a version failed: {opened['error']}"
    assert opened["preview"], "opening a version showed nothing"
    assert opened["before"] == opened["after"], (
        "reading a version changed the graph - that is restoring, not reading"
    )


def test_clicking_a_plain_activity_opens_an_editor_for_it(page) -> None:
    """The popup existed and was unreachable.

    A rule meant to keep the architecture's node popup off the business canvas
    matched on `.node-detail`, and the process popup is one - so every BPMN
    activity opened a panel with `display: none`. Nothing threw, nothing
    logged, and the only way to attach data to an activity was to write three
    BPMN nodes into the Turtle by hand.
    """
    loop, handle = page
    _back_to_business(loop, handle)

    at = loop.run_until_complete(handle.js("""(() => {
        const plain = [...document.querySelectorAll('.pc-activity')]
            .filter((b) => !b.classList.contains('refined'))[0];
        if (!plain) return null;
        const r = plain.querySelector('.pc-box').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + 12) };
    })()"""))
    assert at, "no plain activity on the business canvas to click"

    loop.run_until_complete(handle.click(at["x"], at["y"]))
    seen = loop.run_until_complete(handle.js("""(() => {
        const panel = document.querySelector('#process-detail');
        return {
            hidden: panel.classList.contains('hidden'),
            display: getComputedStyle(panel).display,
            fields: ['#pd-name', '#pd-refines', '#pd-data-add'].filter((s) => panel.querySelector(s)),
            dataRows: panel.querySelectorAll('.pd-data').length,
            classes: panel.querySelectorAll('#pd-data-class option').length,
        };
    })()"""))

    assert not seen["hidden"], "clicking the activity did not open its editor"
    assert seen["display"] != "none", (
        "the editor opened but CSS hides it on the business level - which is the bug"
    )
    assert len(seen["fields"]) == 3, f"the editor is missing controls: {seen['fields']}"
    assert seen["classes"] > 0, "the data classification picker has no options"

    loop.run_until_complete(handle.js(
        'document.querySelector("#process-detail").classList.add("hidden")'))


def test_two_architectures_are_drawn_as_two_named_areas(page) -> None:
    """The scene holds a GraphRAG chatbot and a meter-anomaly scorer because one
    business process runs both. They used to arrive as one undifferentiated
    field of nodes with nothing saying where one ended and the other began."""
    loop, handle = page
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(2)

    seen = loop.run_until_complete(handle.js("""(() => {
        const bounds = [...document.querySelectorAll('.system-bound')];
        return {
            count: bounds.length,
            names: bounds.map((b) => (b.querySelector('.system-bound-label') || {}).textContent),
            boxes: bounds.map((b) => {
                const r = b.querySelector('.system-bound-box');
                return { w: Number(r.getAttribute('width')), h: Number(r.getAttribute('height')) };
            }),
        };
    })()"""))

    assert seen["count"] >= 2, (
        f"expected a boundary per architecture, drew {seen['count']}"
    )
    assert all(name and name.strip() for name in seen["names"]), (
        f"a boundary was drawn with no name on it: {seen['names']}"
    )
    assert all(b["w"] > 0 and b["h"] > 0 for b in seen["boxes"]), (
        f"a boundary has no area: {seen['boxes']}"
    )
    _back_to_business(loop, handle)


@pytest.fixture(scope="module")
def empty_workbench(served):
    """A browser on the real page with nothing loaded - the opening screen.

    Its own page, because the shared `page` fixture loads three graphs before
    anything else runs, and the question this is about is only on screen while
    the workbench is empty."""
    import asyncio

    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to drive")

    port = _free_port()
    process = subprocess.Popen(
        [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
         f"--remote-debugging-port={port}", "--window-size=1400,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    else:
        process.terminate()
        pytest.skip("the browser did not expose a debugging port")

    async def open_page():
        import websockets

        tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
        target = next(tab for tab in tabs if tab["type"] == "page")
        connection = await websockets.connect(target["webSocketDebuggerUrl"], max_size=None)
        handle = _Page(connection)
        await handle.send("Page.navigate", {"url": f"http://127.0.0.1:{served}/"})
        await asyncio.sleep(6)
        return connection, handle

    loop = asyncio.new_event_loop()
    connection, handle = loop.run_until_complete(open_page())
    yield loop, handle
    loop.run_until_complete(connection.close())
    loop.close()
    process.terminate()


def test_the_opening_choice_answers_a_real_click(empty_workbench) -> None:
    """The first thing anyone sees, and it was dead.

    `.canvas-empty` lives inside `#canvas-wrap`, whose pointerdown handler arms
    the architecture pan and takes pointer capture - which retargets the click
    that follows to the wrap, so the card's own handler never ran. Pressing
    either card did nothing at all.

    The suite stayed green because the test for this calls `.click()`, which
    invokes the handler directly and can never see a click that does not
    arrive. Only real input can.
    """
    loop, handle = empty_workbench

    at = loop.run_until_complete(handle.js("""(() => {
        const card = document.querySelector('#start-business');
        if (!card || card.offsetParent === null) return null;
        const r = card.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert at, "the opening question is not on screen on an empty workbench"

    loop.run_until_complete(handle.click(at["x"], at["y"]))
    seen = loop.run_until_complete(handle.js("""(() => {
        const wrap = document.querySelector('#canvas-wrap');
        return {
            started: wrap.classList.contains('started'),
            stillAsking: wrap.classList.contains('unstarted'),
            business: document.querySelector('#level-business').classList.contains('active'),
            tools: document.querySelectorAll('#process-palette .pp-item').length,
            wayBack: !document.querySelector('#level-switch').classList.contains('hidden'),
        };
    })()"""))

    assert seen["started"], "a real click on the opening choice did nothing"
    assert not seen["stillAsking"], "the question stayed on screen after being answered"
    assert seen["business"], "choosing a business process landed on the other layer"
    assert seen["tools"] > 0, "no tools for the layer that was chosen"
    assert seen["wayBack"], "no way back to the architecture layer"


def test_a_new_example_forgets_the_scope_of_the_last_one(page) -> None:
    """Descend into an activity, then pick a plain architecture example.

    The scope survived the change of document, so the findings list filtered
    against a system the new graph does not contain and reported "0 of 18" with
    the breadcrumb still naming an activity from the example before.
    """
    loop, handle = page
    # Restored at the end: this test swaps the document out, and the page
    # fixture is shared with every test after it.
    loop.run_until_complete(handle.js("window.__scene = window.PairAI.Editor.getValue(), 1"))
    _back_to_business(loop, handle)

    at = _box(loop, handle)
    assert at, "no refined activity to descend through"
    loop.run_until_complete(handle.click(round(at["left"] + 30), round(at["top"] + 12)))
    time.sleep(2)
    scoped = loop.run_until_complete(handle.js("window.PairAI.state.scopedSystem"))
    assert scoped, "descending did not narrow to anything, so there is no scope to forget"

    loop.run_until_complete(handle.js("""(() => {
        const s = document.querySelector("#example-select");
        s.value = "simple_graph_rag";
        s.dispatchEvent(new Event("change", { bubbles: true }));
    })()"""))
    time.sleep(4)

    after = loop.run_until_complete(handle.js("""(() => ({
        scoped: window.PairAI.state.scopedSystem,
        openedFrom: window.PairAI.state.openedFrom ? window.PairAI.state.openedFrom.label : null,
        crumb: !document.querySelector("#breadcrumb").classList.contains("hidden"),
    }))()"""))

    loop.run_until_complete(handle.send("Runtime.evaluate", {
        "expression": "window.PairAI.Editor.setValue(window.__scene)",
        "returnByValue": True,
    }))
    time.sleep(3)

    assert after["scoped"] is None, (
        f"the new example is still narrowed to {after['scoped']} from the previous one"
    )
    assert after["openedFrom"] is None, (
        f"the breadcrumb still names {after['openedFrom']}, an activity of the previous example"
    )
    assert not after["crumb"], "the breadcrumb is still on screen for a graph that has no process"


def test_annotate_narrows_with_the_rest_of_the_workbench(page) -> None:
    """Descending filtered the findings list and the canvas, but not this tab.

    Someone opening the meter scorer to annotate it was handed every element of
    the chatbot as well, in a table that had just learned to group by
    architecture - so the grouping told them the elements were from somewhere
    else without telling them why they were there at all.
    """
    loop, handle = page
    _back_to_business(loop, handle)

    at = _box(loop, handle)
    assert at, "no refined activity to descend through"
    loop.run_until_complete(handle.click(round(at["left"] + 30), round(at["top"] + 12)))
    time.sleep(2)
    scoped = loop.run_until_complete(handle.js("window.PairAI.state.scopedSystem"))
    assert scoped, "descending narrowed to nothing, so there is no scope to follow"

    loop.run_until_complete(handle.js("""(() => {
        document.querySelectorAll('.drawer-tab').forEach((t) => {
            if (t.dataset.drawerTab === 'annotate') t.click();
        });
    })()"""))
    time.sleep(4)

    seen = loop.run_until_complete(handle.js("""(() => ({
        rows: document.querySelectorAll('#annotate-list .annotate-row:not(.annotate-row-head)').length,
        groups: [...document.querySelectorAll('#annotate-list .annotate-group')].map((g) => g.textContent),
    }))()"""))

    assert seen["rows"] > 0, "the annotate table is empty for an architecture that has elements"
    assert len(seen["groups"]) == 0, (
        "elements from more than one architecture are listed while the workbench "
        f"is narrowed to one: {seen['groups']}"
    )
    _back_to_business(loop, handle)


def test_widening_by_hand_also_widens_the_annotate_table(page) -> None:
    """The breadcrumb reset it and the level switch did not.

    Widening called the two redraws it knew about rather than announcing the
    change, so the annotate table - which learned to follow the scope later -
    stayed narrowed to the architecture just left.
    """
    loop, handle = page
    _back_to_business(loop, handle)

    at = _box(loop, handle)
    assert at, "no refined activity to descend through"
    loop.run_until_complete(handle.click(round(at["left"] + 30), round(at["top"] + 12)))
    time.sleep(2)
    assert loop.run_until_complete(handle.js("window.PairAI.state.scopedSystem")), "no scope to widen"

    loop.run_until_complete(handle.js("""(() => {
        document.querySelectorAll('.drawer-tab').forEach((t) => {
            if (t.dataset.drawerTab === 'annotate') t.click();
        });
    })()"""))
    time.sleep(3)
    narrowed = loop.run_until_complete(handle.js(
        "document.querySelectorAll('#annotate-list .annotate-group').length"))
    assert narrowed == 0, "descending did not narrow the table, so widening proves nothing"

    # Widen with the level switch, not the breadcrumb.
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(4)
    after = loop.run_until_complete(handle.js("""(() => ({
        scoped: window.PairAI.state.scopedSystem,
        groups: document.querySelectorAll('#annotate-list .annotate-group').length,
    }))()"""))

    assert after["scoped"] is None, "the level switch did not widen the scope"
    assert after["groups"] >= 2, (
        "the annotate table is still showing one architecture after widening to all of them"
    )
    _back_to_business(loop, handle)


def test_an_annotate_group_folds_away(page) -> None:
    """Two architectures list forty-odd elements between them."""
    loop, handle = page
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(2)
    loop.run_until_complete(handle.js("""(() => {
        document.querySelectorAll('.drawer-tab').forEach((t) => {
            if (t.dataset.drawerTab === 'annotate') t.click();
        });
    })()"""))
    time.sleep(4)

    before = loop.run_until_complete(handle.js("""(() => {
        const head = document.querySelector('#annotate-list .annotate-group');
        if (!head) return null;
        const r = head.getBoundingClientRect();
        return {
            rows: document.querySelectorAll('#annotate-list .annotate-row:not(.annotate-row-head)').length,
            x: Math.round(r.left + 40), y: Math.round(r.top + r.height / 2),
        };
    })()"""))
    assert before, "no architecture group heading to fold"
    assert before["rows"] > 0

    loop.run_until_complete(handle.click(before["x"], before["y"]))
    time.sleep(1.5)
    after = loop.run_until_complete(handle.js(
        "document.querySelectorAll('#annotate-list .annotate-row:not(.annotate-row-head)').length"))
    assert after < before["rows"], (
        f"folding the group changed nothing ({after} rows, was {before['rows']})"
    )


def test_the_editor_folds_away_and_the_canvas_refits(page) -> None:
    """A real click, because the toggle sits on the divider - which takes
    pointer capture for its drag and would otherwise swallow it."""
    loop, handle = page
    at = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('#btn-editor-toggle');
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))

    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(1)
    hidden = loop.run_until_complete(handle.js("""(() => ({
        folded: document.body.classList.contains('editor-hidden'),
        editorVisible: document.querySelector('#editor-pane').offsetParent !== null,
    }))()"""))
    assert hidden["folded"], "a real click on the toggle did nothing - the divider ate it"
    assert not hidden["editorVisible"], "the class is set but the editor is still on screen"

    # Read the position again: folding the editor moves the divider - and the
    # button on it - to the left edge.
    moved = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#btn-editor-toggle').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert moved["x"] < at["x"], "the divider did not move, so the editor is still taking space"

    loop.run_until_complete(handle.click(moved["x"], moved["y"]))
    time.sleep(1)
    back = loop.run_until_complete(handle.js(
        "document.querySelector('#editor-pane').offsetParent !== null"))
    assert back, "the editor did not come back"
