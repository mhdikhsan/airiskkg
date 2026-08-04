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

## 7. Provenance summary

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

