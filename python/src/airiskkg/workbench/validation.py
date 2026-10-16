from __future__ import annotations

from functools import lru_cache

from rdflib import RDFS, Graph, URIRef

from airiskkg.paths import CORE_DIR, SHACL_DIR

_SH = "http://www.w3.org/ns/shacl#"
_BEAM = "http://w3id.org/beam/core#"
_BP_NAME = URIRef("https://sBPMN.github.io/2.0/properties#name")
_LEAF_SHAPE = "http://w3id.org/airiskkg/shacl/architecture-input-contract#ResourceLeafTypeShape"
_PLAYS_ROLE = URIRef("http://w3id.org/airiskkg/pair-ai#playsRole")


def _sh(term: str) -> URIRef:
    return URIRef(_SH + term)


@lru_cache(maxsize=1)
def guidance_shape_ids() -> frozenset[str]:
    """Which shapes come from annotation_guidance.ttl rather than the contract."""
    guidance = Graph()
    guidance.parse(SHACL_DIR / "annotation_guidance.ttl", format="turtle")
    return frozenset(str(s) for s in set(guidance.subjects()))


@lru_cache(maxsize=1)
def process_shape_ids() -> frozenset[str]:
    """Which shapes come from process_input_contract.ttl: BPMN, not the architecture."""
    contract = Graph()
    contract.parse(SHACL_DIR / "process_input_contract.ttl", format="turtle")
    return frozenset(str(s) for s in set(contract.subjects()))


@lru_cache(maxsize=1)
def shapes_and_ontology() -> tuple[Graph, Graph]:
    shapes = Graph()
    shapes.parse(SHACL_DIR / "architecture_input_contract.ttl", format="turtle")
    shapes.parse(SHACL_DIR / "annotation_guidance.ttl", format="turtle")
    shapes.parse(SHACL_DIR / "process_input_contract.ttl", format="turtle")
    ontology = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        ontology.parse(CORE_DIR / name, format="turtle")
    return shapes, ontology


def _beam(term: str) -> URIRef:
    return URIRef(_BEAM + term)


def _name(data: Graph, node: URIRef) -> str:
    named = data.value(node, RDFS.label) or data.value(node, _BP_NAME)
    return str(named) if named else str(node).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _kinds_under(ontology: Graph, top: URIRef) -> list[dict]:
    rows = [{"classUri": str(sub), "label": str(ontology.value(sub, RDFS.label) or sub)}
            for sub in ontology.subjects(RDFS.subClassOf, top)]
    return sorted(rows, key=lambda row: row["label"])


def _leaf_type_advice(data: Graph, ontology: Graph, node: URIRef) -> tuple[str, dict]:
    """The bare-Model warning in plain words, with the choices that fix it.

    Match queries read `a beam:StatisticalModel`, so a bare Model matches none."""
    return (
        f'"{_name(data, node)}" is marked only as a general Model, so motifs that involve a '
        "model will not match it: they look for a Statistical Model (a machine-learning or "
        "AI model, such as an LLM) or a Semantic Model (such as an ontology or rule set). "
        "Choose which one it is.",
        {"choices": _kinds_under(ontology, _beam("Model"))},
    )


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
            item = {
                "message": str(message) if message else "Constraint violated.",
                "focusNode": str(focus) if focus else None,
                "focusLabel": _name(data, focus) if isinstance(focus, URIRef) else None,
                # Says which of the two questions this answers, so a caller
                # can act on one without acting on the other.
                "guidance": str(shape) in guidance if shape is not None else False,
                "process": str(shape) in process_shape_ids() if shape is not None else False,
            }
            if str(shape) == _LEAF_SHAPE and isinstance(focus, URIRef):
                item["message"], item["fix"] = _leaf_type_advice(data, ontology, focus)
            elif results_graph.value(result, _sh("resultPath")) == _PLAYS_ROLE and focus is not None:
                item["message"] = (
                    f'"{item["focusLabel"]}" has no role yet, so no motif can match it. '
                    "Click it on the canvas and choose one under Roles.")
            items.append(item)
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
