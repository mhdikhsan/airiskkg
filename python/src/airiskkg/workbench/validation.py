from __future__ import annotations

from functools import lru_cache

from rdflib import Graph, URIRef

from airiskkg.paths import CORE_DIR, SHACL_DIR

_SH = "http://www.w3.org/ns/shacl#"


def _sh(term: str) -> URIRef:
    return URIRef(_SH + term)


@lru_cache(maxsize=1)
def guidance_shape_ids() -> frozenset[str]:
    """Which shapes come from annotation_guidance.ttl rather than the contract.

    The two files answer different questions and the report merges them, so a
    reader cannot tell them apart afterwards. That matters for anything that
    acts on the result: the contract's "type this to a leaf class" warning
    fires on every plain beam:Data and is not a statement about anyone's
    annotation, while the guidance shapes are exactly that."""
    guidance = Graph()
    guidance.parse(SHACL_DIR / "annotation_guidance.ttl", format="turtle")
    return frozenset(str(s) for s in set(guidance.subjects()))


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
    _conforms, results_graph, _text = shacl_validate(
        data_graph=data + ontology,
        shacl_graph=shapes,
        advanced=True,
        inference="none",
    )

    def collect(severity: URIRef) -> list[dict]:
        items = []
        guidance = guidance_shape_ids()
        for result in results_graph.subjects(_sh("resultSeverity"), severity):
            message = results_graph.value(result, _sh("resultMessage"))
            focus = results_graph.value(result, _sh("focusNode"))
            shape = results_graph.value(result, _sh("sourceShape"))
            items.append(
                {
                    "message": str(message) if message else "Constraint violated.",
                    "focusNode": str(focus) if focus else None,
                    # Says which of the two questions this answers, so a caller
                    # can act on one without acting on the other.
                    "guidance": str(shape) in guidance if shape is not None else False,
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
