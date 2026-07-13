# Changelog — AI-RKG Data Model Update (v2, characterization layer)

Branch: `feature/characterization-layer` · Plan: `docs/claude/claude_code_prompt_data_model_update.md`
· Authority: `docs/reference/PAIR-AI_glossary_v1.1.md` (locked). Date: 2026-07-13.

All renamed URIs keep the old URI as a deprecated alias
(`owl:deprecated true` + `dct:isReplacedBy`) for one release.
Note: the glossary writes the pattern-module prefix as `rp:`; the ontology files
use the prefix `pair:` for the same namespace `http://w3id.org/airiskkg/pair-ai#`
(declared `vann:preferredNamespacePrefix "pair"`). The namespace URI is stable;
only the doc-vs-file prefix label differs.

## Task 1 — Renames and divergence fixes

Vocabulary renames (ontology + pattern libraries + all SPARQL + Python):

| Old | New |
| --- | --- |
| `pair:MotifInterpretation` | `pair:RiskPattern` |
| `pair:AIRiskPattern` (duplicate abstract parent) | merged into `pair:RiskPattern` |
| `pair:GraphCondition` | `pair:ApplicabilityCondition` |
| `pair:hasInterpretation` | `pair:hasRiskPattern` |
| `pair:interpretsMotif` | `pair:hasMotif` (inverse of `hasRiskPattern`) |
| `pair:hasInterpretationCondition` | `pair:hasApplicabilityCondition` |
| `pair:interpretedAsMechanism` | `pair:hasMechanism` |
| `pair:implementsInterpretation` | `pair:implementsRiskPattern` |
| `pair:hasInterpretedMechanism` | `pair:hasDerivedMechanism` |
| `pair:hasEvidenceElement` | `pair:hasEvidence` |
| `pat:*Interpretation` (11 instances) | `pat:*RiskPattern` |

New vocabulary:

- `pair:identifiesCandidateRisk` (domain `pair:RiskFinding`, range `beamr:Risk`).
  `pair:RiskFinding` confirmed standalone — it was already not a subclass of
  `beamr:Risk` in the v2 files, so nothing had to be removed.
- `pair:derivedFrom` (domain `pair:GraphMotif` ∪ `pair:RiskPattern`, range open)
  for derivation provenance.

DESIGN DECISION (flagged): evidence (`pair:hasEvidence`) is represented as the
set of matched architecture elements — one triple per element — matching how
findings were already materialized in `outputs/`. A named-graph representation
was rejected as more disruptive.

Naming/consistency fixes (Task 1.6):

1. `pat:EmbeddingMotif` → `pat:EmbeddingsMotif` in `risk_pattern_library.ttl`
   (motif library and all queries already used `EmbeddingsMotif`).
2. Restored the commented-out `pat:VectorBasedInformationRetrievalMotif`:
   `match_vector_ir.rq` and `pat:VectorIR_MatchingOQP` were active while the
   motif itself was commented out; the OQP wrongly claimed
   `implementsMotif pat:RetrievalAugmentedGenerationMotif` and now points to
   the restored motif.
3. Removed a duplicated `hasRiskPattern` block for
   `pat:RetrievalAugmentedGenerationMotif` (two overlapping lists; the superset
   was kept).
4. Fixed title typo "Architecuture Motif's Library" → "Architecture Motif Library".
5. Glossary-consistent `rdfs:comment`s added to every pattern-module class,
   candidate framing throughout ("may indicate", "candidate risk finding").
6. Visualization query variables and a test name still using "interpretation"
   wording renamed.

Provenance (Task 1.7): `pair:derivedFrom` added to all 23 motifs (mirroring
their `dct:source`) and all 11 risk patterns (OWASP LLM Top 10 entry +
`dct:source` OWASP 2025 URL).

## Task 2 — Characterization layer (`ontology/facets/`)

New files:

- `autonomy.ttl` — `AutonomyLevel` scheme (No / Low-HITL / Medium-HOTL /
  High-HOOTL action autonomy), OECD classification framework as source.
- `data_facets.ttl` — `DataProvenance` (ExpertInput, ProvidedData,
  ObservedData, SyntheticData, DerivedData), `DataDynamism` (Static,
  PeriodicallyUpdated, RealTimeUpdated), `DataRights` (Proprietary, Public,
  Personal). No identifiability scheme (DPV reused instead — Task 3).
- `task.ttl` — `AITask` scheme, 9 top-level unified-task-taxonomy concepts
  with curated second-level concepts.
- `context.ttl` — `Domain` / `Purpose` / `DeploymentSetting` extension-point
  schemes; `Purpose` anchored `skos:exactMatch dpv:Purpose`.
- `facet_properties.ttl` — `facet:hasAutonomyLevel`, `hasDataProvenance`,
  `hasDataDynamism`, `hasDataRights`, `hasTaskCategory`, `hasDomain`,
  `hasPurpose`, `hasDeploymentSetting` (+ `hasIdentifiabilityLevel`, Task 3).
  Ranges kept at `skos:Concept`; intended scheme stated in comments only.

Wiring: `FACETS_DIR` added to `paths.py`; facet TTLs loaded by
`load_base_graph()`; `imports.ttl` aggregator imports the facet ontologies.
No TÜV AI.ST mappings anywhere (license on hold).

## Task 3 — DPV reuse

`facet:hasIdentifiabilityLevel` (domain `beam:Data`, range `skos:Concept`);
intended values are DPV URIs referenced directly, never copied.
**Verified against DPV v2.3** (`https://w3id.org/dpv#`, fetched 2026-07-13):
`dpv:IdentifyingPersonalData`, `dpv:PseudonymisedData`, `dpv:AnonymisedData`,
`dpv:ContextuallyAnonymisedData`. DPV defines **no** `IdentifiedData` concept;
`dpv:IdentifyingPersonalData` is the closest verified equivalent (noted in the
property comment).

## Task 4 — BEAM structural additions

`beam_core.ttl`, each with `dct:source` (easy-ai / Boxology anchor):

- under `beam:Data`: Number, Dataset, Tensor, Text, Image, Audio, Video, TimeSeries
- under `beam:Symbol`: Database, KnowledgeGraph, Label, Trace, Rules

No new object properties (R5); no new Model subclasses.

## Task 5 — SHACL input contract

- `shacl/architecture_input_contract.ttl` (operationalizes R4):
  ≥1 `beam:System` per graph (Violation); every `beam:Process` has ≥1
  `beam:use`/`beam:produce` (Violation); resources typed to Data/Symbol/Model
  leaf subtypes (Warning); processes/resources carry ≥1 `pair:playsRole`
  (Warning).
- `python/scripts/validate_graphs.py` + `python/tests/test_input_contract.py`;
  `pyshacl` added to dependencies.
- Both example graphs pass: uc6 (0 violations / 11 warnings), verba
  (0 violations / 20 warnings).

## Task 6 — Tool4Boxology alignment adapter

- `external/tool4boxology/`: vendored `Tool4BoxologyOntology.ttl`,
  `easy-ai-schema.ttl`, trimmed `sample_export.nt` + README (CC BY 4.0 /
  Apache 2.0; Bendler et al., ESWC 2026, DOI 10.1007/978-3-032-25159-6_11).
- `ontology/alignments/tool4boxology_alignment.ttl`: property alignments
  (`inputRoleParticipatesInProcess` ⊑ `beam:usedBy`,
  `outputRoleParticipatesInProcess` ⊑ `beam:produce`) and class alignments
  (Data, Symbol, Model, SemanticModel, Actor→Agent, Train, Transform, Infer,
  Generate).
- `python/scripts/normalize_t4b.py`: case-normalization, BEAM materialization
  (originals kept), `dct:conformsTo` provenance from `t4b:DesignPattern`
  labels, SHACL validation.
- `python/tests/test_t4b_roundtrip.py`: export → normalizer → BEAM → motif
  pipeline; flow triples materialize, SHACL passes (0 violations).

**Upstream issues to report** (documented in the adapter + README):

1. Ontology declares `t4b:patternProcess`; export uses `t4b:hasProcess`
   (adapter targets the export URI).
2. Export types instances with lowercase URIs (`t4b:data`, `t4b:transform`,
   `t4b:training`, …) not declared in the ontology.
3. Export uses `t4b:StatisticModel` / `t4b:Time%20Series`; ontology declares
   `t4b:StatisticalModel` / `t4b:TimeSeries`.
4. `Tool4BoxologyOntology.ttl` as published does not parse as Turtle
   (multi-line single-quoted `dc:description`); vendored copy carries a
   minimal syntax patch.

**DESIGN DECISIONS flagged for review**:

- `t4b:Deduce` → `beam:Infer`; `t4b:Embed` → `beam:Transform` (no direct BEAM
  equivalents).
- `t4b:StatisticalModel` → `beam:StatisticalModel` (beyond the agreed list;
  needed so statistical models normalize to a BEAM leaf type).
- `t4b:Boxology` instances typed `beam:System` by the normalizer (not an OWL
  axiom) so the input contract holds.
- `t4b:ReasoningAssumption` (OWA/CWA) left unmapped.
- `beam:Modify` was **not** added: the R5 remark sanctions it for Task 6, but
  the Task 6 spec itself states no new BEAM classes are needed, and no t4b
  class required it.

## Task 7 — Validation results

- 23/23 `.ttl` files under `ontology/`, `shacl/`, `external/` parse with RDFLib.
- pyshacl: both example graphs conform (warnings only, listed above).
- Assessment re-run on both use cases: **outputs triple-identical to the
  pre-change baseline** modulo exactly the two renamed finding predicates
  (`hasEvidenceElement`→`hasEvidence`, `hasInterpretedMechanism`→
  `hasDerivedMechanism`). uc6: 3 matches / 7 findings; verba: 2 matches /
  6 findings — unchanged.
- Tests: 14 pass, 1 pre-existing failure (below).

## Post-Task 7 addition — third example use case

`ontology/example/onyx_danswer.ttl` — Onyx (formerly Danswer), open-source
(MIT) enterprise RAG platform (`https://github.com/onyx-dot-app/onyx`).
Modeled: connector ingestion → chunking → bi-encoder embedding → hybrid
vector + keyword index → LLM query rephrasing → hybrid search → cross-encoder
reranking → prompt assembly → cited answer. Fires 5 motifs including three
with no prior example coverage (QueryRewriting, Reranker, DirectPrompting)
and 12 candidate findings across 6 risk patterns — including the
supply-chain pattern (its external models are match-bound, unlike verba's).
SHACL: 0 violations / 13 warnings. Tests: `python/tests/test_onyx_assessment.py`.
Note: the strict RAG motif intentionally does not fire — reranking sits
between retrieval and prompt construction, breaking the direct
retrieval-to-prompt chain the motif requires.

## Open TODOs / known debt

1. **Pre-existing test failure** (predates this work):
   `test_verba_external_model_produces_supply_chain_finding`. Root cause:
   `verba:GeneratorModel` (roles ExternalModel/PretrainedModel) is never bound
   by any motif match, and `risk_supply_chain.rq` only fires for match-bound
   elements. Fixing requires a semantic change to a motif or risk query —
   needs sign-off.
2. `risk_supply_chain.rq` references undefined roles `pat:ModelArtifactRole` /
   `pat:ServingImageRole` (defined roles are `pair:ModelArtifact` /
   `pair:ServingImage`) and undeclared roles `pair:ExternalDependency`,
   `pair:ExternalModel`, `pair:ThirdPartyPackage`,
   `pair:ExternalProviderCredential` (used in example graphs but not declared
   in `pair_ai_pattern.ttl`). Fixing changes query semantics — needs sign-off.
3. OECD `skos:exactMatch` URIs for autonomy/data facets: TODO markers (no
   resolvable OECD concept URIs found).
4. `task.ttl` second-level concepts are curated placeholders — reconcile with
   the paper's authoritative unified task taxonomy table before freeze.
5. `pat:VectorBasedInformationRetrievalMotif` provenance is the
   "expert curation" placeholder (origin unknown — please supply).
6. `docs/notes/*.md` still describe the pre-rename (v1) vocabulary; the
   glossary is authoritative, notes not yet rewritten.
7. TÜV AI.ST mappings still on hold (license unverified).
8. SSSOM export for the taxonomy mappings not yet generated (R6 mentions it;
   not in scope of Tasks 1–7).
