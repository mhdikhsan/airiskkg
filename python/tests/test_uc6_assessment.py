from rdflib import DCTERMS, RDF, RDFS, Namespace

from airiskkg.assessment_runner import (
    PAIR,
    PAT,
    load_assessment_graph,
    run_assessment,
)
from airiskkg.paths import EXAMPLE_DIR

UC6_PATH = EXAMPLE_DIR / "uc6.ttl"

OWASP = Namespace("http://w3id.org/airiskkg/taxonomy/owasp-llm#")
ATLAS = Namespace("http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#")
MIT = Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk#")
MITCTRL = Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#")
NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")


def test_uc6_graph_loads() -> None:
    graph = load_assessment_graph(UC6_PATH)
    assert len(graph) > 0


def test_generic_assessment_runner_accepts_architecture_path() -> None:
    result = run_assessment(UC6_PATH, write_outputs=False)
    assert result.motif_match_count > 0


def test_vector_ir_matching_produces_motif_match() -> None:
    result = run_assessment(UC6_PATH, write_outputs=False)
    vector_matches = set(
        result.motif_matches.subjects(
            PAIR.matchesMotif,
            PAT.VectorBasedInformationRetrievalMotif,
        )
    )
    assert vector_matches


def test_vector_ir_match_binds_expected_pattern_nodes() -> None:
    result = run_assessment(UC6_PATH, write_outputs=False)
    vector_match = next(
        result.motif_matches.subjects(
            PAIR.matchesMotif,
            PAT.VectorBasedInformationRetrievalMotif,
        )
    )
    bindings = set(result.motif_matches.objects(vector_match, PAIR.hasNodeBinding))
    bound_pattern_nodes = {
        result.motif_matches.value(binding, PAIR.bindsPatternNode)
        for binding in bindings
    }

    assert PAT.VectorIR_QueryNode in bound_pattern_nodes
    assert PAT.VectorIR_RetrievalStepNode in bound_pattern_nodes
    assert PAT.VectorIR_VectorStoreNode in bound_pattern_nodes
    assert PAT.VectorIR_RetrievedResultNode in bound_pattern_nodes


def test_sensitive_data_risk_pattern_produces_risk_finding() -> None:
    result = run_assessment(UC6_PATH, write_outputs=False)
    sensitive_findings = set(
        result.risk_findings.subjects(
            PAIR.hasDerivedMechanism,
            OWASP["mechanism-sensitive-data-propagation"],
        )
    )
    assert sensitive_findings


def test_sensitive_data_finding_includes_cross_taxonomy_alignment() -> None:
    result = run_assessment(UC6_PATH, write_outputs=False)
    finding = next(
        result.risk_findings.subjects(
            PAIR.hasDerivedMechanism,
            OWASP["mechanism-sensitive-data-propagation"],
        )
    )

    risks = set(result.risk_findings.objects(finding, PAIR.hasCandidateRiskTaxonomyEntry))
    controls = set(result.risk_findings.objects(finding, PAIR.hasSuggestedControl))

    assert OWASP["llm02-sensitive-information-disclosure"] in risks
    assert ATLAS["exposing-personal-information"] in risks
    assert MIT["subdomain-2-1"] in risks

    # Single-vocabulary refactor (2026-07-21): pair:suggestedControl carries only
    # PAIR-AI's own actionable catalogue (pat:Control_*); MIT families are no
    # longer mirrored in as peer controls.
    assert PAT["Control_DataMinimizationAndRedaction"] in controls
    assert PAT["Control_RetrievalAccessControl"] in controls
    assert all(str(control).startswith(str(PAT)) for control in controls)

    # The MIT-grounded control families survive as an EVIDENCE layer, reached
    # through the finding's taxonomy entries via nexus:hasRelatedControl (the
    # CSV-grounded links in taxonomy_mapping.ttl), not as suggested controls.
    grounded = set()
    for entry in risks:
        grounded |= set(result.combined_graph.objects(entry, NEXUS.hasRelatedControl))
    assert MITCTRL["data-governance"] in grounded
    assert MITCTRL["access-management"] in grounded


def test_verba_external_model_produces_supply_chain_finding() -> None:
    result = run_assessment(EXAMPLE_DIR / "verba_goldenverba.ttl", write_outputs=False)
    supply_chain_findings = set(
        result.risk_findings.subjects(
            PAIR.hasDerivedMechanism,
            OWASP["mechanism-supply-chain-compromise"],
        )
    )

    assert supply_chain_findings


def test_every_risk_finding_has_required_fields() -> None:
    result = run_assessment(UC6_PATH, write_outputs=False)
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
            assert (finding, predicate, None) in result.risk_findings
