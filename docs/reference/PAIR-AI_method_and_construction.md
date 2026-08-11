# PAIR-AI — Method and Knowledge-Base Construction

Status: current as of **2026-07-28**, branch `feature/characterization-layer`.
Authority on terminology and modeling rules: `docs/reference/PAIR-AI_glossary_v1_3.md`
(rules R1–R10). Where this document and the glossary disagree, the glossary wins.

**What this document is.** One place that explains how the PAIR-AI knowledge base was
*built* and how an assessment *runs*: where risk patterns come from, where the role
vocabulary actually came from (§2 is deliberately blunt about this), how motifs are
curated, how the ontology reuses and aligns external vocabularies, what the pipeline
executes, and what the method currently cannot do.

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

| Artifact | Count | File |
| --- | --- | --- |
| Architectural motifs (ODPs) | 24 | `ontology/patterns/motif.ttl` |
| AI risk patterns | 11 | `ontology/patterns/risk_pattern_library.ttl` |
| Applicability conditions | 11 | `ontology/patterns/risk_pattern_library.ttl` |
| Risk mechanisms | 10 | `ontology/taxonomy/owasp_llm.ttl` |
| Pattern roles | 85 | `ontology/core/pair_ai_pattern.ttl` |
| Data categories | 8 | `ontology/core/pair_ai_pattern.ttl` |
| Actionable controls (`pat:Control_*`) | 12 | `ontology/patterns/control_mitigation_layer.ttl` |
| Registered SPARQL implementations (OQPs) | 36 | `ontology/patterns/implementation/*.rq` |
| — of which motif matchers | 24 | `match_*.rq` |
| — of which risk-finding queries | 11 | `risk_*.rq` |
| — of which facet propagation | 1 | `propagate_untrusted_content.rq` |

Note the ratio: **every motif has an executable matcher**, but only **12 of 24 motifs
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
in `ontology/taxonomy/owasp_llm.ttl`, each with a `skos:definition` copied or paraphrased
from the OWASP text and a `dct:source` pointing at the OWASP release.

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

Each risk pattern has exactly one OQP. Structurally, every one of the 11 queries:

1. starts from an existing `pair:MotifMatch` and reads its bindings
   (`pair:hasNodeBinding/pair:matchedElement`) — so risk evaluation is always anchored to
   structure that a motif already recognised;
2. adds the applicability conditions: facet checks (data category), extra structural
   reachability via property paths, and control-absence via `FILTER NOT EXISTS`
   (every one of the 11 queries uses at least one; `risk_unbounded_consumption.rq` uses three);
3. CONSTRUCTs a `pair:RiskFinding` carrying `pair:hasEvidence` (the matched elements),
   `pair:hasDerivedMechanism`, `pair:hasSatisfiedCondition` (all 11 queries emit it),
   `pair:hasCandidateRiskTaxonomyEntry`, `pair:hasSuggestedControl`, and
   `pair:findingStatus "candidate"`.

Conditions are **reusable constituents** and are shared across patterns where the
structural gate is genuinely the same. Example, documented in the file itself:
`pat:SensitiveDataRetrievalExposureRiskPattern` (anchored to LLM02) reuses
`pat:VectorEmbeddingWeakness_RetrievalCondition` (defined for LLM08), because the
retrieval-specific route to sensitive-information disclosure is exactly that gate. This is
a deliberate, commented exception, not drift.

### 1.5 Cross-taxonomy mappings

`ontology/taxonomy/taxonomy_mapping.ttl` is organised in explicit provenance tiers:

- **Section 1 — upstream-verified**: taken from IBM AI Atlas Nexus SSSOM mapping sets
  (`ibm2owasp.tsv`, `mit-ai-risk-repository_ibm-risk-atlas.tsv`), predicates preserved
  exactly as curated upstream (`ManualMappingCuration`, confidence 0.95).
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
curation — a reviewed first pass, and explicitly candidate associations (see §6.8 and
`docs/notes/control_layer_weakness_analysis.md`).

---

## 2. Roles creation — an honest account

Roles are the semantic bridge that makes motifs reusable across heterogeneous systems, and
they are also **the weakest-grounded layer of the knowledge base**. This section states
exactly how they came to exist.

### 2.1 What a role is, technically

- `pair:PatternRole` is an `owl:Class` that is `rdfs:subClassOf skos:Concept`; the 85
  roles are *instances* of it, assigned to architecture elements via `pair:playsRole`
  (domain `rdfs:Resource`, i.e. any element).
- Roles form a hierarchy through `pair:subRoleOf`, an `owl:TransitiveProperty`, under three
  roots: `pair:ProcessingStep`, `pair:ControlStep`, `pair:ResourceRole`.
- Queries match with `pair:playsRole/pair:subRoleOf* pair:SomeRole`, so tagging a more
  specific sub-role (`pair:PublicUserInput`) still satisfies a motif asking for the parent
  (`pair:UserInput`). This is what lets one motif match two systems annotated at different
  levels of specificity.

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

All 85 roles now carry `dct:source`. Breakdown:

| `dct:source` anchor(s) | Roles |
| --- | --- |
| Martin Fowler, gen-AI patterns | 24 |
| Mercari ML System Design Pattern | 20 |
| DPV / DPV-AI + Fowler | 9 |
| OWASP LLM Top 10 | 9 |
| Tool4Boxology + Fowler | 6 |
| DPV / DPV-AI + Mercari | 4 |
| Tool4Boxology | 3 |
| Tool4Boxology + DPV + Mercari | 2 |
| AIRO + DPV | 2 |
| Other combinations (Tool4Boxology/AIRO/DPV/Fowler/Mercari) | 4 |
| "expert curation" (+ OWASP scope note) | 2 |
| **Roles with no `dct:source`** | **0** |

Read that table carefully, because it is easy to over-claim:

- The provenance was **added after the roles existed**, during the v1.1/v2 consistency
  pass — it records *what a role was read from or anchored to*, not that the term was
  imported from a published vocabulary.
- **No role URI is an external URI.** All 85 live in the `pair:` namespace.
- There is **no `skos:exactMatch` / `skos:broadMatch` from any role to an external role
  vocabulary**, and there is **no `skos:ConceptScheme` for roles** (unlike the facets,
  which are proper SKOS schemes). The hierarchy uses the custom `pair:subRoleOf` rather
  than `skos:broader`.
- Where a source string says "DPV-AI ai:LLM" or "AIRO airo:Output", it means the concept
  was checked against that vocabulary and found compatible — not that the two are formally
  mapped.

### 2.4 Consequences to be aware of

1. **Coverage is exactly as wide as the two pattern catalogs plus OWASP.** Anything
   outside — agentic tool use, multi-agent delegation, human-in-the-loop review — has thin
   or no role coverage.
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
of) `pair:subRoleOf`; publish SKOS mappings to external vocabularies where genuine
counterparts exist (DPV-AI, AIRO, Tool4Boxology already appear in the source strings); and
run an empirical study — annotate unseen architectures with independent annotators and
measure both agreement and whether the role set is sufficient without extension.

---

## 3. Motif curation

### 3.1 Sources

24 motifs, each with `dct:source` **and** `pair:derivedFrom` (R6):

- **9 GenAI motifs** from Martin Fowler, *Emerging patterns for generative AI systems*:
  Direct Prompting, RAG, Embeddings, Vector-based Information Retrieval, Hybrid Retriever,
  Query Rewriting, Reranker, Guardrails, Evals, Fine-Tuning.
- **14 classic ML/MLOps motifs** from the Mercari ML System Design Pattern catalog, each
  sourced to the specific pattern page: serving (Synchronous, Asynchronous, Batch,
  Prep-pred, Multi-stage), training (Batch training, Pipeline training), lifecycle
  (Train-then-serve, Training-to-serving), operation (Prediction log, Prediction
  monitoring, Model load, Model-in-image).
- **1 project-curated motif**: `pat:ExternalDependencyMotif`, sourced as expert curation
  scoped by OWASP LLM03 (supply chain) — no external catalog defines it.

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
not merely asserted: no `match_*.rq` references `pair:containsDataCategory` or any
`facet:` property. (An earlier R2 leak in `match_embeddings.rq`, which filtered on a data
category, has been removed.) Keeping motifs facet-blind is what keeps them risk-neutral
and reusable: retrieval over public data and retrieval over sensitive data are the *same*
structure, and only the risk stage is allowed to care about the difference.

---

## 4. Ontology model: modules, reuse, alignment

### 4.1 Module map

| Module | Files | Content |
| --- | --- | --- |
| **Architecture** | `ontology/core/beam_core.ttl`, `ontology/alignments/*` | BEAM: `beam:System`, `beam:Process` (+ `Transform`/`Infer`/`Train`/`Generate`), `beam:Resource` (+ `Data`/`Symbol`/`Model`), `beam:Agent`, `beam:Task`; flow predicates `beam:use`, `beam:produce`, `beam:inform` |
| **Risk** | `ontology/core/beam_core_risk.ttl`, `ontology/taxonomy/*` | BEAM Risk (built on AIRO) + OWASP/IBM/MIT taxonomies + cross-mappings |
| **Pattern** | `ontology/core/pair_ai_pattern.ttl`, `ontology/patterns/*` | Roles, data categories, motif/risk-pattern/finding vocabulary, the two libraries, the control layer |
| **Facets** | `ontology/facets/*` | SKOS characterization schemes + their attachment properties |
| **Contract** | `shacl/architecture_input_contract.ttl` | SHACL shapes for a valid submitted architecture graph |

Stored permanently: the three modules (this is the reusable **AI-RKG**). Not stored:
per-system architecture graphs and their findings — those are assessment input/output and
land in `outputs/`.

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
  `skos:exactMatch` / `broadMatch` / `closeMatch`: OECD (data facets), VAIR, TÜV AI.ST
  (**on hold**, license unverified — do not add TÜV mappings).

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
| `pair:containsDataCategory` | `beam:Data` | `pair:DataCategory` (8), in the **pattern** module |

The Data Category facet sits in the pattern module rather than the facet module for a
substantive reason: its values are **propagated along data flow by a registered query**
(R8, derived facts), whereas every other facet is a base fact annotated by the modeler.
Ranges are kept at `skos:Concept` deliberately — the intended scheme is stated in the
property comment rather than enforced with OWL axioms.

R7 is respected throughout: **Task ≠ Capability ≠ Application Type** are three separate
axes and are never merged.

### 4.6 Input contract (R4)

`shacl/architecture_input_contract.ttl` makes explicit what a submitted graph *must*
(Violation) and *should* (Warning) represent for candidate findings to be meaningful — at
minimum one `beam:System`, and every `beam:Process` participating in at least one
`beam:use`/`beam:produce`. This is the operational counterpart of the Open World
Assumption: absence-of-control checks are only defensible if the contract states what the
submitter was expected to model.

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
   every file in `ontology/facets/`, and every file in `ontology/taxonomy/`, into one
   `rdflib.Graph`; then the submitted architecture file(s) are parsed into the *same*
   graph.
1. **Propagate** (`_propagate_data_categories`) — every implementation registered with
   `pair:producesOutputType pair:DataCategoryPropagation` (currently one:
   `propagate_untrusted_content.rq`) runs repeatedly until no new triple appears, capped
   at 20 iterations. Roots: anything under `pair:PublicUserInput` or
   `pair:RetrievedContext`. Taint flows along `beam:use`/`beam:produce`. It stops at a step
   under `pair:GuardrailStep` or at an element explicitly tagged `pair:TrustedContent`.
   Rationale: forgetting to hand-tag one derived element three hops downstream would
   silently suppress a finding.
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

### 5.3 Entry points

- **CLI** — `airiskkg assess <graph.ttl> [more.ttl ...] [--output-dir DIR]`
  (see `docs/notes/running_assessment_runner.md`).
- **Web workbench** — `airiskkg serve`: visual builder, Turtle editor, Tool4Boxology
  import, SHACL validation, and in-memory assessment rendered by OWASP category
  (see `docs/user_guide.md`, `docs/notes/running_the_webapp.md`).
- **Tool4Boxology import** — `python/scripts/normalize_t4b.py` and the workbench endpoint,
  both via `t4b_import.py`.

### 5.4 What a run currently produces

Verified on 2026-07-28 against the bundled examples:

| Example | Motif matches | Findings | Motifs that matched |
| --- | --- | --- | --- |
| `ontology/example/onyx_danswer.ttl` | 13 | 23 | DirectPrompting, Embeddings, ExternalDependency, QueryRewriting, Reranker, RAG, VectorIR |
| `ontology/example/beam_export_graph_rag.ttl` | 0 | 0 | — (raw Tool4Boxology export, **no role annotations**) |

The 23 findings on `onyx_danswer` span 16 distinct (motif, risk) combinations across eight
OWASP categories, with prompt-injection alone firing from four different motifs. The zero
on `beam_export_graph_rag.ttl` is not a failure of the pipeline — it is the method's
central dependency made visible: an unannotated graph, however well-drawn, matches nothing
(§6.6; `ontology/example/beam_export_graph_rag_annotated.ttl` is the annotated form of exactly this
file).

---

## 6. Current limitations

Each item below was verified against the repository on 2026-07-28, not carried over from
older notes.

**6.1 The characterization facet layer is declared but not consumed.** No query in
`ontology/patterns/implementation/` references any `facet:` property. Autonomy,
provenance, identifiability, dynamism, rights, domain, purpose, deployment setting, task,
implementation type — all modelled, none read. Only the Data Category facet (in the
pattern module) is operational. Until at least one applicability condition reads a facet,
the layer is an enabler, not a capability, and the "structure + context" story is
half-delivered.

**6.2 Only one derived facet exists.** Untrusted-content taint is the sole propagated
category. `pair:SensitiveInformation`, `pair:PromptInstruction`, and the rest must be
hand-tagged on every element that carries them. Propagation also only covers what is
structurally derivable — a `beam:Data` node labelled "internal HR records" with no
distinctive role stays untagged unless a human tags it.

**6.3 ODP and OQP are synchronized by hand.** No compiler turns a motif declaration into
its query. `test_library_consistency.py` catches identifier drift mechanically, but
semantic divergence (a query that is stricter or looser than its declaration) is only
caught by reading both.

**6.4 The role vocabulary is unvalidated and partly circular.** See §2.4: no external
grounding by URI, no SKOS scheme, no inter-annotator agreement study, and role granularity
was shaped by what motifs needed to bind.

**6.5 Example and test debt.** `ontology/example/uc6.ttl` and the Verba example were
removed, but `python/tests/test_uc6_assessment.py` and two tests in
`test_webapp_endpoints.py` still load them: **10 of 47 tests currently fail**
(`FileNotFoundError`), all for that reason. The remaining 37 pass. These tests need to be
repointed at `onyx_danswer.ttl` or a replacement fixture; until then the suite gives no
signal on those code paths.

**6.6 Assessment quality is bounded by annotation quality.** The method has no way to
recover a role the modeler did not assign, and three type mismatches silently block
matching (the LLM-call step must be `beam:Infer`, the model `beam:StatisticalModel`, data
boxes `beam:Data`). A perfectly drawn diagram with no `pair:playsRole` produces zero
findings, as `beam_export_graph_rag.ttl` demonstrates.

**6.7 Risk coverage is GenAI-shaped and OWASP-shaped.** 11 risk patterns anchored to the
OWASP LLM Top 10 cover **12 of 24 motifs**. The 12 uncovered motifs are almost entirely
the classic ML/MLOps set — Synchronous/Asynchronous/Batch/Multi-stage/Prep-pred
prediction, Batch and Pipeline training, Train-then-serve, Prediction logging and
monitoring — plus Evals and Hybrid Retriever. IBM Atlas and MIT entries are used as *link
targets*, never as sources of new patterns, so risks that OWASP does not name (fairness,
environmental cost, labour impact, most MIT domains) cannot currently be found even though
they are present in the loaded taxonomies.

**6.8 The control layer is a curated first pass.** `pair:realizedByMotif` covers 5 of 12
controls and encodes an *assumed* structural mitigation, not evidence that inserting the
motif removes the risk. The same MIT control family can still be reached by a finding
along multiple paths (as `pair:suggestedControl`, through a `pat:Control_*`
`skos:relatedMatch`, and through the risk's taxonomy entry). Detailed critique:
`docs/notes/control_layer_weakness_analysis.md`; forward plan:
`docs/notes/mitigation_research_roadmap.md`.

**6.9 Provenance obligations are partly unmet (R6).** The SSSOM export for taxonomy
mappings has not been generated. OECD facet concepts carry TODO markers instead of
`skos:exactMatch` because OECD publishes no resolvable concept URIs. `task.ttl`
second-level concepts and the Implementation Type scheme are curated placeholders awaiting
authoritative taxonomies. TÜV AI.ST is on hold pending license verification.

**6.10 Findings are unranked and overlapping.** There is no severity, likelihood, or
priority; no de-duplication when several motifs trigger the same risk on overlapping
evidence (prompt-injection fires four times on `onyx_danswer`); and no aggregation from
findings to a system-level statement. A human reads a flat list.

**6.11 There is no evaluation yet.** No ground-truth dataset, no precision/recall against
expert assessment, no baseline comparison, no user study. Firing counts on three example
architectures are the only empirical signal, and those examples were themselves annotated
by the method's authors.

**6.12 Engineering constraints.** The whole knowledge base plus the architecture graph is
loaded into a single in-memory `rdflib.Graph` per run; no OWL reasoning is performed at any
point (alignments are additive and are *not* consumed during matching, by design); and the
workbench builder does not support `beam:Agent` / `beam:Task`, so agentic architectures
cannot be authored there even though the vocabulary exists.

---

## Related documents

| Document | Role |
| --- | --- |
| `docs/reference/PAIR-AI_glossary_v1_3.md` | **Authoritative.** Definitions, rules R1–R10, grounding references |
| `docs/reference/catalogue.md` | Full inventory of motifs, risk patterns, roles, data categories |
| `docs/reference/risk_control_linkage.md` | Risk to control linkage, including the MIT evidence layer |
| `docs/user_guide.md` | Workbench user guide |
| `ontology/example/*.ttl` | Worked and unannotated example architecture graphs |
| `docs/notes/running_assessment_runner.md`, `running_the_webapp.md` | Operational setup |
| `docs/notes/control_layer_weakness_analysis.md` | Deep critique of the risk→control→motif chain |
| `docs/notes/mitigation_research_roadmap.md` | Forward plan for the mitigation layer |
| `CHANGELOG_data_model.md` | v1 → v2 rename and migration record |
