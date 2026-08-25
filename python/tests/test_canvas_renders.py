"""Does the canvas actually draw anything?

Every other check in this repository passed while the business canvas showed a
blank rectangle for three rounds of fixes. The element ids all existed, the CSS
classes were all defined, the JavaScript parsed, the endpoints returned correct
data, and 196 tests were green - because none of them ran the page. The renderer
was fine; a wiring call had landed inside `renderFindings()` instead of `init()`,
so nothing initialised until an assessment had been run.

Only one thing catches that: loading the real page in a real browser and looking
at what came out. This does that headlessly, and skips rather than pretends when
no browser is installed.

It asserts presence and rough shape, not pixels. A screenshot comparison would
fail on a font change and teach everyone to ignore it.
"""

from __future__ import annotations

import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

from airiskkg.paths import REPO_ROOT

STATIC = REPO_ROOT / "python" / "src" / "airiskkg" / "webapp" / "static"

_BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google-chrome",
    "chromium",
    "msedge",
)


def _browser() -> str | None:
    for candidate in _BROWSERS:
        if Path(candidate).exists():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def served():
    """The real app, on a real port. Nothing is stubbed: a bug that only appears
    once the whole page is wired together is exactly what this is for."""
    flask = pytest.importorskip("flask")  # noqa: F841
    from airiskkg.webapp.app import create_app

    port = _free_port()
    app = create_app(local_examples=False)
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, use_reloader=False, threaded=True),
        daemon=True,
    )
    server.start()

    import urllib.error
    import urllib.request

    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    else:
        pytest.skip("the workbench did not come up")
    return port


def _dump_dom(browser: str, url: str, budget: int = 15000) -> str:
    """Virtual time fast-forwards timers, but not the work behind a fetch - an
    assessment takes a couple of real seconds, so a probe that runs one needs a
    budget that accounts for it."""
    completed = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--window-size=1400,900",
            f"--virtual-time-budget={budget}",
            "--dump-dom",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    return completed.stdout


@pytest.fixture(scope="module")
def rendered(served):
    """Load both graphs the way a person would, then read the resulting page."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    probe = STATIC / "_render_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <script>
  window.addEventListener("load", async () => {
    const a = await (await fetch("/api/examples/simple_graph_rag")).json();
    const p = await (await fetch("/api/examples/energy_customer_service")).json();
    window.PairAI.Editor.setValue(a.ttl + String.fromCharCode(10,10) + p.ttl);
    setTimeout(() => document.querySelector("#level-business").click(), 2500);
  });
  </script>
"""
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        return _dump_dom(browser, f"http://127.0.0.1:{served}/static/_render_probe.html")
    finally:
        probe.unlink(missing_ok=True)


def test_the_business_canvas_draws_its_pools_and_activities(rendered) -> None:
    """The bug this file exists for: an empty <svg> and no error anywhere."""
    canvas = re.search(r'<svg id="process-canvas".*?</svg>', rendered, re.S)
    assert canvas, "the business canvas is not in the page at all"

    markup = canvas.group(0)
    assert 'class="pc-pool' in markup, "no pools were drawn"
    assert 'class="pc-activity' in markup, "no activities were drawn"
    assert "pc-flow message" in markup, "no message flow between the two participants"
    assert "Northwind Energy" in markup and "Customer" in markup


def test_the_architecture_canvas_still_draws_beside_it(rendered) -> None:
    """Adding a business layer must not cost the layer that was already there."""
    assert 'class="node' in rendered, "no architecture nodes were drawn"


def test_the_bpmn_palette_stays_on_its_own_level(rendered) -> None:
    """It used to un-hide itself on every render, so it sat on top of the
    architecture canvas over the BEAM palette whichever level was chosen."""
    palette = re.search(r'id="process-palette"[^>]*class="([^"]*)"', rendered) or re.search(
        r'class="([^"]*)"[^>]*id="process-palette"', rendered
    )
    assert palette, "the business palette is missing"
    # The probe ends on the business level, so here it should be showing.
    assert "hidden" not in palette.group(1)


def test_nothing_threw_while_the_page_wired_itself_up(rendered) -> None:
    """A silent failure is the failure mode: the canvas came up blank with no
    console error, because the initialiser simply never ran."""
    assert "Uncaught" not in rendered


# Clicking is not tested here. A synthetic click lands on whatever element you
# name it at, so it proved nothing while a real one was being retargeted by
# pointer capture and reaching no handler at all. Interaction is tested with
# real input in test_canvas_interaction.py.


def test_picking_the_process_example_gives_something_assessable(served) -> None:
    """The whole scene, from one choice in the dropdown.

    Selecting the process used to load the process alone: the business diagram
    drew, the architecture canvas stayed empty, and Run assessment finished with
    nothing - which reads as a broken tool rather than a missing dependency."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    probe = STATIC / "_scene_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  window.addEventListener("load", () => {
    setTimeout(() => {
      const sel = document.querySelector("#example-select");
      sel.value = "energy_customer_service";
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      setTimeout(() => {
        document.querySelector("#btn-assess").click();
        setTimeout(() => {
          log("nodes=" + document.querySelectorAll(".node").length);
          log("findings=" + (document.querySelector("#findings-count").textContent || "0"));
          log("activities=" + (document.querySelector("#process-count").textContent || "0"));
        }, 9000);
      }, 4500);
    }, 2500);
  });
  </script>
"""
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_scene_probe.html", budget=45000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""

    # An empty report must fail, not pass. Asserting only that "nodes=0" is
    # absent is true of a probe that never ran, and a check that passes when
    # nothing happened is worse than no check. 
    counts = dict(re.findall(r"(\w+)=(\d+)", report))
    assert {"nodes", "findings", "activities"} <= counts.keys(), (
        f"the probe did not report: {report!r}"
    )
    assert int(counts["activities"]) > 0, "the process itself did not load"
    assert int(counts["nodes"]) > 0, "the architectures did not come with the process"
    assert int(counts["findings"]) > 0, "nothing was assessable"


def _drive(served, script, budget=45000):
    """Run a snippet against the real page and read back what it logged."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")
    probe = STATIC / "_drive_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    probe.write_text(
        source.replace("</body>", '<div id="probe-log"></div><script>' + script + "</script></body>"),
        encoding="utf-8",
    )
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_drive_probe.html", budget=budget)
    finally:
        probe.unlink(missing_ok=True)
    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    assert report, "the probe did not report - it may not have finished"
    return report


def test_an_empty_workbench_asks_which_layer_rather_than_guessing(served) -> None:
    """The two layers are different jobs, and which one someone came to do is
    not guessable. Before a choice, neither layer's tools are on screen."""
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", () => setTimeout(() => {
      log("asks=" + !!document.querySelector("#start-business"));
      log("unstarted=" + document.querySelector("#canvas-wrap").classList.contains("unstarted"));
      document.querySelector("#start-architecture").click();
      setTimeout(() => log("after=" + document.querySelector("#canvas-wrap").classList.contains("unstarted")), 800);
    }, 2000));
    """, budget=20000)

    assert "asks=true|" in report
    assert "unstarted=true|" in report, "both palettes were on screen before a choice"
    assert "after=false|" in report, "choosing a layer did not start the workbench"


def test_a_process_example_opens_on_the_business_layer(served) -> None:
    """A process was opened to be looked at. The presence of an architecture
    used to win, so loading a business example dropped the reader into the
    architecture and the BPMN diagram had to be hunted for."""
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", () => setTimeout(() => {
      const s = document.querySelector("#example-select");
      s.value = "energy_customer_service";
      s.dispatchEvent(new Event("change", { bubbles: true }));
      setTimeout(() => {
        log("business=" + document.querySelector("#level-business").classList.contains("active"));
        log("activities=" + (document.querySelector("#process-count").textContent || "0"));
      }, 6000);
    }, 2000));
    """)

    assert "business=true|" in report, "the process example did not open on its own layer"
    assert "activities=0|" not in report


def test_choosing_a_layer_hands_over_the_tools_for_it(served) -> None:
    """Choosing "a business process" on an empty workbench used to do nothing
    visible: the palette that makes a process is built on first render, and
    there was no process to render - so the answer led to a blank canvas with
    nothing to press and no way back."""
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", () => setTimeout(() => {
      document.querySelector("#start-business").click();
      setTimeout(() => {
        log("tools=" + document.querySelectorAll("#process-palette .pp-item").length);
        log("wayback=" + !document.querySelector("#level-switch").classList.contains("hidden"));
        log("started=" + document.querySelector("#canvas-wrap").classList.contains("started"));
      }, 1500);
    }, 2000));
    """, budget=20000)

    assert "tools=0|" not in report, "the business palette was empty after choosing it"
    assert "wayback=true|" in report, "no way back to the architecture layer"
    assert "started=true|" in report, "the opening question stayed on screen"


def test_descending_is_not_dragged_back_to_the_business_layer(served) -> None:
    """The landing rule ran on every refresh, and descending triggers one - so
    the canvas switched to the architecture and was immediately pulled back. It
    looked like a glitch and was a rule fighting the click that caused it."""
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", () => setTimeout(() => {
      const s = document.querySelector("#example-select");
      s.value = "energy_customer_service";
      s.dispatchEvent(new Event("change", { bubbles: true }));
      setTimeout(() => {
        log("landed=" + (document.querySelector("#level-business").classList.contains("active") ? 1 : 0));
        const box = document.querySelector(".pc-activity.refined .pc-box");
        log("box=" + (box ? 1 : 0));
        if (box) box.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        setTimeout(() => {
          log("arch=" + (document.querySelector("#level-architecture").classList.contains("active") ? 1 : 0));
          log("nodes=" + document.querySelectorAll(".node").length);
        }, 4500);
      }, 7000);
    }, 2000));
    """)

    counts = dict(re.findall(r"(\w+)=(\d+)", report))
    assert counts.get("landed") == "1", "the process example did not open on the business layer"
    assert counts.get("box") == "1", "no AI activity was drawn to descend from"
    assert counts.get("arch") == "1", "descending bounced back to the business layer"
    assert int(counts.get("nodes", 0)) > 0, "the architecture did not draw after descending"
