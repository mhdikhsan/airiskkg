"""Assessment tests for the Onyx (formerly Danswer) enterprise RAG example.

This example exercises motifs the other examples do not: query rewriting,
reranker, and direct prompting — and, unlike verba, its external models are
bound in motif matches, so the supply-chain risk pattern fires.
"""

from rdflib import DCTERMS, RDF, RDFS, Namespace
from rdflib.namespace import SKOS

from airiskkg.assessment_runner import PAIR, PAT, run_assessment
from airiskkg.paths import EXAMPLE_DIR

ONYX_PATH = EXAMPLE_DIR / "onyx_danswer_rag_chatbot.ttl"

OWASP = Namespace("http://w3id.org/airiskkg/taxonomy/owasp-llm#")


def _result():
    return run_assessment(ONYX_PATH, write_outputs=False)


def test_onyx_matches_expected_motifs() -> None:
    result = _result()
    matched_motifs = set(result.motif_matches.objects(None, PAIR.matchesMotif))
    assert PAT.QueryRewritingMotif in matched_motifs
    assert PAT.RerankerMotif in matched_motifs
    assert PAT.VectorBasedInformationRetrievalMotif in matched_motifs
    assert PAT.EmbeddingsMotif in matched_motifs
    assert PAT.DirectPromptingMotif in matched_motifs


def test_onyx_reranker_match_binds_reranker_model() -> None:
    result = _result()
    reranker_match = next(
        result.motif_matches.subjects(PAIR.matchesMotif, PAT.RerankerMotif)
    )
    bound_elements = {
        result.motif_matches.value(binding, PAIR.matchedElement)
        for binding in result.motif_matches.objects(reranker_match, PAIR.hasNodeBinding)
    }
    onyx = Namespace("http://w3id.org/airiskkg/example/onyx-danswer#")
    assert onyx.RerankerModel in bound_elements
    assert onyx.RetrievedSections in bound_elements
    assert onyx.RerankedSections in bound_elements


def test_onyx_produces_supply_chain_finding() -> None:
    """Match-bound external models (generator LLM, reranker) must yield
    candidate supply-chain findings."""
    result = _result()
    supply_chain_findings = set(
        result.risk_findings.subjects(
            PAIR.hasDerivedMechanism,
            OWASP["mechanism-supply-chain-compromise"],
        )
    )
    assert supply_chain_findings


def test_onyx_produces_prompt_injection_and_sensitive_findings() -> None:
    result = _result()
    mechanisms = set(result.risk_findings.objects(None, PAIR.hasDerivedMechanism))
    assert OWASP["mechanism-instruction-override"] in mechanisms
    assert OWASP["mechanism-sensitive-data-propagation"] in mechanisms
    assert OWASP["mechanism-vector-embedding-retrieval-weakness"] in mechanisms


def test_onyx_all_findings_are_candidates() -> None:
    result = _result()
    findings = set(result.risk_findings.subjects(RDF.type, PAIR.RiskFinding))
    assert findings
    for finding in findings:
        status = result.risk_findings.value(finding, PAIR.findingStatus)
        assert str(status) == "candidate"


ATLAS = Namespace("http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#")
MIT = Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk#")
MITCTRL = Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#")
NIST = Namespace("http://w3id.org/airiskkg/taxonomy/nist-genai#")
NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")


def test_sensitive_data_finding_includes_cross_taxonomy_alignment() -> None:
    """One finding should reach every alignment layer: OWASP anchor, IBM Atlas,
    MIT domain, MIT control families as evidence, and NIST through Atlas."""
    result = _result()
    # Two patterns share this mechanism - the retrieval-scoped one and the
    # general user-facing-output one - so picking whichever came first out of an
    # unordered set made this test depend on graph iteration order. The
    # retrieval-scoped finding is the one that reaches every layer, and it is
    # identified by the control only it suggests.
    finding = next(
        candidate
        for candidate in result.risk_findings.subjects(
            PAIR.hasDerivedMechanism, OWASP["mechanism-sensitive-data-propagation"]
        )
        if PAT["Control_RetrievalAccessControl"]
        in set(result.risk_findings.objects(candidate, PAIR.hasSuggestedControl))
    )
    risks = set(result.risk_findings.objects(finding, PAIR.hasCandidateRiskTaxonomyEntry))
    controls = set(result.risk_findings.objects(finding, PAIR.hasSuggestedControl))

    assert OWASP["llm02-sensitive-information-disclosure"] in risks
    assert ATLAS["exposing-personal-information"] in risks
    assert MIT["subdomain-2-1"] in risks

    # pair:suggestedControl carries only PAIR-AI's own actionable catalogue.
    assert PAT["Control_DataMinimizationAndRedaction"] in controls
    assert PAT["Control_RetrievalAccessControl"] in controls
    assert all(str(control).startswith(str(PAT)) for control in controls)

    # MIT control families survive as an EVIDENCE layer reached through the
    # finding's taxonomy entries, not as suggested controls.
    grounded = set()
    for entry in risks:
        grounded |= set(result.combined_graph.objects(entry, NEXUS.hasRelatedControl))
    assert MITCTRL["data-governance"] in grounded
    assert MITCTRL["access-management"] in grounded

    # NIST AI 600-1 is reachable through IBM Atlas rather than anchored directly,
    # which is the whole design of that alignment layer.
    aligned = set()
    for entry in risks:
        for predicate in (SKOS.exactMatch, SKOS.broadMatch, SKOS.closeMatch, SKOS.relatedMatch):
            aligned |= set(result.combined_graph.objects(entry, predicate))
    assert NIST["data-privacy"] in aligned


def test_every_risk_finding_has_required_fields() -> None:
    """Structural integrity of the output: no finding may be missing a field the
    view layer and the SHACL output contract rely on."""
    result = _result()
    findings = set(result.risk_findings.subjects(RDF.type, PAIR.RiskFinding))
    assert findings

    required_predicates = {
        RDFS.label,
        DCTERMS.description,
        PAIR.generatedFromMatch,
        PAIR.generatedByMotif,
        PAIR.hasDerivedMechanism,
        PAIR.hasEvidence,
        PAIR.findingStatus,
    }
    for finding in findings:
        for predicate in required_predicates:
            assert (finding, predicate, None) in result.risk_findings, f"{finding} missing {predicate}"
