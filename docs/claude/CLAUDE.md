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
- **A design pattern is identified by a `pair:DesignPatternCitation`, never modelled.** The 22
  handles at the top of `motif.ttl` carry a label and a `dct:source`, and nothing else.
  `test_a_design_pattern_citation_stays_a_citation` fails on any other predicate, because a
  `dct:description` there would start modelling the intent and consequences the method drops.
  The handles are what turn the m:n relation into a traversal: `Cite_Guardrails` is reached by
  Guardrails, Input Screening and Output Screening.
- **A handle is minted in `pat:` but stands for someone else's catalogue.** So `library.py`
  reads its origin off its own `dct:source`. Reading it off the IRI would credit Fowler's
  patterns to PAIR-AI.
- **Not every motif derives from a design pattern, and the graph says which.** The 4 agentic
  motifs point `derivedFrom` straight at their OWASP ASI concepts and carry no handle, because
  their structural signature was inferred from a *risk* entry rather than read off a catalogue.
  `ExternalDependencyMotif` names `owasp:llm03-supply-chain` for the same reason. Keep that
  visible; it is a weaker derivation and must be described as one.
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
are modelled: **ASI01** goal hijack, **ASI02** tool misuse, **ASI06** memory and context
poisoning, **ASI07** insecure inter-agent communication. Entries defined by runtime
behaviour have no shape in a represented graph; adding them would fire on every agent and
break candidate framing rather than support it.

---

## Authoritative documents

Read before non-trivial changes.

| Document | What it is |
| --- | --- |
| `docs/reference/PAIR-AI_glossary_v1_3.md` | Terminology and modeling rules. **v1.3** supersedes v1.2 (deleted). Sections: **A** core terms, **B** internal terms, **C** rules **R1–R10**, **D** grounding references. A reference to `PAIR-AI_glossary_v1.2.md` is a broken link to fix; v1.2's Sections E/F are gone — do not cite them. |
| `docs/reference/PAIR-AI_method_and_construction.md` | How the knowledge base was built and how an assessment runs. |
| `docs/reference/catalogue.md` | Inventory of every motif, risk pattern, role, and data category. **Hand-written, so it goes stale silently** — re-check its counts whenever the library changes. |
| `docs/reference/risk_control_linkage.md` | How risk patterns reach controls, including the MIT evidence layer. **Generated** — regenerate, never hand-edit. |
| `docs/reference/competency_questions.md` + `competency_questions/*.rq` | What the knowledge base can be asked, as 27 runnable SPARQL SELECTs. `test_competency_questions.py` checks every question is listed and none has gone silent. **A question that returns nothing is drift, not a passing test.** |
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
- **Flow relations are not data flow.** `inform` is process-to-process ordering with no
  resource transfer, and it is load-bearing — the Guardrails motif is constituted by a
  guardrail step *informing* a generation step. Never redefine a motif over "data flow".
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
  a `bpmn:itemDefinition` and emits `pair:SensitiveInformation` on the input-playing elements
  of the refined system, with a `prov:Derivation` naming the annotation that produced it. What
  is *annotated* stays annotated; what is *derived* is the data category. **No facet is
  propagated as a facet and no BPMN triple enters the architecture.** The mapping goes by role,
  not by name, because nothing in the business layer names an architecture element — that is
  the point, since the analyst does not know them.
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
- **A document is not a database, and the editor can say which.** `add-data` takes a `shape`
  (`object` | `store`); `set-data-shape` retypes in place, keeping the name, classification
  and associations a finding reads. `bp:isCollection` is declared on `dataObject` and not on
  `dataStore`, so it is dropped on a retype rather than carried into a domain sBPMN does not
  declare.
- **A pool collapses to a band.** BPMN's black-box pool: a collapsed participant keeps its band
  and name, its members keep a slot on that band so message flow still lands on the pool, and
  nothing inside is drawn.
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
  structure, run the assessment. The detail panel is laid out as the constituent equation (motif → conditions → mechanism →
  taxonomy links → controls), because that is what it is teaching.
- **Two risk patterns name no motif and must keep saying so** rather than showing an empty heading:
  `ExcessiveAgency` and `SensitiveInformationDisclosure` are evaluated over any motif match
  whose conditions hold.
- **The front door steps aside on content, and only the front door.** `settleChoice()` emits
  `choice:settled`; the library closes on it *only* when it was opened as the opening screen.
  Adding a motif leaves opening mode first, so the library stays put — picking one risk usually
  means adding more than one motif.
- **A risk pattern with no `dct:description` borrows the definition of the entry it was derived
  from, attributed.** The taxonomy entry names the risk; the risk pattern says when the library
  raises it. The two must not be presented as one sentence.
- **Risk patterns are listed, not filed.** A risk pattern is a weakness in a design; the risk is
  the harm it may end in, and a shelf must not blur the two. The list is flat; the consequence
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
- **Three risk patterns are unclearable by design, and that is correct.**
  `DataAndModelPoisoning`, `SupplyChainCompromise` and `VectorAndEmbeddingWeakness`
  (`data_model_poisoning.rq`, `supply_chain.rq`, `vector_embedding_weakness.rq` — the 3 of 15
  risk queries carrying no `FILTER NOT EXISTS` at all) rest on provenance and vetting — non-technical controls with no runtime shape — so no structural
  escape exists to write. The answer is **finding-level triage**, not a query escape:
  `pair:findingStatus` is the extension point, finding IRIs are deterministic so a judgement
  survives re-runs, and "accepted, handled by process" is a human act recorded against the
  finding rather than a fabricated structural fact. Never conflate the two.
- **Carrying a `FILTER NOT EXISTS` is not the same as being clearable.** 12 of 15 risk queries
  carry one or two; several test only the structural half while the annotation half stays
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
  and 8 edges; prompt injection needs an input screen and nothing else, so
  `InputScreeningMotif` / `OutputScreeningMotif` are 3 nodes and 2 edges each and nest inside it.
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
| `ontology/taxonomy/` | IBM Atlas, OWASP LLM, OWASP Agentic (ASI), MIT, NIST AI 600-1, plus the tiered cross-taxonomy mappings. |
| `ontology/context/` | The business layer bridge. `bpmn_context.ttl` declares `pair:refinedBy`, `pair:businessFollows`, `pair:BusinessFlowDerivation`, and registers `business_flow.rq` and `business_data_bridge.rq` in `context/implementation/`. |
| `ontology/visualization/` | Standalone SPARQL run by hand, referenced by no declaration. |

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
(`validate_graphs.py`, `normalize_t4b.py`, `run_competency_questions.py`,
`generate_mapping_provenance.py`), or it rewrites a tracked file
(`generate_mit_action_layer.py` writes `ontology/taxonomy/mit_mitigation_action.ttl`,
`generate_risk_control_linkage.py` writes `docs/reference/risk_control_linkage.md`).
`export_ontology.py`, `pattern_provenance_worklist.py` and `role_provenance_export.py` meet
none of those and belong in `local/`. **A tracked file that says "regenerate with X" while X
is gitignored cannot be regenerated from a clone** — the artifact stops being reproducible, which is the
whole reason it is checked in. Moving a script means updating its callers in the same commit.

`assessment_runner` and `paths` keep their import paths on purpose: the evaluation harness in
the gitignored `docs/evaluation/` imports them and cannot be updated from a clone.

### Example graphs

- **`ontology/example/` — what the deployment offers, and only that**: `simple_graph_rag.ttl`,
  `it_support_agent.ttl`, and `context/it_service_desk.ttl`. This is the list the example
  dropdown shows, so it stays small on purpose.
- **`python/tests/fixtures/` — graphs a test needs that the deployment does not offer**:
  `onyx_rag_chatbot.ttl` (the only graph exercising query rewriting, reranking, embeddings and
  supply chain), `wien_energie_bottina.ttl`, `wien_energie_tariff_change.ttl`, and
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
- **`facet:hasDomain`, `facet:hasPurpose`, `facet:hasAutonomyLevel`** and the rest of the
  situational layer remain inert. The risk-view work did not activate them, and `ctx:Domain`
  and `ctx:Purpose` are declared empty on purpose.
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

### Library (counted off the loaded graph, 2026-09-08)

| | |
| --- | --- |
| Motifs | **31** — GenAI 13, ML serving and training 13, Agentic 4, Supply chain 1 |
| Risk patterns | **15** (15 motifs carry one; 16 carry none) |
| Pattern roles | **97** |
| Data categories | **7** |
| Facet concepts | **35** (task 20, data 11, autonomy 4) |
| Risk mechanisms | **14** |
| Applicability conditions | **16**, carried on 20 attachments |
| Controls | **12** `pat:Control_*` |
| Triples | **7 529** |

**63 registered implementations** over 62 `.rq` files: 31 match, 15 risk, 6 propagation, 9
mitigation rewrites over 8 files (`response_verification.rq` is registered twice, under two
controls for the same risk pattern), and 2 business-context derivations under
`ontology/context/` — one of which registers as `DataCategoryPropagation`, so the runner sees 7
of those and 1 `BusinessFlowDerivation`.

### Assessment baselines (matches / findings)

| Graph | Matches | Findings |
| --- | --- | --- |
| RAG chatbot, Onyx / Danswer (broadest: 8 distinct motifs) | 14 | 22 |
| Minimal graph RAG | 3 | 7 |
| Wien Energie chatbot (BotTina) | 5 | 9 |
| Wien Energie tariff change (4 systems) | 3 | 9 |
| IT support agent (agentic) | 4 | 8 |
| Energy scene: BotTina + the business process | 5 | 10 |
| Tariff scene: the tariff graph + its business process | 3 | 11 |
| IT service desk scene: the agent + its business process | 4 | 9 |

No bundled scene clears anything; `test_business_context.py` covers the clearing half by
building an approval inline.

### Test suite

**258 of 308 tests** in ~2.5 min by default; ~10.5 min for all 308.
