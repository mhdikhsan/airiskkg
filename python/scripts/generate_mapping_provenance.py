from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rdflib import Graph, SKOS, URIRef  # noqa: E402

from airiskkg.paths import CORE_DIR, PATTERNS_DIR, TAXONOMY_DIR  # noqa: E402

SOURCE = TAXONOMY_DIR / "taxonomy_mapping.ttl"
TARGET = TAXONOMY_DIR / "provenance" / "mapping_provenance.ttl"

NEXUS_TSV = (
    "https://github.com/IBM/ai-atlas-nexus/blob/main/src/ai_atlas_nexus/data/mappings/"
)

BLOCKS = [
    {
        "start": "## Atlas <-> OWASP",
        "set": "nexus-ibm2owasp",
        "label": "IBM Atlas to OWASP LLM Top 10 (Nexus)",
        "justification": "ManualMappingCuration",
        "confidence": "0.95",
        "tsv": "ibm2owasp.tsv",
        "date": None,
        "curator": "upstream",
    },
    {
        "start": "## Atlas <-> MIT AI Risk Repository",
        "set": "nexus-ibm2mit",
        "label": "IBM Atlas to MIT AI Risk Repository (Nexus)",
        "justification": "ManualMappingCuration",
        "confidence": "0.95",
        "tsv": "mit-ai-risk-repository_ibm-risk-atlas.tsv",
        "date": None,
        "curator": "upstream",
    },
    {
        "start": "## OWASP Agentic Top 10 (ASI) <-> OWASP LLM Top 10",
        "set": "nexus-asi2owasp",
        "label": "OWASP ASI to OWASP LLM Top 10 (Nexus)",
        "justification": "ManualMappingCuration",
        # Per-row confidences are stated in the block header; recorded individually below.
        "confidence": None,
        "tsv": "owasp_asi2owasp_llm.tsv",
        "date": "2026-04-28",
        "curator": "upstream",
    },
    {
        "start": "## IBM Atlas <-> NIST AI RMF",
        "set": "nexus-ibm2nist",
        "label": "IBM Atlas to NIST AI 600-1 (Nexus)",
        "justification": "ManualMappingCuration",
        "confidence": "0.95",
        "tsv": "ibm2nistgenai.tsv",
        "date": "2025-01-29",
        "curator": "upstream",
    },
    {
        "start": "# Section 2",
        "set": "pair-ai-curation",
        "label": "PAIR-AI project curation",
        "justification": "ManualMappingCuration",
        "confidence": None,
        "tsv": None,
        "date": None,
        "curator": "pair-ai",
    },
    {
        "start": "# Section 3",
        "set": "pair-ai-risk-to-control-embedding",
        "label": "OWASP risk to MIT control family, embedding-derived",
        "justification": "SemanticSimilarityThresholdMatching",
        "confidence": None,
        "tsv": None,
        "date": "2026-07-17",
        "curator": "pair-ai",
        "validated": False,
        "except_subjects": ("llm07-", "llm08-", "llm10-"),
        "source_note": (
            "PAIR-AI risk-to-mitigation CSV, "
            "data/mappings/Final_Mapped_Taxonomy_Table_Output.csv "
            "(OWASP -> IBM Atlas -> MIT-action embedding mapping; 93 rows, 7 "
            "OWASP risks, 30 IBM risks, 52 MIT actions), applied 2026-07-17. "
            "Method per its own reference doc: embedding-matched, cosine top-3, "
            "UNVALIDATED - reproducible but not adjudicated. Rollup: each risk's "
            "mapped actions collected to their MIT sub-categories, mapped 1:1 to "
            "mitctrl:*, with three approximations (2.2 Model Alignment -> "
            "model-safety-engineering; 4.4 Governance Disclosure -> "
            "risk-disclosure; 4.5 Third-Party System Access -> "
            "access-management). Covers LLM01-06 and LLM09 only; LLM07/08/10 "
            "keep prior curation. Defects carried from the source: action A0973 "
            "sits in sub-category 2.3 but is tagged Category 3 (does not affect "
            "the rollup, which keys on Sub_category); OWASP ids embed the year "
            "inline (llm022025-) unlike the ontology; 19 of the 30 referenced "
            "IBM risks are not declared in this project."
        ),
    },
    {
        "start": "## IBM Atlas risk -> control",
        "set": "unrecorded-risk-to-control",
        "label": "Atlas and MIT risk to control family, provenance unrecorded",
        "justification": "UnspecifiedMatching",
        "confidence": None,
        "tsv": None,
        "date": None,
        "curator": "unrecorded",
        "validated": False,
    },
]

# Subjects excluded from the embedding-derived block keep their prior curation.
CURATED_FALLBACK = {
    "set": "pair-ai-risk-to-control-curated",
    "label": "OWASP risk to MIT control family, prior project curation",
    "justification": "ManualMappingCuration",
    "confidence": None,
    "tsv": None,
    "date": None,
    "curator": "pair-ai",
    "validated": True,
}

ELSEWHERE = {
    "set": "pair-ai-vocabulary-alignment",
    "label": "Alignments declared inline in a vocabulary file",
    "justification": "ManualMappingCuration",
    "confidence": None,
    "tsv": None,
    "date": None,
    "curator": "pair-ai",
    "validated": True,
}

CONTROL_BRIDGE = {
    "set": "pair-ai-control-bridge",
    "label": "PAIR-AI control catalogue to MIT mitigation family (indicative)",
    "justification": "ManualMappingCuration",
    "confidence": None,
    "tsv": None,
    "date": None,
    "curator": "pair-ai",
    "validated": False,
}

VOCABULARY_ALIGNMENT = {
    "set": "beam-external-vocabulary-alignment",
    "label": "BEAM/PAIR-AI vocabulary alignment to Boxology, DPV and AIRO",
    "justification": "ManualMappingCuration",
    "confidence": None,
    "tsv": None,
    "date": None,
    "curator": "pair-ai",
    "validated": True,
}

# Per-row confidences stated in the ASI block header.
ROW_CONFIDENCE = {
    ("asi02-tool-misuse", "llm06-excessive-agency"): "0.90",
    ("asi06-memory-and-context-poisoning", "llm04-data-and-model-poisoning"): "0.85",
    ("asi06-memory-and-context-poisoning", "llm01-prompt-injection"): "0.75",
    ("asi06-memory-and-context-poisoning", "llm08-vector-and-embedding-weaknesses"): "0.75",
}

HAS_RELATED_CONTROL = URIRef("http://w3id.org/airiskkg/taxonomy/nexus#hasRelatedControl")

MAPPING_PREDICATES = (
    SKOS.exactMatch,
    SKOS.closeMatch,
    SKOS.broadMatch,
    SKOS.narrowMatch,
    SKOS.relatedMatch,
    HAS_RELATED_CONTROL,
)


def _prefixes(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.startswith("@prefix"))


def _split_into_blocks(text: str) -> list[tuple[dict, str]]:
    """Attribute every line of the mapping file to the block it falls under."""
    lines = text.splitlines()
    starts = []
    for block in BLOCKS:
        for index, line in enumerate(lines):
            if line.startswith(block["start"]):
                starts.append((index, block))
                break
        else:  # pragma: no cover - a renamed header must not fail silently
            raise SystemExit(f"Block header not found, generator is stale: {block['start']}")
    starts.sort()
    out = []
    for position, (index, block) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        out.append((block, "\n".join(lines[index:end])))
    return out


def _local(term) -> str:
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _curie(term, namespaces: dict[str, str]) -> str:
    for prefix, uri in namespaces.items():
        if str(term).startswith(uri):
            return f"{prefix}:{str(term)[len(uri) :]}"
    return f"<{term}>"


_ATLAS_NS = "http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#"
_OWASP_NS = "http://w3id.org/airiskkg/taxonomy/owasp-llm#"
_MIT_NS = "http://w3id.org/airiskkg/taxonomy/mit-ai-risk#"


def _chain_corroboration(records) -> dict:
    atlas_to_owasp: dict = {}
    atlas_to_mit: dict = {}
    curated_pairs = []

    for subject, _predicate, obj, block, _confidence in records:
        subject_str, object_str = str(subject), str(obj)
        ends = {subject_str, object_str}
        upstream = block["set"] != "pair-ai-curation"

        def other(ns: str):
            return subject if object_str.startswith(ns) else obj

        if upstream and any(e.startswith(_ATLAS_NS) for e in ends):
            if any(e.startswith(_OWASP_NS) for e in ends):
                anchor = subject if subject_str.startswith(_ATLAS_NS) else obj
                atlas_to_owasp.setdefault(anchor, set()).add(other(_ATLAS_NS))
            elif any(e.startswith(_MIT_NS) for e in ends):
                anchor = subject if subject_str.startswith(_ATLAS_NS) else obj
                atlas_to_mit.setdefault(anchor, set()).add(other(_ATLAS_NS))

        if not upstream and {_OWASP_NS, _MIT_NS} <= {
            _OWASP_NS if e.startswith(_OWASP_NS) else _MIT_NS if e.startswith(_MIT_NS) else ""
            for e in ends
        }:
            curated_pairs.append((subject, obj))

    result: dict = {}
    for subject, obj in curated_pairs:
        owasp_end = subject if str(subject).startswith(_OWASP_NS) else obj
        mit_end = obj if str(obj).startswith(_MIT_NS) else subject
        shared = sorted(
            (
                anchor
                for anchor in set(atlas_to_owasp) & set(atlas_to_mit)
                if owasp_end in atlas_to_owasp[anchor] and mit_end in atlas_to_mit[anchor]
            ),
            key=str,
        )
        result[(subject, obj)] = shared
    return result


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    target = Path(argv[0]) if argv else TARGET

    text = SOURCE.read_text(encoding="utf-8")
    header = _prefixes(text)

    namespaces: dict[str, str] = {}
    for prefix, uri in re.findall(r"@prefix\s+(\w+):\s+<([^>]+)>", header):
        namespaces[prefix] = uri

    records = []
    for block, body in _split_into_blocks(text):
        graph = Graph()
        graph.parse(data=header + "\n" + body, format="turtle")
        for predicate in MAPPING_PREDICATES:
            for subject, _, obj in graph.triples((None, predicate, None)):
                effective = block
                excluded = block.get("except_subjects", ())
                if any(_local(subject).startswith(p) for p in excluded):
                    effective = CURATED_FALLBACK
                confidence = effective["confidence"] or ROW_CONFIDENCE.get(
                    (_local(subject), _local(obj))
                )
                records.append((subject, predicate, obj, effective, confidence))

    already = {(s, p, o) for s, p, o, _, _ in records}
    for directory, block in (
        (TAXONOMY_DIR, ELSEWHERE),
        (PATTERNS_DIR, CONTROL_BRIDGE),
        (CORE_DIR, VOCABULARY_ALIGNMENT),
    ):
        for path in sorted(directory.glob("*.ttl")):
            if path == SOURCE:
                continue
            graph = Graph()
            graph.parse(path)
            for predicate in MAPPING_PREDICATES:
                for subject, _, obj in graph.triples((None, predicate, None)):
                    if (subject, predicate, obj) not in already:
                        already.add((subject, predicate, obj))
                        records.append((subject, predicate, obj, block, None))

    records.sort(key=lambda r: (r[3]["set"], str(r[0]), str(r[1]), str(r[2])))

    lines = [
        "# GENERATED FILE - do not edit by hand.",
        "# Regenerate with: python python/scripts/generate_mapping_provenance.py",
        "# Source of truth is ontology/taxonomy/taxonomy_mapping.ttl; this file lifts",
        "# the provenance stated in that file's section comments into queryable form.",
        "#",
        "# Deliberately NOT in ontology/taxonomy/ itself. The assessment runner globs",
        "# that directory non-recursively, so living one level down keeps this layer",
        "# out of the graph the pipeline reasons over: it is evidence about the",
        "# knowledge base, not knowledge the assessment may act on. A test enforces it.",
        "",
        header,
        "@prefix sssom:  <https://w3id.org/sssom/> .",
        "@prefix semapv: <https://w3id.org/semapv/vocab/> .",
        "@prefix prov:   <http://www.w3.org/ns/prov#> .",
        "@prefix pairm:  <http://w3id.org/airiskkg/taxonomy/mappings/provenance#> .",
        "",
    ]

    seen_sets = []
    for block in [*BLOCKS, CURATED_FALLBACK, ELSEWHERE, CONTROL_BRIDGE, VOCABULARY_ALIGNMENT]:
        if block["set"] in seen_sets:
            continue
        seen_sets.append(block["set"])
        lines.append(f"pairm:{block['set']} a sssom:MappingSet ;")
        lines.append(f'    rdfs:label "{block["label"]}"@en ;')
        if block["tsv"]:
            lines.append(f"    dct:source <{NEXUS_TSV}{block['tsv']}> ;")
        if block.get("source_note"):
            lines.append(f'    dct:source "{block["source_note"]}"@en ;')
        if block.get("validated") is False:
            lines.append(
                '    dct:description "NOT validated. These links were produced '
                "without human adjudication of each row; treat as a baseline "
                'pending review, not as curated correspondences."@en ;'
            )
        elif block["curator"] == "upstream":
            lines.append(
                '    dct:description "Adopted verbatim from the upstream SSSOM set. '
                'Predicates and directions are reproduced as curated there, not '
                're-derived here."@en ;'
            )
        else:
            lines.append(
                '    dct:description "Curated by this project because no upstream '
                'SSSOM row exists. Each mapping carries a stated rationale in the '
                'source file; no measured confidence is claimed."@en ;'
            )
        lines.append(f"    sssom:mapping_tool \"{block['curator']}\" .")
        lines.append("")

    corroboration = _chain_corroboration(records)

    for index, (subject, predicate, obj, block, confidence) in enumerate(records, start=1):
        lines.append(f"pairm:mapping-{index:03d} a sssom:Mapping ;")
        lines.append(f"    sssom:subject_id {_curie(subject, namespaces)} ;")
        lines.append(f"    sssom:predicate_id {_curie(predicate, namespaces)} ;")
        lines.append(f"    sssom:object_id {_curie(obj, namespaces)} ;")
        lines.append(f"    sssom:mapping_justification semapv:{block['justification']} ;")
        if confidence:
            lines.append(f"    sssom:confidence {confidence} ;")
        if block["date"]:
            lines.append(f'    sssom:mapping_date "{block["date"]}"^^xsd:date ;')
        via = corroboration.get((subject, obj))
        if via is not None:
            lines.append(f"    pairm:chainCorroborated {'true' if via else 'false'} ;")
            for anchor in via:
                lines.append(f"    pairm:corroboratedVia {_curie(anchor, namespaces)} ;")
        lines.append(f"    prov:wasDerivedFrom pairm:{block['set']} .")
        lines.append("")

    lines.insert(
        lines.index(header) + 1,
        "@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .",
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"{target.name}: {len(records)} mappings across {len(seen_sets)} sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
