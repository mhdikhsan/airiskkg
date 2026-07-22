"""Tests for the SHACL architecture-graph input contract (Rule R4)."""

import sys
from pathlib import Path

from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "scripts"))

from validate_graphs import SHAPES_PATH, _load_ontology_graph, validate_graph  # noqa: E402

from airiskkg.paths import EXAMPLE_DIR  # noqa: E402


def _shapes() -> Graph:
    shapes = Graph()
    shapes.parse(SHAPES_PATH, format="turtle")
    return shapes


def test_example_graphs_have_no_violations() -> None:
    shapes = _shapes()
    ont = _load_ontology_graph()
    for graph_path in sorted(EXAMPLE_DIR.glob("*.ttl")):
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
