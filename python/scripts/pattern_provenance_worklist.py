from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rdflib import DCTERMS, RDF, RDFS, Graph, URIRef  # noqa: E402

from airiskkg.assessment_runner import PAIR, load_base_graph  # noqa: E402
from airiskkg.paths import PATTERNS_DIR  # noqa: E402

DEFAULT_OUTPUT = Path("/tmp/pattern_provenance_worklist.csv")

DECLARING_FILE = {
    "GraphMotif": PATTERNS_DIR / "motif.ttl",
    "RiskPattern": PATTERNS_DIR / "risk_pattern_library.ttl",
}
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
    if not source:
        return False
    stripped = source.strip()
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return True
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
