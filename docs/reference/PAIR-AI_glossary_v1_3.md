# PAIR-AI Glossary and Modeling Rules (v1.3)

**Status:** Single source of truth for terminology in the paper, slides, ontology comments, and
code. Any change to a definition here requires a version bump and a check of all downstream
artifacts.

**Notation.** This document uses the prefix `pair:` for the pattern module, matching every
ontology file, SPARQL query, and Python module. The namespace is
`http://w3id.org/airiskkg/pair-ai#` (`vann:preferredNamespacePrefix "pair"`). Where paper text
still writes `rp:X`, read it as `pair:X`; aligning the paper on `pair:` is recommended.

 **Scope note**. Every assessment output of PAIR-AI is a candidate risk: a claim that the
submitted architecture graph represents a configuration disposed toward harm, never that a
failure has occurred, that a vulnerability is confirmed, or that harm will occur. Confirming a
candidate requires evidence the method does not have — human review, or observation of the
running system.

---

## A. Core terms 

### 1. Architecture Graph

An RDF instance graph (ABox) representing one concrete AI system under assessment, expressed in
the Boxology Notation (BEAM) vocabulary: typed elements (System, Resource, Model, Process, Agent) connected by flow
relations (`use`, `produce`, `inform`, `participatedIn`, `contain`). Its schema (TBox) is the
Architecture module: BEAM plus vocabulary alignments plus the SHACL input contract. It may be
stored as a named graph alongside the AI-RKG, but it is per-system *input*, not part of the
reusable knowledge resource.

**Canonical model.** BEAM is the canonical internal model; external tool vocabularies (e.g.,
Tool4Boxology [D13]) are normalized at ingestion through alignment adapters. One-line version:
*"Systems are assessed in BEAM; tools deliver graphs in their own vocabulary, normalized at
ingestion."*

### 2. Pattern Role (`pair:PatternRole`)

An abstract functional role (e.g., VectorStore, RetrievalStep, GenerativeModel,
UserFacingOutput) assigned to a concrete architecture element via `pair:playsRole`; modeled as a
SKOS concept. A role labels *one element's function*; a motif is a *structure over several
roles*. Roles are the semantic bridge that makes motifs reusable across heterogeneous systems —
motifs match against roles, never against implementation-specific labels.

Grounded in role modeling [D8] and the *participants* element of classical design patterns [D2].
The same device is used in design-pattern detection, where motif occurrences are identified
through the roles and relationships that describe the motif [D17].

*Not:* a BEAM class (`beam:Model` = what an element structurally is; a role = what it
functionally does in this system). 

### 3. Characterization Facet

A classification dimension attached to a structural element, modeled as a SKOS concept scheme
[D9] and assigned via a dedicated property. The implemented facets are:

| Facet | Assigned via | Attached to |
| --- | --- | --- |
| AI Task | `facet:hasTaskCategory` | `beam:Task` |
| Autonomy Level | `facet:hasAutonomyLevel` | `beam:System` |
| Domain / Purpose / Deployment Setting | `facet:hasDomain` / `hasPurpose` / `hasDeploymentSetting` | `beam:System` |
| Data Provenance / Data Dynamism / Data Rights | `facet:hasDataProvenance` / `hasDataDynamism` / `hasDataRights` | `beam:Data` |
| Data Identifiability & personal-data kind | `facet:hasIdentifiabilityLevel` / `hasPersonalDataCategory` (DPV URIs directly) | `beam:Data` |
| Implementation Type | `facet:hasImplementationType` | `beam:Model` |
| Data Category | `pair:containsDataCategory` | `beam:Data` |

Data Category members (`pair:DataCategoryScheme`): Information, Sensitive Information,
Confidential Information, External User Content, Generated Content, Prompt Instruction,
Untrusted Content, Trusted Content — three of which carry `skos:relatedMatch` to DPV. There is
deliberately **no "Personal" data category**: personal data is expressed with DPV concepts
through `facet:hasPersonalDataCategory` (R3), never mirrored into this scheme.

Data Category is the one facet that lives in the pattern module rather than the facet module,
because its values are also *derived* along data flow by a registered query (R8); every other
facet is a base fact annotated by the modeler.

**Why facets exist.** Without them, every category would have to be encoded as graph structure
and the motif library would explode combinatorially (separate motifs for "RAG with personal
data" and "RAG without"). With facets: one motif, plus applicability conditions that read facet
values. Facets characterize elements; they are never nodes that motifs traverse. In paper prose,
"system properties" is an acceptable synonym.

### 4. Architectural Motif (`pair:GraphMotif`)

> A **reusable, type-level configuration of pattern roles connected by flow relations**, capturing
> a recurring arrangement in AI system architectures (e.g., vector-based retrieval,
> retrieval-augmented generation, human-in-the-loop decision support). A motif is *descriptive*
> and **risk-neutral by itself**: it states what structure is present, never whether that
> structure is dangerous.

Three properties carry the definition, and the rest of the method depends on each:

- **A configuration, not an element.** A motif constrains *several elements together with the
  relations between them* — the unit that risk attaches to (§B, System Configuration), justified
  system-theoretically: hazards emerge from component interactions, not from isolated components
  [D5]. One annotated element is never a motif.
- **Over roles, not implementations.** A motif's nodes are constrained by **pattern roles**
  (term 2) and BEAM classes, never by implementation-specific labels. This is what lets one motif
  match heterogeneous systems.
- **Structure only, hence risk-neutral.** A motif ranges over roles and **flow relations**
  (`use`, `produce`, `inform`) and reads **no characterization facet** (R2). Risk enters only
  when a risk pattern (term 7) evaluates its applicability conditions over a motif match.

**Motifs cannot express absence.** Motif matching is monotone: if a motif matches an architecture
graph, it matches every extension of that graph. A motif therefore asserts the presence of
structure only. Every negative or exclusivity claim ("without grounding", "no validation step",
"direct") belongs to an applicability condition (R2, R4), and motif labels must be positive
accordingly (R9).

**Motifs may nest.** The library is deliberately not an antichain: a smaller motif can be a
subgraph of a larger one, and a nested motif always co-matches with its container. Match counts
are therefore a measure of structural coverage, not of distinct architectural features.

**Flow relations are not the same as data flow.** `inform` is process-to-process ordering with no
resource transfer, and it is load-bearing in the library (e.g., the Guardrails motif is
constituted by a guardrail step *informing* a generation step). Defining a motif over "data flow"
alone would exclude it.

**Type and instance.** The motif is the type; a **motif match** (§B) is its instantiation — a
mapping from the motif's abstract pattern nodes to concrete architecture elements. "Reusable" is
exact in this sense: one motif, many matches, across systems.

**Terminology grounding.** "Motif" is established terminology in design-pattern detection, where
a *design motif* is the structural solution core of a pattern, described by roles and relations
and matched against concrete systems, as distinct both from the full pattern and from its
occurrences [D17, D15]. The granularity claim follows the notion of **architectural primitives**:
abstractions below the level of a pattern that recur across the realizations of several patterns
[D18, D19]. Annotating an architecture with such abstractions and then proposing catalogued
patterns from the annotations is an established method shape [D20]; PAIR-AI applies it over RDF
and adds risk semantics. The graph-theoretic sense of a small recurring subgraph matched against
a host graph [D1] is the secondary reading. In ontology-engineering terms the declarative motif is
a content-level **Ontology Design Pattern** [D14, D24] over the BEAM and role vocabulary.

**Relationship to architecture design patterns is m:n.** One architecture design pattern (e.g.,
RAG) induces several motifs; one motif (e.g., vector retrieval) occurs in several design patterns
— mirroring elementary versus composite patterns in the Boxology [D4]. Architecture design
patterns are **not modeled in the ontology**; only motifs and AI risk patterns are. In prose,
always write "architecture design pattern" or "AI risk pattern", never bare "pattern".

**What "recurring" claims, and what it does not.** In [D1] a network motif is a subgraph
*statistically over-represented* relative to a randomized null model. PAIR-AI computes **no**
such over-representation. Recurrence here is **editorial**: every motif is derived from a
published architecture pattern catalogue or from an explicitly curated source, recorded per entry
via `pair:derivedFrom` / `dct:source`.

*Not:* a prescriptive design or architectural pattern [D2, D3] — those are applied while
designing, a motif is recognized afterwards. *Not:* an architectural style [D16], which fixes a
vocabulary and constraints for a whole system; a motif is local and several may co-occur in one
architecture. *Not:* a risk, and *not* a single role.

### 5. Motif Implementation (`pair:PatternImplementation`)

The executable SPARQL CONSTRUCT query that detects a motif in an architecture graph and
materializes each occurrence as a motif match (`pair:implementedBy`). Executing it performs
subgraph matching: SPARQL basic graph pattern evaluation is subgraph-homomorphism search over the
RDF graph [D6]. The model *permits* several implementations of one motif; the current library is
1:1 (one matcher per motif). An implementation is an implementation *of the motif*, not of the
risk pattern.

**ODP and OQP.** The declarative motif and its executable query are the two roles a semantic
pattern can take: an **ontology design pattern (ODP)** when it structures the ontology or
knowledge graph, and an **ontology query pattern (OQP)** when it is operationalized as a reusable
SPARQL template that retrieves instances of that structure [D25, D14, D24]. An OQP is derived from
its ODP and may differ topologically where the application requires it, but must not violate the
ODP's semantics [D25]. Pairing a declarative definition with an executable CONSTRUCT query in this
way is the arrangement established by SPIN [D23].

### 6. Applicability Condition (`pair:ApplicabilityCondition`)

A risk-relevant predicate evaluated **over a motif match** — over the bound elements, not over the
graph at large — which determines whether a risk pattern applies to that match. "Personal data is
present somewhere in this system" and "the data bound to the prompt-context node is personal" are
different claims; only the second licenses a finding.

Conditions are constituents *of* a risk pattern, not external inputs. A condition may be shared by
several patterns where the structural gate is genuinely identical; such reuse must be documented
at the reusing pattern.

Four kinds are in use:

| Kind | Reads | Example | R8 status |
| --- | --- | --- | --- |
| Facet | a facet value on a bound element | prompt context is personal data | annotated |
| Data category | `pair:containsDataCategory`, possibly propagated along flow | untrusted content in the generation context | derived |
| Structural | graph structure beyond the motif's own edges | generated output reaches a user-facing sink | derived |
| Absence | `FILTER NOT EXISTS` over the submitted graph | no validation step on the output path | derived, graph-relative (R4) |

`pair:PropertyPathCondition` is the subclass for conditions evaluated via a SPARQL property path
(e.g., reachability of untrusted content to a generation step). Every condition must declare which
of its inputs are annotated and which are derived (R8).

**Grounding.** "Applicability" is the pattern literature's own term for the situations in which a
pattern applies [D2]. Conceptually the split follows the two-part definition of a hazard as a
system state or set of conditions that, together with a further set of conditions, leads to a loss
[D5]: the motif is the configuration, the applicability conditions are the circumstances under
which it becomes risk-relevant. The disanalogy is worth stating — in [D5] the further conditions
lie in the environment, outside the designer's control, whereas PAIR-AI's conditions are read from
the submitted graph.

*Not:* a facet (a facet is a value on an element; a condition is a predicate over a match).
*Not:* a claim about the world — satisfaction means the submitted graph *represents* the condition
as holding (R4).

### 7. AI Risk Pattern (`pair:RiskPattern`)

A reusable, system-independent unit of risk knowledge stating that a particular architectural
configuration, under stated conditions, is disposed toward a particular kind of harm, together
with the causal account and the controls that address it. Constituents:

> **Risk Pattern = Motif + Applicability Conditions + Mechanism + Taxonomy Links + Controls**

- *Motif* (term 4): the structural configuration that must be present — the structural
  WHERE-clause.
- *Applicability Conditions* (term 6): the risk-relevant predicates over a motif match.
- *Mechanism* (term 8): the causal account of how the configuration is disposed toward harm.
- *Taxonomy Links*: anchors to external taxonomies (IBM AI Risk Atlas, OWASP LLM Top 10, MIT AI
  Risk Repository) via `pair:mayIndicateRisk`, for interoperable findings.
- *Controls*: suggested mitigations via `pair:suggestedControl`.

**Genre grounding.** The format instantiates the classical context–problem–solution pattern anatomy [D2, D3]. 
Its closest existing genre is the misuse pattern in security engineering [D26], 
which likewise pairs the environment in which a misuse occurs with how it occurs, 
the countermeasures that address it, and the evidence needed to trace it.

**Link direction.** Motif and risk pattern are connected by the inverse pair `pair:hasMotif`
(pattern → motif) and `pair:hasRiskPattern` (motif → pattern).

> **`pair:hasMotif` is canonical.** The binding is authored on the **risk pattern**, because the
> motif is a *constituent of* the pattern per the equation above. `pair:hasRiskPattern` is a
> **required mirror**, not an optional convenience.

The mirror is mandatory because **no OWL reasoning runs in the assessment pipeline**: asserting
one direction does not materialize the other, so a one-sided assertion is invisible to any
consumer reading the other side. `owl:inverseOf` is declared in the ontology as documentation
only. Both directions are written explicitly in the library, the mirror is enforced by
`python/tests/test_library_consistency.py`, and the authoring rule is restated in the
`rdfs:comment` of both properties.

*Not:* a risk (a pattern is type-level and reusable; a finding is instance-level and
system-specific). *Not:* an anti-pattern — a risk pattern does not assert that the configuration
is bad practice, only that it is conditionally disposed toward harm. *Not:* a taxonomy entry,
which classifies harms rather than configurations.

### 8. Risk Mechanism (`pair:RiskMechanism`)

A curated statement of how a matched configuration, under the satisfied conditions, can lead to
harm — the risk pattern's **why**, as against its applicability conditions, which are the
machine-checkable **what**.

A mechanism is a node in the AI-RKG carrying reusable text and links to one or more external
taxonomy entries. It is **not computed and takes no part in detection**: it is never evaluated or
filtered on during motif matching or condition evaluation. Findings carry it by reference
(`pair:hasDerivedMechanism`), so the same explanation is reproduced unchanged across systems and
runs. Any sentence naming the concrete matched elements is built in the presentation layer from
the mechanism text plus evidence labels; it is not stored in the graph.

**Grounding.** Following the mechanistic account of causal explanation [D21], the motif supplies
the organised entities and activities, the applicability conditions supply the set-up conditions,
and the mechanism names the productive continuity between them and the outcome. The causal claim
is not entailed by the architecture graph, which is why it is curated rather than derived —
computing it at assessment time would assert more than the structure supports.

### 9. Candidate Risk Finding (`pair:RiskFinding`)

A system-specific, defeasible assertion that a risk pattern applies to one motif match, generated
when the submitted architecture graph *represents* that pattern's applicability conditions as
satisfied for that match. A finding links the motif match it was generated from, the matched
motif, the satisfied conditions, the derived mechanism, taxonomy entries, suggested controls, and
its **evidence** — the matched elements, attached via `pair:hasEvidence`, retained for durable
traceability in the spirit of PROV [D10].

Its epistemic status is carried by `pair:findingStatus`, the extension point for human triage and
for later runtime evidence. The **assessed system is not asserted on the finding**; it is
derivable by traversing from an evidence element to the `beam:System` that contains it.

A candidate risk is a structural disposition toward harm. It is not a confirmed failure,
 an observed incident, or a prediction that harm will occur. The stance is that 
 of static-analysis alerting, 
 where automated detection yields alerts requiring human triage rather than confirmed defects [D22]; 
 the formal basis is R4.


**Open item.** `pair:identifiesCandidateRisk` is declared but not yet emitted; no finding
currently links to a `beamr:Risk` individual, and no alignment exists between `nexus:Risk`
(taxonomy entries) and `beamr:Risk`. The intended target is that each finding maps onto a minted
`beamr:Risk` per finding, keeping taxonomy *categories* distinct from this system's *risk
instance*.

---

## B. Internal and narrative terms 

**Motif Match** (`pair:MotifMatch`) — a total mapping from the pattern nodes of one motif to
elements of one architecture graph that preserves the motif's declared edges and satisfies each
node's expected class and role. Matches are materialized as first-class resources with explicit
node bindings (`pair:hasNodeBinding`, `pair:bindsPatternNode`, `pair:matchedElement`) rather than
left implicit in query results, so that every downstream finding can name the concrete elements it
rests on. Because BGP matching is homomorphic, distinct pattern nodes are not distinct elements by
default; where a motif requires distinctness, its implementation must state it.

**System Aspect / System Configuration** — narrative concepts for the paper's motivation, not
ontology classes. An aspect is an individual element or property; a configuration is a combination
of aspects *and their relations* — the unit risk attaches to, justified system-theoretically:
hazards emerge from component interactions, not isolated components [D5]. In RDF a configuration
is simply a subgraph.

**Assessment output** — the aggregate RDF produced per assessment run, containing all candidate
risk findings for one system (one SonarQube *report* versus individual *warnings*). The paper also
calls this the Candidate Risk Graph. Not a defined vocabulary term.

**AI-RKG** — the reusable knowledge resource: Architecture module (BEAM + alignments), Risk module
(BEAM Risk / AIRO + taxonomies + control mappings), Pattern module. Stored permanently: the three
modules. Not stored permanently: per-system architecture graphs and findings.

**Motif Library** and **Risk Pattern Library** — two separate curated collections: the Motif
Library holds risk-neutral motifs; the Risk Pattern Library holds risk patterns (conditions,
mechanisms, links, controls). Both carry per-entry derivation provenance (`pair:derivedFrom` /
`dct:source`): (i) deductive from Boxology elementary patterns, (ii) interpretive from taxonomy
entries (e.g., OWASP), (iii) LLM-assisted with human validation. Firing-coverage denominators for
evaluation are computed against the frozen Risk Pattern Library.

**Control layer** — `pair:controlNature` (technical / non-technical, a SKOS scheme) and
`pair:realizedByMotif` (control → motif that could structurally realize it). Only the
project-authored `pat:Control_*` concepts appear in `pair:suggestedControl`; MIT `mitctrl:*`
families are reached as an evidence layer through taxonomy links. `pair:realizedByMotif` marks a
**candidate** structural mitigation, not proof that inserting the motif removes the risk.
Documented at file level in `ontology/patterns/control_mitigation_layer.ttl`; no modeling rule is
adopted for it yet.

---

## C. Modeling rules

**R1 — OWL class vs SKOS concept.**
OWL class for anything instantiated and traversed by queries (BEAM elements). SKOS concept for
anything only *assigned* as a classification value (roles, all facets including data categories).
Never instantiate a facet value.

**R2 — Motifs match structure; applicability conditions evaluate structure + facets.**
Motif matching operates exclusively on the structural layer (roles + flow relations).
Applicability conditions operate on structure *plus* facets, including context and
absence-of-control checks. Situational context enters at the applicability phase, not at matching.

**R3 — Two reuse mechanisms.**
*Structural reuse* (`owl:imports` / subclassing + `dct:source`): Boxology→BEAM, AIRO→BEAM Risk, DPV
for identifiability and entities. *Vocabulary reuse* (own SKOS scheme + `skos:exactMatch` /
`broadMatch`, exported as SSSOM [D11]): OECD, TÜV AI.ST (license pending), VAIR. Never copy DPV
concepts locally; reuse their URIs.
*Current state:* OECD anchoring is present as citations only — OECD publishes no resolvable
concept URIs, so those mappings remain TODO. VAIR is an intended target with no mapping yet. TÜV
AI.ST is on hold. The SSSOM export has not been generated, so R6's mapping-set obligation is
outstanding.

**R4 — Absence is graph-relative (candidate framing, formal basis).**
RDF/OWL follows the Open World Assumption: a missing triple means *unknown*, not *false*.
`FILTER NOT EXISTS` is a closed-world claim about the *submitted graph only*: "no validation
control is represented" ≠ "none exists". This formally justifies (a) candidate framing and (b) the
executable input contract (SHACL shapes).

**R5 — Predicate economy.**
Edge semantics derive from node types, not from proliferating properties, within BEAM core.
External vocabularies (Tool4Boxology, later AgentO) are aligned via `rdfs:subPropertyOf` and
CONSTRUCT normalization in `ontology/alignments/`, never by extending BEAM's property set.

**R6 — Provenance on every reused or curated concept.**
`dct:source` on every adapted concept; SKOS mapping where an external equivalent exists;
`pair:derivedFrom` on every motif and risk pattern; SSSOM with directionality and confidence for
mapping sets.

**R7 — Task ≠ Capability ≠ Application Type.**
Task: functional input→output relation of a functional unit (compositional). Capability
(VAIR/AIRO): what a technique can do; characterizes risk sources. Application type (OECD):
system-level facet. Three axes; SKOS-mapped, never merged.

**R8 — Annotated vs derived facts.**
Base facts are annotated by the modeler (this data is personal; this output is user-facing) — knowledge only 
humans have at design time. Derived facts are computed by rules or queries (untrusted content is reachable 
to a generation step via a property path; a control is absent on that path). Every applicability condition
 must state which of its inputs are annotated and which are derived. Runtime vulnerabilities appear at 
 design time as their structural preconditions, which is what a design-time method can see and what threat
  modeling practice already relies on [D12].

**R9 — Motif names are positive.**
A motif label may not contain a term implying absence, exclusivity, or sufficiency (*direct*,
*only*, *pure*, *without*, *unmediated*, *standalone*). Because motif matching is monotone
(term 4), a motif cannot assert absence, so a name that implies it will misreport. Absence is
expressible solely in applicability conditions (R2, R4), and a risk pattern name may carry it. The
library is swept against this rule at each version.

**R10 — Facet conditions are positive; control conditions may be negative.**
An applicability condition may test for the presence of a facet value on a bound element, 
never for its absence, unless the input contract makes that facet mandatory via SHACL.
 Facets are annotated base facts (R8): a missing `hasIdentifiabilityLevel` 
 means the modeler did not fill it in, not that the data is non-personal, 
 so a negative facet condition fires on every under-annotated system. Absence-of-control conditions are exempt, 
 because absence of a represented control is a claim about structure and is already graph-relative and 
 candidate-framed (R4). Making a facet mandatory in the input contract converts its absence from a silent
  default into a contract violation, and only then may conditions test it negatively.

---

## D. Grounding references

- **[D1]** Milo, R. et al. (2002). Network motifs: Simple building blocks of complex networks.
  *Science*, 298(5594), 824–827. — Graph-theoretic sense of "motif".
- **[D2]** Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design Patterns: Elements of
  Reusable Object-Oriented Software*. Addison-Wesley. — Pattern format; *Participants* ≈ roles;
  *Applicability* section (term 6).
- **[D3]** Buschmann, F. et al. (1996). *Pattern-Oriented Software Architecture, Vol. 1*. Wiley. —
  Architectural patterns as prescriptive solutions.
- **[D5]** Leveson, N. *Engineering a Safer World: Systems Thinking Applied to Safety*. MIT Press.
  — Hazards emerge from interactions; two-part hazard definition (state + conditions). *Decide
  between the 2011/2012 book and the STPA Handbook (Leveson & Thomas, 2018) and confirm the page.*
- **[D6]** Pérez, J., Arenas, M., & Gutiérrez, C. (2009). Semantics and complexity of SPARQL. *ACM
  Transactions on Database Systems*, 34(3). — Formal basis of the matching method.
- **[D9]** W3C (2009). *SKOS Simple Knowledge Organization System Reference*. W3C Recommendation.
  — Facet modeling.
- **[D10]** W3C (2013). *PROV-O: The PROV Ontology*. W3C Recommendation. — Evidence and derivation
  provenance.
- **[D12]** Shostack, A. (2014). *Threat Modeling: Designing for Security*. Wiley. — Design-time
  analysis of runtime attack surfaces.
- **[D14]** Gangemi, A., & Presutti, V. (2009). Ontology design patterns. In S. Staab & R. Studer
  (Eds.), *Handbook on Ontologies* (2nd ed.). Springer. DOI 10.1007/978-3-540-92673-3_10. —
  Establishes ODP terminology. *Confirm the page range.*
- **[D15]** Tsantalis, N., Chatzigeorgiou, A., Stephanides, G., & Halkidis, S. T. (2006). Design
  pattern detection using similarity scoring. *IEEE Transactions on Software Engineering*, 32(11),
  896–909. DOI 10.1109/TSE.2006.112. — Pattern detection as graph matching.
- **[D16]** Shaw, M., & Garlan, D. (1996). *Software Architecture: Perspectives on an Emerging
  Discipline*. Prentice Hall. — Architectural style, cited for contrast in A.4. *Confirm the page.*
- **[D17]** Guéhéneuc, Y.-G., & Antoniol, G. (2008). DeMIMA: A multilayered approach for design
  pattern identification. *IEEE Transactions on Software Engineering*, 34(5), 667–684.
  DOI 10.1109/TSE.2008.48. — **Primary grounding for "motif":** the design motif as the structural
  solution core of a pattern, individuated by roles and relations, matched against concrete
  systems.
- **[D18]** Zdun, U., & Avgeriou, P. (2005). Modeling architectural patterns using architectural
  primitives. *OOPSLA '05* (ACM SIGPLAN Notices). — Abstractions below the level of a pattern.
  *Confirm issue and pages.*
- **[D19]** Zdun, U., & Avgeriou, P. (2008). A catalog of architectural primitives for modeling
  architectural patterns. *Information and Software Technology*, pp. 1003–1034. — Primitives recur
  across the realizations of several patterns; grounds the m:n claim. *Confirm the volume.*
- **[D20]** Haitzer, T., & Zdun, U. (2015). Semi-automatic architectural pattern identification and
  documentation using architectural primitives. *Journal of Systems and Software*, 102, 35–57. —
  Method precedent: annotate with primitives, then propose catalogued pattern instances.
- **[D21]** Machamer, P., Darden, L., & Craver, C. F. (2000). Thinking about mechanisms.
  *Philosophy of Science*, 67(1), 1–25. DOI 10.1086/392759. — Definition of "mechanism": organised
  entities and activities productive of regular change from set-up to termination conditions.
- **[D22]** Heckman, S., & Williams, L. (2011). A systematic literature review of actionable alert
  identification techniques for automated static code analysis. *Information and Software
  Technology*, 53(4), 363–387. — Actionable vs unactionable alerts; grounds candidate framing.
- **[D23]** Knublauch, H., Hendler, J. A., & Idehen, K. (2011). *SPIN — Overview and Motivation*.
  W3C Member Submission. — Declarative definitions paired with executable SPARQL CONSTRUCT rules.
- **[D24]** Hitzler, P., Gangemi, A., Janowicz, K., Krisnadhi, A., & Presutti, V. (Eds.) (2016).
  *Ontology Engineering with Ontology Design Patterns: Foundations and Applications*. Studies on
  the Semantic Web, Vol. 25. IOS Press. — Current canonical ODP collection.
- **[D25]** De Nicola, A., & Villani, M. L. (2025). Actionable semantic patterns in the crisis
  management lifecycle: The TERMINUS ontology. *Smart Cities*, 8(5), 179.
  DOI 10.3390/smartcities8050179. — **Source of the ODP / OQP pairing:** a semantic pattern takes
  the ODP role when it structures an ontology or knowledge graph and the OQP role when it is
  operationalized as a reusable SPARQL template; the OQP may differ topologically from its ODP but
  must not violate its semantics.

- **[D4]** van Harmelen, F., & ten Teije, A. — Boxology of design patterns for hybrid learning and
  reasoning systems. Early version in *Journal of Web Engineering* (2019); extended version by van
  Bekkum et al., cited variously as *Applied Intelligence* (2021) and *Journal of Web Semantics*
  (2023). 
- **[D8]** Steimann, F. (2000). On the representation and essence of roles in object-oriented and
  conceptual modelling. *Data & Knowledge Engineering*, 35. — Role modeling.
- **[D11]** Matentzoglu, N. et al. (2022). SSSOM: A simple standard for sharing ontological
  mappings. *Database*. — Mapping provenance format.
- **[D13]** Bendler, J. E. et al. (2026). Tool4Boxology: A Semantic Toolbox for Constructing and
  Analysing Neuro-Symbolic Architectures. *ESWC 2026*, Springer, pp. 191–211,
  DOI 10.1007/978-3-032-25159-6_11. — Taken from the repository README; confirm against the
  published proceedings.
- **[D26]** Fernandez, E. B. et al. — Misuse patterns. 
The concept appears across several venues (VoIP misuse patterns; misuse patterns for cloud computing; 
Security Patterns in Practice, Wiley, 2013). Open: select one source that actually contains the definition, 
read it, and confirm it states the environment / mechanism / countermeasures / forensic-evidence anatomy b
efore citing. Not to be confused with misuse activities [D28], which is a threat-elicitation method, 
not a pattern genre.
- **[D27]** Blomqvist, E., & Sandkuhl, K. (2005). Patterns in ontology engineering: Classification
  of ontology patterns. *ICEIS 2005*, pp. 413–416. — Semantic-pattern classification underlying
  
- **[D28]** Pedraza-García, G., Noël, R., Matalonga, S., Astudillo, H., & Fernandez, E. B. (2016). Mitigating security threats using tactics and patterns: A controlled experiment. ECSAW '16, Copenhagen, ACM. DOI 10.1145/2993412.3007552. — Controlled-experiment design for pattern-based threat mitigation: expert-defined ground truth fixed in advance, binary per-decision scoring, nonparametric median comparison, training used as blocking. Also reports concrete structured pattern advice outperforming abstract tactics for novice subjects (3.0 vs 1.9, p = 0.027), with the authors' caveat that this runs contrary to earlier results with professionals. Confirm article number and page range.
