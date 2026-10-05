"""Tests for the SHACL architecture-graph input contract (Rule R4)."""

import sys
from pathlib import Path

from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "scripts"))

from validate_graphs import SHAPES_PATH, _load_ontology_graph, validate_graph  # noqa: E402

from conftest import FIXTURE_DIR  # noqa: E402

from airiskkg.paths import EXAMPLE_DIR  # noqa: E402


def _shapes() -> Graph:
    shapes = Graph()
    shapes.parse(SHAPES_PATH, format="turtle")
    return shapes


def _tracked_graphs() -> list[Path]:
    """Every architecture graph the repository ships, offered or kept for a test."""
    return sorted(EXAMPLE_DIR.glob("*.ttl")) + sorted(FIXTURE_DIR.glob("*.ttl"))


def test_example_graphs_have_no_violations() -> None:
    shapes = _shapes()
    ont = _load_ontology_graph()
    graphs = _tracked_graphs()
    assert graphs, "no architecture graphs found to validate"
    for graph_path in graphs:
        ok, violations, _warnings, results_text = validate_graph(graph_path, shapes, ont)
        assert ok, f"{graph_path.name} has {violations} violation(s):\n{results_text}"


def test_graph_without_system_is_rejected(tmp_path: Path) -> None:
    graph_path = tmp_path / "no_system.ttl"
    graph_path.write_text(
        """
        @prefix beam: <http://w3id.org/beam/core#> .
        @prefix ex:   <http://example.org/> .
        ex:step a beam:Process ; beam:use ex:input .
        ex:input a beam:Data .
        """,
        encoding="utf-8",
    )
    ok, violations, _warnings, _text = validate_graph(graph_path, _shapes(), _load_ontology_graph())
    assert not ok
    assert violations >= 1


def test_process_without_flow_is_rejected(tmp_path: Path) -> None:
    graph_path = tmp_path / "dangling_process.ttl"
    graph_path.write_text(
        """
        @prefix beam: <http://w3id.org/beam/core#> .
        @prefix ex:   <http://example.org/> .
        ex:system a beam:System .
        ex:step a beam:Process .
        """,
        encoding="utf-8",
    )
    ok, violations, _warnings, _text = validate_graph(graph_path, _shapes(), _load_ontology_graph())
    assert not ok
    assert violations >= 1


# A well-formed graph the malformed cases below are grafted onto, so each case
# differs from an accepted graph by exactly the one edge under test.
_WELL_FORMED = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix ex:   <http://example.org/contract#> .
ex:sys a beam:System ; beam:hasProcess ex:step ; beam:hasResource ex:a , ex:b .
ex:step a beam:Process ; pair:playsRole pair:GenerationStep ;
    beam:use ex:a ; beam:produce ex:b .
ex:a a beam:Data ; pair:playsRole pair:UserInput .
ex:b a beam:Data ; pair:playsRole pair:LLMResponse .
"""

_MALFORMED_EDGES = {
    "data uses data": "ex:a beam:use ex:b .",
    "data produces data": "ex:a beam:produce ex:b .",
    "data uses a symbol": "ex:sym a beam:Symbol . ex:a beam:use ex:sym .",
    "a symbol produces data": "ex:sym a beam:Symbol . ex:sym beam:produce ex:a .",
    "model uses model": "ex:m a beam:Model . ex:n a beam:Model . ex:m beam:use ex:n .",
    # A process reaching a process is the same defect as data reaching data,
    # and BEAM no longer declares a predicate that could say it.
    "a process reaches a process directly":
        "ex:later a beam:Process ; beam:produce ex:c . ex:c a beam:Data ."
        " ex:step beam:inform ex:later .",
    # An agent and a system are siblings of beam:Resource, not kinds of it.
    "a process uses an agent": "ex:who a beam:Agent . ex:step beam:use ex:who .",
    "a process uses a system": "ex:step beam:use ex:sys .",
    "an agent stands in for a resource": "ex:who a beam:Agent . ex:who beam:usedBy ex:step .",
    "one element is both kinds": "ex:both a beam:Process , beam:Data ; beam:use ex:a .",
}


def test_an_edge_between_two_resources_is_rejected(tmp_path: Path) -> None:
    """Flow joins a process to a resource. BEAM states the domain and range, but
    no reasoner runs, so only a shape rejects a data-to-data edge."""
    shapes, ont = _shapes(), _load_ontology_graph()

    baseline = tmp_path / "well_formed.ttl"
    baseline.write_text(_WELL_FORMED, encoding="utf-8")
    ok, violations, _warnings, text = validate_graph(baseline, shapes, ont)
    assert ok, f"the baseline these cases are grafted onto must conform:\n{text}"

    for name, edge in _MALFORMED_EDGES.items():
        path = tmp_path / (name.replace(" ", "_") + ".ttl")
        path.write_text(_WELL_FORMED + edge, encoding="utf-8")
        ok, violations, _warnings, _text = validate_graph(path, shapes, ont)
        assert not ok and violations >= 1, f"accepted a malformed edge: {name}"


def test_the_contract_accepts_the_edges_beam_does_declare(tmp_path: Path) -> None:
    """The counterpart: an agent reaches a process, and a resource names the
    process that reads it. Rejecting these would be the shapes overreaching."""
    for name, edge in {
        "an agent participates in a process":
            "ex:who a beam:Agent . ex:who beam:participatedIn ex:step .",
        "a resource names the process that uses it": "ex:a beam:usedBy ex:step .",
        "a resource names the process that produced it": "ex:b beam:producedBy ex:step .",
        "a process reaches a process through the box between them":
            "ex:later a beam:Process ; beam:use ex:b ; beam:produce ex:c ."
            " ex:c a beam:Data .",
    }.items():
        path = tmp_path / (name.replace(" ", "_") + ".ttl")
        path.write_text(_WELL_FORMED + edge, encoding="utf-8")
        ok, _violations, _warnings, text = validate_graph(path, _shapes(), _load_ontology_graph())
        assert ok, f"rejected a well-formed edge ({name}):\n{text}"
