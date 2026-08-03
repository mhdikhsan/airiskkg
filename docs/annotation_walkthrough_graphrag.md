# Annotation Walkthrough — GraphRAG Example

A step-by-step, reproduce-it-yourself guide to annotating a real, un-annotated
architecture graph so that PAIR-AI can match it against motifs and produce
candidate risk findings.

We use the bundled example **`ontology/example/beam_export_graph_rag.ttl`** — a
GraphRAG "event information chatbot" exported from the t4b-beam tool. Like every
export from that tool, it carries **structure only** (BEAM types + data-flow
edges) and **no pattern roles at all**. That is exactly why, out of the box, it
produces **zero findings** — and why annotation is the step that unlocks the
assessment.

> Everything below is verified against the actual pipeline: un-annotated the
> graph yields **0 motif matches / 0 findings**; after the annotation in this
> guide it yields **1 motif match and 3 candidate findings**.

---

## 1. The example at a glance

It is a Retrieval-Augmented Generation pipeline over a knowledge graph:

```
 "Natural Language Question"  (nlq, beam:Data)
            │ use
            ▼
 [Event ID Extraction]  (extraction, beam:Infer)
            │ produce
            ▼
      "Event ID"  (event_id, beam:Data) ─────────────┐
                                                      │ use
 "Event KG" (event_kg, beam:SemanticModel) ── use ──▶ │
 "SPARQL Query Template" (sparql_tmpl, beam:Symbol) ─ use ─▶ [KG Querying / Retrieval]
                                                             (kg_query, beam:Transform)
                                                                     │ produce
                                                                     ▼
                                        "Event KG Subgraph"  (kg_subgraph, beam:Data) ──┐
                                                                                        │ use
 "LLM" (llm, beam:StatisticalModel) ───────────────── use ─────────────────────────▶  │
 "System Prompt Template" (sys_prompt_tmpl, beam:Symbol) ── use ──▶ [LLM Prompting / Generation]
                                                                    (llm_prompt, beam:Generate)
                                                                            │ produce
                                                                            ▼
                                                      "Event Summary"  (summary, beam:Data)
```

The modelers even wrote their own risk notes into the file (as `beamr:Risk`
annotations): **Information Leakage**, **Malicious Knowledge Injection**,
**Hallucination**, **Context too long**. Two of these map directly onto
PAIR-AI risk patterns — which is what our annotation will surface.

### Why it produces nothing as-is

Motifs match on **roles**, not on BEAM types alone. The export has
`beam:Data` / `beam:Transform` / `beam:StatisticalModel` and `beam:use` /
`beam:produce` edges, but not a single `pair:playsRole` triple. No roles ⇒ no
motif can bind ⇒ no findings. Annotation adds the missing roles (and the data
categories the risk conditions read).

---

## 2. What we are aiming for

| Modeler's own note in the file | PAIR-AI candidate finding we will produce | OWASP |
| --- | --- | --- |
| "Information Leakage — private info in KG may be leaked" | **Sensitive data retrieval exposure** | LLM02 |
| "Malicious Knowledge Injection → malicious prompt" | **Prompt injection exposure** | LLM01 |
| *(structural consequence of KG retrieval)* | **Vector & embedding weakness** | LLM08 |

All three are driven by one motif: the **Vector-Based Information Retrieval
Motif**. (The "Hallucination" note would map to *Misinformation from weak
grounding*, but that needs the full RAG motif — see [§6](#6-going-further).)

---

## 3. The annotation — which component gets which role

This is the heart of the exercise. Assign each component the role (and, where
noted, the data category) below. **★ = strictly required** to produce the three
findings; the unmarked rows make the model semantically complete and are good
practice.

| ★ | Component (label) | BEAM type (in file) | **Role** | **Data category** | Why it matters |
| --- | --- | --- | --- | --- | --- |
| ★ | Natural Language Question | `beam:Data` | `PublicUserInput` | — | The end-user's question. It is the **untrusted-input source**: the taint that makes the prompt-injection finding fire is propagated from here. |
|   | Event ID Extraction | `beam:Infer` | `QueryReformulationStep` | — | Turns the NL question into a query key (semantic completeness). |
| ★ | Event ID | `beam:Data` | `UserInput` | — | The query the retrieval step actually consumes — the motif binds this as the "query". |
| ★ | KG Querying (Retrieval) | `beam:Transform` | `RetrievalStep` | — | The retrieval process — the anchor of the motif. |
| ★ | Event KG | `beam:SemanticModel` | `VectorStore` | `SensitiveInformation` | The store being retrieved from; the note says it holds private data. |
| ★ | Event KG Subgraph | `beam:Data` | `RetrievedResult` | `SensitiveInformation` | The retrieved context handed to the LLM. Sensitive → disclosure risk; being retrieved from an external store → untrusted → injection risk. |
|   | System Prompt Template | `beam:Symbol` | `SystemPrompt` | — | Hidden instructions (semantic completeness). |
| ★ | LLM | `beam:StatisticalModel` | `GenerativeModel` | — | The generation model. |
| ★ | LLM Prompting (Generation) | `beam:Generate` | `GenerationStep` | — | The step that produces the answer. |
| ★ | Event Summary | `beam:Data` | `UserFacingOutput` | — | The answer shown to the user — the sink the risks flow to. |
|   | SPARQL Query Template | `beam:Symbol` | *(none needed)* | — | Auxiliary input; no role required. |

Notes worth knowing:

- **`VectorStore` on a knowledge graph is a modeling approximation.** The motif
  is named "vector-based retrieval" but structurally it just means *retrieval
  from a store*. `VectorStore` is a sub-role of `KnowledgeSource`; using it here
  is what lets the retrieval motif (and its risk patterns) recognise the KG.
- **You do not need to retype anything.** The two risk patterns we target check
  the *role* on the generation step, not its BEAM class, so `llm_prompt` can stay
  `beam:Generate`. (The *stricter* RAG and direct-prompting motifs would require
  a `beam:Infer` generation step — again, see §6.)
- **One role + one category per element is enough.** The `UntrustedContent`
  taint on the subgraph is derived automatically from the public input flowing
  through the pipeline, so you never have to add it by hand.

---

## 4. Do it in the UI (step by step)

1. **Start the app** and open it in the browser:
   ```bash
   .venv/Scripts/airiskkg.exe serve      # → http://127.0.0.1:5000/
   ```
2. **Load the example** — toolbar → **Load example ▾ → `beam_export_graph_rag`**.
   The pipeline draws on the right.
3. **(Optional) Confirm the baseline** — click **Run assessment**. The Findings
   tab shows **nothing**. That is the "no roles" state.
4. **Open the Annotate tab** — bottom drawer → **Annotate**. Every element is
   listed with a **Role** selector and a **Data category** selector. The count
   badge shows how many elements are still untagged. Selecting a row highlights
   that element in the diagram.
5. **Fill in the table from [§3](#3-the-annotation--which-component-gets-which-role)** —
   for each component pick its Role, and for **Event KG** and **Event KG
   Subgraph** also pick the Data category **`Sensitive Information`**.
   - Prefer clicking a node in the diagram? Its popup has the same **Role** and
     **Data category** selectors plus **Apply** — either path writes the same
     triples.
6. **Click "Apply annotations."** The Turtle on the left grows `pair:playsRole`
   and `pair:containsDataCategory` triples. (Re-applying is idempotent, so you
   can iterate freely.)
7. **Click "Run assessment."** The Findings tab now shows **3 candidate
   findings** (see below). Select any finding to highlight its evidence in the
   diagram.

---

## 5. Expected result

After annotation the assessment reports:

```
motif matches : 1   (Vector-Based Information Retrieval Motif)
findings      : 3
  • Candidate prompt injection exposure            → OWASP LLM01
  • Candidate sensitive data retrieval exposure    → OWASP LLM02
  • Candidate vector and embedding weakness        → OWASP LLM08
```

What each one means:

- **Prompt injection (LLM01)** — untrusted content (the subgraph retrieved from
  the KG, tainted by the public question) reaches the generation step and the
  user-facing summary with no represented sanitization. *This is the modelers'
  "Malicious Knowledge Injection".*
- **Sensitive data retrieval exposure (LLM02)** — sensitive content in the KG
  and in the retrieved subgraph reaches generation and user-facing output with
  no represented disclosure control. *This is the modelers' "Information
  Leakage".*
- **Vector & embedding weakness (LLM08)** — a structural consequence of building
  the system on retrieval from a store; flagged for review of the retrieval /
  indexing layer.

### Reproduce it without the UI

The finished result is bundled as
**`ontology/example/beam_export_graph_rag_annotated.ttl`** — the same export with
this annotation already applied. It appears in **Load example ▾** next to the raw
one, so you can load either and compare, or run it straight from the CLI:

```bash
.venv/Scripts/airiskkg.exe assess ontology/example/beam_export_graph_rag_annotated.ttl
```

To do it by hand instead, paste this block at the end of the loaded Turtle (or
append it to the file) and **Run assessment** — it is exactly what the UI writes,
and exactly what the bundled annotated file contains:

```turtle
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix comp: <http://tool4boxology.org/Component/> .

comp:nlq             pair:playsRole pair:PublicUserInput .
comp:extraction      pair:playsRole pair:QueryReformulationStep .
comp:event_id        pair:playsRole pair:UserInput .
comp:kg_query        pair:playsRole pair:RetrievalStep .
comp:event_kg        pair:playsRole pair:VectorStore ;
                     pair:containsDataCategory pair:SensitiveInformation .
comp:kg_subgraph     pair:playsRole pair:RetrievedResult ;
                     pair:containsDataCategory pair:SensitiveInformation .
comp:sys_prompt_tmpl pair:playsRole pair:SystemPrompt .
comp:llm             pair:playsRole pair:GenerativeModel .
comp:llm_prompt      pair:playsRole pair:GenerationStep .
comp:summary         pair:playsRole pair:UserFacingOutput .
```

> Remember the framing: these are **candidate** risks — structural dispositions
> the architecture is prone to *unless* something outside the submitted graph
> prevents them. They are prompts for review, not confirmed failures.

---

## 6. Going further

Want the assessment to also flag the modelers' **"Hallucination"** note
(*Misinformation from weak grounding*, OWASP LLM09)? That risk pattern fires on
a match of the **full RAG motif**, which is stricter than the retrieval motif we
used and needs the graph to represent, in addition to the roles above:

- a **prompt-construction step** (`beam:Transform`, role `PromptConstructionStep`)
  that uses both the query and the retrieved context and **produces a prompt**
  (`beam:Data`, role `PromptTemplate`);
- a **generation step typed `beam:Infer`** (not `beam:Generate`) that uses that
  prompt, and
- the response tagged `LLMResponse`.

The GraphRAG export has no separate prompt-construction node (its generation
step consumes the subgraph directly), so surfacing the hallucination finding is
a small **structural** edit, not an annotation — a good next exercise using the
canvas: drag in a Transform node, wire it between retrieval and generation, and
retype the generation step. The "Context too long" note has no structural motif
and is out of scope for design-time matching.

## See also

- [user_guide.md](user_guide.md) — the general workbench guide (running, UI, findings)
- [reference/PAIR-AI_glossary_v1.2.md](reference/PAIR-AI_glossary_v1.2.md) — terminology and modeling rules
- [notes/running_the_webapp.md](notes/running_the_webapp.md) — run/setup notes
