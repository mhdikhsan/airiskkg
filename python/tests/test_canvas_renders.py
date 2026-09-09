"""Does the canvas actually draw anything?"""

from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

from airiskkg.paths import REPO_ROOT
from conftest import process_path  # noqa: E402

pytestmark = pytest.mark.browser

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
    """The real app, on a real port."""
    flask = pytest.importorskip("flask")  # noqa: F841
    from airiskkg.webapp.app import create_app

    port = _free_port()
    # The fixtures ride along so the canvas has a rich process model to draw -
    # lanes, a gateway, two architectures. They are not part of the curated set
    # the deployment offers; see conftest.FIXTURE_DIR.
    from conftest import FIXTURE_DIR

    app = create_app(local_examples=False, extra_example_dirs=[FIXTURE_DIR])
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
        # The page is UTF-8 and the DOM it dumps carries the glyphs the canvas draws.
        encoding="utf-8",
        errors="replace",
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
    const a = await (await fetch("/api/examples/wien_energie_bottina")).json();
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
    assert "Wien Energie Chatbot" in markup and "Customer" in markup


def test_the_business_canvas_draws_the_data_and_what_it_is(rendered) -> None:
    """dpv:PersonalData on an item definition is what business_data_bridge.rq
    turns into a data category on the architecture, so leaving it off the
    diagram hides the cause of the findings it produces."""
    canvas = re.search(r'<svg id="process-canvas".*?</svg>', rendered, re.S)
    assert canvas, "the business canvas is not in the page at all"
    markup = canvas.group(0)

    assert "pc-data-shape" in markup, "no data objects were drawn"
    assert "pc-data-link" in markup, "data objects are drawn but not associated with any activity"
    assert "Customer question" in markup, "the customer question data object is not labelled"
    assert "Personal data" in markup, (
        "the data object carries dpv:PersonalData and the diagram does not say so"
    )


def test_a_long_activity_name_wraps_rather_than_being_cut(rendered) -> None:
    """"Take over the conv..." reads as a different activity from the one it is."""
    canvas = re.search(r'<svg id="process-canvas".*?</svg>', rendered, re.S)
    # Only what is painted on the box.
    painted = " ".join(re.findall(r'<text[^>]*class="pc-label"[^>]*>([^<]*)</text>', canvas.group(0)))
    assert "live" in painted, (
        "the second half of \"Take over the conversation in live chat\" never made it onto the box; "
        "the labels drawn were: " + painted
    )


def test_a_pool_with_lanes_is_banded_and_named(rendered) -> None:
    """The model declared three lanes all along and the canvas drew none of
    them, so the human step and the answer sources sat in the same undivided
    strip as the agent chain that calls them."""
    canvas = re.search(r'<svg id="process-canvas".*?</svg>', rendered, re.S)
    markup = canvas.group(0)
    assert "pc-lane-box" in markup, "the chatbot pool declares lanes and none was drawn"

    painted = set(re.findall(r'<text[^>]*class="pc-lane-label"[^>]*>([^<]*)</text>', markup))
    assert {"LLM agent chain", "Answer source"} <= painted, (
        f"the lane names never reached the canvas; drawn: {sorted(painted)}"
    )


def test_events_and_gateways_are_drawn_the_way_bpmn_draws_them(rendered) -> None:
    """A start event is a ring, an end event a thick one, a gateway a diamond."""
    canvas = re.search(r'<svg id="process-canvas".*?</svg>', rendered, re.S)
    markup = canvas.group(0)

    assert "pc-ev-ring start" in markup, "no start event was drawn"
    assert "pc-ev-ring end" in markup, "no end event was drawn"
    assert "pc-gate-box" in markup, "no gateway diamond was drawn"
    assert "pc-ev-glyph" in markup, "the message start event carries no trigger glyph"

    painted = " ".join(re.findall(r'<text[^>]*class="pc-ev-label"[^>]*>([^<]*)</text>', markup))
    assert "Which source can" in painted, (
        f"the gateway is drawn but not named; labels drawn: {painted}"
    )


def test_sequence_flow_is_drawn_from_the_model_not_from_what_sits_beside_what(rendered) -> None:
    """The canvas used to draw an arrow between consecutive boxes in layout
    order, whether or not a flow joined them: a three-way branch came out as a
    straight chain, and the flow to the human step was not drawn at all. Every
    top-level flow the model declares must now be on screen, and no more."""
    from rdflib import RDF, Graph, URIRef

    from airiskkg.paths import EXAMPLE_DIR

    classes = "https://sBPMN.github.io/2.0/classes#"
    props = "https://sBPMN.github.io/2.0/properties#"
    model = Graph().parse(process_path("energy_customer_service"), format="turtle")

    # A flow inside a sub-process is not drawn until the box is expanded.
    nested = {
        child
        for activity in model.subjects(RDF.type, URIRef(classes + "subProcess"))
        for child in model.objects(activity, URIRef(props + "contains"))
    }
    declared = [
        flow
        for flow in model.subjects(RDF.type, URIRef(classes + "sequenceFlow"))
        if model.value(flow, URIRef(props + "sourceRef")) not in nested
        and model.value(flow, URIRef(props + "targetRef")) not in nested
    ]

    canvas = re.search(r'<svg id="process-canvas".*?</svg>', rendered, re.S)
    drawn = len(re.findall(r'class="pc-seq"', canvas.group(0)))
    assert drawn == len(declared), (
        f"the model declares {len(declared)} sequence flows outside a sub-process "
        f"and the canvas drew {drawn}"
    )


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


# Clicking is not tested here.


def test_picking_the_process_example_gives_something_assessable(served) -> None:
    """The whole scene, from one choice in the dropdown."""
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

    # An empty report must fail, not pass.
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
    """The two layers are different jobs, and which one someone came to do is not guessable."""
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
    """A process was opened to be looked at."""
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
    nothing to press and no way back.

    This drives the handler synthetically, so it checks what choosing a layer
    *does*, never that the card can be clicked - and the card later stopped
    being clickable while this stayed green. Reaching it with a real mouse is
    test_canvas_interaction.py::test_the_opening_choice_answers_a_real_click.
    """
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
        // The chip, not the box: the box selects and stays put on purpose.
        const chip = document.querySelector(".pc-activity.refined .pc-open");
        log("box=" + (chip ? 1 : 0));
        if (chip) chip.dispatchEvent(new MouseEvent("click", { bubbles: true }));
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


def test_picking_a_scene_replaces_what_was_there(served) -> None:
    """Switching examples must not add up."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    probe = STATIC / "_replace_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  const pick = (name) => {
    const sel = document.querySelector("#example-select");
    sel.value = name;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  };
  window.addEventListener("load", () => {
    setTimeout(() => {
      pick("simple_graph_rag");                       // an architecture first
      setTimeout(() => {
        pick("energy_customer_service");              // then the scene
        setTimeout(() => {
          const ttl = window.PairAI.Editor.getValue();
          log("firstleft=" + (ttl.includes("graphrag-example") ? 1 : 0));
          log("bottina=" + (ttl.includes("AgentChain") ? 1 : 0));
          log("process=" + (ttl.includes("energy-cs") ? 1 : 0));
        }, 6000);
      }, 5000);
    }, 2500);
  });
  </script>
"""
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_replace_probe.html", budget=30000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert "firstleft" in seen, f"the probe never reported: {report!r}"

    assert seen["firstleft"] == 0, (
        "the architecture loaded before the scene is still in the editor - it was "
        "added, not replaced, and its findings will be counted alongside the scene's"
    )
    for part in ("bottina", "process"):
        assert seen[part] == 1, f"the scene is missing its {part} half: {report}"


def test_loading_another_example_clears_the_last_run(served) -> None:
    """The canvas redrew and the risk list did not."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    probe = STATIC / "_stale_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  const pick = (name) => {
    const sel = document.querySelector("#example-select");
    sel.value = name;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const drawerCounts = (tag) => {
    log(tag + "findings=" + (document.querySelector("#findings-count").textContent || "0"));
    log(tag + "motifs=" + (document.querySelector("#motifs-count").textContent || "0"));
    log(tag + "derived=" + (document.querySelector("#derived-count").textContent || "0"));
  };
  window.addEventListener("load", () => {
    setTimeout(() => {
      pick("wien_energie_bottina");
      setTimeout(() => {
        document.querySelector("#btn-assess").click();
        setTimeout(() => {
          drawerCounts("before");
          pick("wien_energie_tariff_change");     // a different document
          setTimeout(() => drawerCounts("after"), 4000);
        }, 11000);
      }, 4000);
    }, 2500);
  });
  </script>
"""
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_stale_probe.html", budget=45000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert seen.get("beforefindings", 0) > 0, f"the first example assessed to nothing: {report}"

    for what in ("findings", "motifs", "derived"):
        assert seen.get("after" + what, -1) == 0, (
            f"{what} from the previous example survived loading a new one "
            f"({seen.get('after' + what)} left): {report}"
        )


def test_the_motifs_tab_explains_an_annotation_that_cannot_bind(served) -> None:
    """The two halves of "why did nothing match" used to sit in different tabs."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    bad = (
        (REPO_ROOT / "ontology" / "example" / "simple_graph_rag.ttl").read_text(encoding="utf-8")
        + '\n@prefix exx: <http://example.org/xx#> .\n'
        'exx:Screen a <http://w3id.org/beam/core#Data> ;\n'
        '    <http://www.w3.org/2000/01/rdf-schema#label> "Screening" ;\n'
        '    <http://w3id.org/airiskkg/pair-ai#playsRole> '
        '<http://w3id.org/airiskkg/pair-ai#InputGuardrailStep> .\n'
    )

    probe = STATIC / "_guidance_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  window.addEventListener("load", () => setTimeout(() => {
    window.PairAI.Editor.setValue(BAD_TTL);
    setTimeout(() => {
      document.querySelector("#btn-assess").click();
      setTimeout(() => {
        log("flagged=" + document.querySelectorAll(".gap-candidate.flagged").length);
        log("plain=" + document.querySelectorAll(".gap-candidate:not(.flagged)").length);
        log("rows=" + document.querySelectorAll(".flagged-row").length);
        const text = document.querySelector("#motifs-list").textContent;
        log("saysWhy=" + (text.includes("process family") ? 1 : 0));
        log("leafClassNoise=" + (text.includes("leaf class") ? 1 : 0));
      }, 11000);
    }, 3000);
  }, 2000));
  </script>
""".replace("BAD_TTL", json.dumps(bad))
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_guidance_probe.html", budget=40000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert "rows" in seen, f"the probe never reported: {report!r}"

    assert seen["rows"] >= 1, "the mis-annotated element is not explained in the Motifs tab"
    assert seen["saysWhy"] == 1, "the explanation does not name the actual problem"
    assert seen["flagged"] >= 1, (
        "the element is still offered as a plain candidate, with no sign the "
        f"annotation is what is wrong: {report}"
    )
    assert seen["plain"] > 0, "every candidate was flagged; the marking is not discriminating"
    assert seen["leafClassNoise"] == 0, (
        "the input contract's warnings leaked in - they fire on every plain "
        "beam:Data and say nothing about anyone's annotation"
    )
