import pytest
from rdflib import RDF, Graph

from airiskkg.architecture_builder import APP, BuilderError, build_graph, build_ttl
from airiskkg.assessment_runner import BEAM, PAIR, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.paths import EXAMPLE_DIR

flask = pytest.importorskip("flask")
from airiskkg.webapp import create_app  # noqa: E402


STARTER_MODEL = {
    "systemName": "DemoSystem",
    "systemLabel": "Demo RAG system",
    "resources": [
        {
            "name": "UserQuestion",
            "label": "User question",
            "class": str(BEAM.Data),
            "roles": [str(PAIR.PublicUserInput)],
            "dataCategories": [str(PAIR.ExternalUserContent)],
        },
        {
            "name": "VectorDB",
            "label": "Vector store",
            "class": str(BEAM.Data),
            "roles": [str(PAIR.VectorStore)],
            "dataCategories": [str(PAIR.SensitiveInformation)],
        },
        {
            "name": "RetrievedContext",
            "class": str(BEAM.Data),
            "roles": [str(PAIR.RetrievedResult)],
            "dataCategories": [str(PAIR.UntrustedContent)],
        },
    ],
    "processes": [
        {
            "name": "Retrieval",
            "class": str(BEAM.Infer),
            "roles": [str(PAIR.RetrievalStep)],
            "use": ["UserQuestion", "VectorDB"],
            "produce": ["RetrievedContext"],
            "inform": [],
        }
    ],
}


@pytest.fixture()
def client():
    return create_app().test_client()


def test_build_graph_creates_system_and_edges():
    graph = build_graph(STARTER_MODEL)
    system = APP.DemoSystem
    assert (system, RDF.type, BEAM.System) in graph
    assert (system, BEAM.hasResource, APP.UserQuestion) in graph
    assert (system, BEAM.hasProcess, APP.Retrieval) in graph
    assert (APP.Retrieval, BEAM.use, APP.VectorDB) in graph
    assert (APP.Retrieval, BEAM.produce, APP.RetrievedContext) in graph
    assert (APP.UserQuestion, PAIR.playsRole, PAIR.PublicUserInput) in graph


def test_build_graph_rejects_unknown_edge_target():
    bad = {
        "resources": [{"name": "A", "class": str(BEAM.Data)}],
        "processes": [{"name": "P", "class": str(BEAM.Infer), "use": ["DoesNotExist"]}],
    }
    with pytest.raises(BuilderError):
        build_graph(bad)


def test_build_graph_rejects_empty_model():
    with pytest.raises(BuilderError):
        build_graph({"resources": [], "processes": []})


def test_generated_ttl_is_parseable_and_assessable():
    ttl = build_ttl(STARTER_MODEL)
    Graph().parse(data=ttl, format="turtle")  # parses cleanly
    result = run_assessment_from_text(ttl)
    assert result.motif_match_count > 0
    assert result.risk_finding_count > 0


def test_summarize_result_shape():
    ttl = (EXAMPLE_DIR / "uc6.ttl").read_text(encoding="utf-8")
    summary = summarize_result(run_assessment_from_text(ttl))
    assert summary["summary"]["riskFindingCount"] == len(summary["findings"])
    first = summary["findings"][0]
    assert first["label"]
    assert first["taxonomyEntries"]
    # taxonomy entries carry a readable label and a source grouping
    assert all(entry["label"] and entry["source"] for entry in first["taxonomyEntries"])


def test_vocabulary_endpoint(client):
    data = client.get("/api/vocabulary").get_json()
    assert data["roles"] and data["dataCategories"]
    assert any(r["label"] == "Vector Store" for r in data["roles"])
    assert data["resourceClasses"] and data["processClasses"]


def test_examples_endpoint_lists_and_returns_ttl(client):
    listed = client.get("/api/examples").get_json()
    names = {item["name"] for item in listed}
    assert "uc6" in names
    detail = client.get("/api/examples/uc6").get_json()
    assert "beam:System" in detail["ttl"] or "a beam:System" in detail["ttl"]


def test_example_endpoint_rejects_traversal(client):
    assert client.get("/api/examples/..%2f..%2fpyproject").status_code == 404


def test_build_endpoint(client):
    res = client.post("/api/build", json=STARTER_MODEL)
    assert res.status_code == 200
    assert "beam:System" in res.get_json()["ttl"]


def test_assess_endpoint_returns_findings(client):
    ttl = (EXAMPLE_DIR / "uc6.ttl").read_text(encoding="utf-8")
    res = client.post("/api/assess", json={"ttl": ttl})
    assert res.status_code == 200
    data = res.get_json()
    assert data["summary"]["riskFindingCount"] > 0
    assert data["findings"]


def test_assess_endpoint_requires_ttl(client):
    assert client.post("/api/assess", json={"ttl": ""}).status_code == 400


def test_assess_endpoint_reports_parse_error(client):
    res = client.post("/api/assess", json={"ttl": "this is not turtle @@@"})
    assert res.status_code == 400
    assert "error" in res.get_json()
