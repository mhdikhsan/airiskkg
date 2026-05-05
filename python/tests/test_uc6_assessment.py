from rdflib import DCTERMS, RDF, RDFS

from airiskkg.assessment_runner import PAT, RP, load_uc6_graph, run_uc6_assessment


def test_uc6_graph_loads() -> None:
    graph = load_uc6_graph()
    assert len(graph) > 0


def test_vector_ir_matching_produces_motif_match() -> None:
    result = run_uc6_assessment(write_outputs=False)
    vector_matches = set(
        result.motif_matches.subjects(
            RP.matchesMotif,
            PAT.VectorBasedInformationRetrievalMotif,
        )
    )
    assert vector_matches


def test_vector_ir_match_binds_expected_pattern_nodes() -> None:
    result = run_uc6_assessment(write_outputs=False)
    vector_match = next(
        result.motif_matches.subjects(
            RP.matchesMotif,
            PAT.VectorBasedInformationRetrievalMotif,
        )
    )
    bindings = set(result.motif_matches.objects(vector_match, RP.hasNodeBinding))
    bound_pattern_nodes = {
        result.motif_matches.value(binding, RP.bindsPatternNode)
        for binding in bindings
    }

    assert PAT.VectorIR_QueryNode in bound_pattern_nodes
    assert PAT.VectorIR_RetrievalStepNode in bound_pattern_nodes
    assert PAT.VectorIR_VectorStoreNode in bound_pattern_nodes
    assert PAT.VectorIR_RetrievedResultNode in bound_pattern_nodes


def test_sensitive_data_interpretation_produces_risk_finding() -> None:
    result = run_uc6_assessment(write_outputs=False)
    sensitive_findings = set(
        result.risk_findings.subjects(
            RP.hasInterpretedMechanism,
            PAT.SensitiveDataRetrievalExposure,
        )
    )
    assert sensitive_findings


def test_every_risk_finding_has_required_fields() -> None:
    result = run_uc6_assessment(write_outputs=False)
    findings = set(result.risk_findings.subjects(RDF.type, RP.RiskFinding))
    assert findings

    required_predicates = {
        RDFS.label,
        DCTERMS.description,
        RP.generatedFromMatch,
        RP.generatedByMotif,
        RP.hasInterpretedMechanism,
        RP.hasEvidenceElement,
        RP.findingStatus,
    }
    for finding in findings:
        for predicate in required_predicates:
            assert (finding, predicate, None) in result.risk_findings
