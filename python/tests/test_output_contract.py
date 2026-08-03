"""Tests for the SHACL assessment-output contract (pair:findingStatus value set).

The pipeline emits candidate risk findings and nothing else: every risk query
writes the literal "candidate". The other four status values are an extension
point for later human review, so the shape has to accept them while rejecting
anything outside the closed set.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph

pytest.importorskip("pyshacl")

from pyshacl import validate as shacl_validate  # noqa: E402

from airiskkg.assessment_runner import run_assessment  # noqa: E402
from airiskkg.paths import CORE_DIR, EXAMPLE_DIR, PATTERNS_DIR, SHACL_DIR  # noqa: E402

SHAPES_PATH = SHACL_DIR / "assessment_output_contract.ttl"
ALLOWED_STATUSES = {"candidate", "confirmed", "refuted", "mitigated", "accepted"}


def _shapes() -> Graph:
    return Graph().parse(SHAPES_PATH, format="turtle")


def _ontology() -> Graph:
    ontology = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        ontology.parse(CORE_DIR / name, format="turtle")
    return ontology


def _conforms(data: Graph) -> tuple[bool, str]:
    conforms, _results, text = shacl_validate(
        data_graph=data,
        shacl_graph=_shapes(),
        ont_graph=_ontology(),
        advanced=True,
        inference="none",
    )
    return conforms, text


def test_example_assessment_output_conforms() -> None:
    """A real example's assessment output satisfies the output contract."""
    result = run_assessment(EXAMPLE_DIR / "onyx_danswer.ttl", write_outputs=False)
    assert result.risk_finding_count > 0, "expected findings to validate"
    conforms, text = _conforms(result.risk_findings)
    assert conforms, text


def test_status_outside_the_value_set_is_rejected() -> None:
    """The shape actually constrains: an out-of-set status is a violation."""
    data = Graph().parse(
        data="""
        @prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
        @prefix ex:   <http://example.org/> .
        ex:finding a pair:RiskFinding ; pair:findingStatus "probably" .
        """,
        format="turtle",
    )
    conforms, _text = _conforms(data)
    assert not conforms


def test_missing_and_duplicate_status_are_rejected() -> None:
    """Exactly one status per finding: neither zero nor two."""
    missing = Graph().parse(
        data="""
        @prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
        @prefix ex:   <http://example.org/> .
        ex:finding a pair:RiskFinding .
        """,
        format="turtle",
    )
    assert not _conforms(missing)[0]

    duplicate = Graph().parse(
        data="""
        @prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
        @prefix ex:   <http://example.org/> .
        ex:finding a pair:RiskFinding ; pair:findingStatus "candidate", "confirmed" .
        """,
        format="turtle",
    )
    assert not _conforms(duplicate)[0]


def test_every_allowed_status_is_accepted() -> None:
    """All five values of the closed set validate, so the extension point is usable."""
    for status in sorted(ALLOWED_STATUSES):
        data = Graph().parse(
            data=f"""
            @prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
            @prefix ex:   <http://example.org/> .
            ex:finding a pair:RiskFinding ; pair:findingStatus "{status}" .
            """,
            format="turtle",
        )
        conforms, text = _conforms(data)
        assert conforms, f"{status} should be allowed:\n{text}"


def test_pipeline_only_ever_writes_candidate() -> None:
    """No code path emits a status other than "candidate"; the other four values
    are set by humans downstream, never by the assessment."""
    emitted: dict[str, set[str]] = {}
    for query_path in sorted(Path(PATTERNS_DIR / "implementation").glob("*.rq")):
        text = query_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "findingStatus" not in line:
                continue
            statuses = {part.split('"')[0] for part in line.split('pair:findingStatus "')[1:]}
            if statuses:
                emitted.setdefault(query_path.name, set()).update(statuses)

    assert emitted, "expected risk queries to emit a finding status"
    offenders = {name: values for name, values in emitted.items() if values != {"candidate"}}
    assert not offenders, f"queries emitting a non-candidate status: {offenders}"
