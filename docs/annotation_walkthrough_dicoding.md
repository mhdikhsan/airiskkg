# Annotation Walkthrough — Dicoding RAG Assistant

Role annotation for the **`ontology/example/dicoding.ttl`** example: the Dicoding
course-explanation assistant, a hybrid-retrieval RAG chatbot (sparse retrieval +
query embedding + re-ranking, wrapped in input sanitization and output
guardrails, with conversation history). Exported from t4b-beam, it carries
**structure only** — no pattern roles — so out of the box it yields **0
findings**. This guide assigns the roles (and one type correction) that make it
assessable.

> Verified end to end: un-annotated → **0 findings**; after this annotation →
> **5 candidate findings across 3 motif matches**, two of which match the risks
> the modelers themselves noted on the diagram (prompt injection, system prompt
> leakage).

---

## 1. The pipeline

```
INDEXING (offline)
  "Course Material" ──▶ [Compute Embeddings] ◀── "Embedding Models"
  "Course Material" ──▶ [Indexing]           ─────▶ "Vector Representations"

QUERY (online)
  "User Query" ──▶ [Sanitize Input] ──▶ "Sanitized User Query"
        │
        ├─▶ [Compute embedding] ──▶ "User Query Vector Representation"
        │
        └─▶ [Sparse Retrieval] ◀── "Vector Representations" ──▶ "Sparse Retrieval Results"
                                                                       │
        "FlashRank" ──▶ [Re-Ranking] ◀── "User Query Vector Representation"
                                     ◀── "Sparse Retrieval Results"
                                        └─▶ "Retrieved Course Material Chunks"
                                                     │
                              [Sanitize Input] ──▶ "Sanitized Retrieved Course Material"
                                                     │
  [Generation] ◀── "LLM", "System Prompt", "Conversation History",
                   "Sanitized User Query", "Sanitized Retrieved Course Material"
        └─▶ "Generated Answer" ──▶ [Guardrail Checks] ──▶ "Checked Answer"
                                                                │
                                        [Extend Conversation History] ──▶ "Conversation History" ↩ (back to Generation)
```

The modelers' own risk notes on the diagram: **Potential Processing of Personal
Data**, **Prompt Injection (direct & indirect)**, **System Prompt Leakage**,
**Model/Provider Unavailable**.

---

## 2. The annotation — component → role

Assign each element the role below (via the **Annotate** tab, or the node popup).
**★** marks the one **type correction**: the LLM comes in as a generic
`beam:Model`; an LLM is a statistical model, and the generation-side motif
requires `beam:StatisticalModel`, so retype it (popup → **Type**). Rows without a
role are auxiliary — no motif needs them.

### Resources

| Element (label) | BEAM type | **Role** | Data category |
| --- | --- | --- | --- |
| User Query | `Data` | `PublicUserInput` | `SensitiveInformation` |
| Sanitized User Query | `Data` | `UserInput` | — |
| Course Material | `Data` | `SourceDocument` | — |
| Vector Representations | `Data` | `VectorStore` **+** `VectorIndex` | — |
| User Query Vector Representation | `Data` | `EmbeddingVector` | — |
| Embedding Models | `Model` | `EmbeddingModel` | — |
| Sparse Retrieval Results | `Data` | `RetrievedContext` | — |
| FlashRank | `Model` | `RerankerModel` | — |
| Retrieved Course Material Chunks | `Data` | `RetrievedContext` | — |
| Sanitized Retrieved Course Material | `Data` | `RetrievedContext` | — |
| **LLM** | `Model` → **`StatisticalModel`** ★ | `GenerativeModel` **+** `FoundationLLM` | — |
| System Prompt | `Data` | `SystemPrompt` | — |
| Generated Answer | `Data` | `LLMResponse` **+** `UserFacingOutput` | — |
| Checked Answer | `Data` | `UserFacingOutput` **+** `SanitizedOutput` | — |
| Conversation History | `Data` | *(none — auxiliary)* | — |

### Processes

| Element (label) | BEAM type | **Role** |
| --- | --- | --- |
| Compute Embeddings | `Infer` | `EmbeddingStep` |
| Indexing | `Transform` | `EmbeddingStep` |
| Compute embedding | `Infer` | `EmbeddingStep` |
| Sparse Retrieval | `Transform` | `RetrievalStep` |
| Re-Ranking | `Infer` | `RerankingStep` |
| Sanitize Input *(query)* | `Transform` | `InputGuardrailStep` |
| Sanitize Input *(retrieved)* | `Transform` | `InputGuardrailStep` |
| Generation | `Infer` | `GenerationStep` |
| Guardrail Checks | `Transform` | `OutputGuardrailStep` |
| Extend Conversation History | `Transform` | *(none — auxiliary)* |

Why `Generated Answer` gets `UserFacingOutput`: the role covers data "exposed to
a user **or downstream consumer**" — the generated answer is consumed by the
output guardrail on its way to the user, so it qualifies, and this is what lets
the output-side risk patterns evaluate it.

---

## 3. Reproduce it

Paste this at the end of the loaded Turtle and **Run assessment** (it's exactly
what the Annotate tab + the one type fix write):

```turtle
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix comp: <http://tool4boxology.org/Component/> .

comp:node_1784869896349  a beam:StatisticalModel .                                          # ★ LLM: correct the type

comp:node_1784870012743  pair:playsRole pair:PublicUserInput ;
                         pair:containsDataCategory pair:SensitiveInformation .              # User Query
comp:node_1784887565510  pair:playsRole pair:UserInput .                                    # Sanitized User Query
comp:node_1784887540045  pair:playsRole pair:InputGuardrailStep .                           # Sanitize Input (query)
comp:node_1784869793422  pair:playsRole pair:SourceDocument .                               # Course Material
comp:node_1784874668240  pair:playsRole pair:EmbeddingModel .                               # Embedding Models
comp:node_1784869989408  pair:playsRole pair:EmbeddingStep .                                # Compute Embeddings
comp:node_1784875092512  pair:playsRole pair:EmbeddingStep .                                # Indexing
comp:node_1784869861521  pair:playsRole pair:VectorStore , pair:VectorIndex .               # Vector Representations
comp:node_1784875177561  pair:playsRole pair:EmbeddingStep .                                # Compute embedding (query)
comp:node_1784875216876  pair:playsRole pair:EmbeddingVector .                              # User Query Vector Representation
comp:node_1784870083270  pair:playsRole pair:RetrievalStep .                                # Sparse Retrieval
comp:node_1784875312354  pair:playsRole pair:RetrievedContext .                             # Sparse Retrieval Results
comp:node_1784875268724  pair:playsRole pair:RerankerModel .                                # FlashRank
comp:node_1784875284652  pair:playsRole pair:RerankingStep .                                # Re-Ranking
comp:node_1784870112185  pair:playsRole pair:RetrievedContext .                             # Retrieved Course Material Chunks
comp:node_281784888790737 pair:playsRole pair:InputGuardrailStep .                          # Sanitize Input (retrieved)
comp:node_1784887780141  pair:playsRole pair:RetrievedContext .                             # Sanitized Retrieved Course Material
comp:node_1784869896349  pair:playsRole pair:GenerativeModel , pair:FoundationLLM .         # LLM
comp:node_1784870019545  pair:playsRole pair:SystemPrompt .                                 # System Prompt
comp:node_1784870052005  pair:playsRole pair:GenerationStep .                               # Generation
comp:node_1784870179734  pair:playsRole pair:LLMResponse , pair:UserFacingOutput .          # Generated Answer
comp:node_1784870204212  pair:playsRole pair:OutputGuardrailStep .                          # Guardrail Checks
comp:node_1784870222579  pair:playsRole pair:UserFacingOutput , pair:SanitizedOutput .      # Checked Answer
```

---

## 4. Expected result

```
motif matches : 3   (Direct Prompting · Vector-based Information Retrieval · Reranker)
findings      : 5
  • Candidate system prompt leakage exposure       → OWASP LLM07
  • Candidate prompt injection exposure             → OWASP LLM01
  • Candidate vector and embedding weakness         → OWASP LLM08   (×2: retrieval + rerank)
  • Candidate unbounded LLM or retrieval consumption → OWASP LLM10
```

Mapped to the modelers' own notes:

| Modeler's note on the diagram | PAIR-AI finding |
| --- | --- |
| "Prompt Injection (direct & indirect)" | ✓ **Prompt injection (LLM01)** — untrusted retrieved course material reaches generation |
| "System Prompt Leakage" | ✓ **System prompt leakage (LLM07)** — system prompt feeds a generation path to user output |
| "Potential Processing of Personal Data" | Tagged (`SensitiveInformation` on the user query); no retrieval-disclosure finding because the sensitive data is in the *query*, not the retrieved course material |
| "Model/Provider Unavailable" | Out of scope — an availability/ops concern, not a structural motif |

### What is *not* flagged — and why (the controls are working)

Two output-side patterns are **correctly suppressed** by controls present in the
architecture:

- **Improper output handling (LLM05)** — suppressed because **Guardrail Checks**
  (`OutputGuardrailStep`) screens the generated answer before it goes out.
- **Direct-prompting-without-grounding (LLM09)** — suppressed because the
  retrieved course material (`RetrievedContext`) grounds the generation.

This is the intended reading: findings are **candidate** risks, and a represented
control removes the corresponding candidate. Dicoding's sanitization + guardrail +
grounding structure is why several risks the raw shape could carry are not raised.

## See also

- [annotation_walkthrough_graphrag.md](annotation_walkthrough_graphrag.md) — the simpler GraphRAG worked example
- [annotation_facilitator_cheatsheet.md](annotation_facilitator_cheatsheet.md) — recipes + steering script (incl. the `StatisticalModel` type gotcha used here)
- [reference/catalogue.md](reference/catalogue.md) — every motif, risk pattern, and role
