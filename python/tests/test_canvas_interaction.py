"""Can the canvas actually be clicked?"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request

import pytest

from tests.conftest import *  # noqa: F401,F403 - shared example lookup

pytest.importorskip("websockets")

from test_canvas_renders import STATIC, _browser, _free_port, served  # noqa: E402,F401

from conftest import AGENT_NS, GRAPH_RAG_NS, TARIFF_NS, WIEN_ENERGIE_NS, example_path  # noqa: E402

pytestmark = pytest.mark.browser


def _example(namespace: str) -> str:
    """The name /api/examples answers to, found by the IRI the graph mints
    under rather than by what the file is called today. These probes name their
    examples in JavaScript, so they cannot call example_path directly - and a
    rename that renumbered the files last time silently paired the tariff
    architecture with the chatbot process, which refines neither of its
    systems. Every activity then looked unrefined and eight tests failed on
    "descending narrowed to nothing"."""
    return example_path(namespace).stem

CDP_PORT_TRIES = 6


def _load_example_probe() -> str:
    """A copy of the app that loads the whole scene on its own - two
    architectures and the process that runs both - so the driver only clicks."""
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <script>
  window.addEventListener("load", async () => {
    const nl = String.fromCharCode(10,10);
    const a = await (await fetch("/api/examples/RAG")).json();
    const m = await (await fetch("/api/examples/ARCH")).json();
    const p = await (await fetch("/api/examples/energy_customer_service")).json();
    window.PairAI.Editor.setValue(a.ttl + nl + m.ttl + nl + p.ttl);
  });
  </script>
""".replace("RAG", _example(GRAPH_RAG_NS)).replace("ARCH", _example(WIEN_ENERGIE_NS))
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
    """A headless browser on the business level of the real app, driveable with real input."""
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
    # Wait for the scene this fixture promises rather than trusting the sleeps
    # above: under load the server's first graph request outlasts them, and the
    # first test then finds an empty canvas. A scene that never renders still
    # fails that test with its own message.
    _settle(loop, handle,
            "document.querySelector('.pc-activity.refined .pc-box') ? 1 : 0", 0, tries=150)
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


def _chip(loop, handle):
    """The blue "AI system" chip - the one way down to the architecture."""
    return loop.run_until_complete(handle.js("""(() => {
        const c = document.querySelector('.pc-activity.refined .pc-open');
        if (!c) return null;
        const r = c.getBoundingClientRect();
        return { left: r.left, top: r.top, width: r.width, height: r.height };
    })()"""))


def _descend(loop, handle):
    """Open the architecture the way a reader now has to: by asking for it."""
    chip = _chip(loop, handle)
    assert chip, "no refined activity offered a chip to descend through"
    loop.run_until_complete(handle.click(
        round(chip["left"] + chip["width"] / 2), round(chip["top"] + chip["height"] / 2)))
    return chip


def _descend_from(loop, handle, label):
    """Descend from a named activity rather than from whichever one is drawn first."""
    chip = loop.run_until_complete(handle.js(f"""(() => {{
        const box = [...document.querySelectorAll('.pc-activity.refined')]
            .find((a) => (a.textContent || '').includes({label!r}));
        const c = box && box.querySelector('.pc-open');
        if (!c) return null;
        const r = c.getBoundingClientRect();
        return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
    }})()"""))
    assert chip, f"no refined activity named {label!r} to descend from"
    loop.run_until_complete(handle.click(chip["x"], chip["y"]))
    return chip


def _open_palette(loop, handle):
    """Unfold the palette if this viewport folded it."""
    return loop.run_until_complete(handle.js("""(() => {
        const host = document.querySelector('#process-palette');
        if (!host) return 0;
        if (!host.querySelector('.pp-item')) {
            const fold = host.querySelector('.pp-fold');
            if (fold) fold.click();
        }
        return host.querySelectorAll('.pp-item').length;
    })()"""))


def _fold_palette(loop, handle):
    """Give the diagram the whole canvas."""
    loop.run_until_complete(handle.js("""(() => {
        const host = document.querySelector('#process-palette');
        if (host && host.querySelector('.pp-item')) host.querySelector('.pp-fold').click();
        return 1;
    })()"""))
    time.sleep(0.5)


@pytest.fixture
def scene_restored(page):
    """Put the document back, whatever happened to the test."""
    loop, handle = page
    saved = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))
    yield page
    loop.run_until_complete(handle.send("Runtime.evaluate", {
        "expression": "window.PairAI.Editor.setValue(" + json.dumps(saved) + ")",
        "returnByValue": True,
    }))
    _settle(loop, handle, "window.PairAI.Editor.getValue().length", 0, tries=40)
    # The level too, and the selection.
    loop.run_until_complete(handle.js(
        "window.PairAI.GraphView && window.PairAI.GraphView.selectSystem"
        " ? (window.PairAI.GraphView.selectSystem(null), 1) : 1"))
    _back_to_business(loop, handle)
    _settle(loop, handle,
            "document.querySelectorAll('#process-canvas .pc-pool').length", 0, tries=40)


def _add_from_palette(loop, handle, label):
    """Click a palette button by name."""
    _open_palette(loop, handle)
    at = loop.run_until_complete(handle.js(f"""(() => {{
        const b = [...document.querySelectorAll('#process-palette .pp-item')]
            .find((x) => x.textContent.trim() === {label!r});
        if (!b) return null;
        b.scrollIntoView({{ block: 'nearest' }});
        const r = b.getBoundingClientRect();
        return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
    }})()"""))
    assert at, f"the palette offers no {label}"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(2.5)


def _on_architecture(loop, handle):
    return loop.run_until_complete(
        handle.js('document.querySelector("#level-architecture").classList.contains("active")')
    )


def _settle(loop, handle, expression, unwanted, tries=20):
    """Wait for the page to finish, rather than guessing how long it takes."""
    for _ in range(tries):
        value = loop.run_until_complete(handle.js(expression))
        if value != unwanted:
            return value
        time.sleep(0.4)
    return loop.run_until_complete(handle.js(expression))


def _back_to_business(loop, handle):
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(1.5)


def test_the_chip_opens_the_architecture_and_the_box_does_not(page) -> None:
    """Descending is asked for, not stumbled into."""
    loop, handle = page
    box = _box(loop, handle)
    assert box, "no refined activity was drawn to click"

    loop.run_until_complete(handle.click(round(box["left"] + 30), round(box["top"] + 12)))
    assert not _on_architecture(loop, handle), (
        "the box still descends - reading a refined activity throws the reader a level down"
    )

    _descend(loop, handle)
    assert _on_architecture(loop, handle), "the chip did not open the architecture"
    _back_to_business(loop, handle)


def test_a_pool_collapses_to_a_band_and_opens_again(page) -> None:
    """BPMN's black-box pool."""
    loop, handle = page
    _back_to_business(loop, handle)

    before = loop.run_until_complete(handle.js("""(() => {
        const f = document.querySelector('.pc-pool .pc-pool-fold');
        const r = f.getBoundingClientRect();
        return {
            x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
            activities: document.querySelectorAll('#process-canvas .pc-activity').length,
        };
    })()"""))
    assert before["activities"] > 0, "nothing was drawn to collapse"

    loop.run_until_complete(handle.click(before["x"], before["y"]))
    time.sleep(0.8)
    folded = loop.run_until_complete(handle.js(
        'document.querySelectorAll("#process-canvas .pc-activity").length'))
    assert folded < before["activities"], (
        f"collapsing the pool drew the same {folded} activities"
    )

    # The band and its name stay: a collapsed pool is still a participant.
    kept = loop.run_until_complete(handle.js(
        'document.querySelectorAll("#process-canvas .pc-pool-label").length'))
    assert kept >= 1, "collapsing the pool took its name with it"

    at = loop.run_until_complete(handle.js("""(() => {
        const f = document.querySelector('.pc-pool .pc-pool-fold');
        const r = f.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(0.8)
    reopened = loop.run_until_complete(handle.js(
        'document.querySelectorAll("#process-canvas .pc-activity").length'))
    assert reopened == before["activities"], (
        f"reopening drew {reopened} activities against {before['activities']} before"
    )


def test_the_palette_folds_to_its_handle(page) -> None:
    """It went from seven buttons to twenty-four when it started offering the
    whole notation, and three rows of them sat over the diagram they are for."""
    loop, handle = page
    _back_to_business(loop, handle)

    shown = _open_palette(loop, handle)
    assert shown > 10, f"the palette is not offering the notation: {shown} buttons"

    at = loop.run_until_complete(handle.js("""(() => {
        const f = document.querySelector('#process-palette .pp-fold');
        const r = f.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(0.4)
    after = loop.run_until_complete(handle.js("""(() => ({
        items: document.querySelectorAll('#process-palette .pp-item').length,
        handle: Boolean(document.querySelector('#process-palette .pp-fold')),
    }))()"""))
    assert after["items"] == 0, "folding left the buttons on screen"
    assert after["handle"], "folding took the handle with it, so it cannot be unfolded"

    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(0.4)
    back = loop.run_until_complete(handle.js(
        'document.querySelectorAll("#process-palette .pp-item").length'))
    assert back == shown, f"unfolding gave back {back} buttons against {shown}"


def test_every_palette_button_draws_the_shape_it_inserts(page) -> None:
    """A row of words says a gateway is available; it does not say a gateway is
    a diamond, and the whole reason BPMN has a notation is that the shape
    carries the meaning."""
    loop, handle = page
    _back_to_business(loop, handle)
    _open_palette(loop, handle)

    seen = loop.run_until_complete(handle.js("""(() => {
        const items = [...document.querySelectorAll('#process-palette .pp-item')];
        return {
            total: items.length,
            withIcon: items.filter((b) => b.querySelector('svg.pp-icon')).length,
            gateways: items.filter((b) => b.querySelector('.pc-gate-box')).length,
            events: items.filter((b) => b.querySelector('.pc-ev-ring')).length,
            triggers: items.filter((b) => b.querySelector('.pc-ev-glyph')).length,
        };
    })()"""))

    assert seen["withIcon"] == seen["total"], (
        f"{seen['total'] - seen['withIcon']} palette buttons are words with no shape"
    )
    assert seen["gateways"] >= 4, f"the gateways are not drawn as diamonds: {seen}"
    assert seen["events"] >= 5, f"the events are not drawn as rings: {seen}"
    assert seen["triggers"] >= 3, f"no event button shows the trigger it carries: {seen}"


def test_a_connector_can_be_dragged_from_a_gateway(scene_restored) -> None:
    """Events and gateways carry a connector handle, and it can be grabbed."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    _fold_palette(loop, handle)

    ports = loop.run_until_complete(handle.js("""(() => {
        const rows = [];
        document.querySelectorAll('#process-canvas [data-node]').forEach((g) => {
            const dot = g.querySelector('.pc-port-dot');
            const r = dot ? dot.getBoundingClientRect() : null;
            rows.push({
                kind: String(g.getAttribute('class')).split(' ')[0],
                width: r ? Math.round(r.width) : 0,
            });
        });
        return rows;
    })()"""))
    kinds = {row["kind"] for row in ports}
    assert {"pc-gateway", "pc-event", "pc-activity"} <= kinds, (
        f"the scene does not draw all three node kinds: {kinds}"
    )
    for kind in ("pc-gateway", "pc-event", "pc-activity"):
        widths = [row["width"] for row in ports if row["kind"] == kind]
        assert widths and min(widths) >= 10, (
            f"the connector handle on a {kind} is {min(widths, default=0)}px across - "
            "too small to grab at this zoom"
        )

    # And it must be visible when the node is under the pointer.
    for kind in ("pc-gateway", "pc-event"):
        spot = loop.run_until_complete(handle.js(f"""(() => {{
            const g = document.querySelector('#process-canvas .{kind}');
            const r = g.getBoundingClientRect();
            return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
        }})()"""))
        loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": spot["x"], "y": spot["y"]}))
        time.sleep(0.3)
        shown = loop.run_until_complete(handle.js(
            f"getComputedStyle(document.querySelector('#process-canvas .{kind} .pc-port-dot'))"
            ".opacity"))
        assert shown == "1", f"hovering a {kind} does not reveal its connector handle"

    # Then drag one onto another node and check a flow was actually written.
    ends = loop.run_until_complete(handle.js("""(() => {
        const gw = document.querySelector('#process-canvas .pc-gateway');
        const dot = gw.querySelector('.pc-port-dot').getBoundingClientRect();
        const to = document.querySelector('#process-canvas .pc-activity .pc-box')
            .getBoundingClientRect();
        return {
            fromX: Math.round(dot.left + dot.width / 2),
            fromY: Math.round(dot.top + dot.height / 2),
            toX: Math.round(to.left + to.width / 2),
            toY: Math.round(to.top + to.height / 2),
        };
    })()"""))
    # Kept and put back: this writes to the document, and the page fixture is
    # shared with every test after it.
    before = loop.run_until_complete(handle.js(
        "window.PairAI.Editor.getValue().split('sequenceFlow').length"))
    loop.run_until_complete(
        handle.drag(ends["fromX"], ends["fromY"], ends["toX"], ends["toY"]))
    time.sleep(1.5)
    after = loop.run_until_complete(handle.js(
        "window.PairAI.Editor.getValue().split('sequenceFlow').length"))

    assert after > before, (
        f"dragging from a gateway wrote no sequence flow ({before} -> {after})"
    )


def test_clicking_empty_canvas_does_not_open_anything(page) -> None:
    """The other half of the same claim: the box means something, the space around it does not."""
    loop, handle = page
    box = _box(loop, handle)

    loop.run_until_complete(
        handle.click(round(box["left"] + box["width"] / 2), round(box["top"] + box["height"] + 60))
    )
    assert not _on_architecture(loop, handle), "empty canvas opened the architecture"


def test_dragging_the_canvas_is_not_a_click(page) -> None:
    """Panning ends in a click the reader did not mean."""
    loop, handle = page
    chip = _chip(loop, handle)
    assert chip, "no chip to let go over"
    target_x = round(chip["left"] + chip["width"] / 2)
    target_y = round(chip["top"] + chip["height"] / 2)

    loop.run_until_complete(handle.drag(target_x - 140, target_y, target_x, target_y))
    assert not _on_architecture(loop, handle), "a drag was treated as a click"


def test_the_risk_badge_folds_the_findings_it_counts(page) -> None:
    """A count alone is a number nobody can act on; the whole list at once is a wall."""
    loop, handle = page
    _back_to_business(loop, handle)
    _fold_palette(loop, handle)

    # Waited for, not slept through.
    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    _settle(loop, handle,
            'Number(document.querySelector("#findings-count").textContent || 0)', 0, tries=75)
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    _settle(loop, handle, 'document.querySelectorAll(".pc-risk").length', 0, tries=25)

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
    """"Open this activity" means the architecture behind it, not the other tab."""
    loop, handle = page

    # Widen first, deliberately.
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(2)
    whole = loop.run_until_complete(handle.js('document.querySelectorAll(".node").length'))
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(2)

    def spot(index):
        """Fresh coordinates each time: going back to the business level refits
        the canvas, so positions read before a round trip are stale."""
        return loop.run_until_complete(handle.js(f"""(() => {{
            const chips = document.querySelectorAll('.pc-activity.refined .pc-open');
            if (chips.length <= {index}) return null;
            const r = chips[{index}].getBoundingClientRect();
            return {{
                x: Math.round(r.left + r.width / 2),
                y: Math.round(r.top + r.height / 2),
                count: chips.length,
            }};
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
    """The "it gets stuck" report, reduced."""
    loop, handle = page
    _back_to_business(loop, handle)

    at = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('.pc-activity.refined .pc-box');
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + 30), emptyY: Math.round(r.bottom + 90) };
    })()"""))

    # A pan that ends over empty canvas, so no activity handler sees its click.
    loop.run_until_complete(handle.drag(at["x"] - 150, at["emptyY"], at["x"], at["emptyY"]))
    assert not _on_architecture(loop, handle), "the pan itself opened something"

    # The pan moved everything, so read the chip again rather than clicking
    # where it used to be - which is a mistake this test made first.
    _descend(loop, handle)
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

    # Waited for, not slept through: this scene is three graphs, and nine
    # seconds was enough on the machine this was written on and not on a busy
    # one - so it reported "nothing was found to narrow" for a run that had
    # simply not come back yet.
    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    everything = _settle(
        loop, handle,
        'Number(document.querySelector("#findings-count").textContent || 0)', 0, tries=75,
    )
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(2)

    assert everything > 0, "nothing was found to narrow"

    _descend(loop, handle)
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
    """Restore replaces the graph on screen, which is a commitment."""
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
    """The popup existed and was unreachable."""
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
    """The scene holds the graph-RAG chatbot and the Wien Energie architecture, because one business process runs both."""
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
    """A browser on the real page with nothing loaded - the opening screen."""
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


# What the workbench opens on.


def _library_state(loop, handle):
    return loop.run_until_complete(handle.js("""(() => ({
        open: !document.querySelector('#library').classList.contains('hidden'),
        lead: !document.querySelector('#library-lead').classList.contains('hidden'),
        risks: document.querySelectorAll('#library-list .lib-row').length,
        tiles: document.querySelectorAll('#library-detail .lib-tile').length,
        motifCards: document.querySelectorAll('#library-detail .lib-card').length,
        previews: document.querySelectorAll('#library-detail .motif-preview .shape').length,
    }))()"""))


def _spot(loop, handle, expression):
    """The middle of an element, in page coordinates, or None if it is not on
    screen - so a click is never sent at a shape that is not there."""
    return loop.run_until_complete(handle.js(f"""(() => {{
        const node = {expression};
        if (!node || node.offsetParent === null) return null;
        const r = node.getBoundingClientRect();
        return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
    }})()"""))


def test_the_library_is_what_the_workbench_opens_on(empty_workbench) -> None:
    """An empty canvas says nothing about what would be found on it."""
    loop, handle = empty_workbench

    opened = _library_state(loop, handle)
    assert opened["open"], "the workbench did not open on the library"
    assert opened["lead"], "the opening frame that explains motif and risk pattern is missing"
    assert opened["risks"] > 10, (
        f"the risk list has {opened['risks']} entries; the library holds 15 risk patterns"
    )
    assert opened["tiles"] > 10, "the opening panel does not show the catalogue"

    at = _spot(loop, handle,
               "[...document.querySelectorAll('#library-list .lib-row')]"
               ".find((r) => r.textContent.includes('Prompt injection'))")
    assert at, "no row for prompt injection in the risk list"
    loop.run_until_complete(handle.click(at["x"], at["y"]))

    picked = _library_state(loop, handle)
    assert picked["motifCards"] >= 3, (
        "prompt injection applies to three motifs and the panel drew "
        f"{picked['motifCards']} of them"
    )
    assert picked["previews"] > 0, (
        "the motifs are listed but not drawn - a reader cannot tell what structure "
        "would have to be present"
    )


def test_the_opening_choice_answers_a_real_click(empty_workbench) -> None:
    """The first thing anyone sees, and it was dead."""
    loop, handle = empty_workbench

    dismissed = _spot(loop, handle, "document.querySelector('#btn-library-close')")
    assert dismissed, "the library has no way out of it"
    loop.run_until_complete(handle.click(dismissed["x"], dismissed["y"]))

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


def test_a_motif_added_from_the_library_lands_on_the_canvas(empty_workbench) -> None:
    """The backward route, end to end: pick a risk, add the structure it applies
    to, and the editor holds an annotated graph the assessment can already read.

    The library stays open on purpose. Picking one risk usually means adding
    more than one motif, and being thrown onto the canvas after each would make
    that a round trip every time.

    Runs after the opening-choice test because it leaves content behind, and
    the question that test is about is only on screen while there is none.
    """
    loop, handle = empty_workbench

    reopen = _spot(loop, handle, "document.querySelector('#btn-library')")
    assert reopen, "the toolbar has no way back into the library"
    loop.run_until_complete(handle.click(reopen["x"], reopen["y"]))
    time.sleep(1)

    at = _spot(loop, handle,
               "[...document.querySelectorAll('#library-list .lib-row')]"
               ".find((r) => r.textContent.includes('Prompt injection'))")
    assert at, "no row for prompt injection in the risk list"
    loop.run_until_complete(handle.click(at["x"], at["y"]))

    add = _spot(loop, handle,
                "[...document.querySelectorAll('#library-detail .lib-card button')]"
                ".find((b) => b.textContent === 'Add to canvas')")
    assert add, "the motifs a risk applies to offer no way to add one"
    loop.run_until_complete(handle.click(add["x"], add["y"]))
    time.sleep(4)

    after = loop.run_until_complete(handle.js("""(() => ({
        ttl: window.PairAI.Editor.getValue(),
        drawn: document.querySelectorAll('#canvas .shape').length,
        stillOpen: !document.querySelector('#library').classList.contains('hidden'),
        said: document.querySelector('#library-status').textContent,
    }))()"""))

    assert "pair:playsRole" in after["ttl"], (
        "the motif was added without the roles it matches on, so nothing would bind"
    )
    assert after["drawn"] > 0, "the motif reached the editor but was never drawn"
    assert after["stillOpen"], "adding a motif closed the library"
    assert "Added" in after["said"], (
        "the library sits over the status bar and said nothing about what it did: "
        + after["said"]
    )


def test_a_new_example_forgets_the_scope_of_the_last_one(scene_restored) -> None:
    """Descend into an activity, then pick a plain architecture example."""
    loop, handle = scene_restored
    # Restored at the end: this test swaps the document out, and the page
    # fixture is shared with every test after it.
    _back_to_business(loop, handle)

    _descend(loop, handle)
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


    assert after["scoped"] is None, (
        f"the new example is still narrowed to {after['scoped']} from the previous one"
    )
    assert after["openedFrom"] is None, (
        f"the breadcrumb still names {after['openedFrom']}, an activity of the previous example"
    )
    assert not after["crumb"], "the breadcrumb is still on screen for a graph that has no process"


def test_annotate_narrows_with_the_rest_of_the_workbench(page) -> None:
    """Descending filtered the findings list and the canvas, but not this tab."""
    loop, handle = page
    _back_to_business(loop, handle)

    _descend(loop, handle)
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
    """The breadcrumb reset it and the level switch did not."""
    loop, handle = page
    _back_to_business(loop, handle)

    _descend(loop, handle)
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
        // The pane stays - as a rail. What must go is the code.
        codeVisible: document.querySelector('#editor').offsetParent !== null,
        paneWidth: Math.round(document.querySelector('#editor-pane').getBoundingClientRect().width),
    }))()"""))
    assert hidden["folded"], "a real click on the toggle did nothing - the divider ate it"
    assert not hidden["codeVisible"], "the class is set but the editor is still on screen"
    assert hidden["paneWidth"] < 60, (
        f"the pane is {hidden['paneWidth']}px wide - it folded to a rail, not to a panel"
    )

    # Folded, not gone: a panel that leaves no trace is one nobody goes looking
    # for. The rail says the editor is still there and is the way back.
    rail = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#editor-rail');
        const box = r.getBoundingClientRect();
        return { shown: r.offsetParent !== null, width: Math.round(box.width),
                 text: r.textContent.trim() };
    })()"""))
    assert rail["shown"], "the editor folded away completely, leaving nothing to click"
    assert rail["width"] > 0, "the rail has no width"
    assert "Editor" in rail["text"], f"the rail does not say what it is: {rail['text']!r}"

    # Read the position again: folding the editor moves the divider - and the
    # button on it - to the left edge.
    moved = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#btn-editor-toggle').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert moved["x"] < at["x"], "the divider did not move, so the editor is still taking space"

    # Open it from the rail rather than the chevron: that is what a reader who
    # folded it and forgot will click.
    at_rail = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#editor-rail').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + 60) };
    })()"""))
    loop.run_until_complete(handle.click(at_rail["x"], at_rail["y"]))
    time.sleep(1)
    back = loop.run_until_complete(handle.js("""(() => ({
        editor: document.querySelector('#editor-pane').offsetParent !== null,
        railHidden: document.querySelector('#editor-rail').offsetParent === null,
    }))()"""))
    assert back["editor"], "clicking the rail did not bring the editor back"
    assert back["railHidden"], "the rail is still showing beside the open editor"
    assert moved["x"] < at["x"], "the divider did not move, so the editor kept its space"


def test_starter_still_works_from_its_new_home_on_the_editor(page) -> None:
    """Starter and Clear moved out of the toolbar and onto the editor pane,
    because they act on what is in the pane rather than on the assessment.
    Moving markup is where handlers get orphaned, so this presses the button
    where it now lives."""
    loop, handle = page

    where = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('#btn-starter');
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return {
            insidePane: !!b.closest('#editor-pane'),
            inToolbar: !!b.closest('.toolbar'),
            x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
        };
    })()"""))
    assert where, "the Starter button is gone from the page entirely"
    assert where["insidePane"], "Starter is not on the editor pane"
    assert not where["inToolbar"], "Starter is still in the top toolbar as well"

    before = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue().length"))
    loop.run_until_complete(handle.click(where["x"], where["y"]))
    time.sleep(2)
    after = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))

    assert after, "Starter left the editor empty"
    assert len(after) != before, "a real click on Starter changed nothing - the handler is orphaned"
    assert "@prefix" in after, f"Starter did not load a graph: {after[:80]!r}"


def test_the_brand_goes_back_to_the_opening_question(scene_restored) -> None:
    """Clicking PAIR-AI starts over."""
    loop, handle = scene_restored

    # Empty the document without going through the confirm dialog, which would block a headless browser.
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue('')"))
    time.sleep(3)
    started = loop.run_until_complete(handle.js(
        "document.querySelector('#canvas-wrap').classList.contains('started')"))
    assert started, "the workbench is not in the started state, so there is nothing to undo"

    at = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#btn-home').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(2)

    seen = loop.run_until_complete(handle.js("""(() => {
        const wrap = document.querySelector('#canvas-wrap');
        const card = document.querySelector('#start-business');
        return {
            asking: wrap.classList.contains('unstarted'),
            started: wrap.classList.contains('started'),
            choiceVisible: card ? card.offsetParent !== null : false,
            levelSwitchHidden: document.querySelector('#level-switch').classList.contains('hidden'),
        };
    })()"""))

    assert seen["asking"], "the opening question did not come back"
    assert not seen["started"], "the workbench still thinks a choice has been made"
    assert seen["choiceVisible"], "the question is set but its cards are not on screen"
    assert seen["levelSwitchHidden"], "the level switch is still offered before a choice"



def test_motifs_and_data_flow_narrow_to_the_architecture_on_screen(page) -> None:
    """Descending narrows the motif list to the architecture on screen."""
    loop, handle = page
    # Load the scene itself rather than inheriting whatever the last test left.
    loop.run_until_complete(handle.js("""(async () => {
        const nl = String.fromCharCode(10, 10);
        const get = async (n) => (await (await fetch('/api/examples/' + n)).json()).ttl;
        const a = await get('RAG');
        const m = await get('ARCH');
        const p = await get('energy_customer_service');
        window.PairAI.Editor.setValue(a + nl + m + nl + p);
        return 1;
    })()""".replace("RAG", _example(GRAPH_RAG_NS)).replace("ARCH", _example(WIEN_ENERGIE_NS))))
    time.sleep(5)

    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(2)
    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    # Waited for, not slept through: this scene is three graphs and takes longer
    # than a single example, and a fixed sleep reads the render before it.
    # The budget is generous on purpose - the assessment behind it runs about
    # twenty seconds, and 40 tries (16s) read an empty list as "nothing matched".
    _settle(loop, handle, "document.querySelectorAll('#motifs-list .motif-row-name').length", 0,
            tries=120)
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(2)

    def listed():
        return loop.run_until_complete(handle.js("""(() => {
            const rows = [...document.querySelectorAll('#motifs-list .motif-row')];
            return {
                names: rows.map((r) => r.querySelector('.motif-row-name').textContent),
                total: rows.reduce((n, r) => {
                    const c = r.querySelector('.motif-row-count').textContent;
                    return n + (c.startsWith('×') ? Number(c.slice(1)) : 1);
                }, 0),
            };
        })()"""))

    everything = listed()
    assert everything["total"] > 0, "nothing matched, so there is nothing to narrow"
    assert any("Retrieval" in name or "RAG" in name for name in everything["names"]), (
        f"the chatbot's retrieval motifs are not listed even unscoped: {everything}"
    )

    # Named, not "the first one drawn": this test's claim is about an
    # architecture that does no retrieval, and the chatbot has one that does.
    _descend_from(loop, handle, "Domain classification")
    time.sleep(3)

    scoped = loop.run_until_complete(handle.js("""(() => ({
        system: window.PairAI.state.scopedSystem,
        badge: document.querySelector('#system-badge').textContent,
    }))()"""))
    narrowed = listed()

    assert scoped["system"], "descending narrowed to nothing, so there is no scope to respect"
    assert narrowed["total"], "the motifs tab lists nothing at all for the open architecture"
    assert narrowed["total"] < everything["total"], (
        f"the motifs tab showed {narrowed['total']} matches of {everything['total']} - "
        "it did not narrow to the architecture on screen"
    )
    assert "·" not in scoped["badge"], (
        f"more than one architecture is on screen while scoped: {scoped['badge']!r}"
    )
    _back_to_business(loop, handle)


def test_adding_the_first_participant_stays_on_the_business_layer(page) -> None:
    """Drawing a process from nothing threw you to the architecture."""
    loop, handle = page
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue('')"))
    time.sleep(3)
    loop.run_until_complete(handle.js('document.querySelector("#start-business").click()'))
    time.sleep(2)

    # An empty canvas is small, so the palette may have folded itself away.
    _open_palette(loop, handle)

    # The Participant button prompts for a name; answer it without a dialog.
    loop.run_until_complete(handle.js("""(() => {
        window.__realPrompt = window.prompt;
        window.prompt = () => "Customer";
    })()"""))
    at = loop.run_until_complete(handle.js("""(() => {
        const b = [...document.querySelectorAll('#process-palette .pp-item')]
            .find((x) => x.textContent.trim() === 'Participant');
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert at, "the business palette does not offer a Participant"

    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(5)
    loop.run_until_complete(handle.js("window.prompt = window.__realPrompt"))

    seen = loop.run_until_complete(handle.js("""(() => ({
        level: window.PairAI.state.level,
        pools: document.querySelectorAll('#process-canvas .pc-pool').length,
        businessActive: document.querySelector('#level-business').classList.contains('active'),
    }))()"""))
    assert seen["pools"] >= 1, "the participant was not drawn at all"
    assert seen["level"] == "business", (
        f"adding a participant moved the workbench to the {seen['level']} layer"
    )
    assert seen["businessActive"], "the level switch does not show business as current"


def test_three_lanes_on_a_new_participant_are_all_drawn(page) -> None:
    """An empty lane is the first thing a modeller draws."""
    loop, handle = page
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue('')"))
    time.sleep(3)
    loop.run_until_complete(handle.js('document.querySelector("#start-business").click()'))
    time.sleep(2)

    names = ["Wien Energie", "LLM Agent", "Customer Service Agent", "Customer Portal"]
    loop.run_until_complete(handle.js(f"""(() => {{
        window.__answers = {names!r};
        window.__i = 0;
        window.prompt = () => window.__answers[window.__i++];
    }})()"""))

    _add_from_palette(loop, handle, "Participant")
    for _ in range(3):
        _add_from_palette(loop, handle, "Lane")

    seen = loop.run_until_complete(handle.js("""(() => ({
        pools: document.querySelectorAll('#process-canvas .pc-pool').length,
        bands: document.querySelectorAll('#process-canvas .pc-lane-box').length,
        labels: [...document.querySelectorAll('#process-canvas .pc-lane-label')]
            .map((n) => n.textContent),
    }))()"""))

    assert seen["pools"] == 1, f"expected one participant, drew {seen['pools']}"
    assert seen["bands"] == 3, (
        f"three lanes were added and {seen['bands']} bands were drawn"
    )
    assert seen["labels"] == names[1:], (
        f"lanes stack as {seen['labels']}, not in the order they were added"
    )


def test_a_step_lands_in_the_lane_that_was_selected(page) -> None:
    """Clicking a lane must select that lane."""
    loop, handle = page
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue('')"))
    time.sleep(3)
    loop.run_until_complete(handle.js('document.querySelector("#start-business").click()'))
    time.sleep(2)

    names = ["Wien Energie", "LLM Agent", "Customer Service Agent", "Customer Portal"]
    loop.run_until_complete(handle.js(f"""(() => {{
        window.__answers = {names!r}; window.__i = 0;
        window.prompt = () => window.__answers[window.__i++];
    }})()"""))

    _add_from_palette(loop, handle, "Participant")
    for _ in range(3):
        _add_from_palette(loop, handle, "Lane")

    # Aim at the middle of the band, which is what a reader points at.
    target = loop.run_until_complete(handle.js("""(() => {
        const g = [...document.querySelectorAll('#process-canvas .pc-lane')]
            .find((l) => l.querySelector('.pc-lane-label').textContent === 'Customer Portal');
        if (!g) return null;
        const r = g.querySelector('.pc-lane-box').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert target, "the lane to aim at was not drawn"
    loop.run_until_complete(handle.click(target["x"], target["y"]))
    time.sleep(0.8)

    note = loop.run_until_complete(handle.js(
        "document.querySelector('#process-palette .pp-note').textContent"))
    assert "Customer Portal" in note, (
        f"clicking the lane did not select it - the palette says {note!r}"
    )

    _add_from_palette(loop, handle, "Task")

    landed = loop.run_until_complete(handle.js("""(() => {
        const act = document.querySelector('#process-canvas .pc-activity');
        if (!act) return { error: 'no step was added' };
        const r = act.querySelector('.pc-box').getBoundingClientRect();
        const mid = r.top + r.height / 2;
        const band = [...document.querySelectorAll('#process-canvas .pc-lane')].find((l) => {
            const b = l.querySelector('.pc-lane-box').getBoundingClientRect();
            return mid >= b.top && mid <= b.bottom;
        });
        return { band: band ? band.querySelector('.pc-lane-label').textContent : 'NONE' };
    })()"""))
    assert landed.get("band") == "Customer Portal", (
        f"the step was aimed at Customer Portal and was drawn in {landed}"
    )


def test_putting_something_in_a_lane_does_not_move_the_lane(page) -> None:
    """Lane order is a modelling choice, not a consequence of content."""
    loop, handle = page
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue('')"))
    time.sleep(3)
    loop.run_until_complete(handle.js('document.querySelector("#start-business").click()'))
    time.sleep(2)

    names = ["Wien Energie", "LLM Agent", "Customer Service Agent", "Customer Portal"]
    loop.run_until_complete(handle.js(f"""(() => {{
        window.__answers = {names!r}; window.__i = 0;
        window.prompt = () => window.__answers[window.__i++];
    }})()"""))
    _add_from_palette(loop, handle, "Participant")
    for _ in range(3):
        _add_from_palette(loop, handle, "Lane")

    def stacking():
        return loop.run_until_complete(handle.js("""(() => {
            return [...document.querySelectorAll('#process-canvas .pc-lane')]
                .map((g) => ({
                    label: g.querySelector('.pc-lane-label').textContent,
                    top: g.querySelector('.pc-lane-box').getBoundingClientRect().top,
                    handle: Boolean(g.querySelector('.pc-lane-edit')),
                }))
                .sort((a, b) => a.top - b.top);
        })()"""))

    before = stacking()
    assert [row["label"] for row in before] == names[1:], (
        f"lanes did not stack in the order they were added: {before}"
    )
    assert all(row["handle"] for row in before), (
        "a lane has no edit handle, so it cannot be renamed or deleted"
    )

    target = loop.run_until_complete(handle.js("""(() => {
        const g = [...document.querySelectorAll('#process-canvas .pc-lane')]
            .find((l) => l.querySelector('.pc-lane-label').textContent === 'Customer Portal');
        const r = g.querySelector('.pc-lane-box').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(target["x"], target["y"]))
    time.sleep(0.8)
    _add_from_palette(loop, handle, "Start")

    after = stacking()
    assert [row["label"] for row in after] == names[1:], (
        f"adding a start event reordered the lanes: {[r['label'] for r in after]}"
    )

    landed = loop.run_until_complete(handle.js("""(() => {
        const ev = document.querySelector('#process-canvas .pc-event');
        if (!ev) return 'no event was drawn';
        const r = ev.getBoundingClientRect();
        const mid = r.top + r.height / 2;
        const band = [...document.querySelectorAll('#process-canvas .pc-lane')].find((l) => {
            const b = l.querySelector('.pc-lane-box').getBoundingClientRect();
            return mid >= b.top && mid <= b.bottom;
        });
        return band ? band.querySelector('.pc-lane-label').textContent : 'NONE';
    })()"""))
    assert landed == "Customer Portal", f"the start event was drawn in {landed}"


def test_a_system_is_named_and_described_from_the_architecture_canvas(scene_restored) -> None:
    """An architecture has to be nameable where it is drawn."""
    loop, handle = scene_restored
    architecture = (
        '@prefix beam: <http://w3id.org/beam/core#> .' + chr(10)
        + '@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .' + chr(10)
        + '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .' + chr(10)
        + '@prefix ex:   <http://example.org/one-system#> .' + chr(10)
        + 'ex:Sys a beam:Element , beam:System ; rdfs:label "My system" ;' + chr(10)
        + '    beam:hasProcess ex:Step ; beam:hasResource ex:In .' + chr(10)
        + 'ex:In a beam:Element , beam:Data ; rdfs:label "In" ;' + chr(10)
        + '    pair:playsRole pair:UserInput .' + chr(10)
        + 'ex:Step a beam:Element , beam:Infer ; rdfs:label "Step" ;' + chr(10)
        + '    pair:playsRole pair:PredictionStep ;' + chr(10)
        + '    beam:use ex:In ; beam:produce ex:Out .' + chr(10)
        + 'ex:Out a beam:Element , beam:Data ; rdfs:label "Out" ;' + chr(10)
        + '    pair:playsRole pair:PredictionResult .' + chr(10)
    )
    loop.run_until_complete(handle.send("Runtime.evaluate", {
        "expression": "window.PairAI.Editor.setValue(" + json.dumps(architecture) + ")",
        "returnByValue": True,
    }))
    # Waited for, not slept through: the page fixture arrives with whatever the
    # last test left, and a fixed sleep asserted against the previous document.
    _settle(
        loop, handle,
        "((window.PairAI.state.lastGraph || {}).systems || []).length === 1", False, tries=60,
    )
    loop.run_until_complete(handle.js(
        'document.querySelector("#level-architecture").click()'))
    _settle(loop, handle,
            "document.querySelectorAll('#canvas .system-bound').length", 0, tries=40)

    # The frame has to exist - it is the only thing on the canvas that *is* the
    # system - but the element palette floats over the top-left of the canvas,
    # which is where its name is drawn, so the name is not a dependable target.
    # The badge always is, and both open the same editor.
    frame = loop.run_until_complete(handle.js(
        "document.querySelectorAll('#canvas .system-bound').length"))
    assert frame == 1, f"one architecture drew {frame} frames"

    handle_at = loop.run_until_complete(handle.js("""(() => {
        const name = document.querySelector('#system-badge .system-badge-name');
        if (!name) return null;
        const r = name.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert handle_at, "the system badge offers no name to click"
    loop.run_until_complete(handle.click(handle_at["x"], handle_at["y"]))
    time.sleep(0.8)
    panel = loop.run_until_complete(handle.js("""(() => {
        const box = document.querySelector('#node-detail');
        return {
            hidden: box.classList.contains('hidden'),
            heading: box.querySelector('h4') ? box.querySelector('h4').textContent : null,
            fields: ['#sd-label', '#sd-description', '#sd-context']
                .filter((sel) => box.querySelector(sel)).length,
        };
    })()"""))
    assert panel["heading"] == "AI system", f"the badge opened {panel}"
    assert not panel["hidden"], (
        "the editor opened and was hidden again by the same gesture"
    )
    assert panel["fields"] == 3, f"the editor is missing a field: {panel}"

    loop.run_until_complete(handle.js("""(() => {
        document.querySelector('#sd-label').value = 'Tariff conversation agent';
        document.querySelector('#sd-description').value = 'Answers the customer in chat.';
        document.querySelector('#sd-context').value = 'Public self-service portal.';
        return 1;
    })()"""))
    # Brought into view first.
    at = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('#sd-apply');
        b.scrollIntoView({ block: 'nearest' });
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(3)

    written = loop.run_until_complete(handle.js("""(() => {
        const ttl = window.PairAI.Editor.getValue();
        const system = (window.PairAI.state.lastGraph.systems || [])[0] || {};
        return {
            description: /beam:description/.test(ttl),
            context: /beam:context/.test(ttl),
            label: system.label,
            servedDescription: system.description,
        };
    })()"""))
    assert written["description"] and written["context"], (
        f"the description and context were not written to the graph: {written}"
    )
    assert written["label"] == "Tariff conversation agent", written
    assert written["servedDescription"] == "Answers the customer in chat.", (
        f"the description is not served back to the canvas: {written}"
    )



def test_a_selected_system_is_where_a_new_element_lands(scene_restored) -> None:
    """The architecture's pool."""
    loop, handle = scene_restored
    two = (
        '@prefix beam: <http://w3id.org/beam/core#> .' + chr(10)
        + '@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .' + chr(10)
        + '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .' + chr(10)
        + '@prefix ex:   <http://example.org/two-systems#> .' + chr(10)
        + 'ex:First a beam:System ; rdfs:label "Taxonomy Expansion" ;' + chr(10)
        + '    beam:hasProcess ex:Step ; beam:hasResource ex:In .' + chr(10)
        + 'ex:In a beam:Data ; rdfs:label "In" ; pair:playsRole pair:UserInput .' + chr(10)
        + 'ex:Step a beam:Transform ; rdfs:label "Step" ;' + chr(10)
        + '    pair:playsRole pair:RetrievalStep ;' + chr(10)
        + '    beam:use ex:In ; beam:produce ex:Out .' + chr(10)
        + 'ex:Out a beam:Data ; rdfs:label "Out" ;' + chr(10)
        + '    pair:playsRole pair:RetrievedContext .' + chr(10)
        + 'ex:Second a beam:System ; rdfs:label "LLM based retrieval" .' + chr(10)
    )
    loop.run_until_complete(handle.send("Runtime.evaluate", {
        "expression": "window.PairAI.Editor.setValue(" + json.dumps(two) + ")",
        "returnByValue": True,
    }))
    _settle(
        loop, handle,
        "((window.PairAI.state.lastGraph || {}).systems || []).length === 2", False, tries=60,
    )
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle,
            "document.querySelectorAll('#canvas .system-bound').length", 0, tries=40)

    frames = loop.run_until_complete(handle.js("""(() => {
        return [...document.querySelectorAll('#canvas .system-bound')].map((g) => {
            const box = g.querySelector('.system-bound-box').getBoundingClientRect();
            return {
                label: g.querySelector('.system-bound-label').textContent,
                empty: g.classList.contains('empty'),
                x: Math.round(box.left + box.width / 2),
                y: Math.round(box.top + box.height / 2),
            };
        });
    })()"""))
    assert len(frames) == 2, f"two systems drew {len(frames)} frames: {frames}"
    empty = next((f for f in frames if f["empty"]), None)
    assert empty, f"the system with nothing in it drew no frame: {frames}"
    assert empty["label"] == "LLM based retrieval"

    loop.run_until_complete(handle.click(empty["x"], empty["y"]))
    time.sleep(1)
    picked = loop.run_until_complete(handle.js("""(() => ({
        selected: [...document.querySelectorAll('#canvas .system-bound.selected')]
            .map((g) => g.querySelector('.system-bound-label').textContent),
        bar: document.querySelector('#system-badge').textContent,
    }))()"""))
    assert picked["selected"] == ["LLM based retrieval"], (
        f"clicking the frame did not select it: {picked}"
    )
    assert "adding to: LLM based retrieval" in picked["bar"], (
        f"the bar does not say where a new element goes: {picked['bar']!r}"
    )

    at = loop.run_until_complete(handle.js("""(() => {
        const b = [...document.querySelectorAll('.palette-item')]
            .find((x) => x.textContent.trim() === 'Data');
        if (!b) return null;
        b.scrollIntoView({ block: 'nearest' });
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert at, "the element palette offers no Data"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(3)

    members = loop.run_until_complete(handle.js("""(() => {
        const rows = (window.PairAI.state.lastGraph || {}).systems || [];
        const out = {};
        rows.forEach((s) => { out[s.label] = (s.members || []).length; });
        return out;
    })()"""))
    assert members.get("LLM based retrieval") == 1, (
        f"the element did not land in the selected system: {members}"
    )
    assert members.get("Taxonomy Expansion") == 2, (
        f"the element landed in the other system as well: {members}"
    )



def test_a_participant_can_be_deleted_from_the_canvas(page) -> None:
    """The delete op has handled a participant all along - it takes the process
    and its activities with it - but nothing on the canvas asked for it, so a
    pool added by mistake could only be removed by editing Turtle."""
    loop, handle = page
    pools = loop.run_until_complete(handle.js(
        "document.querySelectorAll('#process-canvas .pc-pool').length"))
    assert pools >= 1, "no participant on the canvas to delete"

    at = loop.run_until_complete(handle.js("""(() => {
        const e = document.querySelector('#process-canvas .pc-pool-edit');
        if (!e) return null;
        const r = e.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert at, "a participant offers no way to rename or delete it"

    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(1)
    opened = loop.run_until_complete(handle.js("""(() => {
        const p = document.querySelector('#process-detail');
        return { shown: !p.classList.contains('hidden'),
                 hasDelete: !!p.querySelector('#pd-pool-delete') };
    })()"""))
    assert opened["shown"], "the participant panel did not open"
    assert opened["hasDelete"], "the participant panel offers no Delete"

    loop.run_until_complete(handle.js('document.querySelector("#pd-pool-delete").click()'))
    time.sleep(5)
    after = loop.run_until_complete(handle.js(
        "document.querySelectorAll('#process-canvas .pc-pool').length"))
    assert after < pools, f"the participant is still on the canvas ({after} of {pools})"


def test_clicking_a_business_element_reveals_its_line(page) -> None:
    """A click on the business canvas had nowhere to go."""
    loop, handle = page
    before = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))
    try:
        loop.run_until_complete(handle.js("""(async () => {
            const nl = String.fromCharCode(10, 10);
            const a = await (await fetch("/api/examples/ARCH")).json();
            const p = await (await fetch("/api/examples/energy_customer_service")).json();
            window.PairAI.Editor.setValue(a.ttl + nl + p.ttl);
        })()""".replace("ARCH", _example(WIEN_ENERGIE_NS))))
        time.sleep(8)
        loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
        time.sleep(1)

        at = loop.run_until_complete(handle.js("""(() => {
            const a = document.querySelector('#process-canvas .pc-activity');
            if (!a) return null;
            const r = a.getBoundingClientRect();
            return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + 14) };
        })()"""))
        assert at, "no activity on the business canvas"

        marked = "document.querySelectorAll('#gutter .marked-line').length"
        # Start from no mark: an earlier test may have left one, and it would
        # satisfy the assertion below without this click resolving anything.
        loop.run_until_complete(handle.js("window.PairAI.Editor.revealLines([])"))
        assert loop.run_until_complete(handle.js(marked)) == 0

        loop.run_until_complete(handle.click(at["x"], at["y"]))
        time.sleep(2)
        business_marks = loop.run_until_complete(handle.js(marked))
        assert business_marks > 0, "clicking an activity marked no line in the editor"

        # And the architecture still resolves.
        loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
        time.sleep(1)
        loop.run_until_complete(handle.js("window.PairAI.GraphView.fit()"))
        time.sleep(1)
        node_at = loop.run_until_complete(handle.js("""(() => {
            const view = document.querySelector('#canvas').getBoundingClientRect();
            const lined = new Set((window.PairAI.state.lastGraph.nodes || [])
                .filter((x) => x.line).map((x) => x.id));
            for (const n of document.querySelectorAll('#canvas g.node')) {
                if (!lined.has(n.getAttribute('data-id'))) continue;
                const r = n.getBoundingClientRect();
                const x = Math.round(r.left + r.width / 2);
                const y = Math.round(r.top + r.height / 2);
                if (x > view.left + 4 && x < view.right - 4
                    && y > view.top + 4 && y < view.bottom - 4) return { x, y };
            }
            return null;
        })()"""))
        assert node_at, "no architecture node on the canvas"
        # Clear first: the business mark would otherwise satisfy the assertion
        # below without the architecture click resolving anything at all.
        loop.run_until_complete(handle.js("window.PairAI.Editor.revealLines([])"))
        assert loop.run_until_complete(handle.js(marked)) == 0
        loop.run_until_complete(handle.click(node_at["x"], node_at["y"]))
        time.sleep(2)
        assert loop.run_until_complete(handle.js(marked)) > 0, (
            "clicking an architecture node marked no line once a process was present"
        )
    finally:
        loop.run_until_complete(handle.js(
            f"window.PairAI.Editor.setValue({json.dumps(before)})"))
        time.sleep(4)


def _open_risk_level(loop, handle):
    """Load the agentic scene, assess it, and land on the risk level."""
    loop.run_until_complete(handle.js("""(async () => {
        const nl = String.fromCharCode(10, 10);
        const get = async (n) => (await (await fetch('/api/examples/' + n)).json()).ttl;
        window.PairAI.Editor.setValue(await get('AGENT') + nl + await get('DESK'));
        return 1;
    })()""".replace("AGENT", _example(AGENT_NS)).replace("DESK", "it_service_desk")))
    time.sleep(4)
    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    _settle(loop, handle,
            "(window.PairAI.state.lastAssessment && "
            "window.PairAI.state.lastAssessment.riskView) ? 1 : 0", 0, tries=120)
    loop.run_until_complete(handle.js('document.querySelector("#level-risk").click()'))
    time.sleep(2)
    # A selection survives a re-render on purpose - triage keeps the box you are
    # judging in view - so a helper that promises a known state has to clear it,
    # or the rail is still showing whatever the last test picked.
    loop.run_until_complete(handle.js(
        'window.PairAI.RiskCanvas.clearSelection(); '
        'document.querySelector("#level-risk").click(); 1'))
    time.sleep(1.5)
    drawn = loop.run_until_complete(handle.js('document.querySelectorAll(".rc-card").length'))
    assert drawn > 0, "the notation drew nothing, so there is nothing to drag"


def _card_centre(loop, handle, index=0):
    """A card to press: inside the canvas, and actually what a press there hits.

    The notation is wider than its pane, so a card can sit clipped outside it -
    and a press aimed at one lands on whatever is drawn over that spot instead.

    Scoped to the risk canvas. An activity carries the same data-node on the
    process canvas, so an unscoped lookup can answer with the hidden copy - and
    a hidden copy reports a zero rect, which reads as a box that did not move.
    """
    return loop.run_until_complete(handle.js(f"""(() => {{
        const view = document.querySelector('#risk-canvas').getBoundingClientRect();
        const cards = [...document.querySelectorAll('#risk-canvas .rc-card')].slice({index});
        for (const card of cards) {{
            const r = card.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            if (x < view.left || x > view.right || y < view.top || y > view.bottom) continue;
            const hit = document.elementFromPoint(x, y);
            if (hit && hit.closest('.rc-card') === card) {{
                return {{ id: card.getAttribute('data-node'), x, y }};
            }}
        }}
        return null;
    }})()"""))


def _pan(loop, handle):
    return loop.run_until_complete(handle.js(
        'document.querySelector("#rc-root").getAttribute("transform")'))


def test_the_risk_canvas_stops_panning_when_the_button_comes_up(page) -> None:
    """The stuck-drag bug, under real input.

    A pointer capture that is taken and never released leaves the canvas glued
    to the cursor: the reader lets go and the diagram keeps moving. Only real
    input finds it - a synthetic MouseEvent is delivered to whatever element it
    is aimed at, capture or no capture.
    """
    loop, handle = page
    _open_risk_level(loop, handle)

    # Somewhere on the background, clear of every box - checked, not assumed.
    empty = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#risk-canvas').getBoundingClientRect();
        for (let fy = 0.9; fy > 0.1; fy -= 0.1) {
            for (let fx = 0.1; fx < 0.9; fx += 0.1) {
                const x = Math.round(r.left + r.width * fx);
                const y = Math.round(r.top + r.height * fy);
                const at = document.elementFromPoint(x, y);
                if (at && at.closest('#risk-canvas') && !at.closest('[data-node]')) {
                    return { x, y, on: at.tagName };
                }
            }
        }
        return null;
    })()"""))
    assert empty, "no clear background to press on"

    before = _pan(loop, handle)
    loop.run_until_complete(handle.drag(empty["x"], empty["y"], empty["x"] + 120, empty["y"] - 60))
    panned = _pan(loop, handle)
    assert panned != before, "dragging the background did not pan the diagram"

    # The button is up. Moving now must change nothing.
    loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": empty["x"] + 300, "y": empty["y"] - 200, "buttons": 0,
    }))
    time.sleep(0.5)
    assert _pan(loop, handle) == panned, (
        "the diagram kept moving after the button came up - the pan is still "
        "holding a pointer capture it never released"
    )


def test_a_risk_box_can_be_repositioned_by_hand(page) -> None:
    """The notation is generated, and a reader still has to be able to tidy it.

    View-only: moving a box must not write anything into the graph - the
    diagram is derived, and a hand-placed card is a reading aid, not a claim.
    """
    loop, handle = page
    _open_risk_level(loop, handle)

    card = _card_centre(loop, handle)
    assert card, "no risk box is on screen to move"
    before = loop.run_until_complete(handle.js('window.PairAI.Editor.getValue().length'))

    loop.run_until_complete(handle.drag(card["x"], card["y"], card["x"] + 140, card["y"] + 90))
    # The id is an IRI, so the selector is built in Python and passed whole -
    # quoting it into a JS string literal by hand ends the literal at the IRI.
    selector = "#risk-canvas [data-node=%s]" % json.dumps(card["id"])
    moved = loop.run_until_complete(handle.js(f"""(() => {{
        const card = document.querySelector({json.dumps(selector)});
        if (!card) return null;
        const r = card.getBoundingClientRect();
        return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
    }})()"""))
    assert moved, "the box vanished from the diagram during the drag"

    assert abs(moved["x"] - (card["x"] + 140)) < 40, f"the box did not follow the pointer: {moved}"
    assert abs(moved["y"] - (card["y"] + 90)) < 40, f"the box did not follow the pointer: {moved}"
    assert loop.run_until_complete(handle.js('window.PairAI.Editor.getValue().length')) == before, (
        "moving a box edited the graph - the layout is a reading aid, not a claim"
    )

    # And it stays put when the diagram is drawn again.
    loop.run_until_complete(handle.js('window.PairAI.RiskCanvas.fit()'))
    time.sleep(0.5)
    again = loop.run_until_complete(handle.js(
        f"document.querySelector({json.dumps(selector)}) ? 1 : 0"))
    assert again == 1, "the box vanished when the diagram was redrawn"


def _press_a_candidate_risk(loop, handle):
    """Press a Risk box the library raised, rather than one a person drew."""
    at = loop.run_until_complete(handle.js("""(() => {
        const view = document.querySelector('#risk-canvas').getBoundingClientRect();
        const cards = [...document.querySelectorAll('.rc-card')].filter((c) =>
            c.querySelector('.rc-chip').textContent === 'Risk'
            && /^Candidate/.test(c.querySelector('.rc-title').textContent));
        for (const card of cards) {
            const r = card.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2);
            const y = Math.round(r.top + r.height / 2);
            // On screen, and actually the thing a press at that point would hit:
            // the diagram is wider than the pane at fit scale, so some boxes sit
            // outside it and a click there lands on whatever is underneath.
            if (x < view.left || x > view.right || y < view.top || y > view.bottom) continue;
            const hit = document.elementFromPoint(x, y);
            if (hit && hit.closest('.rc-card') === card) return { x, y };
        }
        return null;
    })()"""))
    assert at, "no candidate risk box is on screen to judge"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(0.6)



def test_a_risk_is_drawn_on_by_dragging_it_onto_what_it_is_about(page) -> None:
    """Assessing by hand, as a gesture rather than a form.

    The library covers a fraction of what an assessor wants to record, so what
    it cannot say still has to reach the graph. Dragging a shape from the
    palette onto an element writes it in the vocabulary a run emits - marked as
    the person's, and exported with everything else.

    Real input, because a drag with a drop target is exactly what a synthetic
    MouseEvent cannot stand in for: it is delivered wherever it is aimed.
    """
    loop, handle = page
    _open_risk_level(loop, handle)
    loop.run_until_complete(handle.js(
        'window.prompt = () => "Written by the drag test"; 1'))

    at = loop.run_until_complete(handle.js("""(() => {
        const item = document.querySelector('#risk-palette .pp-item[data-kind="risk"]');
        if (!item) return null;
        const view = document.querySelector('#risk-canvas').getBoundingClientRect();
        for (const box of document.querySelectorAll('#risk-canvas .rc-card')) {
            if (box.querySelector('.rc-chip').textContent !== 'System') continue;
            // The box, not the group: the group's rect takes in the type chip
            // painted above it, so its centre can fall in the gap between.
            const r = box.querySelector('rect.rc-box').getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            if (x < view.left || x > view.right || y < view.top || y > view.bottom) continue;
            if (document.elementFromPoint(x, y)?.closest('.rc-card') !== box) continue;
            const from = item.getBoundingClientRect();
            return {
                fromX: Math.round(from.left + from.width / 2),
                fromY: Math.round(from.top + from.height / 2),
                toX: x, toY: y,
                onto: box.getAttribute('data-node'),
            };
        }
        return null;
    })()"""))
    assert at, "no system is on screen to drop a risk onto"

    before = loop.run_until_complete(handle.js(
        'window.PairAI.state.lastAssessment.summary.riskFindingCount'))

    loop.run_until_complete(handle.drag(at["fromX"], at["fromY"], at["toX"], at["toY"]))
    written = _settle(loop, handle,
                      'window.PairAI.Editor.getValue().includes("Written by the drag test") ? 1 : 0',
                      0, tries=120)
    assert written == 1, "the drag wrote nothing into the graph"
    # The graph is edited at once; the notation follows the re-run it triggers.
    _settle(loop, handle, """[...document.querySelectorAll('#risk-canvas .rc-card')]
        .filter((c) => /Written by the drag test/.test(c.textContent)).length""", 0, tries=150)

    # Read it off the drawing, not off the Turtle: a system is serialized with
    # its description, so a regex bounded by the next full stop ends inside that
    # sentence. The attachment is a line somebody drew, so it is painted with a
    # hit path naming both ends - which is the same claim, and visible.
    state = loop.run_until_complete(handle.js("""(() => {
        const mine = [...document.querySelectorAll('#risk-canvas .rc-card')]
            .filter((c) => /Written by the drag test/.test(c.textContent));
        const id = mine.length ? mine[0].getAttribute('data-node') : null;
        return {
            attached: !!id && [...document.querySelectorAll('#risk-canvas .rc-link-hit')]
                .some((p) => p.getAttribute('data-from') === id
                          && p.getAttribute('data-to') === %s),
            drawn: mine.length,
            ghosts: document.querySelectorAll('.risk-ghost').length,
            highlights: document.querySelectorAll('.rc-drop').length,
            findings: window.PairAI.state.lastAssessment.summary.riskFindingCount,
        };
    })()""" % json.dumps(at["onto"])))

    assert state["attached"], "the risk was written but not hung off what it was dropped on"
    assert state["drawn"] >= 1, "a hand-written risk has to appear in the notation"
    assert state["ghosts"] == 0, "the drag ghost outlived the drop"
    assert state["highlights"] == 0, "the drop highlight was left on the target"
    # Writing a judgement detects nothing and hides nothing.
    assert state["findings"] == before


def test_a_tray_folds_when_its_head_is_actually_pressed(page) -> None:
    """The two trays over the risk canvas fold from their own head.

    Both heads answered element.click() and neither answered a mouse, because
    the architecture wrap underneath captured the pointer on pointerdown and
    every pointerup retargeted to it - so no click was ever composed. That is
    the retargeting the canvases are driven with real input to catch, and a
    synthetic event proves nothing about it.
    """
    loop, handle = page
    _open_risk_level(loop, handle)

    for head, tray, what in (("#btn-tools-fold", "#risk-tools", "the tools"),
                             ("#btn-side-fold", "#risk-side-tray", "the detail")):
        at = loop.run_until_complete(handle.js("""(() => {
            const h = document.querySelector('%s');
            if (!h) return null;
            const r = h.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            // Pressing where the head is not on top proves nothing either.
            const hit = document.elementFromPoint(x, y);
            return hit && hit.closest('%s') === h ? { x, y } : null;
        })()""" % (head, head)))
        assert at, f"{what} tray has no head a press would reach"

        loop.run_until_complete(handle.click(at["x"], at["y"]))
        folded = loop.run_until_complete(handle.js(
            "document.querySelector('%s').classList.contains('collapsed')" % tray))
        assert folded, f"a real press on its head did not fold {what}"

        loop.run_until_complete(handle.click(at["x"], at["y"]))
        back = loop.run_until_complete(handle.js("""(() => {
            const t = document.querySelector('%s');
            return { folded: t.classList.contains('collapsed'),
                     height: Math.round(t.getBoundingClientRect().height) };
        })()""" % tray))
        assert not back["folded"], f"{what} did not come back"
        assert back["height"] > 60, f"{what} came back as a head with nothing under it"


def test_a_drag_shows_what_is_being_dragged_even_with_nowhere_to_drop(page) -> None:
    """A gesture that displays nothing cannot be told from one that never began.

    The ghost used to be removed the instant nothing on screen would accept the
    kind - which is the first thing a reader tries, since a consequence needs a
    risk and an impact needs a consequence before either has anywhere to go. All
    that was left was a line in the status bar, read after the gesture.
    """
    loop, handle = page
    _open_risk_level(loop, handle)

    at = loop.run_until_complete(handle.js("""(() => {
        const item = document.querySelector('#risk-palette .pp-item[data-kind="impact"]');
        if (!item) return null;
        const r = item.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert at, "the hand-assessment palette offers no impact to drag"

    loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": at["x"], "y": at["y"],
        "button": "left", "clickCount": 1, "buttons": 1}))
    for step in range(1, 4):
        loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": at["x"] + 70 * step, "y": at["y"] + 45 * step,
            "button": "left", "buttons": 1}))
    time.sleep(0.3)

    mid = loop.run_until_complete(handle.js("""(() => {
        const g = document.querySelector('.risk-ghost');
        if (!g) return null;
        const r = g.getBoundingClientRect();
        return { text: g.textContent.trim(), width: Math.round(r.width),
                 band: g.classList.contains('band-impact'),
                 nowhere: g.classList.contains('nowhere'),
                 targets: document.querySelectorAll('#risk-canvas .rc-droppable').length };
    })()"""))
    assert mid, "nothing followed the cursor, so the drag showed the reader nothing"
    assert mid["text"] == "Impact", "the shape being dragged has to name what it is"
    assert mid["band"], "the ghost has to carry the colour of the box it writes"
    assert mid["width"] >= 80, "a label is not a box"
    if not mid["targets"]:
        assert mid["nowhere"], "with nowhere to land the ghost has to say so"

    loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": at["x"] + 210, "y": at["y"] + 135,
        "button": "left", "clickCount": 1, "buttons": 0}))
    time.sleep(0.5)
    left = loop.run_until_complete(handle.js("""(() => ({
        ghosts: document.querySelectorAll('.risk-ghost').length,
        marks: document.querySelectorAll('#risk-canvas .rc-droppable, #risk-canvas .rc-drop').length,
    }))()"""))
    assert left["ghosts"] == 0, "the ghost outlived the gesture"
    assert left["marks"] == 0, "the drop marks were left on the canvas"


def test_picking_a_concern_on_a_lens_lights_the_work_it_arises_in(page) -> None:
    """The process column used to stay dimmed whatever was picked.

    Process cards were linked only to the defined risk, so they sat two hops from
    every concern. The same lens is drawn on the overview, so this is that page's
    behaviour too. Drawing the lens is setup; the pick is a real press.
    """
    loop, handle = page
    _open_risk_level(loop, handle)
    drawn = loop.run_until_complete(handle.js("""(() => {
        const rows = window.PairAI.state.lastAssessment.riskView.byProcess.systems
            .filter((row) => row.lens.about.length
                && row.lens.process.some((p) => (p.concerns || []).length));
        if (!rows.length) return 0;
        window.PairAI.RiskCanvas.clearSelection();
        window.PairAI.RiskCanvas.renderLens(rows[0].lens);
        return document.querySelectorAll('.rc-card').length;
    })()"""))
    assert drawn, "no system on the scene has a lens with process points bearing on a concern"
    time.sleep(0.8)

    at = loop.run_until_complete(handle.js("""(() => {
        const view = document.querySelector('#risk-canvas').getBoundingClientRect();
        const why = [];
        for (const card of document.querySelectorAll('#risk-canvas .rc-card[data-node^="about:"]')) {
            const r = card.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            if (x < view.left || x > view.right || y < view.top || y > view.bottom) {
                why.push(`offscreen at ${x},${y}`);
                continue;
            }
            const hit = document.elementFromPoint(x, y);
            if (hit && hit.closest('.rc-card') === card) return { x, y };
            why.push(`covered at ${x},${y} by ` + (hit ? (hit.id || hit.getAttribute('class')) : 'nothing'));
        }
        return { why: why.join('; ') || 'no about: card is on the lens at all' };
    })()"""))
    assert at and at.get("x") is not None, (
        "no concern on the lens is on screen to pick: " + (at or {}).get("why", "")
    )
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(0.6)

    state = loop.run_until_complete(handle.js("""(() => {
        const proc = [...document.querySelectorAll('.rc-card')]
            .filter((c) => c.querySelector('.rc-chip')
                && /^(Activity|Data object|Human step)$/i.test(c.querySelector('.rc-chip').textContent));
        return {
            process: proc.length,
            lit: proc.filter((c) => !c.classList.contains('dim')).length,
            context: document.querySelectorAll('.rc-link.context').length,
            dimmed: document.querySelectorAll('.rc-card.dim').length,
        };
    })()"""))
    assert state["dimmed"] > 0, f"the pick did not narrow the lens at all: {state}"
    assert state["lit"] > 0, f"picking a concern left the whole process column dimmed: {state}"
    assert state["context"] > 0, f"and no line joins the concern to the work: {state}"


def test_pressing_a_box_without_moving_selects_it(page) -> None:
    """Drag and click are one gesture, told apart by distance. A press that goes
    nowhere has to still be a selection, or nothing on the diagram is readable."""
    loop, handle = page
    _open_risk_level(loop, handle)

    # A Risk box, not whichever card sorts first - an Impact box has a detail of
    # its own and none of the things this test is about.
    _press_a_candidate_risk(loop, handle)

    state = loop.run_until_complete(handle.js("""(() => {
        const rail = document.querySelector('#risk-side').textContent || '';
        return {
            dimmed: document.querySelectorAll('.rc-card.dim').length,
            total: document.querySelectorAll('.rc-card').length,
            why: /why/i.test(rail),
            leadsTo: /may lead to/i.test(rail),
            where: /where/i.test(rail),
        };
    })()"""))
    assert 0 < state["dimmed"] < state["total"], (
        f"pressing a box did not narrow the diagram to its chain: {state}"
    )
    # Everything the grouped list used to carry is now the detail of a pick.
    assert state["why"], "the satisfied condition is why it fired"
    assert state["leadsTo"], "and the harm it rolls up to is what it may lead to"
    assert state["where"], "and the evidence is where"


def test_a_risk_on_the_diagram_can_be_settled_and_reopened(page) -> None:
    """The extension point the vocabulary always declared and nothing ever wrote.

    Three risk patterns carry no structural escape at all, so a recorded
    judgement is the only disposition they have. It has to reach the graph,
    survive the re-run, and be reversible.
    """
    loop, handle = page
    _open_risk_level(loop, handle)
    # A judgement nobody can read back is not reviewable, so the page asks.
    loop.run_until_complete(handle.js(
        'window.prompt = () => "handled by the engineer approval"; 1'))

    _press_a_candidate_risk(loop, handle)
    accepted = loop.run_until_complete(handle.js("""(() => {
        const chip = [...document.querySelectorAll('.concern-triage .chip')]
            .find((b) => b.textContent === 'Accepted');
        if (!chip) return 0;
        chip.click();
        return 1;
    })()"""))
    assert accepted, "a risk box offered no disposition"

    settled = _settle(loop, handle,
                      "window.PairAI.state.lastAssessment.riskView.summary.settled", 0, tries=120)
    assert settled == 1, "settling one concern settles exactly one"
    assert loop.run_until_complete(handle.js(
        'window.PairAI.Editor.getValue().includes("TriageDecision")')), (
        "the judgement is written into the graph, not held in the page"
    )
    assert loop.run_until_complete(handle.js(
        'document.querySelectorAll(".rc-mark").length')) >= 1, (
        "and the diagram says so on the box"
    )

    # The rail redraws off the re-assessment, which lands after the count does -
    # so wait for the control rather than for the number.
    assert _settle(loop, handle,
                   "[...document.querySelectorAll('.concern-triage .chip')]"
                   ".some((b) => b.textContent === 'reopen') ? 1 : 0", 0, tries=60) == 1, (
        "a settled concern never offered a way back"
    )
    loop.run_until_complete(handle.js("""(() => {
        [...document.querySelectorAll('.concern-triage .chip')]
            .find((b) => b.textContent === 'reopen').click();
        return 1;
    })()"""))

    back = _settle(loop, handle,
                   "window.PairAI.state.lastAssessment.riskView.summary.settled", 1, tries=120)
    assert back == 0, "reopening did not put it back"
    assert not loop.run_until_complete(handle.js(
        'window.PairAI.Editor.getValue().includes("TriageDecision")')), (
        "reopening removes the decision rather than hiding it"
    )


# ---- taking a connector back out -------------------------------------------
#
# Both canvases could draw a line and neither could remove one, so a line drawn
# wrong cost the boxes at either end: deleting an element was the only thing
# that took its connectors with it. These two run last in the file because they
# edit the scene the other tests read.


def _reachable_line(loop, handle, canvas, hit_class):
    """A connector a press would actually land on.

    Both the midpoint and the topmost check matter. The diagram is wider than
    its pane so a line can sit clipped outside it, and connectors are painted
    under the boxes, so the middle of one can be covered by whatever crosses it.
    """
    return loop.run_until_complete(handle.js("""(() => {
        const view = document.querySelector('%s').getBoundingClientRect();
        for (const hit of document.querySelectorAll('%s %s')) {
            const len = hit.getTotalLength();
            if (!len) continue;
            const pt = hit.getPointAtLength(len / 2);
            const m = hit.getScreenCTM();
            const x = Math.round(m.a * pt.x + m.c * pt.y + m.e);
            const y = Math.round(m.b * pt.x + m.d * pt.y + m.f);
            if (x < view.left + 4 || x > view.right - 4) continue;
            if (y < view.top + 4 || y > view.bottom - 4) continue;
            if (document.elementFromPoint(x, y) !== hit) continue;
            return { x, y };
        }
        return null;
    })()""" % (canvas, canvas, hit_class)))


def _badge(loop, handle, canvas, disc_class):
    return loop.run_until_complete(handle.js("""(() => {
        const c = document.querySelector('%s %s');
        if (!c) return null;
        const r = c.getBoundingClientRect();
        const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
        const hit = document.elementFromPoint(x, y);
        // A control under a box is not a control.
        return { x, y, reachable: !!(hit && hit.closest('%s')) };
    })()""" % (canvas, disc_class, disc_class.rsplit('-', 1)[0])))


def test_an_architecture_connector_goes_without_the_elements_it_joined(page) -> None:
    """beam:use is drawn backwards on purpose - resource into process - and both
    use and produce have an inverse form that draws the same line. So the canvas
    sends the line as drawn and the server holds the table of what wrote it; a
    client guessing the triple gets it wrong in exactly one of the four cases,
    which is what the first attempt at this did."""
    loop, handle = page
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(2)

    before = loop.run_until_complete(handle.js("""(() => ({
        edges: document.querySelectorAll('#canvas .edge:not(.temp)').length,
        nodes: document.querySelectorAll('#canvas .node').length,
    }))()"""))
    assert before["edges"] > 0 and before["nodes"] > 0

    at = _reachable_line(loop, handle, "#canvas", ".edge-hit")
    assert at, "no connector on the architecture canvas is reachable to press"
    loop.run_until_complete(handle.click(at["x"], at["y"]))

    picked = loop.run_until_complete(handle.js("""(() => ({
        lines: document.querySelectorAll('#canvas .edge.picked').length,
        badges: document.querySelectorAll('#canvas .edge-drop').length,
    }))()"""))
    assert picked["lines"] == 1, "pressing a connector did not pick it"
    assert picked["badges"] == 1, "a picked connector has to offer to go"

    badge = _badge(loop, handle, "#canvas", ".edge-drop-disc")
    assert badge and badge["reachable"], "the remove badge is under something"
    loop.run_until_complete(handle.click(badge["x"], badge["y"]))
    _settle(loop, handle,
            "document.querySelectorAll('#canvas .edge:not(.temp)').length",
            before["edges"], tries=120)

    after = loop.run_until_complete(handle.js("""(() => ({
        edges: document.querySelectorAll('#canvas .edge:not(.temp)').length,
        nodes: document.querySelectorAll('#canvas .node').length,
    }))()"""))
    assert after["edges"] == before["edges"] - 1, (
        f"the connector did not go: {before} -> {after}"
    )
    assert after["nodes"] == before["nodes"], (
        "removing a connector took an element with it, which is the whole "
        f"thing this replaces: {before} -> {after}"
    )


def test_a_business_connector_goes_without_the_boxes_it_joined(page) -> None:
    """Same gesture on the process canvas, and the same guarantee.

    The badge is painted over everything rather than in the connector's own
    group: connectors are drawn under the boxes so a line never sits on one it
    only passes, which put the badge under a port dot where no press reached it.
    """
    loop, handle = page
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    time.sleep(3)

    before = loop.run_until_complete(handle.js("""(() => ({
        flows: document.querySelectorAll('#process-canvas .pc-seq').length,
        boxes: document.querySelectorAll('#process-canvas [data-node]').length,
    }))()"""))
    assert before["flows"] > 0 and before["boxes"] > 0

    at = _reachable_line(loop, handle, "#process-canvas", ".pc-flow-hit")
    assert at, "no connector on the business canvas is reachable to press"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    assert loop.run_until_complete(handle.js(
        "document.querySelectorAll('#process-canvas .pc-flow.picked').length")) == 1, (
        "pressing a connector did not pick it"
    )

    badge = _badge(loop, handle, "#process-canvas", ".pc-flow-drop-disc")
    assert badge and badge["reachable"], (
        "the remove badge is under something - connectors are painted below the "
        "boxes, so a badge left in that layer cannot be pressed"
    )
    loop.run_until_complete(handle.click(badge["x"], badge["y"]))
    _settle(loop, handle,
            "document.querySelectorAll('#process-canvas .pc-seq').length",
            before["flows"], tries=120)

    after = loop.run_until_complete(handle.js("""(() => ({
        flows: document.querySelectorAll('#process-canvas .pc-seq').length,
        boxes: document.querySelectorAll('#process-canvas [data-node]').length,
    }))()"""))
    assert after["flows"] == before["flows"] - 1, (
        f"the connector did not go: {before} -> {after}"
    )
    assert after["boxes"] == before["boxes"], (
        f"removing a connector took a box with it: {before} -> {after}"
    )
