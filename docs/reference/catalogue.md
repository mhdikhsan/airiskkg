# PAIR-AI Catalogue — Motifs, Risk Patterns & Annotation Roles

The complete inventory of what PAIR-AI can recognise and flag: every **motif**
(24), every **risk pattern** (11), every **annotation role** (85), and the
**data categories** (8). Generated from the loaded ontology, so it reflects the
current library.

## How the three fit together

- **Roles** annotate elements. You put a `pair:playsRole` on a single BEAM
  element (a box) — one element may carry several roles.
- **Motifs** are the *linter rules*. A motif is a graph pattern over **a
  combination of role-tagged elements plus their flow edges** (`beam:use` /
  `beam:produce` / `beam:inform`). Matching finds the combination.
- **Risk patterns** are the *warnings*. When a motif match also satisfies a
  risk pattern's applicability conditions (a data category, the absence of a
  control, a tool edge…), PAIR-AI emits a **candidate** risk finding.

> **Per-element or combination?** Annotation is **per-element** — you tag each
> box on its own. Recognition is **per-combination** — a motif only matches when
> several correctly-tagged elements are wired together in the expected shape. So
> one box's role is meaningless in isolation; it becomes a finding only in
> concert with the others (e.g. `GenerationStep` + `GenerativeModel` +
> `UserFacingOutput` + a `beam:use`/`beam:produce` wiring = a Direct-Prompting
> match). You never annotate "a combination"; you annotate the parts and let the
> motif capture the combination.

---

## 1. Motifs (24)

Motifs are risk-neutral: they describe *structure*, not danger. The **Feeds**
column lists the risk patterns a match can trigger (see §2). Two motifs are
**controls** — their presence *suppresses* findings rather than raising them.

### Gen AI — generation & retrieval

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **DirectPromptingMotif** | A user query handled directly by a generative-model step, producing a user-facing answer. | LLM09 (no grounding), LLM05, LLM07, LLM10, LLM06 |
| **RetrievalAugmentedGenerationMotif** | User query → query-driven retrieval of context from a vector store → build prompt → LLM → answer (also matches Vector-based IR). | LLM09 (misinformation), LLM08, LLM01, LLM10 |
| **VectorBasedInformationRetrievalMotif** | A retrieval step uses a vector store / knowledge source and produces retrieved context (the retrieval stage on its own). | LLM02, LLM01, LLM08 |
| **EmbeddingsMotif** | Source documents/data chunked and transformed into vectors stored in a vector index. | LLM08, LLM04 |
| **QueryRewritingMotif** | An LLM reformulates a user query into alternative queries used for retrieval. | LLM10 |
| **RerankerMotif** | A candidate set of retrieved fragments is reranked by a model to select context. | LLM08 |
| **HybridRetrieverMotif** | Vector search and keyword/structured search combined and aggregated into a candidate context set. | LLM08 |

### Gen AI — controls & evaluation *(presence suppresses findings)*

| Motif | Recognises | Effect |
| --- | --- | --- |
| **GuardrailsMotif** | Input/output guardrail steps screen or sanitize prompts and responses around the LLM. | Suppresses LLM01 / LLM05 on the guarded path. |
| **EvalsMotif** | Model input, output, expected output, and optional context are scored/judged into evaluation results. | Suppresses LLM09 (grounding present). |

### Gen AI — adaptation

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **FineTuningMotif** | A pre-trained LLM further trained on a task/domain dataset to produce a fine-tuned model. | LLM04, LLM03 |

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
| **TrainingToServingMotif** | A training pipeline automatically produces an artifact built/deployed into serving. | LLM04 |

### Operational

| Motif | Recognises |
| --- | --- |
| **ModelLoadMotif** | Server image and model artifact managed separately; model loaded before prediction. |
| **ModelInImageMotif** | A trained artifact packaged into a serving image deployed as the runtime. |
| **PredictionLoggingMotif** | Prediction inputs/results/latency collected into logs. |
| **PredictionMonitoringMotif** | Logs/result trends monitored against expected behavior; may raise alerts. |

### Supply chain

| Motif | Recognises | Feeds |
| --- | --- | --- |
| **ExternalDependencyMotif** | An external dependency, pre-trained model, artifact, or serving image is used by a step. Risk-neutral by itself. | LLM03 |

---

## 2. Risk patterns (11)

Each risk pattern interprets a motif match. **Fires when** is the verified
trigger; **Motif** is what must match first; **Suggested controls** are the
mitigations attached to the finding.

| OWASP | Risk pattern | Fires when | Motif | Suggested controls |
| --- | --- | --- | --- | --- |
| **LLM01** | Prompt injection | Untrusted content (from retrieval/tools, tainted by public input) reaches generation → user output, with no input/output control. | any binding the untrusted element (Vector-IR, RAG) | Input/output filtering; input validation & prompt isolation; logging/monitoring/evals |
| **LLM02** | Sensitive data retrieval exposure | The store **and** the retrieved result carry `SensitiveInformation` → generation → user output, no disclosure control. | Vector-IR | Data minimization & redaction; input/output filtering; output validation; retrieval access control |
| **LLM03** | Supply chain compromise | An external model / data / dependency / artifact is used, with no control on it. | External Dependency | Model & dependency provenance; logging/monitoring/evals |
| **LLM04** | Data & model poisoning | A bound source tagged `UntrustedContent` enters embeddings / fine-tuning / training-to-serving. | Embeddings / FineTuning / TrainingToServing | Trusted training & indexing data; model & dependency provenance; logging/monitoring/evals |
| **LLM05** | Improper output handling | Generation → user output with no `OutputValidationStep` / `OutputGuardrailStep`. | any binding the gen step | Output validation & sanitization; input/output filtering |
| **LLM06** | Excessive agency | The generation step `inform`s a `ToolInvocationStep` / `StateChangingStep`, no control on it. | any binding the gen step | Tool permission boundaries; rate/budget/loop control; logging/monitoring/evals |
| **LLM07** | System prompt leakage | A `SystemPrompt` feeds generation → user output, no control. | any binding sysprompt / gen / output | System prompt secrecy; input/output filtering; output validation |
| **LLM08** | Vector & embedding weakness | Any vector-retrieval / embedding / reranker motif matches. | Vector-IR / RAG / Embeddings / Reranker | Trusted training & indexing data; retrieval access control; grounding & verification |
| **LLM09** | Misinformation (weak grounding) | A RAG generation reaches a response with no `EvaluationStep` / `ScoringStep`. | RAG | Grounding & verification; logging/monitoring/evals |
| **LLM09** | Direct prompting without grounding | A Direct-Prompting generation with no `KnowledgeSource` / `RetrievedContext` grounding. | Direct Prompting | Grounding & verification; logging/monitoring/evals |
| **LLM10** | Unbounded consumption | An LLM/retrieval loop or generation with no `RateLimitControlStep`. | Direct Prompting / RAG / Query Rewriting | Rate/budget/loop control; logging/monitoring/evals |

*All findings are **candidate** risks — structural dispositions, not confirmed
failures. Missing findings usually mean a missing role, not a safe system.*

---

## 3. Annotation roles (85)

Assign with `pair:playsRole`. Roles are organised into sub-role hierarchies
(shown by the groups below); a motif that asks for a parent role also matches its
sub-roles (`pair:subRoleOf*`).

### User I/O
*(typical BEAM type: `beam:Data`)*

| Role | Definition |
| --- | --- |
| `UserInput` | Information provided directly by a user (UI or API input). |
| `PublicUserInput` | Input from an open/public population (anonymous or self-registered). **Treated as untrusted** by taint propagation. |
| `UserFacingOutput` | Data exposed to a user or downstream consumer (a sink). |
| `PublicUserFacingOutput` | User-facing output exposed to the public (e.g. a chatbot response). |

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
| `RetrievedContext` | Content returned by a retrieval step for use as context. |
| `RetrievedResult` | A result item returned by a retrieval step (a `RetrievedContext`). |
| `RetrievedCandidateSet` | A set of retrieved candidate fragments prior to reranking. |
| `RerankedContext` | Reranked, selected context fragments for generation. |
| `SourceDocument` | A source document ingested into a knowledge base. |
| `DocumentChunk` | A chunk of a source document used for embedding/retrieval. |
| `EmbeddingVector` | A stored embedding vector. |

### Prompts & generation resources
*(typical BEAM type: `beam:Data`)*

| Role | Definition |
| --- | --- |
| `PromptTemplate` | A prompt template combining instructions and inputs. |
| `SystemPrompt` | A hidden system prompt / instruction template, not authored by the end user. |
| `LLMResponse` | A response from a generative model, prior to output screening. |
| `RewrittenQuery` | A reformulated query produced by a query-rewriting step. |
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
| `ProcessingStep` | A workflow step (Boxology process box). |
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

### Control steps
*(typical BEAM type: `beam:Transform` / `beam:Process`; sub-roles of `ControlStep`)*

| Role | Definition |
| --- | --- |
| `ControlStep` | A step implementing a risk control / mitigation (screening, validation, rate limiting). |
| `GuardrailStep` | A guardrail step that screens input or output. |
| `InputGuardrailStep` | Screens user input before generation. |
| `OutputGuardrailStep` | Screens model output before release. |
| `OutputValidationStep` | Validates/encodes/sanitizes model output before downstream use. |
| `RateLimitControlStep` | Enforces rate/budget/quota/loop bounds. |

---

## 4. Data categories (8)

Assign with `pair:containsDataCategory` on a `beam:Data` element. Only a few
conditions read them; most are auto-derived along data flow.

| Category | Definition |
| --- | --- |
| `Information` | Root category for content-kind classification. |
| `SensitiveInformation` | Content whose exposure can harm people/orgs (personal, medical, financial). Read by sensitive-data conditions (LLM02). |
| `ConfidentialInformation` | Secrets for operational/business reasons (credentials, keys, config). *Not* a sub-category of Sensitive. |
| `PromptInstruction` | Instructional content steering behavior (system prompts, templates, config). Read by system-prompt-leakage / embeddings conditions. |
| `UntrustedContent` | Content whose integrity the graph can't vouch for (public input, external docs, retrieved context). Read by prompt-injection / poisoning; **also auto-derived** by the taint propagation query. Absence means *unknown*, not trusted. |
| `TrustedContent` | Explicit override clearing untrusted taint that would otherwise propagate. |
| `ExternalUserContent` | Content from a user outside the boundary. *Not* a sub-category of Untrusted (taint is derived, not implied). |
| `GeneratedContent` | Content produced by a generative model rather than authored/retrieved. |

## See also

- [../annotation_facilitator_cheatsheet.md](../annotation_facilitator_cheatsheet.md) — recipes per common Gen AI system + steering script
- [../annotation_walkthrough_graphrag.md](../annotation_walkthrough_graphrag.md) — a full worked annotation example
- [../user_guide.md](../user_guide.md) — running the workbench
- [PAIR-AI_glossary_v1.2.md](PAIR-AI_glossary_v1.2.md) — terminology and modeling rules
