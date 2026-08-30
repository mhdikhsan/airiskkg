from __future__ import annotations

import re
from pathlib import Path

from rdflib import DCTERMS, RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.paths import ONTOLOGY_DIR, REPO_ROOT

T4B = Namespace("http://tool4boxology.org/")
BEAM = Namespace("http://w3id.org/beam/core#")
BOXPAT = Namespace("http://w3id.org/airiskkg/boxology-elementary-pattern#")

ALIGNMENT_PATH = ONTOLOGY_DIR / "alignments" / "tool4boxology_alignment.ttl"
T4B_ONTOLOGY_PATH = REPO_ROOT / "external" / "tool4boxology" / "Tool4BoxologyOntology.ttl"

_TYPE_ALIASES = {
    T4B["training"]: T4B["Train"],
    T4B["engineering"]: T4B["Engineer"],
    T4B["prediction"]: T4B["Infer"],
    T4B["StatisticModel"]: T4B["StatisticalModel"],
    T4B["Time%20Series"]: T4B["TimeSeries"],
}

# "1d Extract Relevant Information" -> pattern id "1d"
_PATTERN_ID_RE = re.compile(r"^\s*(\d+[a-z]?)\b", re.IGNORECASE)


class T4bImportError(Exception):
    """Raised when a t4b export cannot be parsed or normalized."""


def _declared_classes(t4b_ontology: Graph) -> dict[str, URIRef]:
    """Local-name (lowercased) -> declared t4b class URI."""
    classes: dict[str, URIRef] = {}
    for cls in t4b_ontology.subjects(RDF.type, URIRef("http://www.w3.org/2002/07/owl#Class")):
        if isinstance(cls, URIRef) and str(cls).startswith(str(T4B)):
            local = str(cls)[len(str(T4B)):]
            classes[local.lower()] = cls
    return classes


def case_normalize_types(graph: Graph, t4b_ontology: Graph) -> int:
  
    declared = _declared_classes(t4b_ontology)
    fixes = 0
    for subject, obj in list(graph.subject_objects(RDF.type)):
        if not isinstance(obj, URIRef) or not str(obj).startswith(str(T4B)):
            continue
        target = _TYPE_ALIASES.get(obj)
        if target is None:
            local = str(obj)[len(str(T4B)):]
            declared_cls = declared.get(local.lower())
            if declared_cls is not None and declared_cls != obj:
                target = declared_cls
        if target is not None:
            graph.remove((subject, RDF.type, obj))
            graph.add((subject, RDF.type, target))
            fixes += 1
    return fixes


def materialize_beam(graph: Graph, alignment: Graph, t4b_ontology: Graph) -> int:
    added = 0

    
    for artifact, process in graph.subject_objects(T4B["inputRoleParticipatesInProcess"]):
        if (process, BEAM.use, artifact) not in graph:
            graph.add((process, BEAM.use, artifact))
            added += 1
    
    for process, artifact in graph.subject_objects(T4B["outputRoleParticipatesInProcess"]):
        if (process, BEAM.produce, artifact) not in graph:
            graph.add((process, BEAM.produce, artifact))
            added += 1

  
    hierarchy = Graph()
    for g in (alignment, t4b_ontology):
        for triple in g.triples((None, RDFS.subClassOf, None)):
            hierarchy.add(triple)

    def beam_supers(cls: URIRef, seen: set[URIRef]) -> set[URIRef]:
        result: set[URIRef] = set()
        for parent in hierarchy.objects(cls, RDFS.subClassOf):
            if not isinstance(parent, URIRef) or parent in seen:
                continue
            seen.add(parent)
            if str(parent).startswith(str(BEAM)):
                result.add(parent)
            else:
                result |= beam_supers(parent, seen)
        return result

    for subject, cls in list(graph.subject_objects(RDF.type)):
        if not isinstance(cls, URIRef) or not str(cls).startswith(str(T4B)):
            continue
        for beam_cls in beam_supers(cls, {cls}):
            if (subject, RDF.type, beam_cls) not in graph:
                graph.add((subject, RDF.type, beam_cls))
                added += 1

 
    for boxology in list(graph.subjects(RDF.type, T4B["Boxology"])):
        if (boxology, RDF.type, BEAM.System) not in graph:
            graph.add((boxology, RDF.type, BEAM.System))
            added += 1

    return added


def annotate_pattern_provenance(graph: Graph) -> int:
    added = 0
    member_predicates = (T4B["hasInput"], T4B["hasOutput"], T4B["hasProcess"])
    for pattern in graph.subjects(RDF.type, T4B["DesignPattern"]):
        label = graph.value(pattern, RDFS.label)
        if label is None:
            continue
        match = _PATTERN_ID_RE.match(str(label))
        if match is None:
            continue
        pattern_uri = BOXPAT[match.group(1).lower()]
        if (pattern_uri, RDFS.label, None) not in graph:
            graph.add((pattern_uri, RDFS.label, Literal(str(label))))
            added += 1
        for predicate in member_predicates:
            for member in graph.objects(pattern, predicate):
                if (member, DCTERMS.conformsTo, pattern_uri) not in graph:
                    graph.add((member, DCTERMS.conformsTo, pattern_uri))
                    added += 1
    return added


def _load_adapter_graphs() -> tuple[Graph, Graph]:
    t4b_ontology = Graph()
    t4b_ontology.parse(T4B_ONTOLOGY_PATH, format="turtle")
    alignment = Graph()
    alignment.parse(ALIGNMENT_PATH, format="turtle")
    return t4b_ontology, alignment


def normalize_graph(graph: Graph) -> dict[str, int]:
    graph.bind("t4b", T4B)
    graph.bind("beam", BEAM)
    graph.bind("dct", DCTERMS)
    graph.bind("boxpat", BOXPAT)

    t4b_ontology, alignment = _load_adapter_graphs()
    return {
        "fixed": case_normalize_types(graph, t4b_ontology),
        "materialized": materialize_beam(graph, alignment, t4b_ontology),
        "annotated": annotate_pattern_provenance(graph),
    }


def normalize(export_path: Path) -> Graph:
    graph = Graph()
    graph.parse(export_path, format="nt")
    counts = normalize_graph(graph)
    print(f"case-normalized type triples: {counts['fixed']}")
    print(f"materialized BEAM triples:    {counts['materialized']}")
    print(f"pattern provenance triples:   {counts['annotated']}")
    return graph


def normalize_text(text: str, fmt: str = "nt") -> tuple[Graph, dict[str, int]]:
    
    graph = Graph()
    try:
        graph.parse(data=text, format=fmt)
    except Exception as error:  # noqa: BLE001 - surface parse errors to the caller
        raise T4bImportError(f"Could not parse as {fmt}: {error}") from error
    if len(graph) == 0:
        raise T4bImportError("No triples found in the uploaded file.")
    counts = normalize_graph(graph)
    return graph, counts


def t4b_to_ttl(text: str, fmt: str = "nt") -> tuple[str, list[str]]:
   
    graph, counts = normalize_text(text, fmt=fmt)
    if not any(graph.subjects(RDF.type, BEAM.System)):
        raise T4bImportError(
            "No t4b:Boxology (architecture root) found - is this a Tool4Boxology export?"
        )
    notes = [
        f"Case-normalized {counts['fixed']} export type triple(s) to declared t4b classes.",
        f"Materialized {counts['materialized']} BEAM triple(s) (flow edges + types) via the alignment adapter; "
        "original t4b triples were kept.",
    ]
    if counts["annotated"]:
        notes.append(
            f"Recovered {counts['annotated']} dct:conformsTo provenance triple(s) from t4b:DesignPattern groupings."
        )
    notes.append(
        "No pattern roles or data categories are set by Tool4Boxology exports - "
        "annotate elements in Draw mode so motifs and risk patterns can match."
    )
    return graph.serialize(format="turtle"), notes
