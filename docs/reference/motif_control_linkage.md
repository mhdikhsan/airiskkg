# Motif → Control Linkage

How a matched motif reaches a suggested control, what kind of claim each link
makes, and how much of that claim rests on evidence rather than on our own say-so.

**Generated from the ontology** by `python/scripts/generate_motif_control_linkage.py`; every count and
every tier below is computed from the graph, not transcribed. Regenerate after
changing `motif.ttl`, `risk_pattern_library.ttl`, or `control_mitigation_layer.ttl`.

---

## The two links are different claims

A motif and a control can be related in two ways, and conflating them is the
main modelling hazard here.

```
  EXPOSURE     motif --hasMotif--> risk pattern --suggestedControl--> control
               "this shape exposes a risk that this control mitigates"

  REALIZATION  control --realizedByMotif--> motif
               "this shape IS the control"
```

The direction of benefit is opposite. In an **exposure** link the motif is the
problem; in a **realization** link the motif is the fix. `GuardrailsMotif` is both,
depending on which risk pattern you approach it from — it realizes
`Control_Guardrails` while itself exposing `SystemPromptLeakageRiskPattern`.
A document that merged the two would suggest guardrails as a mitigation for
guardrails.

Counts today:

| | |
|---|---|
| Motifs in the library | 26 |
| Risk patterns | 13 |
| Controls (`pat:Control_*`) | 12 |
| Exposure links (motif × control, via a risk pattern) | 64 |
| Realization links (`pair:realizedByMotif`) | 10 |

---

## Confidence: what it means and how it is derived

**No confidence number here is asserted.** Every link in this file is project
curation — nobody publishes a motif→control mapping we could adopt — so a
numeric score would be false precision of exactly the kind the mapping
provenance layer exists to expose (`ontology/taxonomy/provenance/`).

What *can* be derived is how **checkable** a link is: whether its truth or
falsity could be established from a submitted architecture graph. That is a
property of the control, not an opinion about the link, and it is computed:

| Tier | Meaning | Can the assessment verify the fix landed? |
|---|---|---|
| **A** | Technical control **and** a motif realizes it | **Yes** — the fix is expressible in the same vocabulary, so its presence or absence is decidable |
| **B** | Technical control, no realizing motif | **No** — the fix has an architectural footprint but the library cannot express it |
| **C** | Non-technical control | **No, and never** — governance/process, no architectural footprint by definition |

Tier A is the only one where *"you applied this control"* is a falsifiable
statement. Tiers B and C are advice: correct, possibly essential, but the tool
cannot confirm or refute that they were acted on. Reporting them at the same
visual weight as tier A would overstate what the method knows.

This mirrors Rule R4. Absence is closed-world over the submitted graph only, so
the assessment can say *"no guardrail motif is present"* (tier A) but can never
say *"no model provenance process exists"* (tier C) — that fact simply is not in
the graph.

Distribution of the 64 exposure links:

| Tier | Links | Share |
|---|---|---|
| A | 38 | 59% |
| B | 11 | 17% |
| C | 15 | 23% |

So **59%** of what the tool suggests is structurally
verifiable; the rest is advice it cannot follow up on.

**Read that number with a caveat.** One control does most of the work:
`LoggingMonitoringAndEvals` alone accounts for **18 of the 38**
tier-A links, because 9 of the
13 risk patterns suggest it — logging and evaluation are close to
universally applicable, so they attach almost everywhere and are cheap to
verify. Excluding it, structurally verifiable suggestions drop to **20 of
64** (31%).

Only **5 of the 12 controls** are ever tier A. That is the
more useful figure for planning: it is the size of the vocabulary in which the
method can currently express a *checkable* fix.

---

## Risk pattern → taxonomy: explicit triples, not inferred from names

Risk pattern names read like OWASP entries (`PromptInjection`,
`SystemPromptLeakage`), which invites the assumption that the taxonomy link is
recovered from the name. It is not. There is no `mapsToRisk` predicate and no
string matching anywhere in the pipeline. Every risk pattern carries two
explicit sets of triples to resolvable URIs:

- **`pair:derivedFrom`** — the single entry the pattern was written from.
- **`pair:mayIndicateRisk`** — every taxonomy entry a finding may cite. Named
  for Rule R1: a match *may indicate* a risk, it does not *map to* one.

Name-based inference would in fact get several of these wrong:

| | |
|---|---|
| `DirectPromptingWithoutGrounding` **and** `MisinformationFromWeakGrounding` | both anchor to `llm09-misinformation` — two patterns, one OWASP entry |
| `ToolMisuse` | derives from **ASI**02, yet also indicates `llm06-excessive-agency` |
| `MemoryPoisoning` | derives from **ASI**06, yet also indicates `llm04-data-and-model-poisoning` |
| `VectorAndEmbeddingWeakness` | indicates `ibm-risk-atlas:prompt-injection`, which its name never suggests |

Two tests hold the chain together:

- `test_risk_patterns_have_condition_mechanism_and_taxonomy_anchor` — a risk
  pattern without an anchor fails.
- `test_may_indicate_risk_entries_are_mapped_to_anchor` — every *non-anchor*
  entry must be joined to the anchor by a real SKOS mapping triple in the
  taxonomy layer. Atlas and MIT entries cannot float free; they are reachable
  only through a mapping that itself now carries a semapv justification in
  `ontology/taxonomy/provenance/`.

So the full evidence chain behind one suggested control is:

```
  motif --hasMotif--> risk pattern --derivedFrom--> OWASP entry
                            |
                            +--mayIndicateRisk--> Atlas / MIT / ASI entries
                            |                     (each SKOS-mapped to the anchor,
                            |                      each mapping justified)
                            +--suggestedControl--> control
```

Only the last hop is uncorroborated project curation. Everything to its left
is either a published pattern catalogue or a taxonomy link with recorded
provenance.

| Risk pattern | Anchor (`derivedFrom`) | Also indicates (`mayIndicateRisk`) |
|---|---|---|
| `DataAndModelPoisoning` | `llm04-data-and-model-poisoning` | `data-poisoning`, `subdomain-1-3`, `subdomain-2-2`, `subdomain-7-3` |
| `DirectPromptingWithoutGrounding` | `llm09-misinformation` | `hallucination`, `incomplete-advice`, `subdomain-3-1`, `subdomain-5-1`, `subdomain-7-3` |
| `ExcessiveAgency` | `llm06-excessive-agency` | `redundant-actions-agentic`, `subdomain-2-2`, `subdomain-5-2` |
| `ImproperOutputHandling` | `llm05-improper-output-handling` | `subdomain-1-2`, `subdomain-2-2` |
| `MemoryPoisoning` | `asi06-memory-and-context-poisoning` | `llm04-data-and-model-poisoning`, `subdomain-2-2`, `subdomain-3-1` |
| `MisinformationFromWeakGrounding` | `llm09-misinformation` | `hallucination`, `incomplete-advice`, `subdomain-3-1`, `subdomain-5-1`, `subdomain-7-3` |
| `PromptInjection` | `llm01-prompt-injection` | `prompt-injection`, `subdomain-2-2` |
| `SensitiveDataRetrievalExposure` | `llm02-sensitive-information-disclosure` | `exposing-personal-information`, `subdomain-2-1` |
| `SupplyChainCompromise` | `llm03-supply-chain` | `data-curation`, `subdomain-2-2`, `subdomain-7-3`, `subdomain-7-4` |
| `SystemPromptLeakage` | `llm07-system-prompt-leakage` | `confidential-data-in-prompt`, `prompt-leaking`, `subdomain-2-1`, `subdomain-2-2` |
| `ToolMisuse` | `asi02-tool-misuse` | `llm06-excessive-agency`, `subdomain-2-2`, `subdomain-5-2` |
| `UnboundedConsumption` | `llm10-unbounded-consumption` | `redundant-actions-agentic`, `subdomain-2-2`, `subdomain-6-6`, `subdomain-7-3` |
| `VectorAndEmbeddingWeakness` | `llm08-vector-and-embedding-weaknesses` | `prompt-injection`, `subdomain-2-2`, `subdomain-7-3` |

---

## Realization links — the motifs that ARE controls

These are the tier-A enablers: insert this motif and the control is, structurally,
in place.

| Control | Nature | Realized by motif |
|---|---|---|
| `Control_GroundingAndVerification` | Technical | `HybridRetrieverMotif`, `RerankerMotif`, `RetrievalAugmentedGenerationMotif`, `VectorBasedInformationRetrievalMotif` |
| `Control_Guardrails` | Technical | `GuardrailsMotif` |
| `Control_InputValidationAndPromptIsolation` | Technical | `GuardrailsMotif` |
| `Control_LoggingMonitoringAndEvals` | Technical | `EvalsMotif`, `PredictionLoggingMotif`, `PredictionMonitoringMotif` |
| `Control_OutputValidationAndSanitization` | Technical | `GuardrailsMotif` |

Controls with **no** realizing motif — every suggestion naming one is tier B or C:

| Control | Nature | Why nothing realizes it |
|---|---|---|
| `Control_DataMinimizationAndRedaction` | Technical | `pair:RedactionStep` exists as a *role* and acts as the propagation barrier, but no motif declares the surrounding shape |
| `Control_ModelAndDependencyProvenance` | NonTechnical | supplier attestation and review process - no structure to detect |
| `Control_RateLimitBudgetAndLoopControl` | Technical | no motif expresses budget or loop bounding |
| `Control_RetrievalAccessControl` | Technical | no motif expresses per-user authorization on retrieval |
| `Control_SystemPromptSecrecy` | Technical | no motif expresses prompt/secret separation |
| `Control_ToolPermissionBoundaries` | Technical | no motif expresses tool scoping; `ToolUsingAgentMotif` is the exposure, not the boundary |
| `Control_TrustedTrainingAndIndexingData` | NonTechnical | data sourcing and vetting process - no structure to detect |

The five technical ones are the **actionable backlog**: each is a motif that,
if added, would move every link naming it from tier B to tier A.

---

## Exposure links by motif

Read as: *if this motif matches, these controls are suggested, at this tier.*

| Motif | Provenance | Via risk pattern | Suggested control | Tier |
|---|---|---|---|---|
| `AgentMemoryLoopMotif` | OWASP ASI (taxonomy-derived) | `MemoryPoisoning` | `InputValidationAndPromptIsolation` | A |
|  |  | `MemoryPoisoning` | `LoggingMonitoringAndEvals` | A |
|  |  | `MemoryPoisoning` | `TrustedTrainingAndIndexingData` | C |
| `DirectPromptingMotif` | Fowler GenAI patterns | `DirectPromptingWithoutGrounding` | `GroundingAndVerification` | A |
|  |  | `DirectPromptingWithoutGrounding` | `LoggingMonitoringAndEvals` | A |
|  |  | `ImproperOutputHandling` | `Guardrails` | A |
|  |  | `ImproperOutputHandling` | `OutputValidationAndSanitization` | A |
|  |  | `PromptInjection` | `Guardrails` | A |
|  |  | `PromptInjection` | `InputValidationAndPromptIsolation` | A |
|  |  | `PromptInjection` | `LoggingMonitoringAndEvals` | A |
|  |  | `UnboundedConsumption` | `LoggingMonitoringAndEvals` | A |
|  |  | `UnboundedConsumption` | `RateLimitBudgetAndLoopControl` | B |
| `EmbeddingsMotif` | Fowler GenAI patterns | `DataAndModelPoisoning` | `LoggingMonitoringAndEvals` | A |
|  |  | `DataAndModelPoisoning` | `ModelAndDependencyProvenance` | C |
|  |  | `DataAndModelPoisoning` | `TrustedTrainingAndIndexingData` | C |
|  |  | `VectorAndEmbeddingWeakness` | `GroundingAndVerification` | A |
|  |  | `VectorAndEmbeddingWeakness` | `RetrievalAccessControl` | B |
|  |  | `VectorAndEmbeddingWeakness` | `TrustedTrainingAndIndexingData` | C |
| `ExternalDependencyMotif` | OWASP LLM Top 10 | `SupplyChainCompromise` | `LoggingMonitoringAndEvals` | A |
|  |  | `SupplyChainCompromise` | `ModelAndDependencyProvenance` | C |
| `FineTuningMotif` | Fowler GenAI patterns | `DataAndModelPoisoning` | `LoggingMonitoringAndEvals` | A |
|  |  | `DataAndModelPoisoning` | `ModelAndDependencyProvenance` | C |
|  |  | `DataAndModelPoisoning` | `TrustedTrainingAndIndexingData` | C |
|  |  | `SupplyChainCompromise` | `LoggingMonitoringAndEvals` | A |
|  |  | `SupplyChainCompromise` | `ModelAndDependencyProvenance` | C |
| `GuardrailsMotif` | Fowler GenAI patterns | `ImproperOutputHandling` | `Guardrails` | A |
|  |  | `ImproperOutputHandling` | `OutputValidationAndSanitization` | A |
|  |  | `SystemPromptLeakage` | `Guardrails` | A |
|  |  | `SystemPromptLeakage` | `OutputValidationAndSanitization` | A |
|  |  | `SystemPromptLeakage` | `SystemPromptSecrecy` | B |
| `ModelInImageMotif` | Mercari ML system design patterns | `SupplyChainCompromise` | `LoggingMonitoringAndEvals` | A |
|  |  | `SupplyChainCompromise` | `ModelAndDependencyProvenance` | C |
| `ModelLoadMotif` | Mercari ML system design patterns | `SupplyChainCompromise` | `LoggingMonitoringAndEvals` | A |
|  |  | `SupplyChainCompromise` | `ModelAndDependencyProvenance` | C |
| `QueryRewritingMotif` | Fowler GenAI patterns | `PromptInjection` | `Guardrails` | A |
|  |  | `PromptInjection` | `InputValidationAndPromptIsolation` | A |
|  |  | `PromptInjection` | `LoggingMonitoringAndEvals` | A |
|  |  | `UnboundedConsumption` | `LoggingMonitoringAndEvals` | A |
|  |  | `UnboundedConsumption` | `RateLimitBudgetAndLoopControl` | B |
| `RerankerMotif` | Fowler GenAI patterns | `VectorAndEmbeddingWeakness` | `GroundingAndVerification` | A |
|  |  | `VectorAndEmbeddingWeakness` | `RetrievalAccessControl` | B |
|  |  | `VectorAndEmbeddingWeakness` | `TrustedTrainingAndIndexingData` | C |
| `RetrievalAugmentedGenerationMotif` | Fowler GenAI patterns | `MisinformationFromWeakGrounding` | `GroundingAndVerification` | A |
|  |  | `MisinformationFromWeakGrounding` | `LoggingMonitoringAndEvals` | A |
|  |  | `PromptInjection` | `Guardrails` | A |
|  |  | `PromptInjection` | `InputValidationAndPromptIsolation` | A |
|  |  | `PromptInjection` | `LoggingMonitoringAndEvals` | A |
|  |  | `UnboundedConsumption` | `LoggingMonitoringAndEvals` | A |
|  |  | `UnboundedConsumption` | `RateLimitBudgetAndLoopControl` | B |
|  |  | `VectorAndEmbeddingWeakness` | `GroundingAndVerification` | A |
|  |  | `VectorAndEmbeddingWeakness` | `RetrievalAccessControl` | B |
|  |  | `VectorAndEmbeddingWeakness` | `TrustedTrainingAndIndexingData` | C |
| `ToolUsingAgentMotif` | OWASP ASI (taxonomy-derived) | `ToolMisuse` | `LoggingMonitoringAndEvals` | A |
|  |  | `ToolMisuse` | `RateLimitBudgetAndLoopControl` | B |
|  |  | `ToolMisuse` | `ToolPermissionBoundaries` | B |
| `TrainingToServingMotif` | Mercari ML system design patterns | `DataAndModelPoisoning` | `LoggingMonitoringAndEvals` | A |
|  |  | `DataAndModelPoisoning` | `ModelAndDependencyProvenance` | C |
|  |  | `DataAndModelPoisoning` | `TrustedTrainingAndIndexingData` | C |
|  |  | `SupplyChainCompromise` | `LoggingMonitoringAndEvals` | A |
|  |  | `SupplyChainCompromise` | `ModelAndDependencyProvenance` | C |
| `VectorBasedInformationRetrievalMotif` | Fowler GenAI patterns | `SensitiveDataRetrievalExposure` | `DataMinimizationAndRedaction` | B |
|  |  | `SensitiveDataRetrievalExposure` | `Guardrails` | A |
|  |  | `SensitiveDataRetrievalExposure` | `OutputValidationAndSanitization` | A |
|  |  | `SensitiveDataRetrievalExposure` | `RetrievalAccessControl` | B |

---

## Motifs that reach no control

12 of 26 motifs participate in no risk pattern, so matching them
suggests nothing. This is by design for the neutral ML-serving shapes — the Motif
Library is risk-neutral and a motif is not obliged to carry risk.

- `AsynchronousPredictionMotif`
- `BatchPredictionMotif`
- `BatchTrainingMotif`
- `EvalsMotif` — but realizes `LoggingMonitoringAndEvals`
- `HybridRetrieverMotif` — but realizes `GroundingAndVerification`
- `MultiStagePredictionMotif`
- `PipelineTrainingMotif`
- `PredictionLoggingMotif` — but realizes `LoggingMonitoringAndEvals`
- `PredictionMonitoringMotif` — but realizes `LoggingMonitoringAndEvals`
- `PreprocessPredictionMotif`
- `SynchronousPredictionMotif`
- `TrainThenServeMotif`

Note that 4 of them are not idle: they realize controls, so they are
*fixes* that the library can recognise even though they expose nothing.

---

## Known gaps

1. **`ExcessiveAgencyRiskPattern` declares no motif**, so it can never fire. Its controls —
   `LoggingMonitoringAndEvals`, `RateLimitBudgetAndLoopControl`, `ToolPermissionBoundaries` —
   are still reachable: `ToolMisuseRiskPattern` suggests the same set and does
   have a motif. So no control is stranded. What is lost is the *excessive
   agency* reading of an architecture, not the advice attached to it.

2. **No risk pattern declares `pair:maturity`.** The property exists and a test
   is marked xfail against it, so link quality cannot yet be filtered by
   maturity — the tiers here are the only quality signal available.

3. **Every link in this file is project curation.** No upstream publishes
   motif→control mappings. Unlike the taxonomy layer, there is nothing to adopt,
   so these cannot be corroborated against a third party — only reviewed.

