"""Assessment tests for the Onyx (formerly Danswer) enterprise RAG example.

This example exercises motifs the other examples do not: query rewriting,
reranker, and direct prompting — and, unlike verba, its external models are
bound in motif matches, so the supply-chain risk pattern fires.
"""

from rdflib import RDF, Namespace

from airiskkg.assessment_runner import PAIR, PAT, run_assessment
from airiskkg.paths import EXAMPLE_DIR

ONYX_PATH = EXAMPLE_DIR / "onyx_danswer.ttl"

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
