"""The overview: the run placed on the work, for people not editing the graph.

The page used to list findings per activity. Attribution is not partition - one
architecture carries out several activities - so the same concern was repeated
once per activity it reached, and ten concerns read as thirty. The capability is
the honest unit: named once, with the work it does underneath it.

What no activity carries out is named rather than filtered away, because "not in
this process" and "not found" are different answers.
"""

from __future__ import annotations

import pytest
from rdflib import Graph

from airiskkg.assessment_runner import PAIR, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.workbench.process_risk import process_risk
from airiskkg.workbench.risk_view import group_findings, risk_view
from conftest import AGENT_NS, ONYX_NS, TARIFF_NS, example_path, process_path

pytestmark = pytest.mark.ui


def _scene(namespace: str, process: str) -> str:
    return "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in (example_path(namespace), process_path(process))
    )


def _by_process(ttl: str) -> dict:
    result = run_assessment_from_text(ttl)
    summary = summarize_result(result)
    return risk_view(summary, result.combined_graph, result=result)["byProcess"]


@pytest.fixture(scope="module")
def tariff() -> dict:
    return _by_process(_scene(TARIFF_NS, "energy_tariff_change"))


def test_a_capability_is_named_once_with_the_work_it_carries(tariff) -> None:
    agent = next(row for row in tariff["systems"] if len(row["activities"]) > 1)
    assert len(agent["activities"]) == 3, "the conversation agent carries three activities"
    labels = [row["label"] for row in tariff["systems"]]
    assert len(labels) == len(set(labels)), f"a capability was listed twice: {labels}"


def test_the_count_is_concerns_and_not_the_attribution_sum(tariff) -> None:
    """Ten concerns must not read as thirty because one agent carries three steps."""
    keys = {c["key"] for row in tariff["systems"] for c in row["concerns"]}
    assert len(keys) == tariff["summary"]["inProcess"] == tariff["summary"]["concerns"]
    # Listing the same step three times is the bug; listing one concern under
    # the two capabilities it genuinely cites is not, and it is marked.
    listed = sum(len(row["concerns"]) for row in tariff["systems"])
    assert listed == tariff["summary"]["listed"]
    assert listed - len(keys) == tariff["summary"]["spanning"]


def test_a_concern_reaching_two_capabilities_says_so(tariff) -> None:
    """Otherwise the card counts do not add up to the total and nothing explains why."""
    spanning = [c for row in tariff["systems"] for c in row["concerns"] if c["spans"]]
    assert len(spanning) == tariff["summary"]["spanning"] * 2 or not spanning
    for concern in spanning:
        assert concern["spans"], f"{concern['label']} is listed twice and says nothing about it"


def test_a_capability_with_nothing_found_is_still_listed(tariff) -> None:
    """On a page shown to stakeholders, "we looked and found nothing represented
    here" is half the message."""
    clean = [row for row in tariff["systems"] if not row["concerns"]]
    assert clean, "two of the four capabilities raise nothing, and both belong on the page"
    assert tariff["summary"]["aiSystems"] > tariff["summary"]["withConcerns"]


def test_every_concern_says_where_it_sits(tariff) -> None:
    """Two concerns can carry the same name at different places; without the
    evidence beside them the page reads as if it repeated itself."""
    for row in tariff["systems"]:
        for concern in row["concerns"]:
            assert concern["evidence"], f"{concern['label']} is listed with no place"


def test_a_capability_no_activity_carries_out_is_named_not_dropped() -> None:
    """Filtered off the diagram, never out of the assessment."""
    scene = _scene(TARIFF_NS, "energy_tariff_change")
    graph = Graph().parse(data=scene, format="turtle")
    # The conversation agent: the one whose concerns cite only its own elements.
    dropped = None
    for activity, system in list(graph.subject_objects(PAIR.refinedBy)):
        if str(system).endswith("ConversationAgent"):
            graph.remove((activity, PAIR.refinedBy, system))
            dropped = system
    assert dropped is not None, "the scene no longer refines the conversation agent"

    by_process = _by_process(graph.serialize(format="turtle"))
    assert by_process["offProcess"], "a concern in an uncalled architecture vanished"
    assert by_process["summary"]["offProcess"] == len(by_process["offProcess"])
    assert all(row["systems"] for row in by_process["offProcess"]), (
        "an off-process concern has to say which architecture holds it"
    )
    # Still counted against the whole run, so nothing is quietly lost.
    accounted = by_process["summary"]["inProcess"] + by_process["summary"]["offProcess"]
    assert accounted == by_process["summary"]["concerns"]


def test_a_graph_with_no_process_says_so_rather_than_showing_an_empty_page() -> None:
    architecture = example_path(ONYX_NS).read_text(encoding="utf-8")
    by_process = _by_process(architecture)
    assert by_process["present"] is False
    assert by_process["systems"] == []


def test_the_agentic_scene_places_its_one_capability(tmp_path) -> None:
    by_process = _by_process(_scene(AGENT_NS, "it_service_desk"))
    assert by_process["present"]
    assert len(by_process["systems"]) == 1
    only = by_process["systems"][0]
    assert [a["label"] for a in only["activities"]] == ["Triage and resolve the request"]
    assert only["activities"][0]["participant"] == "Northwind IT"
    assert only["activities"][0]["lane"] == "Automated"


def test_placing_concerns_on_the_work_reads_the_same_concerns() -> None:
    """The overview is a reading of the run, and reads exactly what the run said."""
    scene = _scene(TARIFF_NS, "energy_tariff_change")
    result = run_assessment_from_text(scene)
    summary = summarize_result(result)
    groups = group_findings(summary["findings"])
    placed = process_risk(result.combined_graph, groups)
    seen = {c["key"] for row in placed["systems"] for c in row["concerns"]}
    seen |= {c["key"] for c in placed["offProcess"]}
    assert seen == {group["key"] for group in groups}
