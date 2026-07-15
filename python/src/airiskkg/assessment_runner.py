from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, Namespace, URIRef

from airiskkg.paths import (
    CORE_DIR,
    EXAMPLE_DIR,
    OUTPUTS_DIR,
    PATTERNS_DIR,
    TAXONOMY_DIR,
    REPO_ROOT,
)


PAIR = Namespace("http://w3id.org/airiskkg/pair-ai#")
PAT = Namespace("http://w3id.org/airiskkg/patterns#")
BEAM = Namespace("http://w3id.org/beam/core#")
BEAMR = Namespace("http://w3id.org/beam/risk#")
OWASP = Namespace("http://w3id.org/airiskkg/taxonomy/owasp-llm#")
ATLAS = Namespace("http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#")
MIT = Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk#")
MITCTRL = Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#")
NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")

CORE_FILES = [
    CORE_DIR / "beam_core.ttl",
    CORE_DIR / "beam_core_risk.ttl",
    CORE_DIR / "imports.ttl",
    CORE_DIR / "pair_ai_pattern.ttl",
]

PATTERN_FILES = [
    PATTERNS_DIR / "motif.ttl",
    PATTERNS_DIR / "risk_pattern_library.ttl",
]

DEFAULT_ARCHITECTURE_FILES = [
    EXAMPLE_DIR / "uc6.ttl",
]


@dataclass(frozen=True)
class AssessmentResult:
    working_graph: Graph
    motif_matches: Graph
    risk_findings: Graph
    combined_graph: Graph

    @property
    def motif_match_count(self) -> int:
        return len(set(self.motif_matches.subjects(RDF.type, PAIR.MotifMatch)))

    @property
    def risk_finding_count(self) -> int:
        return len(set(self.risk_findings.subjects(RDF.type, PAIR.RiskFinding)))


def _bind_prefixes(graph: Graph) -> Graph:
    graph.bind("pair", PAIR)
    graph.bind("pat", PAT)
    graph.bind("beam", BEAM)
    graph.bind("beamr", BEAMR)
    graph.bind("owasp", OWASP)
    graph.bind("atlas", ATLAS)
    graph.bind("mit", MIT)
    graph.bind("mitctrl", MITCTRL)
    graph.bind("nexus", NEXUS)
    graph.bind("rdfs", RDFS)
    graph.bind("skos", SKOS)
    graph.bind("dct", DCTERMS)
    return graph


def _load_turtle(graph: Graph, path: Path) -> None:
    graph.parse(path, format="turtle")


def _as_path_list(paths: Path | str | Iterable[Path | str] | None) -> list[Path]:
    if paths is None:
        return list(DEFAULT_ARCHITECTURE_FILES)
    if isinstance(paths, (str, Path)):
        paths = [paths]

    resolved_paths: list[Path] = []
    for path_value in paths:
        path = Path(path_value)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.is_file():
            raise FileNotFoundError(f"Architecture graph not found: {path}")
        resolved_paths.append(path)
    return resolved_paths


def _resolve_output_dir(output_dir: Path | str) -> Path:
    path = Path(output_dir)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def load_base_graph() -> Graph:
    """Load the reusable knowledge base (core, patterns, taxonomies) without any
    architecture graph. This is the shared starting point for every assessment."""
    graph = _bind_prefixes(Graph())
    for path in CORE_FILES:
        _load_turtle(graph, path)
    for path in PATTERN_FILES:
        _load_turtle(graph, path)
    for path in sorted(TAXONOMY_DIR.glob("*.ttl")):
        _load_turtle(graph, path)
    return graph


def load_assessment_graph(architecture_paths: Path | str | Iterable[Path | str] | None = None) -> Graph:
    graph = load_base_graph()
    for path in _as_path_list(architecture_paths):
        _load_turtle(graph, path)
    return graph


def load_assessment_graph_from_text(architecture_ttl: str) -> Graph:
    """Build an assessment graph from an in-memory Turtle architecture description."""
    graph = load_base_graph()
    graph.parse(data=architecture_ttl, format="turtle")
    return graph


def load_uc6_graph() -> Graph:
    return load_assessment_graph(DEFAULT_ARCHITECTURE_FILES)


def run_construct_query(graph: Graph, query_path: Path) -> Graph:
    constructed = _bind_prefixes(Graph())
    query = query_path.read_text(encoding="utf-8")
    for triple in graph.query(query):
        constructed.add(triple)
    return constructed


def implementation_paths_for_output_type(graph: Graph, output_type: URIRef) -> list[Path]:
    paths: list[Path] = []
    for implementation in graph.subjects(PAIR.producesOutputType, output_type):
        path_value = graph.value(implementation, PAIR.implementationPath)
        if path_value is None:
            continue
        path = REPO_ROOT / str(path_value)
        paths.append(path)
    return sorted(set(paths))


def _merge(target: Graph, source: Graph) -> None:
    for triple in source:
        target.add(triple)


def run_assessment_on_graph(working_graph: Graph) -> AssessmentResult:
    """Run the two-step assessment pipeline against an already-loaded graph.

    Step 1 materializes motif matches; step 2 applies interpretation conditions to
    produce risk findings. Both sets of constructed triples are merged back into the
    working graph so later queries can build on earlier results.
    """
    motif_matches = _bind_prefixes(Graph())
    risk_findings = _bind_prefixes(Graph())

    for query_path in implementation_paths_for_output_type(working_graph, PAIR.MotifMatch):
        constructed = run_construct_query(working_graph, query_path)
        _merge(motif_matches, constructed)
        _merge(working_graph, constructed)

    for query_path in implementation_paths_for_output_type(working_graph, PAIR.RiskFinding):
        constructed = run_construct_query(working_graph, query_path)
        _merge(risk_findings, constructed)
        _merge(working_graph, constructed)

    combined_graph = _bind_prefixes(Graph())
    _merge(combined_graph, working_graph)

    return AssessmentResult(
        working_graph=working_graph,
        motif_matches=motif_matches,
        risk_findings=risk_findings,
        combined_graph=combined_graph,
    )


def _write_outputs(result: AssessmentResult, output_dir: Path | str) -> None:
    output_path = _resolve_output_dir(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    result.motif_matches.serialize(output_path / "motif_matches.ttl", format="turtle")
    result.risk_findings.serialize(output_path / "risk_findings.ttl", format="turtle")
    result.combined_graph.serialize(output_path / "combined_assessment_graph.ttl", format="turtle")


def run_assessment(
    architecture_paths: Path | str | Iterable[Path | str] | None = None,
    *,
    write_outputs: bool = True,
    output_dir: Path | str = OUTPUTS_DIR,
) -> AssessmentResult:
    working_graph = load_assessment_graph(architecture_paths)
    result = run_assessment_on_graph(working_graph)
    if write_outputs:
        _write_outputs(result, output_dir)
    return result


def run_assessment_from_text(
    architecture_ttl: str,
    *,
    write_outputs: bool = False,
    output_dir: Path | str = OUTPUTS_DIR,
) -> AssessmentResult:
    """Run an assessment against an architecture graph supplied as Turtle text.

    This powers the web UI, where the developer's architecture is submitted as raw
    Turtle rather than a file on disk.
    """
    working_graph = load_assessment_graph_from_text(architecture_ttl)
    result = run_assessment_on_graph(working_graph)
    if write_outputs:
        _write_outputs(result, output_dir)
    return result


def run_uc6_assessment(write_outputs: bool = True) -> AssessmentResult:
    return run_assessment(DEFAULT_ARCHITECTURE_FILES, write_outputs=write_outputs)


def _label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, RDFS.label)
    return str(value) if value else str(resource)


def print_assessment_summary(result: AssessmentResult) -> None:
    print(f"Motif matches: {result.motif_match_count}")
    print(f"Risk findings: {result.risk_finding_count}")

    for finding in sorted(result.risk_findings.subjects(RDF.type, PAIR.RiskFinding), key=str):
        print(f"- {_label(result.risk_findings, finding)}")
        evidence = sorted(result.risk_findings.objects(finding, PAIR.hasEvidenceElement), key=str)
        for element in evidence:
            print(f"  evidence: {_label(result.combined_graph, element)}")


def main() -> None:
    result = run_assessment(write_outputs=True)
    print_assessment_summary(result)


if __name__ == "__main__":
    main()
