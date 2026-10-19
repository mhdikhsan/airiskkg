"""The tutorial's starter scenario, and an activity naming the steps that carry it out."""

from __future__ import annotations

import pytest
from rdflib import RDF, Graph, URIRef

from airiskkg.assessment_runner import PAIR, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.workbench.validation import shacl_report
from conftest import SUPPORT_CHATBOT_NS, example_path, process_path  # noqa: E402

CSP = "http://w3id.org/airiskkg/example/customer-support#"
CSA = SUPPORT_CHATBOT_NS
ANSWER_QUESTION = CSP + "AnswerQuestion"


def _scene() -> str:
    return "\n\n".join(path.read_text(encoding="utf-8")
                       for path in (example_path(CSA), process_path("customer_support")))


def _patterns(ttl: str) -> list[str]:
    graph = run_assessment_from_text(ttl).combined_graph
    return sorted(str(graph.value(f, PAIR.generatedByRiskPattern)).rsplit("#", 1)[-1].removesuffix("RiskPattern")
                  for f in graph.subjects(RDF.type, PAIR.RiskFinding))


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


def _edit(client, ttl: str, op: str, **payload) -> str:
    response = client.post("/api/process-edit", json={"ttl": ttl, "op": op, **payload})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["ttl"]


def _activity(client, ttl: str) -> dict:
    view = client.post("/api/process", json={"ttl": ttl}).get_json()
    return next(a for a in view["activities"] if a["id"] == ANSWER_QUESTION)


def test_the_starter_scene_raises_what_the_guide_says() -> None:
    """docs/user_guide.md section 2.7 lists these six, with a reason each."""
    assert _patterns(_scene()) == [
        "MisinformationFromWeakGrounding", "PromptInjection", "PromptInjection",
        "ProtectedDataToExternalModel", "SensitiveInformationDisclosure", "SupplyChainCompromise",
    ]


def test_the_process_changes_what_the_architecture_alone_raises() -> None:
    """Personal data is said by the process, and the agent's review clears output handling."""
    alone = _patterns(example_path(CSA).read_text(encoding="utf-8"))
    assert "ImproperOutputHandling" in alone
    assert "ProtectedDataToExternalModel" not in alone and "SensitiveInformationDisclosure" not in alone
    assert "ImproperOutputHandling" not in _patterns(_scene())


def test_the_starter_scene_is_well_formed_bpmn_and_a_valid_architecture() -> None:
    report = shacl_report(_scene())
    assert not report["violations"], report["violations"]
    assert not [row for row in report["warnings"] if row["process"]], report["warnings"]


def test_the_starter_follows_the_bpmn_naming_it_teaches() -> None:
    """Verb first and no articles, on every activity."""
    graph = Graph().parse(process_path("customer_support"), format="turtle")
    bp = "https://sBPMN.github.io/2.0/properties#name"
    tasks = [t for kind in ("task", "serviceTask", "userTask", "sendTask", "receiveTask")
             for t in graph.subjects(RDF.type, URIRef(f"https://sBPMN.github.io/2.0/classes#{kind}"))]
    assert len(tasks) >= 8
    for task in tasks:
        name = str(graph.value(task, URIRef(bp)))
        assert not {"a", "an", "the"} & set(name.lower().split()), name


def test_an_activity_names_the_steps_that_carry_it_out(client) -> None:
    scene = _scene()
    row = _activity(client, scene)
    assert row["steps"] == sorted(CSA + s for s in ("BuildPrompt", "FindPassages", "GenerateAnswer"))
    assert {o["id"] for o in row["stepOptions"]} == set(row["steps"]), "offers a step of another system"

    one = _edit(client, scene, "set-steps", activity=ANSWER_QUESTION, steps=[CSA + "FindPassages"])
    assert _activity(client, one)["steps"] == [CSA + "FindPassages"]
    refused = client.post("/api/process-edit", json={
        "ttl": scene, "op": "set-steps", "activity": ANSWER_QUESTION, "steps": [CSA + "Answer"]})
    assert refused.status_code == 400, "named a resource, or a step of no refined system, as a step"


def test_findings_go_under_the_activity_whose_steps_or_data_they_cite(client) -> None:
    """Named steps narrow what an activity carries; with none named, the whole system's."""
    scene = _scene()
    every = summarize_result(run_assessment_from_text(scene))
    narrowed = _edit(client, scene, "set-steps", activity=ANSWER_QUESTION, steps=[CSA + "FindPassages"])
    narrow = summarize_result(run_assessment_from_text(narrowed))

    def listed(summary) -> set[str]:
        row = next(r for r in summary["findingsByActivity"] if r["id"] == ANSWER_QUESTION)
        return {item["label"] for item in row["items"]}

    assert any("supply chain" in label.lower() for label in listed(every)), listed(every)
    assert len(listed(narrow)) < len(listed(every)), "naming one step did not narrow what the activity carries"
    assert not any("supply chain" in label.lower() for label in listed(narrow)), (
        "the model's supply chain is listed under an activity whose step and data never touch it")


def test_carrying_data_makes_the_elements_it_names(client) -> None:
    """A data object with no element gets one in the refined system, linked by realisedBy;
    with one step named, the step reads or writes it as the process does."""
    scene = _scene().replace("    pair:realisedBy csa:KnowledgeBase .", "    bp:name \"Knowledge base\" .")
    one = _edit(client, scene, "set-steps", activity=ANSWER_QUESTION, steps=[CSA + "FindPassages"])
    carried = client.post("/api/process-edit", json={"ttl": one, "op": "carry-data", "activity": ANSWER_QUESTION})
    assert carried.status_code == 200, carried.get_json()
    body = carried.get_json()
    graph = Graph().parse(data=body["ttl"], format="turtle")
    made = [URIRef(i) for i in body["newIds"]]
    assert len(made) == 1, "made an element for data that already names one"
    element = made[0]
    beam = "http://w3id.org/beam/core#"
    assert (URIRef(CSA + "SupportChatbot"), URIRef(beam + "hasResource"), element) in graph
    assert (URIRef(CSP + "KnowledgeBase"), PAIR.realisedBy, element) in graph
    assert (URIRef(CSA + "FindPassages"), URIRef(beam + "use"), element) in graph

    again = client.post("/api/process-edit", json={"ttl": body["ttl"], "op": "carry-data", "activity": ANSWER_QUESTION})
    assert again.status_code == 400, "carried the same data twice"


def test_a_new_system_drops_the_steps_of_the_old_one(client) -> None:
    scene = _scene()
    moved = _edit(client, scene, "set-refines", activity=ANSWER_QUESTION, system="")
    assert _activity(client, moved)["steps"] == []
