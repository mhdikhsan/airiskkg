"""Validating a submitted graph against the architecture input contract, and
shaping the report into the three severities the UI shows.

Two shapes files ride together here: `architecture_input_contract.ttl` asks
whether the graph is acceptable at all, and `annotation_guidance.ttl` asks
whether the annotation will actually match anything. Guidance is always Info or
Warning and never Violation, so it can never change whether a graph conforms.
"""

from __future__ import annotations

from functools import lru_cache

from rdflib import Graph, URIRef

from airiskkg.paths import CORE_DIR, SHACL_DIR

_SH = "http://www.w3.org/ns/shacl#"


def _sh(term: str) -> URIRef:
    return URIRef(_SH + term)


@lru_cache(maxsize=1)
def shapes_and_ontology() -> tuple[Graph, Graph]:
    shapes = Graph()
    shapes.parse(SHACL_DIR / "architecture_input_contract.ttl", format="turtle")
    shapes.parse(SHACL_DIR / "annotation_guidance.ttl", format="turtle")
    ontology = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        ontology.parse(CORE_DIR / name, format="turtle")
    return shapes, ontology


def shacl_report(ttl: str) -> dict:
    """Validate Turtle against the architecture input contract (Rule R4)."""
    from pyshacl import validate as shacl_validate

    data = Graph()
    data.parse(data=ttl, format="turtle")
    shapes, ontology = shapes_and_ontology()
    # The ontology is merged into the data graph, not passed as ont_graph. The
    # guidance shapes walk pair:subRoleOf* inside sh:sparql constraints, and
    # those constraints only see the data graph: with ont_graph the role
    # hierarchy is invisible to them and every Info-level hint silently
    # disappears (onyx_danswer drops from 8 hints to 0).
    _conforms, results_graph, _text = shacl_validate(
        data_graph=data + ontology,
        shacl_graph=shapes,
        advanced=True,
        inference="none",
    )

    def collect(severity: URIRef) -> list[dict]:
        items = []
        for result in results_graph.subjects(_sh("resultSeverity"), severity):
            message = results_graph.value(result, _sh("resultMessage"))
            focus = results_graph.value(result, _sh("focusNode"))
            items.append(
                {
                    "message": str(message) if message else "Constraint violated.",
                    "focusNode": str(focus) if focus else None,
                }
            )
        return sorted(items, key=lambda item: (item["focusNode"] or "", item["message"]))

    violations = collect(_sh("Violation"))
    warnings = collect(_sh("Warning"))
    hints = collect(_sh("Info"))
    return {
        "conforms": not violations,
        "violations": violations,
        "warnings": warnings,
        "hints": hints,
    }
