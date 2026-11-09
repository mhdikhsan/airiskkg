"""What a click waits on: faster paths that must answer exactly as the slow ones did."""

from __future__ import annotations

import json

import pytest

from airiskkg.assessment_runner import load_base_graph
from airiskkg.paths import EXAMPLE_DIR
from airiskkg.workbench.scope import read_scope, scope_report, stated_notes, stated_risks, triage_decisions
from airiskkg.workbench.validation import clear_reports, known_report, shacl_report


@pytest.mark.parametrize("path", sorted(EXAMPLE_DIR.glob("*.ttl")), ids=lambda p: p.stem)
def test_the_scope_report_reads_the_same_without_a_copy(path) -> None:
    ttl = path.read_text(encoding="utf-8")
    copied = load_base_graph()
    copied.parse(data=ttl, format="turtle")
    expected = {
        "scope": read_scope(copied), "statedRisks": stated_risks(copied),
        "notes": stated_notes(copied), "triage": triage_decisions(copied),
    }
    assert json.dumps(scope_report(ttl), sort_keys=True, default=str) == json.dumps(expected, sort_keys=True, default=str)


def test_a_document_already_validated_is_answered_from_memory() -> None:
    ttl = next(EXAMPLE_DIR.glob("*.ttl")).read_text(encoding="utf-8")
    clear_reports()
    assert known_report(ttl) is None
    report = shacl_report(ttl)
    assert known_report(ttl) == report
    report["violations"].append("changed by a caller")
    assert known_report(ttl) != report, "a caller's copy reached the remembered report"
    clear_reports()
    assert known_report(ttl) is None
