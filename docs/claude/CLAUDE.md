# CLAUDE.md — airiskkg (PAIR-AI)

This file is read automatically by Claude Code at the start of every session.
It encodes the project context and the locked design decisions. Do not contradict it;
if a task seems to require violating a rule here, stop and ask.

## What this project is

PAIR-AI is a design-time AI risk assessment method. It matches **architectural motifs**
(reusable, type-level configurations of **pattern roles** connected by flow relations,
executed as SPARQL CONSTRUCT queries) against RDF **architecture graphs** of AI systems
(BEAM, the Boxology Notation vocabulary). A motif is risk-neutral by itself: it states
what structure is present, never whether that structure is dangerous. Risk enters only
when an **AI risk pattern** evaluates its **applicability conditions** over a motif match.
Satisfaction emits a **candidate risk finding** carrying evidence, a curated risk
mechanism, taxonomy links (IBM AI Risk Atlas / OWASP LLM Top 10 / OWASP Agentic Top 10 /
MIT AI Risk Repository / NIST AI 600-1), and suggested controls.

The constituent equation (glossary term 7):
**Risk Pattern = Motif + Applicability Conditions + Mechanism + Taxonomy Links + Controls.**

Mental model: static code analysis for AI architectures. Motifs ≈ linter rules,
findings ≈ alerts requiring human triage — never confirmed defects.

The library covers GenAI, ML serving/training, supply-chain, and agentic shapes.
Agentic coverage is deliberately partial: only ASI entries with a design-time
structural signature are modelled (ASI01 goal hijack, ASI02 tool misuse, ASI06
memory and context poisoning, ASI07 insecure inter-agent communication).
Entries defined by runtime behaviour have no shape in a submitted graph,
and adding them would fire a finding on every agent — noise that breaks candidate
framing instead of supporting it.

## Authoritative documents (read before non-trivial changes)

- `docs/reference/PAIR-AI_glossary_v1_3.md` — terminology and modeling rules, **v1.3**
  (supersedes v1.2, which is deleted; any surviving reference to `PAIR-AI_glossary_v1.2.md`
  is a broken link to fix). Four sections: **A** core terms (the nine defined entities),
  **B** internal and narrative terms, **C** modeling rules **R1–R10** — a hard constraint on
  every change — and **D** grounding references. The rename record and decision record that
  v1.2 carried as Sections E/F are gone; do not cite them.
- `docs/reference/PAIR-AI_method_and_construction.md` — how the knowledge base was built and how
  an assessment runs: risk-pattern derivation, role provenance, motif curation, ontology reuse
  and alignment, the pipeline, and current limitations.
- `docs/reference/catalogue.md` — the inventory of what the library can recognise and flag:
  every motif, risk pattern, annotation role, and data category. Written by hand against the
  loaded ontology, so it goes stale silently — re-check its counts whenever the library changes.
- `docs/reference/risk_control_linkage.md` — how risk patterns reach controls, including the
  MIT mitigation/action evidence layer.
- `CHANGELOG_data_model.md` — running record of data-model changes and past audits, including
  which layers were found to contain fabricated content and how each was fixed. Worth reading
  before touching the taxonomy or mapping layers. Local-only (gitignored).

## Locked decisions (summary — full versions in the glossary, Sections A and C)

- **Candidate framing is non-negotiable.** All outputs are *candidate* risks
  (structural dispositions), never confirmed failures, observed incidents, or predictions
  that harm will occur. Every comment, label, and doc string must respect this. Formal
  basis (R4): Open World Assumption — `FILTER NOT EXISTS` is closed-world over the
  submitted graph only, so "no validation control is represented" ≠ "none exists".
- **Motifs cannot express absence (R9).** Motif matching is monotone: if a motif matches
  a graph it matches every extension of it, so a motif asserts presence only. Every
  negative, exclusivity, or sufficiency claim (*direct*, *only*, *pure*, *without*,
  *unmediated*, *standalone*) belongs to an applicability condition, and motif labels must
  be positive accordingly. A risk pattern name may carry the negative; a motif name may not.
- **Motifs may nest, deliberately.** The library is not an antichain — a smaller motif can
  be a subgraph of a larger one and always co-matches with it. Match counts therefore
  measure structural coverage, not distinct architectural features; never report them as
  "how many different things the system does".
- **Facet conditions are positive; only control conditions may be negative (R10).** A
  condition may test for the presence of a facet value on a bound element, never its
  absence, unless the SHACL input contract makes that facet mandatory. Facets are annotated
  base facts (R8), so a missing value means the modeler did not fill it in — a negative
  facet condition fires on every under-annotated system. Absence-of-control conditions are
  exempt: they are claims about represented structure, already graph-relative under R4.
- **Conditions are evaluated over a motif match, not over the graph at large.** "Personal
  data is present somewhere in this system" and "the data bound to the prompt-context node
  is personal" are different claims; only the second licenses a finding.
- **`pair:hasMotif` is canonical, `pair:hasRiskPattern` is a required mirror.** The binding
  is authored on the risk pattern, because the motif is a constituent of the pattern. **No
  OWL reasoning runs in the pipeline** — `owl:inverseOf` is declared as documentation only,
  so a one-sided assertion is invisible to any consumer reading the other side. Write both
  directions; `test_library_consistency.py` enforces it.
- **Mechanisms are curated, never computed.** A `pair:RiskMechanism` takes no part in
  detection: it is never evaluated or filtered on during matching or condition evaluation.
  Findings carry it by reference (`pair:hasDerivedMechanism`) so the same explanation
  reproduces unchanged across systems and runs. Sentences naming concrete matched elements
  are built in the presentation layer from mechanism text plus evidence labels — never
  stored in the graph.
- **A declarative motif and its query are ODP and OQP.** The motif is the ontology design
  pattern; the registered SPARQL CONSTRUCT is the ontology query pattern derived from it.
  The OQP may differ topologically where matching requires it, but must not violate the
  ODP's semantics — which is why a declaration that drifts from its `.rq` is a defect, not
  a stylistic mismatch.
- **Process typing never decides whether a motif matches (unified 2026-08-06).** Every
  step-node class check in every match query is `?step a/rdfs:subClassOf* beam:Process`
  — the same shape as the library's role idiom, `pair:playsRole/pair:subRoleOf*`. It walks
  the class hierarchy already in the loaded graph, so no reasoner is involved and
  `beam:Process`, `beam:Infer`, `beam:Transform`, `beam:Train`, and `beam:Generate` all
  bind identically. Before this, three conventions coexisted and a leaf-typed agent matched
  *zero* agentic motifs while an identical generic-typed one matched them all.
  **Never write a bare `a beam:Infer` in a query** — `test_queries_check_process_typing_one_way`
  fails on it, and `test_process_typing_does_not_change_what_matches` proves the equivalence
  end to end. The role is the discriminator; the class is only a coarse process/resource
  guard. `annotation_guidance.ttl` still warns when a step carries no process-family class
  at all, since that genuinely cannot bind.
- **Provenance reaches the role vocabulary too (R6).** Every `pair:PatternRole` states a
  `dct:source` or a SKOS mapping. Where a role has no external source of its own, its
  provenance is *derived* — the source of the motif or risk pattern whose registered query
  traverses it — or declared explicitly as a refinement introduced for annotation
  precision. Never attribute a role to a document it did not come from;
  `test_every_pattern_role_states_its_provenance` is the net.
- **Declared-but-unused vocabulary gets removed, not documented.** `pair:maturity` and
  `pair:identifiesCandidateRisk` were deleted 2026-08-06: nothing wrote them and nothing
  read them, so they described intentions rather than the pipeline. Reinstate such a term
  only together with the query that populates it.
- **BEAM is the canonical internal model.** External tool vocabularies (Tool4Boxology
  now, AgentO later) enter only via alignment adapters in `ontology/alignments/` +
  normalizer scripts. Nothing tool-specific in `beam_core.ttl`.
- **OWL class vs SKOS concept (R1)**: OWL classes only for instantiated, query-traversed
  structure (BEAM elements). SKOS concepts for classification values (pattern roles,
  data categories, all facets). Never instantiate a facet value.
- **Motifs match structure only (R2)** — roles + flow relations, reading **no** facet.
  Applicability conditions evaluate structure + facets (context, data categories, absence
  of controls). Situational context enters at the applicability phase, never at matching.
- **Flow relations are not data flow.** `inform` is process-to-process ordering with no
  resource transfer and it is load-bearing (the Guardrails motif is constituted by a
  guardrail step *informing* a generation step). Never redefine a motif over "data flow".
- **Facets reach the assessment two ways, and only two (decided 2026-08-11).**
  (i) **Bridge** — a protection-relevant facet value is mapped into a `pair:DataCategory`
  by a registered propagation query, and the category then travels along the flow like any
  other. Used for `facet:hasPersonalDataCategory` → `SensitiveInformation` and
  `facet:hasDataRights dataf:Proprietary` → `ConfidentialInformation`.
  (ii) **Direct read** — an applicability condition tests the facet on a *bound element of
  the match* (R2), positively (R10). No propagation is involved.
  **Facets are never propagated as facets.** R8 makes Data Category the one facet that is
  also derived; propagating others would break that line and force every condition to read
  two propagating vocabularies. Concretely: content-borne properties (sensitivity,
  confidentiality) bridge and travel; element-intrinsic properties (provenance, dynamism)
  do not, because an element derived from observed data is *derived* data, not observed
  data — copying the label downstream would assert something false. "What was this derived
  from?" is answered by the `prov:Derivation` chain instead, which is exact.
- **There is no "Personal" data category, and there must not be one.** Personal data is
  expressed with DPV concepts through `facet:hasPersonalDataCategory` (R3), never mirrored
  into `pair:DataCategoryScheme`. Data Category is the one facet that lives in the pattern
  module rather than `ontology/facets/`, because its values are also *derived* along data
  flow by registered propagation queries (R8); every other facet is an annotated base fact.
- **Predicate economy**: no new flow predicates in BEAM core; node types carry edge
  semantics.
- **Provenance everywhere**: `dct:source` on reused concepts; `pair:derivedFrom` on every
  motif and risk pattern; SKOS mappings for taxonomy alignments.
- **Adopt upstream mappings; do not re-derive them.** Cross-taxonomy links were the
  documented fabrication hotspot of this project, so `taxonomy_mapping.ttl` is tiered by
  evidence (Section 1 upstream, Section 2 project curation, Section 3 risk→control).
  Before curating a link, check whether IBM AI Atlas Nexus already publishes an SSSOM row
  for it; if so, reproduce their predicate and direction exactly, even if your reading
  differs — a hand-asserted `broadMatch` was already found to be the inverse of upstream's
  curated `narrowMatch`. Prefer rows justified `semapv:ManualMappingCuration`; treat
  `semapv:LLMBasedMatching` rows as a human decision, not an automatic adoption.
  (R6's own-SSSOM export has never been generated; the project consumes upstream sets
  instead. Say so rather than implying the export exists.)
- **Licence discipline: reference, never reproduce.** The repository is CC BY 4.0. Both
  OWASP sources (LLM Top 10 2025, Agentic Top 10 2026) are CC BY-**SA** 4.0, whose
  ShareAlike term binds adaptations. Reuse only their identifiers, numbering, and links —
  facts and short names — and write every definition, mechanism, and condition from
  scratch. Copying their descriptions, mitigation lists, or attack scenarios would pull
  ShareAlike onto the file and conflict with the repository licence. IBM AI Atlas Nexus is
  Apache 2.0 (permissive, attribution recorded); NIST AI 600-1 is a U.S. government work
  with no domestic copyright. Record every ingested source in `NOTICE.md`.
- **Task ≠ Capability ≠ Application Type** — three separate axes, SKOS-mapped, never
  merged.
- **DPV is referenced, never copied** (identifiability, entities, purposes).
- **TÜV AI.ST taxonomy is excluded** (license verified 2026-08-03, still closed).
  The v0.1 whitepaper carries "© TÜV AI.Lab GmbH" with no licence grant, is a public
  download but publicly available ≠ reusable, and the PDF itself is marked
  "CONFIDENTIAL. DO NOT SHARE". Do not mint TÜV concepts, reproduce its tables, or
  add TÜV mappings. Citing it in prose is normal scholarship and remains fine.
  Reopen only on written permission from <info@tuev-lab.ai>.
- **OECD is absorbed, not represented** (decided 2026-08-03). Facet values carry OECD
  as `dct:source`; there is no `oecd:` concept scheme and there must not be one.
  OECD publishes no resolvable URIs, so any `oecd:X` would be a concept we wrote from
  the same reading that produced the facet value — the `exactMatch` would be true by
  construction and prove nothing, while doubling the concept count. Adding document
  loci would change this, but loci must be read from the source, never inferred.
  **DPV is the alignment target** (resolvable, third-party checkable); OECD is a cited
  documentary source. Say "informed by OECD", not "aligned to OECD".
- **The facet layer is a documented mixture, not wholesale external grounding.**
  59 concepts: 24 cite OECD, 35 declare project curation, 34 carry no external
  mapping. Do not describe it as "OECD/DPV-derived" without that qualification.
- **Alignment provenance is data, not commentary.** Every mapping has an
  `sssom:Mapping` record in `ontology/taxonomy/provenance/` with a semapv
  justification. It sits below the runner's non-recursive glob deliberately — a
  finding must never cite its own provenance as support. Never move it up a level.
  Regenerate with `python python/scripts/generate_mapping_provenance.py`.
- **MIT upstream terms are unverified.** `mit_air_risk_control.ttl` reproduces the MIT
  RiskControlGroup layer verbatim; Apache 2.0 covers IBM's packaging, not MIT's own rights.
  Resolve before publication.

## Naming (current, post-v1.1 renames)

The prefix is **`pair:`** (`http://w3id.org/airiskkg/pair-ai#`) — this section previously
wrote these terms as `rp:`, which appears nowhere in the ontology. Pattern instances use
`pat:`; taxonomies use `owasp:` / `asi:` / `atlas:` / `mit:` / `nist:` / `nexus:`.

- `pair:RiskPattern` — the AI risk pattern entity.
- `pair:ApplicabilityCondition`, with `pair:PropertyPathCondition` for conditions evaluated
  via a SPARQL property path (reachability).
- `pair:GraphMotif` (the ODP) / `pair:PatternImplementation` (the OQP) / `pair:MotifMatch`
  (the instantiation, materialized with explicit `pair:hasNodeBinding` bindings).
- `pair:hasEvidence` — property on `pair:RiskFinding`.
- `pair:RiskFinding` carries its taxonomy entries on `pair:hasCandidateRiskTaxonomyEntry`
  and its status on `pair:findingStatus` (the triage extension point). The assessed system
  is **not** asserted on the finding — derive it by traversing from an evidence element to
  the containing `beam:System`.
- `pair:identifiesCandidateRisk` is **declared but not emitted** — no finding currently
  links to a `beamr:Risk` individual, and no alignment exists between `nexus:Risk`
  (taxonomy entries) and `beamr:Risk`. Open item; do not write docs implying it works.
- Two curated collections: **Motif Library** (risk-neutral) and **Risk Pattern Library**.
- Control layer: `pair:controlNature` (technical / non-technical) and
  `pair:realizedByMotif` (control → motif that could structurally realize it).
  `pair:realizedByMotif` marks a **candidate** structural mitigation, not proof that
  inserting the motif removes the risk — and several realizing motifs are themselves
  risk-bearing. Only project-authored `pat:Control_*` concepts appear in
  `pair:suggestedControl`; MIT `mitctrl:*` families are reached as an evidence layer
  through taxonomy links.

If code or TTL still uses old names, that is migration debt — fix toward the new names,
never toward the old ones.

## Repo layout (key paths)

Three kinds of thing, kept apart on purpose: knowledge (`ontology/`), contracts
(`shacl/`), and code (`python/`).

- `ontology/core/` — beam_core.ttl, beam_core_risk.ttl, pair_ai_pattern.ttl (pattern meta-vocabulary)
- `ontology/patterns/` — motif.ttl, risk_pattern_library.ttl, control_mitigation_layer.ttl
- `ontology/patterns/implementation/` — the executable SPARQL CONSTRUCTs, in three
  subdirectories: `match/` (one per motif, 28), `risk/` (one per risk pattern, 15), and
  `propagation/` (4 derived-fact rules: content categories, untrusted taint, generated
  content, personal data rights — re-run to a fixed point by the runner).
  **These paths are data**: each is registered by a `pair:PatternImplementation` whose
  `pair:implementationPath` is a literal string, so moving or renaming a query means updating
  its declaration too. `test_library_consistency.py` fails if the two drift apart.
- `ontology/facets/` — SKOS characterization facets: `task.ttl`, `context.ttl` (domain,
  purpose, deployment setting), `autonomy.ttl`, `data_facets.ttl` (provenance, dynamism,
  rights), `implementation_type.ttl`, and `facet_properties.ttl` (the assignment
  properties). Data Category is **not** here — see the locked decision above.
- `ontology/alignments/` — external vocabulary adapters (Tool4Boxology, DPV; later AgentO)
- `ontology/taxonomy/` — IBM Atlas, OWASP LLM, OWASP Agentic (ASI), MIT, NIST AI 600-1 + the
  cross-taxonomy mappings. Mappings are tiered by evidence: Section 1 reproduces upstream SSSOM
  rows exactly, Section 2 is project curation where no upstream row exists, Section 3 grounds
  risk to controls. Prefer adopting an upstream row over curating one.
- `ontology/visualization/` — standalone SPARQL run by hand; referenced by no declaration,
  unlike `patterns/implementation/`
- `ontology/example/` — **every** architecture graph the repo ships: a RAG chatbot
  (Onyx / Danswer) and a minimal graph-RAG. Two, deliberately: enough for someone to
  try the tool, and a set small enough to keep pinned.
  **Never name one of these files in a test.** They get renamed — `onyx_danswer.ttl`
  became `onyx_danswer_rag_chatbot.ttl` became `ony_rag_chatbot.ttl` became
  `onyx_rag_chatbot.ttl` inside two days — and each rename broke suites for reasons
  unrelated to what they test. Resolve one through
  `tests/conftest.py::example_path(NAMESPACE)`, which finds the graph by the IRI it
  mints elements under: renaming a file is a filing decision, changing a namespace is
  a modelling one.
- `ontology/example_local/` — **the user's own graphs: gitignored, and not in the
  Docker image.** Confidential and NDA-covered architectures live here (the MCP
  tool-use graph moved here 2026-08-17). Only its `README.md` is tracked. Nothing in
  the test suite or the shipped library may read from it — a fresh clone has to pass —
  and `test_private_examples.py` enforces that, plus the ignore rule, the
  `.dockerignore` allow-list, and that a WSGI app neither lists nor serves the folder.
  Serving it is opt-in: `create_app(local_examples=True)`, which only `cli serve` does.
- **`.dockerignore` is an allow-list, and must stay one.** `COPY . /app` once shipped
  `docs/example_UC/` — NDA-covered and carefully gitignored — because `.gitignore` and
  `.dockerignore` are unrelated files and nobody updated the second. It now excludes
  `*` and names what the app reads, so a new private directory is left out by default
  rather than by vigilance. Never convert it back to a deny-list; when the app starts
  reading a new path, add a `!` line and rebuild.
- `docs/example_UC/` — **NDA-covered use-case graphs, gitignored.** Absent from a fresh
  clone, so nothing in the test suite or the library may depend on it. `paths.EXAMPLE_UC_DIR`
  resolves it for local runs only; never add a test or an example that reads from there.
- `shacl/` — three shapes files answering three different questions:
  `architecture_input_contract.ttl` (is this graph acceptable? Violations),
  `assessment_output_contract.ttl` (are emitted findings well formed?), and
  `annotation_guidance.ttl` (will this annotation actually match anything?).
  **Every guidance shape is `sh:Info` or `sh:Warning`, never `sh:Violation`** — it
  cannot change whether a graph conforms, and a test enforces that. It rides along with
  the input contract in the webapp and in `validate_graphs.py`.
- `external/tool4boxology/` — vendored schema + sample export; attribution in `NOTICE.md`
- `python/src/airiskkg/`, `python/scripts/`, `python/tests/` — pipeline code, CLI, webapp, and
  maintenance scripts. The Python package root is `python/`, not the repo root; `airiskkg.paths`
  resolves back to the knowledge base by walking up until it finds both `ontology/` and `python/`.
- `outputs/` — generated motif matches and findings (assessment output, not knowledge; untracked)
- `v1/` — frozen snapshot of the prior ontology generation (do not edit; see `v1/legacy/` for the
  earlier pre-BEAM flat layout)
- `NOTICE.md` — third-party attributions and the licence posture for each ingested source

## Working conventions

- Branch per feature; one labeled commit per task; never commit directly to main.
- After every ontology change: parse all `.ttl` with RDFLib, run pyshacl where shapes
  exist, and re-run the assessment on the bundled examples — then explain any diff.
  Current baseline (matches / findings, as of 2026-08-17):

  | Graph | Matches | Findings |
  | --- | --- | --- |
  | RAG chatbot, Onyx / Danswer (broadest: 8 distinct motifs) | 14 | 25 |
  | Minimal graph RAG | 3 | 8 |

  The agentic layer is covered by `test_agentic_assessment.py`, which states its own
  graph inline — the MCP example it used to read now lives in `example_local/`.

  Matches are `pair:MotifMatch` instances, not distinct motifs — nested motifs co-match
  by design, so the number is structural coverage. `test_propagation.py` asserts these
  numbers; the graphs are named there by namespace, not filename.
- **rdflib's SPARQL compiler is not thread-safe.** pyparsing keeps global parser state, so
  two threads compiling queries at once corrupt it and surface as
  "`Param.postParse2() missing 1 required positional argument`". Compilation is serialized
  in `assessment_runner._prepared_query`; keep it there rather than locking in a caller,
  and never parse SPARQL off the main thread outside that function.
- **Clause order is load-bearing in a risk query (2026-08-17).** rdflib has no query
  optimizer: it evaluates a BGP in textual order and applies a FILTER to its whole group.
  So every risk query is written as `WHERE { { structure … FILTER NOT EXISTS … } curated
  metadata . OPTIONAL … BIND … }`. The metadata block (`hasMechanism` /
  `hasApplicabilityCondition` / `mayIndicateRisk` / `suggestedControl`) is a small cross
  product — 18 to 36 rows — and leading with it multiplied every structural join, property
  path, and absence-of-control check by that factor. Restoring the old order costs ~3x
  runtime and changes nothing about the result. Never hoist the metadata back to the top,
  and keep the structural braces: without them the filters leave that group and fire once
  per metadata row again.
- **The knowledge base is parsed once per process** and copied per call
  (`assessment_runner._base_knowledge`). Turtle parsing was the largest single cost in
  every entry point. `load_base_graph()` still hands back a fresh writable graph — callers
  parse an architecture into it — so never return the cached instance. Editing a `.ttl` in
  a live server needs `reload_knowledge_base()`; Flask's reloader watches Python only.
- Adding a query file is a two-part change: the `.rq` **and** a `pair:PatternImplementation`
  registering its `pair:implementationPath`. `test_library_consistency.py` is the net that
  catches an orphaned query or a dangling path.
- New taxonomy files need no wiring: `load_base_graph` globs `ontology/taxonomy/*.ttl`.
- Motif templates in the workbench catalogue and the "why didn't this match" gap report are
  both generated from the declared `pair:hasPatternNode` / `pair:hasPatternEdge` structure,
  so declaration and match query must stay in sync — a motif whose declaration drifts from
  its `.rq` produces a template that cannot match itself.
- Tool4Boxology export quirks the normalizer must handle: lowercase type URIs
  (`t4b:transform` vs `t4b:Transform`), ontology declares `patternProcess` but exports
  `hasProcess`, instances multi-typed with `t4b:Component`.
- Current library size (2026-08-17, counted off the loaded graph): **31 motifs**,
  **16 risk patterns**, **97 pattern roles**, **7 data categories**, **35 facet
  concepts**, 21 applicability-condition attachments. Implementations: 31 match
  queries, 16 risk queries, 6 propagation rules.
  Every figure but the motif count had already drifted before anyone noticed, so
  re-count rather than edit by hand:
  `len(set(load_base_graph().subjects(RDF.type, PAIR.GraphMotif)))` and its siblings.
  When any of these changes, update `docs/reference/catalogue.md` in the same commit —
  nothing regenerates it.
- **A control clears a finding by being built, not by being asserted.** A risk query
  whose only escape is `?control beamr:associatedTo ?element` cannot be cleared by
  changing the architecture — `beamr:associatedTo` appears in no bundled example and no
  UI writes it — so the finding is unfalsifiable by design work. Prompt injection was
  fixed 2026-08-17 by testing for a screening step on the path; **7 of 16 risk queries
  still have no structural check at all** (data_model_poisoning, excessive_agency,
  sensitive_retrieval, supply_chain, system_prompt_leakage, vector_embedding_weakness,
  and the annotation half of others). Some are legitimately unstructural — supply-chain
  vetting has no shape — but audit before assuming.
- **Control motifs are sized to the risk, not to the vocabulary.** `GuardrailsMotif` is
  8 nodes and 8 edges; prompt injection needs an input screen and nothing else, so
  `InputScreeningMotif` / `OutputScreeningMotif` are 3 nodes and 2 edges each and nest
  inside it. A control whose `pair:realizedByMotif` points at a motif far larger than
  the risk it addresses is not actionable — that motif is what the canvas offers to
  insert.
- Sweep motif labels against R9 whenever the library version changes: no *direct*, *only*,
  *pure*, *without*, *unmediated*, *standalone* in a motif name.
- Write English comments/labels; APA 7th for any citation in docs.
- Ask before any change that alters the semantics of existing motif SPARQL queries.
- Roles must sit under the role their motif query actually traverses. Queries walk
  `pair:playsRole/pair:subRoleOf*` from a general role, so a precise role parented to an
  abstract top-level role is inert: tagging an element with the obviously-correct term then
  silently prevents the motif from matching. This bit `RewrittenQuery` and `RerankedContext`.
