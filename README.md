# AI Risk Knowledge Graph

This repository supports the working paper:

**A Pattern-Based Method for Design-Time AI Risk Assessment Using Knowledge Graphs Operationalization**

It contains ontology files and a small Python workspace for AI risk knowledge
graph assessment.

## Structure

```text
ontology/
  core/                     Core ontology files
  patterns/                 Risk and motif pattern definitions
    implementation/         SPARQL construct queries for patterns
  taxonomy/                 AI risk taxonomy sources and mappings
  example/                  Example ontology instance data
  queries/                  Visualization and audit queries
outputs/                    Generated assessment outputs

python/
  src/airiskkg/             Reusable Python code and CLI tools
  tests/                    Tests
  scripts/                  Helper scripts
  pyproject.toml            Python package configuration
```


## Development

Keep ontology sources in `ontology/`, grouped by core model, patterns,
taxonomies, and examples.

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

The UI provides:

- **Guided builder** — describe a system as resources and processes, choosing
  roles and data categories from the pattern vocabulary and wiring them together
  with `use` / `produce` / `inform` edges. It generates a valid architecture
  graph for you.
- **Turtle source** — load a bundled example, upload, or paste an architecture
  graph, then review and run the assessment.
- **Findings view** — motif/finding counts, an OWASP-LLM category breakdown, and
  per-finding cards showing the interpreted mechanism, cross-taxonomy risk
  entries (OWASP / MIT / IBM Risk Atlas), evidence elements, and suggested
  controls.

The UI is a thin layer over the same `airiskkg.assessment_runner` pipeline used by
the CLI; assessment logic lives in one place.
