# Third-party notices

PAIR-AI (airiskkg) is licensed **CC BY 4.0** — see [LICENSE](LICENSE). The
knowledge base references and, where noted, adapts third-party material. This
file records those attributions in one place.

Per-file attribution also appears as `dct:license` / `dct:rights` on each
ontology file's `owl:Ontology` header.

---

## IBM AI Atlas Nexus — Apache License 2.0

<https://github.com/IBM/ai-atlas-nexus>

Apache 2.0 text: [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt), as published at
<https://www.apache.org/licenses/LICENSE-2.0>.

Copyright IBM Corporation and the AI Atlas Nexus contributors.

The material derived from Nexus remains under the Apache License 2.0; PAIR-AI's own
modelling around it is CC BY 4.0. Each file below says so in its `dct:rights`.

**Changes were made.** The upstream YAML data was subset to the entries needed
for the current assessment examples, restructured into RDF, and aligned to the
PAIR-AI vocabulary.

Files derived from it:

| File | What is derived |
| --- | --- |
| `ontology/taxonomy/ibm_risk_atlas.ttl` | IBM AI Risk Atlas groups and risk entries (subset; every IBM risk the `data/mappings/` cross-walk names). The mechanisms and conditions on three entries are PAIR-AI's own |
| `ontology/taxonomy/mit_ai_risk_repo.ttl` | MIT AI Risk Repository domain taxonomy (subset) |
| `ontology/taxonomy/mit_air_risk_control.ttl` | MIT draft AI risk mitigation taxonomy + controls |
| `ontology/taxonomy/nexus_taxonomy_core.ttl` | Nexus taxonomy structure, adapted |
| `ontology/taxonomy/taxonomy_mapping.ttl` | Section 1 cross-taxonomy mappings (SSSOM sets) |
| `ontology/taxonomy/owasp_llm.ttl` | `nexus:tag` entry identifiers only |
| `ontology/taxonomy/taxonomy_mapping.ttl` (Section 1) | ASI <-> OWASP LLM rows (`owasp_asi2owasp_llm.tsv`) and Atlas <-> NIST rows (`ibm2nistgenai.tsv`) |

Apache 2.0 covers IBM's packaging, not the rights in the third-party content Nexus
redistributes. Of that content, the MIT material is attributed under its own licence
below; OWASP, NIST and Eticas have sections of their own.

Apache 2.0 §4(d) asks for the contents of an upstream `NOTICE` file to be carried
along. The Nexus repository ships none (checked 2026-11-10: no `NOTICE` at its root),
so there is nothing further to propagate.

## MIT AI Risk Initiative — CC BY 4.0

Verified 2026-11-10: "Data from the MIT AI Risk Initiative is licensed under CC BY 4.0"
(<https://airisk.mit.edu/>, site footer), and the paper is published under CC BY 4.0.

> Slattery, P., Saeri, A. K., Grundy, E. A. C., Graham, J., Noetel, M., Uuk, R.,
> Dao, J., Pour, S., Casper, S., & Thompson, N. (2026). The AI risk repository: A
> meta-review, database, and taxonomy of risks from artificial intelligence.
> *Patterns*, Article 101517. <https://doi.org/10.1016/j.patter.2026.101517>
>
> MIT AI Risk Initiative. (2025, July 28). *Mapping AI risk mitigations: Evidence
> scan & draft mitigation taxonomy*.
> <https://airisk.mit.edu/blog/mapping-ai-risk-mitigations>

CC BY 4.0, the same licence as this repository. The material reached this project
through IBM AI Atlas Nexus, above.

| File | What is reproduced |
| --- | --- |
| `ontology/taxonomy/mit_ai_risk_repo.ttl` | The domain taxonomy (subset), aligned to the PAIR-AI vocabulary |
| `ontology/taxonomy/mit_air_risk_control.ttl` | The draft mitigation taxonomy's categories and sub-categories, unchanged; the concrete controls under them are PAIR-AI's |
| `ontology/taxonomy/mit_mitigation_action.ttl` | The 52 mitigation action ids and names the PAIR-AI cross-walk cites |
| `data/mappings/Final_Mapped_Taxonomy_Table_Output.csv` | The same action ids and names, in the cross-walk they were mapped in |

**Changes were made.** The material was subset, restructured into RDF and aligned to
the PAIR-AI vocabulary. The mitigation sub-category page does not name a licence of its
own, so the site-wide data licence above is the one relied on.

## OWASP Top 10 for LLM Applications 2025 — CC BY-SA 4.0

OWASP GenAI Security Project. (2024). *OWASP Top 10 for LLM Applications 2025*
(Version 2025). <https://genai.owasp.org/>

CC BY-SA 4.0: <https://creativecommons.org/licenses/by-sa/4.0/>

**Referenced, not adapted.** `ontology/taxonomy/owasp_llm.ttl` reuses only entry
identifiers, numbering, and links to the official entry pages — facts and short
names, not protected expression. Every `skos:definition` in that file, and every
`pair:RiskMechanism` and risk condition attached to an OWASP entry in
`ontology/patterns/risk_mechanisms.ttl`, is written for PAIR-AI's structural model.
A risk pattern cites its OWASP entry by `pair:derivedFrom`, shown as "anchored to"
under References, never as its source.

**Checked against the source text, 2026-11-10.** Every sentence of the repository
(RDF literals, Turtle comments, documentation and interface text, 8,136 in all) was
compared with OWASP's own text: the ten LLM 2025 entries from the project's GitHub
repository and the Agentic Top 10 2026 publication with its two public drafts. The
measures were the longest shared word run, 4-gram overlap, and similarity to the
closest OWASP sentence. Eleven definitions and one mechanism that followed OWASP's
opening sentences were rewritten. Afterwards no definition or mechanism shares more
than a publication title with OWASP's text (longest run 7 words, the title), and none
is closer than 0.31 to any OWASP sentence.

This distinction matters: CC BY-SA's ShareAlike term binds *adaptations*, and
this repository is CC BY 4.0. **Anyone extending the OWASP taxonomy files must
reference OWASP rather than reproduce its prose** — copying their descriptions,
mitigation lists, or attack scenarios would pull ShareAlike onto the file and
conflict with the repository licence.

## OWASP Top 10 for Agentic Applications 2026 — CC BY-SA 4.0

OWASP GenAI Security Project. (2025). *OWASP Top 10 for Agentic Applications
2026* (Version 2026). <https://genai.owasp.org/>

**Referenced, not adapted**, on the same terms as the LLM Top 10 above.
`ontology/taxonomy/owasp_asi.ttl` reuses the ten entry identifiers, numbering and
links. Its definitions, mechanisms and conditions are written for PAIR-AI, and
ASI10 is catalogued without a risk pattern. The ASI ↔ LLM mappings come from IBM
AI Atlas Nexus above.

## Eticas AI Risk Taxonomy — CC BY 4.0

Eticas. (n.d.). *Eticas AI risk taxonomy*. <https://taxonomy.eticas.ai/>

Licensed CC BY 4.0, the same licence as this repository.

| File | What is derived |
| --- | --- |
| `data/eticas.ttl` | The taxonomy as published, kept as source data |
| `ontology/taxonomy/eticas_risk.ttl` | Generated from it by `python/scripts/generate_eticas_layer.py` |

**Changes were made.** Concept IRIs, labels and definitions are unchanged. Eticas's
published mappings are kept only where the target is a concept this knowledge base
declares, or a DPV term. Its own handles for other catalogues are translated to
this knowledge base's IRIs where they name exactly one concept, and dropped
otherwise. `skos:broadMatch` and `skos:narrowMatch` rows are dropped because they
read opposite to SKOS. The generated file's header counts every dropped row by
reason.

## Zhang et al. (2022) — risks in AI/ML systems

> Zhang, X., Chan, F. T. S., Yan, C., & Bose, I. (2022). Towards risk-aware
> artificial intelligence and machine learning systems: An overview. *Decision
> Support Systems, 159*, Article 113800.
> <https://doi.org/10.1016/j.dss.2022.113800>

© Elsevier. **Referenced, not adapted.** `ontology/taxonomy/ml_risk.ttl` reuses
the paper's risk category names and their arrangement (its Figure 1). Every
definition, mechanism and condition in that file is written for PAIR-AI, as are
the roles that cite the paper (`FairnessEvaluationStep`, `InputDomainCheckStep`,
`UncertaintyEstimate`).

## NIST AI 600-1 — U.S. government work, no copyright

National Institute of Standards and Technology. (2024). *Artificial intelligence
risk management framework: Generative artificial intelligence profile*
(NIST AI 600-1). <https://doi.org/10.6028/NIST.AI.600-1>

Works of the U.S. federal government are not subject to domestic copyright
protection (17 U.S.C. §105), so unlike the OWASP material there is no ShareAlike
constraint here. `ontology/taxonomy/nist_genai.ttl` uses the profile's category
identifiers and short names; the definitions in that file are PAIR-AI summaries,
not NIST text. The Atlas ↔ NIST mappings come from IBM AI Atlas Nexus above.

## sBPMN 2.0 — CC BY 4.0

The business-context layer reads process models expressed in the sBPMN ontology,
an OWL formalization of the BPMN 2.0 core constructs.

> Krause, F., Paulheim, H., Vázquez, A., & Espert, A. (2025). sBPMN: A framework
> for capturing business process semantics in dynamic knowledge graphs.
> *Proceedings of the 13th Knowledge Capture Conference (K-CAP '25)*.
> <https://doi.org/10.1145/3731443.3771361>

| File | What is derived |
| --- | --- |
| `external/sbpmn/sbpmn_2.0.ttl` | The published ontology, vendored unchanged from <https://sbpmn.github.io/2.0/ontology.ttl> |

Licensed CC BY 4.0 — the same licence as this repository, so it may be vendored,
extended and redistributed with attribution. PAIR-AI adds no terms to it and
modifies no file in `external/sbpmn/`; the bridge vocabulary that connects a BPMN
activity to a BEAM system is this project's own, in `ontology/context/`.

## Sources cited by the motif and role libraries

These are cited as `dct:source` / `pair:derivedFrom` provenance on motifs, risk
patterns, and pattern roles. Their terms have **not** been verified; do not copy
their prose into the ontology.

| Source | Used for |
| --- | --- |
| mercari, *ML System Design Patterns* — <https://mercari.github.io/ml-system-design-pattern/> | ML serving, training, and lifecycle motifs |
| Liu, Y., Lo, S. K., Lu, Q., et al. (2025). Agent design pattern catalogue. *The Journal of Systems & Software, 220*, 112278 — <https://doi.org/10.1016/j.jss.2024.112278> | Agentic, guardrail, evaluation and RAG motifs |
| Gao, Y., Xiong, Y., Gao, X., et al. (2023). Retrieval-augmented generation for large language models: A survey. arXiv — <https://doi.org/10.48550/arXiv.2312.10997> | RAG, retrieval, embedding, reranking and hybrid-retrieval motifs |
| Ma, X., Gong, Y., He, P., Zhao, H., & Duan, N. (2023). Query rewriting for retrieval-augmented large language models. arXiv — <https://doi.org/10.48550/arXiv.2305.14283> | Query rewriting motif |
| Wei, J., Bosma, M., Zhao, V. Y., et al. (2021). Finetuned language models are zero-shot learners. arXiv — <https://doi.org/10.48550/arXiv.2109.01652> | Prompted generation and fine-tuning motifs (the paradigms its Figure 2 compares) |
| van Bekkum et al. (2021), Boxology / Tool4Boxology | BEAM element and flow vocabulary |
| W3C Data Privacy Vocabulary (DPV, DPV-AI) — <https://w3id.org/dpv> | Referenced concepts, never copied (glossary rule) |
| AIRO — <https://w3id.org/airo> | Risk control alignment |

`external/tool4boxology/` vendors upstream schema and sample data; see that
directory and `docs/claude/CLAUDE.md` for its stated terms.

---

*If you add a third-party source, record it here and on the consuming file's
`owl:Ontology` header. Never attribute a definition to a document it did not
come from.*
