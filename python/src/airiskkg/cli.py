import argparse

from airiskkg.assessment_runner import print_assessment_summary, run_assessment
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
        nargs="+",
        help="Architecture graph TTL file(s) to assess.",
    )
    assess_parser.add_argument(
        "--output-dir",
        default=OUTPUTS_DIR,
        help="Base directory for run output. Each run writes into an auto-numbered "
        "subdirectory (output_1, output_2, ...) containing motif_matches.ttl, "
        "risk_findings.ttl, and combined_assessment_graph.ttl.",
    )

    serve_parser = subparsers.add_parser("serve", help="Launch the web UI for risk assessment.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default 127.0.0.1).")
    serve_parser.add_argument("--port", type=int, default=5000, help="Port to bind (default 5000).")
    serve_parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")
    serve_parser.add_argument(
        "--no-local-examples",
        action="store_true",
        help="Do not offer graphs from ontology/example_local/. They are offered "
        "by default here because this command is a local run; a WSGI server "
        "importing the app never offers them.",
    )

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
            args.architecture_graph,
            write_outputs=True,
            output_dir=args.output_dir,
        )
        print_assessment_summary(result)
    elif args.command == "serve":
        from airiskkg.paths import EXAMPLE_LOCAL_DIR
        from airiskkg.webapp import create_app

        local_examples = not args.no_local_examples
        app = create_app(local_examples=local_examples)
        print(f"PAIR-AI risk assessment UI running at http://{args.host}:{args.port}")
        if local_examples:
            count = len(list(EXAMPLE_LOCAL_DIR.glob("*.ttl"))) if EXAMPLE_LOCAL_DIR.is_dir() else 0
            # Say it out loud: these graphs may be confidential, and binding to a
            # non-loopback host puts them on the network.
            print(
                f"Offering {count} local graph(s) from {EXAMPLE_LOCAL_DIR} "
                "(--no-local-examples to hide them)"
            )
        app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
