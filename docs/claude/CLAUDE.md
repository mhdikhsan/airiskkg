# CLAUDE.md — airiskkg (PAIR-AI)

This file is read automatically by Claude Code at the start of every session.
It encodes the project context and the locked design decisions. Do not contradict it;
if a task seems to require violating a rule here, stop and ask.

## What this project is

PAIR-AI is a design-time AI risk assessment method. It matches **architectural motifs**
(SPARQL graph patterns over pattern roles) against RDF **architecture graphs** of AI
systems (BEAM vocabulary), and when a motif match satisfies the **applicability
conditions** of an **AI risk pattern**, it emits a **candidate risk finding** with
evidence, a risk mechanism, taxonomy links (IBM AI Risk Atlas / OWASP LLM Top 10 /
OWASP Agentic Top 10 / MIT AI Risk Repository / NIST AI 600-1), and suggested
controls.

Mental model: static code analysis for AI architectures. Motifs ≈ linter rules,
findings ≈ warnings (never confirmed bugs).

The library covers GenAI, ML serving/training, supply-chain, and agentic shapes.
Agentic coverage is deliberately partial: only ASI entries with a design-time
structural signature are modelled. Entries defined by runtime behaviour (ASI10
Rogue Agents is behavioural divergence after deployment) have no shape in a
submitted graph, and adding them would fire a finding on every agent — noise that
breaks candidate framing instead of supporting it.

## Authoritative documents (read before non-trivial changes)

- `docs/reference/PAIR-AI_glossary_v1.2.md` — terminology and modeling rules, **v1.2, locked
  2026-07-28** (supersedes v1.1). Section C (rules R1–R8) is a hard constraint on every change.
  Section E is the completed rename record; Section F is the decision record.
- `docs/reference/PAIR-AI_method_and_construction.md` — how the knowledge base was built and how
  an assessment runs: risk-pattern derivation, role provenance, motif curation, ontology reuse
  and alignment, the pipeline, and current limitations.
- `docs/claude/claude_code_prompt_data_model_update.md` — the Tasks 1–7 plan this branch grew
  from. Largely delivered: the Task 2 facets, Task 5 SHACL contract, and Task 6 Tool4Boxology
  adapter and `external/` vendoring all exist. Read it as history and rationale, not as an
  outstanding backlog.
- `CHANGELOG_data_model.md` — running record of data-model changes and past audits, including
  which layers were found to contain fabricated content and how each was fixed. Worth reading
  before touching the taxonomy or mapping layers. Local-only (gitignored).

## Locked decisions (summary — full versions in GLOSSARY.md Section C)

- **Candidate framing is non-negotiable.** All outputs are *candidate* risks
  (structural dispositions), never confirmed failures. Every comment, label, and doc
  string must respect this. Formal basis: Open World Assumption — `FILTER NOT EXISTS`
  is closed-world over the submitted graph only.
- **BEAM is the canonical internal model.** External tool vocabularies (Tool4Boxology
  now, AgentO later) enter only via alignment adapters in `ontology/alignments/` +
  normalizer scripts. Nothing tool-specific in `beam_core.ttl`.
- **OWL class vs SKOS concept**: OWL classes only for instantiated, query-traversed
  structure (BEAM elements). SKOS concepts for classification values (pattern roles,
  data categories, all facets). Never instantiate a facet value.
- **Motifs match structure only** (roles + flow relations). Applicability conditions
  evaluate structure + facets (context, data categories, absence of controls).
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

- `pair:RiskPattern` (formerly `MotifInterpretation`) — the AI risk pattern entity.
- `pair:ApplicabilityCondition` (formerly interpretation/graph condition).
- `pair:hasEvidence` — property on `pair:RiskFinding` (EvidenceSubgraph class demoted).
- `pair:RiskFinding` links to risk via `pair:identifiesCandidateRisk` (no longer a subclass
  of `beamr:Risk`); its taxonomy entries hang off `pair:hasCandidateRiskTaxonomyEntry`.
- Two curated collections: **Motif Library** (risk-neutral) and **Risk Pattern Library**.

If code or TTL still uses old names, that is migration debt — fix toward the new names,
never toward the old ones.

## Repo layout (key paths)

Three kinds of thing, kept apart on purpose: knowledge (`ontology/`), contracts
(`shacl/`), and code (`python/`).

- `ontology/core/` — beam_core.ttl, beam_core_risk.ttl, pair_ai_pattern.ttl (pattern meta-vocabulary)
- `ontology/patterns/` — motif.ttl, risk_pattern_library.ttl, control_mitigation_layer.ttl
- `ontology/patterns/implementation/` — one executable SPARQL CONSTRUCT per motif / risk pattern.
  **These paths are data**: each is registered by a `pair:PatternImplementation` whose
  `pair:implementationPath` is a literal string, so moving or renaming a query means updating
  its declaration too. `test_library_consistency.py` fails if the two drift apart.
- `ontology/facets/` — SKOS characterization facets (task, context, autonomy, data)
- `ontology/alignments/` — external vocabulary adapters (Tool4Boxology, DPV; later AgentO)
- `ontology/taxonomy/` — IBM Atlas, OWASP LLM, OWASP Agentic (ASI), MIT, NIST AI 600-1 + the
  cross-taxonomy mappings. Mappings are tiered by evidence: Section 1 reproduces upstream SSSOM
  rows exactly, Section 2 is project curation where no upstream row exists, Section 3 grounds
  risk to controls. Prefer adopting an upstream row over curating one.
- `ontology/visualization/` — standalone SPARQL run by hand; referenced by no declaration,
  unlike `patterns/implementation/`
- `ontology/example/` — architecture graphs used as worked examples and test fixtures
- `shacl/` — `architecture_input_contract.ttl` (accepted input) and
  `assessment_output_contract.ttl` (emitted findings)
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
  exist, and re-run the assessment on the bundled examples — `onyx_danswer.ttl` (broadest:
  13 motifs / 23 findings), `agentic_assistant.ttl` (agentic layer),
  `rag_with_guardrails.ttl` (composition), `beam_export_graph_rag.ttl` (unannotated import,
  expects zero) — and explain any diff in findings.
- **rdflib's SPARQL compiler is not thread-safe.** pyparsing keeps global parser state, so
  two threads compiling queries at once corrupt it and surface as
  "`Param.postParse2() missing 1 required positional argument`". Compilation is serialized
  in `assessment_runner._prepared_query`; keep it there rather than locking in a caller,
  and never parse SPARQL off the main thread outside that function.
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
- Write English comments/labels; APA 7th for any citation in docs.
- Ask before any change that alters the semantics of existing motif SPARQL queries.
- Roles must sit under the role their motif query actually traverses. Queries walk
  `pair:playsRole/pair:subRoleOf*` from a general role, so a precise role parented to an
  abstract top-level role is inert: tagging an element with the obviously-correct term then
  silently prevents the motif from matching. This bit `RewrittenQuery` and `RerankedContext`.
