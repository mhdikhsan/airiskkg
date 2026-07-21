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

## Post-Task 7 addition — Data Category formalized as a facet (in place)

Glossary v1.1 A.3 classifies Data Category as a characterization facet; it was
modeled inside the pattern module before the facet layer existed. Decision:
**formalize in place, no URI migration** — `pair:containsDataCategory` values
are propagated along data flow (Rule R8 derived facts) and traversed via
`pair:subDataCategoryOf*` by ten applicability-condition queries, so moving
the namespace buys nothing and touches everything.

- `pair:DataCategoryScheme` (skos:ConceptScheme) declared; the 7 category
  values that were used but never declared now have definitions, scheme
  membership, `dct:source`, and verified DPV `skos:relatedMatch` links
  (`dpv:SensitivePersonalData`, `dpv:ConfidentialData`, `dpv:GeneratedData` —
  DPV v2.3, verified 2026-07-13): Information, SensitiveInformation,
  ConfidentialInformation, ExternalUserContent, GeneratedContent,
  PromptInstruction, UntrustedContent (TrustedContent already existed).
- Hierarchy edges added only INTO `pair:Information` (no query targets it);
  a header comment warns that edges into the three query-traversed roots
  (UntrustedContent, SensitiveInformation, PromptInstruction) widen results
  and need sign-off. ConfidentialInformation and ExternalUserContent are
  deliberately NOT under SensitiveInformation / UntrustedContent.
- `ontology/facets/implementation_type.ttl`: Implementation Type facet stub
  (extension point) + `facet:hasImplementationType` (domain `beam:Model`) —
  the facet counterpart to Task 4's "no Model implementation subclasses".
- Cross-references added in `data_facets.ttl` and the `pair:DataCategory`
  class comment; imports aggregator updated.
- Verified: assessment findings on uc6 / verba / onyx byte-identical
  (0 triples added or removed); all tests unchanged.

BEAM structural classes (Model, Process, Data, ...) stay OWL classes — R1:
they are instantiated, query-traversed structure; only their classification
values (implementation type, task, autonomy, data categories) are facets.

## Post-Task 7 addition — DPV personal_data module reuse widened

The DPV alignment was limited to identifiability. The DPV **personal_data
module** (`https://w3id.org/dpv/2.3/modules/personal_data`, verified
2026-07-15) defines the whole `dpv:Data` hierarchy, so the facet layer now
reuses it fully (Rule R3, URIs only, nothing copied):

- New `facet:hasPersonalDataCategory` (domain `beam:Data`): intended values
  are `dpv:PersonalData` and narrower (`dpv:SensitivePersonalData`,
  `dpv:SpecialCategoryPersonalData`, `dpv:IdentifyingPersonalData`,
  `dpv:CollectedPersonalData`, `dpv:DerivedPersonalData`,
  `dpv:InferredPersonalData`, `dpv:GeneratedPersonalData`) plus
  `dpv:NonPersonalData` / `dpv:AnonymisedData`; fine-grained categories via
  the DPV-PD extension (`https://w3id.org/dpv/pd#`).
- `facet:hasIdentifiabilityLevel` is now `rdfs:subPropertyOf` it (the
  identifiability axis of the same module); `dct:source` on both points at
  the module URL.
- OECD provenance concepts gained verified `skos:closeMatch` links to their
  DPV counterparts: `dataf:ProvidedData`→`dpv:ProvidedData`,
  `dataf:ObservedData`→`dpv:ObservedData`, `dataf:DerivedData`→
  `dpv:DerivedData`, `dataf:SyntheticData`→`dpv:SyntheticData`
  (`dataf:ExpertInput` has no DPV counterpart, left unmapped).
- Verified: all TTL parse; motif matches / findings on onyx (107/318),
  uc6 (61/189), verba (46/172) unchanged — metadata-only change.

## Post-Task 7 addition — DPV/DPV-AI reuse across all facets

Previously most facets carried only a `dct:source` citation string toward
DPV/OECD — informative for humans, not machine-actionable, and weak on FAIR
interoperability (no resolvable link a tool could follow). Added real
`skos:*Match` links wherever a verified DPV or DPV AI-extension counterpart
exists, checked against the live spec (`https://w3c-cg.github.io/dpv/2.3/`,
2026-07-15). Nothing is copied — only URIs and mapping edges (Rule R3):

- `aut:AutonomyLevel` (`autonomy.ttl`) mapped to DPV's `dpv:AutomationLevel`
  (ISO/IEC 22989:2022 levels 0-6) and `dpv:HumanInvolvement`: scheme-level
  `skos:relatedMatch`; `NoActionAutonomy`→`AssistiveAutomation`
  (relatedMatch, no clean level-0/1 correspondence); `LowActionAutonomy`
  `closeMatch` `PartialAutomation` + `relatedMatch`
  `HumanInvolvementForDecision`; `MediumActionAutonomy` `closeMatch`
  `ConditionalAutomation` + `relatedMatch` oversight/intervention; the top
  `HighActionAutonomy` `narrowMatch`es the three finer DPV levels
  (`HighAutomation`, `FullAutomation`, `Autonomous`) since it spans all three.
- `ctx:Domain` (`context.ttl`) `relatedMatch`es `dpv:Sector`, with
  `rdfs:seeAlso` the DPV sector-extension index
  (`https://w3id.org/dpv/sector`) and named health/finance/education/
  infrastructure/law/public-services extensions in the definition, replacing
  the vague "DPV sector extensions" citation. Checked `dpv:Context`/location
  concepts for a Deployment Setting counterpart — none exists, left
  unmapped, documented rather than silently absent.
- `task:AITask` (`task.ttl`) scheme-level `relatedMatch` to the DPV AI
  extension's `ai:Capability` (`https://w3id.org/dpv/ai#`, a neighboring
  axis per Rule R7, mapped not merged). Per-leaf mappings added where a
  verified Capability exists: `ImageClassification`, `ObjectDetection`,
  `SpeechRecognition`, `NamedEntityRecognition`, `TextGeneration`
  (→`NaturalLanguageGeneration`), `Summarization`
  (→`AutomaticSummarisation`), `Translation` (→`MachineTranslation`),
  `ImageGeneration`, `ConversationalAssistance` (→`ChatbotCapability`),
  `UserProfiling` (→`Profiling`) via `closeMatch`;
  `QuestionAnsweringOverKnowledge` `broadMatch`es the more general
  `ai:QuestionAnswering`; `RetrievalAndRanking`, `InteractionAndDialogue`,
  `PersonalizationAndProfiling`, `GenerationAndTransformation`
  `relatedMatch` their broader DPV counterparts. Checked and confirmed
  **no** DPV AI capability exists for: Recommendation, Forecasting/
  Regression, Anomaly/Drift/Fraud Detection, Decision/Optimization/Control,
  Code Generation, Embedding Computation, Deductive Reasoning, Knowledge
  Graph Completion, Agent Tool Use — left unmapped rather than forced.
- `impl:ImplementationType` (`implementation_type.ttl`, still a stub)
  `relatedMatch`es `ai:Technique`; TODO comment now names verified DPV AI
  technique concepts to reuse once the taxonomy is populated (
  `MachineLearning`, `DeepLearning`, `NeuralNetwork`,
  `ConvolutionalNeuralNetwork`, `RecurrentNeuralNetwork`, the five learning
  paradigms, `RuleBasedTechnique`, `SymbolicReasoning`, `BayesianNetwork`,
  `SupportVectorMachine`, `DecisionTree`, and `ai:LLM` — DPV has no
  "Transformer" architecture concept yet).
- All mapping URIs verified to actually resolve as `rdfs:Class`/
  `skos:Concept` in the downloaded DPV core (`dpv.ttl`) and AI extension
  (`ai.ttl`) Turtle, not just skimmed from HTML.

Metadata-only: all TTL parses; motif matches / findings on onyx (107/318),
uc6 (61/189), verba (46/172) unchanged.

## Post-Task 7 addition — DPV entity alignment (scope-corrected)

**Agreed scope for DPV reuse (2026-07-15): data categories (facet layer
only) and entities such as human/agent actors — not BEAM's general
structural classes.** Tool4Boxology, not DPV, is the adapter for BEAM's
Data/Model/Process/System classes (same architecture-diagram domain,
closer fit; see Task 6). An earlier version of this addition over-reached
by also aligning `beam:Data`/`Model`/`Process`/`System` to the DPV AI
extension — corrected in place, not left as dead history to work around.

New `ontology/alignments/dpv_alignment.ttl`, one axiom:

- `beam:Agent rdfs:subClassOf dpv:Entity` — `dpv:Entity` is "a human or
  non-human 'thing' that constitutes as an entity" (DPV v2.3, verified
  2026-07-15), matching `beam:Agent`'s actual breadth (human actors, e.g.
  a human reviewer node, as well as AI/software agents). Deliberately
  **not** aligned to the narrower `dpv:Agent` (means "acting on behalf of
  another Entity, authorised to do so" — a delegated-authority relation,
  not what `beam:Agent` means) or to the AI extension's `ai:AIAgent`
  (would wrongly imply every `beam:Agent` instance, including human
  actors, is an AI agent — a real correctness bug in the earlier version,
  not just a scope overreach).
- Documented, not added: if BEAM ever splits `beam:Agent` into human vs.
  AI/software subtypes, `dpv:NaturalPerson` ("a human") and the AI
  extension's `ai:AIAgent` are the verified anchors — not added now
  because the BEAM subtypes don't exist (no speculative structure).

Same placement rule as Tool4Boxology: nothing external enters
`beam_core.ttl`; the axiom lives in the alignments adapter. Purely
additive and inert for assessment: not consumed by motif SPARQL (no OWL
reasoning runs during motif matching) and not in the pipeline's load path
(`CORE_FILES` / `imports.ttl`) — confirmed zero-diff on TTL parsing and
the full test suite.

## Post-Task 7 addition — "Import Tool4Boxology" in the workbench

Previously `normalize_t4b.py` was CLI-only (`python python/scripts/
normalize_t4b.py export.nt`); bringing in a Tool4Boxology export required
leaving the workbench. Wired the same normalization into the UI, mirroring
the existing "Import XML" (draw.io) flow:

- New `python/src/airiskkg/t4b_import.py`: the normalization logic (case
  URI fixes, BEAM materialization via the alignment adapter, DesignPattern
  provenance) moved out of the CLI script into the installed package, so
  both the CLI and the webapp share one implementation — same pattern as
  `drawio_import.py`. Adds `normalize_text()` / `t4b_to_ttl()` for
  in-memory (no temp file) use; `normalize(export_path)` kept identical
  for `test_t4b_roundtrip.py`, which still imports it unchanged.
  `python/scripts/normalize_t4b.py` is now a thin CLI wrapper.
- New `POST /api/import/t4b` endpoint (`webapp/app.py`): N-Triples or
  Turtle text in, BEAM Turtle + human-readable import notes out (counts
  of case-normalized / materialized / provenance triples, plus the same
  "no roles/data categories yet - use Draw mode" hint the draw.io importer
  gives).
- New **"Import T4B"** toolbar button next to "Import XML"
  (`index.html`/`app.js`): picks N-Triples vs. Turtle by file extension,
  loads the normalized result into the editor, shows the import notes in
  the validation drawer - exact same UX shape as the XML importer.
- Tests: 3 new endpoint tests (`test_webapp_endpoints.py`) covering the
  vendored sample export, empty input, and malformed input. Full suite:
  32 passed (up from 29) + the one pre-existing unrelated failure.
- Verified end-to-end over a live server: import → live preview (20
  nodes/20 edges) → SHACL validate (0 violations, 29 warnings) on the
  vendored `sample_export.nt`.

## Post-Task 7 addition — Draw mode UI fixes, "Import XML" removed

- **Removed "Import XML" (draw.io/diagrams.net import)** entirely: UI button,
  `POST /api/import/drawio`, `drawio_import.py`, and its dedicated test file.
  Unlike Tool4Boxology, it had no real mapping logic behind it - just regex
  guessing of element kind from shape style/label text - and gave a false
  impression of being an adapter on the same footing as Tool4Boxology.
  "Import T4B" (real alignment-backed) is unaffected.
- **Draw mode property panel reworked**: pattern roles / data categories were
  native `<select multiple>` widgets, wrapped in a `<label>`. Two compounding
  problems: (a) a plain click on an option in a native multi-select *replaces*
  the whole selection rather than adding to it (ctrl/cmd-click required, not
  discoverable) - unusable for a list of 80 pattern roles; (b) wrapping
  multi-control widgets in a `<label>` is an HTML footgun - clicking any
  non-control area inside a label forwards the click to the label's *first*
  control, so clicks elsewhere in the widget could silently toggle the wrong
  checkbox. Replaced with a purpose-built checkbox list (`checkList()` in
  `draw.js`): a filter box for the 80-role list, removable chips showing the
  current selection by label (not just a count), and the widget's own
  container is a `<div>`, never a `<label>`. Delete node/edge buttons given
  explicit `type="button"`.
- Node labels on the Draw canvas now show both role *and* category counts
  (previously only roles), so annotation state is visible without opening
  the panel.
- No backend change was needed: `architecture_builder.build_ttl()` already
  emitted `pair:playsRole` / `pair:containsDataCategory` correctly from
  `resources[].roles` / `resources[].dataCategories` - the gap was entirely
  in the frontend's ability to reliably *set* those arrays. Verified via
  `POST /api/build` with a roles/categories-bearing model: both predicates
  appear in the output Turtle.
- Full suite: 28 passed (32 minus 4 removed drawio tests) + the one
  pre-existing unrelated failure.

## Engine consistency cleanup (2026-07-16, commits 0db7293..e094830)

Executed the plan in `docs/claude/engine_consistency_cleanup_plan.md`
(analysis of LLM-curation drift across vocabulary / motif library / risk
pattern library / queries / examples). Six commits, one per phase:

- **Phase 1** (`0db7293`): declared 9 roles that queries/examples already
  used (ExternalDependency family, SystemPrompt, OutputValidationStep,
  RateLimitControlStep, ToolInvocationStep, StateChangingStep); fixed 4
  wrong-namespace URIs; fixed the doubly-dead DirectPrompting branch of
  risk_unbounded_consumption.rq (drifted pattern-node names AND a SPARQL
  group-scoping bug in `FILTER(?motif = ...)`); asserted both directions
  of all motif↔risk-pattern links; re-minted `uc6:ProductInformation`.
  Delta: onyx +1 unbounded-consumption (documented behavior firing for
  the first time); all else identical.
- **Phase 0** (`d6e5023`): `python/tests/test_library_consistency.py` —
  9 mechanical cross-reference checks; a hallucinated URI is now a test
  failure, not a silently dead rule.
- **Phase 2** (`3de5dce`): removed the R2 leak from match_embeddings.rq by
  restoring the query to its own declared ODP (ChunkingStep +
  SourceDocument role constraints replace the facet read); annotated
  verba's chunking step/source doc with the roles they genuinely play.
  Zero diff.
- **Phase 3** (`506dd4c`): new `pat:ExternalDependencyMotif` + match query;
  risk_supply_chain.rq consumes its own motif's matches instead of
  free-riding on arbitrary ones. Verba supply-chain 0→4 —
  **the long-failing verba test now passes**; onyx 3→7 (one finding per
  actual external-usage site). Side effect flagged: improper-output-
  handling rose (onyx 1→3, verba 0→2) because generation steps are now
  match-bound; substantively correct for verba, duplicated per match
  (see D5 below).
- **Phase 4** (`9473eaa`): ODP declarations reconciled to OQP behavior for
  Embeddings/QueryRewriting/Reranker (phantom nodes removed, expected
  roles corrected, intent kept as comments). Declarative only, zero diff.
- **Phase 5** (`e094830`): **D1** — RAG motif relaxed (optional
  query-embedding leg; path-tolerant retrieval→prompt context via
  `(^beam:use/beam:produce)*` with the consumed context still role-checked)
  — the flagship motif now matches onyx (+1 match; +1 each
  prompt-injection / improper-output-handling / vector-embedding-weakness
  on onyx only). **D2** — MisinformationFromWeakGrounding kept, documented
  as awaiting its own OQP. **D4** — 4 unreferenced roles kept + annotated.

End state: full suite **38 passed, 0 failed** (verba test green for the
first time); SHACL 0 violations on all examples; consistency net green.

## Vocabulary provenance audit — pair_ai_pattern.ttl (2026-07-17)

User-requested audit of the pattern-role vocabulary for LLM-fabricated or
ambiguous concepts, with reuse of established vocabularies as the goal
(publication argument: every term is either reused or traceably curated).

**Provenance grounding (main change).** Every remaining role now carries a
`dct:source` and, where a verified counterpart exists, a SKOS mapping.
All mapping targets were checked against downloaded copies of the
vocabularies (never cited from memory):

- **Tool4Boxology** (`t4b:`, vendored): `Model` (closeMatch), `Process`→
  ProcessingStep (closeMatch), `Embed`→EmbeddingStep (closeMatch),
  `Infer`→Generation/PredictionStep, `Transform`→Chunking/PromptConstruction/
  QueryReformulation/Preprocessing, `Artifact`→ResourceRole, `KG`/`DB`→
  KnowledgeSource/stores, `Tensor`→EmbeddingVector,
  `SelfSupervisedEmbeddingModel`→EmbeddingModel, `Train`→TrainingStep.
- **DPV-AI** (`ai:`, verified 2026-07-16): `LLM`→FoundationLLM (closeMatch),
  `FineTunedModel` (closeMatch), `TrainedModel`→PretrainedModel (broadMatch) /
  ModelArtifact, `GPAIModel` (EU AI Act)→Pretrained/FoundationLLM,
  `GenAI`→GenerativeModel, `InformationRetrieval`→Retrieval/search steps,
  `NaturalLanguageGeneration`→GenerationStep, `ModelTraining`/`ModelFineTuning`
  (closeMatch)→Training/FineTuningStep, `DataPreparation`→PreprocessingStep,
  `Benchmarking`→EvaluationStep, `DeploymentStage`→DeploymentStep,
  `TrainingData` (closeMatch)→TrainingDataset.
- **AIRO** (`airo:`, verified 2026-07-16): `RiskControl` (ISO/IEC 31073,
  3.3.33)→ControlStep, `Input`→UserInput, `Output`→UserFacingOutput,
  `AIModel`→Model. DPV core: `RiskMitigationMeasure`→ControlStep,
  `ProvidedData`→UserInput.
- **Pattern-catalog roles** now cite the catalog page that introduced them
  (same URLs as the motifs that use them): Mercari ML system design patterns
  (all MLOps serving/training/operation roles) and martinfowler.com GenAI
  patterns (all RAG/GenAI roles). Derived mechanically from each motif's
  `dct:source` — the role vocabulary was distilled from these published
  catalogs, not free-invented.
- Remaining `"expert curation"` labels are now honest and few
  (PublicUserInput, PublicUserFacingOutput, Information,
  ExternalUserContent, PromptInstruction, UntrustedContent, TrustedContent).

**Removed (unused + unsourced):** the 10 deprecated v1.1 aliases
(`MotifInterpretation`, `AIRiskPattern`, `GraphCondition`,
`hasInterpretation`, `interpretsMotif`, `hasInterpretationCondition`,
`interpretedAsMechanism`, `implementsInterpretation`,
`hasInterpretedMechanism`, `hasEvidenceElement` — one release elapsed,
zero references outside generated outputs) and 4 roles referenced by no
query, motif, or example (`GuardrailModel`, `VectorRepresentation`,
`EvaluatedOutput`, `EvalDataset` — supersedes the D4 "keep" decision;
re-add with the Guardrails/Evals OQPs if needed). "Formerly named …"
migration comments removed with them.

**Boxology wording:** comments now say "Boxology class/flow predicate
(beam: namespace)" instead of "BEAM" — direction memo: BEAM specializes
the published Tool4Boxology, not vice versa (applies to future alignment
work too).

Verification: TTL parses (744 triples); suite 38/38; firing matrix
identical (onyx 13/22, uc6 3/7, verba 6/12) — all removals were dead URIs.

## Risk pattern library + taxonomy audit (2026-07-17)

User-requested audit of `risk_pattern_library.ttl` for fabricated (non-
evidence-based) content, plus a consistency check of the whole aligned-
knowledge layer against its claimed upstream sources. Method: downloaded the
actual IBM AI Atlas Nexus data (`risk_atlas_data.yaml`, `owasp_llm_2.0_data.
yaml`, `mit_ai_risk_repository_data.yaml`, `mit_ai_risk_mitigation_data.
yaml`) and SSSOM mapping sets (`ibm2owasp.tsv`, `mit-ai-risk-repository_
ibm-risk-atlas.tsv`, `mit_ai_risk_mitigation_mappings.tsv`) and compared
mechanically. Note: the cited repo `IBM/ai-atlas-nexus` is real (renamed
from `risk-atlas-nexus`); all cited paths resolve.

**Verified sound (no fabrication found):**

- All 11 risk patterns anchor to real OWASP LLM Top 10 2025 entries with
  faithful names/definitions; conditions/mechanisms are declared
  operationalizations attached to the right anchors.
- All Atlas risk concepts and MIT subdomains used exist upstream (matched
  by id/name against the Nexus data).
- All suggested-control lists mirror the mapping layer exactly.

**Fabrications / inconsistencies fixed:**

- `taxonomy_mapping.ttl` rewritten into two evidence tiers: Section 1 =
  upstream SSSOM rows with predicates exactly as curated upstream
  (prompt-injection↔llm01 is exactMatch, the llm02 privacy cluster is
  relatedMatch, atlas↔MIT rows are uniformly relatedMatch, etc.);
  Section 2 = project-curated rows, each with a stated rationale.
  Removed as contradicted or baseless: evasion-attack↔llm05,
  poor-model-accuracy↔llm08/llm09, impact-on-the-environment↔llm10
  (upstream: explicit noMatch, "not addressed by OWASP"),
  data-curation↔llm04 (upstream: llm03), prompt-injection/llm01↔
  subdomain-4-3, llm05↔7-3, llm06↔7-4, llm07↔7-4, and 7 more
  atlas↔MIT rows upstream maps elsewhere (full list in the file header).
- `risk_pattern_library.ttl`: mayIndicateRisk updated accordingly
  (ImproperOutputHandling −evasion-attack −7-3; VectorWeakness
  −poor-model-accuracy; Unbounded −impact-on-the-environment;
  PromptInjection −4-3; SystemPromptLeakage/ExcessiveAgency −7-4;
  Poisoning: data-curation → **atlas:data-poisoning** (the upstream-
  verified llm04 anchor, newly declared in `ibm_risk_atlas.ttl`);
  SupplyChain +data-curation). 14 deprecated alias blocks removed
  (`*Interpretation`, `DirectLLM*`) — referenced nowhere.
- **Declaration drift fixed**: `SensitiveDataRetrievalExposureRiskPattern`
  declared `hasMotif` RAG while its OQP consumes
  `VectorBasedInformationRetrievalMotif` matches — re-anchored to match the
  implementation; its deliberate reuse of the LLM08 retrieval condition is
  now documented in-file and as a named exception in the consistency net.
- `mit_air_risk_control.ttl`: the 16 concrete controls that are NOT MIT
  taxonomy subcategories (red-teaming, threat-modelling, input-output-
  filtering, retrieval-source-filtering, …) no longer claim
  `nexus:isDefinedByTaxonomy` MIT; each now cites its real evidence —
  a named mitigation in the MIT mitigation database (Risk Register, Red
  Teaming, Threat Modelling, Training Data Curation, …) or OWASP
  prevention guidance / DPV (`dpv:DataRedaction`), with `skos:broader`
  anchoring to the verbatim MIT subcategory. The subcategory layer itself
  verified verbatim against upstream.
- `owasp_llm.ttl`: `nexus:tag` values corrected to the actual upstream
  Nexus ids (`llm022025-…` style — 9 of 10 were wrong) and per-entry
  `rdfs:seeAlso` links to the official genai.owasp.org pages added.

**Regression net extended** (`test_library_consistency.py`, 9 → 13 checks):
pattern mechanism must belong to its anchor; conditions must operationalize
the anchor's risk conditions (documented exception list); directly suggested
mitctrl controls must be the anchor's related controls; every non-anchor
mayIndicateRisk entry must have a SKOS mapping path to the anchor.

Verification: suite **42 passed / 0 failed**; firing matrix identical
(onyx 13/22, uc6 3/7, verba 6/12) — only taxonomy-entry annotations on
findings changed, not which findings fire.

## Motif library audit (2026-07-17)

Same audit method applied to `motif.ttl` (24 motifs, 139 nodes, 134 edges):

- **No fabricated motifs found.** All 13 Mercari catalog pages and the
  martinfowler.com GenAI patterns article were fetched and verified: every
  page resolves and documents the pattern the motif claims (Direct
  Prompting, Embeddings, Evals, RAG, Hybrid Retriever, Query Rewriting,
  Reranker, Guardrails, Fine Tuning all appear as sections in the Fowler
  article). Structure spot-checks (PredictionLoggingMotif vs the Mercari
  prediction-log page; GuardrailsMotif vs Fowler's input/output guardrails)
  confirmed faithful distillation.
- **Mechanical checks clean**: every `pair:expectedClass` target exists in
  beam_core; the only flow predicates used are beam:use / beam:produce /
  beam:inform; no risk-flavored language in motif descriptions (risk
  neutrality, Rule R1/R2); no stray typed entities.
- **Fixed**: `VectorBasedInformationRetrievalMotif` — the one unattributed
  motif ("expert curation", no derivedFrom; debt item 6) — grounded as the
  factored-out retrieval stage of the RAG/Retriever pattern with
  `pair:derivedFrom` to the Fowler article and OWASP LLM08 named as the
  risk-side scope. Ontology header now states the provenance policy
  (motifs are cited distillations, verified 2026-07-17).

## Facet layer audit (2026-07-17)

Same audit method applied to `ontology/facets/` (6 files):

- **All 35 SKOS mapping targets verified**: every `skos:*Match` in
  autonomy/context/data_facets/implementation_type/task resolves in the
  downloaded DPV v2.3 / DPV-AI vocabularies (autonomy's automation levels,
  the 17 task↔ai: mappings, data provenance closeMatches, `dpv:Purpose`,
  `ai:Technique`, …). Zero hallucinated URIs.
- **OECD decision (closes debt item 4)**: verified via oecd.ai that the
  OECD Framework for the Classification of AI Systems exists only as a
  report — no resolvable concept URIs. All "exactMatch once OECD publishes
  URIs" TODO markers replaced by a documented decision: OECD anchoring is
  citation-level. Each task top-level concept now names its OECD Task &
  Output task type in `dct:source` (Recognition, Event detection,
  Forecasting, Personalisation, Interaction support, Goal-driven
  optimisation, Reasoning with knowledge structures);
  RetrievalAndRanking and GenerationAndTransformation explicitly state
  they have NO OECD counterpart (2022 typology predates GenAI-era tasks)
  rather than force-fitting one.
- **Fabricated citation fixed**: `ctx:DeploymentSetting` cited a
  nonexistent OECD "Context dimension" — corrected to the Economic
  Context dimension (criticality of function, breadth of deployment),
  with the framework's five real dimensions named in the correction note.
- **Still user-blocked (debt item 5)**: task.ttl's second level remains a
  curated placeholder pending the paper's authoritative unified task
  taxonomy table, now marked "user input required".

## Provenance & consistency audit — consolidated summary (2026-07-16/17)

End-to-end audit of the LLM-curated knowledge stack for hallucinated,
fabricated, or unevidenced content. This section is the one-stop record;
the per-layer sections above hold the details.

**Method** (applied uniformly to every layer):

1. Download the claimed source (never cite from memory): Tool4Boxology
   vendored ontology, DPV v2.3 + AI extension, AIRO, the IBM AI Atlas
   Nexus YAMLs and SSSOM mapping sets, all 13 Mercari pattern pages, the
   martinfowler.com GenAI patterns article, OECD publications.
2. Mechanically cross-reference every URI, mapping, tag, and citation
   against the downloaded evidence (scripts over RDFLib + YAML/TSV).
3. Classify each item: upstream-verified / evidence-corrected /
   honestly-curated (rationale stated in-file) / fabricated (removed).
4. Gate every change on the firing matrix (must be explainable; it stayed
   byte-identical through the whole audit) and the pytest consistency net,
   which was extended so recurrence becomes a test failure.

**Results by layer** (one commit each):

| Layer | Commit | Verdict | Key fixes |
| --- | --- | --- | --- |
| Role vocabulary (`pair_ai_pattern.ttl`) | `e8a08ef` | Distilled from real catalogs, not free-invented | Every role sourced + SKOS-mapped (T4B/DPV-AI/AIRO/DPV); 10 deprecated aliases + 4 dead roles removed; Boxology wording |
| Taxonomies + mappings (`ontology/taxonomy/`) | `881c027` | Concepts real; **cross-taxonomy links were the fabrication hotspot** | Mapping file split into upstream-SSSOM vs curated tiers; contradicted links removed; `atlas:data-poisoning` added; 9/10 wrong `nexus:tag` ids fixed; 16 pseudo-MIT controls re-provenanced; 14 deprecated aliases removed; SensitiveData `hasMotif` drift fixed |
| Motif library (`motif.ttl`) | `329f487` | Clean — all 24 motifs trace to verified published patterns | VectorIR motif grounded (was the one unattributed motif); provenance policy in header |
| Facet layer (`ontology/facets/`) | `92d426b` | Clean — all 35 SKOS targets verify | Nonexistent OECD "Context dimension" citation corrected; speculative OECD-URI TODOs → documented citation-level decision |
| Consistency net (`python/tests/`) | `d6e5023` + `881c027` | — | 9 → 13 checks; anchor-alignment now enforced (mechanism, conditions, controls, taxonomy entries must align with each pattern's OWASP anchor) |

End state: suite **42 passed / 0 failed**; firing matrix unchanged
throughout (onyx 13 matches / 22 findings, uc6 3/7, verba 6/12); every
remaining `"expert curation"` label is deliberate and carries a rationale.

**What the audit deliberately did NOT cover**: the example graphs
(`onyx_danswer.ttl`, `verba_goldenverba.ttl`, `uc6.ttl`) are project-
authored models of real systems — their fidelity to the actual codebases
(which store really holds confidential data, which step really reranks)
was not audited and is a modeling responsibility, not a vocabulary one.
Likewise `nexus_taxonomy_core.ttl` is a project-defined meta-vocabulary
(adapted from the Nexus data model), not an external standard — say so if
published.

## Risk Mechanism: kept, clarified, instance-grounded (2026-07-17)

Reviewer-style question: "is the risk mechanism just text, or does it do
work in the matching?" Investigated by comparing every mechanism's text
against its pattern's applicability-condition labels.

**Decision: keep — not redundant with applicability conditions.** The two
play distinct roles, now stated explicitly in the ontology
(`pair:RiskMechanism` comment): the applicability condition is the
machine-checkable **gate** (the observable "what" — a `FILTER`/graph
clause that decides whether a finding fires); the mechanism is the curated
causal **explanation** (the "why it's a risk"). The data confirms they are
not restatements — e.g. supply-chain's condition ("an external dependency
is used") is risk-neutral on its own; the mechanism ("...is compromised,
unverifiable, or insufficiently governed") supplies the harm account. The
mechanism is deliberately **not** part of detection logic: encoding it as a
second graph condition would duplicate the applicability condition and
reintroduce the declarative/executable (ODP/OQP) drift this project spent
the prior sessions auditing out.

**Improvement: instance grounding via `pair:mechanismNarrative`.** The
weakness was real — the finding attached only an opaque mechanism IRI, and
the same generic sentence appeared on every finding of a pattern. Each
finding now also carries a rendered narrative: the pattern's canonical
curated causal text (reused **verbatim** from the mechanism individual —
single source, no paraphrase, so no drift surface) followed by an instance
frame naming the concrete matched elements. The reusable
`pair:hasDerivedMechanism` IRI pointer is kept for traceability; the
narrative complements it, it does not replace it.

Design points that make it clean:

- **Exactly one narrative per finding.** The frame is keyed only on
  match-stable elements (the generation step, output, external resource,
  etc.), never on fan-out sets. Two structurally-different queries
  (`risk_vector_embedding_weakness`, `risk_data_model_poisoning`) that bind
  every matched element are anchored at the motif level instead of
  enumerating elements — otherwise vector-weakness alone emitted up to 12
  trivial "element X participates" sentences per finding.
- **Presentation only.** The added `OPTIONAL`+`BIND` introduce no `FILTER`
  and no new join constraint; the firing matrix is byte-identical (onyx
  13/22, uc6 3/7, verba 6/12). All element references are `COALESCE`-guarded
  so an unbound var never blanks a narrative (0 missing across all
  examples).
- Local names use `STRAFTER`/`IF`, not SPARQL `REPLACE` (the latter makes
  rdflib pass `count` positionally to `re.sub`, emitting a
  `DeprecationWarning` per row — ~13k in one run; avoided).

Note: the narrative makes the **D5** duplication visible (several
near-identical prompt-injection findings on one system now read as
several identical narratives) — this is honest surfacing of the existing
per-match keying, not a new defect; D5 remains the open re-keying decision.

Verification: suite **42 passed / 0 failed**; consistency net accepts the
newly-declared `pair:mechanismNarrative`; firing matrix unchanged; warning
count back to baseline.

## Control mitigation layer: technical/non-technical + motif realization (2026-07-17)

New feature (data model + backend + workbench UI) driven by the
risk-to-mitigation connection analysis: present a finding's suggested
controls in two tiers, and for the architecturally-detectable technical
controls, suggest the motif(s) that can structurally realize them.

**Data model.** Two new properties in `pair_ai_pattern.ttl`:
`pair:controlNature` (→ `pair:TechnicalControl` / `pair:NonTechnicalControl`,
a small `pair:ControlNatureScheme`) and `pair:realizedByMotif`
(control → motif). New file `ontology/patterns/control_mitigation_layer.ttl`
classifies all 33 suggested controls (12 `pat:Control_*` + 21 `mitctrl:*`)
and adds motif-realization links for the 10 motif-expressible ones. The
classification rule is stated in-file (the MIT grouping is functional, not
a technical/non-technical axis — so the cut is a stated PAIR-AI
interpretation, kept out of the pristine taxonomy files). All links are
candidate associations; "realized by motif X" is an *assumed* structural
mitigation, not a proof the motif removes the risk.

Motif-realization links (the situated-suggestion tier):

- Grounding/verification (and retrieval-quality) → RAG, Vector-based IR,
  Hybrid Retriever, Reranker — this makes the headline scenario work: a
  Direct-Prompting-without-grounding (LLM09 misinformation) finding now
  suggests "realize by adding: RAG / Vector-based Information Retrieval …".
- Guardrail / input-output / content-safety controls → Guardrails motif.
- Logging/monitoring/evals, post-deployment monitoring → Prediction
  Logging / Prediction Monitoring / Evals motifs.

**Backend.** `assessment_view._control_ref` adds `nature`
("technical"/"non-technical"/null) and `realizedByMotifs` to every
suggested control in the assessment JSON.

**UI.** `app.js` renders suggested controls in two labeled tiers
(Technical / Non-technical mitigations); each technical control with a
realizing motif shows a "realize by adding motif: …" chip row. `style.css`
adds the tier headings and motif-suggestion chip.

**Wiring & tests.** New file added to the runner's `PATTERN_FILES` and the
consistency net's `libraries` fixture. Two new checks (suite 42 → **44**):
every suggested control has a `controlNature`; every `realizedByMotif`
target is a declared motif. Firing matrix unchanged (onyx 13/22, uc6 3/7,
verba 6/12).

Flagged for review (first-pass curation, adjust as needed): the
technical/non-technical call on borderline controls (e.g. access-management
and data-minimization classed technical by architectural-footprint;
privacy-control and provenance classed non-technical by governance-weight),
and the retrieval-quality→Reranker/Hybrid links (improvement, not strict
"evaluation"). Also relevant: open item #3 (FoundationLLM not under
GenerativeModel) — a bare Direct-Prompting graph only fires the grounding
finding when its model plays `pair:GenerativeModel`, not `pair:FoundationLLM`.

## Taxonomy mapping: recheck + CSV-regrounded control links (2026-07-17)

Prompted by a "this looks suspicious" review of `taxonomy_mapping.ttl`
against the PAIR-AI risk-to-mitigation CSV (`Final_Mapped_Taxonomy_Table_
Output`, the OWASP→IBM→MIT-action embedding mapping).

**Recheck result — the upper mapping is sound.** Every OWASP↔IBM skos edge
where our mapping and the CSV overlap agrees **10/10, zero disagreements**
(both trace to IBM's data). So Sections 1–2 were not the problem. The CSV
also confirmed real limits: it covers only LLM01–06 + 09 (no rows for
LLM07/08/10), references 19 IBM risks we don't declare, and carries the
caveats its own reference doc states (embedding-matched, cosine top-3,
unvalidated) plus one internal rollup error (action A0973 filed under
sub-category 2.3 but tagged Category 3) and capitalization drift.

**What was actually weak — the control-grounding layer (Section 3).** The
`owasp:* nexus:hasRelatedControl mitctrl:*` links were hand-curated, not
evidence-based. Regrounded (bounded to Section 3, user-approved) from the
CSV's action→sub-category rollup: for each of LLM01–06 + 09, the risk's
mapped mitigation actions are rolled up to their MIT sub-categories and
mapped 1:1 to our `mitctrl:*` group concepts. LLM07/08/10 keep their prior
curated links (absent from the CSV). Reverse `mitigatesRiskTaxonomyEntry`
links regenerated as the exact inverse so the file stays consistent.
Sub-category approximations where we omit a concept, noted in-file: 2.2
Model Alignment→model-safety-engineering, 4.4 Governance Disclosure→
risk-disclosure, 4.5 Third-Party System Access→access-management. Mapping
by sub-category number sidesteps the A0973 category-rollup error. These are
labeled CANDIDATE (embedding-derived baseline pending human adjudication).

**Consequence — a deliberate decoupling.** The regrounded
`hasRelatedControl` (taxonomy evidence baseline) now diverges from the risk
patterns' curated `pair:suggestedControl` (what findings show). These are
now distinct provenance layers by design: the curated recommendation is the
more trustworthy and more actionable of the two. The anchor-alignment check
`test_direct_mitctrl_suggestions_are_anchor_related_controls` was relaxed to
`…_are_declared_controls` — it still guards against a hallucinated control
URI (existence), but no longer requires the curated suggestion to be a
subset of the (unvalidated) CSV rollup, which would be backwards.

Not done (bounded choice): no new IBM risks, no MIT-action layer, and
`pair:suggestedControl` in the risk patterns is unchanged — so the workbench
output is unchanged (firing matrix identical: onyx 13/22, uc6 3/7, verba
6/12). Follow-on option if desired: reground `pair:suggestedControl` from
the same evidence so findings and mapping fully agree. Suite 44/44.

## Follow-on: regrounded pair:suggestedControl to match the mapping (2026-07-17)

Completed the follow-on flagged above: the risk patterns' `mitctrl:*`
`pair:suggestedControl` are now regrounded from the same CSV evidence, so
findings and the taxonomy mapping fully agree. For each LLM01-06/09 pattern,
its `mitctrl:*` suggestions were replaced with its OWASP anchor's
(CSV-grounded) `nexus:hasRelatedControl` set; LLM07/08/10 already matched.
The `pat:Control_*` layer (PAIR-AI's own actionable controls, with the
technical/non-technical classification and `realizedByMotif` links) was left
untouched on every pattern.

- 10 newly-referenced control groups classified in
  `control_mitigation_layer.ttl` (model-safety-engineering and
  post-deployment-monitoring technical + motif; the 8 governance/disclosure
  groups non-technical).
- The relaxed anchor test was **restored and strengthened**:
  `test_direct_mitctrl_suggestions_agree_with_anchor_mapping` now enforces
  that every suggested `mitctrl:*` control is a `hasRelatedControl` of the
  pattern's anchor - the finding↔mapping agreement is guarded going forward.
- Finding counts unchanged (suggestedControl doesn't gate firing); only the
  controls each finding carries changed. Suite 44/44.

**Lossiness to be aware of (flagged).** Because the CSV rollup is coarser
and embedding-matched, regrounding *dropped* some intuitively-relevant
`mitctrl:*` anchors in favour of governance-heavy groups - e.g. the
sensitive-information finding lost `mitctrl:privacy-control-for-user-data`
and `mitctrl:retrieval-source-filtering`, gaining `risk-management`,
`societal-impact-assessment`, etc. The actionable equivalents survive in the
`pat:Control_*` layer (Control_DataMinimizationAndRedaction,
Control_RetrievalAccessControl), so findings still recommend the right
concrete actions - but the MIT taxonomy anchors are now coarser. Thinly-
covered risks are worst: llm04 → {data-governance, incident-response-
recovery}; llm05/06 → {safety-decision-frameworks, system-documentation,
user-rights-recourse} only. If this is too lossy, the alternatives are to
keep the union (curated ∪ CSV) or revert this step; the mapping itself
stays CSV-grounded either way.

## Open items

### Needs user decision or input

1. `task.ttl` second-level concepts are curated placeholders — reconcile
   with the paper's authoritative unified task taxonomy table before
   freeze (table not in repository; marked "user input required" in-file).
2. **D5 finding-identity dedup**: findings are keyed per motif match, so
   one generation step bound by several matches yields near-duplicate
   improper-output-handling findings. Re-keying on evidence elements is a
   semantic change to all risk queries' BIND clauses — needs sign-off.
3. Role-hierarchy question: `pair:FoundationLLM` is a sub-role of `Model`
   but not of `GenerativeModel`; making it one is cleaner but widens every
   query that targets GenerativeModel — needs sign-off.
4. `pair:ThirdPartyPackage` is declared (OWASP LLM03-sourced, part of the
   guided ExternalDependency picker family) but used by no query or
   example — keep for guidance or drop.
5. Curated mapping rows (Section 2 of `taxonomy_mapping.ttl`, esp. the
   owasp↔MIT links — no upstream OWASP↔MIT mapping set exists anywhere)
   are the project's own contribution; decide whether to present them as
   such in the paper (and/or propose them upstream to AI Atlas Nexus).
6. TÜV AI.ST mappings still on hold (license unverified).

### Engineering debt (no user input needed, not yet done)

1. **Facet operationalization** (user is implementing): only Data Category
   is read by conditions today; autonomy/context/data facets have no
   consuming applicability condition, the workbench has no system-level
   facet annotation panel, and the SHACL shapes don't validate facet
   values against their schemes.
2. **D3 consequence**: uc6's SystemPrompt yields no leakage finding
   because uc6's generation step is bound by no motif (strict
   match-anchoring kept by decision); uc6 needs a DirectPrompting/
   RAG-shaped generation leg or an annotation pass.
3. Unimplemented OQPs: 17 MLOps/Boxology motifs, GuardrailsMotif,
   EvalsMotif, and `MisinformationFromWeakGroundingRiskPattern` are
   declared knowledge without executable queries (guarded by the
   consistency net; ExcessiveAgency additionally has no motif at all —
   an agentic tool-use motif is missing from the library).
4. Upstream-fidelity regression: the audit verified against downloaded
   upstream data manually; the consistency net only checks *internal*
   coherence. Vendoring the upstream Nexus YAML/SSSOM snapshots (e.g.
   under `external/`) would let a test re-verify upstream fidelity
   offline and detect upstream drift.
5. SSSOM export of our own mappings not yet generated (R6) — now more
   pointed, since we verified *against* SSSOM; exporting Section 1/2 of
   `taxonomy_mapping.ttl` as SSSOM (with `mapping_justification` =
   curation tier) closes the loop and strengthens the FAIR story.
6. Pattern roles have no `skos:ConceptScheme` / `skos:inScheme` (the
   Data Category facet has one) — FAIR polish for publication.
7. `ontology/alignments/` should be re-checked against the 2026-07-16
   direction decision (BEAM specializes the published Tool4Boxology, not
   vice versa) — axioms and comments must state that direction.
8. `docs/notes/*.md` still describe the pre-rename (v1) vocabulary.

### Fixed (audit trail)

- ~~verba supply-chain test failure~~ (Phase 3) · ~~R2 leak in
  match_embeddings~~ (Phase 2) · ~~undeclared/wrong-namespace roles~~
  (Phases 1+3) · ~~OECD URI TODOs~~ (facet audit, documented decision) ·
  ~~VectorIR motif provenance~~ (motif audit) · ~~deprecated aliases,
  dead roles, fabricated taxonomy links, pseudo-MIT control provenance,
  wrong OWASP tags~~ (vocabulary + taxonomy audits).
