"""Annotation-guidance shapes: do they catch the mistakes that lose findings?

These shapes answer a question neither contract asks. The input contract asks
whether a graph is acceptable; the output contract asks whether emitted findings
are well formed. Neither asks whether an annotation will actually match
anything - and a graph can satisfy the input contract completely while producing
zero findings, at which point silence reads as safety.

Two properties are tested here and both matter:

  1. Each shape fires on the mistake it names.
  2. No shape is a Violation, and the curated examples raise nothing. A guidance
     layer that cries wolf on the repository's own examples would be trained
     away within a week.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.assessment_runner import load_base_graph  # noqa: E402
from airiskkg.paths import EXAMPLE_DIR, SHACL_DIR  # noqa: E402

SH = Namespace("http://www.w3.org/ns/shacl#")
GUIDANCE_PATH = SHACL_DIR / "annotation_guidance.ttl"

PREAMBLE = """
@prefix ex:   <http://example.org/guidance#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
ex:sys a beam:System .
"""


@pytest.fixture(scope="module")
def shapes() -> Graph:
    return Graph().parse(GUIDANCE_PATH, format="turtle")


@pytest.fixture(scope="module")
def ontology() -> Graph:
    """The role hierarchy: every shape walks pair:subRoleOf*."""
    return load_base_graph()


def _messages(shapes: Graph, ontology: Graph, turtle: str) -> list[tuple[str, str]]:
    data = Graph().parse(data=PREAMBLE + turtle, format="turtle")
    _conforms, results, _text = validate(
        data_graph=data + ontology,
        shacl_graph=shapes,
        advanced=True,
        inference="none",
    )
    out = []
    for result in results.subjects(SH.resultSeverity, None):
        focus = results.value(result, SH.focusNode)
        message = results.value(result, SH.resultMessage)
        out.append((str(focus).rsplit("#", 1)[-1], str(message)))
    return out


def _fired_on(reports: list[tuple[str, str]], node: str, phrase: str) -> bool:
    return any(focus == node and phrase in message for focus, message in reports)


def test_no_guidance_shape_is_a_violation(shapes: Graph) -> None:
    """The whole point is that these are advisory. A Violation here would make
    the input contract reject graphs it is documented to accept."""
    severities = set(shapes.objects(None, SH.severity))
    assert severities, "shapes declare no severity at all"
    assert SH.Violation not in severities, "guidance shapes must never be Violations"
    assert severities <= {SH.Warning, SH.Info}


def test_step_role_with_no_process_class_at_all_is_flagged(shapes, ontology) -> None:
    """An untyped step is always a mistake: no query can bind it, whichever
    convention that query follows."""
    reports = _messages(
        shapes, ontology, "ex:gen a beam:Data ; pair:playsRole pair:GenerationStep ."
    )
    assert _fired_on(reports, "gen", "no class from the process family")


def test_leaf_typed_step_is_not_flagged(shapes, ontology) -> None:
    """Any process-family typing is now equivalent.

    Step nodes match on `a/rdfs:subClassOf* beam:Process`, so beam:Infer alone
    binds exactly as beam:Process does. The shape that used to nudge modelers to
    dual-type was retired with that unification - keeping it would advise a
    workaround for a problem that no longer exists."""
    reports = _messages(
        shapes, ontology, "ex:gen a beam:Infer ; pair:playsRole pair:GenerationStep ."
    )
    assert not _fired_on(reports, "gen", "no class from the process family")
    assert not _fired_on(reports, "gen", "beam:Process")


def test_dual_typed_step_is_not_flagged(shapes, ontology) -> None:
    reports = _messages(
        shapes,
        ontology,
        """
        ex:llm a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
        ex:gen a beam:Infer, beam:Process ; pair:playsRole pair:GenerationStep ;
            beam:use ex:llm .
        """,
    )
    assert not _fired_on(reports, "gen", "beam:Process")


def test_resource_role_on_a_process_is_flagged(shapes, ontology) -> None:
    reports = _messages(
        shapes, ontology, "ex:weird a beam:Process ; pair:playsRole pair:VectorStore ."
    )
    assert _fired_on(reports, "weird", "plays a resource role but is typed beam:Process")


def test_unretrieved_vector_store_is_flagged(shapes, ontology) -> None:
    reports = _messages(
        shapes, ontology, "ex:store a beam:Data ; pair:playsRole pair:VectorStore ."
    )
    assert _fired_on(reports, "store", "not used by any retrieval step")


def test_one_way_agent_memory_is_flagged(shapes, ontology) -> None:
    """ASI06 is constituted by the loop, so a write-only store cannot raise it."""
    reports = _messages(
        shapes,
        ontology,
        """
        ex:mem a beam:Data ; pair:playsRole pair:AgentMemory .
        ex:writer a beam:Process ; pair:playsRole pair:MemoryWriteStep ;
            beam:produce ex:mem .
        """,
    )
    assert _fired_on(reports, "mem", "only written or only read")


def test_looped_agent_memory_is_not_flagged(shapes, ontology) -> None:
    reports = _messages(
        shapes,
        ontology,
        """
        ex:mem a beam:Data ; pair:playsRole pair:AgentMemory ;
            pair:containsDataCategory pair:Information .
        ex:writer a beam:Process ; pair:playsRole pair:MemoryWriteStep ;
            beam:produce ex:mem .
        ex:reader a beam:Process ; pair:playsRole pair:MemoryReadStep ;
            beam:use ex:mem .
        """,
    )
    assert not _fired_on(reports, "mem", "only written or only read")


def test_unreceived_agent_message_is_flagged(shapes, ontology) -> None:
    reports = _messages(
        shapes, ontology, "ex:msg a beam:Data ; pair:playsRole pair:AgentMessage ."
    )
    assert _fired_on(reports, "msg", "not consumed by any step")


def test_generation_step_without_a_model_is_flagged(shapes, ontology) -> None:
    reports = _messages(
        shapes,
        ontology,
        "ex:gen a beam:Infer, beam:Process ; pair:playsRole pair:GenerationStep .",
    )
    assert _fired_on(reports, "gen", "uses no element playing pair:GenerativeModel")


def test_curated_examples_raise_no_guidance_warnings(shapes, ontology) -> None:
    """The examples are what a modeler is shown as correct. If the guidance layer
    warned about them, it would be teaching the opposite of what it intends.

    Info-level hints are allowed here - "this data element carries no role" is
    legitimately true of incidental elements in a real architecture. Warnings
    are not: those name annotations that cannot work."""
    offenders = []
    for path in (
        EXAMPLE_DIR / "onyx_danswer.ttl",
        EXAMPLE_DIR / "rag_with_guardrails.ttl",
        EXAMPLE_DIR / "agentic_assistant.ttl",
        EXAMPLE_DIR / "multi_agent_assistant.ttl",
    ):
        data = Graph().parse(path, format="turtle")
        _conforms, results, _text = validate(
            data_graph=data + ontology,
            shacl_graph=shapes,
            advanced=True,
            inference="none",
        )
        for result in results.subjects(SH.resultSeverity, SH.Warning):
            focus = results.value(result, SH.focusNode)
            message = results.value(result, SH.resultMessage)
            offenders.append(f"{path.name}: {focus} - {message}")
    assert not offenders, "curated examples raise guidance warnings:\n" + "\n".join(offenders)


def test_guidance_never_changes_whether_a_graph_conforms(shapes, ontology) -> None:
    """Belt and braces on the severity test: a graph full of guidance triggers
    still conforms, because conformance is a Violation-level notion."""
    data = Graph().parse(
        data=PREAMBLE
        + """
        ex:gen a beam:Data ; pair:playsRole pair:GenerationStep .
        ex:store a beam:Data ; pair:playsRole pair:VectorStore .
        ex:orphan a beam:Data .
        """,
        format="turtle",
    )
    _conforms, results, _text = validate(
        data_graph=data + ontology,
        shacl_graph=shapes,
        advanced=True,
        inference="none",
    )
    assert list(results.subjects(SH.resultSeverity, SH.Violation)) == []
    assert list(results.subjects(SH.resultSeverity, None)), "expected advisory results"
