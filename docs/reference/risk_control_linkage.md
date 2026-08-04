# Risk, Motif, Control and Mitigation - linkage reference

The single reference for how a matched motif reaches a mitigation, and what kind
of claim each hop makes. Generated from the ontology and the cross-walk CSV by
`python/scripts/generate_risk_control_linkage.py`; every number is computed.

Supersedes `motif_control_linkage.md` and `control_catalogue_table.md`.

---

## 1. Inventory

| Layer | Count | What it is |
|---|---|---|
| **Motif library** | **26** | Risk-neutral architectural shapes (`pair:GraphMotif`) |
| **Risk patterns** | **13** | Motif + applicability condition -> candidate finding |
| **Suggested controls** | **12** | `pat:Control_*`, the only vocabulary in `pair:suggestedControl` |
| | | |
| MIT control groups | 20 | Categories + sub-categories, **MIT verbatim** |
| MIT mitigation actions | 52 | Concrete actions, **MIT verbatim** |
| PAIR-AI concrete controls | 16 | In `mitctrl:` namespace but **project curation** |
| **Mitigation vocabulary, total** | **88** | of which **72** carry `nexus:isDefinedByTaxonomy` |

### What counts as "a mitigation" depends on the level

Three different numbers are all defensible, so state which one is meant:

- **52** concrete MIT actions (`A0897 Model Prompting`, ...)
- **20** MIT families (4 categories + sub-categories)
- **12** PAIR-AI suggested controls - the only ones a finding emits

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
| 1 | **Input validation and prompt isolation**<br>`pat:Control_InputValidationAndPromptIsolation` | MemoryPoisoning, PromptInjection | AgentMemoryLoop, DirectPrompting, QueryRewriting, RetrievalAugmentedGeneration | **Guardrails** | input-output-filtering, prompt-context-limiting | 0 |
| 2 | **Output validation and sanitization**<br>`pat:Control_OutputValidationAndSanitization` | ImproperOutputHandling, SensitiveDataRetrievalExposure, SystemPromptLeakage | DirectPrompting, Guardrails, VectorBasedInformationRetrieval | **Guardrails** | content-safety-controls, input-output-filtering | 2 |
| 3 | **Data minimization and redaction**<br>`pat:Control_DataMinimizationAndRedaction` | SensitiveDataRetrievalExposure | VectorBasedInformationRetrieval | (none) | data-minimization, privacy-control-for-user-data, redaction | 0 |
| 4 | **Retrieval access control**<br>`pat:Control_RetrievalAccessControl` | SensitiveDataRetrievalExposure, VectorAndEmbeddingWeakness | Embeddings, Reranker, RetrievalAugmentedGeneration, VectorBasedInformationRetrieval | (none) | access-management, retrieval-quality-evaluation, retrieval-source-filtering | 4 |
| 5 | **Model and dependency provenance**<br>`pat:Control_ModelAndDependencyProvenance` | DataAndModelPoisoning, SupplyChainCompromise | Embeddings, ExternalDependency, FineTuning, ModelInImage, ModelLoad, TrainingToServing | (none) | model-infrastructure-security, risk-register, system-architecture-documentation | 0 |
| 6 | **Trusted training and indexing data**<br>`pat:Control_TrustedTrainingAndIndexingData` | DataAndModelPoisoning, MemoryPoisoning, VectorAndEmbeddingWeakness | AgentMemoryLoop, Embeddings, FineTuning, Reranker, RetrievalAugmentedGeneration, TrainingToServing | (none) | data-curation-process, data-governance, testing-auditing | 26 |
| 7 | **Tool permission boundaries**<br>`pat:Control_ToolPermissionBoundaries` | ExcessiveAgency, ToolMisuse | ToolUsingAgent | (none) | access-management, human-oversight-protocol, post-deployment-behavior-monitoring | 4 |
| 8 | **System prompt secrecy**<br>`pat:Control_SystemPromptSecrecy` | SystemPromptLeakage | Guardrails | (none) | prompt-context-limiting, red-teaming, system-architecture-documentation | 0 |
| 9 | **Grounding and verification**<br>`pat:Control_GroundingAndVerification` | DirectPromptingWithoutGrounding, MisinformationFromWeakGrounding, VectorAndEmbeddingWeakness | DirectPrompting, Embeddings, Reranker, RetrievalAugmentedGeneration | **HybridRetriever, Reranker, RetrievalAugmentedGeneration, VectorBasedInformationRetrieval** | human-oversight-protocol, retrieval-quality-evaluation, testing-auditing | 12 |
| 10 | **Rate, budget, and loop control**<br>`pat:Control_RateLimitBudgetAndLoopControl` | ExcessiveAgency, ToolMisuse, UnboundedConsumption | DirectPrompting, QueryRewriting, RetrievalAugmentedGeneration, ToolUsingAgent | (none) | access-management, post-deployment-behavior-monitoring, prompt-context-limiting | 4 |
| 11 | **Logging, monitoring, and evals**<br>`pat:Control_LoggingMonitoringAndEvals` | DataAndModelPoisoning, DirectPromptingWithoutGrounding, ExcessiveAgency, MemoryPoisoning, MisinformationFromWeakGrounding, PromptInjection, SupplyChainCompromise, ToolMisuse, UnboundedConsumption | AgentMemoryLoop, DirectPrompting, Embeddings, ExternalDependency, FineTuning, ModelInImage, ModelLoad, QueryRewriting, RetrievalAugmentedGeneration, ToolUsingAgent, TrainingToServing | **Evals, PredictionLogging, PredictionMonitoring** | post-deployment-behavior-monitoring, red-teaming, testing-auditing | 12 |
| 12 | **Input and output filtering**<br>`pat:Control_Guardrails` | ImproperOutputHandling, PromptInjection, SensitiveDataRetrievalExposure, SystemPromptLeakage | DirectPrompting, Guardrails, QueryRewriting, RetrievalAugmentedGeneration, VectorBasedInformationRetrieval | **Guardrails** | content-safety-controls, input-output-filtering, model-safety-engineering | 9 |

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

Risk patterns with no action-level evidence (3): `SystemPromptLeakage`, `UnboundedConsumption`, `VectorAndEmbeddingWeakness`

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
| `system-documentation` | 2 | **no** |
| `incident-response-recovery` | 1 | **no** |
| `post-deployment-monitoring` | 1 | **no** |
| `risk-management` | 1 | **no** |
| `safety-decision-frameworks` | 1 | **no** |
| `societal-impact-assessment` | 1 | **no** |
| `user-rights-recourse` | 1 | **no** |

Families with no action beneath them (6): `governance-oversight-controls`, `model-infrastructure-security`, `operational-process-controls`, `staged-deployment`, `technical-security-controls`, `transparency-accountability-controls`

---

## 6. Gaps

1. **7 of 12 controls have no realizing motif.** The tool can advise them but cannot verify from the graph that they were applied.
2. **12 of 26 motifs reach no control** - by design for the risk-neutral ML-serving shapes.
3. **1 risk pattern declares no motif** (`ExcessiveAgencyRiskPattern`) so it can never fire.
4. **7 circular suggestions** - the motif that triggers the finding is also the motif that would realize the suggested fix.
5. **Coverage is bounded by the cross-walk.** LLM07, LLM08 and LLM10 have no action-level evidence at all; their control links remain prior curation.

---

## 7. Motif library - all 26, by source catalogue

Motifs are risk-neutral: they describe a shape, not a problem. The grouping below
is the *published catalogue each was derived from* (`pair:derivedFrom`), because
that is the only classification the data actually carries - PAIR-AI does not
assign motifs to families of its own.

### Mercari ML System Design Patterns (13)

| Motif | Catalogue section | Risk patterns it feeds |
|---|---|---|
| `TrainThenServeMotif` | Lifecycle | *(risk-neutral - none)* |
| `TrainingToServingMotif` | Lifecycle | DataAndModelPoisoning, SupplyChainCompromise |
| `ModelInImageMotif` | Operation | SupplyChainCompromise |
| `ModelLoadMotif` | Operation | SupplyChainCompromise |
| `PredictionLoggingMotif` | Operation | *(risk-neutral - none)* |
| `PredictionMonitoringMotif` | Operation | *(risk-neutral - none)* |
| `AsynchronousPredictionMotif` | Serving | *(risk-neutral - none)* |
| `BatchPredictionMotif` | Serving | *(risk-neutral - none)* |
| `MultiStagePredictionMotif` | Serving | *(risk-neutral - none)* |
| `PreprocessPredictionMotif` | Serving | *(risk-neutral - none)* |
| `SynchronousPredictionMotif` | Serving | *(risk-neutral - none)* |
| `BatchTrainingMotif` | Training | *(risk-neutral - none)* |
| `PipelineTrainingMotif` | Training | *(risk-neutral - none)* |

### Fowler - Patterns of Generative AI (10)

| Motif | Catalogue section | Risk patterns it feeds |
|---|---|---|
| `DirectPromptingMotif` | GenAI | DirectPromptingWithoutGrounding, ImproperOutputHandling, PromptInjection, UnboundedConsumption |
| `EmbeddingsMotif` | GenAI | DataAndModelPoisoning, VectorAndEmbeddingWeakness |
| `EvalsMotif` | GenAI | *(risk-neutral - none)* |
| `FineTuningMotif` | GenAI | DataAndModelPoisoning, SupplyChainCompromise |
| `GuardrailsMotif` | GenAI | ImproperOutputHandling, SystemPromptLeakage |
| `HybridRetrieverMotif` | GenAI | *(risk-neutral - none)* |
| `QueryRewritingMotif` | GenAI | PromptInjection, UnboundedConsumption |
| `RerankerMotif` | GenAI | VectorAndEmbeddingWeakness |
| `RetrievalAugmentedGenerationMotif` | GenAI | MisinformationFromWeakGrounding, PromptInjection, UnboundedConsumption, VectorAndEmbeddingWeakness |
| `VectorBasedInformationRetrievalMotif` | GenAI | SensitiveDataRetrievalExposure |

### OWASP Agentic Top 10 (ASI) (2)

| Motif | Catalogue section | Risk patterns it feeds |
|---|---|---|
| `AgentMemoryLoopMotif` | agentic | MemoryPoisoning |
| `ToolUsingAgentMotif` | agentic | ToolMisuse |

### OWASP LLM Top 10 (1)

| Motif | Catalogue section | Risk patterns it feeds |
|---|---|---|
| `ExternalDependencyMotif` | supply chain | SupplyChainCompromise |

---

## 8. Risk patterns - all 13

| Risk pattern | Anchor | Motifs | Suggested controls |
|---|---|---|---|
| **DataAndModelPoisoning** | `llm04-data-and-model-poisoning` | Embeddings, FineTuning, TrainingToServing | LoggingMonitoringAndEvals, ModelAndDependencyProvenance, TrustedTrainingAndIndexingData |
| **DirectPromptingWithoutGrounding** | `llm09-misinformation` | DirectPrompting | GroundingAndVerification, LoggingMonitoringAndEvals |
| **ExcessiveAgency** | `llm06-excessive-agency` | **(none - cannot fire)** | LoggingMonitoringAndEvals, RateLimitBudgetAndLoopControl, ToolPermissionBoundaries |
| **ImproperOutputHandling** | `llm05-improper-output-handling` | DirectPrompting, Guardrails | Guardrails, OutputValidationAndSanitization |
| **MemoryPoisoning** | `asi06-memory-and-context-poisoning` | AgentMemoryLoop | InputValidationAndPromptIsolation, LoggingMonitoringAndEvals, TrustedTrainingAndIndexingData |
| **MisinformationFromWeakGrounding** | `llm09-misinformation` | RetrievalAugmentedGeneration | GroundingAndVerification, LoggingMonitoringAndEvals |
| **PromptInjection** | `llm01-prompt-injection` | DirectPrompting, QueryRewriting, RetrievalAugmentedGeneration | Guardrails, InputValidationAndPromptIsolation, LoggingMonitoringAndEvals |
| **SensitiveDataRetrievalExposure** | `llm02-sensitive-information-disclosure` | VectorBasedInformationRetrieval | DataMinimizationAndRedaction, Guardrails, OutputValidationAndSanitization, RetrievalAccessControl |
| **SupplyChainCompromise** | `llm03-supply-chain` | ExternalDependency, FineTuning, ModelInImage, ModelLoad, TrainingToServing | LoggingMonitoringAndEvals, ModelAndDependencyProvenance |
| **SystemPromptLeakage** | `llm07-system-prompt-leakage` | Guardrails | Guardrails, OutputValidationAndSanitization, SystemPromptSecrecy |
| **ToolMisuse** | `asi02-tool-misuse` | ToolUsingAgent | LoggingMonitoringAndEvals, RateLimitBudgetAndLoopControl, ToolPermissionBoundaries |
| **UnboundedConsumption** | `llm10-unbounded-consumption` | DirectPrompting, QueryRewriting, RetrievalAugmentedGeneration | LoggingMonitoringAndEvals, RateLimitBudgetAndLoopControl |
| **VectorAndEmbeddingWeakness** | `llm08-vector-and-embedding-weaknesses` | Embeddings, Reranker, RetrievalAugmentedGeneration | GroundingAndVerification, RetrievalAccessControl, TrustedTrainingAndIndexingData |

---

## 9. Controls and mitigations - technical vs non-technical

### 9a. PAIR-AI suggested controls (12) - `pair:controlNature`

This is the axis that matters operationally: a technical control has a footprint
in the architecture, so the assessment can look for it. A non-technical one is
organisational and leaves no structure to detect, so it can only ever be advice.

**Technical (10)**

| Control | Realizing motif | Verifiable from the graph? |
|---|---|---|
| **Data minimization and redaction**<br>`Control_DataMinimizationAndRedaction` | (none) | no - no motif expresses it |
| **Grounding and verification**<br>`Control_GroundingAndVerification` | HybridRetriever, Reranker, RetrievalAugmentedGeneration, VectorBasedInformationRetrieval | **yes** |
| **Input and output filtering**<br>`Control_Guardrails` | Guardrails | **yes** |
| **Input validation and prompt isolation**<br>`Control_InputValidationAndPromptIsolation` | Guardrails | **yes** |
| **Logging, monitoring, and evals**<br>`Control_LoggingMonitoringAndEvals` | Evals, PredictionLogging, PredictionMonitoring | **yes** |
| **Output validation and sanitization**<br>`Control_OutputValidationAndSanitization` | Guardrails | **yes** |
| **Rate, budget, and loop control**<br>`Control_RateLimitBudgetAndLoopControl` | (none) | no - no motif expresses it |
| **Retrieval access control**<br>`Control_RetrievalAccessControl` | (none) | no - no motif expresses it |
| **System prompt secrecy**<br>`Control_SystemPromptSecrecy` | (none) | no - no motif expresses it |
| **Tool permission boundaries**<br>`Control_ToolPermissionBoundaries` | (none) | no - no motif expresses it |

**Non-technical (2)**

| Control | Realizing motif | Verifiable from the graph? |
|---|---|---|
| **Model and dependency provenance**<br>`Control_ModelAndDependencyProvenance` | (none) | never - no architectural footprint |
| **Trusted training and indexing data**<br>`Control_TrustedTrainingAndIndexingData` | (none) | never - no architectural footprint |

### 9b. MIT mitigation vocabulary (36 families + 52 actions)

MIT's own top-level category decides technical vs non-technical here. Note that
`nexus:controlType` mixes two axes - the MIT category (governance, technical,
operational, transparency-accountability) and control function (preventive,
detective, corrective) - so it cannot be read as a nature flag on its own.

| Nature | Families/controls | Actions beneath |
|---|---|---|
| **Technical** only | 5 | 9 |
| **Both** - sits under a technical *and* a non-technical category | 5 | 0 |
| Non-technical only | 26 | 43 |

> **The taxonomy is a polyhierarchy.** 8 of the 36 concepts have more than one top-level parent, and 5 of those straddle the technical boundary specifically. So "technical vs non-technical" is not a clean partition here, the way `pair:controlNature` is for the 12 suggested controls. Where a single answer is needed, use 9a.
>
> Note that **all 5 straddling concepts are PAIR-AI curation**, not MIT entries. The ambiguity comes from this project deliberately parenting its own controls under two families, not from anything in MIT's taxonomy.

**Technical only (5)**

- `content-safety-controls` - MIT verbatim, 2 actions  <br>*under: technical-security*
- `input-output-filtering` - **PAIR-AI curation**  <br>*under: technical-security*
- `model-infrastructure-security` - MIT verbatim  <br>*under: technical-security*
- `model-safety-engineering` - MIT verbatim, 7 actions  <br>*under: technical-security*
- `technical-security-controls` - MIT verbatim  <br>*under: technical-security*

**Both technical and non-technical (5)**

- `prompt-context-limiting` - **PAIR-AI curation**  <br>*under: operational-process, technical-security*
- `red-teaming` - **PAIR-AI curation**  <br>*under: operational-process, technical-security*
- `redaction` - **PAIR-AI curation**  <br>*under: operational-process, technical-security*
- `retrieval-source-filtering` - **PAIR-AI curation**  <br>*under: operational-process, technical-security*
- `threat-modelling` - **PAIR-AI curation**  <br>*under: operational-process, technical-security*

**Non-technical only (26)**

- `access-management` - MIT verbatim, 4 actions  <br>*under: operational-process*
- `data-curation-process` - **PAIR-AI curation**  <br>*under: operational-process*
- `data-governance` - MIT verbatim, 14 actions  <br>*under: operational-process*
- `data-minimization` - **PAIR-AI curation**  <br>*under: operational-process*
- `governance-oversight-controls` - MIT verbatim  <br>*under: governance-oversight*
- `human-oversight-protocol` - **PAIR-AI curation**  <br>*under: governance-oversight, transparency-accountability*
- `incident-reporting` - MIT verbatim, 2 actions  <br>*under: transparency-accountability*
- `incident-response-plan` - **PAIR-AI curation**  <br>*under: operational-process, transparency-accountability*
- `incident-response-recovery` - MIT verbatim, 1 actions  <br>*under: operational-process*
- `operational-process-controls` - MIT verbatim  <br>*under: operational-process*
- `post-deployment-behavior-monitoring` - **PAIR-AI curation**  <br>*under: operational-process*
- `post-deployment-monitoring` - MIT verbatim, 1 actions  <br>*under: operational-process*
- `pre-deployment-risk-assessment` - **PAIR-AI curation**  <br>*under: governance-oversight, operational-process*
- `privacy-control-for-user-data` - **PAIR-AI curation**  <br>*under: operational-process*
- `retrieval-quality-evaluation` - **PAIR-AI curation**  <br>*under: operational-process*
- `risk-disclosure` - MIT verbatim, 3 actions  <br>*under: transparency-accountability*
- `risk-management` - MIT verbatim, 1 actions  <br>*under: governance-oversight*
- `risk-register` - **PAIR-AI curation**  <br>*under: governance-oversight*
- `safety-decision-frameworks` - MIT verbatim, 1 actions  <br>*under: governance-oversight*
- `societal-impact-assessment` - MIT verbatim, 1 actions  <br>*under: governance-oversight*
- `staged-deployment` - MIT verbatim  <br>*under: operational-process*
- `system-architecture-documentation` - **PAIR-AI curation**  <br>*under: transparency-accountability*
- `system-documentation` - MIT verbatim, 2 actions  <br>*under: transparency-accountability*
- `testing-auditing` - MIT verbatim, 12 actions  <br>*under: operational-process*
- `transparency-accountability-controls` - MIT verbatim  <br>*under: transparency-accountability*
- `user-rights-recourse` - MIT verbatim, 1 actions  <br>*under: transparency-accountability*

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
| `ontology/patterns/motif.ttl` | the 26 motifs and their pattern nodes/edges |
| `ontology/patterns/risk_pattern_library.ttl` | the 13 risk patterns, the 12 suggested controls, and the control-to-MIT bridge |
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
| `docs/reference/PAIR-AI_glossary_v1.2.md` | terminology and the locked modelling rules (R1-R8). Read Section C before changing anything |
| `docs/reference/PAIR-AI_method_and_construction.md` | how the knowledge base was built |
| `docs/reference/catalogue.md` | the motif catalogue in prose |
| `docs/claude/CLAUDE.md` | locked decisions, including licence posture per source |

