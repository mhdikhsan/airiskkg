"""Normalize a Tool4Boxology N-Triples export into a BEAM architecture graph.

Ports-and-adapters boundary for PAIR-AI: Tool4Boxology delivers architecture
graphs in its own vocabulary (t4b: = http://tool4boxology.org/); this script
normalizes them at ingestion so that assessment always runs against BEAM,
the canonical internal model (Rule R5 - BEAM itself is never extended here).

Steps:
  (a) load a t4b N-Triples export
  (b) case-normalize type URIs (the export uses lowercase URIs such as
      t4b:transform while the ontology declares t4b:Transform - verified
      upstream data-quality issue; see external/tool4boxology/README.md)
  (c) materialize beam:use / beam:produce triples and BEAM class types from
      the alignment adapter (ontology/alignments/tool4boxology_alignment.ttl),
      keeping all original t4b triples
  (d) convert t4b:DesignPattern groupings into provenance: every contained
      element gets dct:conformsTo pointing to the Boxology elementary pattern
      parsed from the grouping's label (feeds motif derivation provenance,
      pair:derivedFrom)
  (e) validate the result against the SHACL input contract (Task 5)

Usage:
    python python/scripts/normalize_t4b.py <export.nt> [-o <out.ttl>] [--skip-validation]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from rdflib import DCTERMS, RDF, RDFS, Graph, Literal, Namespace, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.paths import ONTOLOGY_DIR, REPO_ROOT  # noqa: E402

T4B = Namespace("http://tool4boxology.org/")
BEAM = Namespace("http://w3id.org/beam/core#")
BOXPAT = Namespace("http://w3id.org/airiskkg/boxology-elementary-pattern#")

ALIGNMENT_PATH = ONTOLOGY_DIR / "alignments" / "tool4boxology_alignment.ttl"
T4B_ONTOLOGY_PATH = REPO_ROOT / "external" / "tool4boxology" / "Tool4BoxologyOntology.ttl"

# Verified export -> ontology type-URI fixes that plain capitalization cannot
# recover (see external/tool4boxology/README.md).
_TYPE_ALIASES = {
    T4B["training"]: T4B["Train"],
    T4B["engineering"]: T4B["Engineer"],
    T4B["prediction"]: T4B["Infer"],
    T4B["StatisticModel"]: T4B["StatisticalModel"],
    T4B["Time%20Series"]: T4B["TimeSeries"],
}

# "1d Extract Relevant Information" -> pattern id "1d"
_PATTERN_ID_RE = re.compile(r"^\s*(\d+[a-z]?)\b", re.IGNORECASE)


def _declared_classes(t4b_ontology: Graph) -> dict[str, URIRef]:
    """Local-name (lowercased) -> declared t4b class URI."""
    classes: dict[str, URIRef] = {}
    for cls in t4b_ontology.subjects(RDF.type, URIRef("http://www.w3.org/2002/07/owl#Class")):
        if isinstance(cls, URIRef) and str(cls).startswith(str(T4B)):
            local = str(cls)[len(str(T4B)):]
            classes[local.lower()] = cls
    return classes


def case_normalize_types(graph: Graph, t4b_ontology: Graph) -> int:
    """Rewrite lowercase/misspelled export type URIs to the declared class URIs.

    Original triples are replaced (not duplicated): the lowercase URIs are not
    declared classes, so keeping them adds noise without information.
    """
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
    """Materialize BEAM flow triples and BEAM types (original t4b triples kept)."""
    added = 0

    # Flow: artifact --inputRoleParticipatesInProcess--> process  =>  process beam:use artifact
    for artifact, process in graph.subject_objects(T4B["inputRoleParticipatesInProcess"]):
        if (process, BEAM.use, artifact) not in graph:
            graph.add((process, BEAM.use, artifact))
            added += 1
    # Flow: process --outputRoleParticipatesInProcess--> artifact  =>  process beam:produce artifact
    for process, artifact in graph.subject_objects(T4B["outputRoleParticipatesInProcess"]):
        if (process, BEAM.produce, artifact) not in graph:
            graph.add((process, BEAM.produce, artifact))
            added += 1

    # Types: walk each instance type up the t4b subclass hierarchy until an
    # aligned BEAM superclass is found in the alignment adapter.
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

    # DESIGN DECISION: each t4b:Boxology instance represents one exported
    # architecture; type it beam:System so the SHACL input contract holds.
    for boxology in list(graph.subjects(RDF.type, T4B["Boxology"])):
        if (boxology, RDF.type, BEAM.System) not in graph:
            graph.add((boxology, RDF.type, BEAM.System))
            added += 1

    return added


def annotate_pattern_provenance(graph: Graph) -> int:
    """dct:conformsTo on every element grouped by a t4b:DesignPattern.

    The grouping's rdfs:label carries the Boxology elementary pattern id
    (e.g. "1d Extract Relevant Information"); this feeds pair:derivedFrom
    motif provenance.
    """
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


def normalize(export_path: Path) -> Graph:
    graph = Graph()
    graph.parse(export_path, format="nt")
    graph.bind("t4b", T4B)
    graph.bind("beam", BEAM)
    graph.bind("dct", DCTERMS)
    graph.bind("boxpat", BOXPAT)

    t4b_ontology = Graph()
    t4b_ontology.parse(T4B_ONTOLOGY_PATH, format="turtle")
    alignment = Graph()
    alignment.parse(ALIGNMENT_PATH, format="turtle")

    fixes = case_normalize_types(graph, t4b_ontology)
    materialized = materialize_beam(graph, alignment, t4b_ontology)
    annotated = annotate_pattern_provenance(graph)
    print(f"case-normalized type triples: {fixes}")
    print(f"materialized BEAM triples:    {materialized}")
    print(f"pattern provenance triples:   {annotated}")
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("export", help="Tool4Boxology N-Triples export file")
    parser.add_argument("-o", "--output", help="Output Turtle file (default: <export>.beam.ttl)")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Skip SHACL input-contract validation")
    args = parser.parse_args()

    export_path = Path(args.export)
    if not export_path.is_absolute():
        export_path = REPO_ROOT / export_path
    output_path = Path(args.output) if args.output else export_path.with_suffix(".beam.ttl")

    graph = normalize(export_path)
    graph.serialize(output_path, format="turtle")
    print(f"normalized graph written to: {output_path}  ({len(graph)} triples)")

    if not args.skip_validation:
        from validate_graphs import SHAPES_PATH, _load_ontology_graph, validate_graph

        shapes = Graph()
        shapes.parse(SHAPES_PATH, format="turtle")
        ok, violations, warnings, results_text = validate_graph(
            output_path, shapes, _load_ontology_graph()
        )
        print(f"SHACL input contract: {'PASS' if ok else 'FAIL'} "
              f"(violations: {violations}, warnings: {warnings})")
        if not ok:
            print(results_text)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
