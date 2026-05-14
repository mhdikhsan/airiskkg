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
