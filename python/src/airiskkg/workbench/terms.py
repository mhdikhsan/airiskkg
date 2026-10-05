from __future__ import annotations

import re

from rdflib import RDF, RDFS, SKOS, Graph, Namespace, URIRef

from airiskkg.assessment_runner import BEAM

_NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")
MIT_DOMAIN_TAXONOMY = URIRef(
    "http://w3id.org/airiskkg/taxonomy/mit-ai-risk#MIT_AI_Risk_Repository_Domain_Taxonomy"
)

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
]

PROCESS_CLASS_NAMES = {"Transform", "Infer", "Train", "Generate", "Process"}
TAXONOMY_SOURCES = {
    "http://w3id.org/airiskkg/taxonomy/owasp-llm#": ("OWASP LLM Top 10", "OWASP LLM"),
    "http://w3id.org/airiskkg/taxonomy/owasp-asi#": ("OWASP Agentic Top 10", "OWASP ASI"),
    "http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#": ("IBM AI Risk Atlas", "IBM"),
    "http://w3id.org/airiskkg/taxonomy/mit-ai-risk#": ("MIT AI Risk Repository", "MIT"),
    "http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#": ("MIT AI Risk Control", "MIT"),
    "http://w3id.org/airiskkg/taxonomy/nist-genai#": ("NIST AI 600-1", "NIST"),
    "http://w3id.org/airiskkg/patterns#": ("PAIR-AI Pattern Library", "PAIR-AI"),
}


def source_pair(uri: object) -> tuple[str, str]:
    """(full catalogue name, short name) for the vocabulary an IRI sits in."""
    text = str(uri)
    for prefix, names in TAXONOMY_SOURCES.items():
        if text.startswith(prefix):
            return names
    return ("Other", "Other")


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
    if " " in text:
        return text
    spaced = text.replace("_", " ").replace("-", " ")
    spaced = _ACRONYM_BOUNDARY.sub(" ", _CAMEL_BOUNDARY.sub(" ", spaced))
    return re.sub(r"\s+", " ", spaced).strip()


def class_terms(pairs: list[tuple[URIRef, str]]) -> list[dict[str, str]]:
    return [{"id": str(uri), "label": text} for uri, text in pairs]


def risk_domains(graph: Graph) -> set[URIRef]:
    """The domains of harm the loaded taxonomy offers as a top level."""
    return {
        group
        for group in graph.subjects(RDF.type, _NEXUS.RiskGroup)
        if (group, SKOS.inScheme, MIT_DOMAIN_TAXONOMY) in graph
    }


def domain_of(graph: Graph, entry: URIRef, domains: set[URIRef]) -> URIRef | None:
    """The domain of harm a taxonomy entry rolls up to, if it has one.
    """
    for broader in graph.objects(entry, SKOS.broader):
        if broader in domains:
            return broader
    return None
