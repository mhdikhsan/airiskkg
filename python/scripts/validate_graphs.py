"""Validate architecture instance graphs against the PAIR-AI SHACL input contract.

Usage:
    python python/scripts/validate_graphs.py <graph.ttl> [<graph2.ttl> ...]
    python python/scripts/validate_graphs.py          # validates ontology/example/*.ttl

The contract (shacl/architecture_input_contract.ttl) operationalizes Rule R4:
it makes explicit what the submitted graph must represent for candidate risk
findings to be meaningful. Violations fail (exit code 1); Warnings are
reported but do not fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.paths import CORE_DIR, EXAMPLE_DIR, REPO_ROOT  # noqa: E402

SH = Namespace("http://www.w3.org/ns/shacl#")
SHAPES_PATH = REPO_ROOT / "shacl" / "architecture_input_contract.ttl"


def _load_ontology_graph() -> Graph:
    """Class hierarchy needed by the leaf-type check (rdfs:subClassOf paths)."""
    ont = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        ont.parse(CORE_DIR / name, format="turtle")
    return ont


def validate_graph(graph_path: Path, shapes: Graph, ont: Graph) -> tuple[bool, int, int, str]:
    data = Graph()
    data.parse(graph_path, format="turtle")
    conforms, results_graph, results_text = validate(
        data_graph=data,
        shacl_graph=shapes,
        ont_graph=ont,
        advanced=True,
        inference="none",
    )
    violations = 0
    warnings = 0
    for result in results_graph.subjects(SH.resultSeverity, SH.Violation):
        violations += 1
    for result in results_graph.subjects(SH.resultSeverity, SH.Warning):
        warnings += 1
    return violations == 0, violations, warnings, results_text


def main(argv: list[str]) -> int:
    graph_paths = [Path(arg) for arg in argv]
    if not graph_paths:
        graph_paths = sorted(EXAMPLE_DIR.glob("*.ttl"))
    if not graph_paths:
        print("No instance graphs to validate.")
        return 1

    shapes = Graph()
    shapes.parse(SHAPES_PATH, format="turtle")
    ont = _load_ontology_graph()

    exit_code = 0
    for graph_path in graph_paths:
        if not graph_path.is_absolute():
            graph_path = REPO_ROOT / graph_path
        ok, violations, warnings, results_text = validate_graph(graph_path, shapes, ont)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {graph_path}  (violations: {violations}, warnings: {warnings})")
        if violations or warnings:
            print(results_text)
        if not ok:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
