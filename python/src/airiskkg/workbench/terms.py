"""Naming primitives: how an element or concept is labelled, and which BEAM
classes the guided builder offers.

The bottom of the workbench import graph - nothing here imports anything else in
the package, so templates, gaps and vocabulary can all rely on it without a
cycle.
"""

from __future__ import annotations

import re

from rdflib import RDFS, SKOS, Graph, URIRef

from airiskkg.assessment_runner import BEAM

# Element classes the guided builder offers, paired with the BEAM class they map to.
RESOURCE_CLASSES = [
    (BEAM.Data, "Data"),
    (BEAM.StatisticalModel, "Statistical Model"),
    (BEAM.SemanticModel, "Semantic Model"),
    (BEAM.Symbol, "Symbol"),
]
PROCESS_CLASSES = [
    (BEAM.Transform, "Transform"),
    (BEAM.Infer, "Infer"),
    (BEAM.Train, "Train"),
    (BEAM.Generate, "Generate"),
    (BEAM.Process, "Process (generic)"),
]
EDGE_KINDS = [
    {"id": "use", "label": "uses (process → resource)", "target": "resource"},
    {"id": "produce", "label": "produces (process → resource)", "target": "resource"},
    {"id": "inform", "label": "informs (process → process)", "target": "process"},
]

# BEAM process classes (everything else is a resource) - used to attach a
# templated node to its system via hasProcess vs hasResource.
PROCESS_CLASS_NAMES = {"Transform", "Infer", "Train", "Generate", "Process"}


def short(term: object) -> str:
    """The local part of an IRI: what a term is called, without its namespace."""
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, SKOS.prefLabel) or graph.value(resource, RDFS.label)
    if value:
        return str(value)
    return short(resource)


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ACRONYM_BOUNDARY = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")


def display_label(text: str) -> str:
    """Humanize identifier-style names so role/category labels read uniformly.
    Labels that already contain a space are curated and kept as-is; spaceless
    camelCase / underscore names are split ('GenerativeModel' -> 'Generative
    Model', 'LLMResponse' -> 'LLM Response')."""
    if " " in text:
        return text
    spaced = text.replace("_", " ").replace("-", " ")
    spaced = _ACRONYM_BOUNDARY.sub(" ", _CAMEL_BOUNDARY.sub(" ", spaced))
    return re.sub(r"\s+", " ", spaced).strip()


def class_terms(pairs: list[tuple[URIRef, str]]) -> list[dict[str, str]]:
    return [{"id": str(uri), "label": text} for uri, text in pairs]
