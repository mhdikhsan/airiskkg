# AI Risk Knowledge Graph

This repository supports the working paper:

**A Pattern-Based Method for Design-Time AI Risk Assessment Using Knowledge Graphs Operationalization**

It contains ontology files and a small Python workspace for AI risk knowledge
graph analysis, preprocessing, and experimentation.

## Structure

```text
ontology/
  core/                     Core ontology files
  patterns/                 Risk and motif pattern definitions
    implementation/         SPARQL construct queries for patterns
  taxonomy/                 AI risk taxonomy sources and mappings
  example/                  Example ontology instance data

python/
  src/airiskkg/             Reusable Python code and CLI tools
  tests/                    Tests
  notebooks/                Exploratory notebooks
  scripts/                  Helper scripts
  configs/                  Configuration examples
  pyproject.toml            Python package configuration
```


## Development

Keep exploratory Python work in `python/notebooks/`. Move reusable code into
`python/src/airiskkg/` when it becomes useful across notebooks or scripts.

Keep ontology sources in `ontology/`, grouped by core model, patterns,
taxonomies, and examples.
