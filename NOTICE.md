# Third-party notices

PAIR-AI (airiskkg) is licensed **CC BY 4.0** — see [LICENSE](LICENSE). The
knowledge base references and, where noted, adapts third-party material. This
file records those attributions in one place.

Per-file attribution also appears as `dct:license` / `dct:rights` on each
ontology file's `owl:Ontology` header.

---

## IBM AI Atlas Nexus — Apache License 2.0

<https://github.com/IBM/ai-atlas-nexus>

Apache 2.0 text: <https://www.apache.org/licenses/LICENSE-2.0>

Copyright IBM Corporation and the AI Atlas Nexus contributors.

**Changes were made.** The upstream YAML data was subset to the entries needed
for the current assessment examples, restructured into RDF, and aligned to the
PAIR-AI vocabulary.

Files derived from it:

| File | What is derived |
| --- | --- |
| `ontology/taxonomy/ibm_risk_atlas.ttl` | IBM AI Risk Atlas groups and risk entries (subset) |
| `ontology/taxonomy/mit_ai_risk_repo.ttl` | MIT AI Risk Repository domain taxonomy (subset) |
| `ontology/taxonomy/mit_air_risk_control.ttl` | MIT draft AI risk mitigation taxonomy + controls |
| `ontology/taxonomy/nexus_taxonomy_core.ttl` | Nexus taxonomy structure, adapted |
| `ontology/taxonomy/taxonomy_mapping.ttl` | Section 1 cross-taxonomy mappings (SSSOM sets) |
| `ontology/taxonomy/owasp_llm.ttl` | `nexus:tag` entry identifiers only |
| `ontology/taxonomy/taxonomy_mapping.ttl` (Section 1) | ASI <-> OWASP LLM rows (`owasp_asi2owasp_llm.tsv`) and Atlas <-> NIST rows (`ibm2nistgenai.tsv`) |

> **Open item.** Apache 2.0 covers IBM's packaging, not upstream rights in
> third-party content Nexus itself redistributes. The MIT AI Risk Repository and
> the MIT draft mitigation taxonomy are third-party works whose own terms have
> not been verified — and `mit_air_risk_control.ttl` reproduces the MIT
> RiskControlGroup layer verbatim. Verify MIT's terms before publication.
>
> Apache 2.0 §4(d) also requires propagating the contents of any upstream
> `NOTICE` file. Check whether the Nexus repository ships one; if it does, its
> attribution notices belong in this file.

## OWASP Top 10 for LLM Applications 2025 — CC BY-SA 4.0

OWASP GenAI Security Project. (2024). *OWASP Top 10 for LLM Applications 2025*
(Version 2025). <https://genai.owasp.org/>

CC BY-SA 4.0: <https://creativecommons.org/licenses/by-sa/4.0/>

**Referenced, not adapted.** `ontology/taxonomy/owasp_llm.ttl` reuses only entry
identifiers, numbering, and links to the official entry pages — facts and short
names, not protected expression. Every `skos:definition`, `pair:RiskMechanism`,
and risk condition in that file is written from scratch for PAIR-AI's structural
model.

This distinction matters: CC BY-SA's ShareAlike term binds *adaptations*, and
this repository is CC BY 4.0. **Anyone extending the OWASP taxonomy files must
reference OWASP rather than reproduce its prose** — copying their descriptions,
mitigation lists, or attack scenarios would pull ShareAlike onto the file and
conflict with the repository licence.

## NIST AI 600-1 — U.S. government work, no copyright

National Institute of Standards and Technology. (2024). *Artificial intelligence
risk management framework: Generative artificial intelligence profile*
(NIST AI 600-1). <https://doi.org/10.6028/NIST.AI.600-1>

Works of the U.S. federal government are not subject to domestic copyright
protection (17 U.S.C. §105), so unlike the OWASP material there is no ShareAlike
constraint here. `ontology/taxonomy/nist_genai.ttl` uses the profile's category
identifiers and short names; the definitions in that file are PAIR-AI summaries,
not NIST text. The Atlas ↔ NIST mappings come from IBM AI Atlas Nexus above.

## Sources cited by the motif and role libraries

These are cited as `dct:source` / `pair:derivedFrom` provenance on motifs, risk
patterns, and pattern roles. Their terms have **not** been verified; do not copy
their prose into the ontology.

| Source | Used for |
| --- | --- |
| Martin Fowler, *Emerging patterns in building GenAI products* — <https://martinfowler.com/articles/gen-ai-patterns/> | GenAI motifs and roles |
| mercari, *ML System Design Patterns* — <https://mercari.github.io/ml-system-design-pattern/> | ML serving, training, and lifecycle motifs |
| van Bekkum et al. (2021), Boxology / Tool4Boxology | BEAM element and flow vocabulary |
| W3C Data Privacy Vocabulary (DPV, DPV-AI) — <https://w3id.org/dpv> | Referenced concepts, never copied (glossary rule) |
| AIRO — <https://w3id.org/airo> | Risk control alignment |

`external/tool4boxology/` vendors upstream schema and sample data; see that
directory and `docs/claude/CLAUDE.md` for its stated terms.

---

*If you add a third-party source, record it here and on the consuming file's
`owl:Ontology` header. Never attribute a definition to a document it did not
come from.*
