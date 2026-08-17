# PAIR-AI Workbench — User Guide

A hands-on guide to the PAIR-AI Architecture Workbench: what it is, how to use
it, a complete reference of the motifs, risk patterns, and roles it knows, and a
worked example of annotating an architecture graph so the assessment can match
it.

> This is a living document — edit freely. Screenshots are intentionally left
> out so it stays easy to update as the UI evolves.

---

## 1. What this application is

**PAIR-AI is design-time risk assessment for AI systems.** Instead of running the
system, you describe its architecture as a graph and PAIR-AI tells you which
risks the *structure* predisposes it to. It works with two core concepts.

### Motif

A **motif** is a reusable architectural pattern — a small graph of *pattern
roles* wired together by data-flow relations. For example: *"a retrieval step
that uses a vector store and produces retrieved context"*, or *"a user query
handled directly by a generative model that produces user-facing output"*.

Motifs match **structure only** — the roles elements play and the flow between
them. A motif matching your graph is **risk-neutral**: it just means your system
has that shape. Motifs are the recurring building blocks the method recognises;
the current library has 24 of them (see the [Reference](#4-reference)).

### Candidate risk finding

When a motif match *also* satisfies the **applicability conditions** of a **risk
pattern** — the right context, data categories, or the *absence* of a control —
PAIR-AI emits a **candidate risk finding**. Each finding carries:

- the **risk mechanism** (why the structure enables the risk),
- the **evidence** elements from your graph,
- **taxonomy** links (IBM AI Risk Atlas / OWASP LLM Top 10 / MIT AI Risk
  Repository), and
- **suggested controls**.

**Every output is a *candidate* risk — a structural disposition, never a
confirmed failure.** A finding means *"this shape is known to enable this risk
unless something outside the graph prevents it."* It is a prompt for review, not
a verdict. (Formally: PAIR-AI reasons under the Open World Assumption; a "no
control found" check is closed-world over *the graph you submitted only*.)

### How it works, end to end

1. **You describe the architecture** as a graph of BEAM elements —
   *resources* (`beam:Data`, `beam:StatisticalModel`, `beam:SemanticModel`,
   `beam:Symbol`) and *processes* (`beam:Transform`, `beam:Infer`, `beam:Train`,
   `beam:Generate`, `beam:Process`) wired together with flow edges (`beam:use`,
   `beam:produce`, `beam:inform`).
2. **You annotate** each element with **one or more roles** (e.g. `FoundationLLM`,
   `RetrievedContext`, `GuardrailStep`) and, where relevant, **data categories**.
   Structure alone says *what shape* the system is; roles say *what each part
   means*. An element can play several roles at once — e.g. a store that is both a
   `VectorStore` and a `VectorIndex`.
3. **Motifs match the structure** — the roles and flow.
4. **Risk patterns interpret the matches** and emit candidate risk findings when
   their applicability conditions hold.

---

## 2. Using the application

The workbench is deployed as a web app — just open the URL your team provides in
a browser. Nothing is written to disk from the UI: every assessment runs
in-memory and returns JSON.

### 2.1 The layout

The workbench is a single page with three regions:

```text
┌───────────────────────── header toolbar ─────────────────────────┐
│  Load example ▾  Open .ttl  Starter  Clear │ Validate  Run assess │
├───────────────────────────┬───────────────────────────────────────┤
│                           │                                       │
│   LEFT: Turtle editor     │   RIGHT: live diagram (canvas)        │
│   (edit the code)         │   drag · connect · click-to-edit      │
│                           │   Symbols palette + Motifs catalogue  │
│                           ├───────────────────────────────────────┤
│                           │   bottom drawer:                      │
│                           │  Findings·Motifs·Annotate·Contract    │
└───────────────────────────┴───────────────────────────────────────┘
```

The editor (left) and the diagram (right) are **two views of the same graph and
stay in sync both ways**:

- Type Turtle on the left → the diagram redraws.
- Edit on the right (drag, add, connect, rename, delete) → the Turtle updates.

### 2.2 Header toolbar

| Button | What it does |
| --- | --- |
| **Load example ▾** | Load an architecture graph. Under **Bundled**: `onyx_rag_chatbot` (a fully-annotated RAG assistant) and `simple_graph_rag` (a small graph-RAG). Under **Local**: anything you dropped in `ontology/example_local/` — see [Your own graphs](#26-your-own-graphs). |
| **Open .ttl** | Upload your own Turtle file. |
| **Starter** | Replace the editor with a minimal starter graph to build from. |
| **Clear** | Empty both the code and the diagram (asks to confirm). |
| **Validate** | Check the graph against the SHACL *input contract* — reports in the **Input contract** drawer tab. |
| **Run assessment** | Run the full motif-matching + risk-interpretation pipeline; results land in the **Findings** and **Motifs** tabs. |

### 2.6 Your own graphs

`ontology/example_local/` is yours. Drop any `.ttl` in it and the workbench
offers it in **Load example ▾** under a **Local** heading, so you can always
tell your graphs from the two the project ships.

Nothing there can be published by accident:

| | |
| --- | --- |
| **git** | Every file in the folder is gitignored, so `git add .` cannot stage one. Only the folder's `README.md` is tracked. |
| **Docker image** | `.dockerignore` is an allow-list, and it excludes the folder explicitly. A built image contains the two bundled graphs and nothing else. |
| **Deployed server** | A WSGI server (gunicorn, the Docker image) never lists or serves the folder, whatever is on its disk. Only `cli serve` offers it, because that is by definition a local run — pass `--no-local-examples` to turn it off there too. |

`python/tests/test_private_examples.py` enforces all four of those, so a change
that would start leaking fails the suite rather than a review.

### 2.3 Editing the diagram (right pane)

The canvas carries **two collapsible trays** on the right — click a tray's header
(**▸ / ▾**) to show or hide it:

- **Symbols** — the BEAM element palette (shown by default).
- **Motifs** — the motif catalogue (starts collapsed); see
  [§2.5](#25-building-from-the-motif-catalogue).

- **Add an element** — drag a symbol from the **Symbols** tray onto the canvas, or
  click a symbol to drop it in the centre. The element types are the four BEAM
  resources — **Data**, **Statistical Model**, **Semantic Model**, **Symbol** —
  and the process types **Transform**, **Infer**, **Train**, **Generate**,
  **Process**.
- **Move** — drag a node.
- **Connect** — drag from a node's **▸ port** onto another node. The edge kind is
  inferred from the endpoints. **Hover any edge** for a tooltip that explains it:
  - **uses** (process → resource) — the process reads this resource as input.
  - **produces** (process → resource) — the process writes this resource as output.
  - **informs** (process → process) — one step hands off to the next.
- **Edit / delete** — click a node to open its detail popup. There you can change
  its **Label**, **Name** (renames the URI), **Type** (BEAM class), its **Roles**,
  and its **Data categories**, then **Apply**; or **Delete** it. **Roles** and
  **Data categories** are multi-value pickers — current values show as removable
  chips with a **+ add** dropdown, so an element can carry **several roles** at
  once. The **Delete** / **Backspace** key deletes the selected node too (except
  while you're typing in a field).
- **Zoom / fit** — the `+`, `−`, and fit (`⬒`) controls sit at the corner of the
  canvas.

### 2.4 Reading the results

**Run assessment** fills two drawer tabs at once — **Findings** and **Motifs**.

**Findings** lists each candidate risk finding. Selecting a finding highlights its
**evidence** elements in the diagram (click it again to clear). Each finding shows:

- the **risk mechanism** (why the structure enables it),
- **taxonomy** chips (IBM Atlas / OWASP / MIT), and
- an expandable **Suggested controls · evidence** section with the suggested
  mitigations and the evidence elements.

Some mitigations carry a **"suggested mitigation:"** motif chip. Those chips are
**clickable** — clicking one drops that motif's (already-annotated) elements onto
the canvas so you can scaffold the missing control and re-assess (see §2.5).

**Motifs** lists the motifs that matched your graph. Repeated matches of the same
motif collapse into one row with a **×N** count — so a graph with seven external
dependencies shows a single *External Dependency ×7* row, not seven. Click a row
to highlight all of that motif's elements; click again to clear. A motif matching
is **risk-neutral** — it only becomes a finding when a risk pattern's
applicability condition also holds.

Remember: findings are candidates. An empty result doesn't mean "safe" — it means
no motif matched, often a signal that the graph still needs **roles** (see §3).

### 2.5 Building from the motif catalogue

The **Motifs** tray (right of the canvas) lists all 24 motifs. Click a motif — or
drag it onto the canvas — to instantiate it: the workbench adds that motif's
elements **already wired and annotated** with the roles it expects, and the editor
Turtle updates to match. Then **Run assessment** to see what the new shape
produces.

This is the fastest way to scaffold a system from recognised building blocks, or
to add a control a finding suggested — the clickable mitigation chips in the
Findings tab use exactly this mechanism.

---

## 3. Annotation guide (worked example)

**Why annotation matters:** motifs match on *roles*, not on BEAM types alone. A
graph that has the right shape but no roles will produce **zero findings**. This
is exactly the situation for graphs imported from Tool4Boxology / the private
*t4b-beam* tool: they carry structure (types + flow edges) but **no pattern
roles**. Annotation is the step that makes such a graph assessable.

We'll use the bundled **`beam_export_graph_rag.ttl`** example — a real t4b-beam
export of a GraphRAG event-information chatbot.

> **The finished result of this walkthrough** — the same graph with every role
> and facet filled in — is bundled as
> **`ontology/example/beam_export_graph_rag_annotated.ttl`**, so you can compare
> your annotation against it.

### Step 1 — Load it and look

Toolbar → **Load example ▾ → beam_export_graph_rag**.

You'll see a BEAM-native RAG pipeline: `beam:System`, `beam:Data` /
`beam:StatisticalModel` / `beam:SemanticModel` / `beam:Symbol` resources, and
`beam:Infer` / `beam:Transform` / `beam:Generate` processes, wired with
`beam:use` / `beam:produce`. Structurally sound — but if you **Run assessment**
now you get **nothing**, because **no element has a role**.

### Step 2 — Open the Annotate tab

Bottom drawer → **Annotate**. Every element is listed with a **Roles** picker and
a **Data categories** picker — both multi-value: pick as many as apply and each
shows up as a removable chip. The count badge on the tab shows how many elements
are still untagged. Selecting a row highlights that element in the diagram, so you
can see what you're tagging. (You can also tag an element straight from its popup
on the canvas — click the node and use the same **Roles** / **Data categories**
pickers there.)

### Step 3 — Assign roles

Pick one or more roles per element from the vocabulary — some elements genuinely
play several (e.g. a store that is both `VectorStore` and `VectorIndex`, or an LLM
that is both `FoundationLLM` and `GenerativeModel`). Roles fall into three
families — **resource / data roles**, **process-step roles**, and **control
roles**. The
complete vocabulary (all 85 roles, with definitions) is in
[§4.3 Roles](#43-roles-full-vocabulary). The handful you'll reach for most on a
RAG / LLM graph:

| Need | Roles |
| --- | --- |
| User-facing I/O | `UserInput`, `PublicUserInput`, `UserFacingOutput`, `PublicUserFacingOutput` |
| Knowledge / retrieval | `KnowledgeSource`, `VectorStore`, `RetrievedContext`, `RetrievedResult`, `SourceDocument` |
| Models | `FoundationLLM`, `GenerativeModel`, `EmbeddingModel`, `JudgeModel` |
| Steps | `RetrievalStep`, `PromptConstructionStep`, `GenerationStep`, `EmbeddingStep` |
| Controls | `GuardrailStep`, `InputGuardrailStep`, `OutputGuardrailStep`, `OutputValidationStep`, `RateLimitControlStep` |

For this GraphRAG export the reachable findings are **prompt injection** (LLM01),
**sensitive information disclosure** (LLM02), and **vector & embedding weakness**
(LLM08) — all via the retrieval motif. Assign, at minimum: the question →
`PublicUserInput`; the Event ID → `UserInput`; the retrieval step →
`RetrievalStep`; the Event KG → `VectorStore` + data category `Sensitive
Information`; the retrieved subgraph → `RetrievedResult` + `Sensitive
Information`; the LLM → `GenerativeModel`; the generation step → `GenerationStep`;
the summary → `UserFacingOutput`. (Full table with the "why" for each row is in
the dedicated walkthrough.)

### Step 4 — Apply

Click **Apply annotations**. This writes `pair:playsRole` (and
`pair:containsDataCategory` where set) triples into the editor graph. You'll see
the Turtle on the left grow the new triples, e.g.:

```turtle
<…/Component/kg_subgraph>
    a beam:Data ;
    rdfs:label "Event KG Subgraph on Event ID" ;
    pair:playsRole pair:RetrievedResult ;
    pair:containsDataCategory pair:SensitiveInformation .
```

Re-applying is idempotent — it replaces an element's existing roles with exactly
what's selected, so you can iterate freely.

### Step 5 — Assess again

Click **Run assessment**. With roles in place the retrieval motif matches and the
**Findings** tab shows **3 candidate findings** (prompt injection, sensitive data
retrieval, vector & embedding weakness), each with evidence, taxonomy links, and
suggested mitigations. Select a finding to highlight its evidence in the diagram.

### Annotating by hand (alternative)

You don't have to use the drawer — roles are just triples. In the editor you can
write them directly:

```turtle
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .

ex:MyLLM        a beam:StatisticalModel ; pair:playsRole pair:FoundationLLM .
ex:GenerateStep a beam:Generate ;         pair:playsRole pair:GenerationStep .
ex:Context      a beam:Data ;             pair:playsRole pair:RetrievedContext ;
                                          pair:containsDataCategory ex:UntrustedContent .
```

The diagram and the Annotate tab pick these up immediately.

---

## 4. Reference

The complete vocabulary the assessment knows: every motif, every risk pattern,
and every role. This is what the workbench matches against.

### 4.1 Motifs (24)

Motifs are risk-neutral architectural patterns. Ones marked **→ risk** currently
feed one or more risk patterns (see §4.2); the rest are detected for completeness
and workbench reporting.

#### GenAI / LLM motifs

| Motif | What it captures | |
| --- | --- | --- |
| Direct Prompting | A user query is handled directly by a generative model that produces user-facing output, with no retrieval or grounding step. | → risk |
| Retrieval Augmented Generation (RAG) | A user query **drives** retrieval of relevant context from a **vector store**, which is combined with the query into a prompt and sent to an LLM to produce an answer. Because retrieval is query-driven over a vector store, a RAG graph also matches **Vector-based Information Retrieval**. | → risk |
| Vector-based Information Retrieval | A retrieval process uses a vector store / knowledge source and produces a retrieved result or context (the retrieval stage of RAG, factored out on its own). | → risk |
| Embeddings | Source documents or data blocks are chunked and transformed into vectors stored in a vector index. | → risk |
| Hybrid Retriever | Vector search and keyword / structured search are combined and aggregated to produce a candidate context set. | |
| Query Rewriting | An LLM reformulates a user query into alternative queries that are then used for retrieval. | → risk |
| Reranker | A candidate set of retrieved fragments is reranked by a model so the most useful context is passed on for generation. | → risk |
| Guardrails | Input and output guardrail steps screen or sanitize user prompts and generated responses around the primary LLM generation step. | → risk |
| Fine Tuning | A pre-trained LLM is further trained with a task- or domain-specific dataset to produce a fine-tuned model. | → risk |
| Evals | Model input, generated output, expected output, and optional retrieval context are scored or judged to produce evaluation results. | |

#### Supply-chain & serving-image motifs

| Motif | What it captures | |
| --- | --- | --- |
| External Dependency | A supply-chain-relevant resource (external dependency, pre-trained model, model artifact, or serving image) is used by a process step. | → risk |
| Model Load | A prediction-server image and model artifact are managed separately, and the model is loaded by the server before prediction. | → risk |
| Model-in-Image | A trained model artifact is packaged into a serving image that is deployed as the prediction service runtime. | → risk |

#### ML serving motifs

| Motif | What it captures |
| --- | --- |
| Synchronous Prediction | A prediction step runs inline with a request workflow and produces a result before the workflow proceeds. |
| Asynchronous Prediction | Prediction requests are decoupled from execution through a queue, cache, or similar intermediary. |
| Batch Prediction | A scheduled job runs prediction over a batch dataset and stores batch results. |
| Prep-Pred / Preprocess-Prediction | Preprocessing and prediction are represented as separate steps connected by preprocessed data. |
| Multi-stage Prediction | One prediction path returns a quick result while another produces a slower or richer result. |

#### ML training, lifecycle & operations motifs

| Motif | What it captures | |
| --- | --- | --- |
| Batch Training | A scheduled training job prepares data, trains a model, evaluates it, and records the artifact and evaluation result. | |
| Pipeline Training | Training is decomposed into independently executable pipeline jobs connected by intermediate data and workflow dependencies. | |
| Train-Then-Serve | Training and serving are separated by evaluation, approval, and a release step before the model is used for production prediction. | |
| Training-to-Serving | A training pipeline automatically produces a model artifact that is built or deployed into a serving prediction path. | → risk |
| Prediction Logging | Prediction inputs, results, latency, or related events are collected into prediction logs. | |
| Prediction Monitoring | Prediction logs or result trends are monitored against expected behavior and may produce alerts. | |

### 4.2 Risk patterns (11)

Each risk pattern anchors to an OWASP LLM Top 10 (2025) entry and fires only when
a motif match *also* satisfies its applicability condition.

| Risk pattern | OWASP anchor | Fires when… | On motifs |
| --- | --- | --- | --- |
| Prompt injection | LLM01 | Untrusted user, retrieved, or tool-supplied content can enter a prompt or generation context. | Direct Prompting, RAG, Query Rewriting |
| Sensitive data retrieval exposure | LLM02 | Vector-store retrieval carrying sensitive information reaches generation and can surface in user-facing output. | Vector-based Information Retrieval |
| Supply chain compromise | LLM03 | An external model, data, dependency, provider, or artifact is used. | External Dependency, Fine Tuning, Model Load, Model-in-Image, Training-to-Serving |
| Data and model poisoning | LLM04 | Untrusted data enters training, fine-tuning, evaluation, or indexing. | Embeddings, Fine Tuning, Training-to-Serving |
| Improper output handling | LLM05 | Generated output reaches a user or downstream component without a represented validation, sanitization, or guardrail step. | Direct Prompting, Guardrails |
| Excessive agency | LLM06 | The LLM can trigger tools, permissions, transactions, or state changes (a generation step informing a tool-invocation / state-changing step). | Role-anchored (any match) |
| System prompt leakage | LLM07 | Hidden instructions or system configuration in the prompt context can be exposed through output. | Guardrails |
| Vector and embedding weakness | LLM08 | Vector retrieval or an embedding index feeds the generation context. | RAG, Embeddings, Reranker |
| Direct Prompting without grounding | LLM09 | A Direct Prompting motif produces a user-facing answer with no knowledge source, retrieved context, or verification step. | Direct Prompting |
| Misinformation from weak grounding | LLM09 | A RAG pipeline's retrieved context reaches generation without a represented verification / evaluation / scoring step. | RAG |
| Unbounded consumption | LLM10 | Model calls, retrieval breadth, prompt expansion, tool use, or loops are not bounded by represented rate / budget / loop controls. | Direct Prompting, RAG, Query Rewriting |

Each risk pattern also carries suggested controls drawn from PAIR-AI's
12-entry control catalogue (input validation & prompt isolation, output
validation & sanitization, data minimization & redaction, retrieval access
control, model & dependency provenance, trusted training & indexing data, tool
permission boundaries, system-prompt secrecy, grounding & verification, rate /
budget / loop control, logging / monitoring / evals, and input & output
filtering).

### 4.3 Roles (full vocabulary)

The 85 pattern roles you assign to elements, grouped by family. Assign the most
specific role that fits.

#### Top-level role abstractions

| Role | Meaning |
| --- | --- |
| `ProcessingStep` | Any workflow step (preprocessing, training, inference, post-processing). |
| `ControlStep` | A step implementing a risk control (screening, validation, rate limiting). |
| `ResourceRole` | Any non-process resource: data, models, stores, or artifacts. |

#### User-facing I/O

| Role | Meaning |
| --- | --- |
| `UserInput` | Information provided directly by a user (UI or API input). |
| `PublicUserInput` | User input from an open / public population — treated as untrusted by taint propagation. |
| `UserFacingOutput` | Data exposed to a user or downstream consumer (a sink). |
| `PublicUserFacingOutput` | User-facing output exposed to the public (e.g. a chatbot response). |

#### Knowledge & retrieval resources

| Role | Meaning |
| --- | --- |
| `KnowledgeSource` | A source of information an AI system can access (DB, knowledge graph, external API). |
| `VectorStore` | A vector database serving as a retrieval knowledge source. |
| `VectorIndex` | An index over embedding vectors. |
| `KeywordIndex` | A keyword / text index used for lexical search. |
| `SourceDocument` | A source document ingested into a knowledge base. |
| `DocumentChunk` | A chunk of a source document used for embedding / retrieval. |
| `EmbeddingVector` | A stored embedding vector. |

#### Retrieval outputs & context

| Role | Meaning |
| --- | --- |
| `RetrievedContext` | Content returned by a retrieval step for use as context. |
| `RetrievedResult` | A result item returned by a retrieval step, used as retrieved context. |
| `RetrievedCandidateSet` | A set of retrieved candidate fragments prior to reranking. |
| `RerankedContext` | Reranked, selected context fragments for generation. |
| `RewrittenQuery` | A reformulated query produced by a query-rewriting step. |

#### Models

| Role | Meaning |
| --- | --- |
| `Model` | A machine-learning or statistical model resource. |
| `GenerativeModel` | A model that generates content (e.g. an LLM) at inference time. |
| `PretrainedModel` | A pre-trained model obtained before / without task-specific adaptation. |
| `FoundationLLM` | A foundation large language model used directly for generation. |
| `FineTunedModel` | A model produced by fine-tuning a pre-trained model on task-specific data. |
| `EmbeddingModel` | A model that transforms data into vector embeddings. |
| `JudgeModel` | A model used to score / evaluate another model's output (LLM-as-judge). |
| `RerankerModel` | A model (typically a cross-encoder) that scores candidate relevance for reranking. |
| `LoadedModel` | A model instance loaded into a serving runtime. |
| `ModelArtifact` | A persisted model artifact (weights / checkpoint). |

#### Prompts

| Role | Meaning |
| --- | --- |
| `PromptTemplate` | A prompt template combining instructions and inputs. |
| `SystemPrompt` | A hidden system prompt / instruction template steering model behavior, not authored by the end user. |

#### Generation & guardrail outputs

| Role | Meaning |
| --- | --- |
| `LLMResponse` | A response produced by a generative model prior to output screening. |
| `GuardrailDecision` | A decision (allow / block) produced by a guardrail step. |
| `SanitizedOutput` | Output that has passed an output guardrail / sanitization step. |

#### Evaluation data

| Role | Meaning |
| --- | --- |
| `ExpectedOutput` | A reference / expected output used in evaluation. |
| `EvaluationResult` | The result produced by an evaluation step. |
| `EvaluationScore` | A numeric score produced by an evaluation step. |

#### Prediction & serving data

| Role | Meaning |
| --- | --- |
| `PredictionRequest` | An incoming request for a prediction. |
| `PredictionResult` | The result of a prediction step. |
| `PredictionQueue` | A queue holding prediction requests. |
| `PredictionLog` | A log of predictions for monitoring / audit. |

#### Datasets & training data

| Role | Meaning |
| --- | --- |
| `TrainingDataset` | A dataset used to train a model. |
| `FineTuningDataset` | A dataset used to fine-tune a model. |
| `BatchDataset` | A dataset processed in batch. |
| `PreprocessedData` | Data produced by a preprocessing step. |

#### Monitoring & operations data

| Role | Meaning |
| --- | --- |
| `MonitoringBaseline` | A baseline used by a monitoring step. |
| `Alert` | An alert raised by a monitoring step. |
| `ServingImage` | A container image used to serve a model. |
| `ReleaseApproval` | An approval artifact gating a release. |

#### External / supply chain

| Role | Meaning |
| --- | --- |
| `ExternalDependency` | A resource sourced from outside the org's control whose provenance / integrity the graph can't vouch for. |
| `ExternalModel` | A model obtained from an external provider or model hub. |
| `ThirdPartyPackage` | A third-party software package, library, or plugin the system depends on. |
| `ExternalProviderCredential` | A credential (API key, token) granting access to an external provider. |

#### Generation, retrieval & prompt steps

| Role | Meaning |
| --- | --- |
| `GenerationStep` | Runs a generative model to produce output. |
| `PromptConstructionStep` | Assembles a prompt from inputs and context. |
| `QueryReformulationStep` | Reformulates a query. |
| `RetrievalStep` | Retrieves fragments from a knowledge source. |
| `VectorSearchStep` | Performs vector similarity search. |
| `KeywordSearchStep` | Performs keyword / lexical search. |
| `AggregationStep` | Aggregates results from multiple searches. |
| `RerankingStep` | Reranks retrieved candidates. |
| `EmbeddingStep` | Produces embeddings from data. |
| `ChunkingStep` | Splits documents into chunks. |

#### Prediction & preprocessing steps

| Role | Meaning |
| --- | --- |
| `PredictionStep` | Runs model inference to produce a prediction. |
| `PreprocessingStep` | Preprocesses input data. |
| `FastPredictionStep` | A low-latency prediction step. |
| `SlowPredictionStep` | A higher-latency prediction step. |

#### Training, lifecycle & scheduling steps

| Role | Meaning |
| --- | --- |
| `TrainingStep` | Trains a model. |
| `TrainingPipeline` | Orchestrates model training. |
| `FineTuningStep` | Fine-tunes a pre-trained model. |
| `DeploymentStep` | Deploys a model to serving. |
| `ModelLoadStep` | Loads a model into a runtime. |
| `ImageBuildStep` | Builds a serving image. |
| `JobScheduler` | Schedules jobs in a workflow. |

#### Evaluation, ops & agentic steps

| Role | Meaning |
| --- | --- |
| `ScoringStep` | Scores a model output during evaluation. |
| `EvaluationStep` | Evaluates model behavior. |
| `LoggingStep` | Logs predictions or events. |
| `MonitoringStep` | Monitors a deployed model. |
| `ToolInvocationStep` | Invokes an external tool, plugin, or API on behalf of the system (agentic tool use). |
| `StateChangingStep` | Changes external state: writes, transactions, or actions with side effects outside the system boundary. |

#### Control steps

| Role | Meaning |
| --- | --- |
| `GuardrailStep` | Screens input or output. |
| `InputGuardrailStep` | Screens user input before generation. |
| `OutputGuardrailStep` | Screens model output before release. |
| `OutputValidationStep` | Validates, encodes, or sanitizes model output before use. |
| `RateLimitControlStep` | Enforces rate, budget, quota, or loop bounds on model calls, retrieval breadth, or tool use. |

---

## Quick reference

| I want to… | Do this |
| --- | --- |
| Try it fast | **Load example ▾ → onyx_rag_chatbot**, then **Run assessment** |
| Import a structure-only graph | **Open .ttl**, or **Import t4b** for a Tool4Boxology export, then annotate |
| Make a graph matchable | **Annotate** tab → assign roles → **Apply annotations** |
| Check my graph is well-formed | **Validate** → read the **Input contract** tab |
| See why a finding fired | Select it in **Findings** → evidence highlights in the diagram |
| See which motifs matched | **Run assessment** → **Motifs** tab → click a motif to highlight its elements |
| Scaffold a pattern fast | Open the **Motifs** tray (right of the canvas) → click a motif to drop its annotated elements |
| Start from scratch | **Starter**, or **Clear** and build with the palette |
| Keep a graph off GitHub | Put it in `ontology/example_local/` — gitignored, and never in a built image |
