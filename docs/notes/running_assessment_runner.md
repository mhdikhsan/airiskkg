# Running the PAIR-AI Assessment (assessment_runner.py)

`python/src/airiskkg/assessment_runner.py` loads the ontology, matches
architectural motifs against an input architecture graph, and interprets those
matches into candidate risk findings. It's driven through the `airiskkg` CLI
(`python/src/airiskkg/cli.py`).

## Setup

From the repo root, using the project's `.venv`:

```bash
# create the venv once, if it doesn't exist
python -m venv .venv

# install the package (editable) plus dev extras
.venv/Scripts/python.exe -m pip install -e "python[dev]"
```

On Windows, invoke the venv's Python/console scripts directly
(`.venv/Scripts/python.exe`, `.venv/Scripts/airiskkg.exe`) rather than
`source .venv/bin/activate`, which doesn't exist on Windows venvs.

## Run an assessment

An architecture graph is always required — there's no implicit default
example anymore.

```bash
# assess a specific architecture graph
.venv/Scripts/airiskkg.exe assess ontology/example/uc6.ttl

# assess with a custom output base directory
.venv/Scripts/airiskkg.exe assess ontology/example/uc6.ttl --output-dir outputs/uc6_assessment

# assess multiple architecture graphs at once
.venv/Scripts/airiskkg.exe assess ontology/example/uc6.ttl ontology/example/verba_goldenverba.ttl
```

This prints a summary (motif match count, risk finding count, and each
finding's evidence), then the output directory it wrote to. Every run gets its
own auto-numbered subdirectory (`output_1`, `output_2`, ...) under the output
base (default `outputs/`, created automatically if missing) so repeated runs
never clobber a previous run's results:

```text
outputs/
  output_1/
    inferred_annotations.ttl
    motif_matches.ttl
    risk_findings.ttl
    combined_assessment_graph.ttl
  output_2/
    ...
```

- `inferred_annotations.ttl` — `pair:containsDataCategory` facts the runner inferred (see [Data-category propagation](#data-category-propagation)), not asserted in your input graph
- `motif_matches.ttl` — architectural motif matches (`pair:MotifMatch`)
- `risk_findings.ttl` — candidate risk findings (`pair:RiskFinding`)
- `combined_assessment_graph.ttl` — the full working graph (ontology + input + generated matches/findings)

## What gets loaded

`load_assessment_graph()` builds the working graph in this order:

1. Core ontology: `ontology/core/beam_core.ttl`, `beam_core_risk.ttl`, `imports.ttl`, `pair_ai_pattern.ttl`
2. Pattern library: `ontology/patterns/motif.ttl`, `ontology/patterns/risk_pattern_library.ttl`
3. All taxonomy files in `ontology/taxonomy/*.ttl`
4. The architecture graph(s) you pass in — required, no default

Motif-matching and risk-interpretation queries are not hardcoded — they're
discovered from the graph itself. Any `pair:PatternImplementation` individual
in `risk_pattern_library.ttl` that declares `pair:producesOutputType` and
`pair:implementationPath` gets executed as a SPARQL `CONSTRUCT` query against
the working graph, in this order:

1. **Data-category propagation** (`pair:DataCategoryPropagation` output type) — runs first, see below.
2. **Motif-matching** (`pair:MotifMatch` output type) — results are merged back into the graph.
3. **Risk-interpretation** (`pair:RiskFinding` output type) — can depend on motif matches and propagated data categories already being present.

## Data-category propagation

Risk queries like `risk_prompt_injection.rq` only fire for elements explicitly
tagged `pair:containsDataCategory pair:UntrustedContent` (or a
`pair:subDataCategoryOf*` subcategory). Requiring every architect to manually
re-tag every derived element is fragile — forget one tag on a node three hops
downstream and the finding silently never fires, with no signal anything was
missed.

`ontology/patterns/implementation/propagate_untrusted_content.rq` closes that
gap by inferring untrusted-content taint instead of requiring it to be
hand-asserted everywhere:

- **Roots (untrusted by default, no tag needed):** anything playing a role
  `subRoleOf* pair:PublicUserInput` or `subRoleOf* pair:RetrievedContext` —
  the classic adversarial-input and retrieval-injection vectors.
- **Propagation:** taint flows along `beam:use`/`beam:produce` edges — if a
  step consumes untrusted input, whatever it produces is untrusted too.
- **Trust-clearing:** propagation stops at a step playing a role
  `subRoleOf* pair:GuardrailStep` (input or output guardrail), or at any
  element explicitly tagged `pair:containsDataCategory pair:TrustedContent`
  (the override).

`assessment_runner._propagate_data_categories()` runs registered
`pair:DataCategoryPropagation` queries to a fixed point (each pass can surface
new elements the next pass depends on) before motif matching and risk
interpretation run, so downstream queries see the same graph whether taint was
asserted by hand or inferred. Inferred triples are also merged into
`combined_assessment_graph.ttl`, but kept separately queryable via
`result.inferred_annotations` / `inferred_annotations.ttl` so you can tell
what you asserted from what the tool inferred.

This only covers taint that's structurally derivable from roles and data
flow. Content that's risky for reasons a label reveals but the graph shape
doesn't (e.g. a plain `beam:Data` node labeled "internal HR records") still
needs a human or an LLM-assisted authoring step to tag it — propagation isn't
a substitute for that, just for the mechanical "I forgot to re-tag the
tenth node in the chain" failure mode.

## Run the test suite

```bash
.venv/Scripts/python.exe -m pytest python/tests -q
```

## Programmatic use

```python
from airiskkg.assessment_runner import run_assessment, print_assessment_summary

result = run_assessment("ontology/example/uc6.ttl", write_outputs=False)
print_assessment_summary(result)

result.motif_match_count      # int
result.risk_finding_count     # int
result.motif_matches          # rdflib.Graph of pair:MotifMatch triples
result.risk_findings          # rdflib.Graph of pair:RiskFinding triples
result.combined_graph         # rdflib.Graph, everything merged together
result.inferred_annotations   # rdflib.Graph of inferred pair:containsDataCategory triples
result.output_dir             # Path to the auto-numbered output_N dir, or None if write_outputs=False
```

## Known gaps to be aware of

- **`uc6_onlim.ttl` no longer exists.** It was renamed/superseded by
  `ontology/example/uc6.ttl` (namespace changed from `uc6-onlim#` to `uc6#`).
  The old file is only kept under `old/uc6_onlim.ttl` for reference and isn't
  wired into the CLI or tests.
- **Motif library coverage is partial for uc6.** `match_direct_prompting.rq`
  (the only implemented "generation" motif) requires a raw `pair:UserInput`
  feeding directly into a `beam:Infer` step. UC6's actual generation step
  (`uc6:LLMPrompting`) is a `beam:Transform` fed by retrieved context and a
  system prompt, so it never matches. As a result,
  `risk_system_prompt_leakage.rq` and `risk_improper_output_handling.rq`
  currently produce 0 findings for uc6 — not a bug, just a motif that hasn't
  been authored yet (something like a "RAG generation" motif).
- **`verba_goldenverba.ttl` has an unrelated pre-existing role gap.**
  `test_verba_external_model_produces_supply_chain_finding` currently fails —
  worth investigating separately if you're relying on that example.
