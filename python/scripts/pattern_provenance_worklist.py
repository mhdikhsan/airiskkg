

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rdflib import DCTERMS, RDF, RDFS, Graph, URIRef  # noqa: E402

from airiskkg.assessment_runner import PAIR, load_base_graph  # noqa: E402
from airiskkg.paths import PATTERNS_DIR  # noqa: E402

DEFAULT_OUTPUT = Path("/tmp/pattern_provenance_worklist.csv")

# Where each entry type is declared, so `notes` can cite a real file path.
DECLARING_FILE = {
    "GraphMotif": PATTERNS_DIR / "motif.ttl",
    "RiskPattern": PATTERNS_DIR / "risk_pattern_library.ttl",
}

# A source string that only asserts in-house judgement is not independently
# traceable: flag it so a human can add an external citation.
UNTRACEABLE_MARKERS = ("expert curation",)


def _literal(graph: Graph, subject: URIRef, predicate: URIRef) -> str:
    value = graph.value(subject, predicate)
    return str(value) if value is not None else ""


def _repo_relative(path: Path) -> str:
    try:
        from airiskkg.paths import REPO_ROOT

        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except (ImportError, ValueError):
        return str(path)


def _is_traceable(source: str) -> bool:
    """A source is traceable when it points at something outside this repo: a URL,
    or a named external document. 'expert curation' alone does not qualify."""
    if not source:
        return False
    stripped = source.strip()
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return True
    # A composite string ("expert curation; OWASP ... 2025, LLM03") still names an
    # external document, so it is traceable; a bare marker is not.
    return stripped.lower() not in UNTRACEABLE_MARKERS


def build_rows(graph: Graph) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for type_name, rdf_type in (("GraphMotif", PAIR.GraphMotif), ("RiskPattern", PAIR.RiskPattern)):
        declared_in = _repo_relative(DECLARING_FILE[type_name])
        for subject in sorted(graph.subjects(RDF.type, rdf_type), key=str):
            source = _literal(graph, subject, DCTERMS.source)
            derived = _literal(graph, subject, PAIR.derivedFrom)
            comment = _literal(graph, subject, RDFS.comment)

            notes: list[str] = []

            if source:
                notes.append(f'dct:source already present in {declared_in}: "{source}"')
                if not _is_traceable(source):
                    notes.append("NOT independently traceable - needs an external citation")
            else:
                # dct:source is deliberately absent on entries whose origin is a
                # document rather than a semantic resource (OECD, OWASP, pattern
                # catalogues). pair:derivedFrom carries the origin for those, so
                # it counts as provenance here rather than as a gap to fill.
                if derived:
                    notes.append(f'origin via pair:derivedFrom in {declared_in}: "{derived}"')
                elif comment:
                    notes.append(f'no origin stated; rdfs:comment in {declared_in}: "{comment}"')
                else:
                    notes.append(f"no origin named in {declared_in} - fill in by hand")

            if derived and source and derived != source:
                notes.append(f'pair:derivedFrom: "{derived}"')

            rows.append(
                {
                    "uri": str(subject),
                    "type": type_name,
                    "label": _literal(graph, subject, RDFS.label),
                    "existing_source": source,
                    "origin": derived,
                    "notes": " | ".join(notes),
                }
            )
    return rows


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = build_rows(load_base_graph())
    fields = ["uri", "type", "label", "existing_source", "origin", "notes"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    motifs = [r for r in rows if r["type"] == "GraphMotif"]
    patterns = [r for r in rows if r["type"] == "RiskPattern"]
    # An entry needs a traceable origin, from either predicate. dct:source is not
    # required: it is reserved for semantic resources, and an entry derived from a
    # document states its origin with pair:derivedFrom instead.
    untraceable = [
        r
        for r in rows
        if not _is_traceable(r["existing_source"]) and not _is_traceable(r["origin"])
    ]
    print(f"wrote {len(rows)} rows to {output}")
    print(f"  motifs: {len(motifs)}  risk patterns: {len(patterns)}")
    print(f"  without a traceable origin: {len(untraceable)}")
    for row in untraceable:
        print(f"    no traceable origin: {row['label'] or row['uri']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
