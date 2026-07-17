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

## Open TODOs / known debt

1. ~~Pre-existing verba supply-chain test failure~~ — **fixed** (Phase 3).
2. ~~R2 leak in match_embeddings.rq~~ — **fixed** (Phase 2).
3. ~~Undeclared/wrong-namespace roles in risk_supply_chain.rq~~ —
   **fixed** (Phases 1+3).
4. OECD `skos:exactMatch` URIs for autonomy/data facets: TODO markers (no
   resolvable OECD concept URIs found).
5. `task.ttl` second-level concepts are curated placeholders — reconcile with
   the paper's authoritative unified task taxonomy table before freeze.
6. `pat:VectorBasedInformationRetrievalMotif` provenance is the
   "expert curation" placeholder (origin unknown — please supply).
7. `docs/notes/*.md` still describe the pre-rename (v1) vocabulary; the
   glossary is authoritative, notes not yet rewritten.
8. TÜV AI.ST mappings still on hold (license unverified).
9. SSSOM export for the taxonomy mappings not yet generated (R6 mentions it;
   not in scope of Tasks 1–7).
10. **D5 (new)**: finding-identity dedup — risk findings are keyed per motif
    match, so one generation step bound by several matches yields several
    near-identical improper-output-handling findings. Decide whether finding
    IRIs should key on the evidence elements instead (semantic change to all
    risk queries' BIND clauses — needs sign-off).
11. **D3 (decided: keep strict match-anchoring)**: generation-path risk
    patterns (system-prompt-leakage, improper-output-handling) only fire when
    the generation path is match-bound. uc6's SystemPrompt annotation still
    yields no leakage finding because uc6's generation step is bound by no
    motif; uc6 would need either a DirectPrompting/RAG-shaped generation leg
    or a future annotation pass.
12. Unimplemented motifs (17 MLOps/Boxology motifs, GuardrailsMotif) and
    `MisinformationFromWeakGroundingRiskPattern` still have no OQPs —
    declared knowledge awaiting implementation, guarded by the consistency
    net.
