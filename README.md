# AI Risk Knowledge Graph

This repository supports the working paper:

**A Pattern-Based Method for Design-Time AI Risk Assessment Using Knowledge Graphs Operationalization**

It contains ontology files and a small Python workspace for AI risk knowledge
graph assessment.

## Structure

Three kinds of thing live here, kept apart on purpose: **knowledge** (the
ontology), **contracts** (SHACL shapes), and **code** (the Python package that
executes them).

```text
ontology/                   KNOWLEDGE - the reusable AI risk knowledge base
  core/                     BEAM vocabulary + the PAIR-AI pattern meta-vocabulary
  patterns/                 Motif library, risk pattern library, control layer
    implementation/         Executable SPARQL: one CONSTRUCT per motif / risk pattern
  facets/                   SKOS characterization facets (task, context, autonomy, data)
  taxonomy/                 External risk taxonomies + the cross-taxonomy mappings
  alignments/               Adapters for external vocabularies (Tool4Boxology, DPV)
  example/                  Architecture graphs used as worked examples and fixtures
  queries/                  Standalone SPARQL for humans (visualization, audit)

shacl/                      CONTRACTS - what a graph must satisfy
  architecture_input_contract.ttl   Accepted input graphs
  assessment_output_contract.ttl    Emitted findings

python/                     CODE - the pipeline that runs the knowledge base
  src/airiskkg/             Package: assessment runner, views, importers, webapp
  scripts/                  Standalone maintenance and export utilities
  tests/                    Test suite
  pyproject.toml            Package configuration (installable from python/)

external/                   Vendored third-party sources (see NOTICE.md)
outputs/                    Generated assessment runs (not knowledge; untracked)
v1/                         Frozen prior generation - reference only, do not edit
```

Two details worth knowing before editing:

- **`ontology/patterns/implementation/*.rq` paths are data.** Each query is
  registered by a `pair:PatternImplementation` whose `pair:implementationPath`
  is a literal string. Moving or renaming one of those files means updating its
  declaration too; `test_library_consistency.py` fails if the two drift apart.
  `ontology/queries/` holds the opposite kind of query: standalone, run by hand,
  referenced by no declaration.
- **The Python package root is `python/`, not the repository root.** Install with
  `pip install -e .` from inside `python/`. Paths back to the knowledge base are
  resolved at runtime by `airiskkg.paths`, which walks up until it finds both
  `ontology/` and `python/`.

## Development

Keep ontology sources in `ontology/`, grouped by core model, patterns, facets,
taxonomies, alignments, and examples. After any ontology change: parse every
`.ttl` with RDFLib, run the SHACL shapes, and re-run the assessment on the
bundled examples, explaining any diff in findings.

## Method Flow

The reusable AI Risk KB is split into risk taxonomies, architecture motifs,
and curated motif interpretations. Assessment runs in two executable steps:

1. Match reusable motifs against an input architecture graph.
2. Apply curated interpretation conditions to materialize candidate risk findings.

The SPARQL CONSTRUCT files in `ontology/patterns/implementation/` are executable
implementations of motifs or motif interpretations. 


## Web UI

A Flask-based web UI makes it easier for developers to run an assessment without
hand-writing Turtle or reading raw TTL output.

```bash
cd python
pip install -e ".[web]"
airiskkg serve            # then open http://127.0.0.1:5000
```

The editor and the diagram are two views of the same graph and stay in sync both
ways: type Turtle on the left and the diagram redraws; drag, connect, or rename on
the right and the Turtle updates.

- **Open graph** — load a bundled example, paste Turtle, or upload a file. A
  Tool4Boxology / t4b-beam export is detected by content and normalized to BEAM
  automatically, since such exports carry structure in their own vocabulary.
- **Draw and annotate** — drag BEAM symbols onto the canvas, connect them with
  `use` / `produce` / `inform`, and tag each element with roles and data
  categories. Roles are grouped by family and narrowed to the ones that fit the
  selected element. **Annotation is what makes a graph matchable**: structure
  alone says what shape a system is, roles say what each part means.
- **Motif catalogue** — instantiate any motif as pre-wired, pre-annotated
  elements, either to scaffold a system or to add a control a finding suggested.
- **Findings** — per-finding cards with the risk mechanism, cross-taxonomy
  entries (OWASP LLM / OWASP Agentic / IBM Atlas / MIT / NIST), evidence
  elements, and suggested controls. Selecting a finding highlights its evidence.
- **Motifs** — which motifs matched, and for the near misses, exactly which
  pattern node or edge is missing. That last part matters: without it, an
  under-annotated graph simply matches nothing and gives no clue why.

Every output is a **candidate** risk — a structural disposition, never a
confirmed failure.

The UI is a thin layer over the same `airiskkg.assessment_runner` pipeline used by
the CLI; assessment logic lives in one place.
