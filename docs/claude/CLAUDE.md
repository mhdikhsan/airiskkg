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
MIT AI Risk Repository), and suggested controls.

Mental model: static code analysis for AI architectures. Motifs ≈ linter rules,
findings ≈ warnings (never confirmed bugs).

## Authoritative documents (read before non-trivial changes)

- `docs/reference/PAIR-AI_glossary_v1.1.md` — terminology and modeling rules, **v1.1, locked**.
  Section C (rules R1–R8) is a hard constraint on every change. Section E lists active renames.
- `docs/claude/claude_code_prompt_data_model_update.md` — the current work plan (Tasks 1–7,
  one commit each, branch `feature/characterization-layer`).

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
- **Provenance everywhere**: `dct:source` on reused concepts; `rp:derivedFrom` on every
  motif and risk pattern; SKOS mappings + SSSOM export for taxonomy alignments.
- **Task ≠ Capability ≠ Application Type** — three separate axes, SKOS-mapped, never
  merged.
- **DPV is referenced, never copied** (identifiability, entities, purposes).
- **TÜV AI.ST taxonomy is on hold** (license unverified). Do not add TÜV mappings.

## Naming (current, post-v1.1 renames)

- `rp:RiskPattern` (formerly `rp:MotifInterpretation`) — the AI risk pattern entity.
- `rp:ApplicabilityCondition` (formerly interpretation/graph condition).
- `rp:hasEvidence` — property on `rp:RiskFinding` (EvidenceSubgraph class demoted).
- `rp:RiskFinding` links to risk via `rp:identifiesCandidateRisk` (no longer a subclass
  of `beamr:Risk`).
- Two curated collections: **Motif Library** (risk-neutral) and **Risk Pattern Library**.

If code or TTL still uses old names, that is migration debt from Task 1 — fix toward
the new names, never toward the old ones.

## Repo layout (key paths)

- `ontology/core/` — beam_core.ttl, beam_core_risk.ttl, pair_ai_pattern.ttl (pattern meta-vocabulary)
- `ontology/patterns/` — motif and risk-pattern instances (being split into two libraries)
- `ontology/facets/` — SKOS characterization facets (Task 2, not yet created)
- `ontology/alignments/` — external vocabulary adapters (Tool4Boxology, later AgentO; Task 6, not yet created)
- `ontology/taxonomy/` — IBM Atlas, OWASP, MIT taxonomies + mappings (SSSOM-backed)
- `shacl/` — input contract shapes (Task 5, not yet created)
- `external/tool4boxology/` — vendored schema + sample export (CC BY 4.0 / Apache 2.0; Task 6, not yet created)
- `python/src/airiskkg/`, `python/scripts/` — pipeline code, CLI, and assessment_runner.py
- `outputs/` — generated motif matches and findings (assessment output, not knowledge)
- `v1/` — frozen snapshot of the prior ontology generation (do not edit; see `v1/legacy/` for the
  earlier pre-BEAM flat layout)

## Working conventions

- Branch per feature; one labeled commit per task; never commit directly to main.
- After every ontology change: parse all `.ttl` with RDFLib, run pyshacl where shapes
  exist, and re-run `assessment_runner.py` on the example use-case graphs; explain any
  diff in findings.
- Tool4Boxology export quirks the normalizer must handle: lowercase type URIs
  (`t4b:transform` vs `t4b:Transform`), ontology declares `patternProcess` but exports
  `hasProcess`, instances multi-typed with `t4b:Component`.
- Write English comments/labels; APA 7th for any citation in docs.
- Ask before any change that alters the semantics of existing motif SPARQL queries.
