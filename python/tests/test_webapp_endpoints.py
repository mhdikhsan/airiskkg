"""Endpoint tests for the workbench webapp (live preview + validation)."""

import pytest

flask = pytest.importorskip("flask")

from airiskkg.paths import EXAMPLE_DIR, REPO_ROOT  # noqa: E402
from airiskkg.webapp.app import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_graph_endpoint_returns_nodes_and_edges(client) -> None:
    ttl = (EXAMPLE_DIR / "onyx_danswer.ttl").read_text(encoding="utf-8")
    response = client.post("/api/graph", json={"ttl": ttl})
    assert response.status_code == 200
    data = response.get_json()
    assert data["stats"]["nodes"] > 0
    assert data["stats"]["edges"] > 0
    assert data["systems"], "system entry expected"
    kinds = {node["kind"] for node in data["nodes"]}
    assert {"process", "data", "model"} <= kinds
    node_ids = {node["id"] for node in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids


def test_graph_endpoint_use_edges_point_into_process(client) -> None:
    ttl = """
    @prefix beam: <http://w3id.org/beam/core#> .
    @prefix ex: <http://example.org/> .
    ex:S a beam:System .
    ex:Step a beam:Infer ; beam:use ex:In ; beam:produce ex:Out .
    ex:In a beam:Data . ex:Out a beam:Data .
    """
    data = client.post("/api/graph", json={"ttl": ttl}).get_json()
    edges = {(e["kind"], e["source"].split("/")[-1], e["target"].split("/")[-1]) for e in data["edges"]}
    assert ("use", "In", "Step") in edges       # drawn resource -> process
    assert ("produce", "Step", "Out") in edges  # drawn process -> resource


def test_graph_endpoint_reports_parse_error(client) -> None:
    response = client.post("/api/graph", json={"ttl": "@prefix broken <"})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_graph_endpoint_empty_ttl_is_empty_graph(client) -> None:
    response = client.post("/api/graph", json={"ttl": "   "})
    assert response.status_code == 200
    assert response.get_json()["stats"] == {"nodes": 0, "edges": 0}


def test_validate_endpoint_reports_contract(client) -> None:
    ttl = (EXAMPLE_DIR / "uc6.ttl").read_text(encoding="utf-8")
    response = client.post("/api/validate", json={"ttl": ttl})
    assert response.status_code == 200
    report = response.get_json()
    assert report["conforms"] is True
    assert report["violations"] == []

    broken = """
    @prefix beam: <http://w3id.org/beam/core#> .
    @prefix ex: <http://example.org/> .
    ex:Step a beam:Process .
    """
    report = client.post("/api/validate", json={"ttl": broken}).get_json()
    assert report["conforms"] is False
    assert report["violations"]


def test_assess_endpoint_still_works(client) -> None:
    ttl = (EXAMPLE_DIR / "uc6.ttl").read_text(encoding="utf-8")
    response = client.post("/api/assess", json={"ttl": ttl})
    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["riskFindingCount"] > 0


def test_import_t4b_endpoint_normalizes_sample_export(client) -> None:
    sample = (REPO_ROOT / "external" / "tool4boxology" / "sample_export.nt").read_text(encoding="utf-8")
    response = client.post("/api/import/t4b", json={"data": sample, "format": "nt"})
    assert response.status_code == 200
    data = response.get_json()
    assert "beam:System" in data["ttl"]
    assert "beam:use" in data["ttl"] or "beam:produce" in data["ttl"]
    assert data["warnings"]


def test_import_t4b_endpoint_rejects_empty_input(client) -> None:
    response = client.post("/api/import/t4b", json={"data": "  "})
    assert response.status_code == 400


def test_import_t4b_endpoint_reports_bad_input(client) -> None:
    response = client.post("/api/import/t4b", json={"data": "not a triple at all", "format": "nt"})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_vocabulary_roles_are_grouped_by_top_level_role(client) -> None:
    """Every pattern role carries the label of its top-level ancestor as `group`
    so the UI can render <optgroup> headings. Groups come from the ontology
    (roles with no pair:subRoleOf parent), never a hardcoded list."""
    response = client.get("/api/vocabulary")
    assert response.status_code == 200
    data = response.get_json()

    roles = data["roles"]
    assert roles, "roles expected"
    # every role is selectable and grouped
    assert all(role.get("group") for role in roles), "every role needs a group"
    assert len({role["id"] for role in roles}) == len(roles), "role ids unique"

    # groups are the ontology's top-level roles, which are their own group
    groups = {role["group"] for role in roles}
    by_id = {role["id"]: role for role in roles}
    for top in ("ProcessingStep", "ControlStep", "ResourceRole", "UserInput"):
        uri = f"http://w3id.org/airiskkg/pair-ai#{top}"
        assert by_id[uri]["group"] == by_id[uri]["label"]
        assert by_id[uri]["label"] in groups

    # a role with several parents still resolves to a single group
    external_model = by_id["http://w3id.org/airiskkg/pair-ai#ExternalModel"]
    assert external_model["group"] == "Resource Role"

    # data categories stay ungrouped so their dropdown is unaffected
    assert not any("group" in category for category in data["dataCategories"])


def test_vocabulary_roles_declare_which_element_kind_they_apply_to(client) -> None:
    """Roles carry `applies` ("process" / "resource") so the picker can offer the
    ones that fit the selected element. Derived from each role family's
    expectedClass, so process families never leak into resource families."""
    data = client.get("/api/vocabulary").get_json()
    roles = data["roles"]
    assert all(role.get("applies") in {"process", "resource"} for role in roles)

    by_group: dict[str, set[str]] = {}
    for role in roles:
        by_group.setdefault(role["group"], set()).add(role["applies"])
    # a family is process or resource, never both
    assert all(len(kinds) == 1 for kinds in by_group.values()), by_group
    assert by_group["Processing Step"] == {"process"}
    assert by_group["Control Step"] == {"process"}
    assert by_group["Resource Role"] == {"resource"}


def _rag_with_guardrails_ttl() -> str:
    return (EXAMPLE_DIR / "rag_with_guardrails.ttl").read_text(encoding="utf-8")


def test_assess_reports_why_a_near_miss_motif_did_not_match(client) -> None:
    """Unwiring the retrieval step from the user query drops RAG and Vector-based
    IR; the gap report names the missing edge instead of failing silently."""
    ttl = _rag_with_guardrails_ttl()
    broken = ttl.replace(
        "    beam:use local:userQuery ;\n    beam:use local:vectorStore ;",
        "    beam:use local:vectorStore ;",
    )
    assert broken != ttl, "fixture no longer matches the example"

    data = client.post("/api/assess", json={"ttl": broken}).get_json()
    matched = {m["motif"]["label"] for m in data["motifMatches"]}
    assert not any("Retrieval Augmented" in label for label in matched)

    gaps = {gap["label"]: gap for gap in data["motifGaps"]}
    rag = next(gap for label, gap in gaps.items() if "Retrieval Augmented" in label)
    assert rag["satisfied"] < rag["total"]
    missing = " | ".join(edge["text"] for edge in rag["missingEdges"])
    assert "Retrieval Step" in missing and "User Input" in missing


def test_assess_gaps_exclude_motifs_that_matched(client) -> None:
    """A motif that matched is reported as a match, never as a gap."""
    data = client.post("/api/assess", json={"ttl": _rag_with_guardrails_ttl()}).get_json()
    matched = {m["motif"]["label"] for m in data["motifMatches"]}
    assert matched, "expected the example to match motifs"
    gap_labels = {gap["label"] for gap in data["motifGaps"]}
    assert not (matched & gap_labels)


def test_assess_gap_candidates_are_elements_of_the_submitted_graph(client) -> None:
    """Suggested candidates are real elements with the right type but no role, so
    the UI can highlight them."""
    ttl = _rag_with_guardrails_ttl().replace(
        "    pair:playsRole pair:VectorStore .", "."
    )
    data = client.post("/api/assess", json={"ttl": ttl}).get_json()
    candidates = [
        candidate
        for gap in data["motifGaps"]
        for node in gap["missingNodes"]
        for candidate in node["candidates"]
    ]
    assert candidates, "expected candidate elements for the untagged vector store"
    assert all(candidate["id"].startswith("http") for candidate in candidates)
