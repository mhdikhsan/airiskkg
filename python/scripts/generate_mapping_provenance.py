"""Generate the queryable provenance layer for the cross-taxonomy mappings.

Today a mapping's provenance lives in a section comment in taxonomy_mapping.ttl.
A human reading the file can see that Section 1 came from an upstream SSSOM set
and Section 2 is project curation, but nothing can *query* it: "show me only the
manually curated mappings" has no answer, and neither does "which mappings rest
on our own authority rather than someone else's". For a method whose credibility
depends on how its alignments were produced, that distinction should be data.

This script reads the mapping file block by block and emits one SSSOM-style
reified mapping per triple, carrying the justification, confidence, date and
upstream set that the surrounding comment already states in prose. Nothing new
is asserted - it lifts what is written there into a form a query can reach.

Generated rather than hand-written for two reasons: 83 reified mappings are
tedious and error-prone by hand, and a generator can be re-run, which lets a
test prove the provenance still matches the mappings it describes. Provenance
that silently drifts from what it documents is worse than none.

Why semapv:ManualMappingCuration is used for upstream rows: the curation was
manual, it was simply performed by IBM rather than by us. The distinction that
matters for trust is recorded separately, in the mapping set each row belongs
to, so "curated by someone else and adopted verbatim" stays visible.

Usage:  python python/scripts/generate_mapping_provenance.py
"""

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

# Each block of the mapping file, keyed by the line where it starts. Values are
# taken from the block's own comment header - this table restates them in a form
# the generator can attach to individual mappings.
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
        # Deliberately unset: no measured confidence exists for these. Asserting a
        # number we never computed would be exactly the false precision this layer
        # is meant to expose.
        "confidence": None,
        "tsv": None,
        "date": None,
        "curator": "pair-ai",
    },
    {
        "start": "# Section 3",
        "set": "pair-ai-risk-to-control-embedding",
        "label": "OWASP risk to MIT control family, embedding-derived",
        # The block header states these plainly: "the underlying risk->action
        # edges are embedding-matched (cosine top-3, unvalidated)". Recording
        # them as manual curation would be false; SEMAPV has a term for exactly
        # this and using it is the whole point of the layer. LLM07/08/10 are
        # absent from that CSV and are split out below.
        "justification": "SemanticSimilarityThresholdMatching",
        "confidence": None,
        "tsv": None,
        "date": "2026-07-17",
        "curator": "pair-ai",
        "validated": False,
        "except_subjects": ("llm07-", "llm08-", "llm10-"),
        # The source CSV is now in the tree, so these stopped being assertions
        # and became reproducible: test_section_3_control_links_reproduce_from_
        # the_csv recomputes the rollup and diffs it both ways. Still the weakest
        # block in the knowledge base - reproducible is not the same as
        # validated, and nobody has adjudicated the underlying cosine matches.
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
        # Neither subsection states how these were produced, and inferring a
        # method from the surrounding text would manufacture the confidence this
        # layer exists to prevent. semapv:UnspecifiedMatching is the honest
        # value: it makes the gap queryable instead of letting the links pass as
        # curated. These are the largest single group in the file.
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

# Mappings written directly into a vocabulary file rather than the mapping file.
# Hand-authored alignments in hand-authored files, so the justification is
# accurate rather than assumed.
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

# pat:Control_* -> mitctrl:* in risk_pattern_library.ttl. The file already states
# the provenance exactly: "an INDICATIVE bridge ... not audited SSSOM mappings -
# they are PAIR-AI curation and carry no upstream provenance". Recording it as
# such is the whole job; validated=False carries the "indicative, not audited"
# part, which no justification term expresses on its own.
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

# Role and class alignments to external vocabularies (Tool4Boxology, DPV, AIRO,
# dpv-ai) declared in the core pattern vocabulary. Hand-authored alignments in a
# hand-authored file. Note the direction convention: BEAM specializes the
# published Boxology, so these are closeMatch rather than exactMatch.
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

# Risk -> control grounding is covered alongside the SKOS mappings because it is
# assertion of the same kind - a claim that two concepts correspond - and it is
# the larger and weaker-provenanced half. Leaving it out would let the layer
# report only on the part that was already in good shape. The reverse
# nexus:mitigatesRiskTaxonomyEntry links are inverses of these and are skipped
# rather than counted twice.
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


def main() -> int:
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

    # Mappings are also written directly into vocabulary files rather than into
    # the mapping file, and NOT only under ontology/taxonomy/. Sweeping every
    # directory that can hold one is the difference between a coverage guarantee
    # and a coverage guarantee over the directory we happened to look in - the
    # first version of this script swept taxonomy/ alone and silently missed 80
    # mappings in patterns/ and core/, while its coverage test still passed.
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
        lines.append(f"    prov:wasDerivedFrom pairm:{block['set']} .")
        lines.append("")

    lines.insert(
        lines.index(header) + 1,
        "@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .",
    )

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(lines), encoding="utf-8")
    print(f"{TARGET.relative_to(TARGET.parents[3])}: {len(records)} mappings across {len(seen_sets)} sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
