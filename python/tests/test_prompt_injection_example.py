"""The conceptual example behind the prompt-injection figure.

Four minimal systems, each making one point about how a candidate risk is
raised. The figure in the paper is drawn from this run, so every claim it makes
is asserted here: if the library changes, the drawing stops matching and this
suite says so rather than the reader noticing.

The two contrasts the figure rests on:

* A and D share a motif and differ only in a data category. Same four boxes,
  same three edges; prompt injection is raised on one and not the other. That
  is the applicability condition doing the work, not the structure.
* A and B share a risk pattern and differ in the motif carrying it. The direct
  and indirect kinds are one risk pattern reached two ways, and the difference
  is which element the untrusted content was annotated on.
* A carries two categories, and each is read by a different risk pattern over
  the same match. A candidate risk does not stop at the vulnerability that
  raised it.
"""

from __future__ import annotations

import pytest
from rdflib import RDFS, Graph, Namespace, URIRef

from airiskkg.assessment_runner import PAIR, run_assessment_from_text
from airiskkg.assessment_view import summarize_result
from airiskkg.workbench.risk_view import risk_view
from conftest import PROMPT_INJECTION_NS, example_path

BEAM = Namespace("http://w3id.org/beam/core#")
PAT = Namespace("http://w3id.org/airiskkg/patterns#")
EX = Namespace(PROMPT_INJECTION_NS)

MEMBERSHIP = (BEAM.hasProcess, BEAM.hasResource, BEAM.hasAgent, BEAM.contain)
INJECTION = "Candidate prompt injection"
UNGROUNDED = "Candidate Direct Prompting without grounding"
DISCLOSURE = "Candidate sensitive information disclosure"

DIRECT = "A — Direct assistant"
GROUNDED = "B — Grounded assistant"
SCREENED = "C — Screened assistant"
INTERNAL = "D — Internal summariser"


@pytest.fixture(scope="module")
def scene() -> dict:
    ttl = example_path(PROMPT_INJECTION_NS).read_text(encoding="utf-8")
    result = run_assessment_from_text(ttl)
    summary = summarize_result(result)
    return {
        "ttl": ttl,
        "graph": result.combined_graph,
        "summary": summary,
        "view": risk_view(summary, result.combined_graph, result=result),
    }


def _system_of(graph: Graph, element: str) -> str:
    for predicate in MEMBERSHIP:
        for system in graph.subjects(predicate, URIRef(element)):
            return str(graph.value(system, RDFS.label) or system)
    return "?"


def _raised(scene: dict, system: str) -> set[str]:
    """The labels raised anywhere inside one system."""
    graph = scene["graph"]
    return {
        finding["label"]
        for finding in scene["summary"]["findings"]
        if any(_system_of(graph, e["id"]) == system for e in finding["evidence"])
    }


# ---- the same motif, two different contexts ----


def test_a_and_d_are_the_same_structure(scene) -> None:
    """If the two systems stopped matching the same motif, the contrast the
    figure draws would be about structure after all."""
    graph = scene["graph"]
    per_system: dict[str, set[str]] = {}
    for match in scene["summary"]["motifMatches"]:
        for bound in match["boundElements"]:
            holder = _system_of(graph, bound["elementId"])
            per_system.setdefault(holder, set()).add(match["motif"]["label"])
    assert per_system[DIRECT] == {"Direct Prompting Motif"}
    assert per_system[INTERNAL] == {"Direct Prompting Motif"}


def test_the_data_category_alone_decides_prompt_injection(scene) -> None:
    """A carries Untrusted Content on its input and D does not. Nothing else
    differs, and only A is raised."""
    assert INJECTION in _raised(scene, DIRECT)
    assert INJECTION not in _raised(scene, INTERNAL)


def test_the_same_motif_still_raises_the_risk_that_is_about_its_shape(scene) -> None:
    """A motif is risk-neutral, but Direct Prompting without grounding is about
    the structure rather than the content, so it is raised on both."""
    assert UNGROUNDED in _raised(scene, DIRECT)
    assert UNGROUNDED in _raised(scene, INTERNAL)


# ---- direct and indirect are one risk pattern, reached two ways ----


def test_untrusted_content_is_annotated_in_three_places_only(scene) -> None:
    stated = Graph().parse(data=scene["ttl"], format="turtle")
    assert {str(e) for e in stated.subjects(PAIR.containsDataCategory, PAIR.UntrustedContent)} == {
        str(EX.A_Question),
        str(EX.B_DocumentStore),
        str(EX.C_Question),
    }


def test_the_category_travels_to_the_prompt_it_was_never_annotated_on(scene) -> None:
    """Indirect injection is this propagation: the modeller marked the document
    store, and the retrieved passages and the assembled prompt inherit it."""
    after = {
        str(e) for e in scene["graph"].subjects(PAIR.containsDataCategory, PAIR.UntrustedContent)
    }
    assert {str(EX.B_Context), str(EX.B_Prompt)} <= after
    assert str(EX.D_Note) not in after


def test_one_risk_pattern_is_reached_through_two_different_motifs(scene) -> None:
    """The direct kind arrives over Direct Prompting, the indirect kind over
    retrieval. Same pattern, same mechanism, same OWASP entry."""
    graph = scene["graph"]
    by_system: dict[str, set[str]] = {}
    for finding in scene["summary"]["findings"]:
        if finding["label"] != INJECTION:
            continue
        for element in finding["evidence"]:
            holder = _system_of(graph, element["id"])
            if holder != "?":
                by_system.setdefault(holder, set()).add(finding["motif"]["label"])
    assert by_system[DIRECT] == {"Direct Prompting Motif"}
    assert "Retrieval Augmented Generation (RAG) Motif" in by_system[GROUNDED]


def test_both_kinds_carry_the_same_curated_explanation(scene) -> None:
    injections = [f for f in scene["summary"]["findings"] if f["label"] == INJECTION]
    assert len(injections) >= 2
    assert {f["mechanism"]["label"] for f in injections} == {
        "Instruction override by untrusted context"
    }
    assert {d["label"] for f in injections for d in f["riskDomains"]} == {"Privacy & Security"}
    assert all(
        "LLM01:2025 Prompt Injection" in {t["label"] for t in f["taxonomyEntries"]}
        for f in injections
    )


# ---- the risk extends when another category is present ----


def test_a_second_category_on_the_same_path_raises_a_second_risk(scene) -> None:
    """The customer question is untrusted and personal. Two risk patterns read
    the same four elements and reach different harms."""
    raised = _raised(scene, DIRECT)
    assert {INJECTION, DISCLOSURE} <= raised
    assert DISCLOSURE not in _raised(scene, INTERNAL), (
        "D carries no protected category, so nothing should disclose"
    )


def test_the_two_risks_are_distinct_all_the_way_down(scene) -> None:
    """Same motif, same evidence path, different mechanism and different entry:
    if either collapsed into the other the extension claim would be empty."""
    pair_of = {
        finding["label"]: finding
        for finding in scene["summary"]["findings"]
        if finding["label"] in {INJECTION, DISCLOSURE}
        and any(_system_of(scene["graph"], e["id"]) == DIRECT for e in finding["evidence"])
    }
    assert set(pair_of) == {INJECTION, DISCLOSURE}
    assert pair_of[INJECTION]["motif"]["label"] == pair_of[DISCLOSURE]["motif"]["label"]
    assert pair_of[INJECTION]["mechanism"]["label"] != pair_of[DISCLOSURE]["mechanism"]["label"]
    entries = {
        label: {t["label"] for t in finding["taxonomyEntries"]}
        for label, finding in pair_of.items()
    }
    assert "LLM01:2025 Prompt Injection" in entries[INJECTION]
    assert "LLM02:2025 Sensitive Information Disclosure" in entries[DISCLOSURE]


def test_the_protected_category_reaches_the_reader_by_propagation(scene) -> None:
    """Nobody annotated the answer. It is personal because the step that
    produced it read something personal."""
    stated = Graph().parse(data=scene["ttl"], format="turtle")
    assert (URIRef(EX.A_Answer), PAIR.containsDataCategory, PAIR.SensitiveInformation) not in stated
    after = {
        str(e) for e in scene["graph"].subjects(PAIR.containsDataCategory, PAIR.SensitiveInformation)
    }
    assert {str(EX.A_Question), str(EX.A_Answer)} <= after


# ---- a control clears it by being built ----


def test_screening_clears_the_injection_and_nothing_else(scene) -> None:
    """C is A with one guardrail step added. The escape in the risk query is
    satisfied, so the candidate is not raised - while the risks that guardrail
    does not address stay."""
    screened = _raised(scene, SCREENED)
    assert INJECTION not in screened
    assert UNGROUNDED in screened


def test_the_guardrail_is_visible_as_structure(scene) -> None:
    """It clears the finding by being in the graph as a matched motif, not by
    anyone asserting that the risk was handled."""
    graph = scene["graph"]
    screening = {
        match["motif"]["label"]
        for match in scene["summary"]["motifMatches"]
        for bound in match["boundElements"]
        if _system_of(graph, bound["elementId"]) == SCREENED
    }
    assert "Input Screening Motif" in screening


# ---- what the run is allowed to say ----


def test_every_finding_stays_a_candidate(scene) -> None:
    assert {f["status"] for f in scene["summary"]["findings"]} == {"candidate"}


def test_the_declared_motifs_are_the_ones_the_paper_names(scene) -> None:
    """The risk pattern declares where it applies. The figure quotes this list,
    so it must come from the graph rather than from the prose."""
    declared = {
        str(m).rsplit("#", 1)[-1]
        for m in scene["graph"].objects(PAT.PromptInjectionRiskPattern, PAIR.hasMotif)
    }
    assert declared == {
        "DirectPromptingMotif",
        "QueryRewritingMotif",
        "RetrievalAugmentedGenerationMotif",
        "IterativeRAGMotif",
        "RecursiveRAGMotif",
        "AdaptiveRAGMotif",
        "LLMBasedInformationRetrievalMotif",
    }


def test_a_finding_records_the_match_it_came_from_not_the_declared_motif(scene) -> None:
    """`generatedByMotif` is run provenance: the motif of the match that
    supplied the binding. It nests inside the declared one and is routinely not
    a member of `hasMotif`, so the figure must not draw the two as one arrow."""
    graph = scene["graph"]
    declared = set(graph.objects(PAT.PromptInjectionRiskPattern, PAIR.hasMotif))
    over = {
        graph.value(finding, PAIR.generatedByMotif)
        for finding in graph.subjects(PAIR.generatedByRiskPattern, PAT.PromptInjectionRiskPattern)
    }
    assert over - declared == {PAT.InformationRetrievalMotif}


def test_the_scene_is_pinned(scene) -> None:
    assert len(scene["summary"]["motifMatches"]) == 6
    assert len(scene["summary"]["findings"]) == 13
    assert len(scene["view"]["groups"]) == 12
