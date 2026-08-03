"""Export the pattern-role vocabulary with its provenance, for review.

One row per pair:PatternRole:

    uri, label, parent_role, applies_to, definition, source, external_mappings,
    used_by_motifs, used_by_queries

Every column is read from triples already in the ontology (or, for the usage
columns, from the motif declarations and the SPARQL implementation files).
Nothing is inferred or invented: a role with no source is reported with an
empty source rather than an attributed guess.

`used_by_motifs` / `used_by_queries` show a role's operational reach - a role
no motif or query can ever bind is documentation only, which is exactly the
kind of thing a review should surface.

Usage:  python python/scripts/role_provenance_export.py [OUTPUT_CSV]
        (default output: /tmp/role_provenance.csv)
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from rdflib import DCTERMS, RDF, SKOS, Graph, URIRef

from airiskkg.assessment_runner import PAIR, load_base_graph
from airiskkg.paths import PATTERNS_DIR

DEFAULT_OUTPUT = Path("/tmp/role_provenance.csv")
MAPPING_PREDICATES = (SKOS.closeMatch, SKOS.relatedMatch, SKOS.broadMatch, SKOS.narrowMatch)


def _text(graph: Graph, subject: URIRef, predicate: URIRef) -> str:
    value = graph.value(subject, predicate)
    return str(value) if value is not None else ""


def _label(graph: Graph, subject: URIRef) -> str:
    return _text(graph, subject, SKOS.prefLabel) or str(subject).rsplit("#", 1)[-1]


def _short(term: object) -> str:
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _top_level(graph: Graph, role: URIRef) -> URIRef | None:
    """The role's top-level ancestor, mirroring the webapp's grouping."""
    tops: set[URIRef] = set()
    seen = {role}
    queue = [role]
    while queue:
        node = queue.pop()
        parents = [p for p in graph.objects(node, PAIR.subRoleOf) if isinstance(p, URIRef)]
        if not parents:
            tops.add(node)
            continue
        for parent in parents:
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)
    return sorted(tops, key=str)[0] if tops else None


def build_rows(graph: Graph) -> list[dict[str, str]]:
    # which motifs reference each role through a pattern node
    motif_of_node: dict[URIRef, set[str]] = {}
    for motif in graph.subjects(RDF.type, PAIR.GraphMotif):
        motif_label = _text(graph, motif, SKOS.prefLabel) or _short(motif)
        for pattern_node in graph.objects(motif, PAIR.hasPatternNode):
            role = graph.value(pattern_node, PAIR.expectedRole)
            if role is not None:
                motif_of_node.setdefault(role, set()).add(motif_label)

    query_text = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((PATTERNS_DIR / "implementation").rglob("*.rq"))
    }

    def ancestors(role: URIRef) -> list[URIRef]:
        out: list[URIRef] = []
        seen = {role}
        queue = [role]
        while queue:
            for parent in graph.objects(queue.pop(), PAIR.subRoleOf):
                if isinstance(parent, URIRef) and parent not in seen:
                    seen.add(parent)
                    out.append(parent)
                    queue.append(parent)
        return out

    def named_anywhere(role: URIRef) -> bool:
        name = _short(role)
        return role in motif_of_node or any(
            re.search(r"pair:" + re.escape(name) + r"\b", text) for text in query_text.values()
        )

    rows: list[dict[str, str]] = []
    for role in sorted(graph.subjects(RDF.type, PAIR.PatternRole), key=str):
        name = _short(role)
        parent = graph.value(role, PAIR.subRoleOf)
        top = _top_level(graph, role)
        mappings = sorted(
            str(target)
            for predicate in MAPPING_PREDICATES
            for target in graph.objects(role, predicate)
        )
        naming = sorted(
            filename
            for filename, text in query_text.items()
            if re.search(r"pair:" + re.escape(name) + r"\b", text)
        )
        rows.append(
            {
                "uri": str(role),
                "label": _label(graph, role),
                "parent_role": _short(parent) if parent is not None else "",
                "applies_to": _short(top) if top is not None else "",
                "definition": _text(graph, role, SKOS.definition),
                "source": _text(graph, role, DCTERMS.source),
                "external_mappings": " ; ".join(mappings),
                "used_by_motifs": " ; ".join(sorted(motif_of_node.get(role, ()))),
                "used_by_queries": " ; ".join(naming),
                # Queries traverse pair:playsRole/pair:subRoleOf*, so a role that
                # is never named directly still binds through a named ancestor.
                # Without this column the usage columns read as "does nothing",
                # which would be wrong for e.g. RerankerModel (binds via Model).
                "binds_via_ancestor": " ; ".join(
                    _short(a) for a in ancestors(role) if named_anywhere(a)
                ) if not named_anywhere(role) else "",
            }
        )
    return rows


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)

    graph = load_base_graph()
    rows = build_rows(graph)
    fields = [
        "uri", "label", "parent_role", "applies_to", "definition", "source",
        "external_mappings", "used_by_motifs", "used_by_queries", "binds_via_ancestor",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    no_source = [r for r in rows if not r["source"]]
    no_definition = [r for r in rows if not r["definition"]]
    no_mapping = [r for r in rows if not r["external_mappings"]]
    not_named = [r for r in rows if not r["used_by_motifs"] and not r["used_by_queries"]]
    inert = [r for r in not_named if not r["binds_via_ancestor"]]
    print(f"wrote {len(rows)} roles to {output}")
    print(f"  without dct:source:        {len(no_source)}")
    print(f"  without skos:definition:   {len(no_definition)}")
    print(f"  without external mapping:  {len(no_mapping)}")
    print(f"  not named directly:        {len(not_named)} "
          f"(of which {len(not_named) - len(inert)} still bind via an ancestor)")
    print(f"  cannot influence any match: {len(inert)}")
    for row in inert:
        print(f"    inert: {row['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
