import argparse

from airiskkg.assessment_runner import print_assessment_summary, run_uc6_assessment
from airiskkg.paths import (
    DATA_DIR,
    DOCS_REFERENCE_DIR,
    EXAMPLE_DIR,
    IMPLEMENTATION_DIR,
    NOTEBOOKS_DIR,
    ONTOLOGY_DIR,
    OUTPUTS_DIR,
    PATTERNS_DIR,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    REPO_ROOT,
    TAXONOMY_DIR,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Risk Knowledge Graph project utilities.")
    parser.add_argument("command", choices=["info", "assess-uc6"], help="Command to run.")
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
        print(f"data: {DATA_DIR}")
        print(f"raw: {RAW_DATA_DIR}")
        print(f"processed: {PROCESSED_DATA_DIR}")
        print(f"notebooks: {NOTEBOOKS_DIR}")
    elif args.command == "assess-uc6":
        result = run_uc6_assessment(write_outputs=True)
        print_assessment_summary(result)


if __name__ == "__main__":
    main()
