from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, Namespace, URIRef
from rdflib.plugins.sparql import prepareQuery

from airiskkg.knowledge_base import (
    KnowledgeBaseVersion,
    knowledge_base_version,
    ontology_files,
)
from airiskkg.paths import (
    OUTPUTS_DIR,
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

@dataclass(frozen=True)
class AssessmentResult:
    working_graph: Graph
    motif_matches: Graph
    risk_findings: Graph
    output_dir: Path | None = None
    inferred_annotations: Graph = field(default_factory=Graph)
    version: KnowledgeBaseVersion | None = None

    @property
    def combined_graph(self) -> Graph:
        return self.working_graph

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
        raise ValueError("At least one architecture graph file must be provided.")
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
    if not resolved_paths:
        raise ValueError("At least one architecture graph file must be provided.")
    return resolved_paths


def _resolve_output_dir(output_dir: Path | str) -> Path:
    path = Path(output_dir)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


_OUTPUT_RUN_DIR_RE = re.compile(r"^output_(\d+)$")


def _next_output_run_dir(base_dir: Path) -> Path:
    """Pick the next output_<n> subdirectory so each run gets its own folder."""
    base_dir.mkdir(parents=True, exist_ok=True)
    existing_runs = [
        int(match.group(1))
        for entry in base_dir.iterdir()
        if entry.is_dir() and (match := _OUTPUT_RUN_DIR_RE.match(entry.name))
    ]
    next_run = max(existing_runs, default=0) + 1
    return base_dir / f"output_{next_run}"


@lru_cache(maxsize=1)
def _base_knowledge() -> Graph:
    graph = _bind_prefixes(Graph())
    for path in ontology_files():
        _load_turtle(graph, path)
    return graph


@lru_cache(maxsize=1)
def _cached_version() -> KnowledgeBaseVersion:
    return knowledge_base_version(_base_knowledge())


def knowledge_base_fingerprint() -> KnowledgeBaseVersion:
    """The identity of the loaded library, for recording alongside results."""
    return _cached_version()


def reload_knowledge_base() -> None:
    _base_knowledge.cache_clear()
    _cached_version.cache_clear()


def load_base_graph() -> Graph:
    """A fresh, writable copy of the loaded knowledge base."""
    graph = _bind_prefixes(Graph())
    graph += _base_knowledge()
    return graph


def load_assessment_graph(architecture_paths: Path | str | Iterable[Path | str] | None = None) -> Graph:
    graph = load_base_graph()
    for path in _as_path_list(architecture_paths):
        _load_turtle(graph, path)
    return graph


_PARSE_LOCK = threading.Lock()


@lru_cache(maxsize=None)
def _prepared_query(query_path_str: str):
    with _PARSE_LOCK:
        return prepareQuery(Path(query_path_str).read_text(encoding="utf-8"))


def run_construct_query(graph: Graph, query_path: Path, **bindings: URIRef) -> Graph:
    constructed = _bind_prefixes(Graph())
    query = _prepared_query(str(query_path))
    results = graph.query(query, initBindings=bindings) if bindings else graph.query(query)
    for triple in results:
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


_MAX_PROPAGATION_ITERATIONS = 20
_DERIVED_OUTPUT_TYPES = (PAIR.DataCategoryPropagation, PAIR.BusinessFlowDerivation)


def _derive_facts(working_graph: Graph) -> Graph:
    inferred = _bind_prefixes(Graph())
    propagation_paths = [
        path
        for output_type in _DERIVED_OUTPUT_TYPES
        for path in implementation_paths_for_output_type(working_graph, output_type)
    ]
    if not propagation_paths:
        return inferred

    for _ in range(_MAX_PROPAGATION_ITERATIONS):
        new_triples = _bind_prefixes(Graph())
        for query_path in propagation_paths:
            for triple in run_construct_query(working_graph, query_path):
                if triple not in working_graph:
                    new_triples.add(triple)
        if len(new_triples) == 0:
            break
        _merge(working_graph, new_triples)
        _merge(inferred, new_triples)

    return inferred


def _run_assessment_on_graph(
    working_graph: Graph,
    *,
    write_outputs: bool,
    output_dir: Path | str,
) -> AssessmentResult:
    inferred_annotations = _derive_facts(working_graph)

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

    version = knowledge_base_fingerprint()
    run_output_dir: Path | None = None
    if write_outputs:
        run_output_dir = _next_output_run_dir(_resolve_output_dir(output_dir))
        run_output_dir.mkdir(parents=True, exist_ok=True)
        inferred_annotations.serialize(run_output_dir / "inferred_annotations.ttl", format="turtle")
        motif_matches.serialize(run_output_dir / "motif_matches.ttl", format="turtle")
        risk_findings.serialize(run_output_dir / "risk_findings.ttl", format="turtle")
        working_graph.serialize(run_output_dir / "combined_assessment_graph.ttl", format="turtle")

        (run_output_dir / "knowledge_base_version.json").write_text(
            json.dumps(version.as_dict(), indent=2) + "\n", encoding="utf-8"
        )

    return AssessmentResult(
        working_graph=working_graph,
        motif_matches=motif_matches,
        risk_findings=risk_findings,
        output_dir=run_output_dir,
        inferred_annotations=inferred_annotations,
        version=version,
    )


def run_assessment(
    architecture_paths: Path | str | Iterable[Path | str] | None = None,
    *,
    write_outputs: bool = True,
    output_dir: Path | str = OUTPUTS_DIR,
) -> AssessmentResult:
    working_graph = load_assessment_graph(architecture_paths)
    return _run_assessment_on_graph(working_graph, write_outputs=write_outputs, output_dir=output_dir)


def run_assessment_from_text(ttl_text: str) -> AssessmentResult:
    working_graph = load_base_graph()
    working_graph.parse(data=ttl_text, format="turtle")
    return _run_assessment_on_graph(working_graph, write_outputs=False, output_dir=OUTPUTS_DIR)


def mitigation_implementations(graph: Graph) -> dict[tuple[URIRef, URIRef], Path]:
    found: dict[tuple[URIRef, URIRef], Path] = {}
    for implementation in graph.subjects(PAIR.producesOutputType, PAIR.MitigationApplication):
        control = graph.value(implementation, PAIR.implementsControl)
        pattern = graph.value(implementation, PAIR.mitigatesRiskPattern)
        path_value = graph.value(implementation, PAIR.implementationPath)
        if control is not None and pattern is not None and path_value is not None:
            found[(control, pattern)] = REPO_ROOT / str(path_value)
    return found


def risk_pattern_of(graph: Graph, finding: URIRef) -> URIRef | None:
    """Which rule raised this finding."""
    value = graph.value(finding, PAIR.generatedByRiskPattern)
    return value if isinstance(value, URIRef) else None


def applicable_controls(graph: Graph, finding: URIRef) -> set[URIRef]:
    pattern = risk_pattern_of(graph, finding)
    if pattern is None:
        return set()
    return {c for (c, p) in mitigation_implementations(graph) if p == pattern}


def apply_control(architecture: Graph, control: URIRef, finding: URIRef) -> Graph:
    pattern = risk_pattern_of(architecture, finding)
    if pattern is None:
        return _bind_prefixes(Graph())
    query_path = mitigation_implementations(architecture).get((control, pattern))
    if query_path is None:
        raise ValueError(
            f"No registered mitigation rewrite applies {control} to {pattern}"
        )
    return run_construct_query(architecture, query_path, finding=finding)


def _label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, RDFS.label)
    return str(value) if value else str(resource)


def print_assessment_summary(result: AssessmentResult) -> None:
    if result.version is not None:
        print(result.version.summary())
    if len(result.inferred_annotations) > 0:
        print(f"Inferred data-category annotations: {len(result.inferred_annotations)}")
    print(f"Motif matches: {result.motif_match_count}")
    print(f"Risk findings: {result.risk_finding_count}")

    for finding in sorted(result.risk_findings.subjects(RDF.type, PAIR.RiskFinding), key=str):
        print(f"- {_label(result.risk_findings, finding)}")
        evidence = sorted(result.risk_findings.objects(finding, PAIR.hasEvidence), key=str)
        for element in evidence:
            print(f"  evidence: {_label(result.combined_graph, element)}")

    if result.output_dir is not None:
        print(f"Output written to: {result.output_dir}")
