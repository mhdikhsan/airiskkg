# PAIR-AI Glossary and Modeling Rules (v1.1 — locked)

**Status:** Single source of truth for terminology in the paper, slides, ontology comments, and code.
Any change to a definition here requires a version bump and a check of all downstream artifacts.

**Changes from v1.0 (agreed 2026-07-13):**
1. `rp:MotifInterpretation` renamed to **`rp:RiskPattern`** — the RDF entity now carries the same
   name as the concept it realizes.
2. "Interpretation condition" renamed to **"applicability condition"** (`rp:ApplicabilityCondition`).
3. Public vocabulary consolidated to **8 core terms** (Section A). System Aspect / System
   Configuration become narrative concepts only; Evidence Subgraph becomes a property of
   Finding; Candidate Risk Graph becomes plain "assessment output"; Motif Match becomes an
   internal technical term; Data Category is classified as a facet.
4. Pattern Library split into **Motif Library** (risk-neutral) and **Risk Pattern Library**.
5. Grounding references added (Section D), per the rule: every suggested concept carries a
   literature anchor, marked *verified* or *to verify*.

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
[D9] and assigned via a dedicated property: Task, Autonomy Level, Data Provenance, Data
Identifiability, Data Rights, Implementation Type, Data Category (Sensitive / Personal /
Untrusted / Generated content, aligned to DPV), and Context facets (Domain, Purpose,
Stakeholder). **Why facets exist:** without them, every category would have to be encoded as
graph structure and the motif library would explode combinatorially (separate motifs for "RAG
with personal data" and "RAG without"). With facets: one motif, plus applicability conditions
that read facet values. Facets characterize elements; they are never nodes that motifs traverse.
In paper prose, "system properties" is an acceptable synonym.

**4. Architectural Motif** (`rp:GraphMotif`).
A reusable, *descriptive* graph pattern over pattern roles and flow relations that captures a
recurring system configuration (e.g., vector-based retrieval, retrieval-augmented generation,
human-in-the-loop decision support). A motif is **risk-neutral by itself**.
**Terminology grounding (reviewer-facing):** "motif" is adopted from network analysis, where a
*network motif* is a recurring subgraph in a complex network [D1]. This deliberately
distinguishes our descriptive, detection-oriented patterns from *prescriptive* design and
architectural patterns [D2, D3, D4], which one applies while designing. Relationship to design
patterns is **m:n**: one design pattern (e.g., RAG) induces several motifs; one motif (e.g.,
vector retrieval) occurs in several patterns — mirroring elementary vs. composite patterns in
the Boxology [D4].

**5. Motif Implementation.**
The executable SPARQL query that detects a motif in an architecture graph
(`rp:implementedBy`; the OQP to the motif's ODP). Formally, executing it performs subgraph
matching: SPARQL Basic Graph Pattern evaluation is subgraph-homomorphism search over the RDF
graph [D6]. One motif may have multiple implementations. It is an implementation *of* the
motif, not the pattern itself.

**6. AI Risk Pattern** (`rp:RiskPattern` — renamed from `rp:MotifInterpretation`).
An architectural motif extended with risk semantics. Constituents, term by term:

> **Risk Pattern = Motif + Applicability Conditions + Mechanism + Taxonomy Links + Controls**

- *Motif*: the structural configuration that must be present (the structural WHERE-clause).
- *Applicability Conditions* (`rp:ApplicabilityCondition`, renamed from "graph/interpretation
  condition"): risk-relevant conditions over a motif match — facet values (e.g., personal data,
  autonomy level), data categories, structural properties, or the **absence** of represented
  controls via closed-world query constructs (`FILTER NOT EXISTS`). Conditions are constituents
  *of* the pattern, not external inputs.
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

**7. Risk Mechanism.**
A curated explanation of *how or why* a matched configuration under the observed conditions can
lead to a risk (e.g., untrusted context injection, sensitive data propagation, unsupported model
inference). Mechanisms are defined in the AI-RKG as parts of risk patterns and *selected* at
assessment time — never invented during assessment. Each links to one or more external taxonomy
entries.

**8. Candidate Risk Finding** (`rp:RiskFinding`).
A system-specific *candidate* risk generated when a motif match satisfies the applicability
conditions of a risk pattern. A finding links the assessed system, the matched motif, the
satisfied conditions, the derived mechanism, taxonomy entries, suggested controls, and its
**evidence** — the matched subgraph, attached via `rp:hasEvidence` (a property of the finding,
no longer a separate class; retained for durable traceability in the spirit of PROV [D10]).
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
- **[D10]** W3C (2013). *PROV-O: The PROV Ontology*. W3C Recommendation. — Evidence and
  derivation provenance.
- **[D12]** Shostack, A. (2014). *Threat Modeling: Designing for Security*. Wiley. —
  Design-time analysis of runtime attack surfaces.

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

## E. Rename and cleanup tasks (active, pre-freeze)

1. **Rename** `rp:MotifInterpretation` → `rp:RiskPattern` across ontology, pattern instances,
   SPARQL queries, Python code, paper text, slides, and conceptual-model figure.
2. **Rename** `rp:GraphCondition` (or current condition class) → `rp:ApplicabilityCondition`;
   update all `rdfs:comment`s from "interpretation condition" wording.
3. **Demote** `rp:EvidenceSubgraph` from class to `rp:hasEvidence` property on `rp:RiskFinding`.
4. `rp:RiskFinding` no longer `rdfs:subClassOf beamr:Risk`; link via
   `rp:identifiesCandidateRisk` instead.
5. **Split** pattern instances into Motif Library and Risk Pattern Library files/graphs.
6. Fix remaining naming/namespace inconsistencies; add missing `rp:derivedFrom`/`dct:source`.
