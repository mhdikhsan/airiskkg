"""Run the competency questions and write down what the knowledge base answered."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rdflib import Graph  # noqa: E402

from airiskkg.assessment_export import build_export  # noqa: E402
from airiskkg.assessment_runner import run_assessment  # noqa: E402
from airiskkg.paths import (  # noqa: E402
    CONTEXT_EXAMPLE_DIR,
    DOCS_REFERENCE_DIR,
    EXAMPLE_DIR,
    OUTPUTS_DIR,
    REPO_ROOT,
    TAXONOMY_DIR,
)

QUESTION_DIR = DOCS_REFERENCE_DIR / "competency_questions"
PROVENANCE_DIR = TAXONOMY_DIR / "provenance"

QUESTION_RE = re.compile(r"^#\s*(CQ\d+):\s*(.*)$")
SCOPE_RE = re.compile(r"^#\s*Scope:\s*(.*)$")


class Question:
    """One .rq file: its id, its question text, its note, and the query."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.identifier = path.name.split("_")[0]
        self.question = ""
        self.scope = "library"
        note: list[str] = []
        collecting_question = False
        for line in self.text.splitlines():
            if not line.startswith("#"):
                break
            match = QUESTION_RE.match(line)
            if match:
                self.identifier, self.question = match.group(1), match.group(2).strip()
                collecting_question = True
                continue
            scope = SCOPE_RE.match(line)
            if scope:
                self.scope = scope.group(1).strip()
                collecting_question = False
                continue
            body = line.lstrip("#").strip()
            if body.startswith("Note:"):
                collecting_question = False
                note.append(body[len("Note:"):].strip())
            elif collecting_question:
                self.question = f"{self.question} {body}".strip()
            elif note:
                note.append(body)
        self.note = " ".join(part for part in note if part)


def questions(selected: list[str] | None) -> list[Question]:
    found = [Question(path) for path in sorted(QUESTION_DIR.glob("CQ*.rq"))]
    if selected:
        wanted = {name.upper() for name in selected}
        found = [q for q in found if q.identifier.upper() in wanted]
    return found


def default_graphs() -> list[Path]:
    """Every architecture and process model the repository ships."""
    return sorted(EXAMPLE_DIR.glob("*.ttl")) + sorted(CONTEXT_EXAMPLE_DIR.glob("*.ttl"))


def assembled_graph(graph_paths: list[Path]) -> tuple[Graph, dict[str, int]]:
    result = run_assessment(graph_paths, write_outputs=False)
    graph = result.working_graph
    for triple in build_export(result).graph:
        graph.add(triple)
    for path in sorted(PROVENANCE_DIR.glob("*.ttl")):
        graph.parse(path, format="turtle")
    counts = {
        "matches": result.motif_match_count,
        "findings": result.risk_finding_count,
        "triples": len(graph),
    }
    return graph, counts


def answer(graph: Graph, question: Question) -> tuple[list[str], list[tuple]]:
    results = graph.query(question.text)
    columns = [str(var) for var in results.vars or []]
    rows = [tuple("" if value is None else str(value) for value in row) for row in results]
    return columns, sorted(rows)


def _cell(value: str, width: int = 60) -> str:
    value = value.replace("|", "\\|").replace("\n", " ")
    return value if len(value) <= width else value[: width - 1] + "\u2026"


def _table(columns: list[str], rows: list[tuple], limit: int) -> str:
    if not rows:
        return "_No rows. The graph this ran on says nothing about this question._\n"
    shown = rows[:limit]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines += ["| " + " | ".join(_cell(value) for value in row) + " |" for row in shown]
    if len(rows) > limit:
        lines.append(f"\n_{len(rows) - limit} further rows not shown._")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "graphs",
        nargs="*",
        help="Architecture and process graphs to answer over. Default: everything "
        "in ontology/example/ and ontology/example/context/.",
    )
    parser.add_argument("--cq", action="append", help="Answer only these (e.g. --cq CQ05).")
    parser.add_argument("--limit", type=int, default=8, help="Rows per answer in the report.")
    parser.add_argument(
        "--output",
        default=OUTPUTS_DIR / "competency_questions_report.md",
        help="Where to write the report (default: outputs/competency_questions_report.md).",
    )
    args = parser.parse_args(argv)

    selected = questions(args.cq)
    if not selected:
        print(f"No competency questions found in {QUESTION_DIR}", file=sys.stderr)
        return 1

    graph_paths = [Path(value) for value in args.graphs] or default_graphs()
    graph, counts = assembled_graph(graph_paths)

    report = [
        "# Competency question answers",
        "",
        "Generated by `python python/scripts/run_competency_questions.py`. The queries "
        "are in `docs/reference/competency_questions/`; this file is what they returned.",
        "",
        "Answered over:",
        "",
        *[f"- `{path.relative_to(REPO_ROOT).as_posix()}`" for path in graph_paths],
        "",
        f"{counts['matches']} motif matches, {counts['findings']} candidate findings, "
        f"{counts['triples']} triples in the assembled graph.",
        "",
    ]

    empty = []
    for question in selected:
        columns, rows = answer(graph, question)
        if not rows:
            empty.append(question.identifier)
        print(f"{question.identifier}  {len(rows):>5} rows  {question.question[:70]}")
        report += [
            f"## {question.identifier}: {question.question}",
            "",
            f"*Scope: {question.scope}. Query: "
            f"`{question.path.relative_to(REPO_ROOT).as_posix()}`. {len(rows)} rows.*",
            "",
        ]
        if question.note:
            report += [f"> {question.note}", ""]
        report += [_table(columns, rows, args.limit), ""]

    output = Path(args.output)
    if not output.is_absolute():
        output = REPO_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(report), encoding="utf-8")

    print(f"\n{len(selected)} questions answered, report written to {output}")
    if empty:
        # Not a failure by itself - a gap question is supposed to be able to
        # come back empty - but it is the first thing to look at when a query
        # has drifted from the vocabulary.
        print(f"Empty answers: {', '.join(empty)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
