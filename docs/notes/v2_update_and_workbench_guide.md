# AI-RKG v2 Update & Architecture Workbench Guide

Branch: `feature/characterization-layer` · Status: 2026-07-15
· Authority: `docs/reference/PAIR-AI_glossary_v1.1.md` (locked)
· Detailed change record: `CHANGELOG_data_model.md`

This document has two parts: **Part 1** explains the v2 knowledge-graph
update (what changed, what is new, what is integrated, what is still open,
and what comes next). **Part 2** explains the new web workbench (how it
works, how to use it, and how candidate risk findings are pointed out
directly in the architecture diagram).

---

## Part 1 — The AI-RKG v2 data model update

### 1.1 Why v2

The v1 generation of the ontology (frozen, untouched, under `v1/`) predates
the glossary v1.1 decisions. Its vocabulary still spoke of "motif
interpretations" and "graph conditions", mixed structural and classification
concerns, had no characterization layer, no executable input contract, and
no boundary for external tool vocabularies. v2 realigns the RDF vocabulary
with the locked terminology and operationalizes the modeling rules R1–R8.

### 1.2 What was updated (renames and fixes)

Every rename keeps the old URI as a deprecated alias
(`owl:deprecated true` + `dct:isReplacedBy`) for one release. The namespace
`http://w3id.org/airiskkg/pair-ai#` (prefix `pair:`) is unchanged.

| Old (v1) | New (v2) | Meaning |
| --- | --- | --- |
| `pair:MotifInterpretation` | `pair:RiskPattern` | The AI risk pattern entity now carries the name of the concept it realizes |
| `pair:GraphCondition` | `pair:ApplicabilityCondition` | "Interpretation condition" wording retired everywhere |
| `pair:hasInterpretation` / `pair:interpretsMotif` | `pair:hasRiskPattern` / `pair:hasMotif` | Motif ⇄ risk pattern link |
| `pair:hasInterpretationCondition` | `pair:hasApplicabilityCondition` | Pattern → condition |
| `pair:interpretedAsMechanism` | `pair:hasMechanism` | Pattern → mechanism |
| `pair:implementsInterpretation` | `pair:implementsRiskPattern` | SPARQL implementation → pattern |
| `pair:hasInterpretedMechanism` | `pair:hasDerivedMechanism` | Finding → selected mechanism |
| `pair:hasEvidenceElement` | `pair:hasEvidence` | EvidenceSubgraph demoted to a property; evidence = the set of matched elements |
| `pat:*Interpretation` (11 instances) | `pat:*RiskPattern` | Risk Pattern Library instances |

New vocabulary: `pair:identifiesCandidateRisk` (finding → `beamr:Risk`;
a finding is assessment *output about* a possible risk, not the risk
itself — it is no subclass of `beamr:Risk`) and `pair:derivedFrom`
(derivation provenance on every motif and risk pattern).

Divergence fixes worth knowing about: the `EmbeddingMotif`/`EmbeddingsMotif`
URI mismatch, a duplicated RAG risk-pattern block, and the
Vector-based Information Retrieval motif that was *commented out* while its
matching query was still running — restored and re-linked. All 23 motifs and
11 risk patterns now carry `dct:source` + `pair:derivedFrom`.

### 1.3 What is new

**Characterization layer (`ontology/facets/`)** — the central v2 addition.
All facet values are SKOS concepts (R1), assigned by dedicated properties,
and read *only* by applicability conditions, never matched by motifs (R2):

| Scheme | File | Attachment property (domain) |
| --- | --- | --- |
| Autonomy Level (HITL/HOTL/HOOTL) | `autonomy.ttl` | `facet:hasAutonomyLevel` (System) |
| Data Provenance / Dynamism / Rights | `data_facets.ttl` | `facet:hasDataProvenance` / `hasDataDynamism` / `hasDataRights` (Data) |
| Data Identifiability | — (DPV reused, R3) | `facet:hasIdentifiabilityLevel` (Data) → verified DPV v2.3 URIs |
| AI Task (9 top branches) | `task.ttl` | `facet:hasTaskCategory` (Task) |
| Domain / Purpose / Deployment Setting | `context.ttl` | `facet:hasDomain` / `hasPurpose` / `hasDeploymentSetting` (System) |
| Implementation Type (stub) | `implementation_type.ttl` | `facet:hasImplementationType` (Model) |

**Data Category formalized as a facet, in place.** Glossary A.3 classifies
Data Category as a characterization facet; it stays in the pattern module
because it is the one facet with *derived* values (R8): untrusted-content
taint propagates along `beam:use`/`beam:produce`, and conditions traverse
`pair:subDataCategoryOf*`. All eight category values are now properly
declared (`UntrustedContent`, `SensitiveInformation`, `PromptInstruction`,
`Information`, `ConfidentialInformation`, `ExternalUserContent`,
`GeneratedContent`, `TrustedContent`) with DPV `skos:relatedMatch` links.
BEAM classes (Model, Process, Data …) deliberately remain OWL classes —
they are query-traversed structure, not classification values.

**BEAM structural additions.** Boxology-derived leaf types: 8 under
`beam:Data` (Number, Dataset, Tensor, Text, Image, Audio, Video, TimeSeries)
and 5 under `beam:Symbol` (Database, KnowledgeGraph, Label, Trace, Rules).
No new flow predicates (R5); no Model implementation subclasses (those are
the Implementation Type facet).

**SHACL input contract** (`shacl/architecture_input_contract.ttl`,
operationalizes R4): a graph must contain ≥ 1 `beam:System` and every
process needs ≥ 1 `use`/`produce` (Violations); resources should be typed to
leaf classes and elements should carry `pair:playsRole` (Warnings). Runnable
via `python/scripts/validate_graphs.py` and the workbench.

**Tool4Boxology alignment adapter** (`ontology/alignments/`,
`external/tool4boxology/`, `python/scripts/normalize_t4b.py`): the
ports-and-adapters boundary. Verified export vocabulary aligned via
`rdfs:subPropertyOf`/`rdfs:subClassOf`; the normalizer case-fixes the
export's type URIs, materializes BEAM flow triples, converts DesignPattern
groupings into `dct:conformsTo` provenance, and validates against the input
contract. Nothing tool-specific touches `beam_core.ttl`. This adapter is the
template for AgentO later.

**Third example use case** (`ontology/example/onyx_danswer.ttl`): Onyx
(formerly Danswer), modeled from the public MIT-licensed repo. First example
coverage for the QueryRewriting, Reranker, and DirectPrompting motifs, and
the first example where the supply-chain risk pattern fires (its external
models are bound inside motif matches). 5 matches, 12 candidate findings.

### 1.4 What is now integrated

- The assessment pipeline (`assessment_runner.py`) loads core + patterns +
  **facets** + taxonomies; `imports.ttl` aggregates all facet ontologies.
- SHACL validation is wired into tests, a CLI script, and the workbench.
- The Tool4Boxology ingestion path is round-trip tested: real export →
  normalizer → BEAM graph → motif queries + SHACL.
- All three examples produce findings that are stable under the rename
  (verified triple-identical modulo the two renamed finding predicates).
- The webapp exposes the whole loop: edit/draw → live preview → contract
  validation → candidate findings with evidence highlighting.

### 1.5 What is NOT improved yet (open debt)

1. **Facets are declared but not yet consumed.** No applicability condition
   reads `facet:hasAutonomyLevel`, provenance, identifiability, or context
   yet — the layer is an enabler waiting for facet-aware risk patterns.
2. **Pre-existing failing test** (`verba` supply-chain): the external model
   is never bound by a motif match, and `risk_supply_chain.rq` only fires
   for match-bound elements. Fix requires a semantic query change → sign-off.
3. **R2 leak**: `match_embeddings.rq` (a motif query) reads a data category
   (`FILTER NOT EXISTS … PromptInstruction`). Moving it into an
   applicability condition changes matching semantics → sign-off.
4. `risk_supply_chain.rq` references undeclared roles
   (`pair:ExternalModel`, `pair:ExternalDependency`, `pat:ModelArtifactRole`
   etc. are used in examples/queries but not declared in the ontology).
5. `task.ttl` second-level concepts and the Implementation Type scheme are
   curated placeholders pending the paper's authoritative taxonomies.
6. OECD facet concepts have TODO markers instead of `skos:exactMatch` (no
   resolvable OECD URIs found).
7. `docs/notes/*.md` older notes still describe v1 vocabulary.
8. SSSOM export for taxonomy mappings (R6) not generated yet.
9. TÜV AI.ST mappings on hold (license unverified).
10. Agents/Tasks: `beam:Agent`/`beam:Task` render in the preview but are not
    supported by the builder/Draw mode or the SHACL role warnings.

### 1.6 Next steps (suggested order)

1. **Make facets earn their keep**: add the first facet-aware applicability
   conditions (e.g. excessive agency requires
   `facet:hasAutonomyLevel ≥ MediumActionAutonomy`; sensitive-retrieval
   sharpened by `facet:hasIdentifiabilityLevel`). This is the scientific
   payoff of Task 2.
2. Decide the three sign-off items (verba supply-chain fix, R2 leak,
   undeclared roles) and apply them in one reviewed change.
3. Replace the task/implementation-type placeholders with the paper's
   taxonomies; resolve OECD mapping URIs.
4. Generate the SSSOM export for taxonomy mappings (R6).
5. Build the AgentO adapter using the Tool4Boxology template; then agentic
   examples (tool use, HITL) can exercise autonomy facets.
6. Rewrite the stale v1 notes; keep the glossary as single source of truth.

---

## Part 2 — The Architecture Workbench (web UI)

### 2.1 How it works

Start it with:

```
.venv\Scripts\python.exe -m airiskkg.cli serve        # http://127.0.0.1:5000
```

The page is a split-pane workbench, deliberately similar to Tool4Boxology:
**Turtle editor on the left, live diagram on the right**, connected through
a small Flask API:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/graph` | editor text → typed nodes + flow edges (live preview) |
| `POST /api/validate` | editor text → SHACL input-contract report |
| `POST /api/assess` | editor text → candidate findings + motif matches |
| `POST /api/build` | Draw-mode model → Turtle |
| `POST /api/import/drawio` | draw.io XML → Turtle + import notes |

Every (debounced) edit is parsed **server-side with RDFLib against the real
BEAM class hierarchy**, so the preview always shows exactly what the
assessment pipeline would see. Nodes are classified and drawn
boxology-style: **rectangles = processes**, **rounded boxes = data/symbols**,
**hexagons = models**, **ellipses = agents**. Edges follow the data flow
left-to-right: `use` arrows point *into* a process, `produce` arrows point
*out of* it, `inform` is dashed. Layout is automatic (layered by longest
path, crossing-reduced). If the Turtle has a syntax error, the offending
line is marked red in the gutter and the *last good* diagram stays visible.

### 2.2 How to use it

**Load something.** Toolbar → *Load example…* (`onyx_danswer` is the
richest), *Open .ttl*, *Starter* (a minimal RAG skeleton), or
*Import XML* (a draw.io diagram).

**Edit with live preview.** Type in the left pane; the diagram follows
about half a second after you stop. Click any node for a detail card:
BEAM type, pattern roles, data categories, URI. Pan by dragging, zoom with
the wheel, ⊞ fits the graph.

**Validate.** Toolbar → *Validate* runs the SHACL input contract. Results
appear in the bottom drawer (*Input contract* tab); clicking a row
highlights the offending element in the diagram. Fix Violations before
assessing; Warnings (missing roles, non-leaf types) mean weaker matching.

**Assess.** Toolbar → *Run assessment* executes the full PAIR-AI pipeline
(untrusted-content propagation → motif matching → risk-pattern evaluation)
and opens the *Findings* tab.

**Draw instead of typing.** Switch the right pane to **Draw**:

1. Drag components from the palette (Data, Symbol, Statistical/Semantic
   Model, Transform, Infer, Train, Generate) onto the canvas — or
   double-click a palette entry.
2. Connect components by dragging the small **○ port** of one node onto
   another. The edge kind is inferred from the endpoints
   (resource→process = `use`, process→resource = `produce`,
   process→process = `inform`); resource→resource is rejected, since BEAM
   flow always passes through a process.
3. Select a node to set its identifier, label, BEAM class, **pattern roles
   and data categories** — this annotation step is what makes the drawn
   system assessable (motifs match roles; conditions read categories).
   With nothing selected, the panel edits the system name/label.
4. **Generate Turtle →** writes the diagram into the editor;
   **⟵ From code** does the reverse and turns the current Turtle into an
   editable diagram (this also happens automatically when you enter Draw
   mode with a non-empty editor).

**Import a draw.io diagram.** *Import XML* accepts `.xml`/`.drawio` files
(plain or compressed). Shapes are mapped heuristically — hexagons and
model-ish labels become models, ellipses/cylinders become data, boxes with
process verbs become processes ("Train Model" is correctly a *process*) —
and arrows become flow edges. Because a plain diagram carries no roles or
categories, every guess is listed as an import note in the drawer:
**review the types in Draw mode and annotate roles/categories before
assessing**, otherwise few motifs can match.

### 2.3 How a candidate risk points at the flow in the diagram

This is the core interaction that makes findings interpretable:

Every candidate risk finding carries `pair:hasEvidence` — the **matched
subgraph elements** that triggered it (the same URIs as the diagram nodes).
When you click a finding card in the *Findings* drawer:

1. its evidence nodes get a **red ring** in the diagram,
2. everything else (nodes *and* edges) dims to ~20% opacity,
3. edges **between** evidence nodes stay fully visible.

What remains highlighted is therefore not a list of parts but the **risky
flow path through the architecture**. For example, clicking the *Candidate
prompt injection exposure* finding on the Onyx example lights up:

```
Retrieved candidate sections ──use──▶ Rerank ──produce──▶ Reranked sections
        (UntrustedContent)                                      │ use
                                                                ▼
                       Generator LLM ──use──▶ Generate answer ──produce──▶ Cited answer
                                                                    (user-facing)
```

— i.e. exactly the mechanism the risk pattern describes: untrusted retrieved
content can reach the generation step and its user-facing output. Clicking
the finding again (or the canvas background) clears the highlight; selecting
a different finding switches the path.

Each finding card also shows the **motif** it came from, the **risk
mechanism**, **taxonomy anchors** (OWASP LLM Top 10, IBM Risk Atlas, MIT AI
Risk Repository) and expandable **suggested controls**. Validation rows work
the same way: clicking one highlights the focus node that violates or warns
against the input contract.

Remember the framing: everything shown is a **candidate** risk — a
structural disposition identified at design time over the *submitted* graph
(open-world: an absent control means "not represented", not "absent in
reality") — never a confirmed failure.

### 2.4 Known UI limitations

- Preview→Draw conversion skips `beam:Agent`/`beam:Task` nodes (the builder
  has no agent support yet); they still render in Preview mode.
- Draw mode and the editor are synchronized *explicitly* (via the two
  buttons / mode switch), not live in both directions at once.
- XML import guesses element types; it never guesses roles or categories.
- Evidence highlighting requires the finding's evidence URIs to appear in
  the current editor content — if you edit the graph after assessing,
  re-run the assessment to keep findings and diagram in sync.
