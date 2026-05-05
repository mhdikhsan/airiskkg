from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import DCTERMS, RDF, RDFS, Graph, Namespace, URIRef

from airiskkg.paths import (
    CORE_DIR,
    EXAMPLE_DIR,
    IMPLEMENTATION_DIR,
    OUTPUTS_DIR,
    PATTERNS_DIR,
    TAXONOMY_DIR,
)


RP = Namespace("http://w3id.org/beam/risk-pattern#")
PAT = Namespace("http://w3id.org/airiskkg/patterns#")
BEAM = Namespace("http://w3id.org/beam/core#")
BEAMR = Namespace("http://w3id.org/beam/risk#")

CORE_FILES = [
    CORE_DIR / "beam_core.ttl",
    CORE_DIR / "beam_core_risk.ttl",
    CORE_DIR / "imports.ttl",
    CORE_DIR / "risk_pattern.ttl",
]

PATTERN_FILES = [
    PATTERNS_DIR / "motif.ttl",
    PATTERNS_DIR / "risk_interpretation.ttl",
]

MATCHING_OQPS = [
    IMPLEMENTATION_DIR / "match_vector_ir.construct.rq",
    IMPLEMENTATION_DIR / "match_llm_ir.construct.rq",
]

INTERPRETATION_OQPS = [
    IMPLEMENTATION_DIR / "interpret_sensitive_data_retrieval.construct.rq",
    IMPLEMENTATION_DIR / "interpret_direct_llm_without_grounding.construct.rq",
]


@dataclass(frozen=True)
class AssessmentResult:
    working_graph: Graph
    motif_matches: Graph
    risk_findings: Graph
    combined_graph: Graph

    @property
    def motif_match_count(self) -> int:
        return len(set(self.motif_matches.subjects(RDF.type, RP.MotifMatch)))

    @property
    def risk_finding_count(self) -> int:
        return len(set(self.risk_findings.subjects(RDF.type, RP.RiskFinding)))


def _bind_prefixes(graph: Graph) -> Graph:
    graph.bind("rp", RP)
    graph.bind("pat", PAT)
    graph.bind("beam", BEAM)
    graph.bind("beamr", BEAMR)
    graph.bind("rdfs", RDFS)
    graph.bind("dct", DCTERMS)
    return graph


def _load_turtle(graph: Graph, path: Path) -> None:
    graph.parse(path, format="turtle")


def load_uc6_graph() -> Graph:
    graph = _bind_prefixes(Graph())
    for path in CORE_FILES:
        _load_turtle(graph, path)
    for path in PATTERN_FILES:
        _load_turtle(graph, path)
    for path in sorted(TAXONOMY_DIR.glob("*.ttl")):
        _load_turtle(graph, path)
    _load_turtle(graph, EXAMPLE_DIR / "beam_core_instance_uc6.ttl")
    return graph


def run_construct_query(graph: Graph, query_path: Path) -> Graph:
    constructed = _bind_prefixes(Graph())
    query = query_path.read_text(encoding="utf-8")
    for triple in graph.query(query):
        constructed.add(triple)
    return constructed


def _merge(target: Graph, source: Graph) -> None:
    for triple in source:
        target.add(triple)


def run_uc6_assessment(write_outputs: bool = True) -> AssessmentResult:
    working_graph = load_uc6_graph()
    motif_matches = _bind_prefixes(Graph())
    risk_findings = _bind_prefixes(Graph())

    for query_path in MATCHING_OQPS:
        constructed = run_construct_query(working_graph, query_path)
        _merge(motif_matches, constructed)
        _merge(working_graph, constructed)

    for query_path in INTERPRETATION_OQPS:
        constructed = run_construct_query(working_graph, query_path)
        _merge(risk_findings, constructed)
        _merge(working_graph, constructed)

    combined_graph = _bind_prefixes(Graph())
    _merge(combined_graph, working_graph)

    result = AssessmentResult(
        working_graph=working_graph,
        motif_matches=motif_matches,
        risk_findings=risk_findings,
        combined_graph=combined_graph,
    )

    if write_outputs:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        motif_matches.serialize(OUTPUTS_DIR / "motif_matches.ttl", format="turtle")
        risk_findings.serialize(OUTPUTS_DIR / "risk_findings.ttl", format="turtle")
        combined_graph.serialize(OUTPUTS_DIR / "combined_assessment_graph.ttl", format="turtle")

    return result


def _label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, RDFS.label)
    return str(value) if value else str(resource)


def print_assessment_summary(result: AssessmentResult) -> None:
    print(f"Motif matches: {result.motif_match_count}")
    print(f"Risk findings: {result.risk_finding_count}")

    for finding in sorted(result.risk_findings.subjects(RDF.type, RP.RiskFinding), key=str):
        print(f"- {_label(result.risk_findings, finding)}")
        evidence = sorted(result.risk_findings.objects(finding, RP.hasEvidenceElement), key=str)
        for element in evidence:
            print(f"  evidence: {_label(result.combined_graph, element)}")


def main() -> None:
    result = run_uc6_assessment(write_outputs=True)
    print_assessment_summary(result)


if __name__ == "__main__":
    main()
