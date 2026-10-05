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
            // A prompt would be the old way; if one is reached the test says so.
            window.prompt = () => { window.__prompted = true; return "a prompt"; };
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
            /* The box is drawn by the drop and named afterwards, on the box:
               its editor offers the library first and the person's own words
               always. */
            const named = () => {
              const field = document.querySelector("#risk-side input");
              if (!field) { setTimeout(named, 200); return; }
              log("askedFirst=" + !!document.querySelector("#risk-side select"));
              log("boxFirst=" + document.querySelectorAll("#risk-canvas .rc-card").length);
              field.value = "Written with no run";
              [...document.querySelectorAll("#risk-side button")]
                .find((b) => b.textContent === "Apply").click();
              setTimeout(settle, 900);
            };
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
              log("prompted=" + !!window.__prompted);
            };
            setTimeout(named, 600);
          }, 400);
        }, 4000);
      }, 3000);
    });
    """.replace("__ARCH__", ARCH))

    fields = _fields(report)
    assert fields["assessed"] == "false", "this is the state before any run"
    assert int(fields["palette"]) == 5, (
        "a risk, a source, a consequence, an impact and a control"
    )
    assert int(fields["systems"]) > 0, "the architecture has to be there to drop onto"
    assert int(fields["saysWhere"]) == 5, "each shape says what it may be dropped on"
    assert int(fields["droppable"]) > 0, (
        "starting a drag has to show where it would be accepted - 'drag this "
        "somewhere' is not an instruction"
    )
    assert int(fields["ghost"]) == 1
    assert int(fields["cleared"]) == 0, "releasing left the drag state on screen"

    # Writing one down must not start a run. An assessment is expensive and the
    # decision to make one is the reader's.
    assert fields["dropOn"] == "found", "no system was reachable to drop onto"
    assert fields["askedFirst"] == "true", (
        "the box's own editor has to offer the library: whether this is a risk "
        "the library already knows is a different question from what to call it"
    )
    assert int(fields["boxFirst"]) > 0, (
        "the drop has to put the box on the diagram before anything is named - "
        "asked first, nothing was drawn while the question was being answered "
        "and the drop looked like it had done nothing"
    )
    assert fields["prompted"] == "false", "a browser prompt is not the form"
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




def test_a_risk_can_be_carried_by_an_activity_as_well_as_an_element(served) -> None:
    """A risk is as often carried by a step of the process as by a part of the
    architecture. The two layers are joined by pair:refinedBy rather than one
    standing in for the other, and beamr:hasRisk ranges over the element that
    carries the risk - so the activity band has to accept a drop like any other.
    """
    report = _drive(served, _scene("""
      const item = document.querySelector('#risk-palette .pp-item[data-kind="risk"]');
      const r = item.getBoundingClientRect();
      item.dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true, clientX: r.left + 5, clientY: r.top + 5 }));
      setTimeout(() => {
        // An activity card, and one a press would really reach.
        const pane = document.querySelector("#risk-canvas").getBoundingClientRect();
        let x = 0, y = 0, name = "";
        for (const box of document.querySelectorAll("#risk-canvas .rc-card.rc-droppable, #risk-canvas .rc-droppable")) {
          const chip = box.querySelector(".rc-chip");
          if (!chip || chip.textContent !== "Activity") continue;
          const rect = box.querySelector("rect.rc-box");
          if (!rect) continue;
          const b = rect.getBoundingClientRect();
          const cx = Math.round(b.left + b.width / 2), cy = Math.round(b.top + b.height / 2);
          if (cx < pane.left || cx > pane.right || cy < pane.top || cy > pane.bottom) continue;
          if (document.elementFromPoint(cx, cy)?.closest("[data-node]") !== box) continue;
          x = cx; y = cy; name = box.querySelector(".rc-title").textContent; break;
        }
        log("activityDroppable=" + (x > 0));
        log("onto=" + name);
        window.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: x, clientY: y }));
        window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: x, clientY: y }));
        setTimeout(() => {
          const ttl = window.PairAI.Editor.getValue();
          log("wroteRisk=" + (ttl.indexOf("beamr:Risk") >= 0 || ttl.indexOf("risk#Risk") >= 0));
          log("carried=" + /hasRisk/.test(ttl));
          log("drawn=" + [...document.querySelectorAll("#risk-canvas .rc-chip")]
            .filter((t) => t.textContent === "Risk").length);
        }, 2600);
      }, 700);
    """))

    fields = _fields(report)
    assert fields["activityDroppable"] == "true", (
        "an activity card never offered itself as a drop target, so a risk on a "
        "business step could not be written at all"
    )
    assert fields["onto"], "the probe could not name the activity it dropped on"
    assert fields["wroteRisk"] == "true", "the drop wrote no beamr:Risk"
    assert fields["carried"] == "true", "nothing carries it: no beamr:hasRisk was written"
    assert int(fields["drawn"]) >= 1, "the risk it wrote is not drawn"


def test_a_line_into_a_folded_system_says_which_parts_it_stands_for(served) -> None:
    """Attachments to parts of a folded system all land on its band. Drawing one
    line per attachment would stack them on the same spot, and deduplicating
    them reports one attachment where the person made several - so the line
    names what it stands for instead. Without that, picking a second element
    looks like it did nothing at all.
    """
    report = _drive(served, _scene("""
      const sysId = (window.PairAI.state.lastGraph.systems[0] || {}).id;
      const members = ((window.PairAI.state.lastGraph.systems[0] || {}).members || []).slice(0, 2);
      log("twoMembers=" + (members.length === 2));
      const post = (op, extra) => fetch("/api/scope-edit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ttl: window.PairAI.Editor.getValue(), op, ...extra }),
      }).then((r) => r.json());
      post("state-concept", { kind: "risk", label: "Carried by two parts", attachTo: members })
        .then((made) => {
          window.PairAI.Editor.setValue(made.ttl);
          setTimeout(() => {
            const labels = [...document.querySelectorAll("#risk-canvas .rc-edge-label")]
              .map((t) => t.textContent);
            log("names=" + labels.filter((t) => t.includes(",")).length);
            log("anyLabel=" + labels.length);
          }, 2600);
        });
    """))

    fields = _fields(report)
    assert fields["twoMembers"] == "true", "this test needs a system with two parts"
    assert int(fields["anyLabel"]) >= 1, (
        "the attachment to a folded system drew no labelled line, so the person "
        "cannot tell what the line stands for"
    )
    assert int(fields["names"]) >= 1, (
        "a line standing for two attachments does not name them, so the second "
        "attachment is invisible"
    )


def test_unfolding_a_system_does_not_fill_the_diagram_with_lines(served) -> None:
    """Drawn one per evidence element, the attachment lines were three quarters
    of the ink on the diagram and all of it said "where", not "what": a concern
    cites three to eight elements, so nine concerns drew seventy-four lines.

    They merge into one line per system, which names what it stands for.
    Deduplicating instead would report one attachment where the assessment found
    eight, which is the error the folded case already had to avoid.
    """
    report = _drive(served, _scene("""
      const lines = () => document.querySelectorAll("#risk-canvas .rc-link.attaches").length;
      log("folded=" + lines());
      // The handle listens for pointerdown, not click.
      const unfold = [...document.querySelectorAll("#risk-canvas .rc-unfold[data-unfold]")];
      log("unfoldable=" + unfold.length);
      for (const handle of unfold) {
        handle.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      }
      setTimeout(() => {
        log("unfolded=" + lines());
        log("parts=" + document.querySelectorAll("#risk-canvas .rc-flow").length);
      }, 900);
    """))

    fields = _fields(report)
    assert int(fields["unfoldable"]) >= 1, "no system on this scene can be opened"
    assert int(fields["parts"]) >= 1, "opening a system drew none of its parts"
    assert int(fields["unfolded"]) <= int(fields["folded"]) + 2, (
        "opening a system multiplied the attachment lines: "
        f"{fields['folded']} -> {fields['unfolded']}"
    )


def test_the_detail_opens_folded_and_the_reader_chooses_what_to_read(served) -> None:
    """The panel carried a paragraph, nine conditions and a chain of elements all
    open at once, and the parts worth acting on sat below all of it.

    What a concern may lead to, and what can be done about it, stay in view; the
    long prose folds behind its own key, with a hint of how much is there so a
    reader can tell whether to open it.
    """
    report = _drive(served, _scene("""
      // The canvas picks a box on pointerdown then pointerup, never on click.
      // A hand-written risk, because its panel is where the three tiers meet:
      // Apply is a primary button, Connect a plain one, remove this a chip.
      fetch("/api/scope-edit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ttl: window.PairAI.Editor.getValue(), op: "state-concept",
          kind: "risk", label: "Sizing probe",
        }),
      }).then((r) => r.json()).then((made) => {
        window.PairAI.Editor.setValue(made.ttl);
        setTimeout(() => {
          const card = [...document.querySelectorAll("#risk-canvas .rc-card")]
            .find((c) => c.querySelector(".rc-title")?.textContent === "Sizing probe");
          log("probeDrawn=" + !!card);
          card.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
          window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
          setTimeout(() => {
        const folds = [...document.querySelectorAll(".rail-detail .concern-fold")];
        log("folds=" + folds.length);
        log("openAtFirst=" + folds.filter((f) => f.open).length);
        log("keys=" + folds.map((f) => f.querySelector(".concern-key")?.textContent).join("/"));
        // What to do about it is not hidden behind a fold.
        log("leadsToVisible=" + [...document.querySelectorAll(".rail-detail .concern-row")]
          .some((r) => r.querySelector(".concern-key")?.textContent === "may lead to"));
        const why = folds.find((f) => f.querySelector(".concern-key")?.textContent === "why");
        // checkVisibility reports what is rendered; a closed <details> keeps its
        // children in the DOM, so their presence proves nothing.
        const shown = (fold) => {
          const list = fold.querySelector(".why-list");
          return list.checkVisibility ? list.checkVisibility() : list.offsetParent !== null;
        };
        log("whyHidden=" + (why ? !shown(why) : "none"));
        if (why) why.querySelector("summary").click();
        setTimeout(() => {
          log("whyShownAfterClick=" + (why ? shown(why) : "none"));
        }, 300);
      }, 900);
    """))

    fields = _fields(report)
    assert int(fields["folds"]) >= 2, f"nothing folds in the detail: {fields}"
    assert fields["openAtFirst"] == "0", "a fold is open before anybody asked for it"
    assert fields["leadsToVisible"] == "true", (
        "what the concern may lead to was folded away; that is the part worth seeing"
    )
    assert fields["whyHidden"] == "true", "the conditions are on screen before being asked for"
    assert fields["whyShownAfterClick"] == "true", "opening the fold showed nothing"


def test_the_control_tiers_render_at_one_size(served) -> None:
    """The rail mixed .btn.small with a bare .chip that had a click handler and
    no rule of its own, so a row of actions was several heights. The three tiers
    are a contract now - committing, secondary, quiet - and they share a height,
    a radius and a focus ring. Measured under the real stylesheet rather than
    read off it, because that is the thing that can drift.
    """
    report = _drive(served, """
      window.addEventListener("load", function () {
        var log = function (m) { document.getElementById("probe-log").textContent += m + "|"; };
        var host = document.createElement("div");
        host.className = "risk-side";
        host.innerHTML =
          '<button type="button" class="btn small primary">Apply</button>' +
          '<button type="button" class="btn small">Connect</button>' +
          '<button type="button" class="chip clickable">remove this</button>' +
          '<button type="button" class="chip clickable danger">remove that</button>';
        document.body.appendChild(host);
        setTimeout(function () {
          var buttons = [].slice.call(host.querySelectorAll("button"));
          var heights = buttons.map(function (b) {
            return Math.round(b.getBoundingClientRect().height);
          });
          var radii = buttons.map(function (b) { return getComputedStyle(b).borderTopLeftRadius; });
          log("heights=" + heights.join(","));
          log("radii=" + radii.filter(function (r, i) { return radii.indexOf(r) === i; }).join(","));
          log("danger=" + (getComputedStyle(buttons[3]).color !== getComputedStyle(buttons[1]).color));
        }, 400);
      });
    """)

    fields = _fields(report)
    sizes = [int(h) for h in fields["heights"].split(",") if h]
    assert len(sizes) == 4, f"the probe did not render all four tiers: {fields}"
    assert max(sizes) - min(sizes) <= 1, (
        f"the control tiers are different heights: {sizes}"
    )
    assert len(fields["radii"].split(",")) == 1, (
        f"the tiers do not share a corner radius: {fields['radii']}"
    )
    assert fields["danger"] == "true", "a destructive action looks like an ordinary one"


def test_a_disclosure_marker_is_drawn_rather_than_typed(served) -> None:
    """Both markers were a CSS escape, and the tooling that writes the
    stylesheet turned it into a raw control byte - so every arrow in the rail
    rendered as tofu followed by "b8". Drawn with borders now: no glyph, no
    escape, and no font to depend on.
    """
    report = _drive(served, _scene("""
      var card = pickRisk();
      card.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
      setTimeout(function () {
        var summaries = [].slice.call(document.querySelectorAll(
          ".concern-fold > summary, .rail-section > summary"));
        log("markers=" + summaries.length);
        log("content=" + summaries.map(function (s) {
          return getComputedStyle(s, "::before").content;
        }).filter(function (c, i, all) { return all.indexOf(c) === i; }).join(" "));
        log("widths=" + summaries.map(function (s) {
          return getComputedStyle(s, "::before").borderLeftWidth;
        }).filter(function (w, i, all) { return all.indexOf(w) === i; }).join(" "));
        var rail = document.querySelector(".rail-detail");
        log("overflows=" + (rail ? rail.scrollWidth > rail.clientWidth + 1 : "none"));
      }, 900);
    """))

    fields = _fields(report)
    assert int(fields["markers"]) >= 2, "no disclosure markers in the rail"
    assert "b8" not in fields["content"], (
        f"a marker is rendering as text: {fields['content']!r}"
    )
    assert fields["content"].strip() in ('""', '"none"', 'none', '""'), (
        f"a marker still carries a glyph: {fields['content']!r}"
    )
    assert "4px" in fields["widths"], (
        f"the marker is not the drawn triangle: {fields['widths']!r}"
    )
    assert fields["overflows"] == "false", "the detail scrolls sideways"
