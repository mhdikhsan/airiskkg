# PAIR-AI Glossary and Modeling Rules (v1.2 — locked)

**Status:** Single source of truth for terminology in the paper, slides, ontology comments, and code.
Any change to a definition here requires a version bump and a check of all downstream artifacts.

> **Locked 2026-07-28**, superseding v1.1. Verified against the repository on the same date
> (branch `feature/characterization-layer`). Section F is the decision record: F2 and F4 were
> resolved and implemented in this version; F1 and F3 are recorded deferrals that do not block
> the lock. Every other change is a correction of text that had drifted from the implemented
> ontology, not a new decision.

**Notation.** This document writes the pattern-module prefix as `rp:` (retained from v1.0 for
paper continuity). **Every ontology file, SPARQL query, and Python module uses the prefix
`pair:` for the same namespace** `http://w3id.org/airiskkg/pair-ai#`
(`vann:preferredNamespacePrefix "pair"`). The namespace URI is stable; only the
document-vs-file prefix label differs. Read `rp:X` here as `pair:X` in the code.

**Changes from v1.1 (drafted 2026-07-28):**
1. **Notation note added** (above): the `rp:` / `pair:` divergence is now recorded in the
   glossary itself rather than only in `CHANGELOG_data_model.md`.
2. **A.3 corrected** to the facets actually implemented: "Stakeholder" (never implemented) is
   replaced by **Deployment Setting**, and the missing **Data Dynamism** scheme is added. The
   Data Category members are named as declared.
3. **A.5 clarified**: multiple implementations per motif remain permitted, but the library is
   currently 1:1 — the sentence no longer reads as a description of the library.
4. **A.8 corrected**: a finding does not assert a link to the assessed system; the system is
   derivable through evidence-element membership. See F3.
5. **C/R3 corrected**: VAIR is marked as an intended, not yet realized, reuse target.
6. **Section E converted** from an active task list into a completion record, with E4 flagged
   as partially implemented.
7. **Section F added**: decisions pending before this version can be locked.
8. **A.4 (Architectural Motif) expanded into a full definition** — configuration vs. element,
   roles vs. implementations, structure-only — plus an explicit statement of what "recurring"
   does *not* claim, and what a motif is *not*. **A.5** now flags "OQP" as project terminology.
   New grounding references **[D14]–[D16]** support these.
9. **Motif ⇄ risk-pattern link direction decided** (F4): `rp:hasMotif` is canonical,
   `rp:hasRiskPattern` is a required mirror. Stated normatively in A.6 and mirrored into the
   `rdfs:comment` of both properties in `ontology/core/pair_ai_pattern.ttl`.
10. **`rp:mechanismNarrative` removed** (F2): the property is deleted from the vocabulary and
    from all 11 risk-pattern implementations. Instance-framed prose belongs to the presentation
    layer, not the graph; the elements it named are already asserted as `rp:hasEvidence`.
    Term 7 is amended accordingly. Verified no behavioral change: the `onyx_danswer` example
    still yields 13 motif matches and 23 findings, with exactly 23 fewer triples.

**Scope note:** All assessment outputs of PAIR-AI are *candidate* risks — structural dispositions
toward harm identified at design time — never confirmed failures or observed incidents
(design-time weakness vs. runtime exploit, analogous to CWE vs. CVE [D7]).

---

## A. Core terms (public vocabulary — use these in paper, slides, and ontology)

**1. Architecture Graph.**
An RDF instance graph (ABox) representing one concrete AI system under assessment, expressed in
the BEAM vocabulary: typed elements (System, Resource, Model, Process, Agent) connected by flow
relations (`use`, `produce`, `inform`, `participatedIn`, `contain`). Its schema (TBox) is the
Architecture module: BEAM plus vocabulary alignments plus the SHACL input contract.
It may be stored as a named graph in the same triplestore as the AI-RKG, but it is per-system
*input*, not part of the reusable knowledge resource.
**Canonical model decision:** BEAM is the canonical internal model; external tool vocabularies
(e.g., Tool4Boxology) are normalized at ingestion through alignment adapters. One-line version:
*"Systems are assessed in BEAM; tools deliver graphs in their own vocabulary, normalized at
ingestion."*

**2. Pattern Role** (`rp:PatternRole`).
An abstract functional role (e.g., VectorStore, RetrievalStep, GenerativeModel, UserFacingOutput)
assigned to a concrete architecture element via `rp:playsRole`; modeled as a SKOS concept.
A role labels *one element's function*; a motif is a *structure over several roles*. Roles are
the semantic bridge that makes motifs reusable across heterogeneous systems — motifs match
against roles, never against implementation-specific labels. Grounded in role modeling [D8] and
the *participants* element of classical design patterns [D2].
*Not:* a BEAM class (`beam:Model` = what an element structurally is; a role = what it
functionally does in this system). *Not:* a pattern.

**3. Characterization Facet.**
A classification dimension attached to a structural element, modeled as a SKOS concept scheme
[D9] and assigned via a dedicated property. The implemented facets are:

| Facet | Assigned via | Attached to |
| --- | --- | --- |
| AI Task | `facet:hasTaskCategory` | `beam:Task` |
| Autonomy Level | `facet:hasAutonomyLevel` | `beam:System` |
| Domain / Purpose / **Deployment Setting** | `facet:hasDomain` / `hasPurpose` / `hasDeploymentSetting` | `beam:System` |
| Data Provenance / **Data Dynamism** / Data Rights | `facet:hasDataProvenance` / `hasDataDynamism` / `hasDataRights` | `beam:Data` |
| Data Identifiability & personal-data kind | `facet:hasIdentifiabilityLevel` / `hasPersonalDataCategory` (DPV URIs directly) | `beam:Data` |
| Implementation Type | `facet:hasImplementationType` | `beam:Model` |
| Data Category | `rp:containsDataCategory` | `beam:Data` |

Data Category members as declared (`rp:DataCategoryScheme`): Information, Sensitive Information,
Confidential Information, External User Content, Generated Content, Prompt Instruction,
Untrusted Content, Trusted Content — three of which carry `skos:relatedMatch` to DPV. There is
deliberately **no "Personal" data category**: personal data is expressed with DPV concepts
through `facet:hasPersonalDataCategory` (R3), never mirrored into this scheme.

Data Category is the one facet that lives in the pattern module rather than the facet module,
because its values are also *derived* along data flow by a registered query (R8); every other
facet is a base fact annotated by the modeler.

**Why facets exist:** without them, every category would have to be encoded as
graph structure and the motif library would explode combinatorially (separate motifs for "RAG
with personal data" and "RAG without"). With facets: one motif, plus applicability conditions
that read facet values. Facets characterize elements; they are never nodes that motifs traverse.
In paper prose, "system properties" is an acceptable synonym.

**4. Architectural Motif** (`rp:GraphMotif`).

> A **reusable, type-level configuration of pattern roles connected by flow relations**, capturing
> a recurring arrangement in AI system architectures (e.g., vector-based retrieval,
> retrieval-augmented generation, human-in-the-loop decision support). A motif is *descriptive*
> and **risk-neutral by itself**: it states what structure is present, never whether that
> structure is dangerous.

Three properties carry the definition, and the rest of the method depends on each:

- **A configuration, not an element.** A motif constrains *several elements together with the
  relations between them* — the unit that risk attaches to (§B, System Configuration), justified
  system-theoretically: hazards emerge from component interactions, not from isolated components
  (STAMP/STPA [D5]). One annotated element is never a motif.
- **Over roles, not implementations.** A motif's nodes are constrained by **pattern roles**
  (term 2) and BEAM classes, never by implementation-specific labels. This is precisely what lets
  one motif match heterogeneous systems; roles occupy the *participants* slot of a classical
  design pattern [D2], grounded in role modeling [D8].
- **Structure only, hence risk-neutral.** A motif ranges over roles and **flow relations**
  (`use`, `produce`, `inform`) and reads **no characterization facet** (R2). Risk enters only
  when a risk pattern (term 6) evaluates its applicability conditions over a *motif match*.

**Flow relations are not the same as data flow.** `inform` is process-to-process ordering with
no resource transfer, and it is load-bearing in the library — 22 of 132 declared pattern edges
and 14 of 24 implementations use it (e.g., the Guardrails motif is constituted by a guardrail
step *informing* a generation step). Defining a motif over "data flow" alone would exclude it.

**Type and instance.** The motif is the type; a **motif match** (§B) is its instantiation — a
mapping from the motif's abstract pattern nodes to concrete architecture elements. "Reusable" is
exact in this sense: one motif, many matches, across systems.

**Terminology grounding (reviewer-facing).** "Motif" is adopted from network analysis, where a
*network motif* is a recurring subgraph in a complex network [D1]. This deliberately
distinguishes our descriptive, detection-oriented patterns from *prescriptive* design and
architectural patterns [D2, D3, D4], which one applies while designing. Using patterns
*descriptively* — to locate occurrences of a known structure in a concrete system rather than to
build one — is established practice in design-pattern detection [D15]; PAIR-AI applies that
stance at the architecture level and over RDF rather than source code. In ontology-engineering
terms, the declarative motif is a content-level **Ontology Design Pattern** [D14] over the BEAM
and role vocabulary. Relationship to design patterns is **m:n**: one design pattern (e.g., RAG)
induces several motifs; one motif (e.g., vector retrieval) occurs in several patterns —
mirroring elementary vs. composite patterns in the Boxology [D4].

**What "recurring" claims, and what it does not.** In [D1] a network motif is a subgraph
*statistically over-represented* relative to a randomized null model. PAIR-AI computes **no**
such over-representation. Recurrence here is **editorial**: every motif is derived from a
published architecture pattern catalogue or from an explicitly curated source, recorded per entry
via `rp:derivedFrom` / `dct:source`. The term is borrowed for its descriptive, detection-oriented
stance, **not** for its statistical method — state this before a reviewer familiar with [D1]
raises it.

*Not:* a prescriptive design or architectural pattern [D2, D3] — those are applied while
designing, a motif is recognized afterwards. *Not:* an architectural style [D16], which fixes a
vocabulary and constraints for a whole system; a motif is local and several may co-occur in one
architecture. *Not:* a risk, and *not* a single role.

**5. Motif Implementation.**
The executable SPARQL query that detects a motif in an architecture graph
(`rp:implementedBy`; the OQP to the motif's ODP). Formally, executing it performs subgraph
matching: SPARQL Basic Graph Pattern evaluation is subgraph-homomorphism search over the RDF
graph [D6]. The model *permits* several implementations of one motif; the current library is
1:1 (one matcher per motif). An implementation is an implementation *of* the motif, not the
pattern itself.
**Terminology caution:** "ODP" (Ontology Design Pattern) is established terminology [D14].
**"OQP" (ontology query pattern) is this project's own shorthand** for the executable
counterpart — it is *not* a standard term in the ODP literature. Either define it on first use
or write "motif implementation" in the paper; do not present the ODP/OQP pair as if both halves
were borrowed.

**6. AI Risk Pattern** (`rp:RiskPattern` — renamed from `rp:MotifInterpretation`).
An architectural motif extended with risk semantics. Constituents, term by term:

> **Risk Pattern = Motif + Applicability Conditions + Mechanism + Taxonomy Links + Controls**

- *Motif*: the structural configuration that must be present (the structural WHERE-clause).
- *Applicability Conditions* (`rp:ApplicabilityCondition`, renamed from "graph/interpretation
  condition"): risk-relevant conditions over a motif match — facet values (e.g., personal data,
  autonomy level), data categories, structural properties, or the **absence** of represented
  controls via closed-world query constructs (`FILTER NOT EXISTS`). Conditions are constituents
  *of* the pattern, not external inputs. A condition may be shared by several patterns where the
  structural gate is genuinely identical; such reuse must be documented at the reusing pattern.
- *Mechanism*: the causal account of how/why the configuration is disposed toward harm.
- *Taxonomy Links*: anchors to external taxonomies (IBM AI Risk Atlas, OWASP LLM Top 10,
  MIT AI Risk Repository) for interoperable findings.
- *Controls*: suggested mitigations.

**Justification that this structure qualifies as a "pattern":** it instantiates the classical
pattern format context–problem–solution [D2, D3] (motif+conditions ≈ context/problem situation;
mechanism ≈ problem rationale; controls ≈ solution), and is structurally analogous to security
weakness catalogs: CWE entries describe a design-time weakness with structure, mechanism, and
mitigations, distinct from runtime exploits (CVE) [D7]; attack pattern catalogs (MITRE CAPEC)
follow the same anatomy.
*Not:* a risk (a pattern is reusable knowledge; a finding is a system-specific output).

**Link direction (decided 2026-07-28).** Motif and risk pattern are connected by the inverse
pair `rp:hasMotif` (pattern → motif) and `rp:hasRiskPattern` (motif → pattern).

> **`rp:hasMotif` is canonical.** The binding is authored on the **risk pattern**, because the
> motif is a *constituent of* the pattern per the equation above. `rp:hasRiskPattern` is a
> **required mirror**, not an optional convenience.

The mirror is mandatory because **no OWL reasoning runs in the assessment pipeline**: asserting
one direction does not materialize the other, so a one-sided assertion is invisible to any
consumer reading the other side. `owl:inverseOf` is declared in the ontology as documentation
only — it computes nothing here. Both directions are therefore written explicitly in the library
(all 23 bindings, verified 2026-07-28) and the mirror is enforced by
`python/tests/test_library_consistency.py`. The authoring rule is restated in the `rdfs:comment`
of both properties so it is visible at the point of use.

**7. Risk Mechanism.**
A curated explanation of *how or why* a matched configuration under the observed conditions can
lead to a risk (e.g., untrusted context injection, sensitive data propagation, unsupported model
inference). Mechanisms are defined in the AI-RKG as parts of risk patterns and *selected* at
assessment time — never invented during assessment. Each links to one or more external taxonomy
entries. A mechanism is deliberately **not** part of the detection logic: it is never evaluated
or filtered on during matching, so the same explanation is reproduced verbatim across systems
and runs.

**Instance grounding is not materialized in the graph (decided 2026-07-28, F2).** A finding
carries the mechanism by reference (`rp:hasDerivedMechanism`) and the concrete risk-bearing
elements as `rp:hasEvidence`. It does **not** carry a per-finding prose rendering: any sentence
naming those elements is generated in the presentation layer, where `rdfs:label`s are available.
The former `rp:mechanismNarrative` property was removed for this reason.

**8. Candidate Risk Finding** (`rp:RiskFinding`).
A system-specific *candidate* risk generated when a motif match satisfies the applicability
conditions of a risk pattern. A finding links the motif match it was generated from, the matched
motif, the satisfied conditions, the derived mechanism, taxonomy entries, suggested controls, and
its **evidence** — the matched elements, attached via `rp:hasEvidence` (a property of the
finding, no longer a separate class; retained for durable traceability in the spirit of
PROV [D10]). The **assessed system is not asserted on the finding**; it is derivable by
traversing from an evidence element to the `beam:System` that contains it (see F3).
A candidate risk is a structural disposition toward harm; it is **not** a confirmed failure, an
observed incident, or a prediction that harm will occur.

---

## B. Internal and narrative terms (not part of the public 8)

**Motif Match** (`rp:MotifMatch`) — internal technical entity: the set of node bindings from
abstract pattern nodes to concrete elements produced by a motif implementation. Findings
reference matches; the paper does not need the term in prose beyond the method description.

**System Aspect / System Configuration** — narrative concepts for the paper's motivation, not
ontology classes. An aspect is an individual element or property; a configuration is a
combination of aspects *and their relations* — the unit risk attaches to, justified
system-theoretically: hazards emerge from component interactions, not isolated components
(STAMP/STPA [D5]). In RDF a configuration is simply a subgraph.

**Assessment output** (formerly "Candidate Risk Graph") — the aggregate RDF produced per
assessment run, containing all candidate risk findings for one system (one SonarQube *report*
vs. individual *warnings*). Not a defined vocabulary term.

**AI-RKG** — the reusable knowledge resource: Architecture module (BEAM + alignments),
Risk module (BEAM Risk / AIRO + taxonomies + control mappings), Pattern module (below).
Stored permanently: the three modules. Not stored permanently: per-system architecture graphs
and findings (assessment input/output).

**Motif Library** and **Risk Pattern Library** — two separate curated collections (split per
v1.1): the Motif Library holds risk-neutral motifs; the Risk Pattern Library holds risk patterns
(conditions, mechanisms, links, controls). Both carry per-entry derivation provenance
(`rp:derivedFrom` / `dct:source`): (i) deductive from Boxology elementary patterns, (ii)
interpretive from taxonomy entries (e.g., OWASP), (iii) LLM-assisted with human validation.
Firing-coverage denominators for evaluation are computed against the frozen Risk Pattern Library.

---

## C. Modeling rules (locked decisions)

**R1 — OWL class vs SKOS concept.**
OWL class for anything instantiated and traversed by queries (BEAM elements). SKOS concept for
anything only *assigned* as a classification value (roles, all facets incl. data categories).
Never instantiate a facet value.

**R2 — Motifs match structure; applicability conditions evaluate structure + facets.**
Motif matching operates exclusively on the structural layer (roles + flow relations).
Applicability conditions operate on structure *plus* facets, including context and
absence-of-control checks. Situational context enters at the applicability phase, not matching.

**R3 — Two reuse mechanisms.**
*Structural reuse* (owl:imports / subclassing + dct:source): Boxology→BEAM, AIRO→BEAM Risk,
DPV for identifiability and entities. *Vocabulary reuse* (own SKOS scheme + skos:exactMatch/
broadMatch, exported as SSSOM [D11]): OECD, TÜV AI.ST (license pending), VAIR. Never copy DPV
concepts locally; reuse their URIs.
*Implementation status (2026-07-28):* OECD anchoring is present as citations only — OECD
publishes no resolvable concept URIs, so those mappings remain TODO. **VAIR is an intended
target with no mapping yet.** TÜV AI.ST remains on hold. The SSSOM export has not been
generated; R6's mapping-set obligation is therefore outstanding, not satisfied.

**R4 — Absence is graph-relative (candidate framing, formal basis).**
RDF/OWL follows the Open World Assumption: a missing triple means *unknown*, not *false*.
`FILTER NOT EXISTS` is a closed-world claim about the *submitted graph only*: "no validation
control is represented" ≠ "none exists". This formally justifies (a) candidate framing and
(b) the executable input contract (SHACL shapes).

**R5 — Predicate economy.**
Edge semantics derive from node types, not from proliferating properties, within BEAM core.
External vocabularies (Tool4Boxology, later AgentO) are aligned via rdfs:subPropertyOf and
CONSTRUCT normalization in `ontology/alignments/`, never by extending BEAM's property set.

**R6 — Provenance on every reused or curated concept.**
`dct:source` on every adapted concept; SKOS mapping where an external equivalent exists;
`rp:derivedFrom` on every motif and risk pattern; SSSOM with directionality and confidence for
mapping sets.

**R7 — Task ≠ Capability ≠ Application Type.**
Task: functional input→output relation of a functional unit (compositional). Capability
(VAIR/AIRO): what a technique can do; characterizes risk sources. Application type (OECD):
system-level facet. Three axes; SKOS-mapped, never merged.

**R8 — Annotated vs derived facts (new in v1.1).**
Base facts are annotated by the modeler (this data is personal; this output is user-facing) —
knowledge only humans have at design time. Derived facts are computed by rules/queries
(untrusted content is *reachable* to a generation step via a property path; a control is
*absent* on that path). Every applicability condition must state which of its inputs are
annotated and which are derived. Runtime vulnerabilities appear at design time as their
structural preconditions (weakness, not exploit — CWE vs CVE [D7]; threat modeling practice
[D12]).

*(A proposed R9 on the control layer is parked in F1 until decided.)*

---

## D. Grounding references

*Verified (confident in work and venue; page/volume details still to be checked before citing):*

- **[D1]** Milo, R. et al. (2002). Network motifs: Simple building blocks of complex networks.
  *Science*, 298(5594), 824–827. — Source of the "motif" term.
- **[D2]** Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design Patterns: Elements
  of Reusable Object-Oriented Software*. Addison-Wesley. — Pattern format; participants ≈ roles.
- **[D3]** Buschmann, F. et al. (1996). *Pattern-Oriented Software Architecture, Vol. 1*.
  Wiley. — Architectural patterns as prescriptive solutions.
- **[D5]** Leveson, N. (2011). *Engineering a Safer World: Systems Thinking Applied to Safety*.
  MIT Press. — Hazards emerge from interactions; justifies configuration-level analysis.
- **[D6]** Pérez, J., Arenas, M., & Gutiérrez, C. (2009). Semantics and complexity of SPARQL.
  *ACM Transactions on Database Systems*, 34(3). — Formal basis of the matching method.
- **[D7]** MITRE. Common Weakness Enumeration (CWE) vs Common Vulnerabilities and Exposures
  (CVE). — Design-time weakness vs runtime exploit; anatomy of weakness entries.
- **[D9]** W3C (2009). *SKOS Simple Knowledge Organization System Reference*. W3C
  Recommendation. — Facet modeling.
- **[D14]** Gangemi, A., & Presutti, V. (2009). Ontology design patterns. In S. Staab &
  R. Studer (Eds.), *Handbook on Ontologies* (2nd ed.). Springer.
  DOI 10.1007/978-3-540-92673-3_10 — Establishes ODP terminology and the typology that A.4/A.5
  lean on (the declarative motif as a content-level ODP). Verified 2026-07-28: chapter, editors,
  volume, and DOI confirmed; **confirm the page range before citing.** Note that "OQP" is *not*
  from this literature (see A.5).
- **[D10]** W3C (2013). *PROV-O: The PROV Ontology*. W3C Recommendation. — Evidence and
  derivation provenance.
- **[D12]** Shostack, A. (2014). *Threat Modeling: Designing for Security*. Wiley. —
  Design-time analysis of runtime attack surfaces.
- **[D15]** Tsantalis, N., Chatzigeorgiou, A., Stephanides, G., & Halkidis, S. T. (2006).
  Design pattern detection using similarity scoring. *IEEE Transactions on Software Engineering*,
  *32*(11), 896–909. DOI 10.1109/TSE.2006.112 — Precedent for using patterns
  *descriptively*: detecting occurrences of a known pattern in a concrete system. Grounds the
  detection-oriented stance of A.4 (and the m:n, variant-tolerant matching problem). Verified
  2026-07-28: volume, issue, and page range confirmed.
- **[D16]** Shaw, M., & Garlan, D. (1996). *Software Architecture: Perspectives on an Emerging
  Discipline*. Prentice Hall. — Architectural style as a system-wide vocabulary plus constraints;
  cited in A.4 for the contrast (a motif is local and multiple motifs co-occur). Verified
  2026-07-28: book and publisher confirmed; **confirm the exact page for the style definition
  before quoting it.**

*To verify before citing (work exists, but exact venue/year/details must be confirmed):*

- **[D4]** van Harmelen, F., & ten Teije, A. — Boxology of design patterns for hybrid learning
  and reasoning systems. Early version in *Journal of Web Engineering* (2019); extended version
  by van Bekkum et al. — cited variously as *Applied Intelligence* (2021) and *Journal of Web
  Semantics* (2023, per Tool4Boxology README). **Confirm which version to cite.**
- **[D8]** Steimann, F. (2000). On the representation and essence of roles in object-oriented
  and conceptual modelling. *Data & Knowledge Engineering*, 35. — Role modeling.
- **[D11]** Matentzoglu, N. et al. (2022). SSSOM: A simple standard for sharing ontological
  mappings. *Database*. — Mapping provenance format.
- **[D13]** Bendler, J.E. et al. (2026). Tool4Boxology: A Semantic Toolbox for Constructing and
  Analysing Neuro-Symbolic Architectures. *ESWC 2026*, Springer, pp. 191–211,
  DOI 10.1007/978-3-032-25159-6_11. — Verified from the repository README; confirm against the
  published proceedings.

---

## E. Rename and cleanup tasks — completion record

The v1.1 task list is complete except where noted. Detailed change record:
`CHANGELOG_data_model.md`. Verified against the repository 2026-07-28.

| # | Task | Status |
| --- | --- | --- |
| E1 | Rename `rp:MotifInterpretation` → `rp:RiskPattern` | **Done** in ontology, pattern instances, SPARQL, and Python. *Paper text, slides, and the conceptual-model figure are outside this repository and must be confirmed separately.* |
| E2 | Rename `rp:GraphCondition` → `rp:ApplicabilityCondition`, incl. comment wording | **Done** |
| E3 | Demote `rp:EvidenceSubgraph` to the `rp:hasEvidence` property | **Done** — class removed, property in use on every finding |
| E4 | `rp:RiskFinding` no longer `rdfs:subClassOf beamr:Risk`; link via `rp:identifiesCandidateRisk` | **Partial** — the subclass axiom is gone and `rp:identifiesCandidateRisk` is declared, but **no risk-pattern implementation emits it**, so no finding currently links to a `beamr:Risk`. See F3. |
| E5 | Split pattern instances into Motif Library and Risk Pattern Library | **Done** — `motif.ttl` ("Architecture Motif Library") and `risk_pattern_library.ttl` |
| E6 | Fix naming/namespace inconsistencies; add missing `rp:derivedFrom` / `dct:source` | **Done** — all 24 motifs carry both; all 85 roles carry `dct:source`. One residual gap: `rp:TrustedContent` has no `dct:source`. |

Deprecated aliases from the v1.1 renames (`owl:deprecated` + `dct:isReplacedBy`) were retained
for one release and have since been removed; no alias remains in the ontology.

---

## F. Decision record

Genuine modeling decisions, as distinct from the corrections above. Each records the state that
prompted it, the resolution, and what the resolution commits the project to.

**Status at lock (2026-07-28):** **F2 resolved and implemented** (property removed).
**F4 resolved and implemented** (canonical link direction). **F1 deferred by decision** — no
rule adopted. **F3 deferred with a stated target.** The two deferrals are recorded positions,
not open questions, and do not block this version.

### F1 — Does the control layer earn a rule (proposed R9)? — DEFERRED

**Decision 2026-07-28: not decided; deliberately left open.** No R9 is adopted in v1.2, and the
control layer continues to be documented at file level only. This is a conscious deferral, not
an oversight — it does not block locking v1.2, but it should be revisited when the mitigation
layer work in `docs/notes/mitigation_research_roadmap.md` resumes. The proposal below is
retained verbatim so the analysis is not lost.

*State:* `ontology/patterns/control_mitigation_layer.ttl` (added after v1.1) introduces
`rp:controlNature` (technical / non-technical, a SKOS scheme) and `rp:realizedByMotif`
(control → motif that could structurally realize it), and establishes that only the 12
project-authored `pat:Control_*` concepts may appear in `rp:suggestedControl`, while MIT
`mitctrl:*` families are reached as an evidence layer through taxonomy links. Five of the 12
controls carry `rp:realizedByMotif`. None of this is in the glossary; it lives in the file's own
`dct:description` and in `docs/notes/control_layer_weakness_analysis.md`.

*Proposed R9 text (for review):*

> **R9 — Controls are actionable concepts; taxonomies are evidence.**
> `rp:suggestedControl` ranges only over the project's actionable control catalogue
> (`pat:Control_*`), each classified technical or non-technical via `rp:controlNature`.
> External control taxonomies (MIT AI Risk Controls) are reached from a finding through its
> taxonomy entries as supporting evidence, never as peer suggested controls — classifying a
> whole taxonomy family as one control is an altitude error. Where the motif library contains a
> structure that implements a control's intent, `rp:realizedByMotif` links the two; that link is
> a **candidate** structural mitigation, not proof that inserting the motif removes the risk.

*Locking this commits to:* keeping the two-tier control model, and to `realizedByMotif`
remaining candidate-framed. **Decision needed: adopt as R9, or leave as file-level
documentation?**

### F2 — Does `rp:mechanismNarrative` extend term 7? — RESOLVED: no; property removed

*State that prompted the decision:* all 11 risk implementations emitted
`rp:mechanismNarrative`, a per-finding literal built by concatenating the pattern's canonical
mechanism text with URI fragments of the bound elements. Term 7 predated the property and did
not mention it.

**Decision 2026-07-28: do not extend term 7 — remove `rp:mechanismNarrative` from the knowledge
layer.** Rationale:

1. **It is consumed by nothing.** No Python module, test, or webapp view reads the property. It
   is serialized into every finding and never used.
2. **It duplicates the evidence, in a weaker form.** Every element named in the sentence is
   already asserted as `rp:hasEvidence` — as URIs, queryable and traversable. The narrative
   re-encodes graph facts as prose, which cannot be queried, joined, or validated.
3. **It sits at the wrong altitude.** The strings are built in SPARQL with
   `STRAFTER(STR(?x), "#")` — URI-fragment extraction, i.e. *presentation logic inside the
   knowledge layer*. It also yields worse text than a view could: the fragment, not the
   element's `rdfs:label`.
4. **It is in tension with term 7's own rationale.** The mechanism is defined as inert and
   reproduced verbatim precisely so explanations are never regenerated per run; concatenating a
   new sentence per finding is a paraphrase step reintroduced by the back door.
5. **It costs at authoring time.** Each of the 11 risk implementations carries its own
   string-concatenation block that must be maintained, and nothing checks that the elements
   named in the prose are the same ones asserted as evidence — a silent divergence channel.

*The counter-argument, recorded:* a frozen narrative makes `risk_findings.ttl` self-explanatory
to someone reading it without the UI. Real but small — `rp:hasDerivedMechanism` and
`rp:hasEvidence` sit in the same file and reconstruct the sentence completely.

*Implemented in this version:*

- `rp:mechanismNarrative` deleted from `ontology/core/pair_ai_pattern.ttl`, replaced by a
  tombstone comment recording the decision and where such a sentence belongs instead.
- The CONSTRUCT triple and the `OPTIONAL`/`BIND(CONCAT(...))` block stripped from all 11
  `risk_*.rq` implementations (~11 lines each), together with the comments describing them.
- Term 7 amended ("Instance grounding is not materialized in the graph") and the
  `rp:RiskMechanism` `rdfs:comment` updated to match.
- **Verified no behavioral change:** `onyx_danswer` yields 13 motif matches and 23 findings
  before and after; the findings graph shrinks from 487 to 464 triples — exactly the 23 removed
  narratives — with all 23 `rp:hasDerivedMechanism` and 87 `rp:hasEvidence` triples intact.
  Test suite unchanged at 37 passing.

*Commits the project to:* instance-framed prose being a presentation concern. If a rendered
sentence is wanted in the workbench, build it in `python/src/airiskkg/assessment_view.py` from
the mechanism text plus evidence labels — do not reintroduce it into the graph.

### F3 — Which finding-level links must exist? — DEFERRED, target stated

Two related gaps, both in term 8 / E4:

1. `rp:identifiesCandidateRisk` is declared but never emitted — findings do not link to a
   `beamr:Risk` individual at all.
2. The assessed `beam:System` is not asserted on a finding; it is only derivable by traversing
   from an evidence element to its containing system.

**Decision 2026-07-28: deferred, with the intended target recorded.** The goal is that when the
assessment engine finishes, each candidate risk finding **maps cleanly onto a `beamr:Risk`**, so
that assessment output lands in the Risk module rather than stopping at the pattern module. v1.2
documents the current derivation (term 8) and does not change behavior; the work is scheduled
after this version locks.

*Why it is not a small change — there is currently nothing to point at.* Verified 2026-07-28:

- The graph contains **zero `beamr:Risk` individuals**.
- Taxonomy entries are **not** `beamr:Risk`. `owasp:llm01-prompt-injection` is typed
  `nexus:Risk` ⊑ `nexus:RiskTaxonomyEntry`, while `beamr:Risk` ⊑ `airo:Risk`,
  `beamr:RiskConcept`. **No alignment exists between the two hierarchies.**

So implementation must choose a route:

- **(a) Mint a risk individual per finding** — the engine creates one `beamr:Risk` per candidate
  finding and links it via `rp:identifiesCandidateRisk`, hanging the taxonomy anchors and
  mechanism off it. AIRO-faithful (a risk is an entity with source, consequence, impact) and
  keeps taxonomy *categories* distinct from this system's *risk instance*. More work; changes
  output shape.
- **(b) Align `nexus:Risk` to `beamr:Risk`** and point at the existing taxonomy entries. One
  triple — but it conflates a **category in a taxonomy** with a **risk in this system**, which
  is the class/instance confusion R1 exists to prevent, and would make every finding "identify"
  the same shared node. **Not recommended.**

Route (a) is the one consistent with the rest of the model. Either way the 11 risk
implementations change and the example assessments must be re-run and diffed.

### F4 — Canonical authoring direction for the motif ⇄ risk-pattern link — RESOLVED

**Decision 2026-07-28: `rp:hasMotif` (pattern → motif) is canonical; `rp:hasRiskPattern` is a
required mirror.** Rationale: the motif is a *constituent of* the risk pattern per the term-6
equation, and `risk_pattern_library.ttl` is organised pattern-first. The alternative — following
the `rdfs:domain` on `rp:hasRiskPattern` — was considered and rejected as a weaker signal than
the composition itself.

*Implemented in this version:*

- Normative statement added to term 6 ("Link direction").
- The authoring rule is restated in the `rdfs:comment` of **both** properties in
  `ontology/core/pair_ai_pattern.ttl`, so it is visible where bindings are written, including
  the warning that `owl:inverseOf` materializes nothing without a reasoner.
- No data change was required: all 23 bindings were already asserted both ways, and
  `python/tests/test_library_consistency.py` already fails on a missing mirror.

---

## G. Downstream artifact sweep — completed at lock

Required by the Status rule ("a check of all downstream artifacts"). Performed 2026-07-28 as
part of locking this version. No reference to `PAIR-AI_glossary_v1.1.md` remains in the
repository, and v1.1 has been retired.

**Ontology version strings updated** (`dct:source` / `skos:definition`):

| File | Occurrences |
| --- | --- |
| `ontology/core/pair_ai_pattern.ttl` (incl. `rp:DataCategoryScheme`) | 2 |
| `ontology/facets/implementation_type.ttl` | 2 |

**Documents repointed at this file:**

`docs/claude/CLAUDE.md` (also restates the version and now lists the method document) ·
`docs/claude/claude_code_prompt_data_model_update.md` ·
`docs/reference/PAIR-AI_method_and_construction.md` · `docs/reference/catalogue.md` ·
`docs/annotation_facilitator_cheatsheet.md` · `docs/annotation_walkthrough_graphrag.md` ·
`docs/evaluation/pair_ai_evaluation_survey.md`

**Kept historical:** `CHANGELOG_data_model.md` still records that **v1.1** was the authority for
the v2 data-model work of 2026-07-13; only its now-dangling file path was repointed here, with
the supersession noted. The record of what was true then is unchanged.

**Ontology changes made by this version** (both from Section F):

- `rp:hasMotif` / `rp:hasRiskPattern` — authoring rule added to both `rdfs:comment`s (F4).
- `rp:mechanismNarrative` — property deleted, tombstone comment left in its place; the
  CONSTRUCT triple and `BIND(CONCAT(...))` block removed from all 11 `risk_*.rq` (F2).
- `rp:RiskMechanism` — `rdfs:comment` amended to match the F2 decision.

Regression check at lock: `onyx_danswer` yields 13 motif matches and 23 candidate findings,
unchanged; test suite 37 passing, with 10 pre-existing failures caused by the removed
`uc6.ttl` / Verba example fixtures (unrelated to this version — see
`docs/reference/PAIR-AI_method_and_construction.md` §6.5).

**Outside the repository** (cannot be checked here): paper text, slides, and the
conceptual-model figure — relevant to E1, and to A.4/A.5 if motif wording is quoted there.
