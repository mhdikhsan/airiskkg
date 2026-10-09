"""What a motif needs around it before a risk pattern holds over its match.

A link from a risk pattern to a motif is carried when the motif alone raises
the pattern. Otherwise the risk depends on what the motif's elements are about:
whether the input comes from the public, the data is personal, the model is
hosted by a provider. That context is listed here per link, in words and as the
annotations that state it, so the library can say which links need it and
insert a motif with it. `test_every_motif_risk_link_fires` holds both halves.
"""

from __future__ import annotations

import copy

from airiskkg.workbench.templates import motif_templates


def _role(node: str, role: str) -> tuple[str, str, str]:
    return (node, "role", role)


def _category(node: str, category: str) -> tuple[str, str, str]:
    return (node, "cat", category)


def _node(key: str, cls: str, label: str, roles=(), cats=()) -> dict:
    return {"key": key, "cls": cls, "label": label, "roles": list(roles), "cats": list(cats)}


def _adds(says: str, nodes: list, edges: list, marks=()) -> tuple:
    return (says, list(marks), {"nodes": nodes, "edges": edges})


# Context stated on elements the motif already has.

def public(node: str) -> tuple:
    return ("the input comes from the public", [_role(node, "PublicUserInput")])


def shown(node: str) -> tuple:
    return ("what it produces is shown to a user", [_role(node, "UserFacingOutput")])


def personal(*nodes: str) -> tuple:
    return ("the data it reads is personal", [_category(n, "SensitiveInformation") for n in nodes])


def stores_personal(node: str) -> tuple:
    return ("what it stores is personal data", [_category(node, "SensitiveInformation")])


def untrusted(node: str) -> tuple:
    return ("content it reads comes from outside and is not vetted", [_category(node, "UntrustedContent")])


def hosted(node: str) -> tuple:
    return ("the model is hosted by an external provider", [_role(node, "ExternalModel")])


def third_party(node: str) -> tuple:
    return ("a component it reads comes from a third party", [_role(node, "ThirdPartyPackage")])


def executes_code(node: str) -> tuple:
    return ("the tool runs code", [_role(node, "CodeExecutionStep")])


def looped(step: str, output: str) -> tuple:
    return _adds("what it produces goes round again, with no bound on the rounds", [], [[step, "use", output]])


def evaluated_on_training_data(evaluation: str, data: str) -> tuple:
    return _adds("the evaluation reads the data the model was trained on", [], [[evaluation, "use", data]])


# Context that brings in an element the motif does not declare.

def credential(*steps: str) -> tuple:
    return _adds(
        "the steps act with the same credential",
        [_node("Context_Credential", "Data", "Access Credential", ["AccessCredential"])],
        [[step, "use", "Context_Credential"] for step in steps],
    )


def public_input_to(step: str) -> tuple:
    return _adds(
        "it reads input from the public",
        [_node("Context_Input", "Data", "Public Input", ["UserInput", "PublicUserInput"])],
        [[step, "use", "Context_Input"]],
    )


def component_for(step: str) -> tuple:
    return _adds(
        "it reads a tool description or plug-in from a third party",
        [_node("Context_Component", "Data", "Third-party Component", ["ThirdPartyPackage"])],
        [[step, "use", "Context_Component"]],
    )


def system_prompt(step: str) -> tuple:
    return _adds(
        "the model is given a system prompt",
        [_node("Context_SystemPrompt", "Data", "System Prompt", ["SystemPrompt"])],
        [[step, "use", "Context_SystemPrompt"]],
    )


def answer_from(source: str, model: str) -> tuple:
    return _adds(
        "what it produces feeds an answer generated for a user",
        [_node("Context_Generation", "Infer", "Generation Step", ["GenerationStep"]),
         _node("Context_Answer", "Data", "Answer", ["UserFacingOutput"])],
        [["Context_Generation", "use", source], ["Context_Generation", "use", model],
         ["Context_Generation", "produce", "Context_Answer"]],
    )


def recalled_into_generation(recalled: str) -> tuple:
    return _adds(
        "what it recalls feeds a generation step",
        [_node("Context_Generation", "Infer", "Generation Step", ["GenerationStep"]),
         _node("Context_Answer", "Data", "Answer", ["UserFacingOutput"])],
        [["Context_Generation", "use", recalled], ["Context_Generation", "produce", "Context_Answer"]],
    )


def request_to(step: str, from_public: bool = False) -> tuple:
    roles = ["PredictionRequest", "PublicUserInput"] if from_public else ["PredictionRequest"]
    return _adds(
        "a request from the public reaches the prediction step" if from_public
        else "a request reaches the prediction step",
        [_node("Context_Request", "Data", "Prediction Request", roles)],
        [[step, "use", "Context_Request"]],
    )


def result_shown(step: str) -> tuple:
    return _adds(
        "its prediction is shown to a user",
        [_node("Context_Result", "Data", "Prediction Result", ["PredictionResult", "UserFacingOutput"])],
        [[step, "produce", "Context_Result"]],
    )


def trained_here(model: str, on_personal: bool = False) -> tuple:
    cats = ["SensitiveInformation"] if on_personal else []
    return _adds(
        "the model is trained in this system, on personal data" if on_personal
        else "the model is trained in this system",
        [_node("Context_Training", "Train", "Training Step", ["TrainingStep"]),
         _node("Context_TrainingData", "Data", "Training Data", ["TrainingDataset"], cats)],
        [["Context_Training", "use", "Context_TrainingData"], ["Context_Training", "produce", model]],
    )


def served_model(step: str) -> tuple:
    return _adds(
        "the step serves a model",
        [_node("Context_Model", "StatisticalModel", "Model", ["Model"])],
        [[step, "use", "Context_Model"]],
    )


def training_data(step: str, category: str | None = None) -> tuple:
    says = {
        None: "the training step reads training data",
        "SensitiveInformation": "it is trained on personal data",
        "UntrustedContent": "it is trained on data nobody vetted",
    }[category]
    return _adds(
        says,
        [_node("Context_TrainingData", "Data", "Training Data", ["TrainingDataset"],
               [category] if category else [])],
        [[step, "use", "Context_TrainingData"]],
    )


def fed_back(producer: str, trainer: str) -> tuple:
    return _adds(
        "what it predicts is fed back into its training data",
        [_node("Context_Outcome", "Data", "Recorded Outcome", ["PredictionResult"])],
        [[producer, "produce", "Context_Outcome"], [trainer, "use", "Context_Outcome"]],
    )


def served_and_fed_back(model: str, trainer: str) -> tuple:
    return _adds(
        "the model is served, and what it predicts is fed back into its training data",
        [_node("Context_Serve", "Infer", "Prediction Step", ["PredictionStep"]),
         _node("Context_Outcome", "Data", "Recorded Outcome", ["PredictionResult"])],
        [["Context_Serve", "use", model], ["Context_Serve", "produce", "Context_Outcome"],
         [trainer, "use", "Context_Outcome"]],
    )


def approved_on(seen: str, action: str) -> tuple:
    return _adds(
        "a person approves the action, seeing only what the agent produced",
        [_node("Context_ApprovalStep", "Process", "Human Approval", ["HumanApprovalStep"]),
         _node("Context_Approval", "Data", "Approval")],
        [["Context_ApprovalStep", "use", seen], ["Context_ApprovalStep", "produce", "Context_Approval"],
         [action, "use", "Context_Approval"]],
    )


def handed_on(receiving: str) -> tuple:
    return _adds(
        "the receiving agent hands the work on to another agent that acts on it",
        [_node("Context_WorkItem", "Data", "Work Item", ["AgentMessage"]),
         _node("Context_NextAgent", "Process", "Next Agent", ["AgentHandoffStep"]),
         _node("Context_Change", "Data", "Change Request"),
         _node("Context_Apply", "Process", "Apply Change", ["StateChangingStep"]),
         _node("Context_Applied", "Data", "Applied Change")],
        [[receiving, "produce", "Context_WorkItem"], ["Context_NextAgent", "use", "Context_WorkItem"],
         ["Context_NextAgent", "produce", "Context_Change"], ["Context_Apply", "use", "Context_Change"],
         ["Context_Apply", "produce", "Context_Applied"]],
    )


def _context(*parts) -> dict:
    says, marks, nodes, edges = [], [], [], []
    for part in parts:
        says.append(part[0])
        marks.extend(part[1])
        if len(part) > 2:
            nodes.extend(part[2]["nodes"])
            edges.extend(part[2]["edges"])
    return {"says": says, "marks": marks, "nodes": nodes, "edges": edges}


_PREDICTION = {
    # motif: (prediction step, model or None, request, result)
    "SynchronousPredictionMotif": ("SyncPred_PredictionStepNode", "SyncPred_ModelNode",
                                   "SyncPred_RequestNode", "SyncPred_ResultNode"),
    "AsynchronousPredictionMotif": ("AsyncPred_PredictionStepNode", None,
                                    "AsyncPred_RequestNode", "AsyncPred_ResultNode"),
    "BatchPredictionMotif": ("BatchPred_JobNode", "BatchPred_ModelNode",
                             "BatchPred_DatasetNode", "BatchPred_ResultNode"),
    "PreprocessPredictionMotif": ("PrepPred_PredictionStepNode", "PrepPred_ModelNode",
                                  "PrepPred_InputNode", "PrepPred_ResultNode"),
    "MultiStagePredictionMotif": ("MultiStage_FastPredictionStepNode", "MultiStage_FastModelNode",
                                  "MultiStage_RequestNode", "MultiStage_QuickResultNode"),
}
_TRAIN_AND_SERVE = {
    # motif: (prediction step, training step)
    "TrainThenServeMotif": ("TrainServe_PredictionStepNode", "TrainServe_TrainingStepNode"),
    "TrainingToServingMotif": ("TrainToServe_PredictionStepNode", "TrainToServe_TrainingPipelineNode"),
}


def _model_of(motif: str) -> tuple:
    step, model, _, _ = _PREDICTION[motif]
    return () if model else (served_model(step),)


def _trained(motif: str, on_personal: bool = False) -> tuple:
    step, model, _, _ = _PREDICTION[motif]
    return _model_of(motif) + (trained_here(model or "Context_Model", on_personal),)


def _build() -> dict[tuple[str, str], dict]:
    table: dict[tuple[str, str], dict] = {}

    def link(pattern: str, motif: str, *parts) -> None:
        table[(f"{pattern}RiskPattern", motif)] = _context(*parts)

    # GenAI
    link("PromptInjection", "DirectPromptingMotif", public("DP_QueryNode"))
    link("PromptInjection", "RetrievalAugmentedGenerationMotif", shown("RAG_ResponseNode"))
    link("PromptInjection", "AdaptiveRAGMotif", shown("AdaRAG_AnswerNode"))
    link("PromptInjection", "IterativeRAGMotif", shown("IterRAG_AnswerNode"))
    link("PromptInjection", "RecursiveRAGMotif", shown("RecRAG_AnswerNode"))
    link("PromptInjection", "QueryRewritingMotif",
         answer_from("QueryRewrite_RetrievedContextNode", "QueryRewrite_LLMNode"))
    link("PromptInjection", "LLMBasedInformationRetrievalMotif",
         answer_from("LLMIR_RetrievedResultNode", "LLMIR_LLMNode"))
    link("UnboundedConsumption", "DirectPromptingMotif", public("DP_QueryNode"))
    link("UnboundedConsumption", "RetrievalAugmentedGenerationMotif",
         looped("RAG_RetrievalStepNode", "RAG_ResponseNode"))
    link("UnboundedConsumption", "QueryRewritingMotif",
         looped("QueryRewrite_RewriteStepNode", "QueryRewrite_RetrievedContextNode"))
    link("SystemPromptLeakage", "DirectPromptingMotif", system_prompt("DP_GenerationStepNode"))
    link("ProtectedDataToExternalModel", "DirectPromptingMotif",
         hosted("DP_ModelNode"), personal("DP_QueryNode"))
    link("ProtectedDataToExternalModel", "RetrievalAugmentedGenerationMotif",
         hosted("RAG_LLMNode"), personal("RAG_QueryNode"))
    link("ProtectedDataToExternalModel", "SynchronousPredictionMotif",
         hosted("SyncPred_ModelNode"), personal("SyncPred_RequestNode"))
    link("DataAndModelPoisoning", "EmbeddingsMotif", untrusted("Embedding_SourceDocumentNode"))
    link("DataAndModelPoisoning", "FineTuningMotif", untrusted("FineTune_DatasetNode"))
    link("DataAndModelPoisoning", "RetrievalDataAugmentationMotif", untrusted("RetrAug_SourceDocumentNode"))
    link("DataAndModelPoisoning", "TrainingToServingMotif",
         training_data("TrainToServe_TrainingPipelineNode", "UntrustedContent"))

    # Agentic
    for motif, planner in (
        ("ToolUsingAgentMotif", "ToolAgent_PlanningStepNode"),
        ("AgentDelegationMotif", "AgentDelegation_DelegatingStepNode"),
        ("PlanReflectionMotif", "PlanReflection_PlanningStepNode"),
    ):
        link("GoalHijack", motif, public_input_to(planner))
    link("GoalHijack", "ToolAgentRegistryMotif", untrusted("Registry_RegistryNode"))
    link("GoalHijack", "GoalCreationMotif", public("GoalCreation_PromptNode"))
    link("GoalHijack", "ModelQueryingMotif", public("ModelQuery_PromptNode"))
    link("GoalHijack", "IncrementalModelQueryingMotif", public("IncrQuery_PromptNode"))
    link("AgenticSupplyChain", "ToolAgentRegistryMotif", third_party("Registry_RegistryNode"))
    link("AgenticSupplyChain", "ToolUsingAgentMotif", component_for("ToolAgent_PlanningStepNode"))
    link("AgenticSupplyChain", "AgentDelegationMotif", component_for("AgentDelegation_DelegatingStepNode"))
    link("UnexpectedCodeExecution", "ToolUsingAgentMotif", executes_code("ToolAgent_ActionStepNode"))
    link("UnexpectedCodeExecution", "ToolAgentRegistryMotif", executes_code("Registry_ToolStepNode"))
    link("HumanAgentTrustExploitation", "ToolUsingAgentMotif",
         approved_on("ToolAgent_PlanNode", "ToolAgent_ActionStepNode"))
    link("HumanAgentTrustExploitation", "ToolAgentRegistryMotif",
         approved_on("Registry_AssignmentNode", "Registry_ToolStepNode"))
    link("IdentityPrivilegeAbuse", "AgentDelegationMotif",
         credential("AgentDelegation_DelegatingStepNode", "AgentDelegation_ReceivingStepNode"))
    link("IdentityPrivilegeAbuse", "AgentMemoryLoopMotif", credential("AgentMemory_WriteStepNode"))
    link("CascadingFailures", "AgentDelegationMotif", handed_on("AgentDelegation_ReceivingStepNode"))
    link("MemoryPoisoning", "AgentMemoryLoopMotif", recalled_into_generation("AgentMemory_RecalledContextNode"))
    link("PersonalDataRetained", "AgentMemoryLoopMotif", stores_personal("AgentMemory_StoreNode"))
    link("PersonalDataRetained", "PredictionLoggingMotif", personal("PredLog_RequestNode"))

    # ML serving
    for motif, (step, model, request, result) in _PREDICTION.items():
        link("AdversarialEvasion", motif, public(request))
        link("TrainingDataMembershipInference", motif, public(request), *_trained(motif, on_personal=True))
        link("UnevaluatedModel", motif, *_trained(motif))
        if motif != "SynchronousPredictionMotif":
            link("UnqualifiedPrediction", motif, shown(result))
        if motif != "BatchPredictionMotif":
            link("ModelExtraction", motif, public(request), *_trained(motif))

    # ML training, and training into serving
    for motif, (step, trainer) in _TRAIN_AND_SERVE.items():
        link("AdversarialEvasion", motif, request_to(step, from_public=True))
        link("OutOfDomainInput", motif, request_to(step))
        link("UnqualifiedPrediction", motif, request_to(step), result_shown(step))
        link("ModelExtraction", motif, request_to(step, from_public=True))
        link("TrainingDataMembershipInference", motif,
             request_to(step, from_public=True), training_data(trainer, "SensitiveInformation"))
        link("ModelBias", motif, training_data(trainer, "SensitiveInformation"))
        link("ImproperRetraining", motif, fed_back(step, trainer))
    link("ModelBias", "BatchTrainingMotif", personal("BatchTrain_DatasetNode"))
    link("ModelBias", "PipelineTrainingMotif", personal("PipeTrain_SourceDataNode"))
    link("ImproperRetraining", "BatchTrainingMotif",
         served_and_fed_back("BatchTrain_ModelArtifactNode", "BatchTrain_TrainingStepNode"))
    link("ImproperRetraining", "PipelineTrainingMotif",
         served_and_fed_back("PipeTrain_ModelArtifactNode", "PipeTrain_TrainingJobNode"))
    link("ImproperRetraining", "FineTuningMotif",
         served_and_fed_back("FineTune_FineTunedModelNode", "FineTune_TrainingStepNode"))
    link("EvaluationDataContamination", "BatchTrainingMotif",
         evaluated_on_training_data("BatchTrain_EvaluationStepNode", "BatchTrain_TrainingDataNode"))
    link("EvaluationDataContamination", "PipelineTrainingMotif",
         evaluated_on_training_data("PipeTrain_EvaluationJobNode", "PipeTrain_IntermediateDataNode"))
    link("EvaluationDataContamination", "FineTuningMotif",
         evaluated_on_training_data("FineTune_EvaluationStepNode", "FineTune_DatasetNode"))
    link("EvaluationDataContamination", "TrainThenServeMotif",
         training_data("TrainServe_TrainingStepNode"),
         evaluated_on_training_data("TrainServe_EvaluationStepNode", "Context_TrainingData"))
    return table


LINK_CONTEXT: dict[tuple[str, str], dict] = _build()


def link_context(pattern: str, motif: str) -> dict | None:
    """The context a link needs, or None when the motif carries the risk pattern."""
    return LINK_CONTEXT.get((pattern, motif))


def template_in_context(motif: str, pattern: str) -> dict:
    """The motif's template with the context that raises this risk pattern over it."""
    template = copy.deepcopy(motif_templates()[motif])
    context = link_context(pattern, motif)
    if context is None:
        return template
    nodes = {node["key"]: node for node in template["nodes"]}
    for key, kind, value in context["marks"]:
        field = "roles" if kind == "role" else "cats"
        values = nodes[key].setdefault(field, []) or []
        if value not in values:
            values.append(value)
        nodes[key][field] = values
    template["nodes"].extend(copy.deepcopy(context["nodes"]))
    template["edges"].extend(copy.deepcopy(context["edges"]))
    return template
