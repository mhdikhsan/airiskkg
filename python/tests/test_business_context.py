"""The business process layer: a control that lives in the process, not the pipeline.

Three claims, and each is a test below.

  1. The layer is additive. An architecture assessed alone gives exactly what it
     gave before the layer existed. This is the property everything else rests
     on - a context layer that silently moved the baseline would make every
     recorded assessment incomparable with every later one.
  2. A human review expressed only in the business process clears a finding the
     architecture cannot clear, without asserting anything into the architecture
     and without a negative facet condition (R10).
  3. It clears it for the right reasons. "Findings went down" proves nothing on
     its own: a condition that is merely too permissive clears just as
     thoroughly as a correct one.
"""

from __future__ import annotations

from collections import Counter

import pytest
from rdflib import RDF, Graph

from airiskkg.assessment_runner import PAIR, load_base_graph, run_assessment
from airiskkg.paths import EXAMPLE_DIR
from conftest import ONYX_NS, example_path  # noqa: E402

PROCESS = EXAMPLE_DIR / "context" / "onyx_support_process.ttl"
IMPROPER_OUTPUT = "ImproperOutputHandlingRiskPattern"


def _short(term) -> str:
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _findings_by_pattern(result) -> Counter:
    counts: Counter = Counter()
    for finding in result.risk_findings.subjects(RDF.type, PAIR.RiskFinding):
        counts[_short(result.risk_findings.value(finding, PAIR.generatedByRiskPattern))] += 1
    return counts


@pytest.fixture(scope="module")
def architecture_only():
    return run_assessment(example_path(ONYX_NS), write_outputs=False)


@pytest.fixture(scope="module")
def with_process():
    return run_assessment([example_path(ONYX_NS), PROCESS], write_outputs=False)


def test_the_bridge_vocabulary_is_loaded_and_declared() -> None:
    """The context module and the vendored sBPMN ontology both reach the graph."""
    graph = load_base_graph()

    assert (PAIR.refinedBy, RDF.type, None) in graph
    assert (PAIR.businessFollows, RDF.type, None) in graph
    from rdflib import OWL, URIRef

    assert (URIRef("https://sBPMN.github.io/2.0/classes#userTask"), RDF.type, OWL.Class) in graph


def test_a_bpmn_activity_is_not_a_beam_process() -> None:
    """The layering mistake that would undo the whole idea. Every match query
    types its step as `a/rdfs:subClassOf* beam:Process`, so subsuming activities
    under it would make every business activity a candidate motif node - and the
    input contract, which requires each beam:Process to use or produce a
    resource, would reject every process model outright."""
    from rdflib import RDFS, URIRef

    graph = load_base_graph()
    beam_process = URIRef("http://w3id.org/beam/core#Process")
    activity = URIRef("https://sBPMN.github.io/2.0/classes#activity")

    assert beam_process not in set(graph.transitive_objects(activity, RDFS.subClassOf))


def test_the_architecture_alone_is_unchanged(architecture_only) -> None:
    """The baseline the whole library is measured against."""
    assert architecture_only.motif_match_count == 14
    assert architecture_only.risk_finding_count == 22


def test_context_carries_no_flow_facts_of_its_own(architecture_only) -> None:
    """Nothing is derived over a process that was never submitted."""
    derived = list(architecture_only.working_graph.triples((None, PAIR.businessFollows, None)))
    assert derived == []


def test_business_flow_closes_transitively(with_process) -> None:
    """Five activities in a chain: four sequence flows, ten reachable pairs.

    A gateway or an intervening step between the AI activity and a later control
    must not hide it, and SPARQL cannot type the nodes a property path passes
    through - so the closure is built by the derivation loop instead."""
    derived = list(with_process.working_graph.triples((None, PAIR.businessFollows, None)))
    assert len(derived) == 10


def test_a_review_in_the_process_clears_what_the_pipeline_cannot(
    architecture_only, with_process
) -> None:
    before = _findings_by_pattern(architecture_only)
    after = _findings_by_pattern(with_process)

    assert before[IMPROPER_OUTPUT] == 4
    assert after[IMPROPER_OUTPUT] == 0

    # Onyx has one generation step and one user-facing output; the finding fires
    # four times because that step binds in four motif matches. They share a
    # sink, so they clear together - and nothing else moves.
    assert with_process.motif_match_count == architecture_only.motif_match_count
    for pattern in set(before) | set(after):
        if pattern != IMPROPER_OUTPUT:
            assert before[pattern] == after[pattern], f"{pattern} moved unexpectedly"


def test_the_architecture_gains_no_triples_from_being_reviewed(with_process) -> None:
    """The review clears the finding by being represented, not by being written
    into the pipeline. No control step is invented."""
    architecture = Graph().parse(example_path(ONYX_NS), format="turtle")
    steps_before = set(architecture.subjects(PAIR.playsRole, None))
    steps_after = {
        subject
        for subject in with_process.working_graph.subjects(PAIR.playsRole, None)
        if str(subject).startswith(ONYX_NS)
    }
    assert steps_after == steps_before


# --- the escape must be precise, not merely permissive -----------------------

MUTATIONS = {
    "the review is a serviceTask, not a userTask": (
        "proc:ReviewAnswer a bpmn:userTask ;",
        "proc:ReviewAnswer a bpmn:serviceTask ;",
    ),
    "nobody performs the review": (
        "    bp:resourceRole proc:AgentReviewer .",
        "    .",
    ),
    "the review never reads the drafted answer": (
        "    bp:dataInputAssociation proc:DraftIn ;\n",
        "",
    ),
    "the review happens before the AI drafts": (
        "    bp:sourceRef proc:DraftAnswer ;     bp:targetRef proc:ReviewAnswer .",
        "    bp:sourceRef proc:ReviewAnswer ;    bp:targetRef proc:DraftAnswer .",
    ),
    "the activity is not linked to the system": (
        "    pair:refinedBy onyx:OnyxSystem ;\n",
        "",
    ),
}


@pytest.mark.parametrize("description", sorted(MUTATIONS))
def test_breaking_one_thing_the_escape_requires_brings_the_finding_back(description) -> None:
    """Each mutation breaks exactly one claim the escape makes. The fourth is the
    one that matters: "close the ticket" is also a later human task, and it must
    not count as having reviewed anything."""
    original, replacement = MUTATIONS[description]
    process = PROCESS.read_text(encoding="utf-8")
    assert original in process, f"the example no longer contains: {original!r}"

    graph = load_base_graph()
    graph.parse(example_path(ONYX_NS), format="turtle")
    graph.parse(data=process.replace(original, replacement), format="turtle")

    from airiskkg.assessment_runner import _run_assessment_on_graph

    result = _run_assessment_on_graph(graph, write_outputs=False, output_dir=".")
    assert _findings_by_pattern(result)[IMPROPER_OUTPUT] == 4, (
        f"the escape still fired after breaking: {description}"
    )
