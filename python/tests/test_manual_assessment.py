"""Assessing by hand, in the same vocabulary a run emits.

The library covers 15 risk patterns over 31 motifs. That is a fraction of what
an assessor will want to record, and everything outside it would otherwise be
lost - so a person can write a risk, a risk source, a consequence, an impact
and a risk control directly onto the graph, with no query matching anything.

What is under test is that these are real graph facts rather than a drawing:
they use the classes BEAM already declares, they attach the way AIRO says they
attach, they come back in the notation beside what the library found, and they
survive the round trip out to Turtle and back.
"""

from __future__ import annotations

import pytest
from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import PAIR, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.workbench.risk_view import risk_view
from conftest import TARIFF_NS, example_path, process_path

BEAMR = Namespace("http://w3id.org/beam/risk#")
AGENT = TARIFF_NS + "ConversationAgent"
CHAT = TARIFF_NS + "CustomerChatMessage"

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


@pytest.fixture(scope="module")
def scene() -> str:
    return "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in (example_path(TARIFF_NS), process_path("energy_tariff_change"))
    )


def _state(client, ttl: str, kind: str, label: str, attach=(), **extra) -> tuple[str, str]:
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "state-concept", "kind": kind, "label": label,
        "attachTo": list(attach), **extra,
    }).get_json()
    assert "error" not in body, body
    return body["ttl"], body["newId"]


def _chain(client, scene: str) -> tuple[str, dict]:
    """One assessment written by hand, end to end: source -> risk -> consequence -> impact."""
    ttl, risk = _state(client, scene, "risk", "Chat text is treated as an instruction",
                       attach=[CHAT], statedBy="Service owner", priority="high",
                       description="Nothing screens what a customer types.")
    ttl, source = _state(client, ttl, "source", "The customer chat message", attach=[CHAT])
    ttl, consequence = _state(client, ttl, "consequence", "The agent answers off-policy",
                              attach=[risk])
    ttl, impact = _state(client, ttl, "impact", "A customer acts on a wrong answer",
                         attach=[consequence])
    ttl, control = _state(client, ttl, "control", "Screen the chat text before the agent reads it",
                          attach=[risk])
    return ttl, {"risk": risk, "source": source, "consequence": consequence,
                 "impact": impact, "control": control}


# ---- the facts that get written ----


def test_each_concept_is_written_with_the_class_beam_declares(client, scene) -> None:
    ttl, made = _chain(client, scene)
    graph = Graph().parse(data=ttl, format="turtle")
    for kind, cls in (("risk", BEAMR.Risk), ("source", BEAMR.RiskSource),
                      ("consequence", BEAMR.Consequence), ("impact", BEAMR.Impact),
                      ("control", BEAMR.RiskControl)):
        assert (URIRef(made[kind]), RDF.type, cls) in graph, f"{kind} was not written as {cls}"


def test_the_chain_runs_the_way_airo_says_it_does(client, scene) -> None:
    """Direction is not a detail: a risk hangs off the element that carries it,
    a source points back at the element it arises from."""
    ttl, made = _chain(client, scene)
    graph = Graph().parse(data=ttl, format="turtle")
    assert (URIRef(CHAT), BEAMR.hasRisk, URIRef(made["risk"])) in graph
    assert (URIRef(made["source"]), BEAMR.originatedFrom, URIRef(CHAT)) in graph
    assert (URIRef(made["risk"]), BEAMR.hasConsequence, URIRef(made["consequence"])) in graph
    assert (URIRef(made["consequence"]), BEAMR.hasImpact, URIRef(made["impact"])) in graph
    # The control is the one that points outward at what it changes.
    assert (URIRef(made["control"]), BEAMR.modifiesRiskConcept, URIRef(made["risk"])) in graph


def test_a_source_attached_to_a_risk_points_at_the_risk(client, scene) -> None:
    """The same field means two things by what it is aimed at, and both are
    relations the vocabulary declares."""
    ttl, risk = _state(client, scene, "risk", "Something a person noticed", attach=[CHAT])
    ttl, source = _state(client, ttl, "source", "What gives rise to it", attach=[risk])
    graph = Graph().parse(data=ttl, format="turtle")
    assert (URIRef(source), BEAMR.isRiskSourceFor, URIRef(risk)) in graph


def test_what_the_vocabulary_cannot_say_is_refused(client, scene) -> None:
    """An impact is the impact of a consequence. Attaching one to a box in the
    architecture would invent a relation AIRO does not have."""
    body = client.post("/api/scope-edit", json={
        "ttl": scene, "op": "state-concept", "kind": "impact",
        "label": "Straight onto an element", "attachTo": [CHAT],
    })
    assert body.status_code == 400
    assert "consequence" in body.get_json()["error"].lower()


def test_a_label_is_required(client, scene) -> None:
    body = client.post("/api/scope-edit", json={
        "ttl": scene, "op": "state-concept", "kind": "risk", "attachTo": [CHAT]})
    assert body.status_code == 400


# ---- what it does to the assessment ----


def test_writing_by_hand_detects_nothing_and_hides_nothing(client, scene) -> None:
    """The same rule the scope obeys: a person's judgement is added beside what
    the library found, and changes none of it."""
    plain = summarize_result(run_assessment_from_text(scene))
    ttl, _ = _chain(client, scene)
    after = summarize_result(run_assessment_from_text(ttl))
    assert {f["id"] for f in plain["findings"]} == {f["id"] for f in after["findings"]}


def test_a_hand_written_assessment_is_drawn_beside_the_run(client, scene) -> None:
    ttl, made = _chain(client, scene)
    result = run_assessment_from_text(ttl)
    view = risk_view(summarize_result(result), result.combined_graph, result=result)
    drawn = {node["id"]: node for node in view["diagram"]["nodes"]}
    for key in ("risk", "source", "consequence", "impact"):
        assert made[key] in drawn, f"the hand-written {key} is not on the diagram"
        assert drawn[made[key]]["origin"] == "stated", (
            "a person's claim and the library's are not the same kind of statement"
        )


def test_it_reaches_the_register_with_its_author(client, scene) -> None:
    ttl, made = _chain(client, scene)
    report = client.post("/api/scope", json={"ttl": ttl}).get_json()
    stated = {risk["id"]: risk for risk in report["statedRisks"]}
    assert made["risk"] in stated
    assert stated[made["risk"]]["statedBy"] == "Service owner"
    assert (stated[made["risk"]]["priority"] or {}).get("key") == "high"


# ---- the lines, drawn and redrawn ----


def test_a_connection_can_be_taken_back_on_its_own(client, scene) -> None:
    """A line drawn wrong should cost that line. Without this, an assessor who
    joined two boxes by mistake has to start the assessment again."""
    ttl, made = _chain(client, scene)
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "unlink-concept",
        "from": made["consequence"], "to": made["risk"]}).get_json()
    assert "error" not in body, body
    after = Graph().parse(data=body["ttl"], format="turtle")
    assert (URIRef(made["risk"]), BEAMR.hasConsequence, URIRef(made["consequence"])) not in after
    # Both boxes survive; only what joined them is gone.
    assert (URIRef(made["risk"]), RDF.type, BEAMR.Risk) in after
    assert (URIRef(made["consequence"]), RDF.type, BEAMR.Consequence) in after


def test_a_connection_can_be_drawn_after_the_fact(client, scene) -> None:
    """Joining runs the same way the drop does - this concept, onto that one -
    so the relation written is the one the vocabulary declares, whichever way
    round the arrow is eventually drawn."""
    ttl, made = _chain(client, scene)
    unlinked = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "unlink-concept",
        "from": made["consequence"], "to": made["risk"]}).get_json()["ttl"]
    assert (URIRef(made["risk"]), BEAMR.hasConsequence, URIRef(made["consequence"])) not in \
        Graph().parse(data=unlinked, format="turtle")

    body = client.post("/api/scope-edit", json={
        "ttl": unlinked, "op": "link-concept",
        "from": made["consequence"], "to": made["risk"]}).get_json()
    assert "error" not in body, body
    after = Graph().parse(data=body["ttl"], format="turtle")
    assert (URIRef(made["risk"]), BEAMR.hasConsequence, URIRef(made["consequence"])) in after


def test_a_connection_the_vocabulary_forbids_is_refused(client, scene) -> None:
    ttl, made = _chain(client, scene)
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "link-concept", "from": made["impact"], "to": CHAT})
    assert body.status_code == 400


def test_only_a_line_somebody_drew_is_offered_for_removal(client, scene) -> None:
    """A derived line is recomputed by the next run, so taking it back would
    only mean it came straight back. The diagram says which is which."""
    ttl, _ = _chain(client, scene)
    result = run_assessment_from_text(ttl)
    view = risk_view(summarize_result(result), result.combined_graph, result=result)
    graph = result.combined_graph

    editable = [link for link in view["diagram"]["links"] if link.get("editable")]
    assert editable, "a hand-written assessment has lines of its own"
    for link in editable:
        assert any(
            (URIRef(link["source"]), predicate, URIRef(link["target"])) in graph
            or (URIRef(link["target"]), predicate, URIRef(link["source"])) in graph
            # The same set the server will take back out, which is what makes
            # "offered for removal" and "removable" the same list.
            for predicate in (BEAMR.hasRisk, BEAMR.originatedFrom, BEAMR.isRiskSourceFor,
                              BEAMR.hasConsequence, BEAMR.hasImpact,
                              BEAMR.modifiesRiskConcept)
        ), f"{link} is offered for removal but stands for no triple"

    derived = [link for link in view["diagram"]["links"]
               if not link.get("editable") and link["kind"] == "chain"]
    assert derived, "the run draws lines of its own, and they are not editable"


# ---- before anything has been run ----


def test_the_notation_is_drawn_before_any_assessment(client, scene) -> None:
    """An assessor should not have to run a query to record what they already
    know. The register carries the same notation with nothing found in it."""
    ttl, made = _chain(client, scene)
    report = client.post("/api/scope", json={"ttl": ttl}).get_json()
    drawn = {node["id"]: node for node in report["diagram"]["nodes"]}
    for key in ("risk", "source", "consequence", "impact"):
        assert made[key] in drawn, f"the hand-written {key} is not drawn without a run"
    assert all(node["origin"] == "stated" for node in report["diagram"]["nodes"]
               if node["id"] in set(made.values()))
    # Nothing was assessed, so nothing was found.
    assert not [node for node in report["diagram"]["nodes"] if node["origin"] == "derived"
                and node["band"] == "risk"]


# ---- out, and back ----


def test_it_survives_the_round_trip_to_turtle(client, scene) -> None:
    """Export is the graph in the editor, so what was written by hand has to
    parse back as the same facts."""
    ttl, made = _chain(client, scene)
    reparsed = Graph().parse(data=Graph().parse(data=ttl, format="turtle").serialize(
        format="turtle"), format="turtle")
    assert (URIRef(made["source"]), RDF.type, BEAMR.RiskSource) in reparsed
    assert (URIRef(made["consequence"]), BEAMR.hasImpact, URIRef(made["impact"])) in reparsed


def test_removing_one_leaves_no_arrow_pointing_at_it(client, scene) -> None:
    ttl, made = _chain(client, scene)
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "remove-concept", "concept": made["consequence"]}).get_json()
    assert "error" not in body, body
    after = Graph().parse(data=body["ttl"], format="turtle")
    node = URIRef(made["consequence"])
    assert (node, None, None) not in after
    assert (None, None, node) not in after
    # The rest of the assessment is untouched.
    assert (URIRef(made["risk"]), RDF.type, BEAMR.Risk) in after


def test_only_a_hand_written_concept_can_be_removed(client, scene) -> None:
    body = client.post("/api/scope-edit", json={
        "ttl": scene, "op": "remove-concept", "concept": AGENT})
    assert body.status_code == 400
    assert Graph().parse(data=scene, format="turtle").value(URIRef(AGENT), RDF.type) is not None
    assert PAIR is not None


# ---- the control somebody says is already there ----


def test_a_control_can_modify_any_of_the_four(client, scene) -> None:
    """beamr:modifiesRiskConcept ranges over beamr:RiskConcept, and all four -
    risk, source, consequence, impact - are one. A control that could only hang
    off a risk would refuse the commonest case an assessor writes: something
    that limits the damage rather than stopping the cause."""
    ttl, risk = _state(client, scene, "risk", "Chat text is read as an instruction",
                       attach=[CHAT])
    ttl, source = _state(client, ttl, "source", "The chat message", attach=[CHAT])
    ttl, consequence = _state(client, ttl, "consequence", "The agent answers off-policy",
                              attach=[risk])
    ttl, impact = _state(client, ttl, "impact", "A customer acts on it", attach=[consequence])

    made = {}
    for name, target in (("on the risk", risk), ("on the source", source),
                         ("on the consequence", consequence), ("on the impact", impact)):
        ttl, made[name] = _state(client, ttl, "control", f"Control {name}", attach=[target])

    graph = Graph().parse(data=ttl, format="turtle")
    for name, target in (("on the risk", risk), ("on the source", source),
                         ("on the consequence", consequence), ("on the impact", impact)):
        assert (URIRef(made[name]), RDF.type, BEAMR.RiskControl) in graph
        assert (URIRef(made[name]), BEAMR.modifiesRiskConcept, URIRef(target)) in graph, (
            f"a control written {name} did not point at it"
        )


def test_a_control_on_an_element_of_the_design_is_refused(client, scene) -> None:
    """A control modifies a risk concept, not a box in the architecture. What
    goes on the architecture is a control motif the canvas inserts, and that is
    a different act - it changes the design, and a re-run reads the change."""
    body = client.post("/api/scope-edit", json={
        "ttl": scene, "op": "state-concept", "kind": "control",
        "label": "Straight onto an element", "attachTo": [CHAT],
    })
    assert body.status_code == 400
    assert "control" in body.get_json()["error"].lower()


def test_writing_a_control_by_hand_clears_no_finding(client, scene) -> None:
    """The distinction the whole method rests on.

    A control clears a finding by being built, not by being asserted - the
    escape in a risk query is a structural shape, and saying the words does not
    put it in the design. So this records a claim beside the run and the run
    says exactly what it said before. Clearing one is triage, which is a
    different act with an author and a reason.
    """
    plain = summarize_result(run_assessment_from_text(scene))
    ttl, risk = _state(client, scene, "risk", "Something a person noticed", attach=[CHAT])
    ttl, _ = _state(client, ttl, "control", "We screen it in the gateway", attach=[risk])
    after = summarize_result(run_assessment_from_text(ttl))
    assert {f["id"] for f in plain["findings"]} == {f["id"] for f in after["findings"]}
    assert {f["status"] for f in after["findings"]} == {"candidate"}, (
        "a hand-written control must not decide anything about a finding"
    )


def test_a_hand_written_control_is_drawn_and_marked_as_somebody_s(client, scene) -> None:
    """Beside the controls the library suggested, and told apart from them: one
    is a person's claim that something is handled, the other is what a
    registered rewrite could build."""
    ttl, made = _chain(client, scene)
    result = run_assessment_from_text(ttl)
    view = risk_view(summarize_result(result), result.combined_graph)

    drawn = {node["id"]: node for node in view["diagram"]["nodes"]}
    mine = drawn.get(made["control"])
    assert mine, "a control written by hand is not on the notation"
    assert mine["band"] == "control", f"drawn in the {mine['band']} band"
    assert mine["origin"] == "stated", "a person's control is drawn as a person's"

    derived = [n for n in drawn.values() if n["band"] == "control" and n["origin"] == "derived"]
    assert derived, "the library's own suggested controls are still drawn"

    joined = {(link["source"], link["target"]) for link in view["diagram"]["links"]}
    assert (made["control"], made["risk"]) in joined, (
        "nothing joins the control to the risk it modifies"
    )
