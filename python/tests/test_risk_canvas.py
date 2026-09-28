"""The risk level, drawn: the BEAM risk notation over the architecture flow.

A list of findings makes a reader carry the graph in their head. What is under
test here is that the diagram does not - every band the notation declares is
painted, a risk sits above the elements it concerns, and picking a box says
what stands behind it.

Driven through a real headless browser, like the other canvas suites: an SVG
that is present in the markup and collapsed to nothing on screen passes every
assertion that reads the DOM and none that reads what was painted.

What is *not* here: anything that needs a gesture on the diagram. Selecting a
box is a pointer press with a distance threshold, and a synthetic MouseEvent is
delivered to whatever element it names rather than to whatever the canvas would
actually hit - so those live in `test_canvas_interaction.py`, on real input.
"""

from __future__ import annotations

import pytest

from conftest import AGENT_NS, TARIFF_NS, example_path, process_path
# The browser harness lives with the canvas suite; imported rather than moved
# so there is one place that knows how to drive a real page.
from test_canvas_renders import _drive, served  # noqa: F401 - served is a fixture

pytestmark = pytest.mark.browser

ARCH = example_path(AGENT_NS).stem
PROC = process_path("it_service_desk").stem


def _fields(report: str) -> dict:
    return dict(part.split("=", 1) for part in report.split("|") if "=" in part)


def _scene(body: str, *, budget: int = 45000) -> str:
    """Load the agentic scene, assess it, open the risk level, then run `body`."""
    return (
        """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    const pickRisk = () => [...document.querySelectorAll(".rc-card")]
      .find((c) => c.querySelector(".rc-chip").textContent === "Risk"
        && /^Candidate/.test(c.querySelector(".rc-title").textContent));
    const click = (node) => node.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    window.addEventListener("load", async () => {
      const nl = String.fromCharCode(10, 10);
      const a = await (await fetch("/api/examples/__ARCH__")).json();
      const p = await (await fetch("/api/examples/__PROC__")).json();
      window.PairAI.Editor.setValue(a.ttl + nl + p.ttl);
      setTimeout(() => {
        document.querySelector("#btn-library-close")?.click();
        document.querySelector("#btn-assess").click();
        setTimeout(() => {
          document.querySelector("#level-risk").click();
          setTimeout(() => { __BODY__ }, 1800);
        }, 9000);
      }, 2500);
    });
    """.replace("__ARCH__", ARCH).replace("__PROC__", PROC).replace("__BODY__", body)
    )


def _many_system_scene(body: str) -> str:
    """The tariff scene: four architectures under one process, which is what
    makes filtering worth having."""
    return _scene(body).replace(
        "/api/examples/" + ARCH, "/api/examples/" + example_path(TARIFF_NS).stem,
    ).replace(
        "/api/examples/" + PROC, "/api/examples/" + process_path("energy_tariff_change").stem,
    )


def test_the_notation_is_drawn_rather_than_listed(served) -> None:
    """And drawn coarse.

    The risk is the anchor. Opening on every element of every architecture made
    this a wiring diagram with risks stuck to it, so a system arrives as one box
    with a handle, and what a risk inside it attaches to is drawn to the system
    until somebody asks for the parts.
    """
    report = _drive(served, _scene("""
      const bands = {};
      document.querySelectorAll(".rc-chip").forEach((t) => {
        bands[t.textContent] = (bands[t.textContent] || 0) + 1;
      });
      log("bands=" + Object.keys(bands).sort().join(","));
      log("risks=" + (bands.Risk || 0));
      log("parts=" + document.querySelectorAll(".rc-flow").length);
      log("handles=" + document.querySelectorAll(".rc-unfold").length);
      log("links=" + document.querySelectorAll(".rc-link").length);
      log("unlabelled=" + (document.querySelectorAll(".rc-link:not(.rc-link-hit)").length
        - document.querySelectorAll(".rc-edge-label").length));
      log("concerns=" + window.PairAI.state.lastAssessment.riskView.summary.concerns);
      const risk = pickRisk();
      const system = [...document.querySelectorAll(".rc-card")]
        .find((c) => c.querySelector(".rc-chip").textContent === "System");
      /* On screen, not getBBox: a <g> reports its bbox in its own coordinates,
         so every card claims the same y whatever the band put it at. */
      log("above=" + (risk.getBoundingClientRect().top < system.getBoundingClientRect().top));
      log("painted=" + Math.round(document.querySelector("#rc-root").getBBox().width));
    """))

    fields = _fields(report)
    assert set(fields["bands"].split(",")) == {
        "Activity", "Consequence", "Context", "Risk", "Risk Control", "Risk Source", "System",
    }, (
        "every band the notation declares and this run reaches must be painted - "
        f"Impact only where a person stated one, and this scene states none: {fields['bands']}"
    )
    assert int(fields["parts"]) == 0, (
        "an architecture arrives folded: its parts are asked for, not opened on"
    )
    assert int(fields["handles"]) > 0, "and every system says it has parts to unfold"
    assert int(fields["links"]) > 0, "the chain between the layers is drawn"
    assert int(fields["painted"]) > 500, "a diagram collapsed to nothing is not a diagram"
    assert fields["above"] == "true", "a risk is drawn above what it concerns"
    # More risk boxes than concerns: what people stated is on the same diagram.
    assert int(fields["risks"]) > int(fields["concerns"])


def test_unfolding_a_system_puts_its_parts_inside_its_frame(served) -> None:
    """Containment is the frame, not a line per part.

    A line from the system to each of its parts is the densest possible way to
    say what an enclosure says for free, and at six parts it was most of the
    diagram. So the test of unfolding is not that lines appeared - it is that
    the parts landed inside the frame of the architecture that holds them.
    """
    report = _drive(served, _scene("""
      const handle = document.querySelector(".rc-unfold");
      log("before=" + document.querySelectorAll(".rc-flow").length);
      log("saysHowMany=" + /\\d+ parts/.test(handle.textContent));
      log("frames=" + document.querySelectorAll(".rc-frame").length);
      handle.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      setTimeout(() => {
        const parts = [...document.querySelectorAll(".rc-flow")];
        log("after=" + parts.length);
        log("contains=" + [...document.querySelectorAll(".rc-edge-label")]
          .filter((t) => t.textContent === "contains").length);
        /* Inside some frame, measured on screen. A part drawn outside every
           frame is a part whose architecture the reader cannot tell. */
        const frames = [...document.querySelectorAll(".rc-frame-box")]
          .map((f) => f.getBoundingClientRect());
        const inside = parts.filter((part) => {
          const r = part.getBoundingClientRect();
          return frames.some((f) => r.left >= f.left - 1 && r.right <= f.right + 1
            && r.top >= f.top - 1 && r.bottom <= f.bottom + 1);
        });
        log("framed=" + inside.length);
        document.querySelector(".rc-unfold").dispatchEvent(
          new PointerEvent("pointerdown", { bubbles: true }));
        setTimeout(() => log("folded=" + document.querySelectorAll(".rc-flow").length), 700);
      }, 900);
    """))

    fields = _fields(report)
    assert fields["saysHowMany"] == "true", "the handle has to say how much it would open"
    assert int(fields["before"]) == 0
    assert int(fields["frames"]) > 0, "each architecture is framed, folded or not"
    assert int(fields["after"]) > 0, "unfolding a system drew none of its parts"
    assert int(fields["contains"]) == 0, (
        "containment is the frame - a line per part is what made this unreadable"
    )
    assert fields["framed"] == fields["after"], (
        f"a part was drawn outside every frame: {fields['framed']} of {fields['after']}"
    )
    assert int(fields["folded"]) == 0, "and it folds back up"


def test_each_architecture_is_a_group_and_its_risks_sit_in_it(served) -> None:
    """The grouping is what makes the notation survive a real system.

    Bands used to be one row across the whole diagram, so a risk in one
    architecture sat beside a risk in another and every line between a risk and
    its own elements crossed everything in between. Each architecture now gets
    a column and a frame, and a concern is drawn inside the frame of the system
    it names - which is the claim the layout has to keep.
    """
    report = _drive(served, _many_system_scene("""
      const frames = [...document.querySelectorAll(".rc-frame")].map((f) => ({
        label: f.querySelector(".rc-frame-label").textContent,
        r: f.querySelector(".rc-frame-box").getBoundingClientRect(),
      }));
      log("frames=" + frames.length);
      log("architectures=" + (document.querySelectorAll(".layer-focus option").length - 1));
      /* Every risk box, against the frame of the architecture it says it
         stands in. Read off the run, so this is the payload's own claim. */
      const d = window.PairAI.state.lastAssessment.riskView.diagram;
      const named = new Map(d.nodes.filter((n) => n.isSystem).map((n) => [n.id, n.title]));
      let checked = 0, home = 0;
      for (const card of document.querySelectorAll("#risk-canvas .rc-card")) {
        if (card.querySelector(".rc-chip").textContent !== "Risk") continue;
        const node = d.nodes.find((n) => n.id === card.getAttribute("data-node"));
        if (!node || (node.systems || []).length !== 1) continue;
        checked += 1;
        const want = named.get(node.systems[0]);
        const r = card.getBoundingClientRect();
        const frame = frames.find((f) => f.label === want);
        if (frame && r.left >= frame.r.left - 1 && r.right <= frame.r.right + 1
            && r.top >= frame.r.top - 1 && r.bottom <= frame.r.bottom + 1) home += 1;
      }
      log("checked=" + checked);
      log("home=" + home);
      log("flowEdges=" + document.querySelectorAll(".rc-flow-edge").length);
    """))

    fields = _fields(report)
    assert int(fields["frames"]) == int(fields["architectures"]), (
        "one frame per architecture on the scene"
    )
    assert int(fields["checked"]) > 0, "the scene raises concerns that name one architecture"
    assert fields["home"] == fields["checked"], (
        f"a concern was drawn outside the architecture it names: {fields}"
    )
    assert int(fields["flowEdges"]) == 0, (
        "the architecture's own use/produce edges belong to the architecture "
        "level - over the risk layer they are a second unlabelled set of lines"
    )


def test_the_notation_can_be_read_one_layer_and_one_architecture_at_a_time(served) -> None:
    """Every risk in every architecture on one page is unreadable.

    Two controls answer that: a layer can be turned off, and one architecture
    can be read at a time. Neither changes the run - both choose what is drawn,
    which is the same rule the scope obeys.
    """
    report = _drive(served, _many_system_scene("""
      const chips = () => {
        const seen = {};
        document.querySelectorAll("#risk-canvas .rc-chip").forEach((t) => {
          seen[t.textContent] = (seen[t.textContent] || 0) + 1;
        });
        return seen;
      };
      const toggle = (name) => [...document.querySelectorAll(".layer-toggle")]
        .find((b) => b.textContent === name).click();
      const focusOn = (index) => {
        const picker = document.querySelector(".layer-focus");
        picker.selectedIndex = index;
        picker.dispatchEvent(new Event("change", { bubbles: true }));
        return picker.selectedOptions[0].textContent;
      };
      log("toggles=" + document.querySelectorAll(".layer-toggle").length);
      log("architectures=" + (document.querySelectorAll(".layer-focus option").length - 1));
      log("risksAll=" + (chips().Risk || 0));
      log("activities=" + (chips().Activity || 0));
      log("systemsAll=" + (chips().System || 0));
      toggle("Business");
      setTimeout(() => {
        log("activitiesOff=" + (chips().Activity || 0));
        toggle("Business");
        toggle("Architecture");
        setTimeout(() => {
          log("systemsOff=" + (chips().System || 0));
          log("risksStay=" + (chips().Risk || 0));
          toggle("Architecture");
          const last = document.querySelector(".layer-focus").options.length - 1;
          log("focused=" + focusOn(last));
          setTimeout(() => {
            log("risksFocused=" + (chips().Risk || 0));
            log("activitiesFocused=" + (chips().Activity || 0));
            log("findings=" + window.PairAI.state.lastAssessment.summary.riskFindingCount);
          }, 700);
        }, 700);
      }, 700);
    """))

    fields = _fields(report)
    assert int(fields["toggles"]) == 3, "one toggle per layer"
    assert int(fields["architectures"]) > 1, "the scene runs several architectures"
    assert int(fields["risksAll"]) > 0 and int(fields["systemsAll"]) > 1

    assert int(fields["activities"]) > 0, "the business layer draws the work each system does"
    assert int(fields["activitiesOff"]) == 0, "turning the business layer off takes it away"
    assert int(fields["systemsOff"]) == 0, (
        "turning the architecture off takes its systems with it"
    )
    assert int(fields["risksStay"]) == int(fields["risksAll"]), (
        "hiding one layer must not remove another"
    )
    assert int(fields["risksFocused"]) < int(fields["risksAll"]), (
        f"reading one architecture did not narrow the notation: {fields}"
    )
    assert int(fields["activitiesFocused"]) < int(fields["activities"]), (
        "and the work shown narrows with it"
    )
    # Choosing what is drawn is not choosing what is detected.
    assert int(fields["findings"]) > 0


def test_an_assessment_can_be_written_before_anything_is_run(served) -> None:
    """The risk level used to be empty until a query had matched something.

    An assessor who already knows a risk should not have to run the library to
    record it - the architecture is on screen, the palette is on it, and every
    box a drop would be accepted on says so before the drag starts.

    It lands on the system, because that is what the risk level opens on. A
    beam:System is a beam:Element, so this is the relation the vocabulary
    already has rather than a coarser one invented for the first pass.
    """
    report = _drive(served, """
    const log = (m) => { document.getElementById("probe-log").textContent += m + "|"; };
    window.addEventListener("load", async () => {
      const a = await (await fetch("/api/examples/__ARCH__")).json();
      window.PairAI.Editor.setValue(a.ttl);
      setTimeout(() => {
        document.querySelector("#btn-library-close")?.click();
        document.querySelector("#level-risk").click();   // no assessment at all
        setTimeout(() => {
          log("assessed=" + !!window.PairAI.state.lastAssessment);
          log("palette=" + document.querySelectorAll("#risk-palette .pp-item").length);
          log("systems=" + [...document.querySelectorAll("#risk-canvas .rc-chip")]
            .filter((t) => t.textContent === "System").length);
          log("saysWhere=" + document.querySelectorAll("#risk-palette .pal-where").length);
          const item = document.querySelector('#risk-palette .pp-item[data-kind="risk"]');
          const r = item.getBoundingClientRect();
          item.dispatchEvent(new PointerEvent("pointerdown", {
            bubbles: true, clientX: r.left + 5, clientY: r.top + 5 }));
          setTimeout(() => {
            log("droppable=" + document.querySelectorAll(".rc-droppable").length);
            log("ghost=" + document.querySelectorAll(".risk-ghost").length);
            // Drop it on an element for real, and see what that costs. The box
            // has to be one a press there would actually reach: the notation is
            // wider than its pane, so the first one can be clipped out of it.
            window.prompt = () => "Written with no run";
            const pane = document.querySelector("#risk-canvas").getBoundingClientRect();
            let x = 0, y = 0;
            for (const box of document.querySelectorAll("#risk-canvas .rc-card")) {
              if (box.querySelector(".rc-chip").textContent !== "System") continue;
              // The box, not the group: the group's rect includes the type chip
              // painted above it, so its centre can fall in the gap between.
              const r = box.querySelector("rect.rc-box").getBoundingClientRect();
              const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
              if (cx < pane.left || cx > pane.right || cy < pane.top || cy > pane.bottom) continue;
              if (document.elementFromPoint(cx, cy)?.closest(".rc-card") !== box) continue;
              x = cx; y = cy;
              break;
            }
            log("dropOn=" + (x ? "found" : "none"));
            window.dispatchEvent(new PointerEvent("pointermove",
              { bubbles: true, clientX: x, clientY: y }));
            window.dispatchEvent(new PointerEvent("pointerup",
              { bubbles: true, clientX: x, clientY: y }));
            /* Polled, not waited on: virtual time fast-forwards the timer but
               not the request behind it, so a fixed pause proves nothing. */
            let tries = 0;
            const settle = () => {
              const mine = [...document.querySelectorAll("#risk-canvas .rc-card")]
                .find((c) => /Written with no run/.test(c.textContent));
              if (!mine && tries++ < 60) { setTimeout(settle, 250); return; }
              log("cleared=" + document.querySelectorAll(".rc-droppable,.risk-ghost").length);
              log("ranAssessment=" + !!window.PairAI.state.lastAssessment);
              log("inGraph=" + window.PairAI.Editor.getValue().includes("Written with no run"));
              log("drawn=" + !!mine);
              log("mark=" + (mine ? (mine.querySelector(".rc-mark") || {}).textContent : "-"));
            };
            setTimeout(settle, 600);
          }, 400);
        }, 4000);
      }, 3000);
    });
    """.replace("__ARCH__", ARCH))

    fields = _fields(report)
    assert fields["assessed"] == "false", "this is the state before any run"
    assert int(fields["palette"]) == 4, "a risk, a source, a consequence and an impact"
    assert int(fields["systems"]) > 0, "the architecture has to be there to drop onto"
    assert int(fields["saysWhere"]) == 4, "each shape says what it may be dropped on"
    assert int(fields["droppable"]) > 0, (
        "starting a drag has to show where it would be accepted - 'drag this "
        "somewhere' is not an instruction"
    )
    assert int(fields["ghost"]) == 1
    assert int(fields["cleared"]) == 0, "releasing left the drag state on screen"

    # Writing one down must not start a run. An assessment is expensive and the
    # decision to make one is the reader's.
    assert fields["dropOn"] == "found", "no system was reachable to drop onto"
    assert fields["inGraph"] == "true", "the drop wrote nothing into the graph"
    assert fields["ranAssessment"] == "false", (
        "recording a risk by hand started an assessment nobody asked for"
    )
    assert fields["drawn"] == "true", "and it has to appear without one"
    assert fields["mark"] == "by hand", (
        f"a box has to say whose claim it is, got {fields['mark']!r}"
    )


def test_a_stated_risk_and_a_derived_one_are_told_apart(served) -> None:
    """A person's claim and the library's are different kinds of statement, and
    the notation has to say which is which — that is what makes the diagram a
    reconciliation rather than a pile."""
    report = _drive(served, _scene("""
      const borders = [...document.querySelectorAll(".rc-card")].map((c) =>
        c.querySelector("rect.rc-box").getAttribute("stroke-dasharray"));
      log("stated=" + borders.filter((b) => b === "none").length);
      log("derived=" + borders.filter((b) => b && b !== "none").length);
    """))

    fields = _fields(report)
    assert int(fields["stated"]) >= 4, "the four risks the scene states are drawn as stated"
    assert int(fields["derived"]) >= 1, "and what the run produced is drawn as derived"


def test_storming_takes_the_derived_boxes_off_the_diagram(served) -> None:
    """Risk storming identifies risks in silence first. Offered, not enforced —
    but a reader who has seen the library's answers will not add one it missed,
    so the tool has to be able to stop showing them. What people drew stays:
    that, and the architecture, is what they are storming over.

    The control lives in the toolbar beside the layer toggles; the rail carries
    only the detail of whatever is picked.
    """
    report = _drive(served, _scene("""
      const count = () => document.querySelectorAll(".rc-card").length;
      const stated = () => [...document.querySelectorAll(".rc-card")]
        .filter((c) => c.querySelector("rect.rc-box").getAttribute("stroke-dasharray") === "none").length;
      log("inToolbar=" + !!document.querySelector("#risk-tools .storm-toggle"));
      log("before=" + count());
      log("statedBefore=" + stated());
      document.querySelector(".storm-toggle").click();
      setTimeout(() => {
        log("during=" + count());
        log("statedDuring=" + stated());
        log("archStays=" + ([...document.querySelectorAll(".rc-chip")]
          .filter((t) => t.textContent === "System").length > 0));
        log("canStillWrite=" + !!document.querySelector('#risk-palette .pp-item[data-kind="risk"]'));
        document.querySelector(".storm-toggle").click();
        setTimeout(() => log("after=" + count()), 700);
      }, 800);
    """))

    fields = _fields(report)
    assert fields["inToolbar"] == "true", "the offer has to be somewhere a reader can take it"
    assert int(fields["before"]) > int(fields["during"]), "storming takes the run's answers off"
    assert fields["statedDuring"] == fields["statedBefore"], "and leaves what people drew"
    assert int(fields["during"]) == int(fields["statedDuring"]), "only stated boxes remain"
    assert fields["archStays"] == "true", "the architecture is what they are storming over"
    assert fields["canStillWrite"] == "true", "and a risk can still be written down"
    assert fields["after"] == fields["before"], "and it gives them back"



