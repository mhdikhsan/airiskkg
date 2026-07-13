# Risk Pattern Library: Derivation and Sources

This document explains where the content of `ontology/patterns/risk_pattern_library.ttl`
(and the SPARQL implementations in `ontology/patterns/implementation/risk_*.rq`) actually
comes from — what is copied/re-expressed from an external source, what is a manual
alignment between sources, and what is original interpretive work done for this
project.

## 1. Layered structure

The risk pattern library sits on top of two things that were built first:

```
ontology/taxonomy/          <- external risk taxonomies, re-expressed as RDF/SKOS
ontology/patterns/motif.ttl <- external architecture pattern catalogs, re-expressed as RDF
        |
        v
ontology/patterns/risk_pattern_library.ttl   <- this project's own work: connects
                                                 motifs to taxonomy risks through
                                                 manually authored interpretations
        |
        v
ontology/patterns/implementation/risk_*.rq   <- SPARQL CONSTRUCT rules that execute
                                                 those interpretations against a graph
```

Each `pair:MotifInterpretation` node in `risk_pattern_library.ttl` (e.g.
`pat:PromptInjectionInterpretation`) is built from four kinds of fields, each with a
different provenance:

| Field | Example | Source |
| --- | --- | --- |
| `pair:interpretedAsMechanism` | `owasp:mechanism-instruction-override` | Manually derived from OWASP's prose description (see §3) |
| `pair:hasInterpretationCondition` | `pat:PromptInjection_UntrustedPromptContextCondition` | Authored for this project — no external source |
| `pair:mayIndicateRisk` | `owasp:llm01-prompt-injection`, `atlas:prompt-injection`, `mit:subdomain-2-2` | Copied from external taxonomies + manually cross-mapped |
| `pair:suggestedControl` | `pat:Control_Guardrails`, `mitctrl:red-teaming` | Mix of project-authored controls and MIT AI Risk Control entries |

## 2. External sources, as declared in the files themselves

Every ontology file that re-expresses an external source carries a `dct:source`
triple pointing at it. These are the sources currently used:

**Primary risk taxonomy anchor**
- OWASP Top 10 for LLM Applications 2025
  - https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
  - https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf
  - https://github.com/owasp/www-project-top-10-for-large-language-model-applications
  - Re-expressed in `ontology/taxonomy/owasp_llm.ttl`

**Secondary taxonomies and RDF-ization pipeline**
- IBM AI Atlas Nexus (also the intermediary that supplied machine-readable YAML for
  OWASP, MIT AI Risk Repository, and MIT AI Risk Control/Mitigation data)
  - https://github.com/IBM/ai-atlas-nexus/tree/main/src/ai_atlas_nexus/data/knowledge_graph
  - Re-expressed in `ontology/taxonomy/nexus_taxonomy_core.ttl`, `ibm_risk_atlas.ttl`,
    `mit_ai_risk_repo.ttl`, `mit_air_risk_control.ttl`

**Architecture motifs (`ontology/patterns/motif.ttl`)**
- Mercari ML System Design Pattern catalog — serving, training, lifecycle, and
  operation motifs
  - https://mercari.github.io/ml-system-design-pattern/
- Martin Fowler, "Emerging patterns for generative AI systems" — RAG, embedding,
  reranker, query rewriting, guardrail, eval, and fine-tuning motifs
  - https://martinfowler.com/articles/gen-ai-patterns/

**Base ontology**
- BEAM core (`ontology/core/beam_core.ttl`) — adapted from Boxology's Extended
  Annotation Model
- BEAM risk extension (`ontology/core/beam_core_risk.ttl`) — built on AIRO, the AI
  Risk Ontology (https://w3id.org/airo)
- `pair-ai` (`ontology/core/pair_ai_pattern.ttl`) — this project's own pattern
  vocabulary, no external source; it imports BEAM core and BEAM risk

None of the above is a manual claim — every one of these `dct:source` triples can be
grepped for directly in the `.ttl` files.

## 3. What was manually derived (the actual interpretive work)

OWASP's Top 10 only gives a short prose description per risk category (e.g. LLM01:
"User or external inputs may alter LLM behavior or output in unintended ways"). It
does not define a machine-checkable mechanism or condition. Two things in this
project were manually authored to bridge that gap:

1. **Risk mechanisms and conditions in `owasp_llm.ttl`** — for each `owasp:llmNN-*`
   risk, a `nexus:hasRiskMechanism` and one or more `nexus:hasRiskCondition` were
   written by interpreting the OWASP description into a graph-level cause
   (`pair:RiskMechanism`, e.g. `owasp:mechanism-instruction-override`) and one or
   more preconditions (`nexus:RiskCondition`, e.g.
   `owasp:condition-untrusted-input-enters-prompt-context`).

2. **Motif interpretations and interpretation conditions in
   `risk_pattern_library.ttl`** — for each `pair:MotifInterpretation`, the
   `pair:hasInterpretationCondition` nodes (e.g.
   `pat:PromptInjection_UntrustedPromptContextCondition`) and the SPARQL CONSTRUCT
   logic in the matching `ontology/patterns/implementation/risk_*.rq` file are
   original work: they translate the OWASP mechanism/condition prose into an actual
   graph pattern that can be matched against an architecture instance (e.g. "an
   `pair:UntrustedContent`-tagged element reaches a generation step that produces
   user-facing output").

There is no `dct:source` on these nodes because there isn't one — they are this
project's contribution, not a copy of an external artifact.

## 4. Cross-taxonomy links (`pair:mayIndicateRisk`)

Each interpretation also points at equivalent or related risks in other taxonomies
via `pair:mayIndicateRisk` (e.g. `pat:PromptInjectionInterpretation` links to
`owasp:llm01-prompt-injection`, `atlas:prompt-injection`, `mit:subdomain-2-2`, and
`mit:subdomain-4-3`). These links were built manually by reading the descriptions of
each taxonomy's entries side by side and asserting a match — the same alignment work
also appears as standalone `skos:broadMatch` triples in
`ontology/taxonomy/taxonomy_mapping.ttl`, independent of any single interpretation.
That file is the place to check the mapping without going through a specific motif
interpretation.

## 5. Suggested controls (`pair:suggestedControl`)

Controls attached to an interpretation come from two places:
- `pat:Control_*` nodes — defined at the top of `risk_pattern_library.ttl`
  (lines ~40-135), authored for this project as generic control categories (e.g.
  `pat:Control_Guardrails`, `pat:Control_DataMinimizationAndRedaction`).
- `mitctrl:*` nodes — copied from the MIT AI Risk Repository's mitigation/control
  taxonomy (`ontology/taxonomy/mit_air_risk_control.ttl`), sourced via the same IBM
  AI Atlas Nexus YAML files referenced in §2.

