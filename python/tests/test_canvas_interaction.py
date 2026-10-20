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


def _scene_js() -> str:
    """Load the whole scene: two architectures and the process that runs both."""
    return """(async () => {
    const nl = String.fromCharCode(10,10);
    const a = await (await fetch("/api/examples/RAG")).json();
    const m = await (await fetch("/api/examples/ARCH")).json();
    const p = await (await fetch("/api/examples/energy_customer_service")).json();
    window.PairAI.Editor.setValue(a.ttl + nl + m.ttl + nl + p.ttl);
    return 1;
  })()""".replace("RAG", _example(GRAPH_RAG_NS)).replace("ARCH", _example(WIEN_ENERGIE_NS))


def _load_example_probe() -> str:
    """A copy of the app that loads the scene on its own, so the driver only clicks."""
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = f"""
  <script>
  window.addEventListener("load", () => {_scene_js()});
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

    async def click(self, x, y, modifiers=0):
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
                    "modifiers": modifiers,
                },
            )
            await asyncio.sleep(0.12)
        await asyncio.sleep(0.7)

    async def hover(self, x, y):
        """A pointer move with no button down, which is what opens a submenu."""
        import asyncio

        await self.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y,
                                                     "button": "none", "buttons": 0})
        await asyncio.sleep(0.4)

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
    # A pan starts on empty canvas. Where 140px to the left lands depends on how the
    # diagram was fitted, and starting on a box drags the box onto its neighbour,
    # covering the chip every later test clicks.
    start = loop.run_until_complete(handle.js(f"""(() => {{
        for (const [dx, dy] of [[-140, 0], [-140, 60], [-140, -60], [-220, 0], [-140, 120], [-140, -120]]) {{
            const hit = document.elementFromPoint({target_x} + dx, {target_y} + dy);
            if (hit && hit.closest('#process-canvas') && !hit.closest('[data-node], .pc-pool-strip, .pc-lane-strip'))
                return [{target_x} + dx, {target_y} + dy];
        }}
        return null;
    }})()"""))
    assert start, "no empty canvas near the chip to start a pan from"

    loop.run_until_complete(handle.drag(start[0], start[1], target_x, target_y))
    assert not _on_architecture(loop, handle), "a drag was treated as a click"


def test_the_risk_badge_folds_the_findings_it_counts(page) -> None:
    """A count alone is a number nobody can act on; the whole list at once is a wall."""
    loop, handle = page
    _back_to_business(loop, handle)
    _fold_palette(loop, handle)

    # Waited for, not slept through.
    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    # as long as the finding-click test allows for the same assessment of the same scene
    _settle(loop, handle,
            'Number(document.querySelector("#findings-count").textContent || 0)', 0, tries=150)
    loop.run_until_complete(handle.js('document.querySelector("#level-business").click()'))
    _settle(loop, handle, 'document.querySelectorAll(".pc-risk").length', 0, tries=40)
    # Fitted first: an earlier test leaves its pan behind, and a badge panned
    # off the pane cannot be pressed however well it folds.
    loop.run_until_complete(handle.js('window.PairAI.ProcessCanvas.fit(); 1'))
    time.sleep(0.5)

    badge = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('.pc-risk .pc-risk-box');
        if (!b) return { why: 'no activity reported any candidate risk' };
        const r = b.getBoundingClientRect();
        const pane = document.querySelector('#process-canvas').getBoundingClientRect();
        const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
        if (x < pane.left || x > pane.right || y < pane.top || y > pane.bottom) {
            return { why: `the badge is off the pane at ${x},${y}` };
        }
        // What a press there would actually reach, not what is drawn there.
        const hit = document.elementFromPoint(x, y);
        if (!hit || !hit.closest('.pc-risk')) {
            return { why: 'the badge is under ' + (hit ? (hit.id || hit.getAttribute('class')) : 'nothing') };
        }
        return { x, y };
    })()"""))
    assert badge.get("x") is not None, badge.get("why")

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


def test_clicking_a_finding_shows_its_elements_on_screen(scene_restored) -> None:
    """A student clicked a finding and saw nothing: from the business level the
    evidence is on a canvas that is not drawn, and on the architecture level the
    opened drawer left the whole graph a few pixels high."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    found = _settle(loop, handle, 'document.querySelectorAll(".finding-card").length', 0, tries=150)
    assert found, "the assessment never listed a finding: " + str(loop.run_until_complete(handle.js(
        '[document.querySelector("#status-text").textContent,'
        ' document.querySelector("#findings-count").textContent,'
        ' document.querySelector("#btn-assess").disabled]')))
    def click_a_finding() -> dict:
        at = loop.run_until_complete(handle.js("""(() => {
            const head = document.querySelector(".finding-card .finding-head");
            head.scrollIntoView({ block: "nearest" });
            const r = head.getBoundingClientRect();
            return { x: Math.round(r.left + 20), y: Math.round(r.top + r.height / 2) };
        })()"""))
        loop.run_until_complete(handle.click(at["x"], at["y"]))
        # Waited for: from a narrowed scope the canvas is redrawn before it is marked.
        _settle(loop, handle, 'document.querySelectorAll("#canvas g.node.highlight").length',
                0, tries=30)
        return loop.run_until_complete(handle.js("""(() => {
            const c = document.querySelector("#canvas").getBoundingClientRect();
            const boxes = [...document.querySelectorAll("#canvas g.node.highlight .shape")]
                .map((s) => s.getBoundingClientRect());
            return {
                level: window.PairAI.state.level,
                marked: boxes.length,
                inView: boxes.filter((r) => r.left >= c.left - 1 && r.right <= c.right + 1
                    && r.top >= c.top - 1 && r.bottom <= c.bottom + 1).length,
                smallest: boxes.length ? Math.min(...boxes.map((r) => r.height)) : 0,
            };
        })()"""))

    # Then from a reader who opened one activity's architecture and went back
    # with the Business button, which keeps the scope: opening the level by hand
    # widens it, and the redraw used to wipe the highlight.
    for scoped in (False, True):
        if scoped:
            _descend(loop, handle)
            _back_to_business(loop, handle)
        seen = click_a_finding()
        case = "after opening one architecture" if scoped else "from the business level"
        assert seen["level"] == "architecture", f"{case}: the elements stayed on a hidden canvas"
        assert seen["marked"] > 0, f"{case}: no element was marked"
        assert seen["inView"] == seen["marked"], f"{case}: marked elements are off screen: {seen}"
        assert seen["smallest"] >= 12, f"{case}: marked elements are too small to see: {seen}"
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
            fields: ['#pd-name', '#pd-refines', '#pd-loop'].filter((s) => panel.querySelector(s)),
            // data is edited on the data box, not here
            dataRows: panel.querySelectorAll('.pd-data, #pd-data-add').length,
        };
    })()"""))

    assert not seen["hidden"], "clicking the activity did not open its editor"
    assert seen["display"] != "none", (
        "the editor opened but CSS hides it on the business level - which is the bug"
    )
    assert len(seen["fields"]) == 3, f"the editor is missing controls: {seen['fields']}"
    assert seen["dataRows"] == 0, "the activity editor still edits data, which the data box does"

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
        f"the risk list has {opened['risks']} entries; the library holds 29 risk patterns"
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
        starts: window.PairAI.Editor.getValue().slice(0, 70),
        status: (document.querySelector('#status-text') || {}).textContent,
        options: [...document.querySelectorAll('#example-select option')].map((o) => o.value).join(','),
        scoped: window.PairAI.state.scopedSystem,
        openedFrom: window.PairAI.state.openedFrom ? window.PairAI.state.openedFrom.label : null,
        crumb: !document.querySelector("#breadcrumb").classList.contains("hidden"),
    }))()"""))


    assert after["scoped"] is None, (
        f"the new example is still narrowed to {after['scoped']} from the previous one: {after}"
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
    """Starter moved out of the toolbar and onto the editor pane, because it
    acts on what is in the pane rather than on the assessment. Moving markup is
    where handlers get orphaned, so this presses the button where it now lives."""
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



def test_a_flow_between_two_systems_does_not_lay_one_frame_over_the_other(scene_restored) -> None:
    """A log one system writes feeds the other, which feeds back. Laid out as
    one chain, the second system's parts sat at both ends and its frame
    covered the first."""
    loop, handle = scene_restored
    looped = chr(10).join([
        '@prefix beam: <http://w3id.org/beam/core#> .',
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
        '@prefix ex:   <http://example.org/looped#> .',
        'ex:Expansion a beam:System ; rdfs:label "Expansion" ;',
        '    beam:hasProcess ex:Extract ; beam:hasResource ex:Taxonomy .',
        'ex:Extract a beam:Transform ; rdfs:label "Extract" ;',
        '    beam:use ex:Log ; beam:produce ex:Taxonomy .',
        'ex:Taxonomy a beam:Data ; rdfs:label "Taxonomy" .',
        'ex:Recommender a beam:System ; rdfs:label "Recommender" ;',
        '    beam:hasProcess ex:Record , ex:Recommend ;',
        '    beam:hasResource ex:Query , ex:Log , ex:Result .',
        'ex:Query a beam:Data ; rdfs:label "Query" .',
        'ex:Record a beam:Transform ; rdfs:label "Record" ;',
        '    beam:use ex:Query ; beam:produce ex:Log .',
        'ex:Log a beam:Data ; rdfs:label "Log" .',
        'ex:Recommend a beam:Infer ; rdfs:label "Recommend" ;',
        '    beam:use ex:Query , ex:Taxonomy ; beam:produce ex:Result .',
        'ex:Result a beam:Data ; rdfs:label "Result" .',
    ])
    loop.run_until_complete(handle.send("Runtime.evaluate", {
        "expression": "window.PairAI.Editor.setValue(" + json.dumps(looped) + ")",
        "returnByValue": True,
    }))
    _settle(
        loop, handle,
        "((window.PairAI.state.lastGraph || {}).systems || []).length === 2", False, tries=60,
    )
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle,
            "document.querySelectorAll('#canvas .system-bound').length", 0, tries=40)

    frames = loop.run_until_complete(handle.js("""(() =>
        [...document.querySelectorAll('#canvas .system-bound')].map((g) => {
            const r = g.querySelector('.system-bound-box');
            return {
                label: g.querySelector('.system-bound-label').textContent,
                x: Number(r.getAttribute('x')), y: Number(r.getAttribute('y')),
                w: Number(r.getAttribute('width')), h: Number(r.getAttribute('height')),
            };
        }))()"""))
    assert len(frames) == 2, f"two systems drew {len(frames)} frames: {frames}"
    a, b = frames
    apart = (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"]
             or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
    assert apart, f"one system's frame is drawn over the other's: {frames}"


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
    # The previous test's run would satisfy a wait for any run, so wait for this one.
    loop.run_until_complete(handle.js(
        'window.__runBefore = window.PairAI.state.lastAssessment; '
        'document.querySelector("#btn-assess").click(); 1'))
    _settle(loop, handle,
            "(!document.querySelector('#btn-assess').disabled && "
            "window.PairAI.state.lastAssessment && "
            "window.PairAI.state.lastAssessment !== window.__runBefore && "
            "window.PairAI.state.lastAssessment.riskView) ? 1 : 0", 0, tries=120)
    loop.run_until_complete(handle.js('document.querySelector("#level-risk").click()'))
    time.sleep(2)
    # A selection survives a re-render on purpose - triage keeps the box you are
    # judging in view - so a helper that promises a known state has to clear it,
    # or the rail is still showing whatever the last test picked. Assessing opens
    # the findings drawer, which leaves the canvas too short for a card to be pressed.
    loop.run_until_complete(handle.js(
        'window.PairAI.RiskCanvas.clearSelection(); '
        'if (!document.querySelector("#drawer").classList.contains("collapsed")) '
        'document.querySelector("#drawer-toggle").click(); '
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

    # The box is drawn by the drop and named on the box afterwards.
    _settle(loop, handle, 'document.querySelector("#risk-side input") ? 1 : 0', 0, tries=60)
    asked = loop.run_until_complete(handle.js("""(() => {
        const side = document.querySelector('#risk-side');
        return { picker: !!side.querySelector('select'),
                 field: !!side.querySelector('input'),
                 drawn: document.querySelectorAll('#risk-canvas .rc-card').length };
    })()"""))
    assert asked["drawn"] > 0, "the drop drew nothing before anything was named"
    assert asked["picker"] and asked["field"], (
        f"the box's editor does not offer the library and a name: {asked}"
    )
    loop.run_until_complete(handle.js("""(() => {
        document.querySelector('#risk-side input').value = 'Written by the drag test';
        [...document.querySelectorAll('#risk-side button')]
            .find((b) => b.textContent === 'Apply').click();
        return 1;
    })()"""))
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


def test_a_control_is_offered_on_what_somebody_wrote_and_on_each_candidate(page) -> None:
    """A control written by hand attaches to a risk somebody wrote, and to a
    candidate the run raised - recorded against its findings with
    pair:controlModifiesFinding, which clears nothing. What the run derived
    besides its risks, its sources and its suggested controls, is not a target.
    """
    loop, handle = page
    _open_risk_level(loop, handle)

    kinds = loop.run_until_complete(handle.js(
        "JSON.stringify([...document.querySelectorAll('#risk-palette .pp-item')]"
        ".map((n) => n.getAttribute('data-kind')))"))
    assert json.loads(kinds) == ["risk", "source", "consequence", "impact", "control"], (
        f"the hand palette offers {kinds}"
    )

    at = loop.run_until_complete(handle.js("""(() => {
        const item = document.querySelector('#risk-palette .pp-item[data-kind="control"]');
        if (!item) return null;
        const r = item.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert at, "the palette offers no control to drag"

    loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": at["x"], "y": at["y"],
        "button": "left", "clickCount": 1, "buttons": 1}))
    for step in range(1, 4):
        loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": at["x"] + 80 * step, "y": at["y"] + 30 * step,
            "button": "left", "buttons": 1}))
    time.sleep(0.3)

    offered = loop.run_until_complete(handle.js("""(() => {
        /* Stated and derived are told apart on the drawing itself: a person's
           claim is solid, what the run produced is dashed. */
        const stated = (card) =>
            card.querySelector('rect.rc-box').getAttribute('stroke-dasharray') === 'none';
        const cards = [...document.querySelectorAll('#risk-canvas .rc-card')];
        const marked = cards.filter((c) => c.classList.contains('rc-droppable'));
        const isRisk = (c) => c.querySelector('.rc-chip').textContent === 'Risk';
        return {
            marked: marked.length,
            statedMarked: marked.filter(stated).length,
            derivedConcerns: cards.filter((c) => isRisk(c) && !stated(c)).length,
            concernsMarked: marked.filter((c) => isRisk(c) && !stated(c)).length,
            otherDerivedMarked: marked.filter((c) => !isRisk(c) && !stated(c)).length,
            ghost: (document.querySelector('.risk-ghost') || {}).textContent || null,
        };
    })()"""))

    # Released back over the tray it came from: a drop on a box now writes one,
    # and this test is about what the drag offers, not about adding a control.
    loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": at["x"], "y": at["y"] + 40,
        "button": "left", "clickCount": 1, "buttons": 0}))
    time.sleep(0.5)

    assert offered["ghost"] == "Risk control", "the drag has to show what it is"
    assert offered["derivedConcerns"] > 0, (
        "this scene raises concerns, which is what makes the distinction testable"
    )
    assert offered["statedMarked"] > 0, "the scene states risks, and a control goes on them"
    assert offered["concernsMarked"] == offered["derivedConcerns"], (
        f"{offered['concernsMarked']} of {offered['derivedConcerns']} candidates were offered"
    )
    assert offered["otherDerivedMarked"] == 0, (
        "a derived source or suggested control was offered as a drop target"
    )

    left = loop.run_until_complete(handle.js(
        "document.querySelectorAll('.risk-ghost, #risk-canvas .rc-droppable').length"))
    assert left == 0, "the drag left its marks on the canvas"


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
        /* Along the line, not only at its middle. Connector hit paths are
           painted under the boxes - so that a press over a box belongs to the
           box - which means the midpoint of a line that runs under one is not
           reachable even though the line plainly is. */
        const along = [0.5, 0.3, 0.7, 0.15, 0.85];
        for (const hit of document.querySelectorAll('%s %s')) {
            const len = hit.getTotalLength();
            if (!len) continue;
            const m = hit.getScreenCTM();
            for (const at of along) {
                const pt = hit.getPointAtLength(len * at);
                const x = Math.round(m.a * pt.x + m.c * pt.y + m.e);
                const y = Math.round(m.b * pt.x + m.d * pt.y + m.f);
                if (x < view.left + 4 || x > view.right - 4) continue;
                if (y < view.top + 4 || y > view.bottom - 4) continue;
                if (document.elementFromPoint(x, y) !== hit) continue;
                return { x, y };
            }
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
        return { x, y, reachable: !!(hit && hit.closest('%s')),
                 covered: hit ? (hit.id || hit.getAttribute('class') || hit.tagName) : 'nothing' };
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
    assert badge and badge["reachable"], (
        f"the remove badge is under {badge and badge.get('covered')}")
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


def test_a_pool_is_restacked_by_dragging_its_name_strip(scene_restored) -> None:
    """Pools stacked in whatever order their names fell in, and nothing could
    move one: the reading order of the whole diagram was a side effect of naming.

    Dragged, not stepped through with buttons - the stack is a thing you arrange.
    The strip is the handle because it is the part of a band that is always
    there: a collapsed pool draws nothing else, and a press in the body is a pan
    across a diagram the reader meant to leave alone.
    """
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    _fold_palette(loop, handle)

    strips = loop.run_until_complete(handle.js("""(() => {
        const rows = [];
        document.querySelectorAll('#process-canvas .pc-pool').forEach((pool) => {
            const strip = pool.querySelector('.pc-pool-strip');
            if (!strip) return;
            const r = strip.getBoundingClientRect();
            rows.push({
                band: pool.getAttribute('data-band'),
                x: Math.round(r.left + r.width / 2),
                y: Math.round(r.top + r.height / 2),
                top: Math.round(r.top), bottom: Math.round(r.bottom),
            });
        });
        return rows;
    })()"""))
    assert len(strips) >= 2, f"this test needs two pools on screen, saw {len(strips)}"
    assert all(row["band"] for row in strips), "a band does not say which one it is"

    order_before = loop.run_until_complete(handle.js(
        "window.PairAI.state.lastProcess.participants.map((p) => p.id)"))
    first, second = strips[0], strips[1]

    # Grab the first pool's strip and carry it past the middle of the second.
    loop.run_until_complete(handle.drag(
        first["x"], first["y"], first["x"], second["bottom"] - 4))

    order_after = loop.run_until_complete(handle.js(
        "window.PairAI.state.lastProcess.participants.map((p) => p.id)"))
    assert order_after != order_before, (
        "dragging the name strip restacked nothing: "
        f"{order_before} unchanged"
    )
    assert order_after[0] == order_before[1] and order_after[1] == order_before[0], (
        f"the pool landed somewhere unasked for: {order_before} -> {order_after}"
    )

    # It is in the document, not just on screen: a hand-drawn stack has to
    # survive a reload, unlike a nudged box.
    ttl = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))
    assert "bandOrder" in ttl, "the new order was never written down"


def test_a_press_on_a_pool_body_still_pans(scene_restored) -> None:
    """The strip restacks; everything else is the canvas. Arming the restack on
    the whole band would make every pan across a pool reorder the diagram."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    _fold_palette(loop, handle)

    before = loop.run_until_complete(handle.js(
        "window.PairAI.state.lastProcess.participants.map((p) => p.id)"))
    spot = loop.run_until_complete(handle.js("""(() => {
        const pool = document.querySelector('#process-canvas .pc-pool');
        const box = pool.querySelector('.pc-pool-box').getBoundingClientRect();
        const strip = pool.querySelector('.pc-pool-strip').getBoundingClientRect();
        // Right of the name strip, and clear of anything drawn inside.
        const x = Math.round(strip.right + (box.right - strip.right) * 0.92);
        const y = Math.round(box.top + 6);
        const at = document.elementFromPoint(x, y);
        return { x, y, onBox: !!(at && at.closest('.pc-pool') && !at.closest('[data-node]')) };
    })()"""))
    if not spot["onBox"]:
        pytest.skip("no clear patch of pool body to press on at this size")

    loop.run_until_complete(handle.drag(spot["x"], spot["y"], spot["x"], spot["y"] + 120))
    after = loop.run_until_complete(handle.js(
        "window.PairAI.state.lastProcess.participants.map((p) => p.id)"))
    assert after == before, "a pan across a pool restacked the diagram"


def _wheel(loop, handle, x, y, delta=120):
    """A real wheel, not a dispatched event: the handler reads ev.target, and a
    synthetic one proves nothing about where the browser would route it."""
    loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
        "type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": delta,
    }))
    time.sleep(0.35)


def test_a_wheel_over_a_tray_scrolls_it_rather_than_zooming_the_canvas(page) -> None:
    """The palettes and the detail popup are children of the canvas wrap, and the
    wrap's wheel handler called preventDefault on everything that was not the
    business level. So the motif tray - 31 entries, taller than the viewport -
    could not be reached with a mouse at all, and the wheel zoomed instead."""
    loop, handle = page
    _descend(loop, handle)
    assert _on_architecture(loop, handle), "did not reach the architecture level"

    tray = loop.run_until_complete(handle.js("""(() => {
        const host = document.querySelector('#motif-palette');
        if (!host) return null;
        if (host.classList.contains('collapsed')) host.querySelector('.tray-head').click();
        // The families start folded; opened, they make the tray taller than its box.
        host.querySelectorAll('.motif-family:not(.open)').forEach((head) => head.click());
        const r = host.getBoundingClientRect();
        return {
            x: Math.round(r.left + r.width / 2),
            y: Math.round(r.top + r.height / 2),
            scrollable: host.scrollHeight > host.clientHeight + 4,
            top: host.scrollTop,
        };
    })()"""))
    assert tray, "the architecture level offers no motif tray"
    assert tray["scrollable"], (
        "the tray is not taller than its box, so this cannot test scrolling"
    )

    before = loop.run_until_complete(handle.js(
        "document.querySelector('#viewport').getAttribute('transform')"))

    _wheel(loop, handle, tray["x"], tray["y"])

    after = loop.run_until_complete(handle.js("""(() => ({
        top: document.querySelector('#motif-palette').scrollTop,
        transform: document.querySelector('#viewport').getAttribute('transform'),
    }))()"""))
    # Folded again: the page is shared, and the tray starts folded for the next test.
    loop.run_until_complete(handle.js("""(() => {
        document.querySelectorAll('#motif-palette .motif-family.open').forEach((h) => h.click());
        return 1;
    })()"""))

    assert after["top"] > tray["top"], (
        f"the wheel did not scroll the tray (scrollTop stayed {after['top']})"
    )
    assert after["transform"] == before, (
        "the wheel zoomed the canvas instead of scrolling the tray it was over"
    )


def test_the_term_picker_is_not_clipped_by_the_popup_it_opens_in(page) -> None:
    """The node popup is `overflow: auto` with a max height, so an absolutely
    positioned popover was clipped to about two rows that nothing could scroll.
    It is placed fixed from the trigger instead: fully on screen, taller than
    the popup that hosts it, and its list scrolls."""
    loop, handle = page
    _descend(loop, handle)
    assert _on_architecture(loop, handle), "did not reach the architecture level"

    # open the popup for a data element, then its role picker
    opened = loop.run_until_complete(handle.js("""(() => {
        const node = document.querySelector('#viewport g.node.data');
        if (!node) return 0;
        node.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
        node.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
        return 1;
    })()"""))
    assert opened, "no element on the architecture canvas to open"
    time.sleep(0.5)

    at = loop.run_until_complete(handle.js("""(() => {
        const add = document.querySelector('.node-detail .mp-add');
        if (!add) return null;
        const r = add.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert at, "the node popup offers no term picker"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(0.4)

    seen = loop.run_until_complete(handle.js("""(() => {
        const pop = document.querySelector('.node-detail .mp-pop');
        const host = document.querySelector('.node-detail');
        if (!pop || pop.classList.contains('hidden')) return null;
        const p = pop.getBoundingClientRect();
        const h = host.getBoundingClientRect();
        const list = pop.querySelector('.mp-list');
        return {
            height: Math.round(p.height),
            hostHeight: Math.round(h.height),
            onScreen: p.top >= 0 && p.bottom <= window.innerHeight + 1
                      && p.left >= 0 && p.right <= window.innerWidth + 1,
            categories: pop.querySelectorAll('.mp-list > .mp-row.folder').length,
            fixed: getComputedStyle(pop).position === 'fixed',
        };
    })()"""))
    assert seen, "the picker did not open in the node popup"

    assert seen["fixed"], "the popover is still positioned inside the clipping popup"
    assert seen["onScreen"], "the popover is placed partly off screen"
    assert seen["categories"] >= 5, f"only {seen['categories']} categories are offered"

    # typed into, the menu becomes one list, which is the one that has to scroll
    narrowed = loop.run_until_complete(handle.js("""(() => {
        const pop = document.querySelector('.node-detail .mp-pop');
        const search = pop.querySelector('.mp-search');
        search.value = 'a';
        search.dispatchEvent(new Event('input', { bubbles: true }));
        const list = pop.querySelector('.mp-list');
        return { options: pop.querySelectorAll('.mp-opt').length,
                 overflows: list.scrollHeight > list.clientHeight + 4 };
    })()"""))
    assert narrowed["options"] > 10, f"only {narrowed['options']} terms are reachable"
    assert narrowed["overflows"], "the list does not overflow, so scrolling is untested"

    scrolled = loop.run_until_complete(handle.js("""(() => {
        const list = document.querySelector('.node-detail .mp-pop .mp-list');
        list.scrollTop = 120;
        return list.scrollTop;
    })()"""))
    assert scrolled > 0, "the option list cannot be scrolled"


def test_the_motif_tray_is_shelved_by_the_kind_of_system_each_is_a_shape_of(page) -> None:
    """31 motifs in one alphabetical column said nothing about what each one is
    for. The tray shelves them the way the library does, by `pair:motifFamily`,
    which is a filing decision about this library and is read by no match query.
    """
    loop, handle = page
    _descend(loop, handle)
    assert _on_architecture(loop, handle), "did not reach the architecture level"

    seen = loop.run_until_complete(handle.js("""(() => {
        const host = document.querySelector('#motif-palette');
        if (!host) return null;
        if (host.classList.contains('collapsed')) host.querySelector('.tray-head').click();
        const heads = [...host.querySelectorAll('.motif-family')];
        return {
            families: heads.map((h) => h.firstChild.textContent),
            counts: heads.map((h) => Number(h.querySelector('.motif-family-count').textContent)),
            items: host.querySelectorAll('.motif-item').length,
        };
    })()"""))
    assert seen, "the architecture level offers no motif tray"

    from test_canvas_renders import _library

    library = _library()
    assert seen["items"] == library["motifs"], f"the tray lists {seen['items']} motifs"
    assert seen["families"] == list(library["families"]), seen["families"]
    assert seen["counts"] == list(library["families"].values()), seen["counts"]
    assert sum(seen["counts"]) == seen["items"], "a motif is shelved twice or not at all"


def test_a_part_dragged_past_its_frame_takes_the_frame_with_it(page) -> None:
    """The dashed frame says which architecture a part belongs to, so moving a
    part must stretch the frame round it rather than leave it outside. It was
    measured before the moved positions were applied."""
    loop, handle = page
    _open_risk_level(loop, handle)
    loop.run_until_complete(handle.js(
        'document.querySelector("#risk-canvas .rc-unfold")'
        '.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })); 1'))
    time.sleep(1.2)
    start = loop.run_until_complete(handle.js("""(() => {
        const view = document.querySelector('#risk-canvas').getBoundingClientRect();
        const frames = [...document.querySelectorAll('#risk-canvas .rc-frame-box')]
            .map((f) => f.getBoundingClientRect());
        for (const part of document.querySelectorAll('#risk-canvas .rc-flow')) {
            const r = part.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            if (x < view.left || x > view.right || y < view.top || y > view.bottom) continue;
            const hit = document.elementFromPoint(x, y);
            if (!hit || hit.closest('.rc-flow') !== part) continue;
            const frame = frames.find((f) => r.left >= f.left && r.right <= f.right);
            if (frame) return { id: part.getAttribute('data-node'), x, y,
                                width: Math.round(frame.width), right: Math.round(frame.right),
                                partWidth: Math.round(r.width) };
        }
        return null;
    })()"""))
    assert start, "no part of an unfolded system could be pressed"

    # Far enough that the part's left edge ends beyond where the frame stood.
    target_x = start["right"] + start["partWidth"]
    loop.run_until_complete(handle.drag(start["x"], start["y"], target_x, start["y"]))
    after = loop.run_until_complete(handle.js(f"""(() => {{
        const part = [...document.querySelectorAll('#risk-canvas .rc-flow')]
            .find((p) => p.getAttribute('data-node') === {json.dumps(start["id"])});
        const r = part.getBoundingClientRect();
        const frames = [...document.querySelectorAll('#risk-canvas .rc-frame-box')]
            .map((f) => f.getBoundingClientRect());
        const holding = frames.find((f) => r.left >= f.left - 1 && r.right <= f.right + 1
            && r.top >= f.top - 1 && r.bottom <= f.bottom + 1);
        return {{ moved: Math.round(r.left + r.width / 2), framed: !!holding,
                  width: holding ? Math.round(holding.width) : 0 }};
    }})()"""))
    loop.run_until_complete(handle.js("window.PairAI.RiskCanvas.forgetLayout(); 1"))

    assert after["moved"] > start["right"], f"the part did not move past the frame: {after}"
    assert after["framed"], "the part was dragged out of the frame of its own architecture"
    assert after["width"] > start["width"], "the frame did not grow to hold it"


def test_a_consequence_dropped_on_a_candidate_is_recorded_against_its_findings(page) -> None:
    """What partners add to a candidate in an experiment has to be kept, so the
    run's own risk boxes take a consequence the way a hand-drawn risk does."""
    loop, handle = page
    _open_risk_level(loop, handle)
    aim = loop.run_until_complete(handle.js("""(() => {
        const view = window.PairAI.state.lastAssessment.riskView;
        const keys = new Set(view.groups.map((g) => g.key));
        const pane = document.querySelector('#risk-canvas').getBoundingClientRect();
        for (const card of document.querySelectorAll('#risk-canvas .rc-card')) {
            if (!keys.has(card.getAttribute('data-node'))) continue;
            const r = card.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            if (x < pane.left || x > pane.right || y < pane.top || y > pane.bottom) continue;
            const hit = document.elementFromPoint(x, y);
            if (hit && hit.closest('.rc-card') === card) {
                const item = document.querySelector('#risk-palette .pp-item[data-kind="consequence"]')
                    .getBoundingClientRect();
                return { key: card.getAttribute('data-node'), x, y,
                         fromX: Math.round(item.left + 12), fromY: Math.round(item.top + 10) };
            }
        }
        return null;
    })()"""))
    assert aim, "no candidate risk box could be dropped on"

    loop.run_until_complete(handle.drag(aim["fromX"], aim["fromY"], aim["x"], aim["y"]))
    time.sleep(2.5)
    seen = loop.run_until_complete(handle.js(f"""(() => {{
        const ttl = window.PairAI.Editor.getValue();
        const lines = [...document.querySelectorAll('#risk-canvas .rc-edge-label')]
            .filter((t) => t.textContent === 'hasConsequence').length;
        return {{ recorded: /findingHasConsequence/.test(ttl),
                  asStatedRisk: /beamr:hasConsequence/.test(ttl), lines }};
    }})()"""))

    assert seen["recorded"], "the consequence was not recorded against the candidate's findings"
    assert not seen["asStatedRisk"], "a finding was written as though it were a stated risk"
    assert seen["lines"] >= 1, "the consequence is not drawn on the candidate"

    # And the candidate's own panel says what was added to it.
    loop.run_until_complete(handle.js(
        "window.PairAI.RiskCanvas.select(" + json.dumps(aim["key"]) + "); 1"))
    loop.run_until_complete(handle.js(
        "document.querySelector('#level-risk').click(); 1"))
    time.sleep(1.2)
    panel = loop.run_until_complete(handle.js(
        "(document.querySelector('#risk-side') || {}).textContent || ''"))
    assert "added by hand" in panel, f"the candidate's panel does not show it: {panel[:200]!r}"


_SYNTHETIC_RISKS = """window.__risks = (n) => {
    const S = "urn:s";
    const nodes = [{ id: S, band: "system", title: "System", isSystem: true,
                     origin: "stated", systems: [S] }];
    const links = [];
    for (let i = 1; i <= n; i += 1) {
        nodes.push({ id: "urn:r" + i, band: "risk", title: "Risk " + i,
                     origin: "stated", systems: [S] });
        links.push({ source: "urn:r" + i, target: S, kind: "attaches", label: "hasRisk" });
    }
    document.querySelector("#risk-canvas-empty").classList.add("hidden");
    window.PairAI.RiskCanvas.render({ nodes, links, bands: [] },
        { systems: [{ id: S, members: [] }], nodes: [], edges: [] }, { keepView: true });
    return n;
}; 1"""


def test_a_risk_added_after_a_drag_does_not_land_on_the_dragged_box(page) -> None:
    """A dragged box keeps its place while the layout around it moves, so the
    next risk added was laid out right on top of it and the diagram had to be
    untangled by hand."""
    loop, handle = page
    loop.run_until_complete(handle.js('document.querySelector("#level-risk").click()'))
    time.sleep(1.5)
    try:
        loop.run_until_complete(handle.js(_SYNTHETIC_RISKS))
        loop.run_until_complete(handle.js(
            "window.PairAI.RiskCanvas.forgetLayout(); window.__risks(4);"
            " window.PairAI.RiskCanvas.fit(); 1"))
        time.sleep(0.5)
        first = loop.run_until_complete(handle.js("""(() => {
            const r = document.querySelector('#risk-canvas .rc-card[data-node="urn:r1"]')
                .getBoundingClientRect();
            return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
                     w: r.width, h: r.height };
        })()"""))
        # Down one line: where a fifth risk wraps to, four to a row.
        below = round(first["y"] + first["h"] + 26 * first["w"] / 210)
        loop.run_until_complete(handle.drag(first["x"], first["y"], first["x"], below))
        loop.run_until_complete(handle.js("window.__risks(5)"))
        time.sleep(0.5)
        seen = loop.run_until_complete(handle.js("""(() => {
            const cards = [...document.querySelectorAll('#risk-canvas .rc-card')].map((g) => {
                const r = g.getBoundingClientRect();
                return { id: g.getAttribute('data-node'), x: r.left, y: r.top, w: r.width, h: r.height };
            });
            const moved = cards.find((c) => c.id === 'urn:r1');
            const hits = [];
            cards.forEach((a, i) => cards.slice(i + 1).forEach((b) => {
                if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) {
                    hits.push(a.id + ' x ' + b.id);
                }
            }));
            return { cards: cards.length, movedY: Math.round(moved.y + moved.h / 2), hits };
        })()"""))
    finally:
        loop.run_until_complete(handle.js("window.PairAI.RiskCanvas.forgetLayout(); 1"))
        _back_to_business(loop, handle)

    assert seen["cards"] == 6
    assert abs(seen["movedY"] - below) <= 2, f"the drag did not move the box: {seen}"
    assert seen["hits"] == [], f"a box was laid out on top of another: {seen['hits']}"


def test_an_event_offers_no_type_its_flows_would_break(scene_restored) -> None:
    """A start event with a flow going out could be switched to an end event,
    and the model said the process ends where it begins."""
    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js("""(async () => {
        const post = async (body) => (await (await fetch("/api/process-edit", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body) })).json());
        let r = await post({ ttl: "", op: "add-pool", label: "Desk" });
        const pool = r.newId;
        r = await post({ ttl: r.ttl, op: "add-event", kind: "startEvent", pool });
        const start = r.newId;
        r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool, label: "Answer" });
        r = await post({ ttl: r.ttl, op: "connect", source: start, target: r.newId });
        window.PairAI.Editor.setValue(r.ttl);
        return { start };
    })()"""))
    _back_to_business(loop, handle)
    at = _settle(loop, handle, f"""(() => {{
        const g = document.querySelector('#process-canvas [data-node="{ids["start"]}"]');
        if (!g) return null;
        const r = g.getBoundingClientRect();
        return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
    }})()""", None, tries=40)
    assert at, "the start event was not drawn"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    seen = loop.run_until_complete(handle.js("""(() => {
        const select = document.querySelector("#process-detail #pd-kind");
        if (!select) return null;
        const end = [...select.options].find((o) => o.value === "endEvent");
        const why = document.querySelector("#process-detail #pd-kind-why");
        return { disabled: end.disabled, title: end.title, note: why ? why.textContent : "",
                 others: [...select.options].filter((o) => o.disabled).length };
    })()"""))
    assert seen, "clicking the start event opened no editor"
    assert seen["disabled"], "an end event is still offered while a flow leaves the start event"
    assert "no sequence flow may leave it" in seen["title"], "the disabled type says nothing"
    assert "Remove the outgoing flow" in seen["note"], "the panel does not say how to fix it"
    assert seen["others"] == 1, "a type the flows allow was disabled too"


def test_the_input_contract_is_checked_without_asking(scene_restored) -> None:
    """The panel stayed empty until Validate was pressed, so a student who never
    pressed it never saw that nothing they drew could match."""
    loop, handle = scene_restored
    bare = chr(10).join([
        "@prefix beam: <http://w3id.org/beam/core#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix ex: <http://example.org/unasked#> .",
        'ex:S a beam:System ; rdfs:label "S" ; beam:hasResource ex:Q .',
        'ex:Q a beam:Data ; rdfs:label "Customer question" .',
    ])
    try:
        # Opening the panel checks what is there, with no Validate press.
        loop.run_until_complete(handle.js(
            'document.querySelector(\'[data-drawer-tab="validation"]\').click(); 1'))
        opened = _settle(loop, handle,
                         'document.querySelectorAll("#validation-list .validation-row").length',
                         0, tries=40)
        assert opened, "opening the panel checked nothing"
        loop.run_until_complete(handle.js(
            "window.PairAI.Editor.setValue(" + json.dumps(bare) + "); 1"))
        # The rows of the document before it are still listed until this one is checked.
        checked = _settle(loop, handle,
                          'document.querySelector("#validation-list").textContent'
                          '.includes("Customer question")', False, tries=40)
        seen = loop.run_until_complete(handle.js("""({
            rows: document.querySelectorAll("#validation-list .validation-row").length,
            count: document.querySelector("#validation-count").textContent,
        })"""))
        assert checked, "nothing was checked until Validate was pressed"
        assert seen["count"] == str(seen["rows"]), "the tab does not say how many there are"
    finally:
        # Left open, the panel would check every document the later tests load.
        loop.run_until_complete(handle.js(
            """document.querySelector('[data-drawer-tab="findings"]').click(); 1"""))


def _press(loop, handle, key, code, vk, modifiers=0):
    for kind in ("rawKeyDown", "keyUp"):
        loop.run_until_complete(handle.send("Input.dispatchKeyEvent", {
            "type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk,
            "modifiers": modifiers}))
    time.sleep(0.4)


def _centre(loop, handle, selector):
    return loop.run_until_complete(handle.js(f"""(() => {{
        const b = document.querySelector({json.dumps(selector)});
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
    }})()"""))


def test_the_zoom_buttons_zoom_the_business_process(scene_restored) -> None:
    """The +, - and fit buttons zoomed the architecture canvas hidden behind the
    process, so on the business level they seemed to do nothing."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    scale = ("Number((document.querySelector('#process-canvas g').getAttribute('transform')"
             r" || '').match(/scale\(([^)]+)\)/)[1])")
    start = loop.run_until_complete(handle.js(scale))
    at = _centre(loop, handle, "#btn-zoom-in")
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    zoomed = loop.run_until_complete(handle.js(scale))
    at = _centre(loop, handle, "#btn-fit")
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    fitted = loop.run_until_complete(handle.js(scale))

    assert zoomed > start * 1.1, f"zoom-in left the process at {zoomed} (was {start})"
    assert abs(fitted - start) < 0.01, f"fit did not bring the process back: {fitted} vs {start}"


def test_delete_and_undo_work_on_the_business_process(scene_restored) -> None:
    """DEL removed only a picked flow, never the step that was clicked, and
    Ctrl+Z did nothing at all: writing the editor clears the browser's undo."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    target = loop.run_until_complete(handle.js("""(() => {
        for (const n of document.querySelectorAll('#process-canvas [data-node]')) {
            if (!n.querySelector('.pc-box') || n.classList.contains('refined')) continue;
            const r = n.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            const hit = document.elementFromPoint(x, y);
            if (hit && hit.closest('[data-node]') === n) return { id: n.getAttribute('data-node'), x, y };
        }
        return null;
    })()"""))
    assert target, "no plain activity could be clicked"
    present = f"!!document.querySelector('#process-canvas [data-node=\"{target['id']}\"]')"

    loop.run_until_complete(handle.click(target["x"], target["y"]))
    _press(loop, handle, "Delete", "Delete", 46)
    gone = _settle(loop, handle, present, True, tries=30)
    _press(loop, handle, "z", "KeyZ", 90, modifiers=2)
    back = _settle(loop, handle, present, False, tries=30)
    _press(loop, handle, "z", "KeyZ", 90, modifiers=2 | 8)
    again = _settle(loop, handle, present, True, tries=30)

    assert gone is False, "Delete did not remove the activity whose editor was open"
    assert back is True, "Ctrl+Z did not bring the activity back"
    assert again is False, "Ctrl+Shift+Z did not remove it again"


def test_back_stays_in_the_workbench(scene_restored) -> None:
    """The browser's Back left the tool, and the diagram with it."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(1)
    _back_to_business(loop, handle)
    loop.run_until_complete(handle.js("history.back(); 1"))
    time.sleep(1.5)
    first = loop.run_until_complete(handle.js("({ level: window.PairAI.state.level, url: location.pathname })"))
    loop.run_until_complete(handle.js("window.PairAI.state.levelTrail = []; history.back(); 1"))
    time.sleep(1.5)
    second = loop.run_until_complete(handle.js("({ level: window.PairAI.state.level, url: location.pathname })"))

    assert first["level"] == "architecture", f"Back did not return to the level before: {first}"
    assert second["url"].endswith("_cdp_probe.html"), f"Back left the workbench: {second}"


_KINDS = chr(10).join([
    "@prefix beam: <http://w3id.org/beam/core#> .",
    "@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .",
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
    "@prefix ex: <http://example.org/kinds#> .",
    'ex:S a beam:System ; rdfs:label "S" ; beam:hasResource ex:Q, ex:M ; beam:hasProcess ex:P .',
    'ex:Q a beam:Data ; rdfs:label "Question" .',
    'ex:M a beam:StatisticalModel ; rdfs:label "LLM" ; pair:containsDataCategory pair:Information .',
    'ex:P a beam:Generate ; rdfs:label "Generate" ; beam:use ex:Q, ex:M .',
])


def _open_popup_on(loop, handle, label):
    """Click an element on the architecture canvas with real input; return its popup."""
    loop.run_until_complete(handle.js(
        'document.querySelector("#node-detail").classList.add("hidden"); 1'))
    at = loop.run_until_complete(handle.js(f"""(() => {{
        for (const n of document.querySelectorAll('#canvas g.node')) {{
            if (!n.textContent.startsWith({json.dumps(label)})) continue;
            const r = n.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            const hit = document.elementFromPoint(x, y);
            if (hit && hit.closest('g.node') === n) return {{ x, y }};
        }}
        return null;
    }})()"""))
    assert at, f"{label} cannot be clicked on the canvas"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    assert loop.run_until_complete(handle.js(
        'document.querySelector("#nd-label").value')) == label


def _open_role_menu(loop, handle):
    trigger = _centre(loop, handle, "#nd-role-mp .mp-add")
    loop.run_until_complete(handle.click(trigger["x"], trigger["y"]))


def _role_offer(loop, handle):
    """Open the role menu and walk every submenu, counting the terms it offers."""
    _open_role_menu(loop, handle)
    return loop.run_until_complete(handle.js("""(() => {
        const pop = document.querySelector('#nd-role-mp .mp-pop');
        const cat = document.querySelector('#nd-cat-mp .mp-add');
        const offered = new Set();
        const walk = (panel, depth) => {
            for (const row of panel.querySelectorAll(':scope > .mp-row')) {
                if (row.classList.contains('pick')) offered.add(row.dataset.id);
                const more = row.querySelector('.mp-row-more');
                if (!more) continue;
                more.click();
                walk(document.querySelectorAll('#nd-role-mp .mp-fly')[depth], depth + 1);
            }
        };
        walk(pop.querySelector('.mp-list'), 0);
        return {
            open: !pop.classList.contains('hidden'),
            offered: offered.size,
            more: !!pop.querySelector('.mp-all'),
            catDisabled: cat.disabled,
            catChips: document.querySelectorAll('#nd-cat-mp .mp-chip').length,
        };
    })()"""))


def test_the_popup_offers_the_terms_that_fit_the_element(scene_restored) -> None:
    """A model was offered all 66 resource terms, most of them for data, and a
    step was offered data categories, which only a Data element carries."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js(
        "window.PairAI.Editor.setValue(" + json.dumps(_KINDS) + "); 1"))
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 0, tries=40)
    loop.run_until_complete(handle.js("window.PairAI.GraphView.fit(); 1"))
    time.sleep(0.5)
    expected = loop.run_until_complete(handle.js("""(async () => {
        const v = await (await fetch('/api/vocabulary')).json();
        // the roles the categories refine file them and are not offered
        const tops = new Set(v.roles.filter((r) => r.category).flatMap((r) => r.parents));
        const fit = (cls) => v.roles.filter((r) => r.applies === 'resource'
            && !tops.has(r.id)
            && (r.shelfId === cls || (r.appliesTo || []).includes(cls))).length;
        return { model: fit('http://w3id.org/beam/core#StatisticalModel'),
                 data: fit('http://w3id.org/beam/core#Data') };
    })()"""))

    _open_popup_on(loop, handle, "LLM")
    model = _role_offer(loop, handle)
    _open_popup_on(loop, handle, "Question")
    data = _role_offer(loop, handle)
    _open_popup_on(loop, handle, "Generate")
    step = _role_offer(loop, handle)
    loop.run_until_complete(handle.js(
        'document.querySelector("#node-detail").classList.add("hidden"); 1'))

    assert model["open"] and model["offered"] == expected["model"], (model, expected)
    assert model["more"], "the terms for other kinds of element cannot be reached"
    assert data["offered"] == expected["data"], (data, expected)
    assert model["catDisabled"] and step["catDisabled"], "a data category is offered off Data"
    assert model["catChips"] == 1, "a category the model already carries is no longer shown"
    assert not data["catDisabled"], "a Data element is not offered its data categories"


def test_picking_a_role_closes_the_list_so_apply_can_be_pressed(scene_restored) -> None:
    """The suggestion list stayed open after a pick and covered Apply."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js(
        "window.PairAI.Editor.setValue(" + json.dumps(_KINDS) + "); 1"))
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 0, tries=40)
    loop.run_until_complete(handle.js("window.PairAI.GraphView.fit(); 1"))
    time.sleep(0.5)
    _open_popup_on(loop, handle, "Question")
    _open_role_menu(loop, handle)
    # a category's arrow opens it on a click as well as on a hover, so a touch reaches it
    category = _centre(loop, handle, "#nd-role-mp .mp-list > .mp-row.folder .mp-row-more")
    assert category, "the role list did not open"
    loop.run_until_complete(handle.click(category["x"], category["y"]))
    option = _centre(loop, handle, "#nd-role-mp .mp-fly .mp-row.pick")
    assert option, "a category opened onto nothing to pick"
    loop.run_until_complete(handle.click(option["x"], option["y"]))
    seen = loop.run_until_complete(handle.js("""(() => {
        const apply = document.querySelector('#nd-apply');
        const r = apply.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        const box = document.querySelector('#node-detail').getBoundingClientRect();
        return {
            listOpen: !document.querySelector('#nd-role-mp .mp-pop').classList.contains('hidden')
                || !!document.querySelector('#nd-role-mp .mp-fly'),
            chips: document.querySelectorAll('#nd-role-mp .mp-chip').length,
            applyOnTop: !!hit && !!hit.closest('#nd-apply'),
            why: { apply: [Math.round(r.top), Math.round(r.bottom)],
                   popup: [Math.round(box.top), Math.round(box.bottom)],
                   viewport: innerHeight,
                   hit: hit ? hit.tagName + '#' + hit.id + '.' + hit.className : null,
                   drawerOpen: !document.querySelector('#drawer').classList.contains('collapsed') },
        };
    })()"""))
    loop.run_until_complete(handle.js(
        'document.querySelector("#node-detail").classList.add("hidden"); 1'))

    assert seen["chips"] == 1, "the pick was not recorded"
    assert not seen["listOpen"], "the suggestion list stayed open after a pick"
    assert seen["applyOnTop"], f"Apply is still covered after a pick: {seen['why']}"


def _menu_rows(loop, handle):
    """Each open submenu: its box and its rows with their centres."""
    return loop.run_until_complete(handle.js("""(() => {
        const box = (n) => { const r = n.getBoundingClientRect();
            return { left: r.left, right: r.right, top: r.top, bottom: r.bottom }; };
        return [...document.querySelectorAll('#nd-role-mp .mp-fly')].map((panel) => ({
            box: box(panel),
            rows: [...panel.querySelectorAll(':scope > .mp-row')].map((row) => {
                const r = row.getBoundingClientRect();
                return { label: row.querySelector('.mp-row-label').textContent,
                         x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
            }),
        }));
    })()"""))


def test_the_role_menu_cascades_from_category_to_the_role_that_refines_it(scene_restored) -> None:
    """The role picker was one flat list, so nothing in it said that Foundation
    LLM refines Generative Model, which refines Model. It cascades now: the
    categories that fit the element, then each role under the role it refines,
    opened by pointing at it the way a context menu opens, and picked by its
    label at any level, a category included."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js(
        "window.PairAI.Editor.setValue(" + json.dumps(_KINDS) + "); 1"))
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 0, tries=40)
    loop.run_until_complete(handle.js("window.PairAI.GraphView.fit(); 1"))
    time.sleep(0.5)
    _open_popup_on(loop, handle, "LLM")
    _open_role_menu(loop, handle)

    roots = loop.run_until_complete(handle.js("""[...document.querySelectorAll(
        '#nd-role-mp .mp-list > .mp-row')].map((r) => r.querySelector('.mp-row-label').textContent)"""))
    assert roots and roots[0] == "Models", f"the categories for a model do not come first: {roots}"

    trail = ["Models", "Model", "Generative Model", "Foundation LLM"]
    at = _centre(loop, handle, "#nd-role-mp .mp-list > .mp-row")
    loop.run_until_complete(handle.hover(at["x"], at["y"]))
    hints = []
    for depth, label in enumerate(trail[1:]):
        menus = _menu_rows(loop, handle)
        assert len(menus) == depth + 1, f"pointing at {trail[depth]} opened {len(menus)} menus"
        row = next((r for r in menus[-1]["rows"] if r["label"] == label), None)
        assert row, f"{label} is not under {trail[depth]}: {[r['label'] for r in menus[-1]['rows']]}"
        loop.run_until_complete(handle.hover(row["x"], row["y"]))
        hints.append(loop.run_until_complete(handle.js(
            "document.querySelector('#nd-role-mp .mp-hint').textContent")))

    menus = _menu_rows(loop, handle)
    for menu in menus:
        b = menu["box"]
        assert b["left"] >= 0 and b["top"] >= 0, f"a submenu is off screen: {b}"
    first, third = menus[0]["box"], menus[2]["box"]
    assert first["right"] <= third["left"] + 4 or third["right"] <= first["left"] + 4, (
        f"the third menu landed back on the first: {first} {third}")
    assert hints[1].startswith("Generative Model"), f"the hint does not say what it points at: {hints}"

    leaf = next(r for r in menus[-1]["rows"] if r["label"] == "Foundation LLM")
    loop.run_until_complete(handle.click(leaf["x"], leaf["y"]))
    seen = loop.run_until_complete(handle.js("""({
        chips: [...document.querySelectorAll('#nd-role-mp .mp-chip-label')].map((c) => c.textContent),
        menus: document.querySelectorAll('#nd-role-mp .mp-fly').length,
    })"""))
    assert seen["chips"] == ["Foundation LLM"], f"the pick was not recorded: {seen}"
    assert seen["menus"] == 0, "a submenu stayed open after the pick"

    # and by keyboard: down onto Models, right into it (its own "Use Models" heads the list),
    # down onto Model, Enter picks Model
    _open_role_menu(loop, handle)
    _press(loop, handle, "ArrowDown", "ArrowDown", 40)
    _press(loop, handle, "ArrowRight", "ArrowRight", 39)
    _press(loop, handle, "ArrowDown", "ArrowDown", 40)
    _press(loop, handle, "Enter", "Enter", 13)
    chips = loop.run_until_complete(handle.js(
        "[...document.querySelectorAll('#nd-role-mp .mp-chip-label')].map((c) => c.textContent)"))
    assert chips == ["Foundation LLM", "Model"], f"the keyboard did not walk the menu: {chips}"

    # a category is picked by its label, so an element can be tagged broadly first
    _open_role_menu(loop, handle)
    label = _centre(loop, handle, "#nd-role-mp .mp-list > .mp-row .mp-row-label")
    loop.run_until_complete(handle.click(label["x"], label["y"]))
    chips = loop.run_until_complete(handle.js(
        "[...document.querySelectorAll('#nd-role-mp .mp-chip-label')].map((c) => c.textContent)"))
    loop.run_until_complete(handle.js(
        'document.querySelector("#node-detail").classList.add("hidden"); 1'))
    assert chips[-1] == "Models", f"a category cannot be picked: {chips}"


def test_matches_on_takes_the_reader_to_the_role_and_back(page) -> None:
    """A "matches on" chip opened the term, and the only way back was "All
    terms": the motif the reader came from was gone."""
    loop, handle = page
    loop.run_until_complete(handle.js('document.querySelector("#btn-library").click()'))
    time.sleep(1)
    try:
        loop.run_until_complete(handle.js("""(() => {
            document.querySelector('.library-tab[data-library-tab="motifs"]').click();
            [...document.querySelectorAll('#library-detail .lib-tile')]
                .find((t) => /Information Retrieval/.test(t.textContent)).click();
            return 1;
        })()"""))
        time.sleep(0.8)
        chip = _spot(loop, handle, """(() => {
            const c = [...document.querySelectorAll('#library-detail .lib-roles .chip')]
                .find((x) => x.textContent === 'User Input');
            if (c) c.scrollIntoView({ block: 'center' });
            return c;
        })()""")
        assert chip, "the motif page names no role to follow"
        loop.run_until_complete(handle.click(chip["x"], chip["y"]))
        back = _spot(loop, handle, "document.querySelector('#library-detail .lib-back')")
        term = loop.run_until_complete(handle.js(
            "document.querySelector('#library-detail .lib-back').textContent"))
        loop.run_until_complete(handle.click(back["x"], back["y"]))
        returned = loop.run_until_complete(handle.js(
            "document.querySelector('#library-detail').textContent"))

        # And the browser's Back takes the same step.
        chip = _spot(loop, handle, """(() => {
            const c = [...document.querySelectorAll('#library-detail .lib-roles .chip')]
                .find((x) => x.textContent === 'User Input');
            if (c) c.scrollIntoView({ block: 'center' });
            return c;
        })()""")
        loop.run_until_complete(handle.click(chip["x"], chip["y"]))
        loop.run_until_complete(handle.js("history.back(); 1"))
        time.sleep(1)
        after_browser_back = loop.run_until_complete(handle.js("""({
            open: !document.querySelector('#library').classList.contains('hidden'),
            text: document.querySelector('#library-detail').textContent,
        })"""))
    finally:
        loop.run_until_complete(handle.js('document.querySelector("#btn-library-close").click(); 1'))

    assert term == "Back to Information Retrieval", f"the term page offers {term!r}"
    assert "Information Retrieval" in returned and "matches elements with the roles" in returned, (
        "Back did not return to the motif")
    assert after_browser_back["open"], "the browser's Back closed the library"
    assert "matches elements with the roles" in after_browser_back["text"], (
        "the browser's Back did not return to the motif")


def test_a_motif_match_lists_the_annotations_it_rests_on(scene_restored) -> None:
    """A match row said only which motif matched, never why."""
    loop, handle = scene_restored
    ttl = example_path(GRAPH_RAG_NS).read_text(encoding="utf-8")
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue(" + json.dumps(ttl) + "); 1"))
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    time.sleep(1.5)
    # Waits for this run, not for the rows an earlier test's run left listed.
    loop.run_until_complete(handle.js(
        "window.__runBefore = window.PairAI.state.lastAssessment;"
        " document.querySelector('#btn-assess').click(); 1"))
    _settle(loop, handle,
            "(!document.querySelector('#btn-assess').disabled && "
            "window.PairAI.state.lastAssessment && "
            "window.PairAI.state.lastAssessment !== window.__runBefore) ? 1 : 0", 0, tries=120)
    time.sleep(0.5)
    rows = loop.run_until_complete(handle.js(
        "document.querySelectorAll('#motifs-list .motif-row').length"))
    assert rows, "the assessment listed no motif match"
    loop.run_until_complete(handle.js(
        """document.querySelector('[data-drawer-tab="motifs"]').click(); 1"""))
    time.sleep(0.5)
    at = _spot(loop, handle, "document.querySelector('#motifs-list .motif-row .motif-row-name')")
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    seen = loop.run_until_complete(handle.js("""(() => {
        const row = document.querySelector('#motifs-list .motif-row.selected');
        const list = row && row.querySelector('.motif-bindings');
        return {
            selected: !!row,
            hasList: !!list,
            shown: !!list && list.checkVisibility(),
            items: list ? [...list.querySelectorAll('li')].map((li) => li.textContent) : [],
        };
    })()"""))
    loop.run_until_complete(handle.js(
        """document.querySelector('[data-drawer-tab="findings"]').click(); 1"""))

    assert seen["shown"], f"picking a match shows nothing about why it matched: {seen}"
    assert seen["items"] and all(" as " in item for item in seen["items"]), seen["items"]


_TWO_POOLS = """(async () => {
    const post = async (body) => (await (await fetch("/api/process-edit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) })).json());
    let r = await post({ ttl: "", op: "add-pool", label: "Customer" });
    const customer = r.newId;
    r = await post({ ttl: r.ttl, op: "add-pool", label: "Desk" });
    const desk = r.newId;
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool: customer, label: "Ask" });
    const ask = r.newId;
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool: desk, label: "Answer" });
    const answer = r.newId;
    window.PairAI.Editor.setValue(r.ttl);
    return { ask, answer };
})()"""


def _clear_the_business_canvas(loop, handle):
    """Fold the drawer and the palette, which float over the canvas, then fit."""
    loop.run_until_complete(handle.js("""(() => {
        if (!document.querySelector('#drawer').classList.contains('collapsed')) {
            document.querySelector('#drawer-toggle').click();
        }
        const palette = document.querySelector('#process-palette');
        const fold = palette.querySelector('.pp-fold');
        if (fold && !palette.classList.contains('folded')) fold.click();
        return 1;
    })()"""))
    time.sleep(0.5)
    loop.run_until_complete(handle.js("window.PairAI.ProcessCanvas.fit(); 1"))
    time.sleep(0.5)


def test_a_message_flow_starts_from_the_dot_at_the_bottom_of_a_task(scene_restored) -> None:
    """Dragging from the bottom of a task did nothing; a message flow started only
    from the right-hand dot, which a modeller reads as the sequence flow's."""
    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js(_TWO_POOLS))
    _back_to_business(loop, handle)
    _settle(loop, handle, f"!!document.querySelector('#process-canvas [data-node=\"{ids['answer']}\"]')",
            False, tries=40)
    _clear_the_business_canvas(loop, handle)
    spots = loop.run_until_complete(handle.js(f"""(() => {{
        const box = (id) => document.querySelector('#process-canvas [data-node="' + id + '"]');
        const mid = (r) => ({{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }});
        return {{
            ask: mid(box({json.dumps(ids["ask"])}).querySelector('.pc-box').getBoundingClientRect()),
            mail: mid(box({json.dumps(ids["ask"])}).querySelector('.pc-port-message .pc-port-dot')
                .getBoundingClientRect()),
            answer: mid(box({json.dumps(ids["answer"])}).querySelector('.pc-box').getBoundingClientRect()),
        }};
    }})()"""))
    loop.run_until_complete(handle.send("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": spots["ask"]["x"], "y": spots["ask"]["y"]}))
    time.sleep(0.3)
    shown = loop.run_until_complete(handle.js(
        "getComputedStyle(document.querySelector('#process-canvas .pc-port-message .pc-port-dot'))"
        ".opacity"))
    loop.run_until_complete(handle.drag(spots["mail"]["x"], spots["mail"]["y"],
                                        spots["answer"]["x"] + 40, spots["answer"]["y"]))
    time.sleep(1.5)
    written = loop.run_until_complete(handle.js(
        "window.PairAI.Editor.getValue().includes('a bpmn:messageFlow')"))

    assert shown == "1", "hovering a task does not reveal the message handle"
    assert written, "dragging from the bottom handle to another pool wrote no message flow"


_LANED = """(async () => {
    const post = async (body) => (await (await fetch("/api/process-edit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) })).json());
    let r = await post({ ttl: "", op: "add-pool", label: "Customer" });
    const customer = r.newId;
    r = await post({ ttl: r.ttl, op: "add-lane", pool: customer, label: "Front office" });
    const front = r.newId;
    r = await post({ ttl: r.ttl, op: "add-lane", pool: customer, label: "Back office" });
    const back = r.newId;
    r = await post({ ttl: r.ttl, op: "add-pool", label: "Desk" });
    const desk = r.newId;
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool: customer, lane: front, label: "Ask" });
    const ask = r.newId;
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool: customer, lane: front, label: "Log" });
    const log = r.newId;
    r = await post({ ttl: r.ttl, op: "connect", source: ask, target: log });
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool: desk, label: "Answer" });
    window.PairAI.Editor.setValue(r.ttl);
    return { customer, front, back, desk, ask, log };
})()"""


def test_a_step_is_dragged_into_another_lane_and_another_pool(scene_restored) -> None:
    """Moving a step meant deleting it and drawing it again."""
    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js(_LANED))
    _back_to_business(loop, handle)
    _settle(loop, handle, f"!!document.querySelector('#process-canvas [data-node=\"{ids['log']}\"]')",
            False, tries=40)
    _clear_the_business_canvas(loop, handle)
    # Confirmed without a dialog: a native one would block the headless page.
    loop.run_until_complete(handle.js("window.__asked = null;"
                                      " window.confirm = (m) => { window.__asked = m; return true; }; 1"))

    def drag_into(band_id):
        spots = loop.run_until_complete(handle.js(f"""(() => {{
            const box = document.querySelector('#process-canvas [data-node="{ids['log']}"] .pc-box')
                .getBoundingClientRect();
            const band = document.querySelector('#process-canvas [data-band="' + {json.dumps(band_id)} + '"]')
                .getBoundingClientRect();
            return {{ x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2),
                      toX: Math.round(band.left + band.width * 0.75),
                      toY: Math.round(band.top + band.height / 2) }};
        }})()"""))
        loop.run_until_complete(handle.drag(spots["x"], spots["y"], spots["toX"], spots["toY"]))
        time.sleep(2)
        return loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))

    in_back = drag_into(ids["back"])
    in_desk = drag_into(ids["desk"])
    asked = loop.run_until_complete(handle.js("window.__asked"))

    from rdflib import Graph, URIRef

    lanes = Graph().parse(data=in_back, format="turtle")
    joined = (URIRef(ids["back"]), URIRef("https://sBPMN.github.io/2.0/properties#flowNodeRef"),
              URIRef(ids["log"]))
    assert joined in lanes, "the step did not join the lane it was dropped in"
    assert asked and "would cross between participants" in asked, f"the move asked {asked!r}"
    assert "a bpmn:messageFlow" in in_desk, "the flow left crossing pools was not converted"
    assert "a bpmn:sequenceFlow" not in in_desk


def test_a_store_read_and_written_by_one_step_is_drawn_both_ways(scene_restored) -> None:
    loop, handle = scene_restored
    loop.run_until_complete(handle.js("""(async () => {
        const post = async (body) => (await (await fetch("/api/process-edit", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body) })).json());
        let r = await post({ ttl: "", op: "add-pool", label: "Desk" });
        const pool = r.newId;
        r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool, label: "Update ticket" });
        const task = r.newId;
        r = await post({ ttl: r.ttl, op: "add-data", shape: "store", label: "Tickets" });
        const store = r.newId;
        r = await post({ ttl: r.ttl, op: "connect", source: store, target: task });
        r = await post({ ttl: r.ttl, op: "connect", source: task, target: store });
        window.PairAI.Editor.setValue(r.ttl);
        return 1;
    })()"""))
    _back_to_business(loop, handle)
    titles = _settle(loop, handle, """[...document.querySelectorAll('#process-canvas title')]
        .map((t) => t.textContent).filter((t) => t.startsWith('Tickets'))""", [], tries=40)
    # one box with an arrow each way (asked for 2026-10-19), not the same store drawn twice
    assert len(titles) == 1 and "read and written by Update ticket" in titles[0], titles


_XOR = """(async () => {
    const post = async (body) => (await (await fetch("/api/process-edit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) })).json());
    let r = await post({ ttl: "", op: "add-pool", label: "Desk" });
    const pool = r.newId;
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool, label: "Check request" });
    const check = r.newId;
    r = await post({ ttl: r.ttl, op: "add-gateway", kind: "exclusiveGateway", pool, label: "Valid?" });
    const gw = r.newId;
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool, label: "Answer" });
    const answer = r.newId;
    r = await post({ ttl: r.ttl, op: "add-activity", kind: "task", pool, label: "Reject" });
    const reject = r.newId;
    r = await post({ ttl: r.ttl, op: "connect", source: check, target: gw });
    r = await post({ ttl: r.ttl, op: "connect", source: gw, target: answer });
    r = await post({ ttl: r.ttl, op: "connect", source: gw, target: reject });
    window.PairAI.Editor.setValue(r.ttl);
    return { gw };
})()"""


def test_an_xor_gateway_names_its_branches_where_it_decides(scene_restored) -> None:
    """A branch's condition could only be set by clicking its thin line, was
    then shown in no caption, and drew the conditional diamond BPMN keeps for a
    flow out of an activity."""
    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js(_XOR))
    _back_to_business(loop, handle)
    _settle(loop, handle, f"!!document.querySelector('#process-canvas [data-node=\"{ids['gw']}\"]')",
            False, tries=40)
    _clear_the_business_canvas(loop, handle)
    at = _spot(loop, handle,
               f"document.querySelector('#process-canvas [data-node=\"{ids['gw']}\"] .pc-gate-box')")
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    rows = loop.run_until_complete(handle.js("""(() => {
        const panel = document.querySelector('#process-detail');
        const names = panel.querySelectorAll('.pd-branch-name');
        const whens = panel.querySelectorAll('.pd-branch-when');
        if (names.length !== 2 || whens.length !== 2) return { names: names.length, whens: whens.length };
        names[0].value = 'yes';
        names[1].value = 'no';
        whens[1].value = 'anything is missing';
        return { names: 2, whens: 2 };
    })()"""))
    assert rows == {"names": 2, "whens": 2}, f"the gateway editor lists {rows}"
    apply = _spot(loop, handle, "document.querySelector('#process-detail #pd-apply')")
    loop.run_until_complete(handle.click(apply["x"], apply["y"]))
    seen = _settle(loop, handle, """(() => {
        const labels = [...document.querySelectorAll('#process-canvas .pc-flow-label')]
            .map((l) => l.textContent).sort();
        return labels.length === 2 ? { labels,
            diamonds: document.querySelectorAll('#process-canvas .pc-flow-diamond').length,
            stored: window.PairAI.Editor.getValue().includes('anything is missing') } : null;
    })()""", None, tries=40)

    assert seen, "the branches were not labelled"
    assert seen["labels"] == ["no", "yes"]
    assert seen["stored"], "the condition was not written"
    assert seen["diamonds"] == 0, "a gateway's branch is drawn as a conditional flow out of an activity"


def test_the_palette_offers_an_intermediate_timer(page) -> None:
    """Message catch and throw were the only events offered part-way through."""
    loop, handle = page
    _back_to_business(loop, handle)
    _open_palette(loop, handle)
    offered = loop.run_until_complete(handle.js(
        "[...document.querySelectorAll('#process-palette .pp-item')].map((b) => b.textContent.trim())"))
    assert "Timer catch" in offered, offered


def test_the_input_contract_panel_checks_the_bpmn_too(scene_restored) -> None:
    """Nothing told a modeller that an end event with a flow out of it is not BPMN."""
    loop, handle = scene_restored
    broken = chr(10).join([
        "@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .",
        "@prefix bp: <https://sBPMN.github.io/2.0/properties#> .",
        "@prefix ex: <http://example.org/badflow#> .",
        'ex:A a bpmn:participant ; bp:name "Desk" ; bp:processRef ex:P .',
        "ex:P a bpmn:process ; bp:contains ex:s, ex:t, ex:e .",
        'ex:s a bpmn:startEvent ; bp:name "Begin" .',
        'ex:t a bpmn:task ; bp:name "Answer" .',
        'ex:e a bpmn:endEvent ; bp:name "Done" .',
        "ex:f1 a bpmn:sequenceFlow ; bp:sourceRef ex:s ; bp:targetRef ex:t .",
        "ex:f2 a bpmn:sequenceFlow ; bp:sourceRef ex:t ; bp:targetRef ex:e .",
        "ex:f3 a bpmn:sequenceFlow ; bp:sourceRef ex:e ; bp:targetRef ex:t .",
    ])
    try:
        loop.run_until_complete(handle.js(
            """document.querySelector('[data-drawer-tab="validation"]').click(); 1"""))
        loop.run_until_complete(handle.js(
            "window.PairAI.Editor.setValue(" + json.dumps(broken) + "); 1"))
        row = _settle(loop, handle, """(() => {
            const r = [...document.querySelectorAll('#validation-list .validation-row')]
                .find((x) => x.textContent.includes('is an end event'));
            return r ? { text: r.textContent, violation: r.classList.contains('violation') } : null;
        })()""", None, tries=40)
    finally:
        loop.run_until_complete(handle.js(
            """document.querySelector('[data-drawer-tab="findings"]').click(); 1"""))

    assert row, "the panel says nothing about an end event a flow leaves"
    assert row["violation"] and "BPMN" in row["text"], row


def test_the_motif_tray_starts_folded_and_finds_a_motif_by_what_it_does(page) -> None:
    """47 motifs open at once, each ending in "Motif", and a tooltip that only
    repeated the name: nothing helped a reader find the one they needed."""
    loop, handle = page
    _descend(loop, handle)
    assert _on_architecture(loop, handle), "did not reach the architecture level"
    loop.run_until_complete(handle.js("""(() => {
        const host = document.querySelector('#motif-palette');
        if (host.classList.contains('collapsed')) host.querySelector('.tray-head').click();
        return 1;
    })()"""))
    shown = "[...document.querySelectorAll('#motif-palette .motif-item')].filter((c) => c.checkVisibility())"
    folded = loop.run_until_complete(handle.js(shown + ".length"))

    box = _spot(loop, handle, "document.querySelector('#motif-palette .motif-search')")
    loop.run_until_complete(handle.click(box["x"], box["y"]))
    loop.run_until_complete(handle.send("Input.insertText", {"text": "vector store"}))
    time.sleep(0.5)
    found = loop.run_until_complete(handle.js(shown + """.map((c) => ({ name: c.textContent }))"""))
    # A click opens what the motif is, beside the tray, rather than a tooltip.
    first = _spot(loop, handle, shown + "[0]")
    before = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue().length"))
    loop.run_until_complete(handle.click(first["x"], first["y"]))
    time.sleep(0.6)
    card = loop.run_until_complete(handle.js("""(() => {
        const c = document.querySelector('.motif-card');
        if (!c) return null;
        const r = c.getBoundingClientRect();
        return {
            text: c.textContent, drawn: !!c.querySelector('svg.motif-preview .mp-node, svg.motif-preview rect'),
            inWindow: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight,
            add: !!c.querySelector('.btn.primary'),
        };
    })()"""))
    after = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue().length"))
    loop.run_until_complete(handle.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape"}))
    closed = loop.run_until_complete(handle.js("!document.querySelector('.motif-card')"))
    loop.run_until_complete(handle.js("""(() => {
        const s = document.querySelector('#motif-palette .motif-search');
        s.value = ''; s.dispatchEvent(new Event('input'));
        return 1;
    })()"""))

    assert folded == 0, f"{folded} motifs are listed before any family is opened"
    assert found, "searching what a motif does found nothing"
    assert all(not item["name"].endswith("Motif") for item in found), found
    assert card, "clicking a motif opened no detail"
    assert "vector store" in card["text"].lower(), "the detail of a search hit does not say what matched"
    assert card["drawn"] and card["add"] and card["inWindow"], card
    assert before == after, "a click to read a motif added it to the canvas"
    assert closed, "Escape did not close the detail"


def test_one_attachment_comes_off_a_risk_and_the_risk_stays(scene_restored) -> None:
    """A risk attached to two parts of a folded system drew one line to the
    system, and "remove this connection" unlinked the risk from the system,
    which it was never attached to: nothing came off, and the only other way
    was to delete the risk."""
    loop, handle = scene_restored
    # The scene itself, not whatever an earlier test left in the editor. Setting
    # the editor is not opening a document, so an earlier run on another graph
    # would stay and the risk view would draw that run instead.
    loop.run_until_complete(handle.js(
        "window.PairAI.state.lastAssessment = null; window.PairAI.state.lastRun = null; 1"))
    loop.run_until_complete(handle.js(_scene_js()))
    _settle(loop, handle, "window.PairAI.Editor.getValue().length", 0, tries=40)
    time.sleep(2)
    risk = loop.run_until_complete(handle.js(f"""(async () => {{
        const we = {json.dumps(WIEN_ENERGIE_NS)};
        const r = await (await fetch("/api/scope-edit", {{
            method: "POST", headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ ttl: window.PairAI.Editor.getValue(), op: "state-concept",
                kind: "risk", label: "Leaky answers", attachTo: [we + "Answer", we + "Question"] }}) }})).json();
        window.PairAI.Editor.setValue(r.ttl);
        return r.newId;
    }})()"""))
    time.sleep(3)
    loop.run_until_complete(handle.js(
        'if (!document.querySelector("#drawer").classList.contains("collapsed")) '
        'document.querySelector("#drawer-toggle").click(); '
        'document.querySelector("#level-risk").click(); 1'))
    time.sleep(2)
    # Every layer on and every architecture shown, whatever an earlier test left.
    loop.run_until_complete(handle.js("""(() => {
        document.querySelectorAll('.layer-toggle:not(.on)').forEach((b) => b.click());
        const focus = document.querySelector('.layer-focus');
        if (focus && focus.value) { focus.value = ''; focus.dispatchEvent(new Event('change')); }
        return 1;
    })()"""))
    time.sleep(1)
    drawn = f"!!document.querySelector('#risk-canvas [data-node=\"{risk}\"]')"
    _settle(loop, handle, drawn, False, tries=40)
    loop.run_until_complete(handle.js("window.PairAI.RiskCanvas.fit(); 1"))
    time.sleep(0.5)
    line = loop.run_until_complete(handle.js(f"""(() => {{
        const hit = [...document.querySelectorAll('#risk-canvas .rc-link-hit')]
            .find((h) => h.getAttribute('data-from') === {json.dumps(risk)});
        if (!hit) return null;
        const p = hit.getPointAtLength(hit.getTotalLength() / 2);
        const m = hit.getScreenCTM();
        return {{ x: Math.round(m.a * p.x + m.c * p.y + m.e), y: Math.round(m.b * p.x + m.d * p.y + m.f) }};
    }})()"""))
    why = loop.run_until_complete(handle.js("""(() => ({
        from: [...new Set([...document.querySelectorAll('#risk-canvas .rc-link-hit')]
            .map((h) => h.getAttribute('data-from')))].slice(0, 8),
        layers: [...document.querySelectorAll('.layer-toggle')].map((b) => b.textContent + (b.classList.contains('on') ? '+' : '-')),
        level: document.querySelector('#canvas-wrap').className,
        drawn: [...document.querySelectorAll('#risk-canvas [data-node]')]
            .map((n) => n.getAttribute('data-node').split(/[#/]/).pop()),
        lines: document.querySelectorAll('#risk-canvas .rc-link').length,
        empty: (document.querySelector('#risk-canvas-empty') || {}).textContent,
        run: !!(window.PairAI.state.lastAssessment),
        ttlHasRisk: window.PairAI.Editor.getValue().includes('Leaky answers'),
    }))()"""))
    assert line, f"the risk {risk} draws no line to pick: {why}"
    loop.run_until_complete(handle.click(line["x"], line["y"]))
    off = _spot(loop, handle, """(() => {
        const chip = [...document.querySelectorAll('#risk-side .chip.detach')]
            .find((c) => c.textContent.startsWith('Customer question'));
        return chip ? chip.querySelector('.detach-x') : null;
    })()""")
    assert off, "the line's panel offers no way to take one attachment off"
    loop.run_until_complete(handle.click(off["x"], off["y"]))
    time.sleep(2.5)

    from rdflib import Graph, URIRef

    graph = Graph().parse(data=loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()")),
                          format="turtle")
    has_risk = URIRef("http://w3id.org/beam/risk#hasRisk")
    assert (URIRef(WIEN_ENERGIE_NS + "Question"), has_risk, URIRef(risk)) not in graph, (
        "the attachment was not removed")
    assert (URIRef(WIEN_ENERGIE_NS + "Answer"), has_risk, URIRef(risk)) in graph, (
        "the other attachment went too")
    assert (URIRef(risk), None, None) in graph, "the risk itself was deleted"


def test_a_shape_is_dragged_from_the_palette_into_a_lane(scene_restored) -> None:
    """On the architecture canvas a symbol is dragged where it goes; on the
    business canvas a shape could only be clicked into the selected lane."""
    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js(_LANED))
    _back_to_business(loop, handle)
    _settle(loop, handle, f"!!document.querySelector('#process-canvas [data-band=\"{ids['back']}\"]')",
            False, tries=40)
    loop.run_until_complete(handle.js("""(() => {
        if (!document.querySelector('#drawer').classList.contains('collapsed')) {
            document.querySelector('#drawer-toggle').click();
        }
        return 1;
    })()"""))
    _open_palette(loop, handle)
    loop.run_until_complete(handle.js("window.PairAI.ProcessCanvas.fit(); 1"))
    time.sleep(0.5)
    _open_palette(loop, handle)
    spots = loop.run_until_complete(handle.js(f"""(() => {{
        const task = [...document.querySelectorAll('#process-palette .pp-item')]
            .find((b) => b.textContent.trim() === 'Task');
        task.scrollIntoView({{ block: 'nearest' }});
        const t = task.getBoundingClientRect();
        const band = document.querySelector('#process-canvas [data-band="{ids['back']}"]')
            .getBoundingClientRect();
        return {{ x: Math.round(t.left + t.width / 2), y: Math.round(t.top + t.height / 2),
                  toX: Math.round(band.left + band.width * 0.6),
                  toY: Math.round(band.top + band.height / 2) }};
    }})()"""))
    loop.run_until_complete(handle.drag(spots["x"], spots["y"], spots["toX"], spots["toY"]))
    time.sleep(2)

    from rdflib import Graph, URIRef

    graph = Graph().parse(data=loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()")),
                          format="turtle")
    held = set(graph.objects(URIRef(ids["back"]),
                             URIRef("https://sBPMN.github.io/2.0/properties#flowNodeRef")))
    assert len(held) == 1, f"the dropped shape is not in the lane it was dropped on: {held}"

    # A drag released off its button fires no click; the next click must still add.
    loop.run_until_complete(handle.js("window.__asked = [];"
                                      " window.prompt = (m) => { window.__asked.push(m); return null; }; 1"))
    at = loop.run_until_complete(handle.js("""(() => {
        const store = [...document.querySelectorAll('#process-palette .pp-item')]
            .find((b) => b.textContent.trim() === 'Data store');
        store.scrollIntoView({ block: 'nearest' });
        const r = store.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    asked = loop.run_until_complete(handle.js("window.__asked"))
    assert asked == ["Name of the data store:"], f"the first click after a drag did nothing: {asked}"


SHIFT = 8


def test_clear_is_in_the_top_bar_and_works_with_the_editor_folded(scene_restored) -> None:
    """Clear sat on the editor's own head, which folds away with the editor."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js(
        "document.body.classList.contains('editor-hidden')"
        " || document.querySelector('#btn-editor-toggle').click(); 1"))
    time.sleep(0.6)
    loop.run_until_complete(handle.js("window.__asked = null;"
                                      " window.confirm = (m) => { window.__asked = m; return true; }; 1"))
    where = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('#btn-clear');
        const r = b.getBoundingClientRect();
        const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
        const hit = document.elementFromPoint(x, y);
        return { inToolbar: !!b.closest('.app-header .toolbar'), x, y,
                 onTop: !!hit && !!hit.closest('#btn-clear'),
                 folded: document.body.classList.contains('editor-hidden') };
    })()"""))
    assert where["folded"], "the editor did not fold"
    assert where["inToolbar"], "Clear is not in the top bar"
    assert where["onTop"], "Clear cannot be pressed while the editor is folded"

    loop.run_until_complete(handle.click(where["x"], where["y"]))
    time.sleep(1)
    left = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))
    loop.run_until_complete(handle.js(
        "document.body.classList.contains('editor-hidden')"
        " && document.querySelector('#editor-rail').click(); 1"))
    time.sleep(0.6)
    assert loop.run_until_complete(handle.js("window.__asked")), "Clear did not ask first"
    assert not left.strip(), f"Clear left the document: {left[:80]!r}"


def _node_at(loop, handle, selector, attribute, value):
    """Where a real click lands on that node, or None when something covers it."""
    wanted = f'{selector}[{attribute}="{value}"]'
    return loop.run_until_complete(handle.js(f"""(() => {{
        const n = document.querySelector({json.dumps(wanted)});
        if (!n) return null;
        const r = (n.querySelector('.shape, .pc-box') || n).getBoundingClientRect();
        const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
        const hit = document.elementFromPoint(x, y);
        return hit && hit.closest({json.dumps(selector)}) === n ? {{ x, y }} : null;
    }})()"""))


def test_shift_click_picks_several_elements_and_delete_takes_them_all(scene_restored) -> None:
    """Delete took the one element last clicked; there was no way to pick more."""
    from rdflib import Graph

    loop, handle = scene_restored
    loop.run_until_complete(handle.js(
        "window.PairAI.Editor.setValue(" + json.dumps(_KINDS) + "); 1"))
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 0, tries=40)
    loop.run_until_complete(handle.js(
        "document.querySelector('#drawer').classList.contains('collapsed')"
        " || document.querySelector('#drawer-toggle').click();"
        " window.PairAI.GraphView.fit(); 1"))
    time.sleep(0.6)

    ex = "http://example.org/kinds#"
    for name in ("Q", "M"):
        at = _node_at(loop, handle, "#canvas g.node", "data-id", ex + name)
        assert at, f"{name} cannot be clicked on the canvas"
        loop.run_until_complete(handle.click(at["x"], at["y"], modifiers=SHIFT))
    seen = loop.run_until_complete(handle.js("""(() => ({
        picked: [...document.querySelectorAll('#canvas g.node.highlight')].map((n) => n.dataset.id),
        popup: !document.querySelector('#node-detail').classList.contains('hidden'),
    }))()"""))
    assert sorted(seen["picked"]) == [ex + "M", ex + "Q"], seen
    assert not seen["popup"], "a shift-click opened the element's editor"

    _press(loop, handle, "Delete", "Delete", 46)
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 3, tries=40)
    left = Graph().parse(data=loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()")),
                         format="turtle")
    subjects = {str(s).removeprefix(ex) for s in left.subjects()}
    assert not {"Q", "M"} & subjects, f"a picked element stayed: {subjects}"
    assert {"S", "P"} <= subjects, f"an element nobody picked went: {subjects}"

    _press(loop, handle, "z", "KeyZ", 90, modifiers=2)
    back = _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 1, tries=40)
    assert back == 3, f"one undo brought back {back} of 3 elements"


def test_shift_click_picks_several_shapes_on_the_process_and_delete_takes_them(scene_restored) -> None:
    from rdflib import Graph, URIRef

    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js(_LANED))
    _back_to_business(loop, handle)
    present = "!!document.querySelector('#process-canvas [data-node=\"{}\"]')"
    _settle(loop, handle, present.format(ids["log"]), False, tries=40)
    _clear_the_business_canvas(loop, handle)

    for key in ("ask", "log"):
        at = _node_at(loop, handle, "#process-canvas [data-node]", "data-node", ids[key])
        assert at, f"{key} cannot be clicked on the canvas"
        loop.run_until_complete(handle.click(at["x"], at["y"], modifiers=SHIFT))
    seen = loop.run_until_complete(handle.js("""(() => ({
        picked: [...document.querySelectorAll('#process-canvas .pc-picked')]
            .map((n) => n.getAttribute('data-node')),
        editor: !document.querySelector('#process-detail').classList.contains('hidden'),
    }))()"""))
    assert sorted(seen["picked"]) == sorted([ids["ask"], ids["log"]]), seen
    assert not seen["editor"], "a shift-click opened the shape's editor"

    _press(loop, handle, "Delete", "Delete", 46)
    _settle(loop, handle, present.format(ids["ask"]), True, tries=40)
    left = Graph().parse(data=loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()")),
                         format="turtle")
    subjects = {str(s) for s in left.subjects()}
    assert not {ids["ask"], ids["log"]} & subjects, "a picked shape stayed"
    assert {ids["customer"], ids["desk"]} <= subjects, "a participant nobody picked went"
    assert not set(left.subjects(None, URIRef("https://sBPMN.github.io/2.0/classes#sequenceFlow"))), (
        "the flow between the two deleted steps stayed")

    _press(loop, handle, "z", "KeyZ", 90, modifiers=2)
    _settle(loop, handle, present.format(ids["ask"]), False, tries=40)
    restored = loop.run_until_complete(handle.js(
        "[" + ", ".join(present.format(ids[k]) for k in ("ask", "log")) + "]"))
    assert restored == [True, True], "one undo did not bring both steps back"


def test_the_element_tray_is_named_for_what_it_holds_and_says_what_each_is(scene_restored) -> None:
    """The tray was called "Symbols" while Symbol is one of its own entries, and
    each tooltip only repeated the class name."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#palette .palette-item').length", 0, tries=40)
    tray = loop.run_until_complete(handle.js("""(() => ({
        title: document.querySelector('#palette .tray-head span').textContent,
        tips: [...document.querySelectorAll('#palette .palette-item')]
            .map((chip) => [chip.textContent, chip.title]),
    }))()"""))
    assert tray["title"] == "Elements", tray["title"]
    for label, tip in tray["tips"]:
        said = tip.split(" (beam:")[0]
        assert len(said.split()) >= 4, f"{label} has no tooltip saying what it is: {tip!r}"
        assert "drag onto the canvas" in tip, f"{label}'s tooltip lost how to add it: {tip!r}"


def test_the_fit_leaves_no_element_under_a_tray(scene_restored) -> None:
    """The element tray floats over the canvas, and the fit drew the diagram under it."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 0, tries=40)
    loop.run_until_complete(handle.js("window.PairAI.GraphView.fit(); 1"))
    time.sleep(0.5)
    seen = loop.run_until_complete(handle.js("""(() => {
        const trays = ['#palette', '#motif-palette', '#system-badge']
            .map((s) => document.querySelector(s)).filter((e) => e && e.offsetParent)
            .map((e) => e.getBoundingClientRect());
        const under = [...document.querySelectorAll('#canvas g.node')].filter((g) => {
            const r = g.getBoundingClientRect();
            return trays.some((t) => r.left < t.right && r.right > t.left
                                   && r.top < t.bottom && r.bottom > t.top);
        }).map((g) => g.textContent.slice(0, 30));
        return { trays: trays.length, under };
    })()"""))
    assert seen["trays"] >= 2, "the trays are not on screen to be measured against"
    assert not seen["under"], f"after a fit these sit under a tray: {seen['under']}"


def test_a_pool_and_a_lane_are_resized_by_dragging_their_edges(scene_restored) -> None:
    """Pools and lanes took whatever size the layout gave them."""
    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js(_LANED))
    _back_to_business(loop, handle)
    _settle(loop, handle, f"!!document.querySelector('#process-canvas [data-band=\"{ids['back']}\"]')",
            False, tries=40)
    _clear_the_business_canvas(loop, handle)
    loop.run_until_complete(handle.js("window.PairAI.ProcessCanvas.zoomBy(0.7); 1"))
    time.sleep(0.5)
    before = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))

    sizes = f"""(() => {{
        const box = (id) => document.querySelector('#process-canvas [data-band="' + id + '"] > rect');
        const grip = (sel) => {{
            const r = document.querySelector(sel).getBoundingClientRect();
            return {{ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }};
        }};
        return {{
            lane: +box({json.dumps(ids['front'])}).getAttribute('height'),
            pool: +box({json.dumps(ids['desk'])}).getAttribute('height'),
            width: +box({json.dumps(ids['desk'])}).getAttribute('width'),
            laneGrip: grip('#process-canvas .pc-resize-h[data-grip="' + {json.dumps(ids['front'])} + '"]'),
            poolGrip: grip('#process-canvas [data-band="' + {json.dumps(ids['desk'])} + '"] .pc-resize-h'),
            widthGrip: grip('#process-canvas [data-band="' + {json.dumps(ids['desk'])} + '"] .pc-resize-w'),
        }};
    }})()"""
    start = loop.run_until_complete(handle.js(sizes))
    g = start["laneGrip"]
    loop.run_until_complete(handle.drag(g["x"], g["y"], g["x"], g["y"] + 50))
    after_lane = loop.run_until_complete(handle.js(sizes))
    g = after_lane["poolGrip"]
    loop.run_until_complete(handle.drag(g["x"], g["y"], g["x"], g["y"] + 50))
    after_pool = loop.run_until_complete(handle.js(sizes))
    g = after_pool["widthGrip"]
    loop.run_until_complete(handle.drag(g["x"], g["y"], g["x"] + 40, g["y"]))
    after_width = loop.run_until_complete(handle.js(sizes))
    left = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue()"))

    assert after_lane["lane"] > start["lane"] + 30, (start, after_lane)
    assert after_pool["pool"] > start["pool"] + 30, (after_lane, after_pool)
    assert after_width["width"] > start["width"] + 20, (after_pool, after_width)
    assert left == before, "resizing a band wrote to the document"


def test_the_renamed_labels_are_the_ones_on_screen(scene_restored) -> None:
    """The renames the dry run listed, read off the page where each one shows."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    target = loop.run_until_complete(handle.js("""(() => {
        for (const n of document.querySelectorAll('#process-canvas [data-node]')) {
            if (!n.querySelector('.pc-box') || n.classList.contains('refined')) continue;
            const r = n.getBoundingClientRect();
            const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
            const hit = document.elementFromPoint(x, y);
            if (hit && hit.closest('[data-node]') === n) return { x, y };
        }
        return null;
    })()"""))
    assert target, "no plain activity could be clicked"
    loop.run_until_complete(handle.click(target["x"], target["y"]))
    carried_by = loop.run_until_complete(handle.js(
        "(document.querySelector('#pd-refines option[value=\"__new__\"]') || {}).textContent"))
    loop.run_until_complete(handle.js(
        "document.querySelector('#process-detail').classList.add('hidden'); 1"))

    store = loop.run_until_complete(handle.js("""(async () => {
        window.__asked = [];
        window.__prompt = window.prompt;
        window.prompt = (message) => { window.__asked.push(message); return null; };
        const palette = document.querySelector('#process-palette');
        if (palette.classList.contains('folded')) palette.querySelector('.pp-fold').click();
        await new Promise((r) => setTimeout(r, 300));
        const store = [...document.querySelectorAll('#process-palette .pp-item')]
            .find((b) => /store|database/i.test(b.textContent));
        if (!store) return null;
        store.scrollIntoView({ block: 'nearest' });
        const r = store.getBoundingClientRect();
        return { label: store.textContent.trim(),
                 x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    assert store, "the process palette offers no data store"
    loop.run_until_complete(handle.click(store["x"], store["y"]))

    seen = loop.run_until_complete(handle.js("""(async () => {
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        const text = (sel) => ((document.querySelector(sel) || {}).textContent || '').trim();
        const out = {
            level: text('#level-business'),
            drawer: text('[data-drawer-tab="motifs"]').replace(/[0-9]+/g, '').trim(),
            library: text('[data-library-tab="motifs"]').replace(/[0-9]+/g, '').trim(),
        };

        document.querySelector('#level-architecture').click();
        await wait(800);
        out.tray = text('#motif-palette .tray-head span');
        const add = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === '+ system');
        if (add) add.click();

        document.querySelector('#level-risk').click();
        await wait(1500);
        out.manual = [...document.querySelectorAll('#risk-palette .pp-group')].map((g) => g.textContent);
        out.layers = [...document.querySelectorAll('.layer-toggle')].map((b) => b.textContent);

        document.querySelector('#btn-library').click();
        await wait(1200);
        document.querySelector('.library-tab[data-library-tab="risks"]').click();
        await wait(300);
        const row = document.querySelector('#library-list .lib-row');
        if (row) row.click();
        await wait(400);
        out.riskPage = [...document.querySelectorAll('#library-detail h3')].map((h) => h.textContent.trim());
        document.querySelector('#btn-library-close').click();
        window.prompt = window.__prompt;
        out.asked = window.__asked;
        return out;
    })()"""))
    _back_to_business(loop, handle)

    assert seen["level"] == "Process", seen
    assert seen["drawer"] == seen["library"] == seen["tray"] == "Architectural motifs", seen
    assert store["label"] == "Data store", store
    assert "Manual risk modelling" in seen["manual"], seen
    assert "Process" in seen["layers"] and "Business" not in seen["layers"], seen
    assert carried_by == "+ system…", carried_by
    assert any(h.startswith("Related motifs") for h in seen["riskPage"]), seen["riskPage"]
    assert not any("Structures it applies to" in h for h in seen["riskPage"]), seen["riskPage"]
    assert seen["asked"] == ["Name of the data store:", "Name of the new system:"], seen["asked"]


def test_every_risk_is_listed_on_one_page_under_the_name_the_library_gives_it(page) -> None:
    """There was no one page or URL listing every risk the tool can raise."""
    loop, handle = page
    rail = loop.run_until_complete(handle.js("""(async () => {
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        document.querySelector('#btn-library').click();
        await wait(1200);
        document.querySelector('.library-tab[data-library-tab="risks"]').click();
        await wait(400);
        // Back to the landing, whatever page an earlier test left open.
        for (let i = 0; i < 6 && document.querySelector('#library-detail .lib-back'); i++) {
            document.querySelector('#library-detail .lib-back').click();
            await wait(250);
        }
        for (const shut of document.querySelectorAll('#library-list .lib-group.shut')) {
            shut.click();
            await wait(100);
        }
        const names = [...document.querySelectorAll('#library-list .lib-row-name')]
            .map((n) => n.textContent);
        const link = document.querySelector('#library-detail a[href="/risks"]');
        document.querySelector('#btn-library-close').click();
        return { names, linked: !!link };
    })()"""))
    listed = loop.run_until_complete(handle.js("""(async () => {
        const served = await (await fetch('/api/library')).json();
        const wanted = served.riskPatterns[served.riskPatterns.length - 1].id;
        const frame = document.createElement('iframe');
        frame.style.cssText = 'position:fixed;left:0;top:0;width:900px;height:700px;z-index:9999';
        frame.src = '/risks#' + wanted;
        document.body.appendChild(frame);
        for (let i = 0; i < 60; i++) {
            await new Promise((r) => setTimeout(r, 200));
            const doc = frame.contentDocument;
            if (doc && doc.querySelectorAll('.rl-entry').length) break;
        }
        await new Promise((r) => setTimeout(r, 300));
        const doc = frame.contentDocument;
        const entries = [...doc.querySelectorAll('.rl-entry')];
        const at = doc.getElementById(wanted);
        const out = {
            served: served.riskPatterns.length,
            wanted,
            names: entries.map((s) => s.querySelector('h3').textContent),
            rows: entries.length ? [...entries[0].querySelectorAll('dt')].map((d) => d.textContent) : [],
            inView: !!at && at.getBoundingClientRect().top < 700 && at.getBoundingClientRect().bottom > 0,
            wide: doc.documentElement.scrollWidth > doc.documentElement.clientWidth,
        };
        frame.remove();
        return out;
    })()"""))

    assert listed["names"], "the page listed nothing"
    assert len(listed["names"]) == listed["served"], listed
    assert sorted(listed["names"]) == sorted(rail["names"]), (
        "the page names a risk differently from the library rail")
    assert listed["rows"] == ["Risk mechanism", "Raised when", "May lead to",
                              "Suggested controls", "Related motifs"], listed["rows"]
    assert listed["inView"], f"/risks#{listed['wanted']} did not open at that risk"
    assert not listed["wide"], "the page scrolls sideways"
    assert rail["linked"], "the library does not link to the page"


def test_a_second_process_model_is_drawn_on_its_own_and_switched_to(scene_restored) -> None:
    """The canvas held one process model, so the development process had nowhere to go."""
    loop, handle = scene_restored
    ids = loop.run_until_complete(handle.js(_TWO_POOLS))
    _back_to_business(loop, handle)
    _settle(loop, handle, "document.querySelectorAll('#process-canvas .pc-pool').length", 0, tries=40)
    loop.run_until_complete(handle.js(
        "window.__answers = ['Development process', 'Data team'];"
        " window.prompt = () => window.__answers.shift() || null; 1"))
    pools = """[...document.querySelectorAll('#process-canvas .pc-pool')]
        .map((g) => g.getAttribute('data-band')).sort()"""
    picked = """(() => { const s = document.querySelector('#process-palette .pp-model');
        return s ? s.selectedOptions[0].textContent : null; })()"""

    # The palette scrolls; an earlier test may have left it scrolled past its top row.
    loop.run_until_complete(handle.js(
        "(document.querySelector('#process-palette .pp-model-add') || {scrollIntoView() {}})"
        ".scrollIntoView({ block: 'nearest' }); 1"))
    at = _centre(loop, handle, "#process-palette .pp-model-add")
    assert at, "there is no way to start another process model"
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    _settle(loop, handle, picked, None, tries=40)
    opened = loop.run_until_complete(handle.js(picked))
    empty = loop.run_until_complete(handle.js(pools))

    loop.run_until_complete(handle.js("""(() => {
        const palette = document.querySelector('#process-palette');
        if (palette.classList.contains('folded')) palette.querySelector('.pp-fold').click();
        return 1;
    })()"""))
    time.sleep(0.4)
    at = loop.run_until_complete(handle.js("""(() => {
        const b = [...document.querySelectorAll('#process-palette .pp-item')]
            .find((item) => item.textContent.trim() === 'Participant');
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    _settle(loop, handle, "document.querySelectorAll('#process-canvas .pc-pool').length", 0, tries=40)
    in_new = loop.run_until_complete(handle.js(pools))

    loop.run_until_complete(handle.js("""(() => {
        const s = document.querySelector('#process-palette .pp-model');
        s.value = [...s.options].find((o) => o.textContent.startsWith('Business process')).value;
        s.dispatchEvent(new Event('change'));
        return 1;
    })()"""))
    time.sleep(0.8)
    back = loop.run_until_complete(handle.js(pools))

    assert opened == "Development process (0)", f"the new model was not opened: {opened!r}"
    assert empty == [], f"the new model drew the other model's pools: {empty}"
    assert len(in_new) == 1 and in_new[0] not in (ids["ask"], ids["answer"]), in_new
    assert len(back) == 2 and in_new[0] not in back, (
        f"switching back drew {back}, the new pool was {in_new}")


_BY_CATEGORY = chr(10).join([
    "@prefix beam: <http://w3id.org/beam/core#> .",
    "@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .",
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
    "@prefix ex: <http://example.org/possible#> .",
    'ex:S a beam:System ; rdfs:label "Help desk" ; beam:hasProcess ex:Retrieve, ex:Build, ex:Generate ;'
    " beam:hasResource ex:Question, ex:Manuals, ex:Passages, ex:Prompt, ex:LLM, ex:Answer .",
    'ex:Question a beam:Data ; rdfs:label "Question" ; pair:playsRole pair:UserInputRoles .',
    'ex:Manuals a beam:Data ; rdfs:label "Manuals" ; pair:playsRole pair:KnowledgeContextRoles .',
    'ex:Retrieve a beam:Process ; rdfs:label "Find passages" ; pair:playsRole pair:RetrievalRoles ;'
    " beam:use ex:Question, ex:Manuals ; beam:produce ex:Passages .",
    'ex:Passages a beam:Data ; rdfs:label "Passages" ; pair:playsRole pair:KnowledgeContextRoles .',
    'ex:Build a beam:Transform ; rdfs:label "Build prompt" ; pair:playsRole pair:GenerationRoles ;'
    " beam:use ex:Question, ex:Passages ; beam:produce ex:Prompt .",
    'ex:Prompt a beam:Data ; rdfs:label "Prompt" ; pair:playsRole pair:PromptResponseRoles .',
    'ex:LLM a beam:StatisticalModel ; rdfs:label "LLM" ; pair:playsRole pair:ModelRoles .',
    'ex:Generate a beam:Infer ; rdfs:label "Answer" ; pair:playsRole pair:GenerationRoles ;'
    " beam:use ex:Prompt, ex:LLM ; beam:produce ex:Answer .",
    'ex:Answer a beam:Data ; rdfs:label "Reply" ; pair:playsRole pair:PromptResponseRoles .',
])


def test_a_possible_risk_is_offered_and_one_click_makes_it_a_finding(scene_restored) -> None:
    """A RAG tagged only with categories raises nothing, because a category
    matches nothing. Under the findings it is offered as possible risks, each
    with the tags it needs, and applying one raises it for real."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js(
        "window.PairAI.Editor.setValue(" + json.dumps(_BY_CATEGORY) + "); 1"))
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 0, tries=40)
    loop.run_until_complete(handle.js("""(() => {
        if (document.querySelector('#drawer').classList.contains('collapsed'))
            document.querySelector('#drawer-toggle').click();
        document.querySelector('[data-drawer-tab="findings"]').click();
        document.querySelector('#btn-assess').click();
        return 1;
    })()"""))
    cards = _settle(loop, handle, "document.querySelectorAll('#possible-list .possible-place').length", 0, tries=120)
    assert cards, "no possible risk was offered for a diagram tagged by category"
    before = loop.run_until_complete(handle.js(
        "Number(document.querySelector('#findings-count').textContent || 0)"))
    assert before == 0, "a category raised a finding on its own"

    at = loop.run_until_complete(handle.js("""(() => {
        const b = document.querySelector('#possible-list .possible-place .btn');
        b.scrollIntoView({ block: 'center' });
        const r = b.getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
                 label: b.closest('.possible-card').querySelector('strong').textContent };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    after = _settle(loop, handle, "Number(document.querySelector('#findings-count').textContent || 0)", 0, tries=120)
    titles = loop.run_until_complete(handle.js(
        "[...document.querySelectorAll('#findings-list .finding-head strong')].map((s) => s.textContent)"))
    wanted = at["label"].replace("Possible ", "Candidate ")
    assert after and wanted in titles, f"applying {at['label']} did not raise it: {titles}"


def test_the_starter_scene_names_the_steps_an_activity_is_carried_out_by(scene_restored) -> None:
    """Starter loads the tutorial's scene; the activity's editor offers the steps of the
    system it refines, and the chip opens that system with those steps picked out."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    at = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#btn-starter').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()"""))
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    find = """(() => {
        const box = [...document.querySelectorAll('#process-canvas .pc-activity')]
            .find((g) => g.textContent.includes('Answer question'));
        if (!box) return null;
        const part = (sel) => { const n = box.querySelector(sel); if (!n) return null;
            const r = n.getBoundingClientRect();
            return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }; };
        return { pencil: part('.pc-edit'), chip: part('.pc-open') };
    })()"""
    where = _settle(loop, handle, find, None, tries=40)
    state = loop.run_until_complete(handle.js("""(() => ({
        level: window.PairAI.state.level, scoped: window.PairAI.state.scopedSystem,
        starts: window.PairAI.Editor.getValue().slice(0, 80),
        drawn: [...document.querySelectorAll('#process-canvas .pc-activity')].map((g) => g.textContent.slice(0, 20)),
        model: [...document.querySelectorAll('select')].map((s) => s.value).join('|') }))()"""))
    assert where and where["pencil"] and where["chip"], f"Starter did not draw the refined activity: {where} {state}"

    loop.run_until_complete(handle.click(where["pencil"]["x"], where["pencil"]["y"]))
    time.sleep(1)
    editor = loop.run_until_complete(handle.js("""(() => {
        const steps = document.querySelector('#process-detail #pd-steps');
        return {
            offered: steps ? steps.options.length : 0,
            named: steps ? [...steps.selectedOptions].map((o) => o.textContent).sort() : [],
            carry: !!document.querySelector('#process-detail #pd-carry'),
        };
    })()"""))
    assert editor["named"] == ["Build prompt", "Find passages", "Generate answer"], editor
    assert editor["offered"] == 3, "offered a step of a system this activity does not refine"
    assert not editor["carry"], "offered to carry data that already names its element"
    loop.run_until_complete(handle.js('document.querySelector("#process-detail").classList.add("hidden")'))

    where = loop.run_until_complete(handle.js(find))
    loop.run_until_complete(handle.click(where["chip"]["x"], where["chip"]["y"]))
    picked = _settle(loop, handle, """(() => [...document.querySelectorAll('#canvas .node.highlight')]
        .map((g) => g.textContent.trim()).filter(Boolean).length || null)()""", None, tries=30)
    assert _on_architecture(loop, handle), "the chip did not open the architecture"
    labels = loop.run_until_complete(handle.js("""[...document.querySelectorAll('.node.highlight')]
        .map((g) => g.dataset.id.split('#').pop()).sort()"""))
    assert labels == ["BuildPrompt", "FindPassages", "GenerateAnswer"], (picked, labels)


def test_an_edit_on_the_process_canvas_keeps_the_process_level(scene_restored) -> None:
    """Adding or deleting on the business canvas rewrites the document, and the
    rewrite must not carry the reader off to the architecture: not when what is
    on the page is only a data object or a note, and not when the last pool goes."""
    loop, handle = scene_restored
    level = "document.querySelector('#level-business').classList.contains('active')"
    # a palette entry may ask for a name; a dialog would block a headless page
    loop.run_until_complete(handle.js("window.prompt = () => 'Probe'; window.confirm = () => true; 1"))
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue(''); 1"))
    time.sleep(1.5)
    at = _spot(loop, handle, "document.querySelector('#level-business')")
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    time.sleep(1)
    seen = {"start": loop.run_until_complete(handle.js(level))}
    names = loop.run_until_complete(handle.js("""(() => {
        const host = document.querySelector('#process-palette');
        if (!host.querySelector('.pp-item')) host.querySelector('.pp-fold')?.click();
        return [...host.querySelectorAll('.pp-item')].map((b) => b.textContent.trim());
    })()"""))
    artifacts = [n for n in names if n.lower() in ("data object", "data store", "text annotation", "note")]
    assert artifacts, names
    for label in artifacts[:2]:
        _add_from_palette(loop, handle, label)
        seen["added " + label] = loop.run_until_complete(handle.js(level))
    pool = next((n for n in names if n.lower() in ("participant", "pool")), None)
    if pool:
        _add_from_palette(loop, handle, pool)
        seen["added " + pool] = loop.run_until_complete(handle.js(level))
        loop.run_until_complete(handle.js("""(async () => {
            const ttl = window.PairAI.Editor.getValue();
            const view = await (await fetch('/api/process', { method: 'POST',
                headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ttl }) })).json();
            const id = view.participants[0].id;
            const out = await (await fetch('/api/process-edit', { method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ttl, op: 'delete', element: id }) })).json();
            window.PairAI.Editor.setValue(out.ttl);
            return 1;
        })()"""))
        time.sleep(2.5)
        seen["deleted the last pool"] = loop.run_until_complete(handle.js(level))
    assert all(seen.values()), f"an edit left the process level: {seen} (palette: {names})"


def test_a_box_a_step_reads_and_writes_is_drawn_once_with_two_arrowheads(scene_restored) -> None:
    """Read and written is one box with an arrow each way, never the same box twice."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    loop.run_until_complete(handle.js("""(async () => {
      const get = async (name) => (await fetch('/api/examples/' + name)).json();
      const a = await get('support_chatbot'), p = await get('customer_support');
      const ttl = a.ttl + String.fromCharCode(10, 10) + p.ttl;
      const r = await (await fetch('/api/process-edit', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ttl, op: 'set-data-direction', reference: 'http://w3id.org/airiskkg/example/customer-support#KnowledgeRef',
          activity: 'http://w3id.org/airiskkg/example/customer-support#AnswerQuestion', direction: 'both' }) })).json();
      window.PairAI.Editor.setValue(r.ttl);
      return 1; })()"""))
    seen = _settle(loop, handle, """(() => {
        const boxes = [...document.querySelectorAll('#process-canvas [data-node]')]
          .filter((g) => g.querySelector('.pc-data-label') && g.textContent.includes('Knowledge base'));
        if (!boxes.length) return null;
        const links = boxes.flatMap((g) => [...g.querySelectorAll('.pc-data-link')]);
        const both = links.filter((l) => l.getAttribute('marker-start')).length;
        // waited for the edit's redraw, not for the drawing that was there before it
        return both ? { boxes: boxes.length, both } : null;
    })()""", None, tries=30)
    assert seen, "the knowledge base was not drawn"
    # the store is also written by the agent's step, so it is drawn by that step too: one box per step
    assert seen["both"] == 1, f"no box carries an arrow each way: {seen}"
    assert seen["boxes"] == 2, f"one step drew the box twice: {seen}"


def test_a_role_with_finer_roles_heads_its_own_submenu(scene_restored) -> None:
    """An arrow read as "open me, you cannot stop here": the submenu a role opens starts
    with the role itself, so Generative Model is picked as plainly as Foundation LLM."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js("window.PairAI.Editor.setValue(" + json.dumps(_KINDS) + "); 1"))
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas g.node').length", 0, tries=40)
    loop.run_until_complete(handle.js("window.PairAI.GraphView.fit(); 1"))
    time.sleep(0.5)
    _open_popup_on(loop, handle, "LLM")
    _open_role_menu(loop, handle)
    at = _centre(loop, handle, "#nd-role-mp .mp-list > .mp-row")
    loop.run_until_complete(handle.hover(at["x"], at["y"]))
    for label in ("Model", "Generative Model"):
        menus = _menu_rows(loop, handle)
        row = next(r for r in menus[-1]["rows"] if r["label"] == label)
        loop.run_until_complete(handle.hover(row["x"], row["y"]))
        time.sleep(0.4)
    menus = _menu_rows(loop, handle)
    first = menus[-1]["rows"][0]
    assert first["label"] == "Use Generative Model", [r["label"] for r in menus[-1]["rows"]]
    loop.run_until_complete(handle.click(first["x"], first["y"]))
    time.sleep(0.6)
    chips = loop.run_until_complete(handle.js(
        "[...document.querySelectorAll('#nd-role-mp .mp-chip')].map((c) => c.textContent.replace('×', '').trim())"))
    assert "Generative Model" in chips, chips


def test_a_system_moves_as_one_with_its_frame(scene_restored) -> None:
    """A dragged frame takes every element inside it along; a click still selects it."""
    loop, handle = scene_restored
    loop.run_until_complete(handle.js('document.querySelector("#level-architecture").click()'))
    _settle(loop, handle, "document.querySelectorAll('#canvas .system-bound').length", 0, tries=40)
    before = loop.run_until_complete(handle.js("""(() => {
        const frame = document.querySelector('#canvas .system-bound');
        const members = new Set([...frame.parentNode.querySelectorAll('.node')].map((n) => n.dataset.id));
        const box = frame.querySelector('.system-bound-box').getBoundingClientRect();
        const id = frame.dataset.id;
        const sys = window.PairAI.state.lastGraph.systems.find((s) => s.id === id);
        const own = (sys.members || []).filter((m) => document.querySelector(`#canvas .node[data-id="${CSS.escape(m)}"]`));
        const at = Object.fromEntries(own.map((m) => { const r = document.querySelector(`#canvas .node[data-id="${CSS.escape(m)}"]`).getBoundingClientRect(); return [m, [r.left, r.top]]; }));
        return { x: Math.round(box.left + 6), y: Math.round(box.top + 6), at, id };
    })()"""))
    assert before["at"], "the frame holds nothing drawn"
    loop.run_until_complete(handle.drag(before["x"], before["y"], before["x"] + 80, before["y"] + 40))
    time.sleep(0.6)
    after = loop.run_until_complete(handle.js("""(() => Object.fromEntries(Object.keys(%s).map((m) => {
        const r = document.querySelector(`#canvas .node[data-id="${CSS.escape(m)}"]`).getBoundingClientRect();
        return [m, [r.left, r.top]]; })))()""" % json.dumps(before["at"])))
    shifts = {round(after[m][0] - before["at"][m][0]) for m in after}
    assert len(shifts) == 1 and next(iter(shifts)) > 20, f"the elements did not move together: {shifts}"


def test_a_data_box_joined_to_a_step_still_opens_its_panel(scene_restored) -> None:
    """The box's connector dot covered most of a small box, so a click started a
    connection instead: a press that goes nowhere opens the box's panel."""
    loop, handle = scene_restored
    # what an earlier test left open must not sit over the box
    loop.run_until_complete(handle.js(
        "document.querySelectorAll('.node-detail, #process-detail').forEach((d) => d.classList.add('hidden')); 1"))
    _back_to_business(loop, handle)
    at = _spot(loop, handle, "document.querySelector('#btn-starter')")
    loop.run_until_complete(handle.click(at["x"], at["y"]))
    box = _settle(loop, handle, """(() => { const g = [...document.querySelectorAll('#process-canvas [data-node]')]
        .find((n) => n.querySelector('.pc-data-label') && n.textContent.includes('Knowledge base'));
        if (!g) return null; const r = g.querySelector('path, rect, polygon').getBoundingClientRect();
        return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }; })()""", None, tries=40)
    assert box, "the starter scene drew no knowledge base"
    loop.run_until_complete(handle.click(box["x"], box["y"]))
    _settle(loop, handle, "document.querySelector('#process-detail').classList.contains('hidden')", True, tries=20)
    panel = loop.run_until_complete(handle.js("""({ hidden: document.querySelector('#process-detail').classList.contains('hidden'),
        head: (document.querySelector('#process-detail .nd-head') || {}).textContent,
        ways: document.querySelectorAll('#process-detail .pd-data-way').length })"""))
    assert not panel["hidden"] and panel["head"] == "data store", panel
    assert panel["ways"] >= 1, "the panel does not say which way each step uses it"
    loop.run_until_complete(handle.js('document.querySelector("#process-detail").classList.add("hidden"); 1'))


def test_descending_after_an_assessment_dims_nothing(scene_restored) -> None:
    """A finding picked before, or the steps an activity names, left the opened
    architecture greyed out until a click on blank canvas."""
    loop, handle = scene_restored
    _back_to_business(loop, handle)
    loop.run_until_complete(handle.js('document.querySelector("#btn-assess").click()'))
    _settle(loop, handle, 'document.querySelectorAll(".finding-card").length', 0, tries=150)
    loop.run_until_complete(handle.js("""(() => { const h = document.querySelector('.finding-card .finding-head'); h.click(); return 1; })()"""))
    time.sleep(1)
    _back_to_business(loop, handle)
    _descend(loop, handle)
    time.sleep(2.5)
    dim = loop.run_until_complete(handle.js("document.querySelector('#viewport').classList.contains('has-highlight')"))
    assert not dim, "the opened architecture is greyed out"


def test_a_resized_editor_still_folds_away(page) -> None:
    """Dragging the divider wrote an inline width that beat the folded rule, so the
    editor folded to its rail and kept all its room."""
    loop, handle = page
    width = "Math.round(document.querySelector('#editor-pane').getBoundingClientRect().width)"
    divider = _spot(loop, handle, "document.querySelector('#divider')")
    loop.run_until_complete(handle.drag(divider["x"], divider["y"] + 120, divider["x"] + 160, divider["y"] + 120))
    time.sleep(0.6)
    dragged = loop.run_until_complete(handle.js(width))
    toggle = _spot(loop, handle, "document.querySelector('#btn-editor-toggle')")
    loop.run_until_complete(handle.click(toggle["x"], toggle["y"]))
    time.sleep(1)
    folded = loop.run_until_complete(handle.js(width))
    toggle = _spot(loop, handle, "document.querySelector('#btn-editor-toggle')")
    loop.run_until_complete(handle.click(toggle["x"], toggle["y"]))
    time.sleep(1)
    back = loop.run_until_complete(handle.js(width))
    assert folded < 80, f"the editor folded to {folded}px after a resize to {dragged}px"
    assert abs(back - dragged) <= 4, f"unfolded to {back}px, not the {dragged}px it was resized to"
