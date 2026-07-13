# Pattern, Motif, and Role Derivation

## a. Pattern is derived from OWASP LLM Top 10 (GenAI)

- `ontology/patterns/risk_pattern_library.ttl` declares itself "OWASP-Aligned LLM
  Risk Pattern Library" and lists `dct:source` pointing directly at OWASP:
  - https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
  - https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf
- The 10 OWASP entries themselves are re-expressed as RDF/SKOS in
  `ontology/taxonomy/owasp_llm.ttl` (`owasp:llm01-prompt-injection` … `owasp:llm10-unbounded-consumption`), each with `skos:definition` copied/paraphrased from the OWASP text.
- OWASP only provides prose per category, so each entry was manually extended with:
  - one `nexus:hasRiskMechanism` (a `pair:RiskMechanism`, e.g. `owasp:mechanism-instruction-override`) — the underlying cause, written by interpreting the OWASP description
  - one or more `nexus:hasRiskCondition` (a `nexus:RiskCondition`, e.g. `owasp:condition-untrusted-input-enters-prompt-context`) — the graph-level precondition for that risk to apply
- `risk_pattern_library.ttl` then wraps each mechanism into a `pair:MotifInterpretation` (e.g. `pat:PromptInjectionInterpretation`) that:
  - links back to the OWASP mechanism via `pair:interpretedAsMechanism`
  - links to the OWASP risk (and MIT/IBM equivalents) via `pair:mayIndicateRisk`
  - attaches manually authored `pair:hasInterpretationCondition` nodes and `pair:suggestedControl` entries
- IBM AI Atlas Nexus (https://github.com/IBM/ai-atlas-nexus) is the secondary source, both as an independent taxonomy (IBM AI Risk Atlas) and as the YAML data pipeline used to pull MIT AI Risk Repository / MIT AI Risk Control data into this project's RDF.
- Bottom line: the **risk categories and their definitions** come from OWASP (copied/paraphrased); the **mechanism/condition/interpretation graph structure** is this project's manual translation of that OWASP text into something SPARQL can check.

## b. Motif is derived from GenAI and ML system design patterns

- `ontology/patterns/motif.ttl` re-expresses two external pattern catalogs as RDF, each `dct:source`-tagged per motif:
  - Mercari's ML System Design Pattern catalog (https://mercari.github.io/ml-system-design-pattern/) — serving patterns (Synchronous, Asynchronous, Batch, Prep-pred, Multi-stage prediction), training patterns (Batch training, Pipeline training), lifecycle patterns (Train-then-serve, Training-to-serving), operation patterns (Prediction log, Prediction monitoring, Model load, Model-in-image)
  - Martin Fowler's "Emerging patterns for generative AI systems" (https://martinfowler.com/articles/gen-ai-patterns/) — GenAI-specific motifs: RAG, embedding, evaluation/LLM-as-judge, hybrid vector+keyword search, query rewriting, reranking, guardrails, fine-tuning
- **How each motif is constructed** (two layers, both inside the ontology):
  1. **Declarative shape** — a `pair:GraphMotif` is built from:
     - `pair:PatternNode` instances, each with `pair:expectedClass` (a BEAM class, e.g. `beam:Process`) and `pair:expectedRole` (a `pair:PatternRole`, e.g. `pair:RetrievalStep`) — these are the motif's "slots"
     - `pair:PatternEdge` instances, each with `pair:sourcePatternNode`, `pair:targetPatternNode`, and `pair:patternPredicate` (a BEAM property, typically `beam:use` or `beam:produce`) — these are the required connections between slots
     - Example: `pat:VectorBasedInformationRetrievalMotif` has 4 nodes (query, vector store, retrieval step, retrieved result) wired by `beam:use`/`beam:produce` edges
  2. **Executable matcher** — a matching SPARQL `CONSTRUCT` query in `ontology/patterns/implementation/match_*.rq` (e.g. `match_vector_ir.rq`) that:
     - walks the same shape over an actual architecture instance graph (e.g. `uc6.ttl`), using `pair:subRoleOf*` (transitive) to match role subtypes, not just exact roles
     - materializes a `pair:MotifMatch` node with one `pair:NodeBinding` per pattern node, binding each abstract slot to the concrete matched element
- So "constructing a motif" means: (1) name the required node/edge shape once in `motif.ttl` using the `pair:` vocabulary, then (2) write a SPARQL CONSTRUCT rule that finds that shape and records the match — the declarative shape and the query rule are kept in sync by hand, there's no auto-generation between them.


### Classes

- `pair:PatternRole` — subclass of `skos:Concept`; root of the role taxonomy (`pair:ProcessingStep`, `pair:ControlStep`, `pair:ResourceRole`, and ~60 more specific roles)
- `pair:DataCategory` — subclass of `skos:Concept`; root of the data-sensitivity/provenance taxonomy (`pair:TrustedContent`, and the undeclared-but-used `UntrustedContent`/`SensitiveInformation`/etc.)
- `pair:GraphMotif` — a reusable architectural pattern, composed of pattern nodes/edges
- `pair:PatternNode` / `pair:PatternEdge` — the building blocks of a motif's declarative shape
- `pair:GraphCondition` (and subclass `pair:PropertyPathCondition`) — a checkable condition attached to a motif interpretation
- `pair:AIRiskPattern` (and subclass `pair:MotifInterpretation`) — a risk-bearing reading of a motif
- `pair:RiskMechanism` — the underlying cause a motif interpretation is mapped to (populated from OWASP, see §a)
- `pair:PatternImplementation` — metadata node pointing at the `.rq` file that executes a motif or interpretation
- `pair:MotifMatch` / `pair:NodeBinding` — the runtime result of matching a motif against an instance graph, and the per-slot bindings within it
- `pair:RiskFinding` — the final output: a candidate risk generated from a match, an interpretation, and its evidence
- `pair:DataCategoryPropagation` — marker class for implementations that infer `pair:containsDataCategory` facts (like `propagate_untrusted_content.rq`) rather than requiring manual tagging

### Object properties (grouped by what they connect)

- **Roles/categories:** `pair:playsRole` (Resource → PatternRole), `pair:subRoleOf` (transitive), `pair:containsDataCategory` (beam:Data → DataCategory), `pair:subDataCategoryOf` (transitive)
- **Motif shape:** `pair:hasPatternNode`, `pair:hasPatternEdge`, `pair:sourcePatternNode`, `pair:targetPatternNode`, `pair:patternPredicate`, `pair:expectedClass`, `pair:expectedRole`
- **Interpretation:** `pair:hasInterpretation`, `pair:interpretsMotif`, `pair:hasInterpretationCondition`, `pair:interpretedAsMechanism`, `pair:mayIndicateRisk`, `pair:suggestedControl`, `pair:operationalizesRiskCondition`
- **Implementation linkage:** `pair:implementedBy` (domain is a union of `GraphMotif`/`MotifInterpretation`), `pair:implementsMotif`, `pair:implementsInterpretation`, `pair:producesOutputType`
- **Matching:** `pair:matchesMotif`, `pair:hasNodeBinding`, `pair:bindsPatternNode`, `pair:matchedElement`
- **Findings:** `pair:generatedFromMatch`, `pair:generatedByMotif`, `pair:hasEvidenceElement`, `pair:hasInterpretedMechanism`, `pair:hasCandidateRiskTaxonomyEntry`, `pair:hasSuggestedControl`, `pair:hasSatisfiedCondition`

### Data properties

- `pair:implementationPath` (`xsd:string`) — file path to the `.rq` implementation
- `pair:findingStatus` (`xsd:string`) — status of a finding (e.g. `"candidate"`); the file has an inline `#maybe add skos concept here later` comment noting this is a placeholder that could be tightened to a controlled vocabulary later

## d. Where Roles actually come from

- Roles were not adopted from any pre-existing taxonomy or vocabulary — no external role/annotation standard was used as a starting point.
- They were interpreted directly from two source materials:
  - the risk source documents (currently OWASP LLM Top 10) — read to identify which process/component distinctions actually matter for a risk to apply (e.g. distinguishing a `RetrievalStep` from a generic `ProcessingStep` because OWASP LLM08 specifically talks about retrieval/embedding weaknesses)
  - the architectural patterns (Mercari ML System Design Pattern catalog, Martin Fowler's GenAI patterns) — read to identify the specific processes and components each pattern is built from (e.g. a query rewriting step, a vector store, a reranker model)
- The interpretation step — turning those two source materials into the actual `pair:PatternRole` vocabulary used to annotate processes and components — was done using an LLM, not copied or mapped from a formal ontology/taxonomy.
- In short: Roles are an LLM-assisted reading of OWASP + the architecture pattern catalogs, used to annotate the specific processes and components those sources describe, not a reuse of any existing role vocabulary.

## e. How matching works

Everything runs in one growing working graph (see `python/src/airiskkg/assessment_runner.py`), built up in ordered stages:

1. **Load the base graph** (`load_base_graph`) — BEAM core, BEAM risk, `imports.ttl`, `pair_ai_pattern.ttl`, `motif.ttl`, `risk_pattern_library.ttl`, and every file under `ontology/taxonomy/` are parsed into one `rdflib.Graph`. At this point there is only vocabulary and rules, no architecture instance yet.

2. **Load the architecture instance** (`load_assessment_graph`) — the target file (e.g. `uc6.ttl`) is parsed into the same graph. It's already expressed in BEAM classes (`beam:Process`, `beam:Data`, …) connected by `beam:use`/`beam:produce`, and annotated with `pair:playsRole` / `pair:containsDataCategory` — so everything a motif needs to check is already present as plain triples.

3. **Propagate data categories** (`_propagate_data_categories`) — implementations whose `pair:producesOutputType` is `pair:DataCategoryPropagation` (e.g. `propagate_untrusted_content.rq`) are run repeatedly against the working graph, up to 20 passes, until no new triples appear (a fixed-point loop). This is what tags derived elements as `pair:UntrustedContent` automatically from role + data-flow, instead of requiring every element to be hand-tagged.

4. **Motif matching = "does this shape exist?"** For every implementation whose `pair:producesOutputType` is `pair:MotifMatch`, its `.rq` file is executed as a SPARQL `CONSTRUCT` against the working graph. The `WHERE` clause restates the motif's `PatternNode`/`PatternEdge` shape directly: elements connected the right way via `beam:use`/`beam:produce`, each one's `pair:playsRole` checked against the motif's expected role through `pair:subRoleOf*` (so subtypes count, not just exact matches). Example, `match_vector_ir.rq`:

   ```sparql
   ?retrievalStep
       beam:use ?query ;
       beam:use ?vectorStore ;
       beam:produce ?retrievedResult ;
       pair:playsRole ?retrievalRole .
   ?retrievalRole pair:subRoleOf* pair:RetrievalStep .

   ?query pair:playsRole ?queryRole .
   ?queryRole pair:subRoleOf* pair:UserInput .
   ```

   If the shape is found, the `CONSTRUCT` clause materializes a `pair:MotifMatch` with one `pair:NodeBinding` per slot, linking each abstract `PatternNode` to the concrete element that filled it. These new triples are merged back into the working graph, so later queries can see them.

5. **Risk finding = "motif match + extra condition."** For every implementation whose `pair:producesOutputType` is `pair:RiskFinding`, its `.rq` file runs the same way, but starts from an existing `pair:MotifMatch` and adds the condition that makes it risky. Example, `risk_prompt_injection.rq`:

   ```sparql
   ?match a pair:MotifMatch ; pair:matchesMotif ?motif ;
       pair:hasNodeBinding/pair:matchedElement ?untrustedContent .
   ?untrustedContent pair:containsDataCategory/pair:subDataCategoryOf* pair:UntrustedContent .

   ?generationStep beam:use ?llm ; beam:produce ?userFacingOutput ;
       pair:playsRole ?generationRole .
   ?generationRole pair:subRoleOf* pair:GenerationStep .

   { ?generationStep beam:use ?untrustedContent . }
   UNION
   { ?intermediateStep beam:use ?untrustedContent ; beam:produce ?derivedContext .
     ?generationStep beam:use ?derivedContext . }

   FILTER NOT EXISTS {
       pat:PromptInjectionInterpretation pair:suggestedControl ?implementedControl .
       ?implementedControl beamr:associatedTo ?generationStep .
   }
   ```

   In words: take a match whose bound element is tagged `pair:UntrustedContent`, check whether that content — directly or through one intermediate step — reaches a generation step that uses an LLM and produces user-facing output, and skip the finding entirely if a mitigating control is already represented as attached to that step (`FILTER NOT EXISTS`). What survives becomes a `pair:RiskFinding`, carrying evidence elements, the OWASP mechanism, cross-taxonomy risk entries, and suggested controls — all pulled straight from the matching `pair:MotifInterpretation` (here `pat:PromptInjectionInterpretation`) in `risk_pattern_library.ttl`.

6. **Serialize outputs** — `motif_matches`, `risk_findings`, `inferred_annotations`, and the fully merged `combined_assessment_graph` are each written out as `.ttl` files under `outputs/<usecase>/output_N/`.

In short: a **motif** is a graph shape to find, encoded once declaratively (`motif.ttl`) and executed by a matching SPARQL `CONSTRUCT` (`match_*.rq`); a **risk finding** is that shape plus a "this is bad because…" condition, executed by a second SPARQL `CONSTRUCT` (`risk_*.rq`) layered on top of the first one's output. Both stages run over the exact same working graph, which keeps growing as each stage merges its results back in.
