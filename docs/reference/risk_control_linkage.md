# Risk, Motif, Control and Mitigation - linkage reference

The single reference for how a matched motif reaches a mitigation, and what kind
of claim each hop makes. Generated from the ontology and the cross-walk CSV by
`python/scripts/generate_risk_control_linkage.py`; every number is computed.

Supersedes `motif_control_linkage.md` and `control_catalogue_table.md`.

---

## 1. Inventory

| Layer | Count | What it is |
|---|---|---|
| **Motif library** | **47** | Risk-neutral architectural shapes (`pair:GraphMotif`) |
| **Risk patterns** | **33** | Motif + applicability condition -> candidate finding |
| **Suggested controls** | **30** | `pat:Control_*`, the only vocabulary in `pair:suggestedControl` |
| | | |
| MIT control groups | 20 | Categories + sub-categories, **MIT verbatim** |
| MIT mitigation actions | 52 | Concrete actions, **MIT verbatim** |
| PAIR-AI concrete controls | 16 | In `mitctrl:` namespace but **project curation** |
| **Mitigation vocabulary, total** | **88** | of which **72** carry `nexus:isDefinedByTaxonomy` |

### What counts as "a mitigation" depends on the level

Three different numbers are all defensible, so state which one is meant:

- **52** concrete MIT actions (`A0897 Model Prompting`, ...)
- **20** MIT families (4 categories + sub-categories)
- **30** PAIR-AI suggested controls - the only ones a finding emits

The cross-walk CSV has 93 rows, which are risk-to-action *pairs* with
repeats - 93 rows resolve to 52 distinct actions, sitting in
17 MIT sub-categories that land on 14 `mitctrl:` families (three sub-categories alias
onto families already present).

That is the whole of the "94 rows but only 36 concepts" gap: **rows are not
concepts.** Each row is one risk-action pair, many actions recur across risks, and
the 2026-07-17 rollup collapsed every action into its family before the data
reached the graph. The action level is now modelled, so nothing is collapsed away.

> **Careful with the `mitctrl:` namespace.** It holds two different things: 20 MIT-verbatim groups and 16 PAIR-AI-curated controls that are *named after* MIT mitigations but are not entries of the taxonomy. Only the former carry `nexus:isDefinedByTaxonomy`. Reporting them as one number would claim external grounding for project curation.

---

## 2. The four hops, and what each is worth

```
  motif ──hasMotif──▶ risk pattern ──suggestedControl──▶ pat:Control_*
    ▲                      │                                  │
    │                      │ mayIndicateRisk                  │ relatedMatch
    │                      ▼                                  ▼
    └──realizedByMotif── OWASP/Atlas/MIT entry ──▶ mitctrl:family ──broader──▶ mitact:A0xxx
```

| Hop | Evidence | Strength |
|---|---|---|
| motif -> risk pattern | Published catalogues (Fowler, Mercari) + OWASP/ASI anchors | Strong, externally sourced |
| risk pattern -> taxonomy | Explicit triples, every non-anchor SKOS-mapped to the anchor | Strong, test-enforced |
| risk pattern -> control | Project curation | **Weakest hop, nothing upstream to adopt** |
| control -> MIT family | `skos:relatedMatch`, declared *indicative, not audited* | Weak but explicit |
| taxonomy -> MIT family | Embedding cosine top-3, **unvalidated** | Reproducible, not adjudicated |
| MIT family -> action | `skos:broader` from the cross-walk | Faithful to source |

**Two motif relations, opposite in meaning.** *Exposing*: the motif's presence
raises the risk (the motif is the problem). *Realizing*: the motif implements the
control (the motif is the fix). `GuardrailsMotif` is both at once, which is why
they are never merged into one column.

---

## 3. Suggested control -> everything it touches

| # | Suggested control | Candidate risk | Exposing motif | Realizing motif | MIT family | Actions |
|---|---|---|---|---|---|---|
| 1 | **Input validation and prompt isolation**<br>`pat:Control_InputValidationAndPromptIsolation` | GoalHijack, InsecureAgentCommunication, MemoryPoisoning, PromptInjection | AdaptiveRAG, AgentDelegation, AgentMemoryLoop, DebateBasedCooperation, DirectPrompting, GoalCreation, IncrementalModelQuerying, IterativeRAG, LLMBasedInformationRetrieval, ModelQuerying, PlanReflection, ProactiveGoalCreation, QueryRewriting, RecursiveRAG, RetrievalAugmentedGeneration, ToolAgentRegistry, ToolUsingAgent, VotingBasedCooperation | **InputScreening, RetrievalScreening** | input-output-filtering, prompt-context-limiting | 0 |
| 2 | **Output validation and sanitization**<br>`pat:Control_OutputValidationAndSanitization` | ImproperOutputHandling, SensitiveInformationDisclosure, SystemPromptLeakage, UnexpectedCodeExecution | DirectPrompting, ToolAgentRegistry, ToolUsingAgent | **OutputScreening** | content-safety-controls, input-output-filtering | 2 |
| 3 | **Data minimization and redaction**<br>`pat:Control_DataMinimizationAndRedaction` | PersonalDataRetained, ProtectedDataToExternalModel, SensitiveInformationDisclosure | AgentMemoryLoop, DirectPrompting, PredictionLogging, RetrievalAugmentedGeneration, SynchronousPrediction | (none) | data-minimization, privacy-control-for-user-data, redaction | 0 |
| 4 | **Retrieval access control**<br>`pat:Control_RetrievalAccessControl` | SensitiveInformationDisclosure, VectorAndEmbeddingWeakness | Embeddings, Reranker, VectorBasedInformationRetrieval | (none) | access-management, retrieval-quality-evaluation, retrieval-source-filtering | 4 |
| 5 | **Model and dependency provenance**<br>`pat:Control_ModelAndDependencyProvenance` | AgenticSupplyChain, DataAndModelPoisoning, SupplyChainCompromise | AgentDelegation, Embeddings, ExternalDependency, FineTuning, ModelLoad, RetrievalDataAugmentation, ToolAgentRegistry, ToolUsingAgent, TrainingToServing | (none) | model-infrastructure-security, risk-register, system-architecture-documentation | 0 |
| 6 | **Trusted training and indexing data**<br>`pat:Control_TrustedTrainingAndIndexingData` | DataAndModelPoisoning, ImproperRetraining, MemoryPoisoning, ModelBias, VectorAndEmbeddingWeakness | AgentMemoryLoop, BatchTraining, Embeddings, FineTuning, PipelineTraining, Reranker, RetrievalDataAugmentation, TrainThenServe, TrainingToServing, VectorBasedInformationRetrieval | (none) | data-curation-process, data-governance, testing-auditing | 27 |
| 7 | **Tool permission boundaries**<br>`pat:Control_ToolPermissionBoundaries` | ExcessiveAgency, GoalHijack, HumanAgentTrustExploitation, IdentityPrivilegeAbuse, InsecureAgentCommunication, ToolMisuse, UnqualifiedPrediction | AgentDelegation, AgentMemoryLoop, AsynchronousPrediction, BatchPrediction, DebateBasedCooperation, GoalCreation, IncrementalModelQuerying, ModelQuerying, MultiStagePrediction, PlanReflection, PreprocessPrediction, ProactiveGoalCreation, SynchronousPrediction, ToolAgentRegistry, ToolUsingAgent, TrainThenServe, TrainingToServing, VotingBasedCooperation | **ExecutionScreening, HumanOversight** | access-management, human-oversight-protocol, post-deployment-behavior-monitoring | 5 |
| 8 | **System prompt secrecy**<br>`pat:Control_SystemPromptSecrecy` | SystemPromptLeakage | DirectPrompting | (none) | prompt-context-limiting, red-teaming, system-architecture-documentation | 2 |
| 9 | **Grounding and verification**<br>`pat:Control_GroundingAndVerification` | DirectPromptingWithoutGrounding, MisinformationFromWeakGrounding, VectorAndEmbeddingWeakness | AdaptiveRAG, DirectPrompting, Embeddings, IterativeRAG, LLMBasedInformationRetrieval, RecursiveRAG, Reranker, RetrievalAugmentedGeneration, VectorBasedInformationRetrieval | **Evals, HybridRetriever, Reranker, RetrievalAugmentedGeneration, VectorBasedInformationRetrieval** | human-oversight-protocol, retrieval-quality-evaluation, testing-auditing | 12 |
| 10 | **Rate, budget, and loop control**<br>`pat:Control_RateLimitBudgetAndLoopControl` | CascadingFailures, ExcessiveAgency, ModelExtraction, ToolMisuse, TrainingDataMembershipInference, UnboundedConsumption | AgentDelegation, AsynchronousPrediction, BatchPrediction, DebateBasedCooperation, DirectPrompting, IterativeRAG, MultiStagePrediction, PlanReflection, PreprocessPrediction, QueryRewriting, RecursiveRAG, RetrievalAugmentedGeneration, SynchronousPrediction, ToolAgentRegistry, ToolUsingAgent, TrainThenServe, TrainingToServing | (none) | access-management, post-deployment-behavior-monitoring, prompt-context-limiting | 5 |
| 11 | **Logging, monitoring, and evals**<br>`pat:Control_LoggingMonitoringAndEvals` | DataAndModelPoisoning, DatasetShift, DirectPromptingWithoutGrounding, ExcessiveAgency, GoalHijack, InsecureAgentCommunication, MemoryPoisoning, MisinformationFromWeakGrounding, PromptInjection, SupplyChainCompromise, ToolMisuse, UnboundedConsumption, UnevaluatedModel, UntraceableAgentActions | AdaptiveRAG, AgentDelegation, AgentMemoryLoop, AsynchronousPrediction, BatchPrediction, DebateBasedCooperation, DirectPrompting, Embeddings, ExternalDependency, FineTuning, GoalCreation, IncrementalModelQuerying, IterativeRAG, LLMBasedInformationRetrieval, ModelLoad, ModelQuerying, MultiStagePrediction, PlanReflection, PreprocessPrediction, ProactiveGoalCreation, QueryRewriting, RecursiveRAG, RetrievalAugmentedGeneration, RetrievalDataAugmentation, SynchronousPrediction, ToolAgentRegistry, ToolUsingAgent, TrainThenServe, TrainingToServing, VotingBasedCooperation | **Evals, PredictionLogging, PredictionMonitoring** | post-deployment-behavior-monitoring, red-teaming, testing-auditing | 15 |
| 12 | **Input and output filtering**<br>`pat:Control_Guardrails` | AdversarialEvasion, ImproperOutputHandling, PromptInjection, SensitiveInformationDisclosure, SystemPromptLeakage | AdaptiveRAG, AsynchronousPrediction, BatchPrediction, DirectPrompting, IterativeRAG, LLMBasedInformationRetrieval, MultiStagePrediction, PreprocessPrediction, QueryRewriting, RecursiveRAG, RetrievalAugmentedGeneration, SynchronousPrediction, TrainThenServe, TrainingToServing | **Guardrails, InputScreening, OutputScreening, RetrievalScreening** | content-safety-controls, input-output-filtering, model-safety-engineering | 9 |
| 13 | **Distribution shift monitoring**<br>`pat:Control_DistributionShiftMonitoring` | DatasetShift, OutOfDomainInput | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | **PredictionLogging, PredictionMonitoring** | post-deployment-behavior-monitoring, post-deployment-monitoring, testing-auditing | 14 |
| 14 | **Input domain validation**<br>`pat:Control_InputDomainValidation` | OutOfDomainInput | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | (none) | input-output-filtering, testing-auditing | 12 |
| 15 | **Adversarial robustness**<br>`pat:Control_AdversarialRobustness` | AdversarialEvasion | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | (none) | input-output-filtering, model-safety-engineering, red-teaming | 9 |
| 16 | **Pre-release model evaluation**<br>`pat:Control_PreReleaseModelEvaluation` | EvaluationDataContamination, UnevaluatedModel | AsynchronousPrediction, BatchPrediction, BatchTraining, FineTuning, MultiStagePrediction, PipelineTraining, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | **TrainThenServe** | pre-deployment-risk-assessment, staged-deployment, testing-auditing | 12 |
| 17 | **Fairness evaluation**<br>`pat:Control_FairnessEvaluation` | ModelBias | BatchTraining, PipelineTraining, TrainThenServe, TrainingToServing | (none) | data-governance, societal-impact-assessment, testing-auditing | 27 |
| 18 | **Uncertainty reporting and review**<br>`pat:Control_UncertaintyReportingAndReview` | UnqualifiedPrediction | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | **HumanOversight** | human-oversight-protocol, safety-decision-frameworks | 1 |
| 19 | **Retraining data validation**<br>`pat:Control_RetrainingDataValidation` | ImproperRetraining | BatchTraining, FineTuning, PipelineTraining, TrainThenServe, TrainingToServing | (none) | data-curation-process, data-governance | 15 |
| 20 | **Held-out evaluation data**<br>`pat:Control_HeldOutEvaluationData` | EvaluationDataContamination | BatchTraining, FineTuning, PipelineTraining, TrainThenServe | (none) | data-governance, testing-auditing | 26 |
| 21 | **Training data privacy**<br>`pat:Control_TrainingDataPrivacy` | TrainingDataMembershipInference | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | (none) | data-minimization, privacy-control-for-user-data | 0 |
| 22 | **Scoped agent credentials**<br>`pat:Control_ScopedAgentCredentials` | IdentityPrivilegeAbuse | AgentDelegation, AgentMemoryLoop | (none) | access-management | 4 |
| 23 | **Agent component verification**<br>`pat:Control_AgentComponentVerification` | AgenticSupplyChain | AgentDelegation, ToolAgentRegistry, ToolUsingAgent | (none) | model-infrastructure-security, system-architecture-documentation | 0 |
| 24 | **Sandboxed code execution**<br>`pat:Control_SandboxedCodeExecution` | UnexpectedCodeExecution | ToolAgentRegistry, ToolUsingAgent | **ExecutionScreening** | model-infrastructure-security, technical-security-controls | 0 |
| 25 | **Cascade containment**<br>`pat:Control_CascadeContainment` | CascadingFailures | AgentDelegation | **ExecutionScreening, HumanOversight** | human-oversight-protocol, incident-response-plan, post-deployment-behavior-monitoring | 1 |
| 26 | **Independent evidence for approval**<br>`pat:Control_IndependentEvidenceForApproval` | HumanAgentTrustExploitation | ToolAgentRegistry, ToolUsingAgent | (none) | human-oversight-protocol, transparency-accountability-controls | 0 |
| 27 | **Agent action audit log**<br>`pat:Control_AgentActionAuditLog` | UntraceableAgentActions | ToolAgentRegistry, ToolUsingAgent | (none) | post-deployment-behavior-monitoring, transparency-accountability-controls | 1 |
| 28 | **External provider data agreement**<br>`pat:Control_ExternalProviderDataAgreement` | ProtectedDataToExternalModel | DirectPrompting, RetrievalAugmentedGeneration, SynchronousPrediction | (none) | data-governance, privacy-control-for-user-data | 14 |
| 29 | **Retention limits**<br>`pat:Control_RetentionLimits` | PersonalDataRetained | AgentMemoryLoop, PredictionLogging | (none) | data-governance, data-minimization | 14 |
| 30 | **Model access hardening**<br>`pat:Control_ModelAccessHardening` | ModelExtraction | AsynchronousPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | (none) | access-management, post-deployment-behavior-monitoring | 5 |

---

## 4. Candidate risk -> MIT actions (evidence route)

This is the other route to a mitigation: not via the suggested control, but via the
finding's taxonomy entries and the cross-walk. Only OWASP LLM01-06 and LLM09 are
covered - the cross-walk has no rows for LLM07/08/10.

| OWASP risk | MIT families | Distinct actions |
|---|---|---|
| `llm01-prompt-injection` | 5 | 8 |
| `llm02-sensitive-information-disclosure` | 8 | 16 |
| `llm03-supply-chain` | 5 | 21 |
| `llm04-data-and-model-poisoning` | 2 | 3 |
| `llm05-improper-output-handling` | 3 | 3 |
| `llm06-excessive-agency` | 3 | 3 |
| `llm09-misinformation` | 6 | 12 |

Risk patterns with no action-level evidence (12): `AdversarialEvasion`, `DatasetShift`, `ModelBias`, `ModelExtraction`, `OutOfDomainInput`, `PersonalDataRetained`, `SystemPromptLeakage`, `UnboundedConsumption`, `UnevaluatedModel`, `UnqualifiedPrediction`, `UntraceableAgentActions`, `VectorAndEmbeddingWeakness`

---

## 5. MIT family -> actions underneath it

| MIT family | Actions | Reached by a suggested control? |
|---|---|---|
| `data-governance` | 14 | yes |
| `testing-auditing` | 12 | yes |
| `model-safety-engineering` | 7 | yes |
| `access-management` | 4 | yes |
| `risk-disclosure` | 3 | **no** |
| `content-safety-controls` | 2 | yes |
| `incident-reporting` | 2 | **no** |
| `red-teaming` | 2 | yes |
| `system-documentation` | 2 | **no** |
| `data-curation-process` | 1 | yes |
| `incident-response-recovery` | 1 | **no** |
| `post-deployment-behavior-monitoring` | 1 | yes |
| `post-deployment-monitoring` | 1 | yes |
| `risk-management` | 1 | **no** |
| `safety-decision-frameworks` | 1 | yes |
| `societal-impact-assessment` | 1 | yes |
| `user-rights-recourse` | 1 | **no** |

Families with no action beneath them (6): `governance-oversight-controls`, `model-infrastructure-security`, `operational-process-controls`, `staged-deployment`, `technical-security-controls`, `transparency-accountability-controls`

---

## 6. Gaps

1. **19 of 30 controls have no realizing motif.** The tool can advise them but cannot verify from the graph that they were applied.
2. **12 of 47 motifs reach no control** - by design for the risk-neutral ML-serving shapes.
3. **2 risk patterns declare no motif** (`ExcessiveAgencyRiskPattern`, `SensitiveInformationDisclosureRiskPattern`) - deliberately role-anchored, so nothing appears in the Exposing-motif column even though they fire on the bundled examples.
4. **4 circular suggestions** - the motif that triggers the finding is also the motif that would realize the suggested fix.
5. **Coverage is bounded by the cross-walk.** LLM07, LLM08 and LLM10 have no action-level evidence at all; their control links remain prior curation.

---

## 7. Motif library - all 47, by source catalogue

Motifs are risk-neutral: they describe a shape, not a problem. The grouping below
is the *published catalogue each was derived from* (`pair:derivedFrom`), because
that is the only classification the data actually carries. The relation is m:n,
so a motif derived from several catalogues is listed under each of them.

### Liu et al. (2025) - Agent design pattern catalogue: A collection of architectural patterns for foundation model based agents (31)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `ToolUsingAgentMotif` | Agent adapter | AgenticSupplyChain, GoalHijack, HumanAgentTrustExploitation, ToolMisuse, UnexpectedCodeExecution, UntraceableAgentActions |
| `EvalsMotif` | Agent evaluator | *(risk-neutral - none)* |
| `PlanReflectionMotif` | Cross-reflection | GoalHijack, UnboundedConsumption |
| `DebateBasedCooperationMotif` | Debate-based cooperation | InsecureAgentCommunication, UnboundedConsumption |
| `HumanOversightMotif` | Human reflection | *(risk-neutral - none)* |
| `PlanReflectionMotif` | Human reflection | GoalHijack, UnboundedConsumption |
| `IncrementalModelQueryingMotif` | Incremental model querying | GoalHijack |
| `ModelQueryingMotif` | Incremental model querying | GoalHijack |
| `AgentDelegationMotif` | Multi-path plan generator | AgenticSupplyChain, CascadingFailures, GoalHijack, IdentityPrivilegeAbuse, InsecureAgentCommunication |
| `ToolUsingAgentMotif` | Multi-path plan generator | AgenticSupplyChain, GoalHijack, HumanAgentTrustExploitation, ToolMisuse, UnexpectedCodeExecution, UntraceableAgentActions |
| `ExecutionScreeningMotif` | Multimodal guardrails | *(risk-neutral - none)* |
| `GuardrailsMotif` | Multimodal guardrails | *(risk-neutral - none)* |
| `InputScreeningMotif` | Multimodal guardrails | *(risk-neutral - none)* |
| `OutputScreeningMotif` | Multimodal guardrails | *(risk-neutral - none)* |
| `RetrievalScreeningMotif` | Multimodal guardrails | *(risk-neutral - none)* |
| `ModelQueryingMotif` | One-shot model querying | GoalHijack |
| `GoalCreationMotif` | Passive goal creator | GoalHijack |
| `GoalCreationMotif` | Proactive goal creator | GoalHijack |
| `ProactiveGoalCreationMotif` | Proactive goal creator | GoalHijack |
| `PromptResponseOptimiserMotif` | Prompt/response optimiser | *(risk-neutral - none)* |
| `EmbeddingsMotif` | Retrieval augmented generation | DataAndModelPoisoning, VectorAndEmbeddingWeakness |
| `InformationRetrievalMotif` | Retrieval augmented generation | *(risk-neutral - none)* |
| `RerankerMotif` | Retrieval augmented generation | VectorAndEmbeddingWeakness |
| `RetrievalAugmentedGenerationMotif` | Retrieval augmented generation | MisinformationFromWeakGrounding, PromptInjection, ProtectedDataToExternalModel, UnboundedConsumption |
| `VectorBasedInformationRetrievalMotif` | Retrieval augmented generation | VectorAndEmbeddingWeakness |
| `AgentDelegationMotif` | Role-based cooperation | AgenticSupplyChain, CascadingFailures, GoalHijack, IdentityPrivilegeAbuse, InsecureAgentCommunication |
| `PlanReflectionMotif` | Self-reflection | GoalHijack, UnboundedConsumption |
| `AgentDelegationMotif` | Single-path plan generator | AgenticSupplyChain, CascadingFailures, GoalHijack, IdentityPrivilegeAbuse, InsecureAgentCommunication |
| `ToolUsingAgentMotif` | Single-path plan generator | AgenticSupplyChain, GoalHijack, HumanAgentTrustExploitation, ToolMisuse, UnexpectedCodeExecution, UntraceableAgentActions |
| `ToolAgentRegistryMotif` | Tool/agent registry | AgenticSupplyChain, GoalHijack, HumanAgentTrustExploitation, ToolMisuse, UnexpectedCodeExecution, UntraceableAgentActions |
| `VotingBasedCooperationMotif` | Voting-based cooperation | InsecureAgentCommunication |

### Fowler - Patterns of Generative AI (13)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `DirectPromptingMotif` | Direct Prompting | DirectPromptingWithoutGrounding, ImproperOutputHandling, PromptInjection, ProtectedDataToExternalModel, SystemPromptLeakage, UnboundedConsumption |
| `EmbeddingsMotif` | Embeddings | DataAndModelPoisoning, VectorAndEmbeddingWeakness |
| `EvalsMotif` | Evals | *(risk-neutral - none)* |
| `FineTuningMotif` | Fine Tuning | DataAndModelPoisoning, EvaluationDataContamination, ImproperRetraining, SupplyChainCompromise |
| `GuardrailsMotif` | Guardrails | *(risk-neutral - none)* |
| `InputScreeningMotif` | Guardrails | *(risk-neutral - none)* |
| `OutputScreeningMotif` | Guardrails | *(risk-neutral - none)* |
| `HybridRetrieverMotif` | Hybrid Retriever | *(risk-neutral - none)* |
| `QueryRewritingMotif` | Query Rewriting | PromptInjection, UnboundedConsumption |
| `RerankerMotif` | Reranker | VectorAndEmbeddingWeakness |
| `InformationRetrievalMotif` | Retrieval Augmented Generation (RAG) | *(risk-neutral - none)* |
| `RetrievalAugmentedGenerationMotif` | Retrieval Augmented Generation (RAG) | MisinformationFromWeakGrounding, PromptInjection, ProtectedDataToExternalModel, UnboundedConsumption |
| `VectorBasedInformationRetrievalMotif` | Retrieval Augmented Generation (RAG) | VectorAndEmbeddingWeakness |

### Mercari ML System Design Patterns (13)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `TrainThenServeMotif` | Lifecycle | AdversarialEvasion, DatasetShift, EvaluationDataContamination, ImproperRetraining, ModelBias, ModelExtraction, OutOfDomainInput, TrainingDataMembershipInference, UnqualifiedPrediction |
| `TrainingToServingMotif` | Lifecycle | AdversarialEvasion, DataAndModelPoisoning, DatasetShift, ImproperRetraining, ModelBias, ModelExtraction, OutOfDomainInput, TrainingDataMembershipInference, UnevaluatedModel, UnqualifiedPrediction |
| `ModelInImageMotif` | Operation | *(risk-neutral - none)* |
| `ModelLoadMotif` | Operation | SupplyChainCompromise |
| `PredictionLoggingMotif` | Operation | PersonalDataRetained |
| `PredictionMonitoringMotif` | Operation | *(risk-neutral - none)* |
| `AsynchronousPredictionMotif` | Serving | AdversarialEvasion, DatasetShift, ModelExtraction, OutOfDomainInput, TrainingDataMembershipInference, UnevaluatedModel, UnqualifiedPrediction |
| `BatchPredictionMotif` | Serving | AdversarialEvasion, DatasetShift, OutOfDomainInput, TrainingDataMembershipInference, UnevaluatedModel, UnqualifiedPrediction |
| `MultiStagePredictionMotif` | Serving | AdversarialEvasion, DatasetShift, ModelExtraction, OutOfDomainInput, TrainingDataMembershipInference, UnevaluatedModel, UnqualifiedPrediction |
| `PreprocessPredictionMotif` | Serving | AdversarialEvasion, DatasetShift, ModelExtraction, OutOfDomainInput, TrainingDataMembershipInference, UnevaluatedModel, UnqualifiedPrediction |
| `SynchronousPredictionMotif` | Serving | AdversarialEvasion, DatasetShift, ModelExtraction, OutOfDomainInput, ProtectedDataToExternalModel, TrainingDataMembershipInference, UnevaluatedModel, UnqualifiedPrediction |
| `BatchTrainingMotif` | Training | EvaluationDataContamination, ImproperRetraining, ModelBias |
| `PipelineTrainingMotif` | Training | EvaluationDataContamination, ImproperRetraining, ModelBias |

### Gao et al. (2023) - Retrieval-augmented generation for large language models: A survey (9)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `AdaptiveRAGMotif` | Adaptive retrieval | MisinformationFromWeakGrounding, PromptInjection |
| `IterativeRAGMotif` | Iterative retrieval | MisinformationFromWeakGrounding, PromptInjection, UnboundedConsumption |
| `HybridRetrieverMotif` | Mix/hybrid retrieval | *(risk-neutral - none)* |
| `EmbeddingsMotif` | Naive RAG | DataAndModelPoisoning, VectorAndEmbeddingWeakness |
| `InformationRetrievalMotif` | Naive RAG | *(risk-neutral - none)* |
| `RetrievalAugmentedGenerationMotif` | Naive RAG | MisinformationFromWeakGrounding, PromptInjection, ProtectedDataToExternalModel, UnboundedConsumption |
| `VectorBasedInformationRetrievalMotif` | Naive RAG | VectorAndEmbeddingWeakness |
| `RecursiveRAGMotif` | Recursive retrieval | MisinformationFromWeakGrounding, PromptInjection, UnboundedConsumption |
| `RerankerMotif` | Reranking | VectorAndEmbeddingWeakness |

### OWASP Agentic Top 10 (ASI) (4)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `AgentDelegationMotif` | agentic | AgenticSupplyChain, CascadingFailures, GoalHijack, IdentityPrivilegeAbuse, InsecureAgentCommunication |
| `AgentMemoryLoopMotif` | agentic | IdentityPrivilegeAbuse, MemoryPoisoning, PersonalDataRetained |
| `HumanOversightMotif` | agentic | *(risk-neutral - none)* |
| `ToolUsingAgentMotif` | agentic | AgenticSupplyChain, GoalHijack, HumanAgentTrustExploitation, ToolMisuse, UnexpectedCodeExecution, UntraceableAgentActions |

### Breuer et al. (2025) - Large language models for information retrieval: Challenges and chances (3)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `LLMBasedInformationRetrievalMotif` | LLM-enhanced IR | MisinformationFromWeakGrounding, PromptInjection |
| `RerankerMotif` | LLM-enhanced IR | VectorAndEmbeddingWeakness |
| `RetrievalDataAugmentationMotif` | Training data generation | DataAndModelPoisoning |

### Wei et al. (2021) - Finetuned language models are zero-shot learners (3)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `FineTuningMotif` | Instruction tuning | DataAndModelPoisoning, EvaluationDataContamination, ImproperRetraining, SupplyChainCompromise |
| `FineTuningMotif` | Pretrain-finetune | DataAndModelPoisoning, EvaluationDataContamination, ImproperRetraining, SupplyChainCompromise |
| `DirectPromptingMotif` | Prompting | DirectPromptingWithoutGrounding, ImproperOutputHandling, PromptInjection, ProtectedDataToExternalModel, SystemPromptLeakage, UnboundedConsumption |

### Zhu et al. (2026) - Large language models for information retrieval: A survey (2)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `LLMBasedInformationRetrievalMotif` | Generative retriever | MisinformationFromWeakGrounding, PromptInjection |
| `RetrievalDataAugmentationMotif` | Training data augmentation | DataAndModelPoisoning |

### Ma et al. (2023) - Query rewriting for retrieval-augmented large language models (1)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `QueryRewritingMotif` | Rewrite-retrieve-read | PromptInjection, UnboundedConsumption |

### OWASP LLM Top 10 (1)

| Motif | Pattern or section cited | Risk patterns it feeds |
|---|---|---|
| `ExternalDependencyMotif` | supply chain | SupplyChainCompromise |

---

## 8. Risk patterns - all 33

| Risk pattern | Anchor | Motifs | Suggested controls |
|---|---|---|---|
| **AdversarialEvasion** | `adversarial-attack` | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | AdversarialRobustness, Guardrails |
| **AgenticSupplyChain** | `asi04-agentic-supply-chain` | AgentDelegation, ToolAgentRegistry, ToolUsingAgent | AgentComponentVerification, ModelAndDependencyProvenance |
| **CascadingFailures** | `asi08-cascading-failures` | AgentDelegation | CascadeContainment, RateLimitBudgetAndLoopControl |
| **DataAndModelPoisoning** | `llm04-data-and-model-poisoning` | Embeddings, FineTuning, RetrievalDataAugmentation, TrainingToServing | LoggingMonitoringAndEvals, ModelAndDependencyProvenance, TrustedTrainingAndIndexingData |
| **DatasetShift** | `dataset-shift` | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | DistributionShiftMonitoring, LoggingMonitoringAndEvals |
| **DirectPromptingWithoutGrounding** | `llm09-misinformation` | DirectPrompting | GroundingAndVerification, LoggingMonitoringAndEvals |
| **EvaluationDataContamination** | `data-contamination` | BatchTraining, FineTuning, PipelineTraining, TrainThenServe | HeldOutEvaluationData, PreReleaseModelEvaluation |
| **ExcessiveAgency** | `llm06-excessive-agency` | **(none - cannot fire)** | LoggingMonitoringAndEvals, RateLimitBudgetAndLoopControl, ToolPermissionBoundaries |
| **GoalHijack** | `asi01-agent-goal-hijack` | AgentDelegation, GoalCreation, IncrementalModelQuerying, ModelQuerying, PlanReflection, ProactiveGoalCreation, ToolAgentRegistry, ToolUsingAgent | InputValidationAndPromptIsolation, LoggingMonitoringAndEvals, ToolPermissionBoundaries |
| **HumanAgentTrustExploitation** | `asi09-human-agent-trust-exploitation` | ToolAgentRegistry, ToolUsingAgent | IndependentEvidenceForApproval, ToolPermissionBoundaries |
| **IdentityPrivilegeAbuse** | `asi03-identity-and-privilege-abuse` | AgentDelegation, AgentMemoryLoop | ScopedAgentCredentials, ToolPermissionBoundaries |
| **ImproperOutputHandling** | `llm05-improper-output-handling` | DirectPrompting | Guardrails, OutputValidationAndSanitization |
| **ImproperRetraining** | `improper-retraining` | BatchTraining, FineTuning, PipelineTraining, TrainThenServe, TrainingToServing | RetrainingDataValidation, TrustedTrainingAndIndexingData |
| **InsecureAgentCommunication** | `asi07-insecure-inter-agent-communication` | AgentDelegation, DebateBasedCooperation, VotingBasedCooperation | InputValidationAndPromptIsolation, LoggingMonitoringAndEvals, ToolPermissionBoundaries |
| **MemoryPoisoning** | `asi06-memory-and-context-poisoning` | AgentMemoryLoop | InputValidationAndPromptIsolation, LoggingMonitoringAndEvals, TrustedTrainingAndIndexingData |
| **MisinformationFromWeakGrounding** | `llm09-misinformation` | AdaptiveRAG, IterativeRAG, LLMBasedInformationRetrieval, RecursiveRAG, RetrievalAugmentedGeneration | GroundingAndVerification, LoggingMonitoringAndEvals |
| **ModelBias** | `model-bias` | BatchTraining, PipelineTraining, TrainThenServe, TrainingToServing | FairnessEvaluation, TrustedTrainingAndIndexingData |
| **ModelExtraction** | `extraction-attack` | AsynchronousPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | ModelAccessHardening, RateLimitBudgetAndLoopControl |
| **OutOfDomainInput** | `out-of-domain-data` | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | DistributionShiftMonitoring, InputDomainValidation |
| **PersonalDataRetained** | `https://taxonomy.eticas.ai/risk/weak-data-controls` | AgentMemoryLoop, PredictionLogging | DataMinimizationAndRedaction, RetentionLimits |
| **PromptInjection** | `llm01-prompt-injection` | AdaptiveRAG, DirectPrompting, IterativeRAG, LLMBasedInformationRetrieval, QueryRewriting, RecursiveRAG, RetrievalAugmentedGeneration | Guardrails, InputValidationAndPromptIsolation, LoggingMonitoringAndEvals |
| **ProtectedDataToExternalModel** | `personal-information-in-prompt` | DirectPrompting, RetrievalAugmentedGeneration, SynchronousPrediction | DataMinimizationAndRedaction, ExternalProviderDataAgreement |
| **SensitiveInformationDisclosure** | `llm02-sensitive-information-disclosure` | **(none - cannot fire)** | DataMinimizationAndRedaction, Guardrails, OutputValidationAndSanitization, RetrievalAccessControl |
| **SupplyChainCompromise** | `llm03-supply-chain` | ExternalDependency, FineTuning, ModelLoad | LoggingMonitoringAndEvals, ModelAndDependencyProvenance |
| **SystemPromptLeakage** | `llm07-system-prompt-leakage` | DirectPrompting | Guardrails, OutputValidationAndSanitization, SystemPromptSecrecy |
| **ToolMisuse** | `asi02-tool-misuse` | ToolAgentRegistry, ToolUsingAgent | LoggingMonitoringAndEvals, RateLimitBudgetAndLoopControl, ToolPermissionBoundaries |
| **TrainingDataMembershipInference** | `membership-inference-attack` | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | RateLimitBudgetAndLoopControl, TrainingDataPrivacy |
| **UnboundedConsumption** | `llm10-unbounded-consumption` | DebateBasedCooperation, DirectPrompting, IterativeRAG, PlanReflection, QueryRewriting, RecursiveRAG, RetrievalAugmentedGeneration | LoggingMonitoringAndEvals, RateLimitBudgetAndLoopControl |
| **UnevaluatedModel** | `model-misspecification` | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainingToServing | LoggingMonitoringAndEvals, PreReleaseModelEvaluation |
| **UnexpectedCodeExecution** | `asi05-unexpected-code-execution` | ToolAgentRegistry, ToolUsingAgent | OutputValidationAndSanitization, SandboxedCodeExecution |
| **UnqualifiedPrediction** | `model-uncertainty` | AsynchronousPrediction, BatchPrediction, MultiStagePrediction, PreprocessPrediction, SynchronousPrediction, TrainThenServe, TrainingToServing | ToolPermissionBoundaries, UncertaintyReportingAndReview |
| **UntraceableAgentActions** | `https://taxonomy.eticas.ai/risk/untraceable-agent-actions` | ToolAgentRegistry, ToolUsingAgent | AgentActionAuditLog, LoggingMonitoringAndEvals |
| **VectorAndEmbeddingWeakness** | `llm08-vector-and-embedding-weaknesses` | Embeddings, Reranker, VectorBasedInformationRetrieval | GroundingAndVerification, RetrievalAccessControl, TrustedTrainingAndIndexingData |

---

## 9. Controls and mitigations - technical vs non-technical

### 9a. PAIR-AI suggested controls (12) - `pair:controlNature`

This is the axis that matters operationally: a technical control has a footprint
in the architecture, so the assessment can look for it. A non-technical one is
organisational and leaves no structure to detect, so it can only ever be advice.

**Technical (25)**

| Control | Realizing motif | Verifiable from the graph? |
|---|---|---|
| **Adversarial robustness**<br>`Control_AdversarialRobustness` | (none) | no - no motif expresses it |
| **Agent action audit log**<br>`Control_AgentActionAuditLog` | (none) | no - no motif expresses it |
| **Agent component verification**<br>`Control_AgentComponentVerification` | (none) | no - no motif expresses it |
| **Cascade containment**<br>`Control_CascadeContainment` | ExecutionScreening, HumanOversight | **yes** |
| **Data minimization and redaction**<br>`Control_DataMinimizationAndRedaction` | (none) | no - no motif expresses it |
| **Distribution shift monitoring**<br>`Control_DistributionShiftMonitoring` | PredictionLogging, PredictionMonitoring | **yes** |
| **Fairness evaluation**<br>`Control_FairnessEvaluation` | (none) | no - no motif expresses it |
| **Grounding and verification**<br>`Control_GroundingAndVerification` | Evals, HybridRetriever, Reranker, RetrievalAugmentedGeneration, VectorBasedInformationRetrieval | **yes** |
| **Input and output filtering**<br>`Control_Guardrails` | Guardrails, InputScreening, OutputScreening, RetrievalScreening | **yes** |
| **Held-out evaluation data**<br>`Control_HeldOutEvaluationData` | (none) | no - no motif expresses it |
| **Independent evidence for approval**<br>`Control_IndependentEvidenceForApproval` | (none) | no - no motif expresses it |
| **Input domain validation**<br>`Control_InputDomainValidation` | (none) | no - no motif expresses it |
| **Input validation and prompt isolation**<br>`Control_InputValidationAndPromptIsolation` | InputScreening, RetrievalScreening | **yes** |
| **Logging, monitoring, and evals**<br>`Control_LoggingMonitoringAndEvals` | Evals, PredictionLogging, PredictionMonitoring | **yes** |
| **Model access hardening**<br>`Control_ModelAccessHardening` | (none) | no - no motif expresses it |
| **Output validation and sanitization**<br>`Control_OutputValidationAndSanitization` | OutputScreening | **yes** |
| **Pre-release model evaluation**<br>`Control_PreReleaseModelEvaluation` | TrainThenServe | **yes** |
| **Rate, budget, and loop control**<br>`Control_RateLimitBudgetAndLoopControl` | (none) | no - no motif expresses it |
| **Retraining data validation**<br>`Control_RetrainingDataValidation` | (none) | no - no motif expresses it |
| **Retrieval access control**<br>`Control_RetrievalAccessControl` | (none) | no - no motif expresses it |
| **Sandboxed code execution**<br>`Control_SandboxedCodeExecution` | ExecutionScreening | **yes** |
| **Scoped agent credentials**<br>`Control_ScopedAgentCredentials` | (none) | no - no motif expresses it |
| **System prompt secrecy**<br>`Control_SystemPromptSecrecy` | (none) | no - no motif expresses it |
| **Tool permission boundaries**<br>`Control_ToolPermissionBoundaries` | ExecutionScreening, HumanOversight | **yes** |
| **Uncertainty reporting and review**<br>`Control_UncertaintyReportingAndReview` | HumanOversight | **yes** |

**Non-technical (5)**

| Control | Realizing motif | Verifiable from the graph? |
|---|---|---|
| **External provider data agreement**<br>`Control_ExternalProviderDataAgreement` | (none) | never - no architectural footprint |
| **Model and dependency provenance**<br>`Control_ModelAndDependencyProvenance` | (none) | never - no architectural footprint |
| **Retention limits**<br>`Control_RetentionLimits` | (none) | never - no architectural footprint |
| **Training data privacy**<br>`Control_TrainingDataPrivacy` | (none) | never - no architectural footprint |
| **Trusted training and indexing data**<br>`Control_TrustedTrainingAndIndexingData` | (none) | never - no architectural footprint |

### 9b. MIT mitigation vocabulary

Two altitudes, treated differently on purpose.

**The 16 concrete controls carry `pair:controlNature`**, the same
declared axis as 9a. They are the same altitude as a suggested control, so the same
rule applies: technical means a footprint in the architecture; non-technical means
organisation, process, governance or documentation with nothing to detect.

**The 20 families are deliberately not classified.** A family such as
`data-governance` contains both technical and non-technical mitigations, so a single
label at that altitude would be meaningless - the reason `control_mitigation_layer.ttl`
records for keeping them out.

> Do not read `nexus:controlType` as a nature flag. It mixes the MIT category axis
> (governance, technical, operational, transparency-accountability) with a control
> function axis (preventive, detective, corrective).

#### The 16 concrete controls

| Control | Nature | Sits under | Actions |
|---|---|---|---|
| `data-minimization` | **Technical** | operational-process | - |
| `input-output-filtering` | **Technical** | technical-security | - |
| `post-deployment-behavior-monitoring` | **Technical** | operational-process | 1 |
| `privacy-control-for-user-data` | **Technical** | operational-process | - |
| `prompt-context-limiting` ⚖️ | **Technical** | operational-process, technical-security | - |
| `redaction` ⚖️ | **Technical** | operational-process, technical-security | - |
| `retrieval-quality-evaluation` | **Technical** | operational-process | - |
| `retrieval-source-filtering` ⚖️ | **Technical** | operational-process, technical-security | - |
| `data-curation-process` | Non-technical | operational-process | 1 |
| `human-oversight-protocol` | Non-technical | governance-oversight, transparency-accountability | - |
| `incident-response-plan` | Non-technical | operational-process, transparency-accountability | - |
| `pre-deployment-risk-assessment` | Non-technical | governance-oversight, operational-process | - |
| `red-teaming` ⚖️ | Non-technical | operational-process, technical-security | 2 |
| `risk-register` | Non-technical | governance-oversight | - |
| `system-architecture-documentation` | Non-technical | transparency-accountability | - |
| `threat-modelling` ⚖️ | Non-technical | operational-process, technical-security | - |

⚖️ = one of the 5 controls that sit under a technical **and** a
non-technical MIT category at once. The hierarchy cannot decide their nature, so it is
declared rather than derived - previously this document walked to a top-level ancestor
and silently took whichever branch the traversal reached first. All 5 are PAIR-AI curation; the ambiguity comes from this project
parenting its own controls under two families, not from MIT.

#### The 20 families - not classified, by design

| Family | Actions beneath | Reached by a suggested control? |
|---|---|---|
| `data-governance` | 14 | yes |
| `testing-auditing` | 12 | yes |
| `model-safety-engineering` | 7 | yes |
| `access-management` | 4 | yes |
| `risk-disclosure` | 3 | **no** |
| `content-safety-controls` | 2 | yes |
| `incident-reporting` | 2 | **no** |
| `system-documentation` | 2 | **no** |
| `incident-response-recovery` | 1 | **no** |
| `post-deployment-monitoring` | 1 | yes |
| `risk-management` | 1 | **no** |
| `safety-decision-frameworks` | 1 | yes |
| `societal-impact-assessment` | 1 | yes |
| `user-rights-recourse` | 1 | **no** |
| `governance-oversight-controls` | - | **no** |
| `model-infrastructure-security` | - | yes |
| `operational-process-controls` | - | **no** |
| `staged-deployment` | - | yes |
| `technical-security-controls` | - | yes |
| `transparency-accountability-controls` | - | yes |

---

## 10. Provenance summary

| Claim | Basis |
|---|---|
| Motif shapes | Fowler GenAI patterns, Mercari ML system design patterns, OWASP |
| Risk pattern anchors | OWASP LLM Top 10 / OWASP ASI, explicit triples |
| Cross-taxonomy mappings | IBM AI Atlas Nexus SSSOM, adopted verbatim where available |
| Risk -> MIT family | Embedding cosine top-3, unvalidated, reproducible from the CSV |
| MIT families and actions | MIT Draft AI Risk Mitigation Taxonomy, verbatim |
| Control -> MIT family | PAIR-AI curation, declared indicative |
| Suggested control catalogue | PAIR-AI curation |

Per-mapping records with SEMAPV justifications are in `ontology/taxonomy/provenance/mapping_provenance.ttl`.

---

## 11. Files that make up this work

Everything below is in the repository. Paths are the source of truth; this
document is generated from them.

### Knowledge - the vocabularies and the library

| File | Holds |
|---|---|
| `ontology/patterns/motif.ttl` | the 47 motifs and their pattern nodes/edges |
| `ontology/patterns/risk_pattern_library.ttl` | the 33 risk patterns, the 30 suggested controls, and the control-to-MIT bridge |
| `ontology/patterns/control_mitigation_layer.ttl` | technical/non-technical classification and `realizedByMotif` |
| `ontology/core/pair_ai_pattern.ttl` | the pattern meta-vocabulary: roles, predicates, data categories |
| `ontology/core/beam_core.ttl` | BEAM elements and flow predicates |
| `ontology/taxonomy/mit_air_risk_control.ttl` | 20 MIT families (verbatim) + 16 PAIR-AI concrete controls |
| `ontology/taxonomy/mit_mitigation_action.ttl` | **52 MIT mitigation actions** (generated) |
| `ontology/taxonomy/taxonomy_mapping.ttl` | cross-taxonomy mappings + risk-to-control grounding |
| `ontology/taxonomy/owasp_llm.ttl, owasp_asi.ttl, ibm_risk_atlas.ttl, mit_ai_risk.ttl, nist_genai.ttl` | the risk taxonomies |
| `ontology/facets/` | OECD/DPV characterization facets |
| `ontology/patterns/implementation/` | the executable SPARQL: `match/`, `risk/`, `propagation/` |

### Evidence and provenance

| File | Holds |
|---|---|
| `data/mappings/Final_Mapped_Taxonomy_Table_Output.csv` | the 93-row cross-walk (OWASP -> IBM Atlas -> MIT action). **The source of the action layer.** |
| `ontology/taxonomy/provenance/mapping_provenance.ttl` | one `sssom:Mapping` per correspondence, with a SEMAPV justification. Deliberately outside the runner's glob |
| `NOTICE.md` | third-party attribution and licence posture per source |

### Generators - re-run after editing the ontology

```
python python/scripts/generate_mit_action_layer.py        # the 52-action layer
python python/scripts/generate_mapping_provenance.py      # provenance records
python python/scripts/generate_risk_control_linkage.py    # this document
```

### Tests that hold it together

| File | Checks |
|---|---|
| `python/tests/test_library_consistency.py` | motif/risk-pattern/query coherence, taxonomy anchors, role hierarchy |
| `python/tests/test_mapping_integrity.py` | mapping coherence, provenance coverage, cross-walk reproducibility, the action layer |
| `python/tests/test_propagation.py` | data-category propagation and its barriers |

### Background reading

| File | Why |
|---|---|
| `docs/reference/PAIR-AI_glossary_v1_3.md` | terminology and the modelling rules (R1-R10). Read Section C before changing anything |
| `docs/reference/PAIR-AI_method_and_construction.md` | how the knowledge base was built |
| `docs/reference/catalogue.md` | the motif catalogue in prose |
| `docs/claude/CLAUDE.md` | locked decisions, including licence posture per source |

