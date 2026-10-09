"""The ML, IBM Atlas and agentic risk patterns added 2026-10-09: each fires on its
shape, and building the control it names clears it - except membership inference,
which has no structural escape by design."""

from __future__ import annotations

from collections import Counter

import pytest

from rdflib import Namespace

from airiskkg.assessment_runner import run_assessment_from_text
from conftest import AGENT_NS, CREDIT_SCORING_NS, example_path

PAIR = Namespace("http://w3id.org/airiskkg/pair-ai#")


def _patterns(ttl: str) -> Counter:
    findings = run_assessment_from_text(ttl).risk_findings
    return Counter(str(o).rsplit("#", 1)[-1] for o in findings.objects(None, PAIR.generatedByRiskPattern))


@pytest.fixture(scope="module")
def credit() -> str:
    return example_path(CREDIT_SCORING_NS).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def credit_baseline(credit) -> Counter:
    return _patterns(credit)


ML_PATTERNS = {
    "DatasetShiftRiskPattern",
    "OutOfDomainInputRiskPattern",
    "AdversarialEvasionRiskPattern",
    "UnevaluatedModelRiskPattern",
    "UnqualifiedPredictionRiskPattern",
    "TrainingDataMembershipInferenceRiskPattern",
    "ModelBiasRiskPattern",
    "ImproperRetrainingRiskPattern",
}


def test_an_unmitigated_ml_system_raises_every_ml_pattern_it_has_the_shape_for(credit_baseline) -> None:
    assert ML_PATTERNS <= set(credit_baseline)
    # Contamination needs an evaluation step, and this system has none.
    assert "EvaluationDataContaminationRiskPattern" not in credit_baseline


def _replace(ttl: str, old: str, new: str) -> str:
    assert old in ttl, old
    return ttl.replace(old, new, 1)


def test_monitoring_against_a_baseline_clears_dataset_shift(credit) -> None:
    monitored = credit + """
cs:LogPredictions a beam:Process ; rdfs:label "Log predictions" ;
    pair:playsRole pair:LoggingStep ;
    beam:use cs:LoanApplication, cs:CreditScore ;
    beam:produce cs:PredictionLog .
cs:PredictionLog a beam:Data ; rdfs:label "Prediction log" ; pair:playsRole pair:PredictionLog .
cs:TrainingBaseline a beam:Data ; rdfs:label "Training distribution" ; pair:playsRole pair:MonitoringBaseline .
cs:DriftMonitor a beam:Process ; rdfs:label "Drift monitor" ;
    pair:playsRole pair:MonitoringStep ;
    beam:use cs:PredictionLog, cs:TrainingBaseline ;
    beam:produce cs:DriftAlert .
cs:DriftAlert a beam:Data ; rdfs:label "Drift alert" ; pair:playsRole pair:Alert .
"""
    after = _patterns(monitored)
    assert "DatasetShiftRiskPattern" not in after
    # Monitoring is not a domain check.
    assert "OutOfDomainInputRiskPattern" in after


def test_a_monitor_with_nothing_to_compare_against_does_not_clear_dataset_shift(credit) -> None:
    blind = credit + """
cs:LogPredictions a beam:Process ; rdfs:label "Log predictions" ;
    pair:playsRole pair:LoggingStep ;
    beam:use cs:CreditScore ;
    beam:produce cs:PredictionLog .
cs:PredictionLog a beam:Data ; rdfs:label "Prediction log" ; pair:playsRole pair:PredictionLog .
cs:Watcher a beam:Process ; rdfs:label "Dashboard" ;
    pair:playsRole pair:MonitoringStep ;
    beam:use cs:PredictionLog ;
    beam:produce cs:Chart .
cs:Chart a beam:Data ; rdfs:label "Chart" .
"""
    assert "DatasetShiftRiskPattern" in _patterns(blind)


def test_a_domain_check_clears_out_of_domain_input_but_not_adversarial_evasion(credit) -> None:
    checked = _replace(
        credit,
        "beam:use cs:DeployedScorer, cs:LoanApplication ;",
        "beam:use cs:DeployedScorer, cs:CheckedApplication ;",
    ) + """
cs:DomainCheck a beam:Process ; rdfs:label "Check the application is in scope" ;
    pair:playsRole pair:InputDomainCheckStep ;
    beam:use cs:LoanApplication ;
    beam:produce cs:CheckedApplication .
cs:CheckedApplication a beam:Data ; rdfs:label "In-scope application" ; pair:playsRole pair:PredictionRequest .
"""
    after = _patterns(checked)
    assert "OutOfDomainInputRiskPattern" not in after
    assert "AdversarialEvasionRiskPattern" in after


def test_an_input_guardrail_clears_adversarial_evasion_but_not_out_of_domain_input(credit) -> None:
    screened = _replace(
        credit,
        "beam:use cs:DeployedScorer, cs:LoanApplication ;",
        "beam:use cs:DeployedScorer, cs:ScreenedApplication ;",
    ) + """
cs:InputScreen a beam:Process ; rdfs:label "Screen the application" ;
    pair:playsRole pair:InputGuardrailStep ;
    beam:use cs:LoanApplication ;
    beam:produce cs:ScreenedApplication .
cs:ScreenedApplication a beam:Data ; rdfs:label "Screened application" ; pair:playsRole pair:PredictionRequest .
"""
    after = _patterns(screened)
    assert "AdversarialEvasionRiskPattern" not in after
    assert "OutOfDomainInputRiskPattern" in after


def test_an_evaluation_clears_the_unevaluated_model_and_only_a_fairness_one_clears_bias(credit) -> None:
    accuracy = credit + """
cs:Backtest a beam:Process ; rdfs:label "Backtest the model" ;
    pair:playsRole pair:EvaluationStep ;
    beam:use cs:ScorerArtifact ;
    beam:produce cs:BacktestReport .
cs:BacktestReport a beam:Data ; rdfs:label "Backtest report" ; pair:playsRole pair:EvaluationResult .
"""
    after = _patterns(accuracy)
    assert "UnevaluatedModelRiskPattern" not in after
    assert "ModelBiasRiskPattern" in after

    fairness = credit + """
cs:FairnessAudit a beam:Process ; rdfs:label "Compare outcomes across groups" ;
    pair:playsRole pair:FairnessEvaluationStep ;
    beam:use cs:ScorerArtifact ;
    beam:produce cs:FairnessReport .
cs:FairnessReport a beam:Data ; rdfs:label "Fairness report" ; pair:playsRole pair:EvaluationResult .
"""
    after = _patterns(fairness)
    assert "ModelBiasRiskPattern" not in after
    # A fairness evaluation is an evaluation too.
    assert "UnevaluatedModelRiskPattern" not in after


def test_model_bias_needs_the_training_data_to_be_about_people(credit) -> None:
    impersonal = _replace(credit, "    facet:hasPersonalDataCategory pd:Financial .", "    .")
    after = _patterns(impersonal.replace('pair:playsRole pair:TrainingDataset ;\n    .', "pair:playsRole pair:TrainingDataset ."))
    assert "ModelBiasRiskPattern" not in after
    assert "TrainingDataMembershipInferenceRiskPattern" not in after


@pytest.mark.parametrize("alongside", [
    """
cs:ScoreApplication beam:produce cs:ScoreConfidence .
cs:ScoreConfidence a beam:Data ; rdfs:label "Score confidence" ; pair:playsRole pair:UncertaintyEstimate .
cs:DecideLoan beam:use cs:ScoreConfidence .
""",
    """
cs:CreditOfficer a beam:Process ; rdfs:label "Credit officer review" ;
    pair:playsRole pair:HumanApprovalStep ;
    beam:use cs:CreditScore, cs:LoanApplication ;
    beam:produce cs:OfficerSignOff .
cs:OfficerSignOff a beam:Data ; rdfs:label "Officer sign-off" .
cs:DecideLoan beam:use cs:OfficerSignOff .
""",
])
def test_uncertainty_or_a_review_where_the_prediction_is_used_clears_it(credit, alongside) -> None:
    assert "UnqualifiedPredictionRiskPattern" not in _patterns(credit + alongside)


def test_an_uncertainty_estimate_that_never_reaches_the_decision_clears_nothing(credit) -> None:
    unused = credit + """
cs:ScoreApplication beam:produce cs:ScoreConfidence .
cs:ScoreConfidence a beam:Data ; rdfs:label "Score confidence" ; pair:playsRole pair:UncertaintyEstimate .
"""
    assert "UnqualifiedPredictionRiskPattern" in _patterns(unused)


def test_validating_what_is_fed_back_clears_improper_retraining(credit) -> None:
    vetted = _replace(
        credit,
        "    beam:use cs:LoanApplication, cs:LoanDecision ;\n    beam:produce cs:ApplicantHistory .",
        "    beam:use cs:LoanApplication, cs:LoanDecision ;\n    beam:produce cs:RawOutcome .",
    ) + """
cs:RawOutcome a beam:Data ; rdfs:label "Recorded outcome" .
cs:OutcomeVetting a beam:Process ; rdfs:label "Vet outcomes before reuse" ;
    pair:playsRole pair:DataValidationStep ;
    beam:use cs:RawOutcome ;
    beam:produce cs:ApplicantHistory .
"""
    assert "ImproperRetrainingRiskPattern" not in _patterns(vetted)


def test_membership_inference_has_no_structural_escape(credit) -> None:
    """It rests on how the model is trained, so every control the graph can show leaves it standing."""
    everything = _replace(
        credit,
        "beam:use cs:DeployedScorer, cs:LoanApplication ;",
        "beam:use cs:DeployedScorer, cs:CheckedApplication ;",
    ) + """
cs:InputScreen a beam:Process ; pair:playsRole pair:InputGuardrailStep ;
    beam:use cs:LoanApplication ; beam:produce cs:ScreenedApplication .
cs:ScreenedApplication a beam:Data ; rdfs:label "Screened application" .
cs:DomainCheck a beam:Process ; pair:playsRole pair:InputDomainCheckStep ;
    beam:use cs:ScreenedApplication ; beam:produce cs:CheckedApplication .
cs:CheckedApplication a beam:Data ; rdfs:label "Checked application" ; pair:playsRole pair:PredictionRequest .
cs:Throttle a beam:Process ; pair:playsRole pair:RateLimitControlStep ;
    beam:use cs:CheckedApplication ; beam:produce cs:Quota .
cs:Quota a beam:Data ; rdfs:label "Query quota" .
cs:ScoreApplication beam:use cs:Quota .
"""
    assert "TrainingDataMembershipInferenceRiskPattern" in _patterns(everything)


PIPELINE = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:   <http://example.org/pipeline#> .

ex:Sys a beam:System ; rdfs:label "Training pipeline" .
ex:Source a beam:Data ; rdfs:label "Labelled records" ; pair:playsRole pair:TrainingDataset .
ex:Prepare a beam:Transform, beam:Process ; rdfs:label "Prepare" ;
    pair:playsRole pair:PreprocessingStep ; beam:use ex:Source ; beam:produce ex:Prepared .
ex:Prepared a beam:Data ; rdfs:label "Prepared records" ; pair:playsRole pair:PreprocessedData .
ex:Train a beam:Train, beam:Process ; rdfs:label "Train" ;
    pair:playsRole pair:TrainingStep ; beam:use ex:Prepared ; beam:produce ex:Model .
ex:Model a beam:StatisticalModel ; rdfs:label "Model" ; pair:playsRole pair:ModelArtifact .
ex:Evaluate a beam:Process ; rdfs:label "Evaluate" ;
    pair:playsRole pair:EvaluationStep ; beam:use ex:Model, %s ; beam:produce ex:Report .
ex:Report a beam:Data ; rdfs:label "Evaluation report" ; pair:playsRole pair:EvaluationResult .
ex:HeldOut a beam:Data ; rdfs:label "Held-out records" .
"""


@pytest.mark.parametrize("evaluated_on, contaminated", [
    ("ex:Prepared", True),   # the training data itself
    ("ex:Source", True),     # the set the training data was drawn from
    ("ex:HeldOut", False),   # data training never saw
])
def test_contamination_is_evaluation_over_what_training_drew_from(evaluated_on, contaminated) -> None:
    found = "EvaluationDataContaminationRiskPattern" in _patterns(PIPELINE % evaluated_on)
    assert found is contaminated


AGENT = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:   <http://example.org/agent#> .

ex:Sys a beam:System ; rdfs:label "Operations agent" .
ex:Ticket a beam:Data ; rdfs:label "Ticket" ; pair:playsRole pair:UserInput .
ex:Planning a beam:Infer, beam:Process ; rdfs:label "Plan" ;
    pair:playsRole pair:PlanningStep ; beam:use ex:Ticket ; beam:produce ex:Plan .
ex:Plan a beam:Data ; rdfs:label "Plan" .
"""


def test_a_credential_shared_across_a_hand_off_raises_identity_abuse() -> None:
    shared = AGENT + """
ex:AdminKey a beam:Data ; rdfs:label "Admin API key" ; pair:playsRole pair:AccessCredential .
ex:Planning beam:use ex:AdminKey ; beam:produce ex:Task .
ex:Task a beam:Data ; rdfs:label "Delegated task" ; pair:playsRole pair:AgentMessage .
ex:Worker a beam:Process ; rdfs:label "Worker agent" ;
    pair:playsRole pair:AgentHandoffStep ; beam:use ex:Task, ex:AdminKey ; beam:produce ex:Done .
ex:Done a beam:Data ; rdfs:label "Done" .
"""
    assert "IdentityPrivilegeAbuseRiskPattern" in _patterns(shared)
    own_key = shared.replace("beam:use ex:Task, ex:AdminKey ;", "beam:use ex:Task, ex:WorkerKey ;") + """
ex:WorkerKey a beam:Data ; rdfs:label "Worker's scoped key" ; pair:playsRole pair:AccessCredential .
"""
    assert "IdentityPrivilegeAbuseRiskPattern" not in _patterns(own_key)
    authorised = shared + """
ex:Authorise a beam:Process ; pair:playsRole pair:PolicyEnforcementStep ; beam:produce ex:Grant .
ex:Grant a beam:Data ; rdfs:label "Per-action grant" .
ex:Worker beam:use ex:Grant .
"""
    assert "IdentityPrivilegeAbuseRiskPattern" not in _patterns(authorised)


def test_a_credential_written_to_agent_memory_raises_identity_abuse() -> None:
    remembered = AGENT + """
ex:Session a beam:Data ; rdfs:label "Delegated session" ; pair:playsRole pair:AccessCredential .
ex:Remember a beam:Process ; pair:playsRole pair:MemoryWriteStep ; beam:use ex:Plan, ex:Session ; beam:produce ex:Memory .
ex:Memory a beam:Data ; rdfs:label "Agent memory" ; pair:playsRole pair:AgentMemory .
ex:Recall a beam:Process ; pair:playsRole pair:MemoryReadStep ; beam:use ex:Memory ; beam:produce ex:Recalled .
ex:Recalled a beam:Data ; rdfs:label "Recalled" ; pair:playsRole pair:RetrievedContext .
"""
    assert "IdentityPrivilegeAbuseRiskPattern" in _patterns(remembered)


REGISTRY = AGENT + """
ex:Planning beam:use ex:Registry ; beam:produce ex:Assignment .
ex:Registry a beam:Data ; rdfs:label "Public tool registry" ; pair:playsRole pair:ToolRegistry, pair:ThirdPartyPackage .
ex:Assignment a beam:Data ; rdfs:label "Assignment" .
ex:Call a beam:Process ; rdfs:label "Call the tool" ; pair:playsRole pair:ToolInvocationStep ;
    beam:use ex:Assignment ; beam:produce ex:Result .
ex:Result a beam:Data ; rdfs:label "Result" .
"""


def test_an_external_registry_steering_an_agent_raises_agentic_supply_chain() -> None:
    assert "AgenticSupplyChainRiskPattern" in _patterns(REGISTRY)
    verified = REGISTRY.replace("ex:Planning beam:use ex:Registry ;", "ex:Planning beam:use ex:Pinned ;") + """
ex:Verify a beam:Process ; pair:playsRole pair:PolicyEnforcementStep ; beam:use ex:Registry ; beam:produce ex:Pinned .
ex:Pinned a beam:Data ; rdfs:label "Verified, pinned registry" ; pair:playsRole pair:ToolRegistry .
"""
    assert "AgenticSupplyChainRiskPattern" not in _patterns(verified)


def test_a_hosted_model_or_a_credential_is_not_an_agentic_supply_chain_component() -> None:
    hosted = AGENT + """
ex:HostedLLM a beam:StatisticalModel ; rdfs:label "Hosted LLM" ; pair:playsRole pair:ExternalModel .
ex:ApiKey a beam:Data ; rdfs:label "Provider key" ; pair:playsRole pair:ExternalProviderCredential .
ex:Planning beam:use ex:HostedLLM, ex:ApiKey .
ex:Act a beam:Process ; pair:playsRole pair:ToolInvocationStep ; beam:use ex:Plan ; beam:produce ex:Out .
ex:Out a beam:Data ; rdfs:label "Out" .
"""
    assert "AgenticSupplyChainRiskPattern" not in _patterns(hosted)


CODE = AGENT + """
ex:Run a beam:Process ; rdfs:label "Run the script" ; pair:playsRole pair:CodeExecutionStep ;
    beam:use ex:Plan ; beam:produce ex:Output .
ex:Output a beam:Data ; rdfs:label "Script output" .
"""


def test_an_agent_plan_run_as_code_raises_unexpected_code_execution() -> None:
    assert "UnexpectedCodeExecutionRiskPattern" in _patterns(CODE)
    gated = CODE + """
ex:Sandbox a beam:Process ; pair:playsRole pair:ExecutionGuardrailStep ; beam:use ex:Plan ; beam:produce ex:Verdict .
ex:Verdict a beam:Data ; rdfs:label "Execution verdict" ; pair:playsRole pair:GuardrailDecision .
ex:Run beam:use ex:Verdict .
"""
    assert "UnexpectedCodeExecutionRiskPattern" not in _patterns(gated)


def test_an_ordinary_tool_call_is_tool_misuse_and_not_code_execution() -> None:
    plain = CODE.replace("pair:playsRole pair:CodeExecutionStep", "pair:playsRole pair:ToolInvocationStep")
    after = _patterns(plain)
    assert "UnexpectedCodeExecutionRiskPattern" not in after
    assert "ToolMisuseRiskPattern" in after


RELAY = AGENT + """
ex:Planning beam:produce ex:Order .
ex:Order a beam:Data ; rdfs:label "Order" ; pair:playsRole pair:AgentMessage .
ex:Dispatcher a beam:Process ; rdfs:label "Dispatcher agent" ; pair:playsRole pair:AgentHandoffStep ;
    beam:use ex:Order ; beam:produce ex:WorkItem .
ex:WorkItem a beam:Data ; rdfs:label "Work item" ; pair:playsRole pair:AgentMessage .
ex:Executor a beam:Process ; rdfs:label "Executor agent" ; pair:playsRole pair:AgentHandoffStep ;
    beam:use ex:WorkItem ; beam:produce ex:Change .
ex:Change a beam:Data ; rdfs:label "Change request" .
ex:Apply a beam:Process ; rdfs:label "Apply the change" ; pair:playsRole pair:StateChangingStep ;
    beam:use ex:Change ; beam:produce ex:Applied .
ex:Applied a beam:Data ; rdfs:label "Applied" .
"""


def test_a_decision_relayed_twice_into_an_action_raises_cascading_failures() -> None:
    assert "CascadingFailuresRiskPattern" in _patterns(RELAY)
    checkpointed = RELAY + """
ex:Breaker a beam:Process ; pair:playsRole pair:RateLimitControlStep ; beam:use ex:WorkItem ; beam:produce ex:Budget .
ex:Budget a beam:Data ; rdfs:label "Change budget" .
ex:Executor beam:use ex:Budget .
"""
    assert "CascadingFailuresRiskPattern" not in _patterns(checkpointed)


def test_a_single_hand_off_is_not_a_cascade() -> None:
    single = RELAY.replace(
        "ex:Dispatcher a beam:Process ; rdfs:label \"Dispatcher agent\" ; pair:playsRole pair:AgentHandoffStep ;\n    beam:use ex:Order ; beam:produce ex:WorkItem .",
        "ex:Dispatcher a beam:Process ; rdfs:label \"Dispatcher agent\" ; pair:playsRole pair:AgentHandoffStep ;\n    beam:use ex:Order ; beam:produce ex:Change .",
    )
    assert "CascadingFailuresRiskPattern" not in _patterns(single)


APPROVAL = AGENT + """
ex:Approve a beam:Process ; rdfs:label "Engineer approves" ; pair:playsRole pair:HumanApprovalStep ;
    beam:use ex:Plan ; beam:produce ex:Approval .
ex:Approval a beam:Data ; rdfs:label "Approval" .
ex:Act a beam:Process ; rdfs:label "Change the account" ; pair:playsRole pair:StateChangingStep ;
    beam:use ex:Plan, ex:Approval ; beam:produce ex:Changed .
ex:Changed a beam:Data ; rdfs:label "Changed" .
"""


def test_an_approver_who_sees_only_the_plan_raises_trust_exploitation() -> None:
    after = _patterns(APPROVAL)
    assert "HumanAgentTrustExploitationRiskPattern" in after
    # The approval is what clears tool misuse; this is the risk it brings with it.
    assert "ToolMisuseRiskPattern" not in after
    with_evidence = APPROVAL.replace("beam:use ex:Plan ; beam:produce ex:Approval .", "beam:use ex:Plan, ex:Ticket ; beam:produce ex:Approval .")
    assert "HumanAgentTrustExploitationRiskPattern" not in _patterns(with_evidence)


def test_the_bundled_agent_raises_none_of_the_new_agentic_patterns() -> None:
    """It shows no credential, external component, code execution, relay or approval."""
    after = _patterns(example_path(AGENT_NS).read_text(encoding="utf-8"))
    new = {
        "IdentityPrivilegeAbuseRiskPattern", "AgenticSupplyChainRiskPattern",
        "UnexpectedCodeExecutionRiskPattern", "CascadingFailuresRiskPattern",
        "HumanAgentTrustExploitationRiskPattern",
    }
    assert not new & set(after)


# The four patterns added for structures no other pattern covered.

def test_a_trained_model_open_to_public_queries_raises_model_extraction(credit, credit_baseline) -> None:
    assert "ModelExtractionRiskPattern" in credit_baseline
    throttled = credit + """
cs:Throttle a beam:Process ; pair:playsRole pair:RateLimitControlStep ;
    beam:use cs:LoanApplication ; beam:produce cs:Quota .
cs:Quota a beam:Data ; rdfs:label "Query quota" .
cs:ScoreApplication beam:use cs:Quota .
"""
    assert "ModelExtractionRiskPattern" not in _patterns(throttled)


def test_model_extraction_needs_the_queries_to_be_public(credit) -> None:
    internal = _replace(credit, "pair:playsRole pair:PublicUserInput , pair:PredictionRequest .",
                        "pair:playsRole pair:PredictionRequest .")
    assert "ModelExtractionRiskPattern" not in _patterns(internal)


def test_an_agent_action_nothing_records_raises_untraceable_actions() -> None:
    after = _patterns(REGISTRY)
    assert "UntraceableAgentActionsRiskPattern" in after
    logged = REGISTRY + """
ex:Audit a beam:Process ; rdfs:label "Audit log" ; pair:playsRole pair:LoggingStep ;
    beam:use ex:Assignment, ex:Result ; beam:produce ex:Trail .
ex:Trail a beam:Data ; rdfs:label "Audit trail" .
"""
    assert "UntraceableAgentActionsRiskPattern" not in _patterns(logged)


def test_the_bundled_agent_keeps_no_record_of_its_actions() -> None:
    after = _patterns(example_path(AGENT_NS).read_text(encoding="utf-8"))
    assert after["UntraceableAgentActionsRiskPattern"] == 2


PROVIDER = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:   <http://example.org/provider#> .

ex:Sys a beam:System ; rdfs:label "Claims assistant" .
ex:Claim a beam:Data ; rdfs:label "Claim with medical notes" ;
    pair:playsRole pair:UserInput ; pair:containsDataCategory pair:SensitiveInformation .
ex:HostedLLM a beam:StatisticalModel ; rdfs:label "Hosted LLM" ;
    pair:playsRole pair:GenerativeModel, %s .
ex:ApiKey a beam:Data ; rdfs:label "Provider key" ; pair:playsRole pair:ExternalProviderCredential ;
    pair:containsDataCategory pair:ConfidentialInformation .
ex:Answer a beam:Process ; rdfs:label "Draft a reply" ; pair:playsRole pair:GenerationStep ;
    beam:use %s, ex:HostedLLM, ex:ApiKey ; beam:produce ex:Reply .
ex:Reply a beam:Data ; rdfs:label "Reply" ; pair:playsRole pair:UserFacingOutput .
"""


def test_personal_data_sent_to_a_hosted_model_raises_protected_data_to_external_model() -> None:
    assert "ProtectedDataToExternalModelRiskPattern" in _patterns(PROVIDER % ("pair:ExternalModel", "ex:Claim"))
    in_house = PROVIDER % ("pair:FoundationLLM", "ex:Claim")
    assert "ProtectedDataToExternalModelRiskPattern" not in _patterns(in_house)


def test_redacting_before_the_provider_clears_it_and_the_key_alone_never_raises_it() -> None:
    redacted = PROVIDER % ("pair:ExternalModel", "ex:Masked") + """
ex:Mask a beam:Process ; rdfs:label "Mask identifiers" ; pair:playsRole pair:RedactionStep ;
    beam:use ex:Claim ; beam:produce ex:Masked .
ex:Masked a beam:Data ; rdfs:label "Masked claim" ; pair:playsRole pair:UserInput .
"""
    assert "ProtectedDataToExternalModelRiskPattern" not in _patterns(redacted)


MEMORY = AGENT + """
ex:Ticket pair:containsDataCategory pair:SensitiveInformation .
ex:Remember a beam:Process ; rdfs:label "Remember the ticket" ; pair:playsRole %s ;
    beam:use ex:Ticket ; beam:produce ex:Memory .
ex:Memory a beam:Data ; rdfs:label "Agent memory" ; pair:playsRole pair:AgentMemory .
ex:Recall a beam:Process ; pair:playsRole pair:MemoryReadStep ; beam:use ex:Memory ; beam:produce ex:Recalled .
ex:Recalled a beam:Data ; rdfs:label "Recalled" ; pair:playsRole pair:RetrievedContext .
"""


def test_personal_data_kept_in_agent_memory_raises_personal_data_retained() -> None:
    assert "PersonalDataRetainedRiskPattern" in _patterns(MEMORY % "pair:MemoryWriteStep")
    redacting = MEMORY % "pair:MemoryWriteStep, pair:RedactionStep"
    assert "PersonalDataRetainedRiskPattern" not in _patterns(redacting)


def test_a_prediction_log_of_personal_requests_raises_personal_data_retained(credit) -> None:
    logged = credit + """
cs:LoanApplication pair:containsDataCategory pair:SensitiveInformation .
cs:LogPredictions a beam:Process ; rdfs:label "Log predictions" ;
    pair:playsRole pair:LoggingStep ;
    beam:use cs:LoanApplication, cs:CreditScore ;
    beam:produce cs:PredictionLog .
cs:PredictionLog a beam:Data ; rdfs:label "Prediction log" ; pair:playsRole pair:PredictionLog .
"""
    assert "PersonalDataRetainedRiskPattern" in _patterns(logged)
    masked = logged.replace("pair:playsRole pair:LoggingStep ;", "pair:playsRole pair:LoggingStep, pair:RedactionStep ;")
    assert "PersonalDataRetainedRiskPattern" not in _patterns(masked)
