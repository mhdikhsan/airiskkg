"""Normalize a Tool4Boxology N-Triples export into a BEAM architecture graph.

CLI wrapper around airiskkg.t4b_import (shared with the workbench's
"Import Tool4Boxology" endpoint). See that module's docstring for the
normalization steps.

Usage:
    python python/scripts/normalize_t4b.py <export.nt> [-o <out.ttl>] [--skip-validation]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rdflib import Graph

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.paths import REPO_ROOT  # noqa: E402
from airiskkg.t4b_import import normalize  # noqa: E402,F401 - re-exported for test_t4b_roundtrip.py


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
