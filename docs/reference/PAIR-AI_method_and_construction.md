# PAIR-AI — Method and Knowledge-Base Construction

Status: current as of **2026-08-30**, branch `feature/bpmn-business-context`.
Authority on terminology and modeling rules: `docs/reference/PAIR-AI_glossary_v1_3.md`
(rules R1–R10). Where this document and the glossary disagree, the glossary wins.

**What this document is.** One place that explains how the PAIR-AI knowledge base was
*built* and how an assessment *runs*: where risk patterns come from, where the role
vocabulary actually came from (§2 is deliberately blunt about this), how motifs are
curated, how the ontology reuses and aligns external vocabularies, what the pipeline
executes, what the method currently cannot do, and — since 2026-08 — how a business process
model reaches the assessment (§7).

**What this document is not.** Not a user guide (see `docs/user_guide.md` for the
workbench), not an
inventory (see `docs/reference/catalogue.md`), not a change record (see
`CHANGELOG_data_model.md`).

**Supersedes** (removed in the same commit): `docs/notes/pattern_and_role_derivation.md`,
`docs/notes/pattern_library_derivation.md`, `docs/notes/pipeline_process.md`,
`docs/notes/assessment_guidelines.txt`, `docs/notes/pattern_examples.md`,
`docs/notes/pattern_examples.en.md`, `docs/notes/v2_update_and_workbench_guide.md`,
`docs/reference/pair_ai_semantic_web_guide.html`.

---

## 0. Orientation

PAIR-AI is **design-time** risk assessment for AI systems. The system is never executed;
its architecture is described as an RDF graph, and the method reports which risks the
*structure* predisposes the system to.

The mental model is static analysis for architectures: **motifs ≈ linter rules**,
**candidate risk findings ≈ warnings** — never confirmed bugs.

Formally the method is a function over one architecture graph:

> **Assessment(G) → Findings**, evaluated against two frozen, curated libraries.

- **Motif Library** — risk-neutral structural patterns ("query-driven retrieval over a
  vector store", "a user query answered directly by an LLM").
- **Risk Pattern Library** — risk knowledge, each entry being
  **Risk Pattern = Motif + Applicability Conditions + Mechanism + Taxonomy Links + Controls**,
  anchored to OWASP LLM Top 10 / IBM AI Risk Atlas / MIT AI Risk Repository.

Every output is a **candidate** risk: a structural disposition toward harm, not an
observed failure and not a prediction that harm will occur. The formal basis is the Open
World Assumption (R4): a missing triple means *unknown*, not *false*, so the
`FILTER NOT EXISTS` control checks are closed-world claims **about the submitted graph
only**.

### Current size of the knowledge base

Counted off the loaded graph on 2026-08-30. Re-count rather than edit by hand — every
figure but the motif count had drifted before anyone noticed.

| Artifact | Count | File |
| --- | --- | --- |
| Architectural motifs (ODPs) | 31 | `ontology/patterns/motif.ttl` |
| AI risk patterns | 15 | `ontology/patterns/risk_pattern_library.ttl` |
| Applicability conditions | 16 (on 20 attachments) | `ontology/patterns/risk_pattern_library.ttl` |
| Risk mechanisms | 14 | `ontology/taxonomy/owasp_llm.ttl`, `owasp_asi.ttl` |
| Pattern roles | 97 | `ontology/core/pair_ai_pattern.ttl` |
| Data categories | 7 | `ontology/core/pair_ai_pattern.ttl` |
| Actionable controls (`pat:Control_*`) | 12 | `ontology/patterns/control_mitigation_layer.ttl` |
| Facet concepts (project namespaces) | 35 | `ontology/facets/*.ttl` |
| Registered SPARQL implementations (OQPs) | 63 | `ontology/patterns/implementation/`, `ontology/context/implementation/` |
| — of which motif matchers | 31 | `match/*.rq` |
| — of which risk-finding queries | 15 | `risk/*.rq` |
| — of which data-category derivations | 7 | `propagation/*.rq` (6) + `business_data_bridge.rq` |
| — of which business-flow derivations | 1 | `business_flow.rq` |
| — of which mitigation rewrites | 9 registrations over 8 files | `mitigation/*.rq` |
| Loaded triples | 7 470 | — |

Taxonomy entries loaded: IBM Atlas 30 · MIT domains 19 · MIT control families 88 ·
NIST AI 600-1 9 · OWASP LLM 10 · OWASP ASI 4.

Note the ratio: **every motif has an executable matcher**, but only **14 of 31 motifs
carry at least one risk pattern** (§6.7).

---

## 1. Risk pattern derivation

### 1.1 Source stack

```
ontology/taxonomy/            external risk taxonomies, re-expressed as RDF/SKOS
ontology/patterns/motif.ttl   external architecture pattern catalogs, re-expressed as RDF
        |
        v
ontology/patterns/risk_pattern_library.ttl    project work: binds motifs to taxonomy
                                              risks through curated risk patterns
        |
        v
ontology/patterns/implementation/risk_*.rq    SPARQL CONSTRUCTs that execute them
```

**Primary anchor — OWASP Top 10 for LLM Applications 2025.** The ten categories are
re-expressed as SKOS concepts `owasp:llm01-prompt-injection` … `owasp:llm10-unbounded-consumption`
in `ontology/taxonomy/owasp_llm.ttl`, each with a `dct:source` pointing at the OWASP release.
**Every `skos:definition`, risk mechanism and risk condition in that file is written from
scratch** for PAIR-AI's structural model — not a copy or a close paraphrase. OWASP is
CC BY-**SA** 4.0, whose ShareAlike term would bind this repository's CC BY 4.0 files; only
identifiers, numbering and short names are reused. The file states this in its own header.

**Agentic anchor — OWASP Agentic Top 10 (ASI) 2026**, in `ontology/taxonomy/owasp_asi.ttl`,
under the same licence discipline. Only **4 of its entries** are modelled — ASI01 goal
hijack, ASI02 tool misuse, ASI06 memory and context poisoning, ASI07 insecure inter-agent
communication. The partiality is deliberate: entries defined by runtime behaviour have no
shape in a submitted graph, so modelling them would fire a finding on every agent — noise
that breaks candidate framing rather than supporting it.

**Secondary taxonomies — IBM AI Risk Atlas, MIT AI Risk Repository, MIT AI Risk
Controls**, all obtained through the IBM *AI Atlas Nexus* knowledge-graph YAML/TSV data
and re-expressed in `ibm_risk_atlas.ttl`, `mit_ai_risk_repo.ttl`, `mit_air_risk_control.ttl`,
`nexus_taxonomy_core.ttl`. These are used as **link targets and evidence**, not as
generators of new risk patterns.

### 1.2 The gap that had to be bridged

OWASP publishes prose per category ("user or external inputs may alter LLM behavior in
unintended ways"). Prose is not machine-checkable. Two layers were therefore authored:

1. **Mechanism + risk conditions in `owasp_llm.ttl`.** For each OWASP entry, one
   `pair:RiskMechanism` (e.g. `owasp:mechanism-instruction-override`) and one or more
   `nexus:RiskCondition` (e.g. `owasp:condition-untrusted-input-enters-prompt-context`)
   were written by interpreting the OWASP description into a graph-level cause and its
   preconditions.

2. **Risk patterns + applicability conditions in `risk_pattern_library.ttl`.** For each
   pattern, the `pair:ApplicabilityCondition` instances and the SPARQL logic in the
   matching `risk_*.rq` are original project work: they translate mechanism prose into a
   graph pattern that can actually be evaluated (e.g. "an element carrying
   `pair:UntrustedContent` reaches a generation step that produces user-facing output,
   and no represented control sits on that path").

These nodes deliberately carry no `dct:source`, because there is no external artifact to
point at — they are the project's contribution, not a copy.

### 1.3 Anatomy of a risk pattern

Verbatim from `risk_pattern_library.ttl`:

```turtle
pat:PromptInjectionRiskPattern
    a pair:RiskPattern ;
    pair:derivedFrom owasp:llm01-prompt-injection ;
    dct:source <https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/> ;
    pair:hasMotif pat:DirectPromptingMotif ,
                  pat:RetrievalAugmentedGenerationMotif ,
                  pat:QueryRewritingMotif ;
    pair:hasMechanism owasp:mechanism-instruction-override ;
    pair:hasApplicabilityCondition pat:PromptInjection_UntrustedPromptContextCondition ;
    pair:mayIndicateRisk owasp:llm01-prompt-injection , atlas:prompt-injection ,
                         mit:subdomain-2-2 ;
    pair:suggestedControl pat:Control_InputValidationAndPromptIsolation ,
                          pat:Control_Guardrails ,
                          pat:Control_LoggingMonitoringAndEvals ;
    pair:implementedBy pat:PromptInjectionOQP .
```

Provenance is tiered per field:

| Field | Example value | Provenance |
| --- | --- | --- |
| `pair:hasMechanism` | `owasp:mechanism-instruction-override` | Authored by interpreting OWASP prose (§1.2) |
| `pair:hasApplicabilityCondition` | `pat:PromptInjection_UntrustedPromptContextCondition` | Authored for this project — no external source |
| `pair:mayIndicateRisk` | `owasp:llm01…`, `atlas:prompt-injection`, `mit:subdomain-2-2` | External URIs; cross-taxonomy links partly upstream-verified, partly project curation (§1.5) |
| `pair:suggestedControl` | `pat:Control_Guardrails` | Project-authored control catalogue (§1.6) |
| `pair:hasMotif` | `pat:DirectPromptingMotif` | Curated m:n binding to the Motif Library |

The **mechanism is inert**: it is never evaluated during matching. Encoding the causal
account a second time as a graph condition would duplicate the applicability condition
and reintroduce declarative/executable drift, so the mechanism is attached by reference to
every finding of its pattern — the same explanation is reproduced, never regenerated, per
system and per run. Instance grounding is **not** materialized in the graph: the concrete
risk-bearing elements are already asserted as `pair:hasEvidence`, and any sentence naming
them belongs to the presentation layer. (A `pair:mechanismNarrative` property that built
such a sentence by string concatenation inside the risk queries was removed on 2026-07-28
— glossary v1.2, decision F2.)

### 1.4 The executable side (`risk_*.rq`)

Each risk pattern has exactly one OQP. Structurally, every one of the 15 queries:

1. starts from an existing `pair:MotifMatch` and reads its bindings
   (`pair:hasNodeBinding/pair:matchedElement`) — so risk evaluation is always anchored to
   structure that a motif already recognised;
2. adds the applicability conditions: facet checks (data category), extra structural
   reachability via property paths, and control-absence via `FILTER NOT EXISTS`
   (**12 of the 15** carry at least one, at most two per query);
3. CONSTRUCTs a `pair:RiskFinding` carrying `pair:hasEvidence` (the matched elements),
   `pair:hasDerivedMechanism`, `pair:hasSatisfiedCondition`,
   `pair:hasCandidateRiskTaxonomyEntry`, `pair:hasSuggestedControl`,
   `pair:generatedByRiskPattern`, and `pair:findingStatus "candidate"`.

The **three queries with no control-absence check at all** — data and model poisoning,
supply chain compromise, vector and embedding weakness — are unclearable by design, and
correctly so: they rest on provenance and vetting, which are non-technical controls with no
runtime shape, so no structural escape exists to write. The answer there is finding-level
triage through `pair:findingStatus`, not a query escape. Never conflate the two.

**Clause order is load-bearing.** rdflib has no query optimizer: it evaluates a BGP in
textual order and applies a FILTER to its whole group. Every risk query is therefore written
as `WHERE { { structure … FILTER NOT EXISTS … } curated metadata . OPTIONAL … BIND … }`. The
metadata block is a small cross product (18–36 rows) and hoisting it to the top multiplied
every structural join, property path and absence check by that factor — roughly 3× runtime
for identical results. Keep the structural braces too: without them the filters leave that
group and fire once per metadata row again.

**`pair:generatedByRiskPattern` is what routes a finding to its mitigation rewrite.** The
same control answers several patterns while a rewrite is written against one vulnerable
shape, so rewrites are keyed on (control, risk pattern) — see §1.6.

Conditions are **reusable constituents** and are shared across patterns where the
structural gate is genuinely the same. Example, documented in the file itself:
`pat:SensitiveDataRetrievalExposureRiskPattern` (anchored to LLM02) reuses
`pat:VectorEmbeddingWeakness_RetrievalCondition` (defined for LLM08), because the
retrieval-specific route to sensitive-information disclosure is exactly that gate. This is
a deliberate, commented exception, not drift.

### 1.5 Cross-taxonomy mappings

`ontology/taxonomy/taxonomy_mapping.ttl` is organised in explicit provenance tiers:

- **Section 1 — upstream-verified**: taken from IBM AI Atlas Nexus SSSOM mapping sets
  (`ibm2owasp.tsv`, `mit-ai-risk-repository_ibm-risk-atlas.tsv`, `owasp_asi2owasp_llm.tsv`,
  `ibm2nistgenai.tsv`), predicates preserved exactly as curated upstream
  (`ManualMappingCuration`, confidence 0.95).
- **Section 2 — project curation**: no upstream row exists; each mapping carries a stated
  rationale.
- **Section 3 — risk→control grounding** over the MIT mitigation layer, project curation.

Keeping this file separate means a reader can inspect the alignment without going through
any particular risk pattern.

### 1.6 Controls

Two distinct things are visible on a finding, and the distinction matters:

- **`pat:Control_*` (12)** — the project's own actionable control catalogue, the only
  vocabulary that appears in `pair:suggestedControl`. Each is classified technical or
  non-technical (`pair:controlNature`), and **5 of the 12** carry `pair:realizedByMotif`,
  linking a control to the motif(s) that could structurally realize it (e.g.
  `pat:Control_Guardrails → pat:GuardrailsMotif`). That link is what turns a bare label
  into a situated "insert this structure" suggestion.
- **`mitctrl:*`** — MIT control *families*, reached from a finding through its taxonomy
  entries (`nexus:hasRelatedControl`) as an **evidence layer**, no longer as peer
  suggested controls. Classifying a whole taxonomy family as one technical/non-technical
  control was an altitude error that has since been removed.

Both the classification axis and the `realizedByMotif` assignments are project expert
curation — a reviewed first pass, and explicitly candidate associations (see §6.8).

### 1.7 Applying a control is a registered rewrite, not code

Added since this document was first written. A `pair:MitigationApplication` implementation
restates the vulnerable shape its `pair:mitigatesRiskPattern` found and CONSTRUCTs the step
that interrupts it, bound to the elements the finding already cites — so nothing guesses
which evidence element is which, and the knowledge of where a control belongs lives beside
the rule that raised the finding. **9 rewrites are registered over 8 `.rq` files** in
`ontology/patterns/implementation/mitigation/`, run on demand through `apply_control()` and
scoped to one finding by `initBindings`. Inserted IRIs are derived from the elements they
screen, so re-applying is a no-op.

**The output type is the safety catch.** The pipeline asks only for `pair:MotifMatch` and
`pair:RiskFinding`, so a rewrite never runs inside an assessment. If it did, every finding
would mitigate itself and none would ever be reported;
`test_a_mitigation_rewrite_never_runs_during_an_assessment` enforces it.

**Rewrites are keyed on (control, risk pattern), never on the control alone.** The same
control answers several patterns — output validation is suggested by improper output
handling, sensitive disclosure and system prompt leakage — while a rewrite is written
against one vulnerable shape. Keyed on the control alone, each of those findings offered an
Apply button that ran the wrong rewrite, found its own screen already in place and reported
"already in place on this path". Findings therefore carry `pair:generatedByRiskPattern`, and
a control with no rewrite *for that finding's pattern* reports `applicable: false` rather
than offering a button that does nothing.

**Control motifs are sized to the risk, not to the vocabulary.** `GuardrailsMotif` is 8
nodes and 8 edges; prompt injection needs an input screen and nothing else, so
`InputScreeningMotif` and `OutputScreeningMotif` are 3 nodes and 2 edges each and nest
inside it. A control whose `realizedByMotif` points at a motif far larger than the risk it
addresses is not actionable — that motif is what the canvas offers to insert.

Mechanics in full: `docs/reference/mitigation_and_gap_mechanics.md`.

---

## 2. Roles creation — an honest account

Roles are the semantic bridge that makes motifs reusable across heterogeneous systems, and
they are also **the weakest-grounded layer of the knowledge base**. This section states
exactly how they came to exist.

### 2.1 What a role is, technically

- `pair:PatternRole` is an `owl:Class` that is `rdfs:subClassOf skos:Concept`; the 97
  roles are *instances* of it, assigned to architecture elements via `pair:playsRole`
  (domain `rdfs:Resource`, i.e. any element).
- Roles form a hierarchy through `pair:subRoleOf`, an `owl:TransitiveProperty`, under four
  roots: `pair:ProcessingStep`, `pair:ControlStep`, `pair:ResourceRole`, `pair:UserInput`.
- Queries match with `pair:playsRole/pair:subRoleOf* pair:SomeRole`, so tagging a more
  specific sub-role (`pair:PublicUserInput`) still satisfies a motif asking for the parent
  (`pair:UserInput`). This is what lets one motif match two systems annotated at different
  levels of specificity.
- **Parent choice is load-bearing.** Because queries walk up from a *general* role, a
  precise role parented to an abstract top-level role is inert: tagging an element with the
  obviously-correct term then silently prevents the motif from matching. This bit
  `RewrittenQuery` and `RerankedContext`, which now sit under `UserInput` and
  `RetrievedContext` respectively.

### 2.2 How they were actually created

**No external role vocabulary was adopted.** There was no starting taxonomy, no imported
role ontology, no mapping exercise. The vocabulary was produced by reading two kinds of
source material and extracting the distinctions they implied:

- **the risk sources** (OWASP LLM Top 10) — read to find which process/component
  distinctions a risk statement actually depends on. `pair:RetrievalStep` exists as a
  distinct role from `pair:ProcessingStep` because LLM08 talks specifically about
  retrieval and embedding weaknesses;
- **the architecture pattern catalogs** (Martin Fowler's GenAI patterns; Mercari's ML
  System Design Patterns) — read to enumerate the components each pattern is built from:
  a query-rewriting step, a vector store, a reranker model, a serving image, a prediction
  queue.

That extraction step — turning prose into the actual `pair:PatternRole` set — was done
**LLM-assisted, with human review**, not derived from a formal ontology and not validated
against an external standard. Roles were then added and adjusted **bottom-up as motifs and
queries needed them**: when a motif could not distinguish two elements, a role was
introduced.

### 2.3 The retro-fitted provenance, and what it does not mean

**Every role traces to an origin, in one of three ways** (R6, enforced by
`test_every_pattern_role_states_its_provenance`). Measured 2026-08-30 over 97 roles:

| How the role is grounded | Roles |
| --- | --- |
| States its own `dct:source` | 50 |
| Carries a SKOS mapping into an external vocabulary (DPV, DPV-AI, AIRO, Tool4Boxology) | 35 |
| Neither — inherits through `pair:subRoleOf` from a parent that has one | 12 |
| **Roles with no traceable origin** | **0** |

The 50 own-source roles anchor to Martin Fowler's gen-AI patterns (14 directly), the Mercari
ML System Design Pattern pages, the OWASP LLM Top 10, and — for the agentic additions — the
OWASP ASI entries (13 roles across ASI02, ASI06 and ASI07).

The third row is deliberate rather than an omission: a role introduced to *refine* another
states no source because its grounding is the role it specializes, and `pair:subRoleOf`
already says which one that is. A prose note saying "it inherits the grounding of
`pair:ExternalDependency`" duplicated the triple beside it, and only the triple can be
checked — so the test walks the chain instead.

Read this carefully, because it is easy to over-claim:

- The `dct:source` provenance was **added after the roles existed**, during the v1.1/v2
  consistency pass — it records *what a role was read from or anchored to*, not that the
  term was imported from a published vocabulary.
- **No role URI is an external URI.** All 97 live in the `pair:` namespace.
- There is still **no `skos:ConceptScheme` for roles** (unlike the facets, which are proper
  SKOS schemes), and the hierarchy uses the custom `pair:subRoleOf` rather than
  `skos:broader`.
- The 35 SKOS mappings are a genuine improvement over the earlier state, in which no role
  was formally mapped to anything. They are still **project-asserted alignments**, reviewed
  once, not adopted from an upstream mapping set — and they cover about a third of the
  vocabulary, so the layer as a whole remains the weakest-grounded part of the knowledge
  base (§2.4).

### 2.4 Consequences to be aware of

1. **Coverage is exactly as wide as the sources that were read.** That set has since grown
   — agentic tool use, multi-agent delegation, agent memory and human-in-the-loop review all
   have roles now, extracted from the OWASP ASI entries the same way. The limitation is
   unchanged in kind: anything no source describes still has no role, and adding one is a
   curation act, not a discovery.
2. **Circularity risk.** Roles were partly defined so that motifs would bind. A motif
   matching an architecture therefore demonstrates less independent validation than it
   appears to: the annotator, the role set, and the motif were all shaped by the same
   reading of the same catalogs.
3. **The annotation burden and its variance are unmeasured.** Assessment quality depends
   entirely on the modeler picking the right roles (§6.6), and there has been **no
   inter-annotator agreement study** — two people annotating the same architecture may
   well produce different findings.
4. **`pair:playsRole` has domain `rdfs:Resource`**, so nothing prevents a role intended
   for data being attached to a process. Nothing checks role/class coherence beyond the
   motif queries' own `pair:expectedClass` constraints.

### 2.5 What would actually fix this

Declare a proper `skos:ConceptScheme` for roles with `skos:broader` alongside (or instead
of) `pair:subRoleOf`; extend the SKOS mappings past the 35 roles that now carry one, to
every role with a genuine external counterpart; and run an empirical study — annotate unseen
architectures with independent annotators and measure both agreement and whether the role
set is sufficient without extension.

The mapping half is **partly done**: 35 roles are now aligned to DPV, DPV-AI, AIRO and
Tool4Boxology, where §2.3 previously recorded none at all. The scheme and the study are not.

---

## 3. Motif curation

### 3.1 Sources

31 motifs. **Every one carries `pair:derivedFrom`** (R6); 27 also carry a `dct:source`.
Measured 2026-08-30:

- **13 GenAI motifs** derived from Martin Fowler, *Emerging patterns for generative AI
  systems*: Direct Prompting, RAG, Embeddings, Hybrid Retriever, Query Rewriting, Reranker,
  Guardrails, Evals, Fine-Tuning, plus four refinements introduced later — Information
  Retrieval, Vector-based Information Retrieval, Input Screening, Output Screening. Those
  four state `pair:derivedFrom` alone, because they refine a shape the catalogue already
  describes rather than adding one it does not.
- **13 classic ML/MLOps motifs** from the Mercari ML System Design Pattern catalog, each
  sourced to the specific pattern page: serving (Synchronous, Asynchronous, Batch,
  Prep-pred, Multi-stage), training (Batch training, Pipeline training), lifecycle
  (Train-then-serve, Training-to-serving), operation (Prediction log, Prediction
  monitoring, Model load, Model-in-image).
- **4 agentic motifs** sourced to the OWASP Agentic (ASI) entries whose structural signature
  they express: Tool-Using Agent, Agent Memory Loop, Agent Delegation, Human Oversight.
- **1 project-curated motif**: `pat:ExternalDependencyMotif`, sourced as expert curation
  scoped by OWASP LLM03 (supply chain) — no external catalog defines it.

Two properties of the set shape how to read any count over it:

- **Motifs nest, deliberately.** The library is not an antichain — a smaller motif is often
  a subgraph of a larger one and always co-matches with it (Vector-IR inside RAG; Input and
  Output Screening inside Guardrails). Match counts therefore measure *structural coverage*,
  never "how many different things the system does".
- **A control motif is not a safe motif.** Guardrails and Evals are what absence-of-control
  conditions look for, so their presence suppresses findings on that path — but Guardrails
  is itself the declared gate for improper output handling and system-prompt leakage, since
  a screened path still carries the hidden instructions and the unvalidated output it
  screens. Adding a control motif means re-assessing the amended architecture, not assuming
  a clean sheet.

### 3.2 The two layers, and why they can drift

Every motif exists twice, on purpose:

1. **Declarative shape (ODP)** in `motif.ttl`: a `pair:GraphMotif` composed of
   `pair:PatternNode` instances (each with `pair:expectedClass`, a BEAM class, and
   `pair:expectedRole`, a pattern role) wired by `pair:PatternEdge` instances (each with
   `pair:sourcePatternNode`, `pair:targetPatternNode`, `pair:patternPredicate` — typically
   `beam:use` / `beam:produce` / `beam:inform`).
2. **Executable matcher (OQP)** in `implementation/match_*.rq`: a SPARQL `CONSTRUCT` that
   finds the same shape in an architecture graph and materializes a `pair:MotifMatch` with
   one `pair:NodeBinding` per pattern node.

**Nothing compiles (1) into (2).** The ODP is metadata for humans, the catalogue, and the
UI; the OQP is what actually runs. They are kept in sync by hand, which has historically
been the single largest source of silent bugs (a risk query looking for a
`pair:bindsPatternNode` name that the matcher no longer CONSTRUCTs simply yields zero
findings, with no error). `python/tests/test_library_consistency.py` now mechanically
cross-references the two layers to catch that class of drift.

### 3.3 The curation loop in practice

1. Pick a pattern from a source catalog and decide whether it is one motif or several
   (the relationship is m:n — one design pattern induces several motifs; one motif recurs
   in several patterns).
2. Name the pattern nodes and choose each node's expected BEAM class and role; add roles
   to `pair_ai_pattern.ttl` only if an existing role cannot express the distinction.
3. Write the ODP in `motif.ttl` with `dct:source` + `pair:derivedFrom`.
4. Write the OQP, register it as a `pair:PatternImplementation` with
   `pair:implementsMotif`, `pair:implementationPath`, and
   `pair:producesOutputType pair:MotifMatch`.
5. Run the assessment on the example architectures; inspect what binds and what does not.
6. Adjust — and this is where most of the real work happens (§3.4).

### 3.4 Motifs get corrected when they don't match reality

Two recent, concrete corrections illustrate the curation standard:

- **RAG motif** — the earlier version required a stand-alone query-embedding leg
  (`RAG_QueryEmbeddingStepNode` → `RAG_QueryVectorNode`) and had retrieval read a vector
  *index*, with the result that retrieval was structurally **disconnected from the user
  query** and the embedding output dead-ended. It matched almost nothing real. The motif
  now follows Fowler faithfully: retrieval is **driven by** the user query
  (`?retrievalStep beam:use ?query`) and reads a vector store *or* index; offline document
  embedding/indexing is modelled separately by the Embeddings motif. Retrieved context may
  pass through intermediate steps (reranking, aggregation) before prompt construction —
  the context edge is path-tolerant, `?retrievedCtx (^beam:use/beam:produce)* ?ctxForPrompt`.
  A consequence stated in the motif comment: because retrieval is query-driven over a
  vector store, any RAG graph also satisfies the Vector-based Information Retrieval motif.
- **Guardrails motif** — the matcher additionally demanded that the generation step consume
  the *same* user prompt object that the input guardrail consumed, which fails for the
  common design where the guardrail produces a sanitized prompt. That over-constraint was
  removed, making the motif flow-agnostic about what the generation step reads.

The rule this expresses: when a motif does not match architectures that plainly exhibit
the pattern, the motif is wrong, not the architecture. The declaration and the `.rq` are
corrected together, and the example assessments are re-run so any change in findings is
explained.

### 3.5 Motifs read structure only (R2)

A motif matches **roles + flow relations**, never facets. This is verified mechanically,
not merely asserted: no query in `implementation/match/` references
`pair:containsDataCategory` or any `facet:` property — re-checked 2026-08-30, still zero. (An earlier R2 leak in `match_embeddings.rq`, which filtered on a data
category, has been removed.) Keeping motifs facet-blind is what keeps them risk-neutral
and reusable: retrieval over public data and retrieval over sensitive data are the *same*
structure, and only the risk stage is allowed to care about the difference.

### 3.6 Process typing never decides whether a motif matches

Unified 2026-08-06. Every step-node class check in every match query is
`?step a/rdfs:subClassOf* beam:Process` — the same shape as the library's role idiom,
`pair:playsRole/pair:subRoleOf*`. It walks the class hierarchy already present in the loaded
graph, so no reasoner is involved, and `beam:Process`, `beam:Infer`, `beam:Transform`,
`beam:Train` and `beam:Generate` all bind identically.

Before this, three conventions coexisted, and the consequence was severe rather than
cosmetic: a leaf-typed agent matched *zero* agentic motifs while an identical generic-typed
one matched them all. **Never write a bare `a beam:Infer` in a query** —
`test_queries_check_process_typing_one_way` fails on it, and
`test_process_typing_does_not_change_what_matches` proves the equivalence end to end.

The **role is the discriminator**; the class is only a coarse process/resource guard.
`shacl/annotation_guidance.ttl` still warns when a step carries no process-family class at
all, since that genuinely cannot bind.

---

## 4. Ontology model: modules, reuse, alignment

### 4.1 Module map

| Module | Files | Content |
| --- | --- | --- |
| **Architecture** | `ontology/core/beam_core.ttl`, `ontology/alignments/*` | BEAM: `beam:System`, `beam:Process` (+ `Transform`/`Infer`/`Train`/`Generate`), `beam:Resource` (+ `Data`/`Symbol`/`Model`), `beam:Agent`, `beam:Task`; flow predicates `beam:use`, `beam:produce`, `beam:inform` |
| **Risk** | `ontology/core/beam_core_risk.ttl`, `ontology/taxonomy/*` | BEAM Risk (built on AIRO) + OWASP/IBM/MIT taxonomies + cross-mappings |
| **Pattern** | `ontology/core/pair_ai_pattern.ttl`, `ontology/patterns/*` | Roles, data categories, motif/risk-pattern/finding vocabulary, the two libraries, the control layer |
| **Facets** | `ontology/facets/*` | SKOS characterization schemes + their attachment properties |
| **Context** | `ontology/context/*`, `external/sbpmn/sbpmn_2.0.ttl` | The business layer bridge: `pair:refinedBy`, `pair:businessFollows`, and two registered derivations (§7) |
| **Contract** | `shacl/*` | Three shape sets answering three different questions (§4.6) |

Stored permanently: the modules above (this is the reusable **AI-RKG**). Not stored:
per-system architecture graphs, per-organisation process models, and their findings — those
are assessment input/output and land in `outputs/`.

### 4.2 BEAM is canonical; external vocabularies enter only through adapters (R5)

BEAM is the internal model, and it specializes the published **Boxology / Tool4Boxology**
vocabulary; both anchor to easy-ai. No tool-specific term ever enters `beam_core.ttl`.
External vocabularies enter through two things and nothing else:

1. an **alignment adapter** in `ontology/alignments/` using `rdfs:subClassOf` /
   `rdfs:subPropertyOf`;
2. a **normalizer** that materializes BEAM triples at ingestion
   (`python/src/airiskkg/t4b_import.py`).

`tool4boxology_alignment.ttl` maps the export's edge directions
(`t4b:inputRoleParticipatesInProcess ⊑ beam:usedBy`,
`t4b:outputRoleParticipatesInProcess ⊑ beam:produce`) and its classes to BEAM leaves, with
each judgement call flagged in-file as a `DESIGN DECISION (review)` — e.g. `t4b:Deduce ⊑
beam:Infer`, `t4b:Embed ⊑ beam:Transform`. The normalizer additionally handles verified
export quirks: lowercase type URIs (`t4b:transform` vs `t4b:Transform`), the
`patternProcess`/`hasProcess` divergence, instances multi-typed with `t4b:Component`, and
the misspelled `t4b:StatisticModel`. It also converts `t4b:DesignPattern` groupings into
`dct:conformsTo` provenance pointing at Boxology elementary patterns — feeding motif
derivation provenance rather than the matching layer.

`dpv_alignment.ttl` is deliberately narrow: `beam:Agent rdfs:subClassOf dpv:Entity`, and
nothing else. DPV's breadth is used where it belongs — the facet layer — and BEAM's
structural classes are aligned to Tool4Boxology instead, which is the closer domain fit.
The file also records what was checked and *not* aligned (`dpv:Agent`, `ai:AIAgent`) and
why, so the decision is not silently re-litigated.

### 4.3 Two reuse mechanisms, kept distinct (R3)

- **Structural reuse** — `owl:imports` / subclassing plus `dct:source`: Boxology → BEAM,
  AIRO → BEAM Risk, DPV for entities and identifiability.
- **Vocabulary reuse** — the project defines its own SKOS scheme and links out with
  `skos:exactMatch` / `broadMatch` / `closeMatch`. **DPV is the alignment target**, because
  it is resolvable and third-party checkable.

**OECD is absorbed, not represented** (decided 2026-08-03). It is cited as a `dct:source` on
the facet schemes; there is **no `oecd:` concept scheme and there must not be one**. OECD
publishes no resolvable concept URIs, so any `oecd:X` would be a concept we wrote from the
same reading that produced the facet value — the `exactMatch` would be true by construction
and prove nothing, while doubling the concept count. Say "informed by OECD", not "aligned to
OECD". Adding document loci would change this, but loci must be read from the source, never
inferred.

**TÜV AI.ST is excluded**, not on hold — licence verified closed 2026-08-03. The v0.1
whitepaper carries "© TÜV AI.Lab GmbH" with no licence grant and the PDF is marked
"CONFIDENTIAL. DO NOT SHARE"; publicly downloadable ≠ reusable. Do not mint TÜV concepts,
reproduce its tables, or add TÜV mappings. Citing it in prose is normal scholarship and
remains fine. Reopen only on written permission from the vendor.

**DPV is referenced, never copied.** `facet:hasPersonalDataCategory` and
`facet:hasIdentifiabilityLevel` take DPV URIs directly as values (verified against DPV
v2.3), rather than mirroring DPV concepts locally.

### 4.4 OWL class vs SKOS concept (R1)

OWL classes are used only for what is instantiated and traversed by queries — the BEAM
elements. Everything that is merely *assigned* as a classification value is a SKOS concept:
pattern roles, data categories, and every characterization facet. A facet value is never
instantiated as a node in an architecture graph.

### 4.5 The facet layer

`ontology/facets/facet_properties.ttl` declares the attachment properties; the schemes
live beside it:

| Property | Domain | Values |
| --- | --- | --- |
| `facet:hasDataProvenance` / `hasDataDynamism` / `hasDataRights` | `beam:Data` | `data_facets.ttl` (OECD-derived, with `skos:closeMatch` to DPV where a counterpart exists) |
| `facet:hasPersonalDataCategory` / `hasIdentifiabilityLevel` | `beam:Data` | DPV URIs directly |
| `facet:hasAutonomyLevel` | `beam:System` | `autonomy.ttl` |
| `facet:hasDomain` / `hasPurpose` / `hasDeploymentSetting` | `beam:System` | `context.ttl`, DPV purposes |
| `facet:hasImplementationType` | `beam:Model` | `implementation_type.ttl` |
| `facet:hasTaskCategory` | `beam:Task` | `task.ttl` |
| `pair:containsDataCategory` | `beam:Data` | `pair:DataCategory` (7), in the **pattern** module |

The Data Category facet sits in the pattern module rather than the facet module for a
substantive reason: its values are **propagated along data flow by registered queries**
(R8, derived facts), whereas every other facet is a base fact annotated by the modeler.
Ranges are kept at `skos:Concept` deliberately — the intended scheme is stated in the
property comment rather than enforced with OWL axioms.

**There is no "Personal" data category, and there must not be one.** Personal data is
expressed with DPV concepts through `facet:hasPersonalDataCategory` (R3), never mirrored
into `pair:DataCategoryScheme`.

Concept counts, measured 2026-08-30: **35** concepts across the project's own facet
namespaces — task 20, data 11, autonomy 4. `context.ttl` declares the Domain and Purpose
schemes as shells whose values are taken from DPV directly; `implementation_type.ttl` is
likewise a declared scheme with no project concepts in it yet.

**Facets reach the assessment two ways, and only two** (decided 2026-08-11):

1. **Bridge** — a protection-relevant facet value is mapped into a `pair:DataCategory` by a
   registered propagation query, and the category then travels along the flow like any
   other. Live for `facet:hasPersonalDataCategory` → `SensitiveInformation` and
   `facet:hasDataRights dataf:Proprietary` → `ConfidentialInformation`.
2. **Direct read** — an applicability condition tests the facet on a *bound element of the
   match* (R2), positively (R10). No propagation is involved.

**Facets are never propagated as facets.** R8 makes Data Category the one facet that is also
derived; propagating others would break that line and force every condition to read two
propagating vocabularies. Concretely: content-borne properties (sensitivity,
confidentiality) bridge and travel; element-intrinsic properties (provenance, dynamism) do
not, because an element derived from observed data is *derived* data, not observed data —
copying the label downstream would assert something false. "What was this derived from?" is
answered by the `prov:Derivation` chain instead, which is exact.

R7 is respected throughout: **Task ≠ Capability ≠ Application Type** are three separate
axes and are never merged.

### 4.6 Three SHACL shape sets, three different questions (R4)

| File | Question | Severity |
| --- | --- | --- |
| `shacl/architecture_input_contract.ttl` | Is this graph acceptable? | Violations |
| `shacl/assessment_output_contract.ttl` | Are emitted findings well formed? | Violations |
| `shacl/annotation_guidance.ttl` | Will this annotation actually match anything? | `sh:Info` / `sh:Warning` only |

The **input contract** makes explicit what a submitted graph *must* (Violation) and *should*
(Warning) represent for candidate findings to be meaningful — at minimum one `beam:System`,
and every `beam:Process` participating in at least one `beam:use`/`beam:produce`. This is
the operational counterpart of the Open World Assumption: absence-of-control checks are only
defensible if the contract states what the submitter was expected to model.

**Every guidance shape is `sh:Info` or `sh:Warning`, never `sh:Violation`**, so guidance can
never change whether a graph conforms — a test enforces that. It rides along with the input
contract in the webapp and in `validate_graphs.py`.

---

## 5. The assessment pipeline

### 5.1 Conceptual stages

**Stage 1 — Input and role annotation.** The architecture is expressed as `G = (V, E)`:
nodes are Resources (something that *is*) and Processes (something that *happens*),
gathered under a `beam:System`; edges are `beam:use` (process consumes resource),
`beam:produce` (process creates resource), and `beam:inform` (process → process ordering,
no resource transfer). Each element then receives one or more **pattern roles**, and
optionally **characterization facets**. Until roles are attached the graph is just a data-flow
diagram — the roles are what makes it matchable.

**Stage 2 — Motif matching (structure only).** For each motif, its OQP is executed over
the graph. SPARQL Basic Graph Pattern evaluation *is* subgraph-homomorphism search, so
executing the query enumerates **all** solution mappings from the motif's abstract pattern
nodes to concrete elements. A mapping survives when both hold: **role compatibility** (the
element's role is the required role or transitively a sub-role, via `pair:subRoleOf*`) and
**structural compatibility** (the flow relations hold, with path-tolerance where the motif
declares it). Each solution is recorded as one `pair:MotifMatch` with explicit
`pair:NodeBinding`s — the traceability record used downstream.

**Stage 3 — Risk identification.** What was deliberately separated now meets: structure +
roles (Stage 2) and context/facets (Stage 1). For each risk pattern whose motif matched,
its applicability conditions are evaluated over the *bound* elements — facet checks,
additional reachability, and absence-of-represented-control. If all conditions hold, a
candidate finding is instantiated carrying the pattern's mechanism, taxonomy links, and
controls — selected from curated knowledge, never invented at assessment time.

**Stage 4 — Output.** A structured record per finding: evidence pointers, mechanism,
taxonomy anchors, suggested controls, which conditions were satisfied, and
`pair:findingStatus "candidate"`. The aggregate is a list of structural dispositions for
human review — not a score, not a pass/fail verdict.

```
 architecture graph + roles (+ facets)
              │
              ▼
   [1] facet propagation (fixed point)      ← derived data categories
              │
              ▼
   [2] motif matching  (roles + structure)  → MotifMatch + NodeBindings
              │
              ▼
   [3] applicability conditions             → facets, reachability, control absence
              │                                (closed-world over the submitted graph only)
              ▼
   [4] candidate risk findings              → evidence + mechanism + taxonomy + controls
              │
              ▼
        human assessor
```

### 5.2 What actually executes

`python/src/airiskkg/assessment_runner.py`, in order:

0. **Load** (`load_base_graph`) — BEAM core, BEAM risk, `imports.ttl`,
   `pair_ai_pattern.ttl`, the motif library, the risk pattern library, the control layer,
   every file in `ontology/facets/`, `ontology/taxonomy/`, `ontology/context/`, and
   `external/sbpmn/`, into one `rdflib.Graph`; then the submitted file(s) — an architecture,
   and optionally a business process model — are parsed into the *same* graph.
   **The knowledge base is parsed once per process** and copied per call
   (`_base_knowledge`); Turtle parsing was the largest single cost in every entry point.
   `load_base_graph()` still hands back a fresh writable graph, so never return the cached
   instance. Editing a `.ttl` in a live server needs `reload_knowledge_base()` — Flask's
   reloader watches Python only.
1. **Derive** (`_derive_facts`) — every implementation registered with
   `pair:producesOutputType pair:DataCategoryPropagation` **or**
   `pair:BusinessFlowDerivation` runs repeatedly until no new triple appears, capped at 20
   iterations. **Eight are registered** (measured 2026-08-30): untrusted content, content
   categories, generated content, personal data category, personal data rights, proprietary
   data, the business data bridge, and business flow.
   Untrusted-content taint takes anything under `pair:PublicUserInput` or
   `pair:RetrievedContext` as a root and flows along `beam:use`/`beam:produce`, stopping at a
   step under `pair:GuardrailStep` or at an element explicitly tagged
   `pair:TrustedContent`. Rationale: forgetting to hand-tag one derived element three hops
   downstream would silently suppress a finding.
   **A control barrier must be earned.** Widening the `content_categories.rq` barrier to
   output guardrails was right — a screened output inheriting the categories the screen
   exists to stop made inserting one *grow* the derived set. Adding pseudonymisation to it
   was wrong, and a test caught it: `dpv:PseudonymisedData` is a kind of `dpv:PersonalData`,
   so sensitivity must survive it.
2. **Match motifs** — every implementation with `producesOutputType pair:MotifMatch` runs
   once as a CONSTRUCT; results are merged back into the working graph so later queries
   can see them.
3. **Evaluate risk patterns** — every implementation with
   `producesOutputType pair:RiskFinding` runs the same way, after step 2 because it reads
   the matches.
4. **Serialize** — `inferred_annotations.ttl`, `motif_matches.ttl`, `risk_findings.ttl`,
   and `combined_assessment_graph.ttl` into an auto-numbered `outputs/<run>/output_N/`, so
   repeated runs never clobber each other.

**Nothing is hardcoded in Python.** Queries are discovered from the graph itself through
`pair:producesOutputType` + `pair:implementationPath`; adding a motif or risk pattern means
adding a `.rq` and registering it in Turtle. Prepared queries are cached
(`_prepared_query`); SPARQL parsing dominated runtime, and caching takes a full assessment
from roughly two seconds to a tenth of a second.

**rdflib's SPARQL compiler is not thread-safe.** pyparsing keeps global parser state, so two
threads compiling queries at once corrupt it, surfacing as
"`Param.postParse2() missing 1 required positional argument`". Compilation is serialized
inside `_prepared_query`; keep it there rather than locking in a caller, and never parse
SPARQL off the main thread outside that function.

### 5.3 A run records what it ran on

`build_export` mints a `prov:Activity` and, beside it, **one `prov:Entity` per input** — the
submitted graph, the knowledge base, and the business process layer when one is submitted —
each carrying a `pair:contentFingerprint`, plus `pair:sourceRevision` on the library when a
repository is present (the container has none). Inputs are entities rather than properties on
the activity precisely so that adding a third input costs a call rather than a new predicate.

An entity's IRI *is* its fingerprint, so two runs over the same input reference one node.
`pair:assessmentFingerprint` on the activity answers "same question?"; the activity IRI stays
a fresh UUID, because two runs at different times genuinely are two events and collapsing
them would assert they were one. Graph fingerprints canonicalize blank nodes and sort
N-Triples before hashing — never `to_isomorphic(...).graph_digest()`, whose value is
rdflib's own and would break comparability across an rdflib upgrade.

### 5.4 Entry points

- **CLI** — `airiskkg assess <graph.ttl> [more.ttl ...] [--output-dir DIR]`.
- **Web workbench** — `airiskkg serve`: visual builder, Turtle editor, BPMN process canvas,
  Tool4Boxology import, SHACL validation, and in-memory assessment rendered by OWASP
  category (see `docs/user_guide.md`).
- **Tool4Boxology import** — `python/scripts/normalize_t4b.py` and the workbench endpoint,
  both via `t4b_import.py`.

### 5.5 What a run currently produces

Measured 2026-08-30 by running the pipeline. `test_propagation.py` pins the four
single-graph rows and asserts that **every bundled example has a baseline** — adding one
without a number would otherwise leave it unwatched.

| Example | Motif matches | Findings |
| --- | --- | --- |
| RAG chatbot (Onyx / Danswer) | 14 | 22 |
| Minimal graph RAG | 3 | 7 |
| Meter anomaly scoring (ML serving) | 4 | 1 |
| IT support agent (agentic) | 4 | 8 |
| Energy scene: graph RAG + meter anomaly + the business process | 7 | 8 |
| IT service desk scene: the agent + its business process | 4 | 9 |

The RAG chatbot is the broadest graph in the repository: 14 matches over **8 distinct
motifs** (Direct Prompting, Embeddings, External Dependency, Information Retrieval, Query
Rewriting, Reranker, RAG, Vector-based IR). Matches are `pair:MotifMatch` instances, not
distinct motifs — nested motifs co-match by design, so the number is structural coverage.

**Never name an example file in a test.** These get renamed — `onyx_danswer.ttl` became
`onyx_danswer_rag_chatbot.ttl` became `ony_rag_chatbot.ttl` became `onyx_rag_chatbot.ttl`
inside two days — and each rename broke suites for reasons unrelated to what they test.
Resolve one through `tests/conftest.py::example_path(NAMESPACE)`: renaming a file is a
filing decision, changing a namespace is a modelling one.

**An unannotated graph matches nothing**, however well drawn. That is not a failure of the
pipeline but the method's central dependency made visible (§6.6). The raw Tool4Boxology
export that used to demonstrate this has since been removed from the bundled set, which is
now four annotated architectures plus two process models.

---

## 6. Current limitations

Each item below was verified against the repository on 2026-08-30, not carried over from
older notes.

**6.1 The characterization facet layer is only partly consumed.** Two facets now reach the
assessment, both by the bridge route (§4.5): `facet:hasPersonalDataCategory` and
`facet:hasDataRights`, read by three propagation queries. Autonomy, provenance,
identifiability, dynamism, domain, purpose, deployment setting, task and implementation type
remain modelled and read by nothing. **No applicability condition reads a facet directly**
— the second of the two sanctioned routes is declared but unexercised. So the "structure +
context" story is now partly delivered rather than half-promised, and the untouched
dimensions are still an enabler rather than a capability.

**6.2 Derived facts have grown, and their reach is still structural.** Seven data-category
derivations now run to a fixed point where there was one. But propagation still only covers
what is structurally derivable — a `beam:Data` node labelled "internal HR records" with no
distinctive role and no facet stays untagged unless a human tags it, or unless a business
process model says something about it. `pair:PromptInstruction` and several other categories
are still hand-tagged everywhere they appear.

**6.3 ODP and OQP are synchronized by hand.** No compiler turns a motif declaration into
its query. `test_library_consistency.py` catches identifier drift mechanically, but
semantic divergence (a query that is stricter or looser than its declaration) is only
caught by reading both.

**6.4 The role vocabulary is unvalidated and partly circular.** See §2.4: no external
grounding by URI, no SKOS scheme, no inter-annotator agreement study, and role granularity
was shaped by what motifs needed to bind.

**6.5 Example and test debt — resolved, and now enforced.** Every example the repository
ships lives in `ontology/example/` (four architectures) and `ontology/example/context/` (two
process models); confidential and NDA-covered graphs live in the gitignored
`ontology/example_local/`, which nothing in the test suite or the shipped library may read
— a fresh clone has to pass, and `test_private_examples.py` enforces that plus the ignore
rule, the `.dockerignore` allow-list, and that a WSGI app neither lists nor serves the
folder. `.dockerignore` is an **allow-list** and must stay one: `COPY . /app` once shipped an
NDA-covered directory because `.gitignore` and `.dockerignore` are unrelated files and nobody
updated the second.

**6.6 Assessment quality is bounded by annotation quality.** The method has no way to
recover a role the modeler did not assign. A perfectly drawn diagram with no
`pair:playsRole` produces zero findings.

Process typing no longer contributes to this (§3.6) — any class under `beam:Process` binds
identically, so the old trap of typing an LLM call `beam:Process` instead of `beam:Infer` is
gone. What remains is the **process/resource split** (a resource typed as a process cannot
bind a step node, and vice versa) and, above all, **role choice**, including which parent a
role sits under.

**6.7 Risk coverage is OWASP-shaped.** 15 risk patterns anchored to the OWASP LLM Top 10 and
the ASI entries cover **14 of 31 motifs**. The 17 uncovered motifs are almost entirely the
classic ML/MLOps set — Synchronous/Asynchronous/Batch/Multi-stage/Prep-pred prediction,
Batch and Pipeline training, Train-then-serve, Prediction logging and monitoring — plus
Evals, Hybrid Retriever, Information Retrieval, and the three control motifs, which exist to
be *found* rather than flagged. IBM Atlas, MIT and NIST entries are used as *link targets*,
never as sources of new patterns, so risks that OWASP does not name (fairness, environmental
cost, labour impact, most MIT domains) cannot currently be found even though they are
present in the loaded taxonomies.

The agentic gap has narrowed but is deliberately partial: only the four ASI entries with a
design-time structural signature are modelled (§1.1).

**6.8 The control layer is a curated first pass.** `pair:realizedByMotif` covers 5 of 12
controls and encodes an *assumed* structural mitigation, not evidence that inserting the
motif removes the risk. The same MIT control family can still be reached by a finding
along multiple paths (as `pair:suggestedControl`, through a `pat:Control_*`
`skos:relatedMatch`, and through the risk's taxonomy entry).

**A control clears a finding by being built, not by being asserted.** Fifteen risk queries
once carried `FILTER NOT EXISTS { pattern suggestedControl ?c . ?c beamr:associatedTo
?element }` as an escape. Nothing ever wrote that triple — not an example, not a rewrite,
not any code path — so the escape could not fire, and removing all fifteen left the output
byte-identical. It was worse than dead: it made a finding *look* falsifiable while the only
thing that could clear it was unreachable. Do not reintroduce an escape nothing can satisfy.

Three risk queries still have no structural check at all (§1.4), and are correct that way.
Others carry one on the structural half while the annotation half remains unclearable —
audit before assuming a given finding is actionable. Mechanics in full:
`docs/reference/mitigation_and_gap_mechanics.md`.

**6.9 Provenance obligations are partly unmet (R6).** Every mapping now has an
`sssom:Mapping` record with a semapv justification in
`ontology/taxonomy/provenance/mapping_provenance.ttl`, regenerated by
`python/scripts/generate_mapping_provenance.py`. It sits **below the runner's non-recursive
glob deliberately** — a finding must never cite its own provenance as support — so never
move it up a level. What is still unmet: **R6's own-SSSOM export has never been generated**;
the project consumes upstream sets rather than publishing one, and documentation should say
so rather than imply the export exists.

OECD facet concepts carry no `skos:exactMatch` because OECD publishes no resolvable concept
URIs; OECD is therefore **absorbed as a `dct:source`, not represented as a scheme**, and
there must be no `oecd:` namespace — any such concept would be one we wrote from the same
reading that produced the facet value, making the match true by construction. Say "informed
by OECD", never "aligned to OECD". DPV is the alignment target, because it is resolvable and
third-party checkable.

The facet layer is a **documented mixture**, not wholesale external grounding. Measured
2026-08-30 over its 35 concepts: **25 carry a SKOS mapping** into an external vocabulary
(overwhelmingly DPV), 10 carry none, and only 4 state a `dct:source` of their own — OECD is
cited once per **scheme** (autonomy, data facets, task) rather than per concept, so the
grounding is scheme-level and inherited, not term-by-term. Do not describe the layer as
"OECD/DPV-derived" without that qualification.

`task.ttl` second-level concepts and the Implementation Type scheme are curated placeholders
awaiting authoritative taxonomies. TÜV AI.ST remains excluded — licence verified closed
2026-08-03; cite it in prose, but mint no concepts and reproduce no tables.

**6.10 Findings are unranked and overlapping.** There is no severity, likelihood, or
priority; no de-duplication when several motifs trigger the same risk on overlapping
evidence (prompt injection fires from several matches on the RAG chatbot); and no
aggregation from findings to a system-level statement. A human reads a flat list.
`pair:findingStatus` is the triage extension point, and finding IRIs are deterministic so a
judgement survives a re-run — but nothing consumes a status yet.

**6.11 There is no evaluation yet.** No ground-truth dataset, no precision/recall against
expert assessment, no baseline comparison, no user study. Firing counts on four bundled
architectures and two process models are the only empirical signal, and those examples were
themselves annotated by the method's authors.

**6.12 Engineering constraints.** The whole knowledge base plus the submitted graphs are
loaded into a single in-memory `rdflib.Graph` per run, and **no OWL reasoning is performed at
any point** — alignments are additive and are *not* consumed during matching, by design, and
`owl:inverseOf` is declared as documentation only, which is why `pair:hasMotif` and
`pair:hasRiskPattern` must both be written by hand. The workbench builder offers
`beam:Data` / `StatisticalModel` / `SemanticModel` / `Symbol` and the five process classes,
but no `beam:Agent` or `beam:Task`. That no longer blocks agentic authoring — the bundled
agentic example uses none of either, since agentic motifs bind on roles and process classes
— but the two vocabulary terms remain unreachable from the builder.

**6.13 The business layer has one bridge and one honest gap.** Nothing in a process model
names an architecture element — that is the point, since the analyst does not know them — so
`business_data_bridge.rq` maps **by role**, onto the refined system's `pair:UserInput` and
`pair:PredictionRequest` elements. Where a system has several, all of them are reached
whether or not the declared data actually flows to each. A `prov:Derivation` records
which business annotation produced which category so a modeller can disagree with it, but the
mapping is not element-precise and cannot be. `.bpmn` XML import does not exist: the layer is
authored in Turtle or through the canvas, while a real process model usually starts life in
Camunda or Signavio.

---

## 7. The business context layer

Added on `feature/bpmn-business-context` and absent from every earlier revision of this
document.

### 7.1 Why it exists

A sparse architecture graph fires in every direction, because almost every applicability
condition is either satisfied or unfalsifiable when the graph says little. The missing
information is rarely architectural: whether the data reaching a scoring step identifies a
household is known by the process owner, not by whoever drew the components — and the
artefact the process owner already maintains is a process model. The layer exists to let a
non-RDF-writing analyst state facts that change findings, in a notation they already use.

### 7.2 The join is refinement, never subsumption

```
business (sBPMN 2.0)  --pair:refinedBy-->  architecture (BEAM)  --pair:playsRole-->  patterns
```

**A `bpmn:activity` is not a `beam:Process`** and must never be aligned to one. Every match
query types its step node as `?step a/rdfs:subClassOf* beam:Process` (§3.6), so subsuming
activities under it would make every business activity a candidate motif node — and the input
contract, which requires each `beam:Process` to use or produce a resource, would reject every
process model outright.

`pair:refinedBy` is PAIR's own rather than `sbpmn:calledElement`, whose unconstrained range
would accept it and would hard-code the sBPMN namespace into every submitted architecture,
foreclosing a later change of process ontology.

### 7.3 Two derivations

**`business_flow.rq` — typed reachability.** `bp:sourceRef` and `bp:targetRef` are declared
on *five* classes: `sequenceFlow`, `messageFlow`, `dataAssociation`, `association`,
`conversationLink`. A property path written straight over them walks out of control flow,
through a data association, and back in somewhere unrelated — and the result looks like
evidence. One *typed* hop is therefore materialised as `pair:businessFollows`, so every
condition downstream uses a plain transitive path that cannot make that mistake. **Never
write a raw path over `bp:sourceRef`.**

**`business_data_bridge.rq` — the point of the whole layer.** A personal-data kind declared
on a `bpmn:itemDefinition`, minus the two DPV values that mean "not personal"
(`dpv:AnonymisedData`, `dpv:NonPersonalData`), yields `pair:SensitiveInformation` on the
refined system's resources playing `pair:UserInput` or `pair:PredictionRequest` — or a
sub-role of either — with a `prov:Derivation` recording which annotation produced it.
`dpv:PseudonymisedData` is **not** excluded: pseudonymised data is still personal data.

R8 stays intact: what is *annotated* stays annotated — on the item definition, by a human;
what is *derived* is the data category, exactly as before. **No facet is propagated as a
facet, and no BPMN triple enters the architecture.**

`dpv:AnonymisedData` and `dpv:NonPersonalData` are excluded and are offered in the UI on
purpose: "checked, and not personal" is a claim, and it must not collapse into the silence of
never having said anything.

### 7.4 A control can live in the process

The improper-output-handling query asks its absence question **twice**: once of the
architecture (is there an output validation or guardrail step reading or producing this
output?) and once of the business process (is there a human task, downstream of the activity
this system refines, reading what that activity produced, performed by a `bp:humanPerformer`?).

Without the second question the finding could only be cleared by inserting a control step
into the architecture — and a review that genuinely exists went on being reported as absent.
Nothing is asserted into the architecture and no facet is read: it is a positive structural
claim over represented business structure, evaluated on elements the match already bound,
admissible under R10 and graph-relative under R4 like every other absence here. It is inert
when no process is submitted.

### 7.5 What the layer actually moves

Measured 2026-08-30. Two scenes, two different effects:

**IT service desk** — the agent alone assesses to 4 matches / 8 findings; with its process,
4 / **9**. The added finding is a candidate sensitive information disclosure, raised because
a personal-data item declared on the process reaches the system's user-facing output.
`test_business_data_editing.py` pins the mechanism rather than the total: detaching the data
annotation returns it to 8, re-declaring it as `dpv:PersonalData` restores 9, and
re-declaring it as `dpv:AnonymisedData` leaves it at 8.

**Energy customer service** — the two architectures alone give 7 / 8; with the process, also
7 / 8. **The total is unchanged and the content is not:**

- **+1** candidate sensitive information disclosure, raised by the data bridge;
- **−1** candidate improper LLM output handling, cleared by the human review step that lives
  in the process (§7.4).

State the composition, not the total. A count alone hides two real changes in opposite
directions — and the earlier summary of this layer as "the scene is not the sum of its parts"
is, for this scene, arithmetically false while the underlying claim is stronger than it
sounds.

`ec:LogInteraction` correctly clears nothing: logging an interaction is not reviewing it.
Both steps are in the example on purpose, because a layer where every added step clears
something is a layer that is not being read.

### 7.6 Scoping is a traversal, not stored state

`pair:refinedBy` names the system, and `beam:hasProcess` / `hasResource` / `hasAgent` /
`contain` say what it holds, so "the architecture behind **this** activity" is answered by
walking the graph (`graph_view._members_of()`). There is no database and there must not be one
for this. The same membership draws the per-system boundary on the architecture canvas.

### 7.7 The canvas draws what a risk assessment reads, and no more

Pools as bands, activities in flow order with task-type glyphs, sequence flow within a pool,
message flow across pools, sub-process expansion in place, data objects as folded pages, data
stores as cylinders, data associations as dashed arrows, and the classification humanised
above the shape. **Gateways, events and boundary markers are deliberately absent**: no bundled
example uses one, a faithful BPMN renderer is a project of its own, and none of them changes
a finding.

Editing runs through `/api/process-edit`, a server-side rewrite mirroring `/api/graph-edit`,
so the Turtle in the editor stays the single source of truth. Whether a connection is a
sequence flow or a message flow is read from the containment, never asked — in BPMN that is
not a preference.

---

## Related documents

| Document | Role |
| --- | --- |
| `docs/reference/PAIR-AI_glossary_v1_3.md` | **Authoritative.** Definitions, rules R1–R10, grounding references |
| `docs/reference/catalogue.md` | Full inventory of motifs, risk patterns, roles, data categories |
| `docs/reference/risk_control_linkage.md` | Risk to control linkage, including the MIT evidence layer |
| `docs/reference/mitigation_and_gap_mechanics.md` | How a control is applied and how the gap report is built |
| `docs/user_guide.md` | Workbench user guide |
| `ontology/example/*.ttl`, `ontology/example/context/*.ttl` | The bundled architectures and process models |
| `docs/notes/business_context_as_built.md` | What shipped on the business-layer branch (local-only; `docs/notes/` is gitignored) |
| `CHANGELOG_data_model.md` | Data-model change and audit record (local-only) |
