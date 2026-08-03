"""Tests for the agentic motifs and risk patterns (OWASP Agentic Top 10 subset).

Two shapes distinguish an agent from a single generation call: a planning step
that can act outside the system, and a store the system writes to and reads back.
Both motifs are risk-neutral; the findings depend on what is NOT represented, so
each test pairs a positive case with a control that must suppress it.
"""

from __future__ import annotations

from airiskkg.assessment_runner import run_assessment, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.paths import EXAMPLE_DIR

EXAMPLE = EXAMPLE_DIR / "agentic_assistant.ttl"

POLICY_GATE = """
local:policyGate a beam:Process ; rdfs:label "Policy Gate" ;
    pair:playsRole pair:PolicyEnforcementStep ; beam:inform local:toolCall .
"""

MEMORY_SCREENING = """
local:memScreen a beam:Process ; rdfs:label "Memory Screening" ;
    pair:playsRole pair:MemoryValidationStep ; beam:inform local:memoryWrite .
"""


def _summary(ttl: str) -> dict:
    return summarize_result(run_assessment_from_text(ttl))


def _motifs(summary: dict) -> set[str]:
    return {m["motif"]["label"] for m in (summary["motifMatches"] or [])}


def _findings(summary: dict) -> set[str]:
    return {f["label"] for f in (summary["findings"] or [])}


def _example_ttl() -> str:
    return EXAMPLE.read_text(encoding="utf-8")


def test_agentic_example_matches_both_agentic_motifs() -> None:
    motifs = _motifs(_summary(_example_ttl()))
    assert "Tool-Using Agent Motif" in motifs
    assert "Agent Memory Loop Motif" in motifs


def test_agentic_example_produces_both_agentic_findings() -> None:
    findings = _findings(_summary(_example_ttl()))
    assert "Candidate unmediated agent tool use" in findings
    assert "Candidate agent memory poisoning" in findings


def test_mediating_control_suppresses_the_tool_misuse_finding() -> None:
    """A policy-enforcement step between planning and the action is exactly what
    the applicability condition looks for, so the finding must stop firing while
    the memory finding is left alone."""
    findings = _findings(_summary(_example_ttl() + POLICY_GATE))
    assert "Candidate unmediated agent tool use" not in findings
    assert "Candidate agent memory poisoning" in findings, "unrelated finding must survive"


def test_write_validation_suppresses_the_memory_poisoning_finding() -> None:
    findings = _findings(_summary(_example_ttl() + MEMORY_SCREENING))
    assert "Candidate agent memory poisoning" not in findings
    assert "Candidate unmediated agent tool use" in findings, "unrelated finding must survive"


def test_memory_loop_needs_the_same_store_written_and_read() -> None:
    """The motif is the loop, not merely a read. Pointing the read at a different
    store must stop it matching, otherwise it is just retrieval."""
    ttl = _example_ttl().replace(
        "    beam:use local:agentMemory ;\n    beam:produce local:recalledContext .",
        "    beam:use local:otherStore ;\n    beam:produce local:recalledContext .\n"
        "local:otherStore a beam:Data ; rdfs:label \"Other Store\" ; pair:playsRole pair:AgentMemory .",
    )
    assert "Agent Memory Loop Motif" not in _motifs(_summary(ttl))


def test_agentic_findings_are_candidates() -> None:
    """Candidate framing (Rule R1) holds for the agentic layer too."""
    result = run_assessment(EXAMPLE, write_outputs=False)
    statuses = {
        str(o)
        for _s, o in result.risk_findings.subject_objects(
            __import__("airiskkg.assessment_runner", fromlist=["PAIR"]).PAIR.findingStatus
        )
    }
    assert statuses == {"candidate"}
