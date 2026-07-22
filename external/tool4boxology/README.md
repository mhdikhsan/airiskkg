# Vendored Tool4Boxology schema and sample export

Files in this directory are vendored from the Tool4Boxology repository
(https://github.com/SDM-TIB/Tool4Boxology) as the input side of the PAIR-AI
Tool4Boxology alignment adapter (`ontology/alignments/tool4boxology_alignment.ttl`,
`python/scripts/normalize_t4b.py`).

| File | Origin | Note |
| --- | --- | --- |
| `Tool4BoxologyOntology.ttl` | `Ontology/Tool4BoxologyOntology.ttl` | Tool4Boxology export vocabulary (t4b: = `http://tool4boxology.org/`), fetched 2026-07-13 |
| `easy-ai-schema.ttl` | `Ontology/easy-ai-schema.ttl` | easy-ai schema both Tool4Boxology and BEAM anchor to (`https://kastle-lab.org/easy-ai2/`), fetched 2026-07-13 |
| `sample_export.nt` | trimmed from `KG/Tool4BoxologyKG.nt` | one complete Boxology instance (T4B-1) with its design-pattern groupings and components; preserves the export's data-quality quirks (lowercase type URIs, `hasProcess`) for round-trip testing |

## License

Tool4Boxology is dual-licensed: **CC BY 4.0** (diagrams, documentation,
educational assets) and **Apache 2.0** (included third-party or extended
modules). These vendored copies are redistributed under those terms,
unmodified except for the trimming of `sample_export.nt`.

## Citation (APA 7th)

Bendler, J. E., et al. (2026). Tool4Boxology: A semantic toolbox for
constructing and analysing neuro-symbolic architectures. In *The Semantic Web —
ESWC 2026* (pp. 191–211). Springer. https://doi.org/10.1007/978-3-032-25159-6_11

## Known upstream quirks (handled by the normalizer)

- The export types many instances with **lowercase class URIs** (`t4b:data`,
  `t4b:transform`, `t4b:training`, ...) while the ontology declares
  `t4b:Data`, `t4b:Transform`, `t4b:Train`, ...
- The ontology declares `t4b:patternProcess`, but the export uses
  **`t4b:hasProcess`** — the adapter targets the export URIs.
- The export uses `t4b:StatisticModel`; the ontology declares
  `t4b:StatisticalModel`.
- The export uses `t4b:Time%20Series`; the ontology declares `t4b:TimeSeries`.
- Instances are multi-typed with `t4b:Component` plus a specific class.
- `Tool4BoxologyOntology.ttl` as published does not parse as Turtle: the
  `dc:description` in the ontology header is a single-quoted string spanning
  multiple lines. The vendored copy contains a **minimal syntax patch**
  (converted to a `"""..."""` string); no other content was changed.
  Report upstream together with the `patternProcess`/`hasProcess` mismatch.
