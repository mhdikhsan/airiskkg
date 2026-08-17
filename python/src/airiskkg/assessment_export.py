from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from rdflib import DCTERMS, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import AssessmentResult, _bind_prefixes

PROV = Namespace("http://www.w3.org/ns/prov#")
BEAM = Namespace("http://w3id.org/beam/core#")
PAIR = Namespace("http://w3id.org/airiskkg/pair-ai#")
PAIR_AI_AGENT = URIRef("https://w3id.org/airiskkg/pair-ai")
OUTPUT_CONTRACT = URIRef("http://w3id.org/airiskkg/shacl/assessment-output-contract")

EXPORT_FORMATS = {
    "turtle": ("text/turtle", "ttl"),
    "json-ld": ("application/ld+json", "jsonld"),
    "nt": ("application/n-triples", "nt"),
}


@dataclass(frozen=True)
class AssessmentExport:
    graph: Graph
    activity: URIRef

    def serialize(self, export_format: str = "turtle") -> str:
        if export_format not in EXPORT_FORMATS:
            raise ValueError(
                f"Unsupported export format {export_format!r}; "
                f"expected one of {', '.join(sorted(EXPORT_FORMATS))}"
            )
        if export_format == "json-ld":
            return self.graph.serialize(format="json-ld", auto_compact=True)
        return self.graph.serialize(format=export_format)


def _architecture_graph(result: AssessmentResult, architecture: Graph | None) -> Graph:
    """The submitted graph on its own, without the library.

    Callers that still hold the parsed input pass it directly. Otherwise it is
    recovered by subtracting the base graph from the working graph, because the
    working graph is base + architecture + derived facts. Subtracting matters:
    returning the working graph as-is would republish the whole motif, risk
    pattern, and taxonomy layer into every export, which is the one thing this
    module exists to avoid."""
    if architecture is not None:
        return architecture
    from airiskkg.assessment_runner import load_base_graph

    base = load_base_graph()
    recovered = Graph()
    for triple in result.working_graph:
        if triple not in base:
            recovered.add(triple)
    return recovered


def build_export(
    result: AssessmentResult,
    architecture: Graph | None = None,
    *,
    source_label: str | None = None,
    started_at: datetime | None = None,
) -> AssessmentExport:
    """Assemble the exportable graph for one assessment run."""
    graph = _bind_prefixes(Graph())
    graph.bind("prov", PROV)
    graph.bind("dct", DCTERMS)

    for part in (
        _architecture_graph(result, architecture),
        result.motif_matches,
        result.risk_findings,
        result.inferred_annotations,
    ):
        for triple in part:
            graph.add(triple)

    ended_at = datetime.now(timezone.utc)
    activity = URIRef(f"urn:uuid:{uuid.uuid4()}")
    graph.add((activity, RDF.type, PROV.Activity))
    graph.add((activity, RDFS.label, Literal("PAIR-AI candidate risk assessment run", lang="en")))
    graph.add((activity, PROV.wasAssociatedWith, PAIR_AI_AGENT))
    graph.add((activity, PROV.endedAtTime, Literal(ended_at.isoformat(), datatype=XSD.dateTime)))
    if started_at is not None:
        graph.add(
            (activity, PROV.startedAtTime, Literal(started_at.isoformat(), datatype=XSD.dateTime))
        )
    graph.add((PAIR_AI_AGENT, RDF.type, PROV.SoftwareAgent))
    graph.add((PAIR_AI_AGENT, RDFS.label, Literal("PAIR-AI", lang="en")))

    graph.add((activity, DCTERMS.created, Literal(ended_at.isoformat(), datatype=XSD.dateTime)))
    graph.add((activity, DCTERMS.conformsTo, OUTPUT_CONTRACT))
    if source_label:
        graph.add((activity, DCTERMS.title, Literal(source_label)))
    for system in set(graph.subjects(RDF.type, BEAM.System)):
        graph.add((activity, PROV.used, system))
    for generated_type in (PAIR.RiskFinding, PAIR.MotifMatch):
        for subject in set(graph.subjects(RDF.type, generated_type)):
            graph.add((subject, PROV.wasGeneratedBy, activity))

    return AssessmentExport(graph=graph, activity=activity)
