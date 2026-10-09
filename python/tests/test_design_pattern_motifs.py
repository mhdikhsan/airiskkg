"""Motifs read off the agentic and GenAI design pattern references (Liu et al.,
2025; Gao et al., 2023; Breuer et al., 2025; Zhu et al., 2026).

Each motif is drawn here as a small architecture, the way its design pattern
draws it. Every risk pattern declared on the motif has to fire through the
motif's own match, because a declared link nothing can raise is the same drift
as a declaration its query does not read. The control structures carry no risk
pattern, and have to clear what they are suggested against."""

from __future__ import annotations

import pytest
from rdflib import RDF, Graph

from airiskkg.assessment_runner import PAIR, PAT, apply_control, run_assessment_from_text

PREFIXES = """
@prefix ex:   <http://example.org/design-patterns#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
"""

ITERATIVE_RAG = """
ex:Query a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:Docs a beam:Data ; pair:playsRole pair:KnowledgeSource .
ex:Retrieve a beam:Process ; pair:playsRole pair:RetrievalStep ;
    beam:use ex:Query , ex:Docs , ex:Decision ; beam:produce ex:Context .
ex:Context a beam:Data ; pair:playsRole pair:RetrievedContext .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
ex:Generate a beam:Infer ; pair:playsRole pair:GenerationStep ;
    beam:use ex:Context , ex:LLM ; beam:produce ex:Answer .
ex:Answer a beam:Data ; pair:playsRole pair:LLMResponse , pair:UserFacingOutput .
ex:Judge a beam:Process ; pair:playsRole pair:RetrievalJudgeStep ;
    beam:use ex:Answer ; beam:produce ex:Decision .
ex:Decision a beam:Data ; pair:playsRole pair:RetrievalDecision .
"""

RECURSIVE_RAG = """
ex:Query a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:Docs a beam:Data ; pair:playsRole pair:KnowledgeSource .
ex:Retrieve a beam:Process ; pair:playsRole pair:RetrievalStep ;
    beam:use ex:Query , ex:Docs , ex:SubQuestion ; beam:produce ex:Context .
ex:Context a beam:Data ; pair:playsRole pair:RetrievedContext .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
ex:Generate a beam:Infer ; pair:playsRole pair:GenerationStep ;
    beam:use ex:Context , ex:LLM ; beam:produce ex:Answer .
ex:Answer a beam:Data ; pair:playsRole pair:LLMResponse , pair:UserFacingOutput .
ex:Judge a beam:Process ; pair:playsRole pair:RetrievalJudgeStep ;
    beam:use ex:Answer ; beam:produce ex:Decision .
ex:Decision a beam:Data ; pair:playsRole pair:RetrievalDecision .
ex:Decompose a beam:Transform ; pair:playsRole pair:QueryReformulationStep ;
    beam:use ex:Decision ; beam:produce ex:SubQuestion .
ex:SubQuestion a beam:Data ; pair:playsRole pair:SubQuery .
"""

ADAPTIVE_RAG = """
ex:Query a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:Judge a beam:Process ; pair:playsRole pair:RetrievalJudgeStep ;
    beam:use ex:Query ; beam:produce ex:Decision .
ex:Decision a beam:Data ; pair:playsRole pair:RetrievalDecision .
ex:Docs a beam:Data ; pair:playsRole pair:KnowledgeSource .
ex:Retrieve a beam:Process ; pair:playsRole pair:RetrievalStep ;
    beam:use ex:Decision , ex:Docs ; beam:produce ex:Context .
ex:Context a beam:Data ; pair:playsRole pair:RetrievedContext .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
ex:Generate a beam:Infer ; pair:playsRole pair:GenerationStep ;
    beam:use ex:Context , ex:LLM ; beam:produce ex:Answer .
ex:Answer a beam:Data ; pair:playsRole pair:LLMResponse , pair:UserFacingOutput .
"""

LLM_BASED_IR = """
ex:Query a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
ex:Retrieve a beam:Process ; pair:playsRole pair:RetrievalStep ;
    beam:use ex:Query , ex:LLM ; beam:produce ex:Hits .
ex:Hits a beam:Data ; pair:playsRole pair:RetrievedContext .
ex:Generate a beam:Infer ; pair:playsRole pair:GenerationStep ;
    beam:use ex:Hits , ex:LLM ; beam:produce ex:Answer .
ex:Answer a beam:Data ; pair:playsRole pair:UserFacingOutput .
"""

RETRIEVAL_DATA_AUGMENTATION = """
ex:Crawl a beam:Data ; pair:playsRole pair:SourceDocument ;
    pair:containsDataCategory pair:UntrustedContent .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
ex:Write a beam:Infer ; pair:playsRole pair:SyntheticDataGenerationStep ;
    beam:use ex:Crawl , ex:LLM ; beam:produce ex:PseudoQueries .
ex:PseudoQueries a beam:Data ; pair:playsRole pair:SyntheticTrainingData .
ex:Train a beam:Train ; pair:playsRole pair:TrainingStep ;
    beam:use ex:PseudoQueries ; beam:produce ex:Retriever .
ex:Retriever a beam:StatisticalModel ; pair:playsRole pair:RetrieverModel .
"""

PROMPT_RESPONSE_OPTIMISER = """
ex:Input a beam:Data ; pair:playsRole pair:UserInput .
ex:Template a beam:Data ; pair:playsRole pair:PromptTemplate .
ex:Optimise a beam:Transform ; pair:playsRole pair:PromptOptimisationStep ;
    beam:use ex:Input , ex:Template , ex:Result ; beam:produce ex:Prompt , ex:Reply .
ex:Prompt a beam:Data ; pair:playsRole pair:PromptTemplate .
ex:Generate a beam:Infer ; pair:playsRole pair:GenerationStep ;
    beam:use ex:Prompt ; beam:produce ex:Result .
ex:Result a beam:Data ; pair:playsRole pair:LLMResponse .
ex:Reply a beam:Data .
"""

GOAL_CREATION = """
ex:Prompt a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:Memory a beam:Data ; pair:playsRole pair:AgentMemory .
ex:Create a beam:Process ; pair:playsRole pair:GoalCreationStep ;
    beam:use ex:Prompt , ex:Memory ; beam:produce ex:Goal .
ex:Goal a beam:Data ; pair:playsRole pair:AgentGoal .
"""

# The prompt is not public: what reaches the goal unscreened is what the
# detector captured.
PROACTIVE_GOAL_CREATION = """
ex:Prompt a beam:Data ; pair:playsRole pair:UserInput .
ex:Memory a beam:Data ; pair:playsRole pair:AgentMemory .
ex:Detect a beam:Process ; pair:playsRole pair:ContextDetectionStep ;
    beam:produce ex:Screen .
ex:Screen a beam:Data ; pair:playsRole pair:EnvironmentContext .
ex:Create a beam:Process ; pair:playsRole pair:GoalCreationStep ;
    beam:use ex:Prompt , ex:Memory , ex:Screen ; beam:produce ex:Goal .
ex:Goal a beam:Data ; pair:playsRole pair:AgentGoal .
"""

MODEL_QUERYING = """
ex:Ticket a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
ex:Plan a beam:Process ; pair:playsRole pair:PlanningStep ;
    beam:use ex:Ticket , ex:LLM ; beam:produce ex:Steps .
ex:Steps a beam:Data ; pair:playsRole pair:AgentPlan .
"""

INCREMENTAL_MODEL_QUERYING = MODEL_QUERYING + """
ex:Notes a beam:Data ; pair:playsRole pair:UserFeedback .
ex:Plan beam:use ex:Notes .
"""

PLAN_REFLECTION = """
ex:Ticket a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:Plan a beam:Process ; pair:playsRole pair:PlanningStep ;
    beam:use ex:Ticket , ex:Critique ; beam:produce ex:Steps .
ex:Steps a beam:Data ; pair:playsRole pair:AgentPlan .
ex:Reflect a beam:Process ; pair:playsRole pair:PlanReflectionStep ;
    beam:use ex:Steps ; beam:produce ex:Critique .
ex:Critique a beam:Data ; pair:playsRole pair:ReflectionFeedback .
"""

VOTING = """
ex:VoterA a beam:Process ; beam:produce ex:VoteA .
ex:VoterB a beam:Process ; beam:produce ex:VoteB .
ex:VoteA a beam:Data ; pair:playsRole pair:AgentMessage .
ex:VoteB a beam:Data ; pair:playsRole pair:AgentMessage .
ex:Tally a beam:Process ; pair:playsRole pair:VoteAggregationStep ;
    beam:use ex:VoteA , ex:VoteB ; beam:produce ex:Outcome .
ex:Outcome a beam:Data .
"""

DEBATE = """
ex:Proponent a beam:Process ; beam:produce ex:Claim ; beam:use ex:Rebuttal .
ex:Opponent a beam:Process ; beam:produce ex:Rebuttal ; beam:use ex:Claim .
ex:Claim a beam:Data ; pair:playsRole pair:DebateArgument .
ex:Rebuttal a beam:Data ; pair:playsRole pair:DebateArgument .
"""

TOOL_AGENT_REGISTRY = """
ex:Ticket a beam:Data ; pair:playsRole pair:PublicUserInput .
ex:Catalogue a beam:Data ; pair:playsRole pair:ToolRegistry .
ex:Coordinate a beam:Process ; pair:playsRole pair:PlanningStep ;
    beam:use ex:Catalogue , ex:Ticket ; beam:produce ex:Assignment .
ex:Assignment a beam:Data .
ex:CallTool a beam:Process ; pair:playsRole pair:ToolInvocationStep ;
    beam:use ex:Assignment ; beam:produce ex:ToolOutput .
ex:ToolOutput a beam:Data .
"""

# What each risk pattern the registry motif carries needs on top of the bare shape:
# a third-party catalogue, a tool that runs code, and a second coordinator whose
# tool waits on an approver who sees only its assignment. It needs its own
# coordinator because an approval reading a planner's output clears tool misuse
# for every tool that planner drives.
TOOL_AGENT_REGISTRY_CONDITIONS = """
ex:Catalogue pair:playsRole pair:ThirdPartyPackage .
ex:CallTool pair:playsRole pair:CodeExecutionStep .
ex:Escalate a beam:Process ; pair:playsRole pair:PlanningStep ;
    beam:use ex:Catalogue , ex:Ticket ; beam:produce ex:RefundAssignment .
ex:RefundAssignment a beam:Data .
ex:Approve a beam:Process ; pair:playsRole pair:HumanApprovalStep ;
    beam:use ex:RefundAssignment ; beam:produce ex:Approval .
ex:Approval a beam:Data .
ex:Refund a beam:Process ; pair:playsRole pair:ToolInvocationStep ;
    beam:use ex:RefundAssignment , ex:Approval ; beam:produce ex:Refunded .
ex:Refunded a beam:Data .
"""

# (motif, graph, the risk patterns it carries)
CASES = [
    ("IterativeRAGMotif", ITERATIVE_RAG, {
        "PromptInjectionRiskPattern",
        "MisinformationFromWeakGroundingRiskPattern",
        "UnboundedConsumptionRiskPattern",
    }),
    ("RecursiveRAGMotif", RECURSIVE_RAG, {
        "PromptInjectionRiskPattern",
        "MisinformationFromWeakGroundingRiskPattern",
        "UnboundedConsumptionRiskPattern",
    }),
    ("AdaptiveRAGMotif", ADAPTIVE_RAG, {
        "PromptInjectionRiskPattern",
        "MisinformationFromWeakGroundingRiskPattern",
    }),
    ("LLMBasedInformationRetrievalMotif", LLM_BASED_IR, {
        "PromptInjectionRiskPattern",
        "MisinformationFromWeakGroundingRiskPattern",
    }),
    ("RetrievalDataAugmentationMotif", RETRIEVAL_DATA_AUGMENTATION, {
        "DataAndModelPoisoningRiskPattern",
    }),
    ("PromptResponseOptimiserMotif", PROMPT_RESPONSE_OPTIMISER, set()),
    ("GoalCreationMotif", GOAL_CREATION, {"GoalHijackRiskPattern"}),
    ("ProactiveGoalCreationMotif", PROACTIVE_GOAL_CREATION, {"GoalHijackRiskPattern"}),
    ("ModelQueryingMotif", MODEL_QUERYING, {"GoalHijackRiskPattern"}),
    ("IncrementalModelQueryingMotif", INCREMENTAL_MODEL_QUERYING, {"GoalHijackRiskPattern"}),
    ("PlanReflectionMotif", PLAN_REFLECTION, {
        "GoalHijackRiskPattern",
        "UnboundedConsumptionRiskPattern",
    }),
    ("VotingBasedCooperationMotif", VOTING, {"InsecureAgentCommunicationRiskPattern"}),
    ("DebateBasedCooperationMotif", DEBATE, {
        "InsecureAgentCommunicationRiskPattern",
        "UnboundedConsumptionRiskPattern",
    }),
    ("ToolAgentRegistryMotif", TOOL_AGENT_REGISTRY + TOOL_AGENT_REGISTRY_CONDITIONS, {
        "ToolMisuseRiskPattern",
        "GoalHijackRiskPattern",
        "AgenticSupplyChainRiskPattern",
        "UnexpectedCodeExecutionRiskPattern",
        "HumanAgentTrustExploitationRiskPattern",
        "UntraceableAgentActionsRiskPattern",
    }),
]


def _local(term) -> str:
    return str(term).rsplit("#", 1)[-1]


def _assess(ttl: str):
    return run_assessment_from_text(PREFIXES + ttl)


def _matched(result) -> set[str]:
    return {_local(m) for m in result.combined_graph.objects(None, PAIR.matchesMotif)}


def _raised(result) -> set[tuple[str, str]]:
    """(risk pattern, motif) for every finding: which match raised which pattern."""
    graph = result.risk_findings
    return {
        (_local(graph.value(finding, PAIR.generatedByRiskPattern)), _local(motif))
        for finding in graph.subjects(RDF.type, PAIR.RiskFinding)
        for motif in graph.objects(finding, PAIR.generatedByMotif)
    }


def _evidence(result, pattern: str) -> set[str]:
    graph = result.risk_findings
    return {
        _local(element)
        for finding in graph.subjects(PAIR.generatedByRiskPattern, PAT[pattern])
        for element in graph.objects(finding, PAIR.hasEvidence)
    }


@pytest.mark.parametrize("motif, graph, carried", CASES, ids=[case[0] for case in CASES])
def test_the_motif_matches_its_design_pattern_drawn_as_an_architecture(motif, graph, carried) -> None:
    assert motif in _matched(_assess(graph))


@pytest.mark.parametrize("motif, graph, carried", CASES, ids=[case[0] for case in CASES])
def test_every_risk_pattern_the_motif_carries_fires_through_its_own_match(motif, graph, carried) -> None:
    from airiskkg.assessment_runner import load_base_graph

    declared = {_local(p) for p in load_base_graph().objects(PAT[motif], PAIR.hasRiskPattern)}
    assert declared == carried, f"{motif} declares {sorted(declared)}"

    raised = _raised(_assess(graph))
    missing = sorted(pattern for pattern in carried if (pattern, motif) not in raised)
    assert not missing, f"{motif} carries {missing}, but no match of it raised them: {sorted(raised)}"


def test_captured_environment_context_is_untrusted() -> None:
    """The proactive goal creator's own channel: the prompt is not public, so a
    goal hijack here can only come from what the detector captured."""
    result = _assess(PROACTIVE_GOAL_CREATION)
    assert "Screen" in _evidence(result, "GoalHijackRiskPattern")
    assert "Prompt" not in _evidence(result, "GoalHijackRiskPattern")


def test_a_guardrail_on_captured_context_clears_the_goal_hijack() -> None:
    screened = PROACTIVE_GOAL_CREATION + """
ex:Guard a beam:Process ; pair:playsRole pair:InputGuardrailStep ;
    beam:use ex:Screen ; beam:produce ex:Verdict .
ex:Verdict a beam:Data ; pair:playsRole pair:GuardrailDecision .
ex:Create beam:use ex:Verdict .
"""
    result = _assess(screened)
    assert "ProactiveGoalCreationMotif" in _matched(result)
    assert not _evidence(result, "GoalHijackRiskPattern")


def test_a_reply_between_two_agents_is_not_a_debate() -> None:
    """Request and reply is also a two-way exchange between agents. The argument
    role is what tells a debate apart, so plain messages do not match it."""
    result = _assess("""
ex:Asker a beam:Process ; beam:produce ex:Request ; beam:use ex:Reply .
ex:Helper a beam:Process ; beam:use ex:Request ; beam:produce ex:Reply .
ex:Request a beam:Data ; pair:playsRole pair:AgentMessage .
ex:Reply a beam:Data ; pair:playsRole pair:AgentMessage .
""")
    assert "DebateBasedCooperationMotif" not in _matched(result)


# ---- the control structures ----

RAG_WITHOUT_SCREENING = """
ex:Query a beam:Data ; pair:playsRole pair:UserInput .
ex:Docs a beam:Data ; pair:playsRole pair:KnowledgeSource .
ex:Retrieve a beam:Process ; pair:playsRole pair:RetrievalStep ;
    beam:use ex:Query , ex:Docs ; beam:produce ex:Context .
ex:Context a beam:Data ; pair:playsRole pair:RetrievedContext .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel .
ex:Generate a beam:Infer ; pair:playsRole pair:GenerationStep ;
    beam:use ex:Context , ex:LLM ; beam:produce ex:Answer .
ex:Answer a beam:Data ; pair:playsRole pair:UserFacingOutput .
"""

RAG_GUARDRAIL = """
ex:Screen a beam:Process ; pair:playsRole pair:RetrievalGuardrailStep ;
    beam:use ex:Context ; beam:produce ex:Verdict .
ex:Verdict a beam:Data ; pair:playsRole pair:GuardrailDecision .
ex:Generate beam:use ex:Verdict .
"""


def test_a_rag_guardrail_is_a_retrieval_screening_that_clears_prompt_injection() -> None:
    """Liu et al.'s RAG guardrails: the screened content was retrieved, not typed
    by the user, which is why Input Screening does not see it."""
    bare = _assess(RAG_WITHOUT_SCREENING)
    assert "Context" in _evidence(bare, "PromptInjectionRiskPattern")

    screened = _assess(RAG_WITHOUT_SCREENING + RAG_GUARDRAIL)
    matched = _matched(screened)
    assert "RetrievalScreeningMotif" in matched
    assert "InputScreeningMotif" not in matched
    assert not _evidence(screened, "PromptInjectionRiskPattern")


def test_the_tool_mediation_rewrite_builds_an_execution_screening() -> None:
    """The rewrite a reader applies from a tool-misuse finding inserts the shape
    the Execution Screening motif declares, so the control it realizes and the
    structure the canvas inserts are one thing."""
    architecture = PREFIXES + """
ex:Plan a beam:Process ; pair:playsRole pair:PlanningStep ; beam:produce ex:Steps .
ex:Steps a beam:Data .
ex:CallTool a beam:Process ; pair:playsRole pair:ToolInvocationStep ;
    beam:use ex:Steps ; beam:produce ex:ToolOutput .
ex:ToolOutput a beam:Data .
"""
    before = run_assessment_from_text(architecture)
    finding = next(before.risk_findings.subjects(
        PAIR.generatedByRiskPattern, PAT.ToolMisuseRiskPattern))
    rewrite = apply_control(before.combined_graph, PAT.Control_ToolPermissionBoundaries, finding)
    assert len(rewrite), "the rewrite inserted nothing"

    amended = Graph().parse(data=architecture, format="turtle")
    for triple in rewrite:
        amended.add(triple)
    after = run_assessment_from_text(amended.serialize(format="turtle"))

    assert "ExecutionScreeningMotif" in _matched(after)
    assert not _evidence(after, "ToolMisuseRiskPattern")
