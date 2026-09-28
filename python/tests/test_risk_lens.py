"""A risk defined first, and only the design that bears on it.

The scene is the tariff change: four systems, a customer conversation agent,
and a process in which the customer's chat message is classified personal. The
lens under test is the one a service owner would actually ask for - sensitive
data in the conversation agent.

The property that makes the lens worth having is the split between a concern
that is *about* the risk and one that merely *passes through* it. Every one of
the agent's findings touches an element carrying sensitive data, because the
chat message carries it and feeds everything; a filter on that returns the
whole list. What a risk query actually tests is what separates them.
"""

from __future__ import annotations

import pytest
from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import PAIR, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.workbench.risk_lens import _categories_tested, lens_risks
from airiskkg.workbench.risk_view import risk_view
from conftest import TARIFF_NS, example_path, process_path

pytestmark = pytest.mark.ui

BEAMR = Namespace("http://w3id.org/beam/risk#")
SENSITIVE = str(PAIR.SensitiveInformation)
AGENT = TARIFF_NS + "ConversationAgent"


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


def _define(client, ttl: str, **criteria) -> tuple[str, str]:
    body = client.post("/api/scope-edit", json={
        "ttl": ttl, "op": "define-risk", "label": criteria.pop("label", "A defined risk"),
        **criteria,
    }).get_json()
    assert "error" not in body, body
    return body["ttl"], body["newId"]


def _run(ttl: str) -> tuple[dict, dict]:
    result = run_assessment_from_text(ttl)
    summary = summarize_result(result)
    return summary, risk_view(summary, result.combined_graph, result=result)


@pytest.fixture(scope="module")
def sensitive_in_agent(client, scene):
    """The lens a service owner would ask for, run once for every test here."""
    ttl, made = _define(client, scene, label="Sensitive data in the conversation agent",
                        dataCategory=SENSITIVE, system=AGENT)
    summary, view = _run(ttl)
    lens = next(lens for lens in view["lenses"] if lens["risk"]["id"] == made)
    return {"ttl": ttl, "summary": summary, "view": view, "lens": lens}


# ---- only what bears on it ----


def test_every_architecture_point_says_why_it_is_there(sensitive_in_agent) -> None:
    lens = sensitive_in_agent["lens"]
    assert lens["architecture"], "the agent holds sensitive data, so the lens has points"
    for point in lens["architecture"]:
        assert point["why"], f"{point['label']} is on the view with no reason given"


def test_what_holds_the_content_is_only_what_holds_that_content(sensitive_in_agent) -> None:
    """Asking about sensitive data must not return every element carrying any
    information at all. The category's ancestors reach into what a query is
    about; they do not reach into what an element holds."""
    for point in sensitive_in_agent["lens"]["architecture"]:
        if point["kind"] != "data":
            continue
        assert "carries Sensitive Information" in point["why"], (
            f"{point['label']} is on a sensitive-data lens for another reason: {point['why']}"
        )


def test_the_lens_stays_inside_the_system_it_names(sensitive_in_agent) -> None:
    from airiskkg.graph_view import _members_of

    graph = Graph().parse(data=sensitive_in_agent["ttl"], format="turtle")
    members = {str(m) for m in _members_of(graph, URIRef(AGENT))}
    for point in sensitive_in_agent["lens"]["architecture"]:
        assert point["id"] in members, f"{point['label']} is outside the conversation agent"


def test_the_process_side_is_the_work_that_system_carries_out(sensitive_in_agent) -> None:
    process = sensitive_in_agent["lens"]["process"]
    activities = [p for p in process if p["kind"] == "activity"]
    assert activities, "the agent carries out activities, and they belong on the lens"
    assert all("carried out by" in a["why"] for a in activities)
    # The fact stated on the business side, which is how the data got its category.
    assert any(p["kind"] == "data object" and "PersonalData" in p["why"] for p in process), (
        "the personal-data classification on the process is where this risk starts"
    )


def test_an_activity_bears_on_what_its_architecture_raised(sensitive_in_agent) -> None:
    """Picking a concern has to light the work it arises in. An activity bears on
    a concern when the system refining it holds that concern's evidence - so
    none of the process column is left unconnected to what it carries out."""
    lens = sensitive_in_agent["lens"]
    about = {c["key"] for c in lens["about"]}
    for point in lens["process"]:
        if point["kind"] == "activity":
            assert point["concerns"], f"{point['label']} bears on nothing it carries out"
        assert set(point["concerns"]) <= about, "a link to a concern the view does not draw"


def test_a_data_object_bears_only_on_what_its_classification_seeded(sensitive_in_agent) -> None:
    """Exact, not by adjacency: the classification is derived onto architecture
    elements, and only a risk pattern whose query tests that category is about
    it. Linking a data object to every concern of its activity would say the
    process is behind a prompt injection it said nothing about."""
    lens = sensitive_in_agent["lens"]
    by_key = {g["key"]: g for g in sensitive_in_agent["view"]["groups"]}
    tested = _categories_tested()
    classified = [p for p in lens["process"]
                  if p["kind"] == "data object" and "PersonalData" in p["why"]]
    assert classified and any(p["concerns"] for p in classified), (
        "the personal-data classification reaches a concern through the derivation trail"
    )
    for point in classified:
        for key in point["concerns"]:
            pattern = by_key[key]["riskPattern"]["id"]
            assert "SensitiveInformation" in tested[pattern], (
                f"{point['label']} is linked to {by_key[key]['label']}, whose query "
                "never tests the category it seeded"
            )
    for point in lens["process"]:
        if point["kind"] == "data object" and "no classification stated" in point["why"]:
            assert not point["concerns"], "an unclassified data object seeded nothing"


# ---- about it, or only passing through ----


def test_about_is_what_the_query_tests_not_what_the_evidence_touches(sensitive_in_agent) -> None:
    lens = sensitive_in_agent["lens"]
    assert lens["about"], "sensitive information disclosure is raised in the agent"
    assert lens["passesThrough"], (
        "every finding touches the chat message; if none only passed through, the "
        "split is not being made at all"
    )
    tested = _categories_tested()
    by_key = {g["key"]: g for g in sensitive_in_agent["view"]["groups"]}
    for concern in lens["about"]:
        pattern = by_key[concern["key"]]["riskPattern"]["id"]
        assert "SensitiveInformation" in tested[pattern], (
            f"{concern['label']} is marked about sensitive data, but its query never tests it"
        )
    for concern in lens["passesThrough"]:
        pattern = by_key[concern["key"]]["riskPattern"]["id"]
        assert "SensitiveInformation" not in tested[pattern]


def test_the_categories_a_query_tests_are_read_off_the_query(sensitive_in_agent) -> None:
    """Not curated: a registered query is the one exact statement of what a
    risk pattern reads, and a hand-kept list would drift from it."""
    tested = _categories_tested()
    disclosure = str(PAIR) .replace("pair-ai#", "") + "patterns#SensitiveInformationDisclosureRiskPattern"
    assert "SensitiveInformation" in tested[disclosure]
    injection = disclosure.replace("SensitiveInformationDisclosure", "PromptInjection")
    assert "UntrustedContent" in tested[injection]
    assert "SensitiveInformation" not in tested[injection]


def test_the_controls_are_for_what_is_about_it(sensitive_in_agent) -> None:
    lens = sensitive_in_agent["lens"]
    offered = {c for concern in lens["about"] for c in concern["controls"]}
    assert set(lens["controls"]) == offered, "a control for a passing-through concern leaked in"
    assert set(lens["buildable"]) <= set(lens["controls"])


# ---- narrowing, never gating ----


def test_defining_a_risk_changes_nothing_that_is_detected(client, scene, sensitive_in_agent) -> None:
    """The lens chooses what is shown. If it narrowed the run, "we did not look"
    and "it is not there" would be the same answer again."""
    plain, _ = _run(scene)
    assert {f["id"] for f in plain["findings"]} == {
        f["id"] for f in sensitive_in_agent["summary"]["findings"]
    }


def test_a_defined_risk_is_not_reconciled_as_a_sticky_note(sensitive_in_agent) -> None:
    """It names criteria, not an element, so there is nowhere for a finding to
    corroborate it - and reporting it as "stated, nothing fired" would be false."""
    reconciliation = sensitive_in_agent["view"]["reconciliation"]
    assert reconciliation["statedTotal"] == 0
    assert not reconciliation["statedOnly"]


def test_a_lens_on_a_system_alone_shows_that_system(client, scene) -> None:
    ttl, made = _define(client, scene, label="The eligibility service",
                        system=TARIFF_NS + "EligibilityService")
    _, view = _run(ttl)
    lens = next(l for l in view["lenses"] if l["risk"]["id"] == made)
    assert lens["architecture"], "a system-only lens shows what the system holds"
    assert all("part of" in p["why"] for p in lens["architecture"])


def test_a_lens_by_weakness_is_about_that_weakness_by_definition(client, scene) -> None:
    pattern = "http://w3id.org/airiskkg/patterns#PromptInjectionRiskPattern"
    ttl, made = _define(client, scene, label="Prompt injection anywhere", riskPattern=pattern)
    _, view = _run(ttl)
    lens = next(l for l in view["lenses"] if l["risk"]["id"] == made)
    by_key = {g["key"]: g for g in view["groups"]}
    assert lens["about"]
    assert all(by_key[c["key"]]["riskPattern"]["id"] == pattern for c in lens["about"])
    assert not lens["passesThrough"], "naming the weakness leaves nothing to pass through"


# ---- the edits ----


def test_a_risk_needs_something_to_look_outward_from(client, scene) -> None:
    body = client.post("/api/scope-edit", json={"ttl": scene, "op": "define-risk", "label": "x"})
    assert body.status_code == 400


def test_a_defined_risk_is_written_into_the_graph(client, scene) -> None:
    ttl, made = _define(client, scene, label="Sensitive data in the conversation agent",
                        dataCategory=SENSITIVE, system=AGENT)
    graph = Graph().parse(data=ttl, format="turtle")
    assert (URIRef(made), RDF.type, BEAMR.Risk) in graph
    assert [r["id"] for r in lens_risks(graph)] == [made]


def test_an_empty_name_is_never_written_as_the_word_none(client, scene) -> None:
    """Literal(None) is the string "None", and it reached the page as a person's name."""
    body = client.post("/api/scope-edit", json={
        "ttl": scene, "op": "set-scope", "desiredOutcome": "tariff changes", "statedBy": ""}).get_json()
    graph = Graph().parse(data=body["ttl"], format="turtle")
    assert not list(graph.objects(None, PAIR.statedBy))
    assert "None" not in {str(o) for o in graph.objects()}
