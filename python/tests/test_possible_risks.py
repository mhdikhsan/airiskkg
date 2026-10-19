"""Possible risks: a drawing tagged at a coarser level, or missing a part, still leads to its risks.

People tag at their own level (B-3 invites starting with a category) and draw
what they know, so a strict match is often missing where the risk is real. The
possible risks are what the library would raise if the diagram said a little
more, each with the tags or parts it rests on, kept apart from the findings.
"""
from __future__ import annotations

from rdflib import RDF, Graph, URIRef

from airiskkg.assessment_runner import PAIR, run_assessment_from_text
from airiskkg.workbench.possible import _vocabulary, apply_needs, possible_risks

PREFIXES = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://example.org/possible#> .
"""

# A RAG chatbot tagged only with categories, as B-3 invites a first pass to be.
BY_CATEGORY = PREFIXES + """
ex:S a beam:System ; rdfs:label "Help desk" ;
    beam:hasProcess ex:Retrieve, ex:Build, ex:Generate ;
    beam:hasResource ex:Question, ex:Manuals, ex:Passages, ex:Prompt, ex:LLM, ex:Answer .
ex:Question a beam:Data ; rdfs:label "Question" ; pair:playsRole pair:UserInputRoles .
ex:Manuals a beam:Data ; rdfs:label "Manuals" ; pair:playsRole pair:KnowledgeContextRoles .
ex:Retrieve a beam:Process ; rdfs:label "Find passages" ; pair:playsRole pair:RetrievalRoles ;
    beam:use ex:Question, ex:Manuals ; beam:produce ex:Passages .
ex:Passages a beam:Data ; rdfs:label "Passages" ; pair:playsRole pair:KnowledgeContextRoles .
ex:Build a beam:Transform ; rdfs:label "Build prompt" ; pair:playsRole pair:GenerationRoles ;
    beam:use ex:Question, ex:Passages ; beam:produce ex:Prompt .
ex:Prompt a beam:Data ; rdfs:label "Prompt" ; pair:playsRole pair:PromptResponseRoles .
ex:LLM a beam:StatisticalModel ; rdfs:label "LLM" ; pair:playsRole pair:ModelRoles .
ex:Generate a beam:Infer ; rdfs:label "Answer" ; pair:playsRole pair:GenerationRoles ;
    beam:use ex:Prompt, ex:LLM ; beam:produce ex:Answer .
ex:Answer a beam:Data ; rdfs:label "Reply" ; pair:playsRole pair:PromptResponseRoles .
"""


def _findings(ttl: str) -> set[tuple[str, frozenset]]:
    graph = run_assessment_from_text(ttl).combined_graph
    return {
        (str(graph.value(f, PAIR.generatedByRiskPattern)), frozenset(str(e) for e in graph.objects(f, PAIR.hasEvidence)))
        for f in graph.subjects(RDF.type, PAIR.RiskFinding)
    }


def _pattern(name: str) -> str:
    return f"http://w3id.org/airiskkg/patterns#{name}RiskPattern"


def test_a_diagram_tagged_by_category_still_leads_to_its_risks() -> None:
    assert not _findings(BY_CATEGORY), "a category matches nothing, so nothing is raised yet"
    report = possible_risks(BY_CATEGORY)
    patterns = {r["pattern"] for r in report["risks"]}
    assert _pattern("PromptInjection") in patterns, sorted(patterns)
    rag = [r for r in report["risks"] if r["motif"] == "RetrievalAugmentedGenerationMotif"]
    assert rag, "the RAG reading of the diagram raised nothing"
    roles = {(n["elementLabel"], n["roleLabel"]) for r in rag for n in r["needs"] if n["kind"] == "role"}
    assert ("Find passages", "Retrieval Step") in roles, roles


def test_applying_a_possible_risk_raises_it() -> None:
    """What a possible risk says it needs is what the strict matcher then finds."""
    report = possible_risks(BY_CATEGORY)
    for risk in report["risks"]:
        graph = Graph().parse(data=BY_CATEGORY, format="turtle")
        counter = iter(range(1, 100))
        apply_needs(graph, risk["needs"], lambda: URIRef(f"http://example.org/possible#new{next(counter)}"))
        raised = _findings(graph.serialize(format="turtle"))
        # the same risk at the same place: it may cite an element more or fewer
        cited = set(risk["evidence"])
        assert any(pattern == risk["pattern"] and len(cited & evidence) / len(cited | evidence) >= 0.5
                   for pattern, evidence in raised), (risk["label"], risk["motif"], risk["needs"])


def test_a_category_tag_is_refined_never_kept_beside_its_role() -> None:
    graph = Graph().parse(data=BY_CATEGORY, format="turtle")
    retrieve = URIRef("http://example.org/possible#Retrieve")
    apply_needs(graph, [{"kind": "role", "element": str(retrieve), "role": str(PAIR.RetrievalStep)}], None)
    assert set(graph.objects(retrieve, PAIR.playsRole)) == {PAIR.RetrievalStep}


def test_a_missing_part_is_asked_for_and_added_where_it_belongs() -> None:
    """The prompt left out: the generation step reads the passages directly."""
    without_prompt = BY_CATEGORY.replace(
        "beam:use ex:Prompt, ex:LLM ; beam:produce ex:Answer .", "beam:use ex:Passages, ex:LLM ; beam:produce ex:Answer .")
    report = possible_risks(without_prompt)
    adds = [n for r in report["risks"] for n in r["needs"] if n["kind"] == "add"]
    assert adds, "nothing is asked to be added"
    assert all(n["links"] for n in adds), "an added part is not connected to anything"


def test_a_possible_risk_never_repeats_a_finding() -> None:
    from airiskkg.assessment_runner import REPO_ROOT

    for path in sorted((REPO_ROOT / "ontology" / "example").glob("*.ttl")):
        ttl = path.read_text(encoding="utf-8")
        raised = _findings(ttl)
        for risk in possible_risks(ttl)["risks"]:
            assert (risk["pattern"], frozenset(risk["evidence"])) not in raised, (path.name, risk["label"])


def test_no_condition_asked_for_is_a_barrier() -> None:
    """A role a risk query treats as its escape would clear the risk it is asked for.
    A motif's own node roles are what the structure is, so only conditions are held to it."""
    barriers = {str(p): {str(r) for r in roles} for p, roles in _vocabulary().barriers.items()}
    for risk in possible_risks(BY_CATEGORY)["risks"]:
        for need in risk["needs"]:
            if need.get("condition"):
                assert need.get("role") not in barriers[risk["pattern"]], (risk["label"], need)


def test_looking_for_possible_risks_changes_nothing_that_is_detected() -> None:
    before = _findings(BY_CATEGORY)
    possible_risks(BY_CATEGORY)
    assert _findings(BY_CATEGORY) == before
