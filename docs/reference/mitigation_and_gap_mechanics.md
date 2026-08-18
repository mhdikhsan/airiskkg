# Mitigation and gap mechanics

What changed in the assessment loop, and how the two derived views work: the
**gap report**, which explains why a motif did *not* match, and the **mitigation
rewrite**, which inserts a control into an existing graph so a re-assessment
answers differently.

Counts in this document were read off the loaded ontology on 2026-08-17.
Re-count rather than trust them; `docs/reference/catalogue.md` records how.

---

## 1. What changed

### The retrieval layer stopped being vector-only

`VectorBasedInformationRetrievalMotif` was the only retrieval motif and its
store node demanded `pair:VectorStore`, so retrieval from a knowledge graph, a
keyword index or a relational store matched nothing at all. That was not
theoretical: `simple_graph_rag` annotated its Event KG — a `beam:SemanticModel`
— as a vector store, because that was the only way to be assessable. Labelled
honestly it scored 0 matches and 0 findings.

- `pat:InformationRetrievalMotif` is the general shape; vector IR remains its
  specialization and both match a vector system, which is how motifs nest here.
- RAG took the same correction. Nothing about retrieval-augmented generation
  depends on how the source is indexed, and requiring vectors meant graph RAG
  was not RAG.
- `pair:VectorSearchStep` and `pair:KeywordSearchStep` were `subRoleOf
  ProcessingStep`, not `RetrievalStep`, so tagging a step with the *precise*
  term stopped the motif matching. Onyx hid this by tagging its hybrid search
  with all three roles at once; removing only the generic one cost it 3 motifs
  and 8 findings.

### Controls became things you build, not things you assert

A control used to change nothing. Applying an input guardrail to a
prompt-injection finding left the finding exactly where it was, because the only
escape was an annotation nothing writes.

- Risk queries now test for the control **structurally**. 12 of 15 risk patterns
  have a structural escape, up from 9.
- `beamr:associatedTo` is gone from all 15 queries that carried it. Removing it
  left both examples byte-identical, which is the proof it was never satisfiable.
- `InputScreeningMotif` and `OutputScreeningMotif` are 3 nodes and 2 edges each.
  `GuardrailsMotif` is 8 and 8 — 16 constraints to say "we filter one side".
- Applying a control is a registered SPARQL rewrite (§3), not code.

### Findings say which rule raised them

`pair:generatedByRiskPattern` is emitted by every risk query. Without it a
finding could not be routed to the rewrite written for it, and a control
suggested by four patterns offered the same rewrite to all of them.

### Propagation stopped leaking through screens

`content_categories.rq` treated only redaction as a barrier, so a screened
response inherited exactly the categories the screen exists to stop — inserting
one *grew* the derived set from 12 to 17. Output guardrail and output validation
steps are barriers now. Pseudonymisation deliberately is not: `dpv:PseudonymisedData`
is a kind of `dpv:PersonalData`, so sensitivity must survive it.

### Smaller corrections

| | |
| --- | --- |
| Unbounded consumption | The direct-prompting branch had no loop test and no reachability test, so it fired on the mere presence of an LLM call. It now requires a path reachable from `pair:PublicUserInput`. |
| Sensitive information disclosure | Merged from two patterns that reported one disclosure from two ends, and keyed on (sink, category) so one sink raised several indistinguishable findings. Now one per sink, carrying evidence from both routes. |
| Grounding and verification | Realized only by retrieval motifs while the risk it answers clears on *verification*. `EvalsMotif` joins its realizations. |
| Performance | A run went from ~1.8s to ~0.33s: risk queries reordered for rdflib's left-to-right evaluation, knowledge base parsed once per process. |
| Canvas → source | Clicking a node, motif or finding marks and scrolls to the line that declares it. |

---

## 2. How the missing part of a motif is derived

The **gap report** answers "why didn't this match?", because an empty result set
is otherwise indistinguishable from a safe system. It is computed by
`_motif_gaps()` in `python/src/airiskkg/webapp/app.py` and returned on
`/api/assess` as `motifGaps`.

### Where the expected shape comes from

Not from the SPARQL. Every motif declares its own structure in `motif.ttl`:

```turtle
pat:InputScreeningMotif
    pair:hasPatternNode  pat:InputScreening_UserInputNode , … ;
    pair:hasPatternEdge  pat:InputScreening_ScreeningUsesInputEdge , … .

pat:InputScreening_UserInputNode
    pair:expectedClass beam:Data ;
    pair:expectedRole  pair:UserInput .
```

The report reads those declarations, so it can describe a motif the graph does
**not** contain. This is also why a declaration that drifts from its `.rq` is a
defect: the template would no longer match itself.

### The derivation, per motif

1. **Satisfy each pattern node.** An element qualifies when its `rdf:type` meets
   the node's `expectedClass` and it plays a role under the node's
   `expectedRole`. Both checks mirror the match queries exactly —
   `_elements_of_class` accepts any process-family class, `_role_closure` walks
   `pair:subRoleOf*` downward — so the report can never disagree with the
   assessment about what would bind.
2. **Record near misses.** Elements of the *right class* that lack the role are
   kept (up to four) as candidates. This is the actionable half: they are the
   elements a one-line annotation would promote.
3. **Satisfy each pattern edge.** An edge holds when any element bound to its
   source has that BEAM predicate to any element bound to its target.
4. **Score.** `satisfied / total` over nodes plus edges. A motif scoring 100% is
   dropped — it matched, and is reported as a match instead.
5. **Rank.** Closest first, so the motifs a small fix would complete come first.
   The UI shows those above 50%.

### What it looks like

On `simple_graph_rag`:

```
Query Rewriting Motif: 8/9
   missing edge: no Query Reformulation Step uses a Generative Model
Direct Prompting Motif: 6/7
   missing edge: no Generation Step uses a User Input
```

Clicking a gap highlights its candidate elements on the canvas.

### What it cannot tell you

The report is structural. It says a role is unfilled or an edge absent; it does
not say whether filling it would be *true* of your system. A near miss is an
invitation to check an annotation, never an instruction to add one — annotating
an element to make a motif match is how a graph starts lying about itself.

---

## 3. How a mitigation reaches the graph

Applying a control is a **registered SPARQL CONSTRUCT**, declared beside the
rule that raised the finding. There are 9 rewrites.

### Why a query rather than code

An earlier version did the insertion in Python and guessed which evidence
element was which — first unclaimed anchor satisfying the role. That put the
knowledge of where a control belongs in the webapp, away from the rule, and left
the binding to a heuristic that picks wrongly whenever a finding cites two
elements of the same kind.

A rewrite instead **restates the vulnerable shape** the risk query found. The
conditions that raised the finding also identify where the screen belongs, so
nothing is guessed.

### The declaration

```turtle
pat:InputScreening_MitigationOQP
    a pair:PatternImplementation ;
    pair:implementsControl     pat:Control_InputValidationAndPromptIsolation ;
    pair:mitigatesRiskPattern  pat:PromptInjectionRiskPattern ;
    pair:implementationPath    "…/mitigation/input_screening.rq" ;
    pair:producesOutputType    pair:MitigationApplication .
```

Three properties carry the design:

- **`producesOutputType pair:MitigationApplication` is the safety catch.** The
  assessment pipeline asks only for `MotifMatch` and `RiskFinding`, so a rewrite
  never runs inside an assessment. If it did, every finding would mitigate
  itself and none would ever be reported.
  `test_a_mitigation_rewrite_never_runs_during_an_assessment` enforces it.
- **`implementsControl` + `mitigatesRiskPattern` are the routing key.** Keyed on
  the control alone, one control's only rewrite was offered for every finding
  that suggested it — clicking Apply on a sensitive-retrieval finding ran the
  improper-output-handling rewrite, found its own screen already in place, added
  nothing, and left the risk untouched.
- **`implementationPath` is data.** Moving the file means updating the
  declaration; `test_library_consistency.py` fails if they drift.

### The rewrite

```sparql
CONSTRUCT {
    ?screeningStep a beam:Process ;
        rdfs:label "Input screening"@en ;
        pair:playsRole pair:InputGuardrailStep ;
        beam:use    ?untrustedContent ;
        beam:inform ?generationStep .
    ?system beam:hasProcess ?screeningStep .
}
WHERE {
    ?finding a pair:RiskFinding ;
        pair:generatedByRiskPattern pat:PromptInjectionRiskPattern ;
        pair:hasEvidence ?untrustedContent , ?generationStep .
    …                                 # the vulnerable shape, restated
    FILTER NOT EXISTS { … }           # and only where no screen exists yet
    BIND(IRI(CONCAT(
        "http://w3id.org/airiskkg/generated/mitigation/input-screening/",
        ENCODE_FOR_URI(STR(?untrustedContent)), "/",
        ENCODE_FOR_URI(STR(?generationStep))
    )) AS ?screeningStep)
}
```

`?finding` is supplied by the caller through `initBindings`, so applying a
control acts on the finding an assessor clicked and leaves every other finding
alone.

The inserted IRI is **derived from the elements it screens**, so applying twice
constructs identical triples and the second application is a no-op. The
`FILTER NOT EXISTS` is the same test the risk query uses, so a step is
constructed exactly where one is missing and nowhere else.

### The triples, and where they land

Applying input screening to a bare direct-prompting graph produces six:

```turtle
<…/mitigation/input-screening/…prompt/…gen>
    a beam:Process ;
    rdfs:label "Input screening"@en ;
    pair:playsRole pair:InputGuardrailStep ;
    beam:use    ex:prompt ;
    beam:inform ex:gen .

ex:sys beam:hasProcess <…/mitigation/input-screening/…prompt/…gen> .
```

Every subject or object other than the new step is an element **already in the
graph**, which is what makes this an edit rather than an island: one new node,
wired to the prompt it screens and the generation it informs.

`POST /api/apply-control` runs the assessment (the rewrite reads a finding, which
does not exist in a bare architecture), calls `apply_control()`, merges the
constructed triples into the **architecture** graph — never the library — and
returns the amended Turtle. The UI adopts it and re-assesses immediately.

### What is *not* claimed

`apply_control()` returns the triples and adds nothing itself. The caller
amends the design and re-runs, and the same rules speak again. The finding
disappears because the graph no longer represents the gap — not because anything
was proven safe (Rule R4).

Applied in sequence on onyx, findings fall from 25 to 14.

### A limitation worth knowing

A CONSTRUCT can only **add** triples. A true interceptor — generation produces a
raw response, the screen consumes it and produces the user-facing output —
requires retracting the edge it replaces. Built and measured, it worked
structurally but **over-cleared**: prompt injection and system prompt leakage
vanished because four risk queries require the generation step to produce the
user-facing output *directly*, and interposing breaks that assumption. Untrusted
content still reached the prompt; the tool simply stopped saying so.

It was reverted. False negatives are the worst failure mode for this tool, and
the prerequisite — making those four queries path-tolerant — is a separate,
measurable change.

So a screen is currently **appended**: it reads the output rather than gating it.
For verification that is correct (an evaluator reads a response, it does not
replace it). For screening and redaction it is a known approximation.

---

## 4. Next steps

**Ready to build**

1. **Finding-level triage.** Three risk patterns — data and model poisoning,
   supply chain, vector and embedding weakness — rest on provenance and vetting,
   have no runtime shape, and cannot be cleared by design work. `pair:findingStatus`
   is the documented extension point; finding IRIs are deterministic, so an
   assessor's "accepted, handled by process" survives re-runs and stops
   surviving when the architecture changes. Needs a status control per finding
   and a decision on where the state lives.
2. **Interposition, properly.** Make the four output-side risk queries
   path-tolerant (`beam:produce/(^beam:use/beam:produce)*`, the idiom `rag.rq`
   already uses), then reinstate the retraction mechanism. Verify no finding
   clears for structural reasons rather than mitigated ones.
3. **Two more rewrites** for patterns that already have a structural escape:
   `GoalHijack` (ASI01) and `InsecureAgentCommunication` (ASI07). That takes
   agentic coverage to all four modelled ASI entries.

**Needs a decision first**

4. **Category 2 of the mitigation reference** — process, governance and
   lifecycle measures. They have no runtime shape and must never become motifs.
   Three layers, cheapest first: surface the `lifecyclePhase` the MIT layer
   already carries; add an assessment-level checklist rather than a per-finding
   one; and model `partlyRealizedByMotif` for hybrids like human-oversight
   protocol, where a gate is structural and the protocol behind it is not.
   Avoid SHACL shapes demanding governance annotations — those fire on every
   under-annotated graph.
6. **Findings duplicate per match.** A risk that binds `?match` with an unbound
   `?motif` fires once per match containing the element, so inserting any motif
   can multiply a finding without changing the architecture's risk. Presentation
   layer could group by (label, evidence set).

**Outstanding, unrelated to this work**

7. **MIT upstream terms are unverified.** `mit_air_risk_control.ttl` reproduces
   the MIT RiskControlGroup layer verbatim; Apache 2.0 covers IBM's packaging,
   not MIT's own rights. Resolve before publication.
8. **Push and NDA cleanup.** 13 commits are unpushed. The earlier history
   rewrite still needs GitHub Support contacted to purge cached objects.
