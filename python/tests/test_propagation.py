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
from conftest import GRAPH_RAG_NS, ONYX_NS, example_path  # noqa: E402

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


def test_taint_roots_carry_the_marker_themselves() -> None:
    """An element whose role IS a taint root must carry pair:UntrustedContent.

    Until 2026-08-06 the rule only tagged what a root flowed into, so the
    elements whose untrusted provenance is least in doubt - the public input,
    the retrieved context - were invisible to any condition reading a step's
    own input. Roots are now marked directly."""
    result = run_assessment_from_text(_without_redaction())
    assert "UntrustedContent" in _categories(result, "Query"), "public input is a taint root"
    assert "UntrustedContent" in _categories(result, "Ctx"), "retrieved context is a taint root"


def test_generation_output_is_marked_as_generated_content() -> None:
    """What a generation step produces is generated content, by definition of
    the role. Derived rather than annotated (Rule R8): no human judgement is
    involved, unlike SensitiveInformation."""
    result = run_assessment_from_text(_without_redaction())
    assert "GeneratedContent" in _categories(result, "Answer")


def test_redaction_stops_protected_content_but_not_origin_markers() -> None:
    """Redaction removes protected content; it does not rewrite provenance.

    Redacting a model's output does not make that output un-generated, so
    pair:GeneratedContent passes the barrier while pair:SensitiveInformation
    does not. A barrier that erased both would destroy provenance a downstream
    condition may need."""
    graph = _GRAPH % (_REDACTION, "ex:Clean") + """
ex:RedactAnswer a beam:Process ; pair:playsRole pair:RedactionStep ;
    beam:use ex:Answer ; beam:produce ex:PublicAnswer .
ex:PublicAnswer a beam:Data ; pair:playsRole pair:UserFacingOutput .
"""
    categories = _categories(run_assessment_from_text(graph), "PublicAnswer")
    assert "GeneratedContent" in categories, "redaction does not un-generate content"
    assert "SensitiveInformation" not in categories, "redaction stops protected content"


# --- facet bridges ---------------------------------------------------------
# The point of the facet layer is that a modeler annotates a source once, in the
# vocabulary that fits the fact (a DPV personal-data kind, an OECD rights
# status), and the engine works out where it can reach. These check the bridge
# from each facet into the content-category vocabulary that actually propagates.

_DPV_GRAPH = """
@prefix ex: <http://example.org/facet#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix facet: <http://w3id.org/airiskkg/facets#> .
@prefix dpv: <https://w3id.org/dpv#> .
@prefix dataf: <http://w3id.org/airiskkg/facets/data#> .

ex:sys a beam:System ; beam:contain ex:input, ex:mid, ex:out .
ex:input a beam:Data ; pair:playsRole pair:UserInput ;
    facet:hasPersonalDataCategory dpv:HealthData .
ex:step a beam:Process ; pair:playsRole pair:ProcessingStep %s ;
    beam:use ex:input ; beam:produce ex:mid .
ex:mid a beam:Data ; pair:playsRole pair:RetrievedContext .
ex:step2 a beam:Process ; pair:playsRole pair:ProcessingStep ;
    beam:use ex:mid ; beam:produce ex:out .
ex:out a beam:Data ; pair:playsRole pair:UserFacingOutput .
"""

DPV_EX = "http://example.org/facet#"


def _dpv_categories(mitigation: str, local_name: str) -> set[str]:
    result = run_assessment_from_text(_DPV_GRAPH % mitigation)
    element = URIRef(DPV_EX + local_name)
    return {
        str(c).rsplit("#", 1)[-1]
        for c in result.combined_graph.objects(element, PAIR.containsDataCategory)
    }


def test_a_dpv_personal_data_annotation_reaches_the_output() -> None:
    """Annotate the source with a DPV kind, once, and the sensitivity arrives at
    the user-facing output without a single hand-tagged element in between."""
    assert "SensitiveInformation" in _dpv_categories("", "input")
    assert "SensitiveInformation" in _dpv_categories("", "out")


def test_anonymisation_clears_sensitivity_but_pseudonymisation_does_not() -> None:
    """DPV settles this, and the two must not be treated alike.

    dpv:AnonymisedData is a subclass of dpv:NonPersonalData, so anonymised
    output is no longer personal; dpv:PseudonymisedData is a subclass of
    dpv:PersonalData, so it still is. A barrier that cleared sensitivity at a
    pseudonymisation step would under-report the disclosure risk this facet
    exists to surface."""
    assert "SensitiveInformation" not in _dpv_categories(", pair:AnonymizationStep", "out")
    assert "SensitiveInformation" in _dpv_categories(", pair:PseudonymizationStep", "out")


def test_data_annotated_as_anonymised_is_not_marked_sensitive() -> None:
    """The bridge fires on the presence of a personal-data annotation, so the
    DPV values that say the data is NOT personal have to be excluded - otherwise
    annotating something as anonymised would mark it sensitive, the opposite of
    what the modeler said."""
    graph = _DPV_GRAPH % "" + """
ex:anon a beam:Data ; pair:playsRole pair:UserInput ;
    facet:hasPersonalDataCategory dpv:AnonymisedData .
"""
    result = run_assessment_from_text(graph)
    categories = {
        str(c).rsplit("#", 1)[-1]
        for c in result.combined_graph.objects(URIRef(DPV_EX + "anon"), PAIR.containsDataCategory)
    }
    assert "SensitiveInformation" not in categories


def test_proprietary_rights_become_confidential_information() -> None:
    graph = _DPV_GRAPH % "" + """
ex:corpus a beam:Data ; pair:playsRole pair:KnowledgeSource ;
    facet:hasDataRights dataf:Proprietary .
"""
    result = run_assessment_from_text(graph)
    categories = {
        str(c).rsplit("#", 1)[-1]
        for c in result.combined_graph.objects(URIRef(DPV_EX + "corpus"), PAIR.containsDataCategory)
    }
    assert "ConfidentialInformation" in categories


def test_a_derived_category_can_be_traced_back_to_its_annotation() -> None:
    """A derived fact the modeler cannot check is a fact they have to trust.

    Each propagation hop records the upstream element and the step it passed
    through, so the chain from a sensitive output back to the human annotation
    is walkable."""
    from rdflib import Namespace

    prov = Namespace("http://www.w3.org/ns/prov#")
    result = run_assessment_from_text(_DPV_GRAPH % "")
    graph = result.combined_graph

    def one_hop_back(element):
        for derivation in graph.objects(element, prov.qualifiedDerivation):
            if (derivation, PAIR.derivedCategory, PAIR.SensitiveInformation) in graph:
                return graph.value(derivation, prov.entity), graph.value(derivation, prov.hadActivity)
        return None, None

    upstream, step = one_hop_back(URIRef(DPV_EX + "out"))
    assert upstream == URIRef(DPV_EX + "mid"), "output should trace back to the middle element"
    assert step == URIRef(DPV_EX + "step2"), "the hop must name the step it passed through"

    origin, _ = one_hop_back(upstream)
    assert origin == URIRef(DPV_EX + "input"), "the chain must reach the annotated source"


def test_derivation_records_do_not_break_the_fixed_point() -> None:
    """Provenance IRIs are deterministic on purpose.

    The runner loops until no new triple appears. Blank-node derivations would
    mint a fresh identifier every pass, so the rule would never converge and
    would grow the graph until the iteration cap stopped it."""
    result = run_assessment_from_text(_DPV_GRAPH % "")
    assert len(result.inferred_annotations) < 60, (
        f"propagation did not converge tightly ({len(result.inferred_annotations)} triples); "
        "check the derivation IRIs are deterministic"
    )


def test_propagation_leaves_the_bundled_examples_unchanged() -> None:
    """The propagation rules must not silently re-tag the curated examples.

    Both lost one sensitive-output finding when that pattern stopped keying its
    IRI on the data category. It emitted one finding per (sink, category) while
    the category appears nowhere in the finding, so a sink carrying both
    sensitive and confidential content produced two cards nobody could tell
    apart, for one problem with one fix. Each example has exactly one
    user-facing sink holding protected content, so the collapse loses nothing.

    onyx lost one finding when the unbounded-consumption pattern stopped firing
    on direct prompting alone. That branch had no loop and no reachability test,
    so it asked only whether an LLM call existed without a rate limiter - true of
    nearly every unmitigated GenAI system. It now requires the prompting path to
    be reachable from pair:PublicUserInput. onyx's input is an "Employee chat
    question" on an internal platform, so the silence is discrimination rather
    than a miss; annotation guidance says so at Info level where an input is not
    marked public.

    Last moved 2026-08-17, when the retrieval layer stopped being vector-only,
    and both changes are intended:

      onyx 13 -> 14 matches, 25 findings unchanged. It gains the general
      Information Retrieval match alongside the vector one - they nest by design
      - and the findings net out: it picks up sensitive-data-retrieval from the
      general motif and loses a duplicate vector-embedding-weakness that RAG
      used to contribute.

      graph RAG 11 -> 8 findings, 3 matches unchanged. Its Event KG is now
      annotated pair:KnowledgeSource, which is what it is; it used to be called
      a pair:VectorStore because that was the only way to match any retrieval
      motif at all. All three vector-and-embedding-weakness findings go with it,
      correctly - a knowledge graph has no embeddings to be weak - and prompt
      injection drops from 5 to 3 because it is a per-match finding and the
      vector match is gone. Fewer findings, none of them lost truthfully."""
    expected = {
        example_path(ONYX_NS): (14, 23),
        example_path(GRAPH_RAG_NS): (3, 7),
    }
    # Every graph the repo ships is pinned. Adding one without a baseline would
    # otherwise leave it unwatched, which is how drift goes unnoticed.
    assert set(expected) == set(EXAMPLE_DIR.glob("*.ttl")), (
        "bundled examples without a baseline: "
        + ", ".join(sorted(p.name for p in set(EXAMPLE_DIR.glob("*.ttl")) - set(expected)))
    )
    for name, (motifs, findings) in expected.items():
        result = run_assessment(name, write_outputs=False)
        assert result.motif_match_count == motifs, name
        assert result.risk_finding_count == findings, name


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
