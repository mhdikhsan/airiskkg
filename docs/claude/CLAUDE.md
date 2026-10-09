# CLAUDE.md — airiskkg (PAIR-AI)

Read automatically at the start of every session. It carries the project context and the
locked decisions. **Do not contradict it**; if a task seems to require breaking a rule here,
stop and ask.

Rules are stated first and justified in one clause. The incidents behind them are in
`docs/notes/claude_md_rationale.md` (gitignored) — read that when a rule looks arbitrary.

---

## Development rules

- **No long comments in code.** A comment earns its place by saying what the code cannot:
  a one-line purpose docstring, or a short why-comment tied to the line above it.
- **Narrative belongs elsewhere** — the history of a bug, the reasoning behind a decision,
  a restatement of a rule this file already carries. A rule goes in this file; background
  goes in `docs/notes/`. A code block is not where anyone looks for either, and it rots
  there unseen.
- Write English comments and labels. APA 7th for any citation in docs.
- **Never write bare "pattern" in prose** — write **architecture design pattern**, **AI risk
  pattern**, or **ontology design pattern**. Three levels are involved and they are routinely
  conflated:

  | Level | Term | Carries | Modeled as |
  | --- | --- | --- | --- |
  | Type, with rationale | architecture design pattern (RAG, agentic loop) | structure + intent + applicability + consequences | **not modelled**; identified only by a `pair:DesignPatternCitation` |
  | Type, structure only | **architectural motif** | pattern roles + flow relations | `pair:GraphMotif` |
  | Instance | **motif match** | bindings from pattern nodes to elements | `pair:MotifMatch` |

  The differentia is **what gets dropped**: a design pattern documents *why* the solution works;
  a motif keeps only the structure, which is what makes it matchable and risk-neutral. An **AI
  risk pattern** re-attaches conditions, consequences and controls — so calling *that* a pattern
  is correct. Relationship to design patterns is **m:n**. **A motif is never called a pattern**
  — not "reusable architectural pattern", not "graph pattern", not "structural pattern" — and
  **motif is never used for an occurrence**; that is a motif match. Compounds are fine
  (`pattern role`, `pattern node`, Risk Pattern Library); see the glossary Section B naming
  exception for why `pair:Pattern*` term names keep the word.

- **A shared name is not a shared thing.** Fowler documents a gen-AI design pattern called
  Direct Prompting, and the library declares `pat:DirectPromptingMotif`. These are different
  kinds of entity, not two names for one:

  | | Fowler's *Direct Prompting* | `pat:DirectPromptingMotif` |
  | --- | --- | --- |
  | In the graph? | No. Only a citation handle | Yes: 4 pattern nodes, 3 pattern edges |
  | Read when? | While designing, to decide what to build | Afterwards, matched against what was built |
  | Says anything about risk? | Yes, its *consequences* warn it is ungrounded | No. Risk-neutral by construction (R2) |

  A design pattern's four sections land in three places, which is the shortest statement of
  the method: **structure** becomes the motif, **intent and applicability** are dropped, and
  **consequences** are re-attached by the AI risk pattern. That is why
  `pat:DirectPromptingWithoutGroundingRiskPattern` exists and carries the negative a motif name
  may not (R9).

  The collision is a coincidence of this one case. The relation is m:n, so RAG induces three
  motifs while Direct Prompting happens to induce one, which is what makes it misleading. In
  identifiers the `Motif` suffix disambiguates. In prose, never let "Direct Prompting" stand
  alone: name the level.

- **`pair:derivedFrom` names an entity; `dct:source` names a document.** All 31 motifs and 15
  risk patterns now derive from an entity, held by
  `test_derived_from_points_at_an_entity_never_at_a_document`. Pointed at a URL, `derivedFrom`
  only repeats `dct:source`, and *"which motifs came from this design pattern?"* stops being
  answerable. That is what 23 motif references to one Fowler article URL cost.
- **A design pattern is identified by a `pair:DesignPatternCitation`, never modelled.** The 34
  handles at the top of `motif.ttl` carry a label and a `dct:source` (a DOI handle adds an APA
  `dct:bibliographicCitation`, which the linkage generator reads), and nothing else.
  `test_a_design_pattern_citation_stays_a_citation` fails on any other predicate, because a
  `dct:description` there would start modelling the intent and consequences the method drops.
  The handles are what turn the m:n relation into a traversal: `Cite_Guardrails` is reached by
  Guardrails, Input Screening and Output Screening.
- **A handle is minted in `pat:` but stands for someone else's catalogue.** So `library.py`
  reads its origin off its own `dct:source`. Reading it off the IRI would credit Fowler's
  patterns to PAIR-AI.
- **The library names a paper by its DOI, and nothing else.** A DOI handle's chip reads
  `doi:10.48550/arXiv.2312.10997 · Naive RAG`: the label is the design pattern, the DOI is the
  paper. The venue (`dct:isPartOf`) and the paper's name in the label ("(RAG survey)") were
  removed 2026-10-07, because the chip then said the same thing twice; the full reference is in
  `dct:bibliographicCitation` and `NOTICE.md`. `test_a_paper_is_cited_by_its_doi` holds it.
- **Not every motif derives from a design pattern, and the graph says which.** The agentic
  motifs point `derivedFrom` at their OWASP ASI concepts, because their structural signature was
  inferred from a *risk* entry; three of them have since gained a handle in the agent design
  pattern catalogue, and `AgentMemoryLoopMotif` still has none. `ExternalDependencyMotif` names
  `owasp:llm03-supply-chain` for the same reason and has no handle either. Keep that visible; it
  is a weaker derivation and must be described as one.
- **No motif rests on a blog alone (2026-10-07).** Four motifs cited only Fowler's article:
  Direct Prompting, Fine Tuning, Hybrid Retriever and Query Rewriting. Each now also cites a
  DOI: Wei et al. (2021) for prompting and pretrain–finetune (the paradigms its Figure 2
  draws), Gao et al.'s RAG survey (2023) for Naive RAG, mix/hybrid retrieval and reranking,
  and Ma et al. (2023) for rewrite-retrieve-read. Handles by host: **doi.org 12, Mercari 13,
  Fowler 9**. **Link a source only where it draws the motif's own structure**: `derivedFrom`
  claims the shape was read off that design pattern, so a source that is merely *about* the
  topic does not qualify. Every tracked graph's finding set was triple-identical after the
  change, because no query reads `derivedFrom`.
- **What the 2026-10-07 reference set did not become, and why.** *Lost in the Middle* (Liu et
  al., 2024) is an empirical finding about long contexts, not a structure: evidence for a risk
  pattern's mechanism if anywhere, never a motif's derivation. Breuer et al. (2025) is an
  overview of LLMs in IR, and the figure filed under it in the reference PDF is actually Figure 4
  of Zhu et al.'s LLM-for-IR survey (arXiv 2308.07107). The DOI filed under "Guard Rail" is FLAN,
  an instruction-tuning paper, so it cites the prompting and fine-tuning motifs instead; the
  guardrail motifs already cite the agent catalogue's *Multimodal guardrails*. Patterns in that
  PDF with no motif yet — iterative, recursive and adaptive retrieval; goal creators;
  prompt/response optimiser; one-shot and incremental model querying; plan generators; voting-
  and debate-based cooperation; tool/agent registry — **got no handle**, because a handle no
  motif derives from is declared-but-unused. Mint it with the motif that reads it.
- **The Fowler handles cite the article, not a section.** The article has per-pattern anchors,
  and using them is a one-line change per handle once they are verified against the live page.
  Identity does not wait on that: it is the handle's IRI and label. Do not invent anchors.
- **Ask before any change that alters the semantics of existing motif SPARQL queries.**

---

## What this project is

PAIR-AI is a **pattern-based AI risk assessment method** working over **three views of the
same system**:

- the **architecture view** — an RDF graph of the AI system (BEAM, the Boxology Notation
  vocabulary);
- the **process view** — the business process that runs it (sBPMN 2.0), joined to the
  architecture by `pair:refinedBy`;
- the **risk view** — what a run produced and what people said about it, reconciled on one
  diagram. It reads the other two; it never writes to them.

It serves **both phases of a system's life**: assessing a design before it is built, and
auditing a system already in production. **What it reads is always the represented
structure, never runtime behaviour.** Auditing a running system means describing what was
actually built and assessing that description. Nothing here observes traffic, logs, or
model outputs, and no finding may be worded as if it did (R4).

**The word "data" is where that line gets crossed.** A `beam:Data` node declares that a kind
of resource exists at this point in the design. It is a labelled box, never the data itself,
and no value ever flows anywhere. The graph describes a system; it is not a trace of one
running.

| The method reads this (structure) | It never reads this (runtime behaviour) |
| --- | --- |
| a node exists and is typed `beam:Data` | the bytes, rows, or values in it |
| it is annotated `facet:hasPersonalDataCategory dpv:Name` | whether a name is genuinely present |
| a generation step `beam:use`s it | how often that step runs, or with what latency |
| that step `beam:produce`s a user-facing output | what the model actually answered |
| no validation step is represented on that path | whether validation happens in code nobody modelled |

Two consequences follow. Annotations are claims by a modeler rather than measurements (R8),
which is why a missing facet means "not filled in" and never "false" (R10). And the submitted
graph is the entire universe an absence check ranges over (R4), so every finding says *the
submitted graph does not represent a control here*, never *this system has no control*.
Wording a finding as though the second had been checked is the one error that breaks candidate
framing.

It matches **architectural motifs** — reusable, type-level configurations of **pattern
roles** connected by flow relations — against those graphs. A motif is not itself executed:
each one is detected by a registered SPARQL CONSTRUCT, its **motif matcher** (the OQP to the
motif's ODP). A motif is **risk-neutral**: it states what structure is present, never whether
that structure is dangerous. Risk enters only when an **AI risk pattern** evaluates its
**applicability conditions** over a motif match. Satisfaction emits a **candidate risk
finding** carrying evidence, a curated risk mechanism, taxonomy links (IBM AI Risk Atlas /
OWASP LLM Top 10 / OWASP Agentic Top 10 / MIT AI Risk Repository / NIST AI 600-1), and
suggested controls.

> **Risk Pattern = Motif + Applicability Conditions + Mechanism + Taxonomy Links + Controls**
> (the constituent equation, glossary term 7)

**Mental model:** iterative structural analysis across the architecture and the process it
sits in. A **motif is a structural graph**; a **finding is a potential risk**, raised where a
risk pattern's conditions hold over a motif match — a candidate for triage, never a
confirmed defect.

Where the static-analysis analogy is used, get it the right way round:

| Static analysis | PAIR-AI |
| --- | --- |
| The code shape a rule matches | **Motif** — structural, and risk-neutral on its own |
| The lint rule: shape + guard + message + category + suggested fix | **Risk pattern** — which is the constituent equation, term for term |
| The diagnostic it emits | **Candidate risk finding** — requires triage, never a confirmed defect |

**A motif is not a lint rule.** A lint rule fires; a motif only matches. What fires is the
risk pattern, and only when its applicability conditions hold over that match. Calling a
motif a rule collapses the one distinction the whole method rests on.

**Coverage:** GenAI, ML serving and training, supply chain, and agentic shapes. Agentic
coverage is deliberately partial — only ASI entries with a design-time structural signature
get a risk pattern: **ASI01** goal hijack, **ASI02** tool misuse, **ASI03** identity and
privilege abuse, **ASI04** agentic supply chain, **ASI05** unexpected code execution,
**ASI06** memory and context poisoning, **ASI07** insecure inter-agent communication,
**ASI08** cascading failures, **ASI09** human-agent trust exploitation. **ASI10** rogue agents
is catalogued and has none: it is defined by behaviour drifting after deployment, which has no
shape in a represented graph, and a pattern for it would fire on every agent and break
candidate framing rather than support it.

**ML coverage rests on Zhang et al. (2022)**, not on OWASP or IBM, whose catalogues have no
entry for distribution shift or an unvalidated model fit. Its data-level and model-level risks
are `ontology/taxonomy/ml_risk.ttl`; six risk patterns bind the prediction and training steps
of the ML motifs, which carried none before 2026-10-09. Three more derive from IBM Atlas
entries that have a shape of their own: improper retraining (a loop from a model's output back
into its training data), membership inference, and evaluation data contamination.

---

## Authoritative documents

Read before non-trivial changes.

| Document | What it is |
| --- | --- |
| `docs/reference/PAIR-AI_glossary_v1_3.md` | Terminology and modeling rules. **v1.3** supersedes v1.2 (deleted). Sections: **A** core terms, **B** internal terms, **C** rules **R1–R10**, **D** grounding references. A reference to `PAIR-AI_glossary_v1.2.md` is a broken link to fix; v1.2's Sections E/F are gone — do not cite them. **Stale on one point as of 2026-10-04:** lines 26, 122 and 135–137 still list `inform` as a flow relation and still say flow relations are not data flow. The implementation removed it; **this file wins** until the glossary is reissued. |
| `docs/reference/PAIR-AI_method_and_construction.md` | How the knowledge base was built and how an assessment runs. **Stale on one point as of 2026-10-04:** lines 459, 546 and 695 still name `beam:inform`. `docs/reference/mitigation_and_gap_mechanics.md` likewise, at lines 191, 227 and 234. |
| `docs/reference/catalogue.md` | Inventory of every motif, risk pattern, role, and data category. **Hand-written, so it goes stale silently** — re-check its counts whenever the library changes. |
| `docs/reference/risk_control_linkage.md` | How risk patterns reach controls, including the MIT evidence layer. **Generated** — regenerate, never hand-edit. Its motif section lists every catalogue a motif derives from (m:n) and reads DOI handles off their APA citation; until 2026-10-07 it kept the first Mercari/Fowler/OWASP hit, so the agent catalogue's six handles never appeared in it. `test_generated_documents.py` re-runs the generator and diffs it against what is checked in, because nothing did: when `pair:derivedFrom` moved from naming a URL to naming a `pair:DesignPatternCitation`, the generator kept producing a document while every motif silently fell into *"unrecorded"*. **A generated artifact nothing re-generates is not reproducible, it is just checked in.** |
| `NOTICE.md` | Third-party attributions and the licence posture of each ingested source. |

**Local-only (gitignored — absent from a fresh clone):**

- `docs/notes/claude_md_rationale.md` — the incidents behind the rules in this file.
- `docs/notes/code_rationale.md` — prose lifted out of the code by the 2026-09-08 sweep,
  242 entries with file-and-line provenance.
- `docs/notes/business_context_as_built.md` — the business layer as built. Its companion
  `bpmn_business_context_integration.md` is the prior analysis, marked superseded.
- `CHANGELOG_data_model.md` — data-model changes and past audits, including which layers
  were found to contain fabricated content. Read before touching taxonomy or mappings.

---

## Locked decisions — the method

### Candidate framing and the Open World Assumption

- **Candidate framing is non-negotiable.** Every output is a *candidate* risk — a structural
  disposition, never a confirmed failure, an observed incident, or a prediction that harm
  will occur. Every comment, label, and docstring must respect this.
- **R4 is the formal basis.** `FILTER NOT EXISTS` is closed-world over the *submitted graph
  only*, so "no validation control is represented" ≠ "none exists".

### Motifs

- **Motifs cannot express absence (R9).** Matching is monotone: a motif that matches a graph
  matches every extension of it, so a motif asserts presence only. Every negative,
  exclusivity, or sufficiency claim — *direct*, *only*, *pure*, *without*, *unmediated*,
  *standalone* — belongs to an applicability condition. A risk pattern name may carry the
  negative; **a motif name may not.** Sweep motif labels whenever the library version changes.
- **Motifs match structure only (R2)** — roles and flow relations, reading **no** facet.
  Situational context enters at the applicability phase, never at matching.
- **Motifs may nest, deliberately.** The library is not an antichain; a smaller motif can be
  a subgraph of a larger one and always co-matches with it. **Match counts measure structural
  coverage, not distinct architectural features** — never report them as "how many different
  things the system does".
- **A motif and its query are ODP and OQP.** The motif is the ontology design pattern; the
  registered CONSTRUCT is the ontology query pattern derived from it. The OQP may differ
  topologically where matching requires it but must not violate the ODP's semantics — a
  declaration that drifts from its `.rq` is a defect, not a stylistic mismatch.
  **`test_every_motif_template_matches_its_own_motif` now holds that end to end**: it builds
  each of the 31 templates exactly as `add-motif` does and asserts the motif matches what it
  produced. It caught `EmbeddingsMotif` declaring no indexing-step node at all and papering
  over the gap with a `VectorIndex beam:use Vector` edge — a data-to-data edge in the library
  itself — and `ExternalDependencyMotif` stating no `pair:expectedClass` on either end.
  **`test_every_pattern_edge_crosses_between_an_oval_and_a_box`** holds the bipartite rule over
  all 143 declared edges.
- **Process typing never decides whether a motif matches.** Every step-node check is
  `?step a/rdfs:subClassOf* beam:Process` — the same shape as the role idiom
  `pair:playsRole/pair:subRoleOf*`. It walks the class hierarchy already in the graph, so no
  reasoner is involved and `beam:Process`, `beam:Infer`, `beam:Transform`, `beam:Train` and
  `beam:Generate` all bind identically. **Never write a bare `a beam:Infer` in a query** —
  `test_queries_check_process_typing_one_way` fails on it, and
  `test_process_typing_does_not_change_what_matches` proves the equivalence end to end. The
  role is the discriminator; the class is only a coarse process/resource guard.
  `annotation_guidance.ttl` still warns when a step carries no process-family class at all,
  since that genuinely cannot bind.
- **Roles must sit under the role their motif query actually traverses.** Queries walk
  `pair:playsRole/pair:subRoleOf*` from a general role, so a precise role parented to an
  abstract top-level role is **inert** — tagging an element with the obviously-correct term
  then silently prevents the motif from matching. This bit `RewrittenQuery` and
  `RerankedContext`.

### Risk patterns and conditions

- **Conditions are evaluated over a motif match, not over the graph at large.** "Personal
  data is present somewhere in this system" and "the data bound to the prompt-context node is
  personal" are different claims; only the second licenses a finding.
- **Facet conditions are positive; only control conditions may be negative (R10).** A
  condition may test for the presence of a facet value on a bound element, never its absence,
  unless the SHACL input contract makes that facet mandatory — facets are annotated base
  facts (R8), so a missing value means the modeler did not fill it in. Absence-of-control
  conditions are exempt: they are claims about represented structure, already graph-relative
  under R4.
- **`pair:hasMotif` is canonical; `pair:hasRiskPattern` is a required mirror.** The binding is
  authored on the risk pattern, because the motif is a constituent of the risk pattern. **No OWL
  reasoning runs in the pipeline** — `owl:inverseOf` is documentation only, so a one-sided
  assertion is invisible to a consumer reading the other side. Write both directions;
  `test_library_consistency.py` enforces it.
- **Mechanisms are curated, never computed.** A `pair:RiskMechanism` takes no part in
  detection — never evaluated, never filtered on. Findings carry it by reference
  (`pair:hasDerivedMechanism`) so the same explanation reproduces unchanged across systems and
  runs. Sentences naming concrete matched elements are built in the presentation layer from
  mechanism text plus evidence labels, **never stored in the graph**.

### Vocabulary and modelling

- **OWL class vs SKOS concept (R1).** OWL classes only for instantiated, query-traversed
  structure (BEAM elements). SKOS concepts for classification values (pattern roles, data
  categories, all facets). **Never instantiate a facet value.**
- **The graph is bipartite, and nothing may cross that.** Boxology alternates ovals and boxes:
  a process reaches a process only through the resource one produces and the other uses,
  exactly as data reaches data only through a process. **No data→data, no data→symbol, no
  process→process** — and the same for every other same-kind pair. Only `beam:use`,
  `beam:produce` and their inverses cross between the two sides, plus `beam:participatedIn`
  from an agent. `beam:Agent` and `beam:System` are siblings of `beam:Resource` rather than
  kinds of it, so *"not a process"* is not the same as *"a resource"*; treating them as
  interchangeable is what put `process beam:use agent` on the canvas.
- **`beam:inform` was removed, and this reverses the earlier rule.** It was declared
  `rdfs:domain beam:Process ; rdfs:range beam:Process`, which Boxology does not permit, and
  the library leaned on it in 25 pattern edges across 17 of 31 match queries. Removed
  2026-10-04 from BEAM, every motif, every risk and mitigation query, and all five tracked
  graphs: **every match and every finding came out identical**, which is the measurement that
  settles it — the relation was carrying nothing the assessment read once the boxes were
  there. Where a step genuinely hands something over, the box is now declared; where a motif
  had none, one was added (a `JobScheduler` issues a job request; a planner produces its plan;
  a guardrail produces its decision). Where nothing is handed over, the edge is simply gone:
  the two parallel paths of `MultiStagePredictionMotif` are joined by the request they share.
  **In a query, the replacement for `beam:inform` is the property path
  `beam:produce/^beam:use`**, and for `beam:inform+` it is `(beam:produce/^beam:use)+`. Do not
  reintroduce a process-to-process predicate under any name.
- **Predicate economy.** No new flow predicates in BEAM core; node types carry edge semantics.
- **BEAM is the canonical internal model.** External tool vocabularies (Tool4Boxology now,
  AgentO later) enter only through alignment adapters in `ontology/alignments/` plus
  normalizer scripts. Nothing tool-specific in `beam_core.ttl`.
- **Task ≠ Capability ≠ Application Type** — three separate axes, SKOS-mapped, never merged.
  The rule is preventive and **nothing in the pipeline exercises it yet**; see *Declared but
  not implemented* before describing it as a capability of the method.
- **Declared-but-unused vocabulary gets removed, not documented.** `pair:maturity` and
  `pair:identifiesCandidateRisk` were deleted because nothing wrote them and nothing read them
  — they described intentions rather than the pipeline. Reinstate such a term only together
  with the query that populates it.

### Facets and data categories

- **Facets reach the assessment two ways, and only two.**
  1. **Bridge** — a protection-relevant facet value is mapped into a `pair:DataCategory` by a
     registered propagation query, and the category then travels along the flow like any
     other. Used for `facet:hasPersonalDataCategory` → `SensitiveInformation` and
     `facet:hasDataRights dataf:Proprietary` → `ConfidentialInformation`.
  2. **Direct read** — an applicability condition tests the facet on a *bound element of the
     match* (R2), positively (R10). No propagation involved.
- **Facets are never propagated as facets.** R8 makes Data Category the one facet that is also
  derived. Content-borne properties (sensitivity, confidentiality) bridge and travel;
  element-intrinsic properties (provenance, dynamism) do not — an element derived from
  observed data is *derived* data, and copying the label downstream would assert something
  false. "What was this derived from?" is answered by the `prov:Derivation` chain, which is
  exact.
- **There is no "Personal" data category, and there must not be one.** Personal data is
  expressed with DPV concepts through `facet:hasPersonalDataCategory` (R3), never mirrored
  into `pair:DataCategoryScheme`. Data Category lives in the pattern module rather than
  `ontology/facets/` precisely because its values are also derived (R8); every other facet is
  an annotated base fact.
- **The facet layer is a documented mixture, not wholesale external grounding.** Of 35
  concepts, 25 carry a SKOS mapping (overwhelmingly DPV) and only 4 state a `dct:source` of
  their own — **OECD is cited once per scheme**, so the grounding is scheme-level and
  inherited. `context.ttl` and `implementation_type.ttl` are declared scheme shells with no
  project concepts. Do not describe the layer as "OECD/DPV-derived" without that
  qualification.

### Provenance and external sources

- **Provenance everywhere.** `dct:source` on reused concepts; `pair:derivedFrom` on every
  motif and risk pattern; SKOS mappings for taxonomy alignments.
- **Provenance reaches the role vocabulary (R6).** Every `pair:PatternRole` traces to an origin
  one of three ways: its own `dct:source`, a SKOS mapping into an external vocabulary, or
  inheritance through `pair:subRoleOf` from a parent that has one. The third is deliberate — a
  role introduced to *refine* another is grounded by the role it specializes.
  `test_every_pattern_role_states_its_provenance` **walks the chain**. **Never attribute a role
  to a document it did not come from.**
- **Adopt upstream mappings; do not re-derive them.** Cross-taxonomy links are this project's
  documented fabrication hotspot, so `taxonomy_mapping.ttl` is tiered by evidence: Section 1
  upstream, Section 2 project curation, Section 3 risk→control. Before curating a link, check
  whether IBM AI Atlas Nexus publishes an SSSOM row; if so **reproduce their predicate and
  direction exactly, even if your reading differs** — a hand-asserted `broadMatch` was already
  found to be the inverse of upstream's curated `narrowMatch`. Prefer rows justified
  `semapv:ManualMappingCuration`; treat `semapv:LLMBasedMatching` as a human decision, not an
  automatic adoption.
- **Alignment provenance is data, not commentary.** Every mapping has an `sssom:Mapping`
  record in `ontology/taxonomy/provenance/`. It sits **below** the runner's non-recursive glob
  deliberately — a finding must never cite its own provenance as support. Never move it up a
  level. Regenerate with `python python/scripts/generate_mapping_provenance.py`.
- **DPV is the alignment target** (resolvable, third-party checkable) and is referenced, never
  copied. **OECD is absorbed, not represented**: facet values carry OECD as `dct:source`;
  there is no `oecd:` scheme and there must not be one, because OECD publishes no resolvable
  URIs. Say "informed by OECD", not "aligned to OECD".
- **TÜV AI.ST taxonomy is excluded** (licence verified 2026-08-03, still closed). Do not mint
  TÜV concepts, reproduce its tables, or add TÜV mappings. Citing it in prose is normal
  scholarship and remains fine. Reopen only on written permission from <info@tuev-lab.ai>.
- **MIT upstream terms are unverified.** `mit_air_risk_control.ttl` reproduces the MIT
  RiskControlGroup layer verbatim; Apache 2.0 covers IBM's packaging, not MIT's own rights.
  Resolve before publication.
- **R6's own-SSSOM export has never been generated.** The project consumes upstream sets
  instead. Say so rather than implying the export exists.

### Licence discipline

**Reference, never reproduce.** The repository is CC BY 4.0. Both OWASP sources are CC
BY-**SA** 4.0, whose ShareAlike term binds adaptations — reuse only their identifiers,
numbering, and links, and write every definition, mechanism, and condition from scratch.
Copying their descriptions, mitigation lists, or attack scenarios would pull ShareAlike onto
the file and conflict with the repository licence. IBM AI Atlas Nexus is Apache 2.0; NIST
AI 600-1 is a U.S. government work with no domestic copyright. Record every ingested source
in `NOTICE.md`.

---

## Locked decisions — the business layer

- **The business layer joins by refinement, never subsumption.** Three layers: business
  (sBPMN 2.0) → `pair:refinedBy` → architecture (BEAM) → `pair:playsRole` → patterns.
  **A `bpmn:activity` is not a `beam:Process`** and must never be aligned to one: every match
  query types its step node as `?step a/rdfs:subClassOf* beam:Process`, so subsuming
  activities under it would make every business activity a candidate motif node — and the
  input contract, which requires each `beam:Process` to use or produce a resource, would
  reject every process model outright. `pair:refinedBy` is PAIR's own rather than
  `sbpmn:calledElement`, whose unconstrained range would hard-code the sBPMN namespace into
  every submitted architecture.
- **One bridge, and R8 stays intact.** `business_data_bridge.rq` reads a personal-data kind off
  a `bpmn:itemDefinition` and emits `pair:SensitiveInformation` on elements of the refined
  system, with a `prov:Derivation` naming the annotation that produced it. What
  is *annotated* stays annotated; what is *derived* is the data category. **No facet is
  propagated as a facet and no BPMN triple enters the architecture.**
- **The bridge marks the edge, never the inside.** Content enters where nothing inside the
  system produced it and leaves where nothing inside consumes it; `content_categories.rq`
  carries it the rest of the way and **refuses to carry it through a redaction, output-guardrail
  or output-validation step**. Marking further in is worse than imprecise: a category asserted
  on an element that sits *after* a control never passes through that filter, so the control
  stops clearing the finding it was built to clear. Measured on the redaction fixture — the
  screened element went from carrying no `SensitiveInformation` to carrying it, and the answer
  with it. **Target `beam:Data` only**, which is where `facet:hasPersonalDataCategory` is
  declared: a model and a prompt sit on the same edge and contain nobody's name.
- **Rewritten 2026-10-04, because the old rule reached almost nothing.** The fallback tested for
  `pair:UserInput` or `pair:PredictionRequest` — **4 of the 50 resource-side roles** — so a
  document store, a knowledge graph, a ticket or a patient record reached nothing however it was
  annotated. Four of the eight systems in the bundled scenes could not be marked at all. Personal
  data does not only arrive as something a person typed, and the consuming risk query already
  knew that: `sensitive_information_disclosure.rq` has a branch reading the category off a
  knowledge source. **The architecture-side route, `personal_data_category.rq`, never had a role
  restriction** — only the business-analyst route did, which is the one route used by the person
  most likely to know the data is personal.
- **`pair:realisedBy` is the statement; the edge rule is the fallback.** Named, that element and
  no other; unnamed, the edge. `pair:targetInferred` on the derivation says which, because only
  one of them is somebody's claim. The picker offers the resources of the architectures the
  reading activities refine and refuses anything else, since naming an element of a system this
  activity never touches would mark something the business layer says nothing about.
- **The fallback is coarse on purpose, and coarser than it was.** One annotation marks every
  element content enters the refined system by, so removing one of several annotations changes
  nothing. That is what `realisedBy` is for. `ag:BusinessDataReachesTheArchitectureShape` warns
  when a classification reaches no element at all, which used to fail in silence.
- **`!BOUND(?x) || ?x` is not safe in rdflib**, which does not short-circuit `||`: the second
  operand is evaluated unbound, the filter errors, and the row is dropped. The bridge's
  "means personal" guard was written that way, so **every DPV term outside the five the editor
  lists was silently discarded** — `dpv:MedicalHealth` among them — which is the reverse of what
  the list means. Use `COALESCE(?x, true)`.
- **The business layer carries what the business knows.** Not "everything is stated in the
  process": the test is *who knows it*, because R8 makes every annotation a claim by a modeller.
  What data is involved, what sector, what purpose — the analyst knows. How the thing was built
  — implementation type, deployment setting — the architect knows, and writing it on an activity
  would record a guess as a claim. The declared domains say the same: `facet:hasPersonalDataCategory`
  is about a `beam:Data`, `facet:hasDomain` and `facet:hasPurpose` about a `beam:System`, and
  `facet:hasImplementationType` about a **`beam:Model`** — one system holds several, and an
  activity cannot say which.
- **Domain and purpose are stated from the business view and written on the system.** An activity
  refines exactly one system, so that join is **1:1** with none of the ambiguity the data bridge
  has. Written straight onto the `beam:System` by `set-system-context` rather than derived from a
  business triple, because propagating a facet as a facet is the one thing the method does not
  do. Where it is *authored* is the business view; what it is a property of is the system.
  `pair:SystemContextOption` is the list the editor offers and the writer validates against, so
  the two cannot disagree. **Purpose carries six DPV core terms; domain is empty**, because DPV
  publishes sector *extensions* — six namespaces, each contributing purposes — and no sector
  concepts to assign (checked against the 2.3 index, 2026-10-04). Minting local sectors breaks
  R3 and using an extension's namespace IRI as a `skos:Concept` is type-incorrect. Filling the
  list in is a data change and nothing else.
- **"Not personal" is a claim, not silence.** The two DPV values meaning not personal
  (`dpv:AnonymisedData`, `dpv:NonPersonalData`) are excluded from the bridge *and* offered in
  the UI on purpose: "checked, and not personal" must not collapse into the silence of never
  having said anything.
- **Never write a raw path over `bp:sourceRef` / `bp:targetRef`.** They are declared on five
  classes, so a property path over them walks out of control flow, through a data association,
  and back in somewhere unrelated — and the result looks like evidence. `business_flow.rq`
  materialises one *typed* hop as `pair:businessFollows`; every condition downstream uses a
  plain transitive path over that.
- **Scoping to one architecture is a traversal, not stored state.** `pair:refinedBy` names the
  system and `beam:hasProcess` / `hasResource` / `hasAgent` / `contain` say what it holds, so
  `graph_view._members_of()` answers "the architecture behind THIS activity". There is no
  database and there must not be one for this. The same membership draws the per-system
  boundary on the canvas.
- **A system boundary is not bookkeeping.** Splitting a graph into the capabilities the
  diagram separates changes which findings clear: an escape that asks only that the reviewed
  step and the output belong to the *same* system will clear too much if unrelated
  capabilities are modelled as one system.
- **sBPMN cannot express an expression body**, so a `conditionExpression` carries its readable
  text on `rdfs:label`. `bp:value` is declared for `categoryValue` alone, and
  `bp:documentation` points at a node with no text property — BPMN puts it in XML mixed
  content, which sBPMN does not model. **Do not invent a `bp:` term for it.**

---

## Locked decisions — the risk view

Background: `docs/notes/risk_view_and_backward_method.md` (gitignored).

- **Elicited context scopes the reading. It never gates detection.** Everything else here
  follows from this. Gating detection on an annotation would make "we did not ask" and "it
  does not apply" indistinguishable, which is the failure R4 exists to prevent and an R10
  violation besides. `test_stating_a_scope_does_not_change_what_is_detected` strips every
  scope and stated-risk triple and asserts an identical finding set, and
  `test_a_judgement_changes_no_finding_into_or_out_of_existence` does the same for triage.
  **No `.rq` file was touched to build this view, and none may be.**
- **The method is risk storming** (Simon Brown, in the *Design It!* adaptation), not an
  invention. PAIR-AI turned out to be risk storming with steps 2 and 4 missing and step 1
  automated. Step 1 is stronger here than in C4: two machine-readable levels joined by
  `pair:refinedBy`.
- **A stated risk and a finding are different types, and stay apart.** A `beamr:Risk` attached
  by `beamr:hasRisk` is a person's claim; a `pair:RiskFinding` is a structural candidate.
  Keeping them apart is what lets them be reconciled, and the reconciliation is **computed
  from shared evidence elements, never asserted as a triple**. Asserting it would claim the
  person and the library meant the same thing. No third term was minted, because AIRO already
  had one.
- **A risk is carried by an activity as readily as by an element.** `beamr:hasRisk` ranges over
  whatever carries the risk, so the triple is the same either way and `_attachment` always
  accepted it — what blocked it was `HAND_DROP` in `risk.js` listing only `["system"]` as a
  band a drop lands on, which left activity cards unmarked and absent from the connect picker.
  `["system", "business"]` since 2026-10-04, for a risk and for a risk source. **The business
  layer joins by refinement, so neither layer stands in for the other**: a risk on the step and
  a risk on the element it refines are different claims, and both must be writable.
- **A concern draws one line per system, not one per evidence element.** Measured on the energy
  scene: the server emits 110 links, **74 of them `attaches`**, because a concern cites three to
  eight elements and drew a line to each. Three quarters of the ink said *where*, not *what*,
  which is what made the risk view read as an architecture diagram. Opening a system took the
  drawn links from 53 to 84. They now merge into one labelled line per system in `narrow()`,
  folded or not: 84 → **53**, attaches 48 → 17. **The picked concern is the exception** — a
  merged line stops at the band, and opening a system is how a reader asks which element
  exactly, so the selected concern keeps its own lines to the boxes it cites.
- **A line into a folded system names the parts it stands for.** Attachments to members of a
  folded system all land on its band, and `narrow()` deduplicated them on
  `source|target|kind` — so a risk attached to two elements drew **one** line, and picking the
  second element looked like it did nothing. They now merge into one line labelled with the
  element names (`"N elements"` past two). **Deduplicating an attachment is reporting a
  judgement nobody made**, the same error as settling half a concern.
- **Concerns that share a name say where they are.** Prompt injection is raised once per
  untrusted-content/generation pair, so three boxes reading "Candidate prompt injection
  exposure" are three true and different answers, and nothing on them said which was which.
  A concern is the (risk pattern, evidence set) group, so the **evidence is what differs**:
  `_name_the_place` picks the element fewest siblings cite, because a concern whose evidence is
  a subset of its siblings' has no element of its own and "unique to me" would leave it unnamed.
  It rides **beside** the type chip, right-aligned above the box, so it costs the card no height
  and no wrapped line. **Not on the chip**: that is the notation's type label and has to keep
  reading "Risk" — putting the place there broke
  `test_the_notation_is_drawn_rather_than_listed`, which reads the notation off the canvas, and
  it conflated the type with which instance this is. Built in the presentation layer from
  evidence labels, never stored in the graph.
- **Severity is never computed, and that is the method rather than a gap.** In risk storming
  the priority is a judgement recorded by named participants, and the review step exists to
  surface disagreement. So the tool stays scoreless and `pair:statedPriority` carries human
  priority with `pair:statedBy` provenance, which is R8-shaped like every other facet.
  `test_priority_is_carried_from_the_person_never_computed` holds it.
- **Findings group into concerns, and grouping loses nothing.** Motifs nest, so the same
  weakness at the same place arrives once per structure that reached it. Onyx raised
  `improper output handling` four times with byte-identical evidence. A concern is the
  (risk pattern, evidence set) group; `test_grouping_loses_no_finding` and
  `test_co_matching_motifs_collapse_to_one_concern` pin both halves.
- **`scopeMatch` has three values, and `unclassified` is not a polite `out`.** Nothing upstream
  maps `GoalHijack` or `InsecureAgentCommunication` to a MIT domain, so a domain filter would
  hide exactly the agentic risks a service-desk owner needs: 4 of 8 findings on the IT support
  agent reach no domain at all. The scope cannot speak to them, so the concern is shown.
  Pinned by `test_a_concern_with_no_risk_domain_is_unclassified_never_out`.
- **What narrows a review is the system boundary, not the harm domain.** Filtering Onyx's 22
  findings by MIT domain keeps 21, 12, 5 and 1, which barely narrows anything. Scoping the
  tariff scene to `CustomerRecords` marks 9 of 10 concerns out and keeps 1, while still listing
  all 10. That is what `pair:scopedToSystem` is for.
- **Triage is a node, not a literal.** `assessment_output_contract.ttl` requires exactly one
  `pair:findingStatus` per finding from a closed list of five, so a judgement has to *replace*
  the emitted status rather than sit beside it. A bare literal also cannot say who decided,
  when, or why. Hence `pair:TriageDecision` with `pair:decidesFinding` and
  `pair:decidedStatus`, living in the submitted graph and applied by `_apply_triage`. Use
  `decidedStatus` and not `findingStatus`, which is declared with
  `rdfs:domain pair:RiskFinding`. The four decidable values are the contract's own vocabulary
  minus `candidate`; they were not chosen here.
- **A decision about a finding the run no longer raises is not applied.** Finding IRIs are
  deterministic so a judgement survives a re-run, but a design that changed may not raise the
  thing that was judged, and a decision must never resurrect it.
- **A concern settles only when every finding under it is decided.** Settling half of them
  would report a decision nobody made.
- **The view is a diagram because a list made the reader carry the graph in their head.**
  `risk_diagram.py` maps a run onto the AIRO chain BEAM already declares
  (`beamr:RiskSource → beamr:Risk → beamr:Consequence → beamr:Impact`, with
  `beamr:RiskControl` modifying) rather than inventing a presentation. Two properties the
  drawing must keep: **a risk sits above the elements it concerns**, inheriting its horizontal
  position from what it attaches to, which is risk storming step 3 and the whole reason the
  notation reads; and **stated is solid, derived is dashed**, without which the diagram is a
  pile rather than a reconciliation.
- **The concern detail opens folded.** It carried a paragraph, up to nine conditions and a chain
  of elements all open at once, and the parts worth acting on sat below all of it. What a concern
  **may lead to**, and the **fix** and **triage** rows, stay in view; what it is, why it fired,
  where it is and what raised it fold behind their own keys, each with a hint of how much is
  there so a reader can tell whether to open it. A closed `<details>` keeps its children in the
  DOM, so a test has to assert on `checkVisibility()` rather than on their presence or their box
  height.
- **Storming is offered, never enforced.** Showing machine findings before a team elicits
  anchors the room completely: everyone ratifies the machine and identifies nothing it missed.
  So the toggle hides concerns while the register stays usable. Enforcing it would break the
  ordinary "load example, assess" flow, and the discipline is the team's to keep.
- **"Stated only" is a bucket, not a dropped row.** An expert concern with no risk pattern in
  this library, such as provider unavailability or weak API auth, is reported as unmatched.
  Saying so is what keeps the rest credible.

---

## Locked decisions — the workbench

### The canvas

- **The BPMN canvas draws the notation sBPMN declares.** Pools banded into lanes, activities
  with task-type and loop/multi-instance markers, events (start, intermediate catching and
  throwing, end, boundary) with trigger glyphs, gateways (exclusive, parallel, inclusive,
  event-based, complex), sub-process expansion, data objects with their classification, and
  text annotations. **The vocabulary ceiling is `external/sbpmn/sbpmn_2.0.ttl`** —
  `test_bpmn_authoring.py` fails on a class or property it does not declare. A diagram that
  cannot say "this branches" asserts an order of work the model never claimed.
- **Sequence flow is routed from the model, never from adjacency.** `process_view` emits
  `sequenceFlows`; the canvas layers nodes by longest path and routes orthogonally. **Never
  draw a connector from layout order.** Whether a connection is a sequence flow or a message
  flow is read from the containment, never asked.
- **Editing is a server-side rewrite.** `/api/process-edit` and `/api/graph-edit` keep the
  Turtle in the editor as the single source of truth.
- **One gesture picks the connector, so `connect` has to check the ends.** A data box dragged
  onto another data box used to write a data association *from data to data*, which says
  nothing about who reads either one; dragged onto an event or gateway it wrote
  `bp:dataInputAssociation` outside the domain sBPMN declares for it (activity plus one of
  throwEvent / catchEvent, which the canvas cannot tell apart — so it joins data to an
  **activity** only). Both are refused as of 2026-10-04. The text-annotation branch is read
  **before** the data branch, because an annotation can be attached to a data object and what
  it needs is a plain `bpmn:association`.
- **A document is not a database, and the editor can say which.** `add-data` takes a `shape`
  (`object` | `store`); `set-data-shape` retypes in place, keeping the name, classification
  and associations a finding reads. `bp:isCollection` is declared on `dataObject` and not on
  `dataStore`, so it is dropped on a retype rather than carried into a domain sBPMN does not
  declare.
- **A band's place in the stack is the reader's to choose, and it is dragged.** Pools and lanes
  sorted by label, so a participant could not be moved where the diagram needs it — the order
  was a side effect of naming. The gesture is a grab on the band's **name strip**, which is a
  third mode of the one pointer gesture beside a node move and a pan. `reorder-band` takes the
  index the drop lands on and rewrites **every sibling**, because a half-ordered stack leaves
  the rest interleaving by name in a way nobody chose. A band with no order still falls back to
  its label, so an untouched document draws exactly as before.
  **The handle is the strip and the name, not the band.** The rotated label is painted over the
  strip rect and is a *sibling* of it, so `closest(".pc-pool-strip")` from a press on the name
  finds nothing — `elementFromPoint` at the strip's own centre returns `pc-pool-label`. Arming
  on the whole band instead would make every pan across a pool reorder the diagram, which
  `test_a_press_on_a_pool_body_still_pans` holds.
  **It is a `pair:` term on purpose**: BPMN keeps layout in BPMNDI, which sBPMN does not model,
  and `bp:ordering` is declared on `adHocSubProcess` for Parallel/Sequential — neither can say
  this, and inventing a `bp:` term is what the vocabulary ceiling forbids. Unlike a dragged box,
  which stays in `manualPositions` and is forgotten on reload, this is in the Turtle: it is the
  diagram's reading order, not a nudge.
- **A pool collapses to a band.** BPMN's black-box pool: a collapsed participant keeps its band
  and name, its members keep a slot on that band so message flow still lands on the pool, and
  nothing inside is drawn. A participant with no process is that band from the start, with no
  fold to open, and a message flow that names a participant meets the pool's edge.
- **The palette folds by measurement, not by breakpoint.** Rebuilt unfolded, measured against
  the canvas, folded when it would take more than a third of it — and it decides **both ways,
  every render**; the reader's own toggle wins from then on. Every palette button draws the
  shape it inserts using the same primitives as the canvas, so a button cannot drift from what
  clicking it produces. `fit()` insets the diagram below the palette, which floats over the
  canvas.
- **Descending to the architecture is asked for, not stumbled into.** On a refined activity the
  box only *selects* — it reveals the declaring line and stops. The blue "AI system" chip opens
  the architecture; the pencil opens the editor. An activity with no architecture behind it
  carries neither, so its box opens the editor. **One control per box, never two meanings for
  the same click.** `test_the_chip_opens_the_architecture_and_the_box_does_not` holds both
  halves.

### The front door

- **The workbench opens on the library, not an empty canvas.** `GET /api/library` serves the
  risk pattern library and the motif library **counted off the loaded graph** by
  `workbench/library.py` — never a hand-written list, for the reason `catalogue.md` records.
  Under each risk pattern it lists the motifs it applies to, drawn from their declared
  `pair:hasPatternNode` / `pair:hasPatternEdge` by `lib/motif_preview.js` and insertable with
  the existing `add-motif` edit — so a reader can work backwards: pick the risk, add the
  structure, run the assessment.
- **A detail page keeps the constituent equation's order, with conditions read inside the
  mechanism.** The structure sits in the main column; the aside reads down **Risk mechanism →
  May lead to → Suggested controls**. Applicability conditions are not a section of their own in
  the UI: they appear inside *Risk mechanism* as "raised when", because a reader takes the
  mechanism and the condition that raises it as one thing. **The backend is unchanged** — every
  risk pattern still carries its conditions, and `test_every_risk_pattern_carries_the_constituents_it_is_defined_by`
  still holds the API to all five constituents.
- **The mechanism leads, at every width.** It is the `lead` grid area: top of the aside when
  wide, first on the page when narrow. As the last panel of the main column it sat below three
  diagrams, the panel a reader had to scroll furthest to reach.
  `test_a_risk_page_leads_with_its_mechanism` checks it is in view at 1400 and 1000 px.
- **Every detail page is one shape**: a hero (eyebrow naming the level, title, source, one-line
  lede, a strip of counts), then `lead` / main / aside panels with 16px headings. The way back
  is a full `.btn` on the right of the hero, named for where it goes ("All risk patterns"); it
  was a 12px "‹ all" at the far left. A panel's explanation is one line under its heading or
  the heading's tooltip, never a paragraph: a sentence under every heading is what made these
  pages a wall. **Candidate framing survives the cut** — "A match alone is not a finding",
  "Possible harm, never an observed outcome", "Candidates, not proof the risk is removed".
- **A diagram is kept inside its panel four ways, and the guard proves it can see a breach.**
  `.library-detail` hides horizontal overflow, the SVG has `max-width: 100%`, the preview clips,
  and the preview is a flex container its SVG shrinks inside. Any one is enough: removing three
  left the page fitting, and only removing all four reproduced the breach — measured at
  **306 px** at 1400 wide, which is the overflow that once scrolled the page sideways and cut
  the first letter off every line.
- **Every motif–risk link is carried or names its context, and both are proven.** A motif
  carries a risk pattern when inserting it alone raises the pattern through its own match
  (misinformation via LLM-based IR: the model makes up what it returns). Otherwise the risk
  depends on what the elements are about — public input, personal data, a hosted model, a
  credential — or on what surrounds the motif, such as a training step upstream of a served
  model. `workbench/risk_context.py` states that context per link, in words and as the
  annotations and elements that make the conditions hold; a risk page shows it under each motif,
  and "Add to canvas" there inserts the motif with it, so picking a risk, adding a motif and
  running the assessment raises it. `test_motif_risk_links.py` builds every link exactly as
  `add-motif` does: carried links fire bare, the rest fire with their context, and **no context
  is named for a link the motif already carries**. Until 2026-10-09, 88 of 124 links raised
  nothing when their motif was inserted, and four supply chain links could not fire at all,
  because the query read only External Dependency matches. A link that fires under no context is
  removed rather than kept: Model in Image and Training to Serving train their own artifact, so
  nothing in them enters from outside. **Context never gates detection** — it lives in the
  workbench, no query reads it, and a submitted graph is assessed exactly as before.
- **Two risk patterns name no motif and must keep saying so** rather than showing an empty heading:
  `ExcessiveAgency` and `SensitiveInformationDisclosure` are evaluated over any motif match
  whose conditions hold.
- **The library is drawn, not written.** A motif is a shape, so its card carries `motifPreview`
  of its own declaration rather than a paragraph restating it; a term belongs to one side of a
  bipartite graph, so it and its shelf carry the canvas's own swatch for its class. Both were
  paragraphs, and 97 of them is a wall nobody reads. The colours are the canvas's own `--node-*`
  tokens and the class-to-kind mapping is `kindOf` in `motif_preview.js` — **do not add a third
  copy**, `graph_view.py` already holds the server-side one. **The swatch draws what the canvas
  draws**: what flows rounded, a step square-cornered, a model as a hexagon. An earlier shelf
  marker drew a step as an oval and contradicted the canvas beside it.
- **`kindOf` names the process classes; it never assumes one.** Its fallback was `"process"`, so
  the one `beam:Resource` node in the library (External Dependency) was drawn as a step and its
  `step beam:use resource` edge read as process to process — on the page that exists to teach
  the bipartite rule. Resource maps to `resource`, anything unnamed to `other`, and the canvas
  rounds a `resource` like data. `test_no_motif_is_drawn_with_a_step_feeding_a_step` reads all
  31 declarations through the preview's own mapping: **every drawn edge crosses sides**, the
  drawing-level twin of `test_every_pattern_edge_crosses_between_an_oval_and_a_box`.
- **A term's page shows where it sits.** `motifPreview(template, { highlight })` marks the nodes
  playing given roles, so each structure that reads the term is drawn with that element
  outlined — dashed when the structure is reached through a term this one refines, with the
  ancestor role marked instead. The panels are **Related motifs** and **Related risk patterns**.
- **A term is related to a risk pattern, never said to raise it.** The link is "a motif that
  names this term carries that risk pattern", which says nothing about which side the term is
  on. `Guardrail Decision` reaches *Improper output handling* and *System prompt leakage* only
  through `GuardrailsMotif`, and in both risk queries an output guardrail step is the
  `FILTER NOT EXISTS` escape: the guardrail clears those findings. The panel was called "May
  help raise", which said the opposite. Telling a precondition from an escape would mean
  reading the risk queries' text, which nothing does yet.
- **A term is dimmed only when no motif reaches it**, which is 11, never when no pattern node
  names it, which is 25. The other 14 are read through the term they refine and are in full
  use; dimming them would say the opposite. The count on a card says which: **solid is how
  many motifs name it, outlined is how many it reaches by refinement**, so the rail's 0 beside
  `Reranked Context` and the card's outlined 8 are two true facts rather than a contradiction.
  It replaced a four-segment bar, which topped out at four and could not tell the two apart.
- **The motif thumbnail is a silhouette: the landing hides `.mp-label`.** A nine-node motif
  scaled into a card renders its labels at about four pixels, which is decoration. The shape
  is what separates two motifs at that size, each node keeps its `<title>` for hover, and the
  detail view carries the labelled drawing.
- **The rail folds by group on every tab; Motifs and Terms open folded, Risks open.** Motifs
  and terms as one column give a reader no way to put part of the library aside, so their first
  view is the shelves: the state is the set of groups the reader *opened*, starting empty. Risks
  was flat while it held 15 entries and is shelved by family since it holds 33 (asked for
  2026-10-09), but it is the front door, so its families start open and fold on a click. Two
  things the fold has to respect: a search unfolds everything, or a match inside a folded group would read
  as no match; and `select()` opens the group holding what it selected, or the landing would
  point at a hidden row.
- **There is no "Start from a risk" button.** The risk level is not an entry point in the
  current build, so the front door offers the two layers that are.
- **The front door steps aside on content, and only the front door.** `settleChoice()` emits
  `choice:settled`; the library closes on it *only* when it was opened as the opening screen.
  Adding a motif leaves opening mode first, so the library stays put — picking one risk usually
  means adding more than one motif.
- **A risk pattern with no `dct:description` borrows the definition of the entry it was derived
  from, attributed.** The taxonomy entry names the risk; the risk pattern says when the library
  raises it. The two must not be presented as one sentence.
- **Risk patterns are shelved by the kind of system, never by harm.** A risk pattern is a
  weakness in a design; the risk is the harm it may end in, and a shelf must not blur the two.
  So the shelf is `pair:riskPatternFamily`, from the motif family scheme — GenAI 10, Agentic 11,
  ML serving and training 11, Supply chain 1 — the family most of its motifs belong to,
  with no groups inside it. It is a filing decision like `motifFamily`: no query reads it, and
  `test_every_risk_pattern_is_shelved_where_its_motifs_are` holds it to a family one of its
  motifs is in. The two motif-free patterns are filed by judgement. The consequence
  travels with the entry as **may lead to** chips, and the detail groups entries by the domain
  each rolls up to (`mayIndicateRisk` → `skos:broader` into
  `mit:MIT_AI_Risk_Repository_Domain_Taxonomy`) so a reader sees which link produced which
  domain. Entries rolling up to nothing are listed as **also catalogued as** — a citation, not
  an outcome. **OWASP is a source**, shown as `source:` beside the risk pattern's name, never as a
  category and never as a code chip standing in for the name.
- **Do not curate a link without a source.** `GoalHijack` and `InsecureAgentCommunication` reach
  no risk domain, because nothing upstream maps an OWASP entry to one. The page says so ("no
  risk domain linked"). `test_what_a_pattern_may_lead_to_is_traversed_never_asserted` pins both
  halves: every served domain is re-derived from the graph, and that set of two is asserted.
- **Motifs are shelved by family, and the shelving is data.** `pair:motifFamily` puts every
  motif in one concept of `pair:MotifFamilyScheme` — **GenAI** (13), **ML serving and
  training** (13), **Agentic** (4), **Supply chain** (1). It is a filing decision about *this
  library*, never a reading of a submitted architecture: **no match query may read it** (R2, and
  `test_no_match_query_reads_the_motif_family` enforces it), and one system routinely matches
  several families at once. A motif shelved twice or not at all fails
  `test_library_consistency.py`.

### The annotation vocabulary

- **A term is shelved by the BEAM class it goes on, not by its top-level role.** The role
  hierarchy cannot shelve 97 terms: it has 4 tops and they hold **50 / 32 / 12 / 3**, so half
  the vocabulary sat under `Resource Role`. The shelf is `pair:expectedClass`, read off the
  pattern nodes that name the term and inherited along `pair:subRoleOf` for the 25 terms no
  pattern node names — **7 shelves, every term filed**: Data 39, Process 33, Statistical
  Model 10, Transform 5, Resource 4, Infer 3, Train 3. It answers the question a reader
  settles before any other, which the role tree never asked: *can this term go on this
  element at all?* Where a term declares several classes the shelf is the **most general**
  of them, because `GenerationStep` is `beam:Infer` on one pattern node and `beam:Process`
  on another. **Sort the parents**: a role with several resolves through the first one and
  rdflib hands them back in set order, so `ExternalModel` shelved differently from run to
  run until `_role_parents` sorted them.
- **`appliesTo` is derived from what the queries write, not from what the motif declares —
  and it orders the picker rather than filtering it.** The two sides are typed differently:
  a step is guarded `a/rdfs:subClassOf* beam:Process` in **all 62** places one appears, so a
  node declared `beam:Infer` binds a `beam:Generate` element and **the role is the
  discriminator**; a resource is typed with a bare `a beam:Data` (67×) or
  `a beam:StatisticalModel` (19×), which walks nothing. Deriving the fit from
  `pair:expectedClass` alone put **13 annotations in baseline-pinned graphs** on the wrong
  side of their own element, `GenerationStep` among them.
  **And it must not hide, because some queries are looser than their declaration.**
  `information_retrieval.rq` puts **no class constraint on any of its three resource nodes**,
  only the role — so `IR_QueryNode`, declared `expectedClass beam:Data`, binds the
  `beam:Symbol` element `SPARQL Query Template` in `simple_graph_rag.ttl`. That is 1 of the
  148 element bindings across the tracked graphs, and 5 annotations depend on it. So the
  shelf that fits sorts first, the rest are marked *"not this element"* and stay reachable,
  and the only hard filter is the coarse process/resource split with its existing escape.
  `test_no_annotation_in_a_tracked_graph_is_reported_as_not_fitting` is the guard.
- **A family is read off the motifs that name a term, and is never inherited.**
  `HumanOversightMotif` declares a `ResourceRole` wildcard node, so inheriting through
  ancestors tags **all 53** resource-side terms Agentic — true, and useless, because a filter
  matching everything is not a filter. Direct naming gives Agentic 10 / GenAI 36 / ML 28 /
  Supply chain 1. **A term with no family of its own is never hidden by a family filter**: it
  is a refinement that inherits, and `serves` is the field that says so. Skipping top-level
  ancestors instead was measured and rejected — it leaves `RewrittenQuery` reaching nothing.
- **`motifs` and `serves` are two different facts and must stay apart.** `motifs` are the
  motifs whose pattern nodes name the term itself; `serves` are those it reaches by refining
  a term they name, which is what `playsRole/subRoleOf*` walks. Collapsing them would either
  report a refinement as inert or report every term as agentic.
- **Every term states its origin, by R6's three routes, and the chain is walked.** Measured:
  **50 stated** (`dct:source`), **35 mapped** (SKOS), **12 inherited** through
  `pair:subRoleOf`. An inherited origin names the term it came through, because "grounded by
  the term it specializes" is not the same claim as having cited a source.
  `test_every_term_says_where_it_comes_from` holds all three.
  **The term page does not show it yet** (`SHOW_TERM_PROVENANCE = false` in `library.js`, since
  2026-10-07): several role mappings point at a source that does not match the term's name, and
  the KG is being reviewed by hand. The API keeps serving provenance and its test keeps holding;
  only the panel is hidden. Turn the flag back on once the mappings are clean.
- **The picker is a combobox, not a `<select>`.** A native select can neither search nor show
  a definition, and **all 97 terms carry a `skos:definition` the UI served none of**. That is
  what made `RetrievedContext`, `RetrievedResult` and `DocumentChunk` undecidable in a scroll
  of bare labels. Definitions are served for the 7 data categories too.
- **A shelf heading is a band, not a caption.** It carries the canvas swatch for its class,
  an edge in the class's colour and a count, and it is sticky inside its own `.mp-group`, so
  the class a term goes on stays in view while its terms scroll and leaves with the last one.
  It was a 10px grey line that disappeared under the list it named.
- **The popover is `position: fixed`, placed from the trigger.** `.node-detail` is
  `overflow: auto` with a `max-height`, so an absolutely-positioned child is clipped to about
  two rows that nothing can scroll. It is placed from `getBoundingClientRect()`, flipped up
  when the space below is short, and repositioned on scroll and resize because the popup it
  sits in scrolls under it.
- **The canvas wheel handler must skip the overlays.** `.palette`, `.motif-palette`,
  `.node-detail` and `.mp-pop` are children of `#canvas-wrap`, and its wheel handler called
  `preventDefault()` on everything outside the business level — so a 31-entry tray taller
  than the viewport could not be reached with a mouse at all, and the wheel zoomed instead.
  `OVERLAYS` in `graph_view.js` is the list; add to it when a new scrolling overlay lands
  inside the wrap.
- **The motif tray is shelved by family, like the library shelf.** 31 entries in one
  alphabetical column said nothing about which kind of AI system each is a shape of, so
  `motif_template_list()` carries `pair:motifFamily` and the tray groups on it: Agentic 4,
  GenAI 13, ML serving and training 13, Supply chain 1. It is the same filing decision as the
  library's, so the same rule holds — **no match query may read it** (R2).
- **6 terms are inert — nothing in the 62 registered queries reads them**, directly or by
  subsumption. Three are abstract tops and are fine (`Control Step`, `Processing Step`,
  `Resource Role`). Three are not: **`Document Chunk`, `Embedding Vector`,
  `Pseudonymization Step`** look usable and do nothing when applied. Open item; the rule is
  that declared-but-unused vocabulary gets removed, not documented.
- **A small ODP/OQP drift, recorded so it is not rediscovered.** `Resource Role` is declared
  on a pattern node but named in no `.rq`; `Pre-trained Model` and `State Changing Step` are
  named in a `.rq` but on no pattern node.
- **The gap report's element candidates are not annotation suggestions.** `motif_gaps()`
  filters near-misses by BEAM class alone, so on the helpdesk graph it emits **428**
  element-level hints and offers the same four processes for Embedding Step, Chunking Step and
  Reranking Step. Filtering by the motif's own declared edges cuts 706 candidates to **122**,
  and a ≥50% satisfaction threshold to **12 across 3 motifs** — measured, not implemented. Do
  not describe the gap report as suggesting annotations until that filter exists.

### Controls and chrome

- **Three control tiers, one size.** `.btn.small.primary` commits, `.btn.small` is secondary,
  `button.chip.clickable` is a quiet inline action in a row of metadata, and `.danger` marks a
  destructive one in whichever tier it sits. They share a height, a corner radius and a focus
  ring. The quiet tier was a bare `.chip` with a click handler and **no rule of its own**, so a
  row mixing it with real buttons measured **21, 21, 27, 27** — which is what made the rail look
  assembled by accident. `test_the_control_tiers_render_at_one_size` measures all four under the
  real stylesheet, because the contract is what drifts.
- **A disclosure marker is drawn, never typed.** Both `.concern-fold` and `.rail-section` wrote
  their triangle as a CSS escape, and the tooling that writes this stylesheet turned it into a
  **raw U+0015 byte**, so every arrow in the rail rendered as tofu followed by `b8`. They are
  CSS triangles made of borders now: no glyph, no escape, no font to depend on, and the open
  state is a `rotate(90deg)` rather than a second character. **Do not reintroduce a `content:`
  escape in this file** — it has been mangled twice.
- **Nothing in the rail may be wider than the rail.** `.scope-add-body` carried a fixed
  `width: 320px` inside a narrower panel, which put a horizontal scrollbar under the whole
  detail. Widths there are `max-width: 100%` with `min-width: 0` on the descendants, since a
  flex child defaults to `min-width: auto` and refuses to shrink.

### The front end

- **Native ES modules, and the shape is enforced.** `webapp/static/` is `app.js` (entry: wiring
  only) + `state.js` + `core/` (plumbing that knows nothing about the workbench) + `lib/`
  (self-contained renderers and widgets) + `panels/` (one file per thing on screen).
  `test_webapp_module_layout.py` holds three rules: **no import cycles**, **every imported name
  is actually exported**, and **exactly one browser global** (`window.PairAI`).
- **`core/bus.js` carries four events, and each one earns its place.** A panel emits rather
  than calling across only when the thing it changes is drawn by a panel it must not import.
  Counted 2026-09-14: `scope:changed` (canvas and findings both redraw), `choice:settled`,
  `document:replaced`, and `assessment:rendered` (the risk level reads a run it does not
  draw). **Adding a fifth means naming which two panels must not import each other.** A bus
  that grows without that justification is calling across with extra steps.
- **`state.js` is one mutated object, not exported variables.** An imported binding is
  read-only for the importer, so `scopedSystem = null` in a panel would not reach the canvas
  that draws the scope — and would not even be legal.
- **The web layer holds no library knowledge.** `webapp/routes/` parses a payload, calls in, and
  shapes a response; `webapp/runtime.py` holds the process-wide SPARQL lock and the start-up
  warm-up. Anything that *decides* something about the library — motif templates, the gap
  report, the role/category vocabulary, SHACL report shaping — lives in `airiskkg/workbench/`,
  importable without Flask.
- **Each fact lives once.** The taxonomy-source table (which catalogue an IRI belongs to) is in
  `workbench/terms.py`, and `assessment_view` reads it from there rather than holding a copy.
- **The canvases are only ever tested with real input.**
  `dispatchEvent(new MouseEvent(...))` lands on whatever element you name it at, so it proves
  nothing when pointer capture is retargeting real clicks. `test_canvas_interaction.py` drives
  the DevTools protocol; `test_canvas_renders.py` loads the page in a headless browser.
  **Assert on what is painted.**

---

## Controls and mitigation

- **A control clears a finding by being built, not by being asserted.** A risk query whose only
  escape is a triple no example, rewrite, or UI ever writes is unfalsifiable by design work.
  **Do not reintroduce an escape nothing can satisfy** — `beamr:associatedTo` was removed from
  all fifteen risk queries for exactly this reason, and the output was byte-identical.
- **Four risk patterns are unclearable by design, and that is correct.**
  `DataAndModelPoisoning`, `SupplyChainCompromise` and `VectorAndEmbeddingWeakness`
  (`data_model_poisoning.rq`, `supply_chain.rq`, `vector_embedding_weakness.rq`) rest on
  provenance and vetting — non-technical controls with no runtime shape — and
  `TrainingDataMembershipInference` rests on how the model is trained. No structural
  escape exists to write. Those four and `evaluation_data_contamination.rq` are the 5 of 29
  risk queries carrying no `FILTER NOT EXISTS`; contamination is still clearable, because its
  condition *is* the shared data, and giving the evaluation its own removes it. The answer is **finding-level triage**, not a query escape:
  `pair:findingStatus` is the extension point, finding IRIs are deterministic so a judgement
  survives re-runs, and "accepted, handled by process" is a human act recorded against the
  finding rather than a fabricated structural fact. Never conflate the two.
- **Carrying a `FILTER NOT EXISTS` is not the same as being clearable.** 24 of 29 risk queries
  carry at least one; several test only the structural half while the annotation half stays
  unclearable. **Audit a specific finding before telling anyone it is actionable.**
- **Applying a control is a registered SPARQL rewrite, not code.** A `pair:MitigationApplication`
  restates the vulnerable shape its `pair:mitigatesRiskPattern` found and CONSTRUCTs the step
  that interrupts it, bound to the elements the finding already cites — so nothing guesses which
  evidence element is which. Registered like any other query (`pair:implementsControl` +
  `implementationPath`), run on demand via `apply_control()`, scoped by `initBindings`.
  Inserted IRIs derive from the elements they screen, so re-applying is a no-op.
- **The output type is the safety catch.** The pipeline asks only for MotifMatch and RiskFinding,
  so a rewrite never runs inside an assessment — if it did, every finding would mitigate itself
  and none would be reported.
  `test_a_mitigation_rewrite_never_runs_during_an_assessment` enforces this.
- **Rewrites are keyed on (control, risk pattern), never on the control alone.** The same control
  answers several risk patterns while a rewrite is written against one vulnerable shape. Findings
  carry `pair:generatedByRiskPattern` so a finding routes to the rewrite written for it. A
  control with no rewrite *for that finding's risk pattern* reports `applicable: false` rather than
  offering a button that does nothing.
- **A control barrier must be earned, not assumed.** The `content_categories.rq` barrier
  covers output guardrails, because a screened output must not inherit the
  categories the screen exists to stop — but `dpv:PseudonymisedData` is a kind of
  `dpv:PersonalData`, so sensitivity must **survive** pseudonymisation.
- **A risk that fires on several paths needs a control on each.** Prompt injection is per
  untrusted-content/generation pair.
- **Control motifs are sized to the risk, not to the vocabulary.** `GuardrailsMotif` is 8 nodes
  and 7 edges; prompt injection needs an input screen and nothing else, so
  `InputScreeningMotif` (4 nodes, 3 edges) and `OutputScreeningMotif` (3 and 2) nest inside it.
  A control whose `pair:realizedByMotif` points at a motif far larger than the risk it addresses
  is not actionable — that motif is what the canvas offers to insert.
- **`pair:realizedByMotif` marks a candidate structural mitigation**, not proof that inserting
  the motif removes the risk — and several realizing motifs are themselves risk-bearing.

---

## Naming

Prefix is **`pair:`** (`http://w3id.org/airiskkg/pair-ai#`). Pattern instances use `pat:`;
taxonomies use `owasp:` / `asi:` / `atlas:` / `mit:` / `nist:` / `nexus:`. **`rp:` appears
nowhere in the ontology.**

| Term | Meaning |
| --- | --- |
| `pair:RiskPattern` | The AI risk pattern entity. |
| `pair:ApplicabilityCondition` | With `pair:PropertyPathCondition` for conditions evaluated via a SPARQL property path (reachability). |
| `pair:GraphMotif` / `pair:PatternImplementation` / `pair:MotifMatch` | The ODP / the OQP / the instantiation, materialized with explicit `pair:hasNodeBinding` bindings. |
| `pair:hasEvidence` | Property on `pair:RiskFinding`. |
| `pair:RiskFinding` | Carries taxonomy entries on `pair:hasCandidateRiskTaxonomyEntry` and status on `pair:findingStatus`. **The assessed system is not asserted on the finding** — derive it by traversing from an evidence element to the containing `beam:System`. |
| `pair:controlNature` | technical / non-technical. |
| `pair:suggestedControl` | Only project-authored `pat:Control_*` concepts appear here; MIT `mitctrl:*` families are reached as an evidence layer through taxonomy links. |
| `pair:identifiesCandidateRisk` | **Declared but not emitted.** No finding links to a `beamr:Risk`, and no alignment exists between `nexus:Risk` and `beamr:Risk`. Open item — do not write docs implying it works. |

Two curated collections: **Motif Library** (risk-neutral) and **Risk Pattern Library**.

If code or TTL still uses old names, that is migration debt — fix toward the new names, never
toward the old ones.

---

## Repo layout

Three kinds of thing, kept apart on purpose: knowledge (`ontology/`), contracts (`shacl/`),
and code (`python/`).

### Knowledge

| Path | Contents |
| --- | --- |
| `ontology/core/` | `beam_core.ttl`, `beam_core_risk.ttl`, `pair_ai_pattern.ttl` (pattern meta-vocabulary). |
| `ontology/patterns/` | `motif.ttl`, `risk_pattern_library.ttl`, `control_mitigation_layer.ttl`. |
| `ontology/patterns/implementation/` | Executable SPARQL CONSTRUCTs: `match/` (one per motif), `risk/` (one per risk pattern), `propagation/` (derived-fact rules, re-run to a fixed point by the runner), `mitigation/` (control rewrites). |
| `ontology/facets/` | SKOS characterization facets: `task.ttl`, `context.ttl`, `autonomy.ttl`, `data_facets.ttl`, `implementation_type.ttl`, `facet_properties.ttl`. **Data Category is not here.** |
| `ontology/alignments/` | External vocabulary adapters (Tool4Boxology, DPV; later AgentO). |
| `ontology/taxonomy/` | IBM Atlas, OWASP LLM, OWASP Agentic (ASI), MIT, NIST AI 600-1, ML risks (Zhang et al., 2022), Eticas, plus the tiered cross-taxonomy mappings. |
| `ontology/context/` | The business layer bridge. `bpmn_context.ttl` declares `pair:refinedBy`, `pair:businessFollows`, `pair:BusinessFlowDerivation`, and registers `business_flow.rq` and `business_data_bridge.rq` in `context/implementation/`. |
| `ontology/visualization/` | Standalone SPARQL run by hand, referenced by no declaration. |
| `data/mappings/` | **Source data, not knowledge.** `Final_Mapped_Taxonomy_Table_Output.csv` is the 93-row OWASP → IBM Atlas → MIT action cross-walk that `mit_mitigation_action.ttl` names as its `dct:source` and `generate_mit_action_layer.py` reads. Tracked, and deliberately outside the `.dockerignore` allow-list — the image does not need it, but a clone cannot regenerate the action layer without it. |
| `data/eticas.ttl` | **Source data.** The Eticas AI Risk Taxonomy as published (CC BY 4.0). `generate_eticas_layer.py` writes `ontology/taxonomy/eticas_risk.ttl` from it, keeping a published mapping only where the target is a concept this KB declares or a DPV term. **Eticas writes `broadMatch` and `narrowMatch` the other way round from SKOS** ("data-poisoning narrowMatch MIT 2.2" means poisoning is the narrower), and not uniformly, so those rows are neither adopted nor inverted; nor is an `exactMatch` that would make two catalogues' entries identical. The generated header counts every dropped row by reason. |

**`.rq` paths are data.** Each query is registered by a `pair:PatternImplementation` whose
`pair:implementationPath` is a literal string, so **moving or renaming a query means updating
its declaration in the same commit**. Adding a query is likewise a two-part change — the `.rq`
*and* the registration. `test_library_consistency.py` catches an orphaned query or a dangling
path. New taxonomy files need no wiring: `load_base_graph` globs `ontology/taxonomy/*.ttl`.

### Contracts

`shacl/` answers three different questions:

- `architecture_input_contract.ttl` — is this graph acceptable? (Violations)
- `assessment_output_contract.ttl` — are emitted findings well formed?
- `annotation_guidance.ttl` — will this annotation actually match anything?

**Every guidance shape is `sh:Info` or `sh:Warning`, never `sh:Violation`** — it cannot change
whether a graph conforms, and a test enforces that.

**A malformed edge is caught in three places, and all three must agree.** BEAM declares a domain
and range for every flow predicate, but **no reasoner runs**, so `ex:a beam:use ex:b` between two
data nodes parses cleanly and used to reach the graph unchallenged. Now: `edgeTriple()` in
`graph_view.js` refuses the drag, `flow_endpoint_error()` in `airiskkg/graph_view.py` refuses the
`add-edge` request (the editor is the source of truth, so a payload can arrive the canvas never
vetted), and `sh:Violation` shapes in `architecture_input_contract.ttl` reject the graph — the
flow-predicate ends, `aic:NoProcessToProcessEdgeShape` for a surviving `beam:inform`, and
`aic:ElementIsOneKindShape` for an element typed both ways. Added 2026-10-04; all 274 flow edges
in the tracked graphs already conformed. **The deciding fact is that an end's kind decides the
edge**: an end carrying no BEAM type at all is allowed through the editor so an edge can be drawn
before the node is typed, and the contract still rejects it.

**The process canvas has the same rule.** `connect` picks the connector from what it joins, so a
data box dragged onto another data box used to write a data association *from data to data*, and
onto an event or gateway wrote `bp:dataInputAssociation` outside the domain sBPMN declares for it
(activity plus one of throwEvent / catchEvent, which the canvas cannot tell apart — so it joins
data to an **activity** only). The text-annotation branch is read **before** the data branch,
because an annotation can be attached to a data object and needs a plain `bpmn:association`.

### Code

| Path | Contents |
| --- | --- |
| `python/src/airiskkg/` | Pipeline, CLI, webapp, workbench. The package root is `python/`, not the repo root; `airiskkg.paths` resolves back by walking up until it finds both `ontology/` and `python/`. |
| `python/scripts/` | **Tracked tooling** — something depends on each of these. |
| `python/scripts/local/` | **Gitignored scratch** — one-off and personal scripts. |
| `python/tests/` | Test suite. |
| `python/tests/fixtures/` | Graphs a test needs that the deployment does not offer. |
| `outputs/` | Generated matches and findings — assessment output, not knowledge. Untracked. |

**A script earns `python/scripts/` by being depended on**: a test imports or invokes it
(`validate_graphs.py`, `normalize_t4b.py`, `generate_mapping_provenance.py`), or it rewrites a tracked file
(`generate_mit_action_layer.py` writes `ontology/taxonomy/mit_mitigation_action.ttl`,
`generate_eticas_layer.py` writes `ontology/taxonomy/eticas_risk.ttl`,
`generate_risk_control_linkage.py` writes `docs/reference/risk_control_linkage.md`; it refuses to
run when a control is missing from its `CONTROL_ORDER`, which section 3 walks).
`export_ontology.py`, `pattern_provenance_worklist.py` and `role_provenance_export.py` met none
of those and now sit in `local/`. **A tracked file that says "regenerate with X" while X
is gitignored cannot be regenerated from a clone** — the artifact stops being reproducible, which is the
whole reason it is checked in. Moving a script means updating its callers in the same commit.

**Removed 2026-10-04: the competency questions and everything that ran them.** Commit `20dc12b`
deleted all 27 `docs/reference/competency_questions/*.rq`, which left `run_competency_questions.py`
globbing a directory that no longer exists and `test_competency_questions.py` erroring at module
setup on every run. The script, the test and `competency_questions.md` are gone with them. They
are one command away if the questions are ever reinstated:
`git checkout 20dc12b^ -- docs/reference/competency_questions/` plus
`git checkout 20dc12b~1 -- python/scripts/run_competency_questions.py`.

`assessment_runner` and `paths` keep their import paths on purpose: the evaluation harness in
the gitignored `docs/evaluation/` imports them and cannot be updated from a clone.

### Example graphs

- **`ontology/example/` — what the deployment offers, and only that**: `simple_graph_rag.ttl`,
  `it_support_agent.ttl`, and `context/it_service_desk.ttl`. This is the list the example
  dropdown shows, so it stays small on purpose.
- **`python/tests/fixtures/` — graphs a test needs that the deployment does not offer**:
  `onyx_rag_chatbot.ttl` (the only graph exercising query rewriting, reranking, embeddings and
  supply chain), `ml_credit_scoring.ttl` (the only graph that trains or serves a classical
  model, and so the only one the ML risk patterns fire on), `wien_energie_bottina.ttl`,
  `wien_energie_tariff_change.ttl`, and
  `context/energy_customer_service.ttl` + `context/energy_tariff_change.ttl`.
  Tracked, so a fresh clone passes; outside `ontology/example/`, so nothing offers them.
  **Retiring a graph from the offered set must not retire the coverage that rested on it** —
  that is what this directory is for.
- **`ontology/example_local/` — the user's own graphs: gitignored, and not in the Docker
  image.** Confidential and NDA-covered architectures live here; only its `README.md` is
  tracked. **Nothing in the test suite or the shipped library may read from it** — a fresh
  clone has to pass. `test_private_examples.py` enforces that, plus the ignore rule, the
  `.dockerignore` allow-list, and that a WSGI app neither lists nor serves the folder. Serving
  it is opt-in via `create_app(local_examples=True)`, which only `cli serve` does.
- **`docs/example_UC/` — NDA-covered use-case graphs, gitignored.** `paths.EXAMPLE_UC_DIR`
  resolves it for local runs only; never add a test or example that reads from there.
- Every tracked graph is pinned by `test_propagation.py`, which fails if one arrives without a
  baseline, and validated by `test_input_contract.py`.

**Never name an example file in a test.** They get renamed, and each rename breaks suites for
reasons unrelated to what they test. Resolve one through
`tests/conftest.py::example_path(NAMESPACE)` or `process_path(NAME)`, which look in the offered
set first and fall back to the fixtures — **renaming a file is a filing decision, changing a
namespace is a modelling one.**

### Packaging

**`.dockerignore` is an allow-list, and must stay one.** `COPY . /app` once shipped a
gitignored NDA-covered directory, because `.gitignore` and `.dockerignore` are unrelated files.
It now excludes `*` and names what the app reads, so a new private directory is left out by
default rather than by vigilance. **Never convert it back to a deny-list**; when the app starts
reading a new path, add a `!` line and rebuild.

`external/tool4boxology/` holds the vendored schema and a sample export; attribution in
`NOTICE.md`. Export quirks the normalizer must handle: lowercase type URIs (`t4b:transform` vs
`t4b:Transform`), the ontology declares `patternProcess` but exports `hasProcess`, and
instances are multi-typed with `t4b:Component`.

---

## Working conventions

### Git

Branch per feature; one labeled commit per task; **never commit directly to main.**

### Testing

```bash
cd python
pytest                # default: everything except the browser suites
pytest -m browser     # the two suites that drive a real headless Chrome or Edge
pytest -m ""          # everything
```

The browser suites are ~70% of the wall clock and need a browser installed, so they carry
`pytestmark = pytest.mark.browser` and `addopts = "-m 'not browser'"` deselects them. **Run
`pytest -m ""` before calling a change to the canvas, the page, or the endpoints done.** `ui`
marks workbench-feature suites that need no browser; those stay in the default run.

### After every ontology change

Parse all `.ttl` with RDFLib, run pyshacl where shapes exist, re-run the assessment on the
tracked examples, and **explain any diff**. **Diff the finding set, not the count** — and read
the composition, never the total. Matches are `pair:MotifMatch` instances, not distinct motifs;
nested motifs co-match by design, so the number is structural coverage.

`test_propagation.py` asserts the per-graph baselines and names the graphs by namespace.
`test_agentic_assessment.py` covers the agentic layer with an inline graph;
`it_support_agent.ttl` covers it as a bundled example.

When library counts change, **update `docs/reference/catalogue.md` in the same commit** —
nothing regenerates it.

### Performance and correctness traps

- **rdflib's SPARQL compiler is not thread-safe.** pyparsing keeps global parser state, so two
  threads compiling at once corrupt it and surface as "`Param.postParse2() missing 1 required
  positional argument`". Compilation is serialized in `assessment_runner._prepared_query`; keep
  it there rather than locking in a caller, and **never parse SPARQL off the main thread outside
  that function.**
- **Clause order is load-bearing in a risk query.** rdflib has no query optimizer: it evaluates
  a BGP in textual order and applies a FILTER to its whole group. Every risk query is written as
  `WHERE { { structure … FILTER NOT EXISTS … } curated metadata . OPTIONAL … BIND … }`. The
  metadata block (`hasMechanism` / `hasApplicabilityCondition` / `mayIndicateRisk` /
  `suggestedControl`) is a small cross product — 18 to 36 rows. Leading with it multiplies every structural join and property path by its row count —
  ~3x runtime, identical results. **Never hoist the metadata back to the top, and keep the
  structural braces**; without them the filters leave the group and fire once per metadata row.
- **The knowledge base is parsed once per process** and copied per call
  (`assessment_runner._base_knowledge`). `load_base_graph()` still hands back a fresh writable
  graph — callers parse an architecture into it — so **never return the cached instance**.
  Editing a `.ttl` in a live server needs `reload_knowledge_base()`; Flask's reloader watches
  Python only.
- **`load_base_graph()` copies ~7 800 triples, so never call it inside a loop.** Resolve what
  you need from it once and cache that. `_is_data` asked it per resource and took
  `/api/process` from 0.02 s to **4.24 s**, which slowed the browser suites enough that ten of
  them timed out — the full run went from 13:43 to 30:55 and the failures looked like flakes,
  not like a performance bug. **Anything `@lru_cache`d off the knowledge base must also be
  cleared in `reload_knowledge_base()`**, beside `data_classifications` and the rest, or a
  `.ttl` edit in a live server is invisible to it.
- **Motif templates and the gap report are generated from the declared
  `pair:hasPatternNode` / `pair:hasPatternEdge` structure**, so declaration and match query must
  stay in sync — a motif whose declaration drifts from its `.rq` produces a template that cannot
  match itself.

### Assessment provenance

**A run records what it ran on, not only what it produced.** `build_export` mints a
`prov:Activity` and, beside it, one `prov:Entity` per input — the submitted graph and the
knowledge base — each carrying `pair:contentFingerprint`, plus `pair:sourceRevision` on the
library when a repository is present (the container has none). **Inputs are entities, not
properties on the activity**, so adding a third input costs a call rather than a new predicate.
An entity's IRI *is* its fingerprint, so two runs over the same input reference one node.
`pair:assessmentFingerprint` answers "same question?"; the activity IRI stays a fresh UUID
because two runs at different times genuinely are two events.

Graph fingerprints canonicalize blank nodes and sort N-Triples before hashing — **never
`to_isomorphic(...).graph_digest()`**, whose value is rdflib's own and would break comparability
across an rdflib upgrade.

---

## Declared but not implemented

Modelled, sound, and read by nothing. **Never describe one of these as a capability of the
method**, in a paper, a demo, or a docstring. Each is an enabler waiting for the query that
consumes it, and the bar for leaving this list is a reader rather than an intention.

These are the standing exceptions to *"declared-but-unused vocabulary gets removed, not
documented"*. They are kept because the modelling is correct and externally anchored, not
because the intention is good. An item that never acquires a reader should eventually be
deleted, as `pair:maturity` was.

- **Task ≠ Capability ≠ Application Type (R7): the rule holds, the axes do not exist yet.**
  Measured 2026-09-14. **Task** has 20 SKOS concepts in `ontology/facets/task.ttl` and a
  declared `facet:hasTaskCategory`, but is read by 0 queries, 0 examples and 0 Python;
  `beam:Task` is instantiated in no graph at all, `beam:perform` is used zero times, and the
  builder offers neither term. **Capability** has no axis of its own, appearing only as two
  outbound SKOS mappings to DPV-AI. **Application Type** does not exist at all: no property,
  no concept, not even a mapping, and no home for one while OECD stays absorbed rather than
  represented.

  So R7 prevents a merge rather than enabling an analysis. That is still worth keeping, since
  the three are routinely conflated and the conflation cannot be undone once annotations
  exist. But a write-up must say one axis is modelled, two are empty, and none is consumed.
- **`facet:hasPurpose` is now written, and `facet:hasDomain` still is not.** The business view
  states a purpose on the system it refines (`set-system-context`), so the property has an
  author and a reader. Domain has the same machinery and an empty option list, for the DPV
  reason above. **No applicability condition reads either**, so neither is yet a capability of
  the method — the direct-read route is still unused. `facet:hasAutonomyLevel` and the rest of
  the situational layer remain inert.
- **The direct-read facet route.** Of the two sanctioned routes, only the bridge is live. No
  applicability condition reads a facet directly.
- **`pair:identifiesCandidateRisk`.** Declared, never emitted. No finding links to a
  `beamr:Risk`, and no alignment exists between `nexus:Risk` and `beamr:Risk`. The stated-risk
  layer deliberately does not close this, because reconciliation is computed from shared
  evidence rather than asserted.
- **R6's own-SSSOM export.** Never generated. The project consumes upstream sets, so say that
  rather than implying the export exists.

---

## Current numbers

**Re-count rather than edit by hand** — every figure but the motif count had drifted before
anyone noticed:

```python
len(set(load_base_graph().subjects(RDF.type, PAIR.GraphMotif)))   # and its siblings
```

### Library (counted off the loaded graph, 2026-10-09)

| | |
| --- | --- |
| Motifs | **47** — GenAI 20, ML serving and training 13, Agentic 13, Supply chain 1 |
| Risk patterns | **33** — GenAI 10, Agentic 11, ML serving and training 11, Supply chain 1 (35 motifs carry one; 12 carry none) |
| Pattern nodes / pattern edges | **261** / **224** — every edge crosses between an oval and a box |
| Pattern roles | **123**. The per-shelf, origin and reach figures below them were counted at 97 on 2026-10-04 and have not been re-counted since |
| Data categories | **7** |
| Facet concepts | **35** (task 20, data 11, autonomy 4) |
| Risk mechanisms | **32** |
| Applicability conditions | **34**, carried on 38 attachments |
| Controls | **30** `pat:Control_*` |
| Taxonomy entries (`nexus:Risk`) | OWASP LLM 10, OWASP ASI 10 (ASI10 catalogued only), IBM Atlas 40, MIT subdomains 18, NIST AI 600-1 10, ML risks (Zhang) 12, Eticas 67 (plus 30 Eticas groups) |
| Triples | **12 081** |
| Motif–risk links | **123** — 39 carried by the motif alone, 84 with a named context (32 annotate the motif's own elements, 52 add the surrounding elements the risk needs) |

**97 registered implementations** over 96 `.rq` files: 47 match, 33 risk, 6 propagation, 9
mitigation rewrites over 8 files (`response_verification.rq` is registered twice, under two
controls for the same risk pattern), and 2 business-context derivations under
`ontology/context/` — one of which registers as `DataCategoryPropagation`, so the runner sees 7
of those and 1 `BusinessFlowDerivation`.

### Assessment baselines (matches / findings)

| Graph | Matches | Findings |
| --- | --- | --- |
| RAG chatbot, Onyx / Danswer (broadest: 8 distinct motifs) | 14 | 24 |
| Minimal graph RAG | 3 | 7 |
| Wien Energie chatbot (BotTina) | 5 | 9 |
| Wien Energie tariff change (4 systems) | 3 | 9 |
| IT support agent (agentic) | 4 | 10 |
| Prompt injection, four shapes side by side (fixture) | 6 | 13 |
| Energy scene: BotTina + the business process | 5 | 11 |
| Tariff scene: the tariff graph + its business process | 3 | 11 |
| IT service desk scene: the agent + its business process | 4 | 12 |
| Credit scoring (fixture): train, auto-deploy, score, decide, feed back | 3 | 17 |

Moved 2026-10-09: Onyx +2 protected data to an external model (one concern, raised from the
direct-prompting and RAG matches), the IT support agent +2 untraceable agent actions, its
service desk scene those two plus personal data retained in agent memory, and credit scoring
+2 model extraction and −1 supply chain on the model it trains itself.

No bundled scene clears anything; `test_business_context.py` covers the clearing half by
building an approval inline.

### Test suite

**382 of 463 tests** in ~5 min by default; ~14 min for all 463 (counted 2026-10-04, full run green).
