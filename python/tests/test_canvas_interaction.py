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
    window.Editor.setValue(a.ttl + nl + m.ttl + nl + p.ttl);
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
