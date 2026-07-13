# Claude Code Task Prompt — AI-RKG Data Model Update


You are working on the `airiskkg` repository, which contains the ontologies and pattern
library for PAIR-AI, a design-time AI risk assessment method. The authoritative
terminology and modeling decisions are in `docs/reference/PAIR-AI_glossary_v1.1.md` — **read
that file first and treat its Section E rules (R1–R7) as hard constraints for every change you make.**

Relevant existing files:
- `ontology/core/beam_core.ttl` — BEAM architecture ontology (Element, System, Resource,
  Instance/Data/Symbol, Model, Process, Agent; relations use/produce/inform/participatedIn/contain)
- `ontology/core/beam_core_risk.ttl` — BEAM Risk extension aligned with AIRO
- `ontology/core/pair_ai_pattern.ttl` — pattern meta-vocabulary (GraphMotif, PatternNode,
  PatternEdge, PatternRole, DataCategory, MotifMatch, MotifInterpretation, RiskFinding, ...)
- `ontology/patterns/motif.ttl` — motif library instances
- Python package `python/src/airiskkg` and `assessment_runner.py` with SPARQL CONSTRUCT queries

Work on a new branch `feature/characterization-layer`. Commit in small, labeled steps
(one commit per task below). After every task, ensure all `.ttl` files still parse with
RDFLib and existing SPARQL queries still run.

## Task 1 — Renames and divergence fixes (Glossary v1.1, Sections A and E)

These renames were agreed on 2026-07-13 and are recorded in
`docs/reference/PAIR-AI_glossary_v1.1.md` (v1.1).
For EVERY rename below: first grep all `.ttl`, `.rq`/SPARQL strings, and Python code for
the old URI/name, report what would break, then update ontology + queries + code in the
same commit. Keep the old URI as a deprecated alias
(`owl:deprecated true` + `dct:isReplacedBy` pointing to the new URI) for one release.

1. **Rename `rp:MotifInterpretation` → `rp:RiskPattern`.** The RDF entity now carries the
   same name as the concept it realizes (AI Risk Pattern = Motif + Applicability
   Conditions + Mechanism + Taxonomy Links + Controls). Update all rdfs:comments
   accordingly.
2. **Rename the condition class (currently `rp:GraphCondition` or similar — verify the
   actual name in pair_ai_pattern.ttl first) → `rp:ApplicabilityCondition`**, and replace
   "interpretation condition" wording with "applicability condition" in every comment
   and label.
3. **Demote `rp:EvidenceSubgraph` from a class to a property**: introduce
   `rp:hasEvidence` on `rp:RiskFinding` pointing to the matched subgraph (named graph
   or triple collection — inspect how evidence is currently materialized in
   `outputs/` and choose the least disruptive representation; flag as DESIGN DECISION).
4. **Split the pattern instances into two curated collections**: a Motif Library
   (risk-neutral motifs) and a Risk Pattern Library (risk patterns with conditions,
   mechanisms, links, controls) — separate files or named graphs under
   `ontology/patterns/`, each entry keeping its provenance.
5. Change `rp:RiskFinding` so it is **no longer** `rdfs:subClassOf beamr:Risk`.
   Instead: `rp:RiskFinding` stands alone and gets a new object property
   `rp:identifiesCandidateRisk` (domain `rp:RiskFinding`, range `beamr:Risk`).
6. Fix any naming/namespace inconsistencies you find (mismatched prefixes, typos in
   URIs, labels that differ between ontology comments and class names). List every
   fix in the commit message.
7. Add a provenance slot for patterns: object property `rp:derivedFrom`
   (domain: `rp:GraphMotif` or `rp:RiskPattern`; range: open) plus
   `dct:source` annotations. Ensure every existing motif and risk-pattern instance
   in `ontology/patterns/` has at least a `dct:source` (use "expert curation" placeholder
   where the origin is unknown, and flag those to me in your final report).
8. Check ALL rdfs:comment strings in pair_ai_pattern.ttl for consistency with the
   glossary v1.1 definitions and fix mismatches.

## Task 2 — Characterization layer (new SKOS facet schemes)

Create a new directory `ontology/facets/` with one Turtle file per concept scheme.
All facet concepts are SKOS concepts (Rule R1: facets are never OWL classes to
instantiate). Namespace suggestion: `http://w3id.org/airiskkg/facets/<scheme>#`.

1. `autonomy.ttl` — scheme `AutonomyLevel` with concepts: NoActionAutonomy,
   LowActionAutonomy (HITL), MediumActionAutonomy (HOTL), HighActionAutonomy (HOOTL).
   Each concept: `skos:prefLabel`, `skos:definition`, `dct:source` referencing the
   OECD Framework for the Classification of AI Systems, and `skos:exactMatch`
   placeholders (TODO comments) for OECD URIs if any exist.
2. `data_facets.ttl` — schemes: DataProvenance (ExpertInput, ProvidedData, ObservedData,
   SyntheticData, DerivedData), DataDynamism (Static, PeriodicallyUpdated, RealTimeUpdated),
   DataRights (Proprietary, Public, Personal). Same annotation requirements.
   Do NOT create an identifiability scheme — see Task 3.
3. `task.ttl` — scheme `AITask` implementing the unified task taxonomy
   (top level: PerceptionAndRecognition, RetrievalAndRanking, PredictionAndForecasting,
   AnomalyAndEventDetection, GenerationAndTransformation, DecisionOptimizationControl,
   ReasoningOverKnowledge, InteractionAndDialogue, PersonalizationAndProfiling; add the
   second-level concepts from the taxonomy as `skos:narrower`). Add `skos:broadMatch` /
   `skos:relatedMatch` TODO placeholders toward OECD task categories. **Do not add any
   mapping to the TÜV AI.ST taxonomy yet — its license/citability is unverified.**
4. `context.ttl` — scheme(s) for Domain / Purpose / DeploymentSetting as extension
   points; where DPV has an equivalent (e.g., `dpv:Purpose`), reference the DPV URI
   via `skos:exactMatch` rather than redefining.
5. Attachment properties (put in a small `ontology/facets/facet_properties.ttl`):
   - `hasAutonomyLevel` (domain `beam:System`)
   - `hasDataProvenance`, `hasDataDynamism`, `hasDataRights` (domain `beam:Data`)
   - `hasTaskCategory` (domain `beam:Task`)
   - `hasDomain`, `hasPurpose`, `hasDeploymentSetting` (domain `beam:System`)
   All ranges are `skos:Concept` (optionally restricted per scheme via `rdfs:comment`,
   not OWL axioms — keep it lightweight).

## Task 3 — DPV reuse (no local copies)

For data identifiability and entity/actor types, reuse DPV directly (Rule R3):
- Add a property `hasIdentifiabilityLevel` (domain `beam:Data`) whose intended values
  are DPV concepts (IdentifiedData / PseudonymisedData / AnonymisedData etc.).
  Verify the exact current DPV URIs from https://w3id.org/dpv before writing them;
  if you cannot fetch them, insert TODO markers rather than guessing URIs.
- Do NOT copy DPV concept definitions into local files.

## Task 4 — BEAM structural additions

In `beam_core.ttl`, add Boxology-derived subclasses with `dct:source` on each:
- Under `beam:Data`: Number, Dataset, Tensor, Text, Image, Audio, Video, TimeSeries.
- Under `beam:Symbol`: Database, KnowledgeGraph, Label, Trace, Rules.
Do NOT add new object properties (Rule R5). Do NOT add Model subclasses beyond the
existing Semantic/Statistical split; implementation types belong to the facet layer.

## Task 5 — SHACL input contract

Create `shacl/architecture_input_contract.ttl` defining the minimal valid architecture
graph (this operationalizes Rule R4):
- Every graph must contain at least one `beam:System`.
- Every `beam:Process` must have at least one `beam:use` or `beam:produce`.
- Every `beam:Resource` must be typed to a leaf class (Data/Symbol/Model subtype)
  — severity `sh:Warning`, not Violation.
- Every element intended for motif matching should have at least one `rp:playsRole`
  — severity `sh:Warning`.
Add a `pyshacl` check to the test/CI setup and a make target or script
`scripts/validate_graphs.py` that validates any instance graph against the shapes.

## Task 6 — Tool4Boxology alignment adapter (ports-and-adapters boundary)

Tool4Boxology (https://github.com/SDM-TIB/Tool4Boxology, CC BY 4.0 / Apache 2.0;
paper: Bendler et al., "Tool4Boxology: A Semantic Toolbox for Constructing and Analysing
Neuro-Symbolic Architectures", ESWC 2026, DOI 10.1007/978-3-032-25159-6_11) is the
colleague's modeling tool and a source of architecture graphs for PAIR-AI. Its export
vocabulary has been **verified against the actual repository** — use exactly the URIs
below; do not invent additional ones. BEAM remains the canonical internal model.

**Verified export schema** (namespace `t4b:` = `http://tool4boxology.org/`,
export format N-Triples, see `KG/Tool4BoxologyKG.nt` in their repo):
- Predicates actually used: `t4b:hasPattern`, `t4b:hasInput`, `t4b:hasOutput`,
  `t4b:hasProcess`, `t4b:inputRoleParticipatesInProcess`,
  `t4b:outputRoleParticipatesInProcess` (plus rdf:type, rdfs:label).
- Verified edge directions:
  `InputArtifact --inputRoleParticipatesInProcess--> Process` and
  `Process --outputRoleParticipatesInProcess--> OutputArtifact`.
- Instances are multi-typed: `t4b:Component` plus a specific class (e.g., `t4b:Text`).
- `t4b:DesignPattern` instances group input/process/output per instantiated Boxology
  elementary pattern; their `rdfs:label` carries the elemental pattern ID
  (e.g., "1d Extract Relevant Information", "2a Possible Diagnosis").

Steps:

1. Vendor their two schema files and one export sample into `external/tool4boxology/`
   (`Tool4BoxologyOntology.ttl`, `easy-ai-schema.ttl`, a trimmed `sample_export.nt`)
   with a README noting license (CC BY 4.0 / Apache 2.0) and the citation above.
2. Create `ontology/alignments/tool4boxology_alignment.ttl`:
   - `t4b:inputRoleParticipatesInProcess rdfs:subPropertyOf beam:usedBy`
   - `t4b:outputRoleParticipatesInProcess rdfs:subPropertyOf beam:produce`
   - Class alignments (use `rdfs:subClassOf` toward BEAM, one per line, each with
     `rdfs:comment`): `t4b:Data`→`beam:Data`, `t4b:Symbol`→`beam:Symbol`,
     `t4b:Model`→`beam:Model`, `t4b:SemanticModel`→`beam:SemanticModel`,
     `t4b:Actor`→`beam:Agent`, `t4b:Train`→`beam:Train`, `t4b:Transform`→`beam:Transform`,
     `t4b:Infer`→`beam:Infer`, `t4b:Generate`→`beam:Generate`.
   - DESIGN DECISIONS to flag for my review: `t4b:Deduce`→`beam:Infer` and
     `t4b:Embed`→`beam:Transform` (no direct BEAM equivalents);
     `t4b:ReasoningAssumption` (OWA/CWA) left unmapped for now.
   - Note in comments that both vocabularies anchor to easy-ai
     (`https://kastle-lab.org/easy-ai2/`), which BEAM already references.
3. `scripts/normalize_t4b.py`: ingestion script that (a) loads a t4b N-Triples export,
   (b) **case-normalizes type URIs** (export uses lowercase like `t4b:transform` while
   the ontology declares `t4b:Transform` — verified data-quality issue), (c) materializes
   `beam:use`/`beam:produce` triples via SPARQL CONSTRUCT or owlrl reasoning while
   keeping original t4b triples, (d) converts each `t4b:DesignPattern` grouping into
   provenance: annotate the contained elements/subgraph with `dct:conformsTo` pointing
   to the Boxology elemental pattern ID parsed from the label — this feeds the motif
   derivation provenance (`rp:derivedFrom`) from Task 1, and (e) validates the result
   against the SHACL input contract from Task 5.
4. Round-trip test: their real `sample_export.nt` → normalizer → BEAM graph → run the
   existing motif queries; assert at least the basic process-flow triples materialize
   and SHACL passes.
5. Known upstream quirk (document in the alignment file, defensively handle in code):
   their ontology declares `t4b:patternProcess` but the export uses the URI
   `t4b:hasProcess` — target the **export** URIs, and note this mismatch in the
   changelog so I can report it upstream.

Scope guard: this adapter is the template for future vocabularies (e.g., AgentO).
Everything t4b-specific stays inside `external/tool4boxology/`,
`ontology/alignments/`, and the normalizer; nothing t4b-specific may enter
beam_core.ttl. No new BEAM classes or properties are needed for this task.

## Task 7 — Validation and report

- Parse all `.ttl` with RDFLib; run pyshacl on example instance graphs if present.
- Re-run the assessment pipeline (`assessment_runner.py`) on the existing two use-case
  graphs and diff the produced candidate risk graphs against the previous output.
  Any difference must be explained in the final report.
- Produce `CHANGELOG_data_model.md` summarizing: every fix from Task 1, every new file,
  every TODO left open (unverified DPV URIs, missing provenance, unmapped concepts).

## Hard constraints (from GLOSSARY.md Section E — do not violate)

- R1: OWL classes only for instantiated, traversed structure; SKOS for classification values.
- R2: never make motifs reference facets; facets are only for interpretation conditions.
- R3: import/reference external URIs (DPV, AIRO); never copy their definitions locally.
- R5: no new flow predicates in BEAM core; node types carry edge semantics. External
  vocabularies (tool4boxology, later AgentO) are aligned via rdfs:subPropertyOf and
  CONSTRUCT normalization in `ontology/alignments/`, never by extending BEAM's
  property set. The single sanctioned class addition is `beam:Modify` (Task 6).
- R6: every reused/adapted concept gets `dct:source`; mappings use SKOS mapping properties.
- R7: keep Task, Capability (VAIR), and Application Type as separate axes.
- Candidate framing: all comments/labels must say "candidate risk", never imply
  confirmed failures.
- Ask me before any change that would alter the semantics of existing motif SPARQL
  queries beyond the RiskFinding fix in Task 1.
