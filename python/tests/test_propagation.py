"""Tests for data-category propagation.

The modeler annotates WHERE protected content enters the system; whether it can
REACH a later element is derived by following the flow (Rule R8). Two rules run
to a fixed point, with different semantics:

  untrusted_content.rq   trust taint, seeded from roles, barrier = guardrail
  content_categories.rq  content categories under pair:Information, propagating
                         what was annotated, barrier = redaction

Each test pairs propagation with its barrier: a rule that never stops would tag
the whole graph and make the categories useless for discriminating risk.
"""

from __future__ import annotations

from rdflib import RDF, RDFS, URIRef

from airiskkg.assessment_runner import PAIR, run_assessment, run_assessment_from_text
from airiskkg.paths import EXAMPLE_DIR

EX = "http://example.org/"

# Sensitive content is annotated on the STORE only. Everything downstream that
# carries it afterwards is derived, which is the point of the rule.
_GRAPH = """
@prefix ex: <http://example.org/> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .

ex:Store a beam:Data ; pair:playsRole pair:VectorStore ;
    pair:containsDataCategory pair:SensitiveInformation .
ex:Query a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:Retrieve a beam:Process ; pair:playsRole pair:RetrievalStep ;
    beam:use ex:Query ; beam:use ex:Store ; beam:produce ex:Ctx .
ex:Ctx a beam:Data ; pair:playsRole pair:RetrievedContext .
%s
ex:Gen a beam:Infer, beam:Process ; pair:playsRole pair:GenerationStep ;
    beam:use %s ; beam:use ex:LLM ; beam:produce ex:Answer .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:FoundationLLM, pair:GenerativeModel .
ex:Answer a beam:Data ; pair:playsRole pair:LLMResponse, pair:UserFacingOutput .
"""

_REDACTION = """
ex:Redact a beam:Process ; pair:playsRole pair:RedactionStep ;
    beam:use ex:Ctx ; beam:produce ex:Clean .
ex:Clean a beam:Data ; pair:playsRole pair:RetrievedContext .
"""


def _without_redaction() -> str:
    return _GRAPH % ("", "ex:Ctx")


def _with_redaction() -> str:
    return _GRAPH % (_REDACTION, "ex:Clean")


def _categories(result, local_name: str) -> set[str]:
    element = URIRef(EX + local_name)
    return {
        str(c).rsplit("#", 1)[-1]
        for c in result.combined_graph.objects(element, PAIR.containsDataCategory)
    }


def test_sensitive_information_reaches_the_output_without_being_annotated() -> None:
    """The question this rule exists to answer: tag the source, and the engine
    says whether it can reach the user-facing output."""
    result = _without_redaction()
    result = run_assessment_from_text(result)
    assert "SensitiveInformation" in _categories(result, "Store"), "annotated base fact"
    for derived in ("Ctx", "Answer"):
        assert "SensitiveInformation" in _categories(result, derived), (
            f"ex:{derived} should inherit the category by flow, not by hand-tagging"
        )


def test_a_redaction_step_stops_the_category() -> None:
    """Without a barrier the category would reach everything downstream and stop
    discriminating anything. Redaction is what makes it stop."""
    result = run_assessment_from_text(_with_redaction())
    assert "SensitiveInformation" in _categories(result, "Ctx"), "upstream of redaction"
    for downstream in ("Clean", "Answer"):
        assert "SensitiveInformation" not in _categories(result, downstream), (
            f"ex:{downstream} is downstream of a RedactionStep and must not carry it"
        )


def test_propagation_alone_satisfies_the_sensitive_retrieval_condition() -> None:
    """risk/sensitive_retrieval.rq requires BOTH the vector store and the
    retrieved result to carry the category. Only the store is annotated here, so
    a finding proves the derived fact is doing the work."""
    result = run_assessment_from_text(_without_redaction())
    labels = {
        str(result.risk_findings.value(f, RDFS.label))
        for f in result.risk_findings.subjects(RDF.type, PAIR.RiskFinding)
    }
    assert "Candidate sensitive data retrieval exposure" in labels


def test_trust_taint_and_content_categories_propagate_independently() -> None:
    """Two rules, two barriers. UntrustedContent is seeded from roles and stopped
    by a guardrail; content categories are annotated and stopped by redaction.
    A redaction step must not be mistaken for a guardrail."""
    result = run_assessment_from_text(_with_redaction())
    clean = _categories(result, "Clean")
    assert "UntrustedContent" in clean, "redaction is not a guardrail; trust taint continues"
    assert "SensitiveInformation" not in clean


def test_propagation_leaves_the_bundled_examples_unchanged() -> None:
    """The new rule must not silently re-tag the curated examples."""
    expected = {"onyx_danswer.ttl": (13, 23), "agentic_assistant.ttl": (3, 5)}
    for name, (motifs, findings) in expected.items():
        result = run_assessment(EXAMPLE_DIR / name, write_outputs=False)
        assert result.motif_match_count == motifs, name
        assert result.risk_finding_count == findings, name


# --- OECD/DPV facet bridge -------------------------------------------------
# The characterization facets are declared per Rule R2 to be read by
# applicability conditions, but no condition consumed one, so 95 OECD/DPV-
# grounded concepts had no effect on any outcome. dataf:Personal is the first
# to become load-bearing, via a bridge to the content-category vocabulary.

_FACET_GRAPH = _GRAPH.replace(
    "pair:containsDataCategory pair:SensitiveInformation .",
    "facet:hasDataRights dataf:Personal .",
).replace(
    "@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .",
    "@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .\n"
    "@prefix facet: <http://w3id.org/airiskkg/facets#> .\n"
    "@prefix dataf: <http://w3id.org/airiskkg/facets/data#> .",
)


def test_oecd_personal_rights_derives_the_content_category() -> None:
    """An element characterized only with the OECD data-rights status gains the
    content category, so the facet vocabulary reaches the assessment at all."""
    result = run_assessment_from_text(_FACET_GRAPH % ("", "ex:Ctx"))
    assert "SensitiveInformation" in _categories(result, "Store")


def test_the_facet_route_inherits_propagation_and_the_barrier() -> None:
    """A derived category must behave exactly like an annotated one: it flows
    downstream, and a RedactionStep stops it. This is the reason for bridging
    into the category vocabulary instead of special-casing facets per query."""
    flowing = run_assessment_from_text(_FACET_GRAPH % ("", "ex:Ctx"))
    assert "SensitiveInformation" in _categories(flowing, "Answer")

    stopped = run_assessment_from_text(_FACET_GRAPH % (_REDACTION, "ex:Clean"))
    assert "SensitiveInformation" not in _categories(stopped, "Clean")


def test_a_finding_fires_from_the_facet_alone() -> None:
    """End to end: one OECD facet on the source, no pair: category anywhere in
    the input, and the LLM02 condition is satisfied."""
    ttl = _FACET_GRAPH % ("", "ex:Ctx")
    assert "containsDataCategory" not in ttl, "input must not pre-tag any category"
    result = run_assessment_from_text(ttl)
    labels = {
        str(result.risk_findings.value(f, RDFS.label))
        for f in result.risk_findings.subjects(RDF.type, PAIR.RiskFinding)
    }
    assert "Candidate sensitive data retrieval exposure" in labels


def test_the_bridge_is_one_directional() -> None:
    """Rights status implies the category, never the reverse: sensitive content
    is broader than personal data, so the inverse would assert data-protection
    status the modeler never stated."""
    from rdflib import Namespace

    facet = Namespace("http://w3id.org/airiskkg/facets#")
    dataf = Namespace("http://w3id.org/airiskkg/facets/data#")
    result = run_assessment_from_text(_GRAPH % ("", "ex:Ctx"))  # category-annotated input
    store = URIRef(EX + "Store")
    assert (store, facet.hasDataRights, dataf.Personal) not in result.combined_graph
