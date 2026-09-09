"""The competency questions must keep answering."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "scripts"))

from run_competency_questions import (  # noqa: E402
    QUESTION_DIR,
    Question,
    assembled_graph,
    default_graphs,
    questions,
)

from airiskkg.paths import DOCS_REFERENCE_DIR  # noqa: E402

CATALOGUE = DOCS_REFERENCE_DIR / "competency_questions.md"


@pytest.fixture(scope="module")
def graph():
    assembled, _ = assembled_graph(default_graphs())
    return assembled


@pytest.fixture(scope="module")
def all_questions() -> list[Question]:
    found = questions(None)
    assert found, f"no competency questions in {QUESTION_DIR}"
    return found


def test_every_question_declares_its_identity(all_questions) -> None:
    offenders = []
    for question in all_questions:
        if not question.question:
            offenders.append(f"{question.path.name}: no '# CQnn: <question>' line")
        if not question.path.name.startswith(question.identifier):
            offenders.append(
                f"{question.path.name}: declares {question.identifier}, filename says otherwise"
            )
        if not question.scope:
            offenders.append(f"{question.path.name}: no '# Scope:' line")
    assert not offenders, "Malformed competency questions:\n" + "\n".join(offenders)


def test_identifiers_are_unique(all_questions) -> None:
    seen: dict[str, str] = {}
    duplicates = []
    for question in all_questions:
        if question.identifier in seen:
            duplicates.append(f"{question.identifier}: {seen[question.identifier]} and {question.path.name}")
        seen[question.identifier] = question.path.name
    assert not duplicates, "Duplicate competency question ids:\n" + "\n".join(duplicates)


def test_the_catalogue_lists_every_question(all_questions) -> None:
    """docs/reference/competency_questions.md is written by hand, like
    catalogue.md, so it goes stale silently unless something checks it."""
    text = CATALOGUE.read_text(encoding="utf-8")
    missing = [q.identifier for q in all_questions if f"| {q.identifier} |" not in text]
    assert not missing, (
        f"Not listed in {CATALOGUE.name}: {', '.join(missing)}"
    )


def test_every_question_answers(graph, all_questions) -> None:
    silent = []
    for question in all_questions:
        results = graph.query(question.text)
        if len(list(results)) == 0:
            silent.append(f"{question.identifier} ({question.path.name})")
    assert not silent, (
        "Competency questions that returned nothing:\n" + "\n".join(silent)
    )
