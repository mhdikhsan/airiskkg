# Facilitator Cheat-Sheet — Annotating Gen AI Systems for PAIR-AI

Prep for sessions where partners draw their own AI system in BEAM notation and
you help them annotate it so **Run assessment** produces findings. You don't know
their project in advance — this sheet lets you recognise the common shapes on the
fly and steer the annotation toward a graph the motifs can match.

Every finding and recipe below is **verified against the actual motif/risk
library** (I built each shape and ran the assessment). "✓ N findings" means that
minimal graph really produces N candidate findings.

---

## 0. The one rule to get right

**Motifs match on ROLES, not on BEAM types.** A perfectly drawn diagram with
correct box types and arrows but no `pair:playsRole` annotations produces **zero
findings**. Your whole job when steering is to get roles onto the boxes.

Three type gotchas that silently block matching — check these first:

| Must be… | …or the motif won't bind | Common mistake |
| --- | --- | --- |
| The LLM-call step → BEAM type **`Infer`** | RAG & Direct-Prompting motifs require `beam:Infer` | t4b exports often type it `beam:Generate` → **retype to Infer** |
| The model → **`StatisticalModel`** | generation motifs require `beam:StatisticalModel` | drawn as generic `beam:Model` |
| Data boxes → **`Data`** | query / context / prompt / response nodes must be `beam:Data` | drawn as `Symbol` or `Model` |

Also: wrap everything in a `beam:System` (`beam:hasResource` / `beam:hasProcess`) —
needed for the input-contract check and the diagram, good hygiene for matching.

---

## 1. The "generation quartet" — the minimum that fires

If a graph has an LLM at all, get these four roles on and you already get
findings from the **Direct Prompting motif**:

| Box | Role | BEAM type |
| --- | --- | --- |
| where the user's text enters | `PublicUserInput` (or `UserInput`) | `beam:Data` |
| the LLM | `GenerativeModel` | `beam:StatisticalModel` |
| the step that calls the LLM | `GenerationStep` | `beam:Infer` |
| what the user gets back | `UserFacingOutput` | `beam:Data` |

**✓ 4 findings** just from this (add a `SystemPrompt` box and it's 4 incl. system
prompt leakage): Direct-Prompting-without-grounding (LLM09), Improper Output
Handling (LLM05), System Prompt Leakage (LLM07), Unbounded Consumption (LLM10).

---

## 2. Role quick-map — what to tag with what

| If the box is… | Tag it | 
| --- | --- |
| the user's question / prompt / uploaded content | `PublicUserInput` / `UserInput` |
| the LLM / foundation model | `GenerativeModel` (+ `FoundationLLM` for RAG) |
| the step that runs the LLM to produce an answer | `GenerationStep` |
| the answer shown to the user | `UserFacingOutput` (+ `LLMResponse`) |
| a hidden/system prompt or instruction template | `SystemPrompt` |
| a vector DB / knowledge base / document store | `VectorStore` (or `VectorIndex` for the index) |
| the step that fetches context from that store | `RetrievalStep` |
| the fetched context / passages | `RetrievedContext` / `RetrievedResult` |
| a step that assembles the final prompt | `PromptConstructionStep` → produces `PromptTemplate` |
| a step that rewrites/expands the query | `QueryReformulationStep` → produces `RewrittenQuery` |
| an embedding step / model | `EmbeddingStep` / `EmbeddingModel` → `EmbeddingVector` |
| a reranking step / model | `RerankingStep` / `RerankerModel` |
| a moderation / safety filter on input | `InputGuardrailStep` |
| a moderation / validation filter on output | `OutputGuardrailStep` / `OutputValidationStep` |
| an eval / scoring / LLM-as-judge step | `EvaluationStep` / `ScoringStep` (+ `JudgeModel`) |
| a rate limiter / quota gate | `RateLimitControlStep` |
| a tool / API / function call the LLM triggers | `ToolInvocationStep` |
| a step that writes/changes state (DB write, transaction) | `StateChangingStep` |
| an external/3rd-party model, API, package, or provider | `ExternalModel` / `ExternalDependency` / `ThirdPartyPackage` |

### Data categories (only a few findings need them)

| Category | Tag it on… | Unlocks |
| --- | --- | --- |
| `SensitiveInformation` | a store / retrieved context holding personal or sensitive data | Sensitive-data-retrieval (LLM02) |
| `UntrustedContent` | *usually auto-derived* — content downstream of public input | Prompt injection (LLM01), Poisoning (LLM04) |
| `ConfidentialInformation` | secrets/credentials/config in context | disclosure conditions |

You rarely tag `UntrustedContent` by hand — tag the entry point `PublicUserInput`
and the taint propagates through retrieval/tools automatically.

---

## 3. The common Gen AI archetypes (predicted) + recipes

Ranked by how likely a partner is to draw them.

### A. LLM assistant / copilot — *direct prompting, no retrieval*
Chatbot, writing helper, "classify/extract with an LLM", Q&A with no knowledge base.

Shape: `PublicUserInput` → `GenerationStep`(Infer) uses `GenerativeModel` →
`UserFacingOutput`. (+ optional `SystemPrompt`.)
**✓ 4 findings:** LLM09 (no grounding), LLM05 (output handling), LLM07 (system
prompt), LLM10 (unbounded).

### B. RAG Q&A over documents — *vector store + LLM*
The single most common Gen AI system. Docs → embeddings → vector store; query →
retrieve → stuff into prompt → LLM → answer.

Full-RAG roles: query `PublicUserInput`; index `VectorIndex`(Data); retrieval
`RetrievalStep` → `RetrievedContext`; prompt-build `PromptConstructionStep` →
`PromptTemplate`(Data); LLM `FoundationLLM`(StatisticalModel); gen
`GenerationStep`(Infer) → response `LLMResponse`.
**✓ baseline 2:** LLM09 (misinformation/weak grounding) + LLM08 (vector &
embedding). **Add** `SensitiveInformation` on the store & context → **+LLM02**;
public input flowing into retrieval → **+LLM01**.

### C. GraphRAG / simple "retrieve from a store" — *retrieval motif*
Retrieval from a KG or search index that feeds the LLM directly (no separate
prompt-build box). This is the bundled
[GraphRAG walkthrough](annotation_walkthrough_graphrag.md).

Roles: query `UserInput`; store `VectorStore` + `SensitiveInformation`; retrieval
`RetrievalStep`; result `RetrievedResult` + `SensitiveInformation`; LLM
`GenerativeModel`; gen `GenerationStep`; output `UserFacingOutput`.
**✓ 3 findings:** LLM01 (prompt injection), LLM02 (sensitive retrieval), LLM08
(vector & embedding).

### D. Agent with tools / function calling — *excessive agency*
The LLM decides to call tools / APIs / take actions.

Shape: the generation quartet **plus** a `ToolInvocationStep` (or
`StateChangingStep`) that the generation step **`beam:inform`s** (arrow from the
LLM step to the tool step).
**✓ 4 findings:** adds **LLM06 (excessive agency)** on top of LLM05/LLM09/LLM10.

### E. Summarization / content generation — *direct prompting variant*
Document/data in → LLM → summary/content out. Annotate exactly like archetype A:
the input document is the `PublicUserInput`/`UserInput`, the summary is
`UserFacingOutput`. Same finding family.

### F. Fine-tuned / custom-model pipeline — *training / supply chain*
Train or fine-tune on proprietary data, then serve. More ML-ops than chat.

Roles: fine-tuning/training steps + datasets; an external base model →
`ExternalModel` → **LLM03 (supply chain)**; a training/index input tagged
`UntrustedContent` → **LLM04 (data & model poisoning)**.

---

## 4. Steering toward *fewer* findings — controls suppress risk

Very useful to show partners "how to fix it." Adding a represented control
removes the corresponding finding (verified):

| Add this box… | wired as… | removes |
| --- | --- | --- |
| `OutputGuardrailStep` / `OutputValidationStep` | `beam:use` the output | LLM05 improper output handling |
| `RateLimitControlStep` | `beam:inform` the generation step | LLM10 unbounded consumption |
| `EvaluationStep` / `ScoringStep` | `beam:use` the response | LLM09 misinformation |
| a `KnowledgeSource` / `RetrievedContext` feeding generation | into the prompt | LLM09 direct-prompting-without-grounding |
| `InputGuardrailStep` | `beam:use` the user input | LLM01 prompt injection (input path) |

*Verified:* a direct-prompting graph with an output guardrail **and** a rate
limiter dropped from 4 findings to 1.

---

## 5. Live facilitation script

Ask these, in order, while they draw:

1. **"Where does the user's text enter?"** → tag `PublicUserInput` (Data).
2. **"Which box is the LLM?"** → `GenerativeModel`, and make its **type
   `StatisticalModel`**.
3. **"Which box calls the LLM to produce the answer?"** → `GenerationStep`, and
   make its **type `Infer`** (not Generate!).
4. **"What does the user see?"** → `UserFacingOutput`.
   → *Run assessment now; you already get findings. Momentum.*
5. **"Do you fetch any context / search a knowledge base?"** → the fetch step is
   `RetrievalStep`, the store is `VectorStore`, the result is `RetrievedContext`.
6. **"Does that store hold anything personal or sensitive?"** → tag
   `SensitiveInformation` on the store and the retrieved context.
7. **"Does the LLM call any tools or take actions?"** → the action box is
   `ToolInvocationStep`; draw an arrow (`inform`) from the LLM step to it.
8. **"Any moderation / filtering / rate limiting?"** → tag the guardrail/limit
   roles and watch findings drop — that's their mitigation story.

Reassure them on framing: findings are **candidate** risks (structural
dispositions), not verdicts. Missing findings usually means a missing role, not a
safe system.

---

## 6. Master trigger table (all 11 risk patterns)

Your reference for every lever:

| OWASP | Risk pattern | Fires when | Needs motif |
| --- | --- | --- | --- |
| LLM01 | Prompt injection | untrusted content (from retrieval/tools, tainted by public input) reaches generation → user output, no input/output control | any binding the untrusted element (Vector-IR, RAG) |
| LLM02 | Sensitive data retrieval | store **and** retrieved result tagged `SensitiveInformation` → generation → output, no disclosure control | Vector-IR |
| LLM03 | Supply chain compromise | an external model/data/dependency/artifact is used, no control on it | External Dependency |
| LLM04 | Data & model poisoning | a bound source tagged `UntrustedContent` enters embeddings / fine-tuning / training-to-serving | Embeddings / FineTuning / TrainingToServing |
| LLM05 | Improper output handling | generation → user output with no `OutputValidationStep` / `OutputGuardrailStep` on it | any binding the gen step |
| LLM06 | Excessive agency | generation step `inform`s a `ToolInvocationStep` / `StateChangingStep`, no control | any binding the gen step |
| LLM07 | System prompt leakage | a `SystemPrompt` feeds generation → user output, no control | any binding sysprompt / gen / output |
| LLM08 | Vector & embedding weakness | any vector-retrieval / embedding / reranker motif matches | Vector-IR / RAG / Embeddings / Reranker |
| LLM09 | Misinformation (weak grounding) | RAG generation with no `EvaluationStep` / `ScoringStep` on the response | RAG |
| LLM09 | Direct prompting without grounding | Direct-Prompting generation with no `KnowledgeSource` / `RetrievedContext` grounding | Direct Prompting |
| LLM10 | Unbounded consumption | LLM/retrieval loop or generation with no `RateLimitControlStep` | Direct Prompting / RAG / Query Rewriting |

## See also

- [annotation_walkthrough_graphrag.md](annotation_walkthrough_graphrag.md) — a full worked example, click by click
- [user_guide.md](user_guide.md) — running the workbench and the UI
- [reference/PAIR-AI_glossary_v1.2.md](reference/PAIR-AI_glossary_v1.2.md) — roles and modeling rules
