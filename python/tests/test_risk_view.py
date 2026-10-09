"""The risk view: grouping, scoping, and reconciliation.

The properties under test are the ones that make the view honest rather than
merely tidier - nothing is lost by grouping, nothing is hidden by scoping, and
a stated risk the library cannot speak to is still reported.
"""

from __future__ import annotations

import json

import pytest
from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import PAIR, run_assessment, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.workbench.backward import backward_index
from airiskkg.workbench.risk_view import risk_view
from airiskkg.workbench.scope import read_scope, stated_risks
from conftest import AGENT_NS, ONYX_NS, example_path, process_path

BEAMR = Namespace("http://w3id.org/beam/risk#")

pytestmark = pytest.mark.ui


def _assess(paths):
    result = run_assessment([str(p) for p in paths], write_outputs=False)
    return summarize_result(result), result


@pytest.fixture(scope="module")
def agent_scene():
    paths = [example_path(AGENT_NS), process_path("it_service_desk")]
    summary, result = _assess(paths)
    return risk_view(summary, result.combined_graph), summary


@pytest.fixture(scope="module")
def repeating_view():
    """Onyx raises the same concern several times over, which is what makes it
    the scene for telling repeats apart."""
    summary, result = _assess([example_path(ONYX_NS)])
    return risk_view(summary, result.combined_graph)


@pytest.fixture(scope="module")
def onyx_view():
    summary, result = _assess([example_path(ONYX_NS)])
    return risk_view(summary, result.combined_graph), summary


# ---- grouping ----


def test_grouping_loses_no_finding(onyx_view) -> None:
    view, summary = onyx_view
    collapsed = sum(group["corroboration"] for group in view["groups"])
    assert collapsed == len(summary["findings"])
    ids = {fid for group in view["groups"] for fid in group["findingIds"]}
    assert ids == {finding["id"] for finding in summary["findings"]}


def test_co_matching_motifs_collapse_to_one_concern(onyx_view) -> None:
    """Nested motifs co-match by design, so the same weakness at the same place
    arrives once per structure. That is corroboration, not four risks."""
    view, summary = onyx_view
    assert len(view["groups"]) < len(summary["findings"])
    biggest = max(view["groups"], key=lambda group: group["corroboration"])
    assert biggest["corroboration"] > 1
    # The motifs that reached it are kept, so the collapse adds information.
    assert len(biggest["motifs"]) > 1


def test_a_concern_says_why_it_fired(onyx_view) -> None:
    """pair:hasSatisfiedCondition is emitted on every finding; it must reach a reader."""
    view, _ = onyx_view
    assert all(group["why"] for group in view["groups"])


def test_clearable_is_read_from_the_rewrites_not_from_the_suggestions(onyx_view) -> None:
    view, _ = onyx_view
    clearable = [g for g in view["groups"] if g["clearable"]]
    triage = [g for g in view["groups"] if not g["clearable"]]
    assert clearable and triage, "the split is the point; a uniform list hides it"
    for group in triage:
        assert not group["applicableControls"]


# ---- scoping ----


def test_a_scope_narrows_the_reading_and_removes_nothing(agent_scene) -> None:
    view, summary = agent_scene
    assert view["scope"]["present"], "the bundled scene states a scope"
    assert view["scope"]["undesiredOutcomes"]
    # Every finding is still accounted for, in scope or out of it.
    collapsed = sum(group["corroboration"] for group in view["groups"])
    assert collapsed == len(summary["findings"])
    buckets = view["summary"]["scope"]
    assert sum(buckets.values()) == len(view["groups"])


def test_a_concern_with_no_risk_domain_is_unclassified_never_out(agent_scene) -> None:
    """The trap this view exists to avoid.

    Two risk patterns reach no domain of harm, because nothing upstream maps
    their OWASP entry to one. Treating "reaches no domain" as "outside the
    scope" would silently drop exactly the agentic findings a service-desk
    owner most needs, so they are marked unclassified and shown.
    """
    view, _ = agent_scene
    undomained = [g for g in view["groups"] if not g["riskDomains"]]
    assert undomained, "the agentic example raises findings that reach no domain"
    for group in undomained:
        assert group["scopeMatch"] == "unclassified"
    assert view["summary"]["unclassified"] == len(undomained)


def test_scope_is_read_from_the_graph_not_held_in_the_server() -> None:
    graph = Graph()
    for path in (example_path(AGENT_NS), process_path("it_service_desk")):
        graph.parse(path, format="turtle")
    scope = read_scope(graph)
    assert scope["present"]
    assert scope["desiredOutcome"]
    assert scope["statedBy"]
    assert [s["id"] for s in scope["systems"]] == [f"{AGENT_NS}AgentSystem"]


def test_a_graph_with_no_scope_reads_as_no_scope(onyx_view) -> None:
    view, _ = onyx_view
    assert view["scope"]["present"] is False
    assert all(group["scopeMatch"] == "all" for group in view["groups"])


# ---- reconciliation ----


def test_a_stated_risk_nothing_corroborates_is_reported_not_dropped(agent_scene) -> None:
    """A concern the library has no risk pattern for stays in the register.

    Saying "this is outside what the method models" is what keeps the rest
    credible; quietly dropping it is what does not.
    """
    view, _ = agent_scene
    stated_only = view["reconciliation"]["statedOnly"]
    assert stated_only, "the bundled scene states one risk with no structural signature"
    assert view["reconciliation"]["statedTotal"] == len(view["statedRisks"])
    accounted = view["reconciliation"]["corroborated"] + view["reconciliation"]["raisedOnly"]
    assert accounted == len(view["groups"])


def test_a_stated_risk_meets_the_concern_at_the_element_it_names(agent_scene) -> None:
    view, _ = agent_scene
    corroborated = [g for g in view["groups"] if g["statedRisks"]]
    assert corroborated
    by_id = {risk["id"]: risk for risk in view["statedRisks"]}
    for group in corroborated:
        cited = {element["id"] for element in group["evidence"]}
        for touching in group["statedRisks"]:
            named = {e["id"] for e in by_id[touching["id"]]["elements"]}
            assert cited & named, "a stated risk is attached to an element, not to a risk name"


def test_priority_is_carried_from_the_person_never_computed(agent_scene) -> None:
    view, _ = agent_scene
    graph = Graph()
    for path in (example_path(AGENT_NS), process_path("it_service_desk")):
        graph.parse(path, format="turtle")
    stated = {risk["id"]: risk for risk in stated_risks(graph)}
    assert any(risk["priority"] for risk in stated.values())
    # Nothing the pipeline produced carries one.
    for group in view["groups"]:
        assert "priority" not in group


# ---- the notation: what a Risk Source is, and what Impact is not ----


def test_a_risk_source_is_an_element_of_the_design(agent_scene) -> None:
    """AIRO: an element with the potential to give rise to the risk. So the box
    names an element this graph holds, and hangs off it - not a curated sentence
    that would read the same for every system assessed."""
    view, _ = agent_scene
    graph = Graph()
    for path in (example_path(AGENT_NS), process_path("it_service_desk")):
        graph.parse(path, format="turtle")

    sources = [node for node in view["diagram"]["nodes"] if node["band"] == "source"]
    assert sources, "this scene raises concerns, so something gives rise to them"
    attaches = {
        (link["source"], link["target"])
        for link in view["diagram"]["links"] if link["kind"] == "attaches"
    }
    for node in sources:
        element = URIRef(node["element"])
        assert (element, None, None) in graph, f"{node['title']} is not in the design"
        assert (node["id"], str(element)) in attaches, (
            f"{node['title']} does not hang off the element it names"
        )
        assert node["body"], "a risk source has to say why it is one"


def test_a_risk_source_is_what_feeds_the_path_not_what_it_produces(agent_scene) -> None:
    """Where the risk ends up is not where it comes from. An element a cited
    step produces is the sink, and must not be offered as the source."""
    view, _ = agent_scene
    graph = Graph()
    for path in (example_path(AGENT_NS), process_path("it_service_desk")):
        graph.parse(path, format="turtle")
    beam = Namespace("http://w3id.org/beam/core#")

    by_key = {group["key"]: group for group in view["groups"]}
    for link in view["diagram"]["links"]:
        if link["kind"] != "chain" or link.get("label") != "isRiskSourceFor":
            continue
        group = by_key.get(link["target"])
        if group is None:
            continue
        element = URIRef(link["source"].removeprefix("source:"))
        cited = {URIRef(e["id"]) for e in group["evidence"]}
        produced_by_cited = {
            target for step in cited for target in graph.objects(step, beam.produce)
        }
        assert element not in produced_by_cited, (
            f"{element} is produced inside the path {group['label']} cites"
        )


def test_no_impact_is_drawn_from_a_taxonomy_link(agent_scene) -> None:
    """A harm domain is where the entry sits in someone's taxonomy, not an
    impact on this system. Drawing it as one claimed more than the run knows."""
    view, _ = agent_scene
    domains = {
        domain["id"] for group in view["groups"] for domain in group["riskDomains"]
    }
    assert domains, "the findings still roll up to domains - that data is kept"
    drawn = {node["id"] for node in view["diagram"]["nodes"] if node["band"] == "impact"}
    assert not (drawn & domains), "a harm domain is being drawn as an Impact"


def test_a_condition_is_never_listed_twice_under_one_concern(onyx_view) -> None:
    """Two applicability conditions in the library carry byte-identical labels,
    so a concern satisfying both printed the same sentence twice. Grouping is by
    condition, which is right for the data; what is shown is the sentence, so
    that is what has to be distinct."""
    view, _ = onyx_view
    for group in view["groups"]:
        assert len(group["why"]) == len(set(group["why"])), (
            f"{group['label']} says the same thing twice: {group['why']}"
        )


def test_an_architecture_is_drawn_as_a_system_not_as_a_statement_of_scope(
    agent_scene,
) -> None:
    """Every beam:System used to land in the Context band, so the four
    architectures of the tariff graph read as four statements of scope. A
    system is the coarse handle a risk is rolled up to; the Context box is the
    frame somebody put around the assessment. They are not the same row."""
    view, _ = agent_scene
    systems = [node for node in view["diagram"]["nodes"] if node.get("isSystem")]
    assert systems, "the scene has an architecture, so it has a system to draw"
    assert all(node["band"] == "system" for node in systems)
    context = [node for node in view["diagram"]["nodes"] if node["band"] == "context"]
    assert not any(node.get("isSystem") for node in context)


def test_a_system_says_what_it_holds_and_draws_a_line_to_each_part(agent_scene) -> None:
    """Folded, a system is the only thing a risk inside it can point at. So it
    has to carry its parts - and the line down to each one is what the canvas
    draws once the reader unfolds it. Without it the two layers sat on the same
    page joined by nothing."""
    view, _ = agent_scene
    graph = Graph()
    for path in (example_path(AGENT_NS), process_path("it_service_desk")):
        graph.parse(path, format="turtle")

    contains = {
        (link["source"], link["target"])
        for link in view["diagram"]["links"] if link.get("contains")
    }
    assert contains, "nothing joins a system to what it is built from"
    for node in (n for n in view["diagram"]["nodes"] if n.get("isSystem")):
        members = node.get("members") or []
        assert members, f"{node['title']} is drawn as holding nothing"
        for member in members:
            assert (URIRef(member), None, None) in graph
            assert (node["id"], member) in contains, (
                f"{node['title']} has no line down to {member}"
            )


def test_a_concern_names_the_system_and_the_work_it_stands_in(agent_scene) -> None:
    """The risk is the anchor, so it has to reach its system and its activity
    without the reader following pair:refinedBy by eye. This is what the canvas
    rolls an attachment up to while the parts are folded away, and what the
    detail panel groups by."""
    view, _ = agent_scene
    risks = [node for node in view["diagram"]["nodes"] if node["band"] == "risk"]
    assert risks, "the scene raises concerns"
    systems = {node["id"] for node in view["diagram"]["nodes"] if node.get("isSystem")}
    activities = {node["id"] for node in view["diagram"]["nodes"] if node.get("isActivity")}

    placed = [node for node in risks if node.get("systems")]
    assert placed, "no concern says which architecture it stands in"
    for node in placed:
        assert set(node["systems"]) <= systems, f"{node['title']} names an undrawn system"
        assert set(node.get("activities") or []) <= activities, (
            f"{node['title']} names work that is not on the diagram"
        )
    # The scene's process refines its architecture, so the work is reachable.
    assert any(node.get("activities") for node in placed)


def test_every_line_on_the_notation_says_what_it_means(agent_scene) -> None:
    """An unlabelled arrow asks the reader to already know which of the AIRO
    relations it stands for, which is the thing the diagram exists to save them
    from."""
    view, _ = agent_scene
    unlabelled = [
        link for link in view["diagram"]["links"] if not link.get("label")
    ]
    assert not unlabelled, (
        "lines with no label: "
        + ", ".join(sorted({f"{link['kind']}" for link in unlabelled}))
    )


# ---- the backward index ----


def test_every_risk_pattern_is_reachable_backward() -> None:
    """One axis does not cover the library, which is why there are two."""
    index = backward_index()
    by_outcome = {p for entry in index["outcomes"] for p in entry["riskPatterns"]}
    by_capability = {p for entry in index["capabilities"] for p in entry["riskPatterns"]}
    unreachable = set(index["riskPatterns"]) - by_outcome - by_capability
    assert not unreachable, f"no way back to {sorted(unreachable)}"


def test_an_outcome_no_risk_pattern_reaches_says_so() -> None:
    index = backward_index()
    for outcome in index["outcomes"]:
        assert outcome["reachable"] == bool(outcome["riskPatterns"])
    assert any(not outcome["reachable"] for outcome in index["outcomes"]), (
        "at least one domain of harm is unreached, and the starter must not "
        "offer it as though picking it would find something"
    )


def test_the_work_plan_names_conditions_a_person_can_answer() -> None:
    index = backward_index()
    for entry in index["riskPatterns"].values():
        assert entry["conditions"], f"{entry['label']} asks nothing"


# ---- the property the whole design rests on ----


def test_stating_a_scope_does_not_change_what_is_detected() -> None:
    """Context scopes the reading; it never gates the run.

    Gating detection on an annotation would make "we did not ask" and "it does
    not apply" indistinguishable, which is the failure R4 exists to prevent.
    """
    architecture = example_path(AGENT_NS)
    process = process_path("it_service_desk")

    with_scope, _ = _assess([architecture, process])

    # The same two graphs with every scope and stated-risk triple removed.
    stripped = Graph()
    for path in (architecture, process):
        stripped.parse(path, format="turtle")
    for scope in list(stripped.subjects(RDF.type, PAIR.AssessmentScope)):
        stripped.remove((scope, None, None))
    for consequence in list(stripped.subjects(RDF.type, BEAMR.Consequence)):
        stripped.remove((consequence, None, None))
    for risk in list(stripped.subjects(RDF.type, BEAMR.Risk)):
        stripped.remove((risk, None, None))
        stripped.remove((None, BEAMR.hasRisk, risk))

    result = run_assessment_from_text(stripped.serialize(format="turtle"))
    without_scope = summarize_result(result)

    assert {f["id"] for f in with_scope["findings"]} == {
        f["id"] for f in without_scope["findings"]
    }
    assert with_scope["summary"]["motifMatchCount"] == without_scope["summary"]["motifMatchCount"]


def test_the_view_survives_a_round_trip_through_json(agent_scene) -> None:
    view, _ = agent_scene
    assert json.loads(json.dumps(view))["summary"] == view["summary"]


# ---- the register, read and written through the editor ----


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


def _scene_ttl() -> str:
    return "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in (example_path(AGENT_NS), process_path("it_service_desk"))
    )


def test_the_register_reads_back_without_running_anything(client) -> None:
    """A scope is a document fact. Making a reader run a two-second assessment
    to see what they just typed would put the two on the same clock, and they
    are not: the concerns go stale, the scope does not."""
    body = client.post("/api/scope", json={"ttl": _scene_ttl()}).get_json()
    assert body["scope"]["present"]
    assert body["scope"]["desiredOutcome"]
    assert len(body["statedRisks"]) == 4
    # The domain label lives in the library, not in the submitted graph.
    reached = {d["label"] for o in body["scope"]["undesiredOutcomes"] for d in o["domains"]}
    assert "Privacy & Security" in reached


def test_an_empty_graph_has_an_empty_register(client) -> None:
    body = client.post("/api/scope", json={"ttl": ""}).get_json()
    assert body["scope"]["present"] is False
    assert body["statedRisks"] == []


def test_stating_a_risk_writes_it_into_the_graph_and_nothing_else(client) -> None:
    before = _scene_ttl()
    body = client.post("/api/scope-edit", json={
        "ttl": before, "op": "state-risk",
        "label": "The reply repeats the whole ticket back",
        "elements": [f"{AGENT_NS}DraftReply"],
        "priority": "high", "statedBy": "a test",
    }).get_json()

    after = Graph().parse(data=body["ttl"], format="turtle")
    stated = {risk["label"]: risk for risk in stated_risks(after)}
    assert "The reply repeats the whole ticket back" in stated
    written = stated["The reply repeats the whole ticket back"]
    assert written["priority"]["key"] == "high", (
        "the priority must read the same with or without the library loaded"
    )
    assert [e["id"] for e in written["elements"]] == [f"{AGENT_NS}DraftReply"]

    # And the run over the amended graph finds exactly what it found before.
    base = summarize_result(run_assessment_from_text(before))
    amended = summarize_result(run_assessment_from_text(body["ttl"]))
    assert {f["id"] for f in base["findings"]} == {f["id"] for f in amended["findings"]}


def test_an_outcome_is_removed_whole(client) -> None:
    ttl = _scene_ttl()
    outcome = client.post("/api/scope", json={"ttl": ttl}).get_json()[
        "scope"]["undesiredOutcomes"][0]["id"]
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "remove-outcome", "outcome": outcome}).get_json()
    after = Graph().parse(data=body["ttl"], format="turtle")
    assert (None, None, URIRef(outcome)) not in after
    assert (URIRef(outcome), None, None) not in after


# ---- triage ----


def _triaged(ttl: str, findings: list[str], status: str, client) -> str:
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "triage", "findings": findings, "status": status,
        "rationale": "Handled by the engineer approval in the process.",
        "statedBy": "a test",
    }).get_json()
    assert "error" not in body, body
    return body["ttl"]


def test_a_judgement_replaces_the_emitted_status_rather_than_joining_it(client) -> None:
    """The output contract allows a finding exactly one pair:findingStatus.

    A decision that sat beside the emitted "candidate" would break the contract
    the assessment is supposed to satisfy.
    """
    ttl = _scene_ttl()
    summary, result = _assess([example_path(AGENT_NS), process_path("it_service_desk")])
    target = summary["findings"][0]["id"]

    decided = run_assessment_from_text(_triaged(ttl, [target], "accepted", client))
    statuses = list(decided.risk_findings.objects(URIRef(target), PAIR.findingStatus))
    assert [str(s) for s in statuses] == ["accepted"]


def test_a_judgement_changes_no_finding_into_or_out_of_existence(client) -> None:
    ttl = _scene_ttl()
    before = summarize_result(run_assessment_from_text(ttl))
    after = summarize_result(run_assessment_from_text(
        _triaged(ttl, [before["findings"][0]["id"]], "refuted", client)))
    assert {f["id"] for f in before["findings"]} == {f["id"] for f in after["findings"]}
    assert before["summary"]["motifMatchCount"] == after["summary"]["motifMatchCount"]


def test_a_concern_settles_only_when_every_finding_under_it_is_decided(client) -> None:
    """A concern is what a reader judges; the findings under it are how the
    library reached it. Settling half of them would report a decision nobody made."""
    ttl = _scene_ttl()
    summary, result = _assess([example_path(AGENT_NS), process_path("it_service_desk")])
    view = risk_view(summary, result.combined_graph)
    group = max(view["groups"], key=lambda g: g["corroboration"])
    assert group["corroboration"] > 1

    partial = run_assessment_from_text(_triaged(ttl, group["findingIds"][:1], "accepted", client))
    partial_view = risk_view(summarize_result(partial), partial.combined_graph)
    assert partial_view["summary"]["settled"] == 0

    whole = run_assessment_from_text(_triaged(ttl, group["findingIds"], "accepted", client))
    whole_view = risk_view(summarize_result(whole), whole.combined_graph)
    assert whole_view["summary"]["settled"] == 1
    settled = [g for g in whole_view["groups"] if g["settled"]][0]
    assert settled["status"] == "accepted"
    assert settled["decisions"][0]["rationale"]
    assert settled["decisions"][0]["statedBy"] == "a test"


def test_a_judgement_can_be_reopened(client) -> None:
    ttl = _scene_ttl()
    summary, result = _assess([example_path(AGENT_NS), process_path("it_service_desk")])
    ids = risk_view(summary, result.combined_graph)["groups"][0]["findingIds"]

    decided = _triaged(ttl, ids, "refuted", client)
    reopened = client.post("/api/scope-edit", json={
        "ttl": decided, "op": "triage", "findings": ids, "status": ""}).get_json()["ttl"]

    run = run_assessment_from_text(reopened)
    view = risk_view(summarize_result(run), run.combined_graph)
    assert view["summary"]["settled"] == 0
    assert all(g["status"] == "candidate" for g in view["groups"])


def test_an_unknown_status_is_refused(client) -> None:
    body = client.post("/api/scope-edit", json={
        "ttl": _scene_ttl(), "op": "triage",
        "findings": ["http://example.org/x"], "status": "probably-fine"})
    assert body.status_code == 400
    assert "confirmed" in body.get_json()["error"]


# ---- the two views, side by side ----


def test_the_process_and_the_architecture_are_asked_about_never_reconciled_silently(
    agent_scene,
) -> None:
    """The join neither view can make on its own.

    The process shows an engineer approving the account change; the architecture
    represents no approval on the agent's path. That is a question about which
    description is wrong - never a clearing, because a control clears a finding
    by being built.
    """
    view, _ = agent_scene
    assert view["questions"], "the bundled scene has a human step the architecture omits"
    for question in view["questions"]:
        assert question["humanSteps"]
        assert "?" in question["question"], "it has to stay a question"

    # Only raised where nothing structural would clear it: a rewrite is a
    # better answer than a conversation.
    by_key = {group["key"]: group for group in view["groups"]}
    for question in view["questions"]:
        assert not by_key[question["concern"]]["clearable"]


def test_the_assurance_gaps_are_the_controls_not_the_near_misses(agent_scene) -> None:
    """The near-miss report read whole is noise; filtered to the motifs that
    realize a control it says why the findings stand."""
    from airiskkg.workbench.cross_view import assurance_gaps
    from airiskkg.workbench.gaps import motif_gaps

    ttl = "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in (example_path(AGENT_NS), process_path("it_service_desk"))
    )
    gaps = motif_gaps(ttl)
    filtered = assurance_gaps(gaps)
    assert filtered and len(filtered) < len(gaps)
    for row in filtered:
        assert row["controls"], "every row names the control it stands for"
        assert row["satisfied"] < row["total"], "a matched motif is not a gap"


def test_a_triaged_run_still_satisfies_the_output_contract(client) -> None:
    """The constraint the whole triage design is shaped by.

    sh:maxCount 1 on pair:findingStatus is why a decision replaces the emitted
    status instead of accompanying it; sh:in is why the four decidable values
    are the contract's own vocabulary rather than words of our choosing.
    """
    pytest.importorskip("pyshacl")
    from pyshacl import validate as shacl_validate

    from airiskkg.paths import CORE_DIR, SHACL_DIR

    ttl = _scene_ttl()
    summary, _ = _assess([example_path(AGENT_NS), process_path("it_service_desk")])
    every = [finding["id"] for finding in summary["findings"]]
    decided = run_assessment_from_text(_triaged(ttl, every, "accepted", client))

    ontology = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        ontology.parse(CORE_DIR / name, format="turtle")
    conforms, _results, text = shacl_validate(
        data_graph=decided.risk_findings,
        shacl_graph=Graph().parse(SHACL_DIR / "assessment_output_contract.ttl", format="turtle"),
        ont_graph=ontology,
        advanced=True,
        inference="none",
    )
    assert conforms, text
    statuses = {str(s) for s in decided.risk_findings.objects(None, PAIR.findingStatus)}
    assert statuses == {"accepted"}


def test_a_judgement_about_a_finding_that_no_longer_fires_is_simply_not_applied(client) -> None:
    """Finding IRIs are deterministic so a judgement survives a re-run — but a
    design that changed may no longer raise the thing that was judged, and the
    decision must not resurrect it."""
    ttl = _scene_ttl()
    stale = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "triage",
        "findings": ["http://w3id.org/airiskkg/generated/risk-finding/nothing-like-this"],
        "status": "refuted"}).get_json()["ttl"]

    run = run_assessment_from_text(stale)
    view = risk_view(summarize_result(run), run.combined_graph)
    assert view["summary"]["settled"] == 0
    assert all(group["status"] == "candidate" for group in view["groups"])


# ---- backward: name a risk, then ask the graph about it ----


PAT = "http://w3id.org/airiskkg/patterns#"


def _with_agenda(ttl: str, patterns: list[str], client) -> str:
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "set-agenda", "patterns": [PAT + p for p in patterns],
    }).get_json()
    assert "error" not in body, body
    return body["ttl"]


def _agenda_of(ttl: str) -> dict:
    from airiskkg.workbench.gaps import motif_gaps

    result = run_assessment_from_text(ttl)
    summary = summarize_result(result)
    view = risk_view(summary, result.combined_graph, gaps=motif_gaps(ttl), result=result)
    return view["agenda"]


def test_a_named_risk_comes_back_with_a_verdict(client) -> None:
    """The backward move: ask about one risk, get an answer about that one."""
    ttl = _with_agenda(_scene_ttl(), ["ToolMisuseRiskPattern"], client)
    agenda = _agenda_of(ttl)
    assert [d["label"] for d in agenda["checked"]] == ["Tool misuse risk pattern"]
    assert agenda["checked"][0]["verdict"] == "raised"
    assert agenda["checked"][0]["findings"], "a raised verdict has to carry its evidence"


def test_a_risk_that_did_not_fire_is_diagnosed_rather_than_silent(client) -> None:
    """The gap this exists to close.

    Everywhere else a risk that does not fire is simply absent from the output,
    and absence reads as safety. Here it comes back saying which of four things
    happened, and what is missing.
    """
    ttl = _with_agenda(_scene_ttl(), [
        "SupplyChainCompromiseRiskPattern",   # nothing external is stated
        "ExcessiveAgencyRiskPattern",         # the shape is there, no finding
    ], client)
    by_label = {d["label"]: d for d in _agenda_of(ttl)["checked"]}

    supply = by_label["Supply chain compromise risk pattern"]
    assert supply["verdict"] == "structure-incomplete"
    closest = supply["motifs"][0]
    assert closest["satisfied"] < closest["total"]
    named = [node["role"] for node in closest["missingNodes"]] + \
            [edge["text"] for edge in closest["missingEdges"]]
    assert named, "an incomplete verdict has to say what is missing"

    agency = by_label["Excessive agency risk pattern"]
    assert agency["verdict"] == "structure-present"
    assert "represented" in agency, "it has to say whether anything would interrupt it"


def test_no_verdict_reads_as_a_claim_about_the_system(client) -> None:
    """R4, in the one place a reader is most likely to over-read.

    Closed-world is over the submitted graph, never over the system, so a
    verdict that did not fire has to say so in its own words.
    """
    from airiskkg.workbench.hypothesis import ABSENT, INCOMPLETE, PRESENT, VERDICT_MEANING

    for verdict in (PRESENT, INCOMPLETE, ABSENT):
        meaning = VERDICT_MEANING[verdict].lower()
        assert any(
            phrase in meaning
            for phrase in ("not mean the system is safe", "gap in the description",
                           "about the drawing")
        ), f"{verdict} does not disclaim a reading it invites: {meaning}"


def test_choosing_an_agenda_does_not_change_what_is_detected(client) -> None:
    """The agenda chooses what is reported on, never what may be detected.

    If it narrowed the run, "we did not ask" and "it does not apply" would be
    the same answer again - which is the thing this was built to separate.
    """
    plain = _scene_ttl()
    narrowed = _with_agenda(plain, ["ToolMisuseRiskPattern"], client)

    before = summarize_result(run_assessment_from_text(plain))
    after = summarize_result(run_assessment_from_text(narrowed))
    assert {f["id"] for f in before["findings"]} == {f["id"] for f in after["findings"]}
    assert before["summary"]["motifMatchCount"] == after["summary"]["motifMatchCount"]


def test_a_risk_raised_without_being_asked_is_still_reported(client) -> None:
    """The run stays whole, so the library still says what it saw.

    An assessment that reported only what it was asked would be a search, not an
    assessment.
    """
    ttl = _with_agenda(_scene_ttl(), ["ToolMisuseRiskPattern"], client)
    agenda = _agenda_of(ttl)
    assert agenda["raisedOffAgenda"], "findings outside the agenda vanished"
    assert "Agent goal hijack risk pattern" in agenda["raisedOffAgenda"]


def test_what_was_never_examined_is_counted_not_omitted(client) -> None:
    ttl = _with_agenda(_scene_ttl(), ["ToolMisuseRiskPattern"], client)
    agenda = _agenda_of(ttl)
    assert agenda["counts"]["not-examined"] == len(agenda["notExamined"])
    from airiskkg.assessment_runner import load_base_graph

    library = set(load_base_graph().subjects(RDF.type, PAIR.RiskPattern))
    assert len(agenda["checked"]) + len(agenda["notExamined"]) == len(library)


def test_stating_a_harm_is_enough_to_have_an_agenda() -> None:
    """An analyst who names an outcome should not also have to name risk patterns."""
    agenda = _agenda_of(_scene_ttl())  # the scene states outcomes, not patterns
    assert agenda is not None
    assert len(agenda["checked"]) > 1
    assert {d["verdict"] for d in agenda["checked"]} > {"raised"}, (
        "an agenda of only raised risks would mean the un-fired ones went silent again"
    )


def test_concerns_that_share_a_name_say_where_they_are(repeating_view) -> None:
    """Prompt injection is raised once per untrusted-content/generation pair, so
    three boxes reading "Candidate prompt injection" are three true and
    different answers - and nothing on them said which was which.

    A concern is the (risk pattern, evidence set) group, so the evidence is what
    differs. The element fewest siblings cite says it in the fewest words.
    """
    view = repeating_view
    by_label: dict[str, list[dict]] = {}
    for group in view["groups"]:
        by_label.setdefault(group["label"], []).append(group)

    repeated = {label: rows for label, rows in by_label.items() if len(rows) > 1}
    assert repeated, "this scene no longer raises the same concern twice"

    for label, rows in repeated.items():
        places = [row.get("distinguisher") for row in rows]
        assert all(places), f"a repeat of {label!r} says nothing about where it is"
        assert len(set(places)) == len(places), (
            f"two concerns called {label!r} name the same place: {places}"
        )

    alone = [row for rows in by_label.values() if len(rows) == 1 for row in rows]
    assert all(not row.get("distinguisher") for row in alone), (
        "a concern with a name of its own does not need telling apart"
    )


def test_a_concern_drawn_once_carries_its_place_beside_the_chip(repeating_view) -> None:
    """Beside the type chip, never on it and never in the title.

    The chip is the notation's type label and has to keep reading "Risk" -
    overloading it with which one this is broke the test that reads the notation
    off the canvas. The title would wrap the card onto another line.
    """
    view = repeating_view
    where = {
        group["key"]: group.get("distinguisher")
        for group in view["groups"] if group.get("distinguisher")
    }
    assert where, "nothing to tell apart in this scene"
    for node in view["diagram"]["nodes"]:
        if node["band"] != "risk" or node["id"] not in where:
            continue
        assert node.get("where") == where[node["id"]], (
            f"the box does not say where it is: {node.get('where')!r}"
        )
        assert not node.get("chip"), (
            "the place is on the type chip, which has to keep reading 'Risk'"
        )
        assert where[node["id"]] not in node["title"], (
            "the place is in the title as well, which wraps the box onto another line"
        )
