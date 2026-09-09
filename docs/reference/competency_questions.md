# PAIR-AI competency questions

A competency question states what the knowledge base is supposed to be able to
answer. Written as prose it is a claim; written as SPARQL it is a check. Every
question below is a file in [`competency_questions/`](competency_questions/), and
every one of them is run against a real graph by

```
python python/scripts/run_competency_questions.py
```

which writes `outputs/competency_questions_report.md` — the questions plus the
rows the knowledge base returned. `test_competency_questions.py` runs the same
set and fails when a question stops answering, so a query that drifts away from
the vocabulary is caught rather than quietly returning nothing.

## What they run against

One graph, assembled the way an assessment assembles it:

1. the knowledge base (`knowledge_base.ontology_files()`, 24 files),
2. the shipped example architectures and process models,
3. derived facts — data categories propagated to a fixed point, business flow,
4. motif matches, then candidate risk findings,
5. the run's own PROV record from `build_export`.

Mapping provenance (`ontology/taxonomy/provenance/`) is added **after** the
assessment, never before. It sits below the runner's non-recursive glob on
purpose: a finding must never be able to cite its own provenance as support.
Only CQ19 reads it.

To answer them somewhere else — GraphDB, Fuseki, YASGUI — load the merged export
instead:

```
python python/scripts/local/export_ontology.py --with-examples
```

That writes `outputs/ontology_export/`, which also carries the viewer-ready
files (`pair_ai_complete.owl`, `pair_ai_schema.owl`).

## The questions

Row counts are what the shipped teaching set returned on 2026-09-08. They are a
sanity signal, not a specification: add an example graph and the architecture and
assessment counts move, while the library counts should not.

### Architecture — what a submitted graph says

| CQ | Question | Rows | Reads |
| --- | --- | --- | --- |
| CQ01 | Which AI systems does a submitted architecture graph describe, and how many processes, resources and agents does each hold? | 2 | `beam:System`, `beam:hasProcess` / `hasResource` / `hasAgent` |
| CQ02 | What flows through a system — which process uses or produces which resource, and which process informs which? | 37 | `beam:use`, `beam:produce`, `beam:inform` |
| CQ03 | Which pattern role does each element play, and where does that role sit in the hierarchy? | 34 | `pair:playsRole`, `pair:subRoleOf` |

There is no stored scope: a system boundary is the traversal, which is also how
`graph_view._members_of()` answers "the architecture behind this activity".

### Library — what the method can recognise

| CQ | Question | Rows | Reads |
| --- | --- | --- | --- |
| CQ04 | Which characterization facets can be annotated, on what kind of element, and with what intended values? | 10 | `facet:` object properties, `rdfs:domain` |
| CQ05 | Which motifs does the library recognise, in which family, and how large is each? | 31 | `pair:GraphMotif`, `pair:motifFamily`, `hasPatternNode` / `hasPatternEdge` |
| CQ06 | What structure does one motif declare — which nodes, of which expected class and role, connected how? | 9 | `pair:PatternNode`, `pair:PatternEdge`, `pair:expectedRole` / `expectedClass` |
| CQ07 | Which executable query implements each motif, and where does that file live? | 31 | `pair:implementedBy`, `pair:implementationPath` |
| CQ08 | Which motifs declare a role set contained in another's, and so are candidates to co-match? | 5 | `pair:hasPatternNode/pair:expectedRole` |
| CQ09 | Which design source is each motif derived from? | 31 | `pair:derivedFrom` |
| CQ10 | What is a risk pattern made of — motifs, conditions, mechanism, taxonomy links, controls? | 15 | the constituent equation, glossary term 7 |
| CQ11 | Given a motif, which risk patterns can apply to it, and with what mechanism? | 3 | `pair:hasRiskPattern` (the required mirror) |
| CQ12 | Which risk patterns name no motif, and are evaluated over any match whose conditions hold? | 2 | absence of `pair:hasMotif` |
| CQ13 | Which external catalogues does the library reach, and how many entries of each can a finding cite? | 4 | `pair:mayIndicateRisk` |
| CQ14 | For each risk taxonomy, how many entries can a risk pattern flag, and how many not? | 5 | `nexus:Risk`, `skos:inScheme`, `pair:mayIndicateRisk` |
| CQ15 | Which controls does each risk pattern suggest, of what nature, realized by which motif? | 41 | `pair:suggestedControl`, `pair:controlNature`, `pair:realizedByMotif` |
| CQ16 | Which control can actually be applied to a graph, for which risk pattern, by which rewrite? | 9 | `pair:MitigationApplication`, `pair:implementsControl`, `pair:mitigatesRiskPattern` |
| CQ17 | From an entry the library flags, which entries in other catalogues are reachable, and by which predicate? | 90 | SKOS mapping predicates |
| CQ18 | How does each pattern role state where it came from? | 3 | `dct:source`, SKOS mappings, `pair:subRoleOf+` |

Three answers are worth reading rather than counting:

- **CQ14** — OWASP LLM 10 of 10 and OWASP ASI 4 of 4 are flagged; Atlas 9 of 18,
  MIT 10 of 12, NIST 0 of 9. NIST is an alignment layer reached through Atlas,
  not something risk patterns anchor on, so 0 is the design. ASI is 4 of 4 of
  what is *modelled* — six ASI entries are deliberately absent from the
  knowledge base because they have no design-time structural signature.
- **CQ18** — 50 roles state their own `dct:source`, 35 carry a SKOS mapping, 12
  inherit through `pair:subRoleOf`, and none are ungrounded. The chain is walked,
  not looked at: a role that refines another is grounded by the role it
  specializes.
- **CQ08** — five containments, including `InputScreeningMotif` and
  `OutputScreeningMotif` inside `GuardrailsMotif`. The library is deliberately
  not an antichain, which is why a match count measures structural coverage
  rather than distinct architectural features.

### Assessment — what one run produced

| CQ | Question | Rows | Reads |
| --- | --- | --- | --- |
| CQ20 | Which motifs matched, and which element bound to which pattern node? | 30 | `pair:MotifMatch`, `pair:hasNodeBinding`, `pair:matchedElement` |
| CQ21 | Which candidate findings were raised, from which risk pattern, with what evidence and taxonomy entries? | 9 | `pair:RiskFinding`, `pair:hasEvidence`, `pair:hasCandidateRiskTaxonomyEntry` |
| CQ22 | Which system does each candidate finding belong to? | 11 | evidence element → containing `beam:System` |
| CQ23 | Which data categories reached an element, by annotation or by derivation? | 55 | `pair:containsDataCategory`, `prov:qualifiedDerivation` |
| CQ24 | What did this run run on? | 2 | `prov:Activity`, `prov:Entity`, `pair:contentFingerprint`, `pair:assessmentFingerprint` |

Every finding is a **candidate** risk — a structural disposition requiring human
triage, never a confirmed failure. CQ22 is a traversal rather than a lookup on
purpose: the assessed system is not asserted on the finding.

### Business context — what the process layer contributes

| CQ | Question | Rows | Reads |
| --- | --- | --- | --- |
| CQ25 | Which business activity is carried out by which AI system, and who owns it in the process? | 1 | `pair:refinedBy`, `bp:flowNodeRef`, `bp:processRef` |
| CQ26 | What happens in the process before the activity an AI system carries out? | 2 | `pair:businessFollows` |
| CQ27 | Which annotation on the business process produced a data category in the architecture? | 1 | `prov:qualifiedDerivation` joined on `pair:refinedBy` |

The two layers join by refinement, never subsumption: a `bpmn:activity` is not a
`beam:Process`. CQ26 reads the materialized `pair:businessFollows` hop rather
than a raw path over `bp:sourceRef` / `bp:targetRef`, which is declared on five
classes and would walk out of control flow and back in somewhere unrelated.

### Provenance — what the mappings rest on

| CQ | Question | Rows | Reads |
| --- | --- | --- | --- |
| CQ19 | On what evidence does each cross-taxonomy mapping rest? | 11 | `sssom:Mapping`, `sssom:mapping_justification` |

Answered over `ontology/taxonomy/provenance/` only. The justifications are not
uniform and the query shows which is which: manually curated upstream rows sit
beside 103 rows justified `UnspecifiedMatching` and 32
`SemanticSimilarityThresholdMatching`. Adopt an upstream row over curating one,
and treat a similarity-derived row as a human decision rather than an automatic
adoption.

## Adding a question

1. Write `CQnn_short_name.rq` in `competency_questions/`, starting with
   `# CQnn: <the question>` and a `# Scope:` line.
2. Add a row to the table above.
3. Run the script and check the answer is what you claimed.

Two things the queries do that are worth copying. Aggregates over an OPTIONAL
variable need `COALESCE(REPLACE(...), "")` — rdflib raises `NotBoundError` from
`GROUP_CONCAT(DISTINCT ...)` on an unbound value rather than skipping it. And
`REPLACE(STR(?x), "^.*[#/]", "")` rather than `STRAFTER(STR(?x), "#")`, because
not every example graph mints its IRIs under a `#` namespace.
