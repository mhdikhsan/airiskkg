"""Export one assessment run as a self-contained, traceable knowledge graph.

The assessment already produces RDF - motif matches and candidate risk findings.
What it does not produce is a graph anyone can read on its own. Two things are
missing from a bare dump:

  * The findings reference elements by URI, so without the architecture graph
    beside them the evidence is unresolvable. A finding that says "this element
    is exposed" is useless if nothing in the file says what that element is.
  * Nothing records that the findings came from a *run*: which graph was
    assessed, when, and by what. A file of candidate risks with no provenance
    invites exactly the reading the method rejects - findings as standing facts
    rather than the output of one analysis of one submitted graph.

So the export is the architecture graph, the matches, the findings, the derived
annotations, and a PROV-O record tying them together.

Deliberately NOT included: the motif library, the risk-pattern library, and the
taxonomies. Those are the reusable knowledge resource, not this run's output;
bundling them would republish a CC BY-SA-adjacent corpus into every export and
inflate a small result to megabytes. Findings reference library terms by URI,
which is what URIs are for.

No new pair: vocabulary is minted here. The run header is plain PROV-O and
Dublin Core, so a consumer needs no PAIR-AI-specific knowledge to see what the
file is - and the glossary is explicit that "assessment output" is a narrative
term, not a defined class.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from rdflib import DCTERMS, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import AssessmentResult, _bind_prefixes

PROV = Namespace("http://www.w3.org/ns/prov#")
BEAM = Namespace("http://w3id.org/beam/core#")
PAIR = Namespace("http://w3id.org/airiskkg/pair-ai#")

#: Identifies the software that produced an export, as a PROV agent.
PAIR_AI_AGENT = URIRef("https://w3id.org/airiskkg/pair-ai")

#: The shapes an export is expected to satisfy, advertised via dct:conformsTo so
#: a consumer can check the file rather than take its word for it.
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

    # What was assessed, and what came out of it. prov:used points at the
    # systems present in the submitted graph; every finding and match is
    # attributed to this run, so merging several exports keeps them apart.
    for system in set(graph.subjects(RDF.type, BEAM.System)):
        graph.add((activity, PROV.used, system))
    for generated_type in (PAIR.RiskFinding, PAIR.MotifMatch):
        for subject in set(graph.subjects(RDF.type, generated_type)):
            graph.add((subject, PROV.wasGeneratedBy, activity))

    return AssessmentExport(graph=graph, activity=activity)
