# PAIR-AI Catalogue — Motifs, Risk Patterns & Annotation Roles

The complete inventory of what PAIR-AI can recognise and flag: every **motif**
(28), every **risk pattern** (15), every **annotation role** (95), and the
**data categories** (7). Terminology follows
[PAIR-AI_glossary_v1_3.md](PAIR-AI_glossary_v1_3.md); counts were read off the
loaded ontology on 2026-08-06. This file is maintained by hand — if the library
changes and this page does not, this page is wrong.

## How the three fit together

- **Roles** annotate elements. You put a `pair:playsRole` on a single BEAM
  element (a box) — one element may carry several roles.
- **Motifs** are the *linter rules*. A motif is a type-level configuration of
  **role-tagged elements plus the flow edges between them** (`beam:use` /
  `beam:produce` / `beam:inform`). Matching finds the configuration; a motif is
  **risk-neutral by itself** — it says what structure is present, never whether
  that structure is dangerous.
- **Risk patterns** are the *alerts*. When a motif match also satisfies a risk
  pattern's applicability conditions (a data category, the absence of a
  represented control, a tool edge…), PAIR-AI emits a **candidate** risk finding.

> **Per-element or combination?** Annotation is **per-element** — you tag each
> box on its own. Recognition is **per-combination** — a motif only matches when
> several correctly-tagged elements are wired together in the expected shape. So
> one box's role is meaningless in isolation; it becomes a finding only in
> concert with the others (e.g. `GenerationStep` + `GenerativeModel` +
> `UserFacingOutput` + a `beam:use`/`beam:produce` wiring = a Direct-Prompting
> match). You never annotate "a combination"; you annotate the parts and let the
> motif capture the combination.

Two properties of the library shape how to read the tables below:

- **Motifs nest.** A smaller motif is often a subgraph of a larger one and
  co-matches with it (Vector-IR inside RAG). Match counts measure *structural
  coverage*, not how many distinct things a system does.
- **Motifs cannot express absence.** Matching is monotone — a motif that matches
  a graph matches every extension of it. Every "without", "only", "direct" claim
  lives in an applicability condition, never in a motif (glossary R9).
- **Process typing does not affect matching.** Step nodes match on
  `a/rdfs:subClassOf* beam:Process`, so `beam:Process`, `beam:Infer`,
  `beam:Transform`, `beam:Train`, and `beam:Generate` all bind identically. Type
  a step whichever way fits your architecture; the **role** is what selects it.

---

## 1. Motifs (28)

Motifs are risk-neutral: they describe *structure*, not danger. The **Feeds**
column lists the risk patterns **declared** on the motif via
`pair:hasRiskPattern` (see §2).

> **The declared binding is not the whole firing story.** Risk queries evaluate
> their conditions over *any* `pair:MotifMatch` whose bindings carry the required
> roles, not only over matches of the declared motif. In the bundled examples an
> External Dependency match also produces an improper-output-handling finding, and
> a Reranker match also produces a prompt-injection finding. Read **Feeds** as
> "what this motif was curated to gate", and the risk pattern's **Fires when**
> in §2 as the actual trigger.

### Gen AI — generation & retrieval

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **DirectPromptingMotif** | A user query handled directly by a generative-model step, producing a user-facing answer. | LLM09 (no grounding), LLM05, LLM01, LLM10 |
| **RetrievalAugmentedGenerationMotif** | User query → query-driven retrieval of context from any knowledge source → build prompt → LLM → answer. Retrieval is *driven by* the query (it `beam:use`s it); context may pass reranking/aggregation on the way. | LLM09 (misinformation), LLM01, LLM10 |
| **InformationRetrievalMotif** | A retrieval step uses a query and a knowledge source and produces retrieved context (the retrieval stage on its own). The source may be a vector store, keyword index, knowledge graph, or relational store. | LLM02 |
| **VectorBasedInformationRetrievalMotif** | The same shape, specialized to a vector store. Nests inside InformationRetrievalMotif: a vector system matches both. | LLM08 |
| **EmbeddingsMotif** | Source documents/data chunked and transformed into vectors stored in a vector index. | LLM04, LLM08 |
| **QueryRewritingMotif** | An LLM reformulates a user query into alternative queries used for retrieval. | LLM01, LLM10 |
| **RerankerMotif** | A candidate set of retrieved fragments is reranked by a model to select context. | LLM08 |
| **InputScreeningMotif** | A step screens user input and informs the generation step it protects. Nests inside GuardrailsMotif; realizes input validation without requiring the whole guarded-generation topology. | — (clears LLM01) |
| **OutputScreeningMotif** | A step screens a generated response before release. Nests inside GuardrailsMotif. | — |
| **HybridRetrieverMotif** | Vector search and keyword/structured search combined and aggregated into a candidate context set. | — |

### Gen AI — controls & evaluation

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **GuardrailsMotif** | Input/output guardrail steps screen or sanitize prompts and responses around the LLM. Flow-agnostic: anchored on the `inform` edges, so it matches whether generation consumes the user prompt directly or a constructed prompt. | LLM05, LLM07 |
| **EvalsMotif** | Model input, output, expected output, and optional context are scored/judged into evaluation results. | — |

> **A control motif is not a safe motif.** Guardrails and Evals are what
> absence-of-control conditions look for, so their presence suppresses findings
> that test for a missing control on that path (LLM01, LLM09, LLM10). But
> Guardrails is itself risk-bearing: it is the declared gate for improper output
> handling and system-prompt leakage, because a screened path still carries the
> hidden instructions and the unvalidated output it screens. Adding a control
> motif to an architecture means re-assessing the amended architecture, not
> assuming a clean sheet — the same caveat is recorded on the controls in
> `ontology/patterns/control_mitigation_layer.ttl`.

### Gen AI — adaptation

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **FineTuningMotif** | A pre-trained LLM further trained on a task/domain dataset to produce a fine-tuned model. | LLM04, LLM03 |

### Agentic

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **ToolUsingAgentMotif** | A planning step decides on an action and hands off (`inform`) to a step that invokes an external tool or changes external state, producing a result the system consumes. Risk-neutral: acting through tools is what makes an agent useful. | ASI02 |
| **AgentMemoryLoopMotif** | A step writes content to an agent memory store and a later step reads that same store back into a working context — the loop through a store is the distinguishing shape, and why one bad write outlives the turn that produced it. | ASI06 |
| **AgentDelegationMotif** | One agent's planning step produces a message that another agent's handoff step consumes and acts on, so work crosses an agent boundary. The named message is what makes the crossing assessable. | ASI07 |
| **HumanOversightMotif** | A human approval step informs an acting step, which produces the action's result. A **control** motif: matching it *suppresses* the tool-misuse finding on the mediated path rather than raising anything. | — (suppresses ASI02) |

### Prediction / serving (classic ML)

| Motif | Recognises |
| --- | --- |
| **SynchronousPredictionMotif** | A prediction step runs inline with a request and returns before the workflow proceeds. |
| **AsynchronousPredictionMotif** | Prediction requests decoupled from execution via a queue/cache. |
| **BatchPredictionMotif** | A scheduled job runs prediction over a batch dataset and stores results. |
| **PreprocessPredictionMotif** | Preprocessing and prediction as separate steps connected by preprocessed data. |
| **MultiStagePredictionMotif** | One path returns a quick result while another produces a slower/richer result. |

### Training

| Motif | Recognises |
| --- | --- |
| **BatchTrainingMotif** | A scheduled job prepares data, trains a model, evaluates it, records artifact + evaluation. |
| **PipelineTrainingMotif** | Training decomposed into independently executable pipeline jobs with intermediate data. |

### Lifecycle (train → serve)

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **TrainThenServeMotif** | Training and serving separated by evaluation, approval, and a release step. | — |
| **TrainingToServingMotif** | A training pipeline automatically produces an artifact built/deployed into serving. | LLM04, LLM03 |

### Operational

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **ModelLoadMotif** | Server image and model artifact managed separately; model loaded before prediction. | LLM03 |
| **ModelInImageMotif** | A trained artifact packaged into a serving image deployed as the runtime. | LLM03 |
| **PredictionLoggingMotif** | Prediction inputs/results/latency collected into logs. | — |
| **PredictionMonitoringMotif** | Logs/result trends monitored against expected behavior; may raise alerts. | — |

### Supply chain

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **ExternalDependencyMotif** | An external dependency, pre-trained model, artifact, or serving image is used by a step. Risk-neutral by itself. | LLM03 |

---

## 2. Risk patterns (15)

Each risk pattern interprets a motif match:
**Motif + Applicability Conditions + Mechanism + Taxonomy Links + Controls**.
**Fires when** is the verified trigger; **Declared motif** is what the library
binds the pattern to via `pair:hasMotif`; **Suggested controls** are the
mitigations attached to the finding.

| Taxonomy | Risk pattern | Fires when | Declared motif | Suggested controls |
| --- | --- | --- | --- | --- |
| **LLM01** | Prompt injection | Untrusted content (from retrieval/tools, tainted by public input) reaches generation → user output, with no input/output control. | Direct Prompting, RAG, Query Rewriting | Guardrails; input validation & prompt isolation; logging/monitoring/evals |
| **LLM02** | Sensitive data retrieval exposure | The store **and** the retrieved result carry `SensitiveInformation` → generation → user output, no disclosure control. | Vector-IR | Data minimization & redaction; guardrails; output validation & sanitization; retrieval access control |
| **LLM03** | Supply chain compromise | An external model / data / dependency / artifact is used, with no control on it. | External Dependency, Fine Tuning, Model Load, Model-in-Image, Training-to-Serving | Model & dependency provenance; logging/monitoring/evals |
| **LLM04** | Data & model poisoning | A bound source tagged `UntrustedContent` enters embeddings / fine-tuning / training-to-serving. | Embeddings, Fine Tuning, Training-to-Serving | Trusted training & indexing data; model & dependency provenance; logging/monitoring/evals |
| **LLM05** | Improper output handling | Generation → user output with no `OutputValidationStep` / `OutputGuardrailStep`. | Direct Prompting, Guardrails | Output validation & sanitization; guardrails |
| **LLM06** | Excessive agency | The generation step `inform`s a `ToolInvocationStep` / `StateChangingStep`, no control on it. | *none — deliberately role-anchored, applies to any match binding the generation step* | Tool permission boundaries; rate/budget/loop control; logging/monitoring/evals |
| **LLM07** | System prompt leakage | A `SystemPrompt` feeds generation → user output, no control. | Guardrails | System prompt secrecy; output validation & sanitization; guardrails |
| **LLM08** | Vector & embedding weakness | A vector retrieval or embedding index supplies generation context. | RAG, Embeddings, Reranker | Trusted training & indexing data; retrieval access control; grounding & verification |
| **LLM09** | Misinformation (weak grounding) | A RAG generation reaches a response with no `EvaluationStep` / `ScoringStep`. | RAG | Grounding & verification; logging/monitoring/evals |
| **LLM09** | Direct prompting without grounding | A Direct-Prompting generation with no `KnowledgeSource` / `RetrievedContext` grounding. | Direct Prompting | Grounding & verification; logging/monitoring/evals |
| **LLM10** | Unbounded consumption | An LLM/retrieval loop or generation with no `RateLimitControlStep`. | Direct Prompting, RAG, Query Rewriting | Rate/budget/loop control; logging/monitoring/evals |
| **ASI02** | Tool misuse | A planning step's decision reaches a tool invocation or state change with no represented policy enforcement, human approval, or rate/budget control in between. The agent acts within its permissions; what is missing is anything that can narrow, pause, or refuse a particular action. | Tool-Using Agent | Tool permission boundaries; rate/budget/loop control; logging/monitoring/evals |
| **ASI01** | Agent goal hijack | Untrusted content reaches the step that decides the agent's next action, with nothing screening it. Distinct from LLM01 by *where* the content lands: a hijacked goal makes every later step correct execution of the wrong objective. Binds the planning node of either agentic motif. | Tool-Using Agent, Agent Delegation | Input validation & prompt isolation; tool permission boundaries; logging/monitoring/evals |
| **ASI07** | Insecure inter-agent communication | A message crosses between agents and is acted on with no represented validation, guardrail, or policy step. | Agent Delegation | Input validation & prompt isolation; tool permission boundaries; logging/monitoring/evals |
| **ASI06** | Memory & context poisoning | Content is committed to agent memory with no represented `MemoryValidationStep`, **and** the recalled context later reaches a generation step. | Agent Memory Loop | Trusted training & indexing data; input validation & prompt isolation; logging/monitoring/evals |

Each pattern also links to IBM AI Risk Atlas, MIT AI Risk Repository subdomains,
and (where applicable) NIST AI 600-1 entries via `pair:mayIndicateRisk`; the
agentic patterns carry both their ASI entry and the related LLM entry.

*All findings are **candidate** risks — structural dispositions, not confirmed
failures. Missing findings usually mean a missing role, not a safe system.*

---

## 3. Annotation roles (95)

Assign with `pair:playsRole`. Roles are organised into sub-role hierarchies
(shown by the groups below); a motif that asks for a parent role also matches its
sub-roles (`pair:subRoleOf*`). The four top-level roles are `ResourceRole`,
`ProcessingStep`, `ControlStep`, and `UserInput`.

> **Parent choice is load-bearing.** Match queries walk
> `pair:playsRole/pair:subRoleOf*` from a general role, so a precise role parented
> to the wrong abstraction is inert — tagging an element with the obviously-correct
> term then silently prevents the motif from matching. `RewrittenQuery` sits under
> `UserInput` and `RerankedContext` under `RetrievedContext` for exactly this reason.

### User I/O
*(typical BEAM type: `beam:Data`)*

| Role | Definition |
| --- | --- |
| `UserInput` | Information provided directly by a user (UI or API input). Top-level role. |
| `PublicUserInput` | Input from an open/public population (anonymous or self-registered). **Treated as untrusted** by taint propagation. |
| `UserFacingOutput` | Data exposed to a user or downstream consumer (a sink). |
| `PublicUserFacingOutput` | User-facing output exposed to the public (e.g. a chatbot response). |

### Resources
*(the root of the non-process branch)*

| Role | Definition |
| --- | --- |
| `ResourceRole` | A role played by a non-process resource: data, models, stores, or artifacts. Corresponds to the non-process Boxology boxes. Top-level role. |

### Models
*(typical BEAM type: `beam:StatisticalModel` / `beam:SemanticModel`)*

| Role | Definition |
| --- | --- |
| `Model` | A machine-learning or statistical model resource (Boxology model box). |
| `GenerativeModel` | A model that generates content (e.g. an LLM) at inference time. |
| `FoundationLLM` | A foundation LLM used directly for generation. |
| `PretrainedModel` | A pre-trained model before/without task-specific adaptation. |
| `FineTunedModel` | A model produced by fine-tuning a pre-trained model. |
| `EmbeddingModel` | A model that transforms data into vector embeddings. |
| `JudgeModel` | A model that scores/evaluates another model's output (LLM-as-judge). |
| `RerankerModel` | A model (usually a cross-encoder) that scores candidate relevance. |
| `LoadedModel` | A model instance loaded into a serving runtime. |
| `ModelArtifact` | A persisted model artifact (weights/checkpoint). |

### Knowledge sources & retrieval
*(stores: `beam:Data` / `beam:SemanticModel`; results: `beam:Data`)*

| Role | Definition |
| --- | --- |
| `KnowledgeSource` | A source of information the system can access (DB, knowledge graph, API). |
| `VectorStore` | A vector database serving as a knowledge source for retrieval. |
| `VectorIndex` | An index over embedding vectors. |
| `KeywordIndex` | A keyword/text index used for lexical search. |
| `AgentMemory` | A store holding content the system retains across turns or sessions and reads back into later reasoning (summaries, scratchpads, long-term memory). A `KnowledgeSource` the system **writes to as well as reads from**. |
| `AgentMessage` | Content passed from one agent to another to hand off a task, a result, or a request: the carrier of a delegation, and what a validation step can inspect. |
| `RetrievedContext` | Content returned by a retrieval step for use as context. |
| `RetrievedResult` | A result item returned by a retrieval step (a `RetrievedContext`). |
| `RetrievedCandidateSet` | A set of retrieved candidate fragments prior to reranking. |
| `RerankedContext` | Reranked, selected context fragments for generation (a `RetrievedContext`). |
| `SourceDocument` | A source document ingested into a knowledge base. |
| `DocumentChunk` | A chunk of a source document used for embedding/retrieval. |
| `EmbeddingVector` | A stored embedding vector. |

### Prompts & generation resources
*(typical BEAM type: `beam:Data`)*

| Role | Definition |
| --- | --- |
| `PromptTemplate` | A prompt template combining instructions and inputs. |
| `SystemPrompt` | A hidden system prompt / instruction template, not authored by the end user (a `PromptTemplate`). |
| `LLMResponse` | A response from a generative model, prior to output screening. |
| `RewrittenQuery` | A reformulated query produced by a query-rewriting step (a `UserInput` — same untrusted provenance). |
| `SanitizedOutput` | Output that has passed an output guardrail / sanitization step. |
| `GuardrailDecision` | An allow/block decision produced by a guardrail step. |

### Evaluation resources

| Role | Definition |
| --- | --- |
| `ExpectedOutput` | A reference/expected output used in evaluation. |
| `EvaluationResult` | The result produced by an evaluation step. |
| `EvaluationScore` | A numeric score produced by an evaluation step. |

### Prediction & serving resources

| Role | Definition |
| --- | --- |
| `PredictionRequest` | An incoming request for a prediction. |
| `PredictionResult` | The result of a prediction step. |
| `PredictionQueue` | A queue holding prediction requests. |
| `PredictionLog` | A log of predictions for monitoring/audit. |
| `MonitoringBaseline` | A baseline used by a monitoring step. |
| `Alert` | An alert raised by a monitoring step. |
| `ServingImage` | A container image used to serve a model. |
| `ReleaseApproval` | An approval artifact gating a release. |

### Datasets

| Role | Definition |
| --- | --- |
| `TrainingDataset` | A dataset used to train a model. |
| `FineTuningDataset` | A dataset used to fine-tune a model. |
| `BatchDataset` | A dataset processed in batch. |
| `PreprocessedData` | Data produced by a preprocessing step. |

### External / supply chain
*(sub-roles of `ExternalDependency`)*

| Role | Definition |
| --- | --- |
| `ExternalDependency` | A resource sourced outside the org's control whose provenance/integrity the graph cannot vouch for. |
| `ExternalModel` | A model from an external provider or hub (API-served or downloaded weights). |
| `ThirdPartyPackage` | A third-party software package, library, or plugin. |
| `ExternalProviderCredential` | A credential (API key, token) for an external provider. |

### Processing steps
*(typical BEAM type: `beam:Transform` or `beam:Infer`; sub-roles of `ProcessingStep`)*

| Role | Definition |
| --- | --- |
| `ProcessingStep` | A workflow step (Boxology process box). Top-level role. |
| `RetrievalStep` | Retrieves fragments from a knowledge source. |
| `VectorSearchStep` | Performs vector similarity search. |
| `KeywordSearchStep` | Performs keyword/lexical search. |
| `AggregationStep` | Aggregates results from multiple searches. |
| `RerankingStep` | Reranks retrieved candidates. |
| `QueryReformulationStep` | Reformulates a query. |
| `PromptConstructionStep` | Assembles a prompt from inputs and context. |
| `GenerationStep` | Runs a generative model to produce output (Boxology infer). |
| `EmbeddingStep` | Produces embeddings from data. |
| `ChunkingStep` | Splits documents into chunks. |
| `EvaluationStep` | Evaluates model behavior. |
| `ScoringStep` | Scores a model output during evaluation. |
| `PredictionStep` | Runs model inference to produce a prediction. |
| `FastPredictionStep` | A low-latency prediction step. |
| `SlowPredictionStep` | A higher-latency prediction step. |
| `PreprocessingStep` | Preprocesses input data. |
| `TrainingStep` | Trains a model. |
| `TrainingPipeline` | Orchestrates model training. |
| `FineTuningStep` | Fine-tunes a pre-trained model. |
| `DeploymentStep` | Deploys a model to serving. |
| `ModelLoadStep` | Loads a model into a runtime. |
| `ImageBuildStep` | Builds a serving image. |
| `LoggingStep` | Logs predictions or events. |
| `MonitoringStep` | Monitors a deployed model. |
| `JobScheduler` | Schedules jobs in a workflow. |
| `ToolInvocationStep` | Invokes an external tool/plugin/API (agentic tool use). |
| `StateChangingStep` | Changes external state (writes, transactions, side effects). |

### Agentic steps
*(the agentic layer; `MemoryReadStep` is a `RetrievalStep`, the rest are `ProcessingStep`s)*

| Role | Definition |
| --- | --- |
| `PlanningStep` | The system decides what to do next — selecting a tool, ordering sub-tasks, revising a goal — rather than producing the user-facing answer. What distinguishes an agent from a single generation call. |
| `MemoryWriteStep` | Commits content to agent memory for reuse in later turns or sessions. |
| `MemoryReadStep` | Reads retained agent memory back into a working context (retrieval over the system's own history). |
| `AgentHandoffStep` | Receives work from another agent and acts on it: the entry point on the receiving side of a delegation. |

### Control steps
*(typical BEAM type: `beam:Transform` / `beam:Process`; sub-roles of `ControlStep`)*

| Role | Definition |
| --- | --- |
| `ControlStep` | A step implementing a risk control / mitigation (screening, validation, rate limiting). Top-level role. |
| `GuardrailStep` | A guardrail step that screens input or output. |
| `InputGuardrailStep` | Screens user input before generation. |
| `OutputGuardrailStep` | Screens model output before release. |
| `OutputValidationStep` | Validates/encodes/sanitizes model output before downstream use. |
| `RateLimitControlStep` | Enforces rate/budget/quota/loop bounds. |
| `RedactionStep` | Removes, masks, tokenizes, or minimizes protected content before passing it on. **The barrier for content-category propagation**: elements downstream of it do not inherit the upstream category. |
| `MemoryValidationStep` | Screens, attributes, or scores content before it is committed to agent memory, so what is retained is not simply whatever was produced. Its absence is what ASI06 checks. |
| `PolicyEnforcementStep` | Evaluates a proposed action against a policy before it is carried out, and can narrow or refuse it — deterministic mediation between a model's decision and its effect, not an instruction asking the model to behave. |
| `HumanApprovalStep` | A person must confirm an action before it proceeds (human in the loop). |

---

## 4. Data categories (7)

Assign with `pair:containsDataCategory` on a `beam:Data` element. This is the one
facet that is also **derived**: categories propagate along `beam:use` →
`beam:produce` to a fixed point, so you tag where protected or untrusted content
*enters* and the queries work out where it can reach.

| Category | Definition |
| --- | --- |
| `Information` | Root category for content-kind classification. |
| `SensitiveInformation` | Content whose exposure can harm people/orgs (personal, medical, financial). Read by sensitive-data conditions (LLM02). |
| `ConfidentialInformation` | Secrets for operational/business reasons (credentials, keys, config). *Not* a sub-category of Sensitive. |
| `PromptInstruction` | Instructional content steering behavior (system prompts, templates, config). Read by system-prompt-leakage / embeddings conditions. |
| `UntrustedContent` | Content whose integrity the graph can't vouch for (public input, external docs, retrieved context). Read by prompt-injection / poisoning / goal-hijack; **auto-derived** by the taint rule, which now also marks the *roots* themselves. Absence means *unknown*, not trusted. |
| `ExternalUserContent` | Content from a user outside the boundary. *Not* a sub-category of Untrusted (taint is derived, not implied). |
| `GeneratedContent` | Content produced by a generative model rather than authored/retrieved. **Auto-derived** from any `GenerationStep`'s output. |

> **`TrustedContent` was removed (2026-08-06.)** It existed as an explicit
> override clearing taint that would otherwise propagate, but asserting that
> content *is* trusted is a claim about the world the submitted graph cannot
> support. Taint is now cleared only by a represented `GuardrailStep` — a claim
> about structure, which stays graph-relative and candidate-framed under R4.

**Propagation rules** (`ontology/patterns/implementation/propagation/`, four
rules, re-run to a fixed point):

- `content_categories.rq` — everything under `Information` flows along
  `beam:use` → `beam:produce`. A `RedactionStep` **stops the protected-content
  categories** (Sensitive, Confidential, ExternalUserContent, PromptInstruction)
  but not origin markers: redacting model output does not make it un-generated.
- `untrusted_content.rq` — taint from the `PublicUserInput` and `RetrievedContext`
  roots, cleared only by a `GuardrailStep`. The roots now carry the marker
  **themselves**, not just what they flow into — until 2026-08-06 they did not,
  so a condition reading a step's own input silently missed the direct case.
- `generated_content.rq` — a `GenerationStep`'s output is `GeneratedContent`.
  Definitional rather than interpretive, so it is derived, not annotated (R8).
- `personal_data_rights.rq` — bridges the data-rights facet `dataf:Personal` to
  `SensitiveInformation`, so tagging the source is enough. Both concepts point at
  DPV independently, which is what corroborates the bridge.

Sensitive content annotated on an input **does** reach the output: it propagates
transitively along the flow, so you tag where protected content *enters* and the
rules work out where it can reach.

**There is no `Personal` data category, deliberately.** Personal data is expressed
with DPV concepts through `facet:hasPersonalDataCategory` and
`facet:hasIdentifiabilityLevel`, never mirrored into this scheme (glossary R3).

## 5. Annotation guidance (SHACL)

`shacl/annotation_guidance.ttl` is a third shapes file beside the two contracts.
It asks the question neither contract asks: **will this annotation actually match
anything?** A graph can satisfy the input contract completely and still produce
zero findings because a role sits on the wrong kind of element, or a store
nothing retrieves from — and silence reads as safety.

Every shape is `sh:Info` or `sh:Warning`, **never** `sh:Violation`, so it cannot
change whether a graph conforms. It runs alongside the input contract in the
workbench and in `validate_graphs.py`. What it catches:

| Shape | Catches |
| --- | --- |
| `StepRoleNeedsAProcessTypeShape` | A step role on an element with no process-family class — no query can bind it. |
| `ResourceRoleOnProcessShape` | A resource role on a `beam:Process`. |
| `VectorStoreIsRetrievedFromShape` | A vector store no retrieval step uses. |
| `GenerationStepUsesAModelShape` | A generation step binding no `GenerativeModel`. |
| `AgentMemoryIsALoopShape` | Agent memory only written or only read — ASI06 needs the loop. |
| `AgentMessageIsReceivedShape` | An inter-agent message no `AgentHandoffStep` consumes. |
| `DataCarriesARoleShape` | A `beam:Data` element with no role at all. |
| `UserFacingOutputIsProducedShape` | A sink no step produces. |
| `KnowledgeSourceDeclaresContentShape` | A knowledge source with no data category — an annotated base fact (R8) nothing can supply for you. |

## See also

- [../user_guide.md](../user_guide.md) — running the workbench
- [PAIR-AI_glossary_v1_3.md](PAIR-AI_glossary_v1_3.md) — terminology and modeling rules (R1–R10)
- [PAIR-AI_method_and_construction.md](PAIR-AI_method_and_construction.md) — how the library was built
- [risk_control_linkage.md](risk_control_linkage.md) — risk → control linkage, including the MIT evidence layer
- [../../ontology/example/](../../ontology/example/) — worked annotation examples and the unannotated control graph
