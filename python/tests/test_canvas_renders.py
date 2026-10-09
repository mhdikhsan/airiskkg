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


def _library() -> dict:
    """What the page should show, counted off the loaded graph rather than pinned."""
    from collections import Counter

    from airiskkg.workbench.library import library_catalogue

    catalogue = library_catalogue()
    roles = catalogue["vocabulary"]["roles"]
    families = Counter(m["family"]["label"] for m in catalogue["motifs"] if m["family"])
    return {
        "motifs": len(catalogue["motifs"]),
        "roles": len(roles),
        "quiet": sum(1 for r in roles if not r.get("motifs") and not r.get("serves")),
        "families": dict(sorted(families.items())),
    }
from conftest import (  # noqa: E402
    AGENT_NS,
    GRAPH_RAG_NS,
    TARIFF_NS,
    example_path,
    process_path,
)

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


def _dump_dom(browser: str, url: str, budget: int = 15000, size: str = "1400,900") -> str:
    """Virtual time fast-forwards timers, but not the work behind a fetch - an
    assessment takes a couple of real seconds, so a probe that runs one needs a
    budget that accounts for it."""
    completed = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--window-size={size}",
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


def test_the_overview_fits_the_diagram_it_shows(served) -> None:
    """The stakeholder page is a diagram plus a summary, and the diagram is the
    half someone came to see.

    It is fitted with getBBox, which measures nothing inside display:none - so
    fitting it before the page is on screen collapsed it to a 40px line while
    every activity was present in the markup. Assert on the height that got
    painted, not on whether the elements are there."""
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", async () => {
      const nl = String.fromCharCode(10, 10);
      const a = await (await fetch("/api/examples/ARCH")).json();
      const p = await (await fetch("/api/examples/PROC")).json();
      window.PairAI.Editor.setValue(a.ttl + nl + p.ttl);
      setTimeout(() => {
        document.querySelector("#btn-library-close")?.click();
        document.querySelector("#btn-overview").click();
        setTimeout(() => {
          const svg = document.querySelector("#overview-diagram svg");
          if (!svg) return log("svg=none");
          const box = svg.getBoundingClientRect();
          log("acts=" + svg.querySelectorAll(".pc-activity, .pc-task, [class*='pc-act']").length);
          log("height=" + Math.round(box.height));
          log("viewBox=" + (svg.getAttribute("viewBox") || "").split(" ").slice(2).join("x"));
        }, 1200);
      }, 3500);
    });
    """.replace("ARCH", example_path(TARIFF_NS).stem)
        .replace("PROC", process_path("energy_tariff_change").stem),
    budget=30000)

    assert "svg=none|" not in report, "the overview drew no diagram at all"
    height = int(re.search(r"height=(\d+)\|", report).group(1))
    assert height > 200, (
        f"the overview diagram collapsed to {height}px - it was fitted while hidden: {report}"
    )
    width = float(re.search(r"viewBox=([\d.]+)x", report).group(1))
    assert width > 500, f"the viewBox was computed from an empty box: {report}"


def test_an_activity_in_the_overview_opens_the_architecture_behind_it(served) -> None:
    """`pair:refinedBy` names the system and beam:has* say what it holds, so the
    overview can answer "what carries this out" without leaving the page.

    Only a refined activity opens anything - the rest have no architecture to
    show, and a click that sometimes does nothing is worse than no click."""
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", async () => {
      const nl = String.fromCharCode(10, 10);
      const a = await (await fetch("/api/examples/ARCH")).json();
      const p = await (await fetch("/api/examples/PROC")).json();
      window.PairAI.Editor.setValue(a.ttl + nl + p.ttl);
      setTimeout(() => {
        document.querySelector("#btn-library-close")?.click();
        document.querySelector("#btn-overview").click();
        setTimeout(() => {
          const all = document.querySelectorAll("#overview-diagram [data-node]").length;
          const open = document.querySelectorAll("#overview-diagram .ov-openable").length;
          log("openable=" + open);
          log("someNotOpenable=" + (all > open));
          document.querySelector("#overview-side .ov-row.clickable").click();
          setTimeout(() => {
            const box = document.querySelector("#overview-system");
            log("shown=" + !box.classList.contains("hidden"));
            log("named=" + !!(box.querySelector(".ov-sys-head h3") || {}).textContent);
            log("members=" + box.querySelectorAll(".ov-sys-item").length);
          }, 2500);
        }, 1500);
      }, 3500);
    });
    """.replace("ARCH", example_path(TARIFF_NS).stem)
        .replace("PROC", process_path("energy_tariff_change").stem),
    budget=40000)

    assert "openable=0|" not in report, f"no activity offered its architecture: {report}"
    assert "someNotOpenable=true|" in report, (
        f"every node was made clickable, including ones with no architecture: {report}"
    )
    assert "shown=true|" in report, f"clicking an AI activity revealed nothing: {report}"
    assert "named=true|" in report, f"the revealed architecture had no name: {report}"
    members = int(re.search(r"members=(\d+)\|", report).group(1))
    assert members > 0, f"the architecture was revealed but listed no elements: {report}"


def test_the_process_list_nests_pool_lane_activity_and_says_each_once(served) -> None:
    """The Process tab, read the way the canvas is drawn.

    It grouped by runs of the flow order, which interleaves the pools - so in
    the tariff scene "No lane" appeared five times and "LLM agent" three. And
    "No lane" was false: the customer's pool declares no lanes at all, so its
    activities are not missing one, they are the pool's.
    """
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", async () => {
      const nl = String.fromCharCode(10, 10);
      const a = await (await fetch("/api/examples/ARCH")).json();
      const p = await (await fetch("/api/examples/PROC")).json();
      window.PairAI.Editor.setValue(a.ttl + nl + p.ttl);
      setTimeout(() => {
        const list = document.querySelector("#process-list");
        const text = (sel) => [...list.querySelectorAll(sel)]
          .map((n) => n.firstChild ? n.firstChild.textContent : n.textContent);
        const pools = text(".proc-pool");
        const lanes = text(".proc-lane");
        log("pools=" + JSON.stringify(pools));
        log("lanes=" + JSON.stringify(lanes));
        log("noLane=" + /no lane/i.test(list.textContent));
        const names = [...list.querySelectorAll(".proc-row .proc-name")].map((n) => n.textContent);
        log("rows=" + names.length);
        log("unique=" + new Set(names).size);
        log("activities=" + window.PairAI.state.lastProcess.activities.length);
        // Walk the list: which heading does each row sit under?
        let pool = null, lane = null;
        const under = {};
        for (const node of list.children) {
          if (node.classList.contains("proc-pool")) { pool = node.firstChild.textContent; lane = null; }
          else if (node.classList.contains("proc-lane")) { lane = node.firstChild.textContent; }
          else if (node.classList.contains("proc-row")) {
            under[node.querySelector(".proc-name").textContent] = pool + " / " + (lane || "-");
          }
        }
        log("under=" + JSON.stringify(under));
      }, 4000);
    });
    """.replace("ARCH", example_path(TARIFF_NS).stem).replace("PROC", process_path("energy_tariff_change").stem))

    fields = dict(part.split("=", 1) for part in report.split("|") if "=" in part)
    pools = json.loads(fields["pools"])
    lanes = json.loads(fields["lanes"])
    under = json.loads(fields["under"])

    assert len(pools) == len(set(pools)), f"a pool heading repeated: {pools}"
    assert len(lanes) == len(set(lanes)), f"a lane heading repeated: {lanes}"
    assert fields["noLane"] == "false", (
        "the list says 'No lane' - a pool with no lanes has nothing missing"
    )
    assert fields["rows"] == fields["unique"] == fields["activities"], (
        "every activity is listed, and listed once"
    )
    # The customer's pool declares no lanes: its steps sit straight under it.
    assert under["Change tariff (service plan)"] == "Customer / -"
    # The utility's pool does: each step sits under its own lane.
    assert under["Authenticate the customer"] == "Wien Energie / Customer portal"
    assert under["Change the plan"] == "Wien Energie / Customer service agent"
    # And inside a group the steps follow the work, not the alphabet: flow runs
    # through gateways, and ordering over activities alone lost every such link.
    # The journey as the model states it: portal, chat, then the change itself.
    customer = [name for name, where in under.items() if where == "Customer / -"]
    assert customer == [
        "Log into the customer portal",
        "Start a chat session",
        "Change tariff (service plan)",
        "Fill out the form",
        "Receive the confirmation",
    ], f"the customer's steps are not in the order they happen: {customer}"


def test_the_overview_carries_the_risk_on_the_work_it_belongs_to(served) -> None:
    """The stakeholder page, filtered to this process and drawn on it.

    It listed findings per activity, and attribution is not partition: one
    capability carries three activities in this scene, so ten concerns read as
    thirty. The capability is named once, the activities it carries out sit
    under it, and the diagram is marked where the work is.
    """
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", async () => {
      const nl = String.fromCharCode(10, 10);
      const a = await (await fetch("/api/examples/ARCH")).json();
      const p = await (await fetch("/api/examples/PROC")).json();
      window.PairAI.Editor.setValue(a.ttl + nl + p.ttl);
      setTimeout(() => {
        document.querySelector("#btn-library-close")?.click();
        document.querySelector("#btn-assess").click();
        setTimeout(() => {
          document.querySelector("#btn-overview").click();
          setTimeout(() => {
            const view = window.PairAI.state.lastAssessment.riskView.byProcess;
            log("marks=" + document.querySelectorAll("#overview-diagram .ov-risk-mark").length);
            log("atRisk=" + document.querySelectorAll("#overview-diagram .ov-at-risk").length);
            log("cards=" + document.querySelectorAll(".ov-cap").length);
            log("clean=" + document.querySelectorAll(".ov-cap.clean").length);
            log("aiSystems=" + view.summary.aiSystems);
            log("withConcerns=" + view.summary.withConcerns);
            log("concerns=" + view.summary.concerns);
            log("inProcess=" + view.summary.inProcess);
            // Marks go on the activities the concerned capabilities carry out.
            const expected = view.systems
              .filter((s) => s.concerns.length)
              .reduce((n, s) => n + s.activities.length, 0);
            log("expected=" + expected);
            log("noStaleBadge=" + !document.querySelector("#overview-diagram .pc-risk"));
            log("summary=" + document.querySelector("#overview-side").textContent.includes("of "));
          }, 1500);
        }, 30000);
      }, 2500);
    });
    """.replace("ARCH", example_path(TARIFF_NS).stem).replace("PROC", process_path("energy_tariff_change").stem),
    budget=70000)

    fields = dict(part.split("=", 1) for part in report.split("|") if "=" in part)
    assert int(fields["marks"]) == int(fields["expected"]) > 0, (
        "the diagram is marked where the concerned capabilities do their work"
    )
    assert fields["atRisk"] == fields["marks"]
    assert fields["noStaleBadge"] == "true", (
        "the cloned per-activity finding badges are still there, showing a second number"
    )
    # Every capability is carded, including the ones that raise nothing.
    assert int(fields["cards"]) == int(fields["aiSystems"])
    assert int(fields["clean"]) == int(fields["aiSystems"]) - int(fields["withConcerns"]) > 0
    assert fields["inProcess"] == fields["concerns"], (
        "this scene's concerns all arise under the process, so none is set aside"
    )


def test_opening_an_ai_system_on_the_overview_draws_its_risk(served) -> None:
    """The panel under the diagram shows the risk on that system, not a parts list.

    It used to list the steps and resources inside the architecture, which says
    what is in there and nothing about what was found. With a run in hand it
    draws the same lens the risk level draws, scoped to the one system the
    activity names - the process around it on one side, what it holds on the
    other.
    """
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", async () => {
      const nl = String.fromCharCode(10, 10);
      const a = await (await fetch("/api/examples/ARCH")).json();
      const p = await (await fetch("/api/examples/PROC")).json();
      window.PairAI.Editor.setValue(a.ttl + nl + p.ttl);
      setTimeout(() => {
        document.querySelector("#btn-library-close")?.click();
        document.querySelector("#btn-assess").click();
        setTimeout(() => {
          document.querySelector("#btn-overview").click();
          setTimeout(() => document.querySelector("#overview-side .ov-row.clickable").click(), 800);
          setTimeout(() => {
            const panel = document.querySelector("#overview-system");
            log("open=" + !panel.classList.contains("hidden"));
            log("named=" + (panel.querySelector(".ov-sys-head h3") || {}).textContent);
            log("cards=" + panel.querySelectorAll(".rc-card").length);
            log("heads=" + [...panel.querySelectorAll(".rc-lens-head")].map((h) => h.textContent).join(" / "));
            log("parts=" + panel.querySelectorAll(".ov-sys-item").length);
            // The risk level draws into its own mount on every run, even while
            // hidden. It must still hold the notation, not this panel's lens.
            log("levelCards=" + document.querySelectorAll("#risk-canvas .rc-card").length);
            log("levelIsLens=" + (document.querySelectorAll("#risk-canvas .rc-lens-head").length > 0));
          }, 2600);
        }, 30000);
      }, 2500);
    });
    """.replace("ARCH", example_path(TARIFF_NS).stem).replace("PROC", process_path("energy_tariff_change").stem),
    budget=70000)

    fields = dict(part.split("=", 1) for part in report.split("|") if "=" in part)
    assert fields["open"] == "true", "opening an AI activity revealed nothing"
    assert fields["named"], "the panel did not name the system it opened"
    assert int(fields["cards"]) > 0, "the panel drew no risk diagram"
    assert "In the process" in fields["heads"] and "In the architecture" in fields["heads"], (
        f"the panel is not the lens: {fields['heads']!r}"
    )
    assert fields["parts"] == "0", "the parts list is still there instead of the risk"
    assert int(fields["levelCards"]) > 0 and fields["levelIsLens"] == "false", (
        "mounting the overview's canvas took over the risk level's - the renderer "
        "is a factory so the two mounts must not share state"
    )


BLACK_BOX = """
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix bb:   <http://example.org/black-box#> .

bb:Buyer a bpmn:participant ; bp:name "Buyer" ; bp:processRef bb:Ordering .
bb:Supplier a bpmn:participant ; bp:name "Supplier" .

bb:Ordering a bpmn:process ; bp:contains bb:Received , bb:Enrich , bb:Done .
bb:Received a bpmn:startEvent ; bp:name "Product data received" ;
    bp:eventDefinition bb:Trigger ; bp:outgoing bb:F1 .
bb:Trigger a bpmn:messageEventDefinition .
bb:Enrich a bpmn:task ; bp:name "Enrich the catalogue" ; bp:incoming bb:F1 ; bp:outgoing bb:F2 .
bb:Done a bpmn:endEvent ; bp:incoming bb:F2 .
bb:F1 a bpmn:sequenceFlow ; bp:sourceRef bb:Received ; bp:targetRef bb:Enrich .
bb:F2 a bpmn:sequenceFlow ; bp:sourceRef bb:Enrich ; bp:targetRef bb:Done .

bb:Sends a bpmn:messageFlow ; bp:name "product data" ;
    bp:sourceRef bb:Supplier ; bp:targetRef bb:Received .
"""


def test_a_message_flow_from_a_black_box_pool_is_drawn(served) -> None:
    """A participant with no process is BPMN's black box, so a message flow can
    only name the pool itself. The canvas drew the pool and dropped the arrow."""
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", () => setTimeout(() => {
      window.PairAI.Editor.setValue(GRAPH_TTL);
      setTimeout(() => {
        document.querySelector("#level-business").click();
        setTimeout(() => {
          const canvas = document.querySelector("#process-canvas");
          const flow = canvas.querySelector('[data-flow="http://example.org/black-box#Sends"]');
          log("drawn=" + (flow ? 1 : 0));
          if (!flow) return;
          const pool = [...canvas.querySelectorAll(".pc-pool")]
            .find((g) => g.querySelector(".pc-pool-label").textContent === "Supplier");
          const box = pool.querySelector(".pc-pool-box");
          const top = Number(box.getAttribute("y"));
          const bottom = top + Number(box.getAttribute("height"));
          const cy = Number(flow.querySelector(".pc-msg-start").getAttribute("cy"));
          log("onEdge=" + (Math.abs(cy - top) < 1 || Math.abs(cy - bottom) < 1 ? 1 : 0));
          const xs = flow.querySelector(".pc-flow.message").getAttribute("d")
            .match(/-?[\\d.]+/g).map(Number).filter((_, i) => i % 2 === 0);
          log("straight=" + (Math.max(...xs) - Math.min(...xs) < 1 ? 1 : 0));
          log("pools=" + canvas.querySelectorAll(".pc-pool").length);
          log("folds=" + canvas.querySelectorAll(".pc-pool-fold").length);
        }, 1500);
      }, 2500);
    }, 2000));
    """.replace("GRAPH_TTL", json.dumps(BLACK_BOX)), budget=20000)

    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert seen.get("drawn") == 1, f"the message flow from the black-box pool was not drawn: {report}"
    assert seen["onEdge"] == 1, f"the arrow does not start on the pool's edge: {report}"
    assert seen["straight"] == 1, f"the arrow does not run straight across to its target: {report}"
    assert seen["pools"] == 2 and seen["folds"] == 1, (
        f"the black-box pool offers to open, and there is nothing inside it: {report}"
    )


def test_the_term_picker_searches_and_shows_what_each_term_means(served) -> None:
    """97 terms on four shelves put 50 under one heading, in a native <select>
    that could neither search nor show a definition.

    Four facts, measured on the one model element in the bundled example: the
    picker opens, every option carries its definition, the shelf that goes on
    this element sorts first, and typing narrows the offer. The shelf orders
    rather than filters, because some match queries constrain no class at all.
    """
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    graph = example_path(GRAPH_RAG_NS).read_text(encoding="utf-8")
    probe = STATIC / "_picker_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  window.addEventListener("load", () => setTimeout(() => {
    window.PairAI.Editor.setValue(THE_TTL);
    setTimeout(() => {
      document.querySelectorAll(".drawer-tab").forEach((t) => {
        if (t.dataset.drawerTab === "annotate") t.click();
      });
      setTimeout(() => {
        const rows = [...document.querySelectorAll(".annotate-row:not(.annotate-row-head)")];
        log("rows=" + rows.length);
        const row = rows.find((r) =>
          (r.querySelector(".kind-badge") || {}).textContent === "model");
        log("foundModelRow=" + (row ? 1 : 0));
        if (!row) return;
        row.querySelector(".mp-add").click();
        setTimeout(() => {
          const pop = row.querySelector(".mp-pop");
          log("popOpen=" + (pop && !pop.classList.contains("hidden") ? 1 : 0));
          log("offered=" + pop.querySelectorAll(".mp-opt").length);
          log("withDef=" + pop.querySelectorAll(".mp-opt-def").length);
          const shelves = [...pop.querySelectorAll(".mp-shelf")].map((s) => s.textContent);
          log("shelves=" + shelves.length);
          log("modelShelfFirst=" + (/Statistical Model/.test(shelves[0] || "") ? 1 : 0));
          log("marksTheRest=" + shelves.filter((s) => /not this element/.test(s)).length);
          // the element already plays Foundation LLM and Generative Model, and a
          // selected term is not offered again
          log("alreadyOn=" + row.querySelectorAll(".an-role .mp-chip").length);
          const search = pop.querySelector(".mp-search");
          search.value = "artifact";
          search.dispatchEvent(new Event("input", { bubbles: true }));
          setTimeout(() => {
            const left = pop.querySelectorAll(".mp-opt");
            log("narrowed=" + left.length);
            if (!left.length) return;
            left[0].click();
            setTimeout(() => {
              log("chips=" + row.querySelectorAll(".an-role .mp-chip").length);
            }, 300);
          }, 300);
        }, 700);
      }, 2500);
    }, 2500);
  }, 2000));
  </script>
""".replace("THE_TTL", json.dumps(graph))
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_picker_probe.html", budget=26000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert "offered" in seen, f"the probe never reported: {report!r}"

    assert seen["foundModelRow"] == 1, f"no model row to annotate: {report}"
    assert seen["popOpen"] == 1, "the picker did not open"
    assert seen["offered"] > 0, "the picker offered nothing"
    assert seen["withDef"] == seen["offered"], "an option is offered without its definition"
    assert seen["shelves"] > 1, "the offer is not shelved at all"
    assert seen["modelShelfFirst"] == 1, (
        f"the terms that go on a model do not sort first: {report}"
    )
    assert seen["marksTheRest"] >= 1, (
        "the shelves that do not apply are offered without saying so"
    )
    assert 0 < seen["narrowed"] < seen["offered"], f"typing did not narrow the offer: {report}"
    assert seen["chips"] == seen["alreadyOn"] + 1, (
        f"picking a term did not record it: {report}"
    )


def test_the_library_shelves_the_annotation_vocabulary_by_what_it_goes_on(served) -> None:
    """The library counted 97 roles in its stats and offered no way to read one.
    The Terms tab shelves them by the BEAM class they are annotated on, because
    the role hierarchy's four top-level terms cannot: 50 sit under one."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    probe = STATIC / "_terms_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = r"""
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  window.addEventListener("load", () => setTimeout(() => {
    document.querySelector("#btn-library").click();
    setTimeout(() => {
      const tab = [...document.querySelectorAll(".library-tab")]
        .find((t) => t.dataset.libraryTab === "terms");
      log("hasTab=" + (tab ? 1 : 0));
      if (!tab) return;
      log("counted=" + parseInt(tab.textContent.replace(/\D/g, ""), 10));
      tab.click();
      setTimeout(() => {
        log("shelves=" + document.querySelectorAll("#library-detail h4").length);
        log("tiles=" + document.querySelectorAll(
          "#library-detail .lib-term:not(.lib-term-flat)").length);
        log("defs=" + document.querySelectorAll(
          "#library-detail .lib-term:not(.lib-term-flat) .lib-term-def").length);
        log("railGroups=" + document.querySelectorAll("#library-list .lib-group").length);
        log("categories=" + document.querySelectorAll("#library-detail .lib-term-flat").length);
        log("saysDerived=" + (/derived by the assessment/
          .test(document.querySelector("#library-detail").textContent) ? 1 : 0));
        // open one and read what the detail says about it
        document.querySelector("#library-detail .lib-term:not(.lib-term-flat)").click();
        setTimeout(() => {
          const text = document.querySelector("#library-detail").textContent;
          log("saysWhereItGoes=" + (/goes on /.test(text) ? 1 : 0));
          log("saysWhatNamesIt=" + (/Related motifs/.test(text) && /Related risk patterns/.test(text) && /names? it/.test(text) ? 1 : 0));
          log("saysWhereFrom=" + (/Where it comes from/.test(text) ? 1 : 0));
        }, 500);
      }, 700);
    }, 2500);
  }, 2000));
  </script>
"""
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_terms_probe.html", budget=22000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert "tiles" in seen, f"the probe never reported: {report!r}"

    assert seen["hasTab"] == 1, "the library has no Terms tab"
    roles = _library()["roles"]
    assert seen["counted"] == roles, f"the tab does not count the vocabulary off the graph: {report}"
    assert seen["tiles"] == roles, "not every term is shelved"
    assert seen["defs"] == roles, "a term is listed without its definition"
    assert seen["shelves"] > 4, (
        f"still shelved by the four top-level roles rather than by class: {report}"
    )
    assert seen["railGroups"] > 4, "the rail is not shelved either"
    assert seen["categories"] == 7, "the data categories are not listed with the roles"
    assert seen["saysDerived"] == 1, (
        "nothing says a data category can arrive without anyone annotating it (R8)"
    )
    assert seen["saysWhereItGoes"] == 1, "the detail does not say what the term goes on"
    assert seen["saysWhatNamesIt"] == 1, "the detail does not say what names it"
    # Hidden while the role mappings are reviewed; the API still serves it.
    assert seen["saysWhereFrom"] == 0, "the term's origin is shown while it is under review"


def test_the_library_rail_folds_by_group(served) -> None:
    """Motifs, terms and risk patterns as one long column give a reader no way
    to put a part of the library aside, so every tab folds by its shelf. Risks
    shelve by family once there were 33 of them, as motifs do, without groups
    inside, and open unfolded because they are the front door."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    probe = STATIC / "_fold_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  const rows = () => document.querySelectorAll("#library-list .lib-row").length;
  const tab = (name) => [...document.querySelectorAll(".library-tab")]
    .find((t) => t.dataset.libraryTab === name);
  window.addEventListener("load", () => setTimeout(() => {
    document.querySelector("#btn-library").click();
    setTimeout(() => {
      log("startFromRisk=" + (document.querySelector("#library-start-risk") ? 1 : 0));
      log("riskGroups=" + document.querySelectorAll("#library-list .lib-group").length);
      tab("motifs").click();
      setTimeout(() => {
        const heads = document.querySelectorAll("#library-list .lib-group");
        log("motifGroups=" + heads.length);
        log("atFirst=" + rows());
        log("shutAtFirst=" + document.querySelectorAll("#library-list .lib-group.shut").length);
        heads[0].click();
        setTimeout(() => {
          log("afterOpen=" + rows());
          log("shutMarked=" + document.querySelectorAll("#library-list .lib-group.shut").length);
          document.querySelectorAll("#library-list .lib-group")[0].click();
          setTimeout(() => { log("afterClose=" + rows()); }, 300);
        }, 300);
      }, 500);
    }, 2500);
  }, 2000));
  </script>
"""
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_fold_probe.html", budget=22000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert "motifGroups" in seen, f"the probe never reported: {report!r}"

    assert seen["startFromRisk"] == 0, "the risk starter is still offered"
    assert seen["riskGroups"] == 4, f"the risk rail has {seen['riskGroups']} family groups"
    assert seen["motifGroups"] == 4, f"the motif rail has {seen['motifGroups']} groups"
    assert seen["atFirst"] == 0, f"the rail opened unfolded, showing {seen['atFirst']} rows"
    assert seen["shutAtFirst"] == 4, "not every group starts folded"
    agentic = _library()["families"]["Agentic"]
    assert seen["afterOpen"] == agentic, f"opening Agentic showed {seen['afterOpen']} rows, not its {agentic}"
    assert seen["shutMarked"] == 3, "the opened group is still marked as folded"
    assert seen["afterClose"] == 0, "folding it again did not hide its rows"


def test_the_library_landing_is_drawn_rather_than_written(served) -> None:
    """A motif is a shape and a term belongs to one side of a bipartite graph.
    Both were paragraphs. The motif card draws the structure it matches, and a
    term carries the class colour and the box-or-oval of the notation it
    annotates - so neither has to be read to be told apart."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")

    probe = STATIC / "_landing_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = """
  <div id="probe-log"></div>
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  const tab = (name) => [...document.querySelectorAll(".library-tab")]
    .find((t) => t.dataset.libraryTab === name);
  window.addEventListener("load", () => setTimeout(() => {
    document.querySelector("#btn-library").click();
    setTimeout(() => {
      tab("motifs").click();
      setTimeout(() => {
        const tiles = [...document.querySelectorAll("#library-detail .lib-tile")];
        log("motifTiles=" + tiles.length);
        log("drawn=" + tiles.filter((t) => t.querySelector("svg.motif-preview")).length);
        log("withNodes=" + tiles.filter((t) =>
          t.querySelectorAll("svg.motif-preview .shape").length > 1).length);
        tab("terms").click();
        setTimeout(() => {
          const terms = [...document.querySelectorAll("#library-detail .lib-term:not(.lib-term-flat)")];
          const kinds = new Set();
          terms.forEach((t) => ["data", "process", "model", "symbol", "agent", "resource", "other"]
            .forEach((k) => { if (t.classList.contains(k)) kinds.add(k); }));
          log("terms=" + terms.length);
          log("kinded=" + terms.filter((t) =>
            ["data", "process", "model", "symbol", "agent", "resource", "other"]
              .some((k) => t.classList.contains(k))).length);
          log("distinctKinds=" + kinds.size);
          log("processShelves=" + document.querySelectorAll(
            "#library-detail .lib-shelf .lib-swatch.process").length);
          log("resourceShelves=" + document.querySelectorAll(
            "#library-detail .lib-shelf .lib-swatch.data, #library-detail .lib-shelf .lib-swatch.model, "
            + "#library-detail .lib-shelf .lib-swatch.resource").length);
          log("usage=" + document.querySelectorAll("#library-detail .lib-term-uses").length);
          log("quiet=" + document.querySelectorAll("#library-detail .lib-term.quiet").length);
        }, 600);
      }, 600);
    }, 2500);
  }, 2000));
  </script>
"""
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_landing_probe.html", budget=24000)
    finally:
        probe.unlink(missing_ok=True)

    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", report)}
    assert "motifTiles" in seen, f"the probe never reported: {report!r}"

    library = _library()
    assert seen["motifTiles"] == library["motifs"]
    assert seen["drawn"] == library["motifs"], f"only {seen['drawn']} motif cards draw their shape"
    assert seen["withNodes"] == library["motifs"], "a drawn motif has no elements in it"

    assert seen["terms"] == library["roles"]
    assert seen["kinded"] == library["roles"], "a term is listed without the class it goes on"
    assert seen["distinctKinds"] >= 3, (
        f"every term reads as one kind ({seen['distinctKinds']}), so the colour says nothing"
    )
    assert seen["processShelves"] >= 1, "no shelf is marked as the process side"
    assert seen["resourceShelves"] >= 3, "the resource shelves are not marked as such"
    assert seen["usage"] == library["roles"], "a term does not say how much of the library reads it"
    # exactly the terms no motif reaches. Those read only through the term they
    # refine are in full use, and dimming them would say otherwise.
    assert seen["quiet"] == library["quiet"], f"{seen['quiet']} terms are marked unread"


def _probe(served: int, name: str, script: str, budget: int = 22000,
           size: str = "1400,900") -> dict[str, int]:
    """Load the page with `script` appended, and read back its `key=n|` log."""
    browser = _browser()
    if not browser:
        pytest.skip("no Chromium-family browser to render with")
    probe = STATIC / f"_{name}_probe.html"
    source = (STATIC / "index.html").read_text(encoding="utf-8")
    driver = '<div id="probe-log"></div>\n' + script
    probe.write_text(source.replace("</body>", driver + "</body>"), encoding="utf-8")
    try:
        dom = _dump_dom(browser, f"http://127.0.0.1:{served}/static/_{name}_probe.html",
                        budget=budget, size=size)
    finally:
        probe.unlink(missing_ok=True)
    found = re.search(r'id="probe-log"[^>]*>(.*?)</div>', dom, re.S)
    report = found.group(1).strip() if found else ""
    seen = {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", report)}
    seen["_report"] = report  # type: ignore[assignment]
    return seen


# Opens the library on a tab and, optionally, one entry in it.
_OPEN = """
  <script>
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  const openOn = (tabName, entry, then) => {
    document.querySelector("#btn-library").click();
    setTimeout(() => {
      [...document.querySelectorAll(".library-tab")]
        .find((t) => t.dataset.libraryTab === tabName).click();
      setTimeout(() => {
        if (entry) {
          [...document.querySelectorAll("#library-detail .lib-tile, #library-detail .lib-term")]
            .find((n) => n.textContent.trim().startsWith(entry)).click();
        }
        setTimeout(then, 600);
      }, 500);
    }, 1500);
  };
  </script>
"""


def test_no_motif_is_drawn_with_a_step_feeding_a_step(served) -> None:
    """The drawing has the bipartite rule too. `kindOf` fell back to "process"
    for any class it did not name, so the one `beam:Resource` node in the library
    - External Dependency - was drawn as a step, and its `step beam:use resource`
    edge read as process to process. This reads every declaration through the
    preview's own mapping, as the library page does."""
    seen = _probe(served, "bipartite", """
  <script type="module">
  import { kindOf } from "./lib/motif_preview.js";
  const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
  fetch("/api/library").then((r) => r.json()).then((lib) => {
    let edges = 0, sameSide = 0, untyped = 0;
    lib.motifs.forEach((motif) => {
      const kind = new Map(motif.nodes.map((n) => [n.key, kindOf(n.cls)]));
      kind.forEach((k) => { if (k === "other") untyped += 1; });
      motif.edges.forEach(([from, , to]) => {
        edges += 1;
        if ((kind.get(from) === "process") === (kind.get(to) === "process")) sameSide += 1;
      });
    });
    log("motifs=" + lib.motifs.length);
    log("edges=" + edges);
    log("sameSide=" + sameSide);
    log("untyped=" + untyped);
  });
  </script>
""", budget=12000)
    assert "edges" in seen, f"the probe never reported: {seen['_report']!r}"
    assert seen["motifs"] == _library()["motifs"]
    assert seen["edges"] > 100, "the library's edges were not read"
    assert seen["sameSide"] == 0, (
        f"{seen['sameSide']} drawn edges join two steps or two resources"
    )
    assert seen["untyped"] == 0, "a declared class reaches the drawing with no kind"


_RISK_PAGE = _OPEN + """
  <script>
  window.addEventListener("load", () => setTimeout(() => openOn("risks", "Prompt injection", () => {
    const page = document.querySelector("#library-detail");
    const text = page.textContent;
    const heads = [...page.querySelectorAll(".lib-panel-head h3")];
    const mech = heads.find((h) => h.textContent === "Risk mechanism");
    log("mechanism=" + (mech ? 1 : 0));
    log("raisedWhen=" + (/raised when/.test(text) ? 1 : 0));
    log("conditionSection=" + (/Applicability conditions/i.test(text) ? 1 : 0));
    if (mech) {
      const r = mech.getBoundingClientRect();
      log("mechInView=" + (r.top >= 0 && r.bottom <= window.innerHeight ? 1 : 0));
    }
    log("headingPx=" + Math.round(Math.min(...heads.map((h) => parseFloat(getComputedStyle(h).fontSize)))));
    const back = page.querySelector(".lib-back");
    const pr = page.getBoundingClientRect();
    const br = back.getBoundingClientRect();
    log("backOnRight=" + (br.left > pr.left + pr.width / 2 ? 1 : 0));
    log("backHeight=" + Math.round(br.height));
    log("backSays=" + (back.textContent.trim() === "All risk patterns" ? 1 : 0));
    log("overflow=" + (page.scrollWidth - page.clientWidth));
    back.click();
    setTimeout(() => {
      log("backToLanding=" + (document.querySelector("#library-detail .lib-landing-title") ? 1 : 0));
    }, 300);
  }), 2000));
  </script>
"""


def test_a_risk_page_leads_with_its_mechanism(served) -> None:
    """Conditions are read inside the risk mechanism rather than as a section of
    their own, and the mechanism is in view without scrolling past every
    diagram - at the side when the page is wide, first when it is narrow."""
    for size in ("1400,900", "1000,900"):
        seen = _probe(served, "riskpage", _RISK_PAGE, size=size)
        assert "mechanism" in seen, f"the probe never reported at {size}: {seen['_report']!r}"
        assert seen["mechanism"] == 1, f"no Risk mechanism panel at {size}"
        assert seen["raisedWhen"] == 1, "the condition was dropped rather than merged in"
        assert seen["conditionSection"] == 0, "conditions still have a section of their own"
        assert seen["mechInView"] == 1, f"the mechanism is below the fold at {size}"
        assert seen["headingPx"] >= 15, f"panel headings render at {seen['headingPx']}px"
        assert seen["backOnRight"] == 1, "the way back is not on the right"
        assert seen["backHeight"] >= 28, f"the way back is {seen['backHeight']}px tall"
        assert seen["backSays"] == 1, "the way back does not say where it goes"
        assert seen["overflow"] <= 1, (
            f"the page is {seen['overflow']}px wider than its panel at {size}, "
            "which is what scrolled it sideways and cut off the first letter of every line"
        )
        assert seen["backToLanding"] == 1, "the way back did not return to the catalogue"


def test_a_motif_page_fits_its_panel_at_any_width(served) -> None:
    """The External Dependency page ran off the right edge in a narrow window."""
    script = _OPEN + """
  <script>
  window.addEventListener("load", () => setTimeout(() => openOn("motifs", "External Dependency", () => {
    const page = document.querySelector("#library-detail");
    log("overflow=" + (page.scrollWidth - page.clientWidth));
    log("legend=" + page.querySelectorAll(".lib-legend-item").length);
    log("resourceSwatch=" + page.querySelectorAll(".lib-legend .lib-swatch.resource").length);
    log("processSwatch=" + page.querySelectorAll(".lib-legend .lib-swatch.process").length);
    log("addInHero=" + [...page.querySelectorAll(".lib-hero .btn")]
      .filter((b) => b.textContent === "Add to canvas").length);
  }), 2000));
  </script>
"""
    for size in ("1400,900", "1000,900"):
        seen = _probe(served, "motifpage", script, size=size)
        assert "overflow" in seen, f"the probe never reported at {size}: {seen['_report']!r}"
        assert seen["overflow"] <= 1, f"the page is {seen['overflow']}px too wide at {size}"
        assert seen["legend"] == 2, "the legend does not name the two kinds drawn"
        assert seen["resourceSwatch"] == 1, "the dependency is not drawn as a resource"
        assert seen["processSwatch"] == 1, "the using step is not drawn as a step"
        assert seen["addInHero"] == 1, "the page's own action is not in its header"


def test_a_term_page_marks_where_the_term_sits(served) -> None:
    """Every structure that reads a term is drawn with the element the term would
    annotate marked, and one reached through a refined term is told apart."""
    seen = _probe(served, "termpage", _OPEN + """
  <script>
  window.addEventListener("load", () => setTimeout(() => openOn("terms", "Batch Dataset", () => {
    const uses = [...document.querySelectorAll("#library-detail .lib-use")];
    log("uses=" + uses.length);
    log("marked=" + uses.filter((u) => u.querySelector(".mp-hl")).length);
    log("inherited=" + uses.filter((u) => u.classList.contains("inherited")).length);
  }), 2000));
  </script>
""")
    assert "uses" in seen, f"the probe never reported: {seen['_report']!r}"
    assert seen["uses"] == 2, f"Batch Dataset is read by {seen['uses']} structures here, not 2"
    assert seen["marked"] == 2, "a structure is drawn without the term's place in it"
    assert seen["inherited"] == 1, "the structure reached by refinement is not told apart"


def test_each_landing_says_what_it_is_in_one_line(served) -> None:
    """The risk note ran to four lines inside an 80ch cap on a wide screen."""
    seen = _probe(served, "notes", _OPEN + """
  <script>
  const note = () => (document.querySelector("#library-detail .lib-note") || {}).textContent || "";
  window.addEventListener("load", () => setTimeout(() => openOn("risks", null, () => {
    log("risks=" + note().length);
    [...document.querySelectorAll(".library-tab")].find((t) => t.dataset.libraryTab === "motifs").click();
    setTimeout(() => {
      log("motifs=" + note().length);
      [...document.querySelectorAll(".library-tab")].find((t) => t.dataset.libraryTab === "terms").click();
      setTimeout(() => {
        log("terms=" + note().length);
        log("capped=" + (getComputedStyle(document.querySelector("#library-detail .lib-note")).maxWidth !== "none" ? 1 : 0));
      }, 400);
    }, 400);
  }), 2000));
  </script>
""")
    assert "terms" in seen, f"the probe never reported: {seen['_report']!r}"
    for tab in ("risks", "motifs", "terms"):
        assert 0 < seen[tab] <= 130, f"the {tab} note is {seen[tab]} characters"
    assert seen["capped"] == 0, "the note is still held to a narrow column"
