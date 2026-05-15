import argparse

from airiskkg.assessment_runner import print_assessment_summary, run_assessment, run_uc6_assessment
from airiskkg.paths import (
    DOCS_REFERENCE_DIR,
    EXAMPLE_DIR,
    IMPLEMENTATION_DIR,
    ONTOLOGY_DIR,
    OUTPUTS_DIR,
    PATTERNS_DIR,
    REPO_ROOT,
    TAXONOMY_DIR,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Risk Knowledge Graph project utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("info", help="Print project paths.")

    assess_parser = subparsers.add_parser("assess", help="Run PAIR-AI assessment for architecture graph TTL files.")
    assess_parser.add_argument(
        "architecture_graph",
        nargs="*",
        help="Architecture graph TTL file(s). Defaults to ontology/example/uc6.ttl.",
    )
    assess_parser.add_argument(
        "--output-dir",
        default=OUTPUTS_DIR,
        help="Directory for motif_matches.ttl, risk_findings.ttl, and combined_assessment_graph.ttl.",
    )

    subparsers.add_parser("assess-uc6", help="Run the UC6 example assessment.")
    args = parser.parse_args()

    if args.command == "info":
        print("AI Risk Knowledge Graph")
        print(f"repo: {REPO_ROOT}")
        print(f"ontology: {ONTOLOGY_DIR}")
        print(f"core: {ONTOLOGY_DIR / 'core'}")
        print(f"patterns: {PATTERNS_DIR}")
        print(f"implementation: {IMPLEMENTATION_DIR}")
        print(f"taxonomy: {TAXONOMY_DIR}")
        print(f"example: {EXAMPLE_DIR}")
        print(f"outputs: {OUTPUTS_DIR}")
        print(f"docs reference: {DOCS_REFERENCE_DIR}")
    elif args.command == "assess":
        result = run_assessment(
            args.architecture_graph or None,
            write_outputs=True,
            output_dir=args.output_dir,
        )
        print_assessment_summary(result)
    elif args.command == "assess-uc6":
        result = run_uc6_assessment(write_outputs=True)
        print_assessment_summary(result)


if __name__ == "__main__":
    main()
