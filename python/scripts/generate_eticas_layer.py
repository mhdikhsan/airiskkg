"""Write ontology/taxonomy/eticas_risk.ttl from the Eticas AI Risk Taxonomy in data/eticas.ttl.

Eticas publishes its own handles for most catalogues it maps to. A mapping is kept
only where that handle names one concept this knowledge base declares; the rest are
counted in the output header, never guessed at.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rdflib import DCTERMS, RDF, SKOS, Graph, Literal, Namespace, URIRef  # noqa: E402

from airiskkg.paths import REPO_ROOT  # noqa: E402

SOURCE = REPO_ROOT / "data" / "eticas.ttl"
TARGET = REPO_ROOT / "ontology" / "taxonomy" / "eticas_risk.ttl"
TAXONOMY_DIR = REPO_ROOT / "ontology" / "taxonomy"

ETICAS = "https://taxonomy.eticas.ai/risk/"
ETICAS_ONT = Namespace("https://taxonomy.eticas.ai/ontology/")
EXT = "https://taxonomy.eticas.ai/external/"
MIT_SOURCE = "https://airisk.mit.edu/domain/"

MIT = "http://w3id.org/airiskkg/taxonomy/mit-ai-risk#"
ATLAS = "http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#"
NIST = "http://w3id.org/airiskkg/taxonomy/nist-genai#"
NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")

MAPPING_PREDICATES = (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch, SKOS.narrowMatch, SKOS.relatedMatch)

# Eticas writes these the other way round from SKOS ("data-poisoning narrowMatch MIT 2.2"
# means poisoning is the narrower one), and not uniformly. Reproducing them would assert
# the opposite of what was meant; inverting them would be re-deriving someone else's work.
DIRECTIONAL = (SKOS.broadMatch, SKOS.narrowMatch)

# Eticas labels subdomain-4.2 with the name MIT gives 4.3, so neither reading can be trusted.
MIT_DEFECTS = {"subdomain-4.2"}

# Eticas's NIST AI 600-1 handles, by number and by name, to the category each names.
# "dangerous-content" bundles three categories and is left out.
NIST_HANDLES = {
    "2": "confabulation",
    "4": "data-privacy",
    "7": "human-ai-configuration",
    "8": "information-integrity",
    "9": "information-security",
    "confabulation": "confabulation",
    "data-privacy": "data-privacy",
    "environmental": "environmental-impacts",
    "harmful-bias": "harmful-bias-and-homogenization",
    "harmful-bias-homogenization": "harmful-bias-and-homogenization",
    "information-integrity": "information-integrity",
    "information-security": "information-security",
    "value-chain": "value-chain-and-component-integration",
}

# External vocabularies kept exactly as Eticas publishes them, because they resolve.
PASSTHROUGH = ("https://w3id.org/dpv/ai#", "https://w3id.org/dpv/legal/eu/aiact#")


def _local_taxonomy() -> Graph:
    graph = Graph()
    for path in sorted(TAXONOMY_DIR.glob("*.ttl")):
        if path == TARGET:
            continue
        graph.parse(path)
    return graph


def _translate(target: str, declared: set[str]) -> tuple[str | None, str]:
    """The concept a published handle names here, or None and the reason it was dropped."""
    if target.startswith(PASSTHROUGH):
        return target, ""
    if target.startswith(MIT_SOURCE):
        name = target[len(MIT_SOURCE):]
        if name in MIT_DEFECTS:
            return None, "MIT id and label disagree"
        local = MIT + name.replace(".", "-")
        return (local, "") if local in declared else (None, "MIT concept not modelled")
    if target.startswith(EXT + "nist-ai-600-1/"):
        name = NIST_HANDLES.get(target.rsplit("/", 1)[-1])
        return (NIST + name, "") if name else (None, "NIST handle bundles several categories")
    if target.startswith(EXT + "ibm-risk-atlas/"):
        local = ATLAS + target.rsplit("/", 1)[-1]
        return (local, "") if local in declared else (None, "IBM handle names no Atlas entry declared here")
    if target.startswith(EXT + "oecd-ai/"):
        return None, "OECD is absorbed, not represented"
    if target.startswith(EXT):
        return None, "Eticas-minted handle for " + target[len(EXT):].split("/", 1)[0]
    return None, "unrecognised vocabulary"


def _lit(value: Literal) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    lang = f"@{value.language}" if value.language else ""
    return f'"{text}"{lang}'


def _curie(term: str) -> str:
    for prefix, uri in (("eticas", ETICAS), ("mit", MIT), ("atlas", ATLAS), ("nist", NIST),
                        ("dpvai", "https://w3id.org/dpv/ai#"), ("aiact", "https://w3id.org/dpv/legal/eu/aiact#")):
        if term.startswith(uri) and all(c.isalnum() or c in "-_" for c in term[len(uri):]):
            return f"{prefix}:{term[len(uri):]}"
    return f"<{term}>"


def main() -> int:
    source = Graph()
    source.parse(SOURCE)
    local = _local_taxonomy()
    declared = {str(s) for s in local.subjects(SKOS.prefLabel, None)}
    claimed_exactly = {str(o) for o in local.objects(None, SKOS.exactMatch)}

    scheme = next(source.subjects(RDF.type, SKOS.ConceptScheme))
    concepts = sorted(c for c in source.subjects(RDF.type, SKOS.Concept) if str(c).startswith(ETICAS))

    kept: dict[tuple[str, str], set[URIRef]] = defaultdict(set)
    dropped: dict[str, int] = defaultdict(int)
    for concept in concepts:
        for predicate in MAPPING_PREDICATES:
            for target in source.objects(concept, predicate):
                local, reason = _translate(str(target), declared)
                if local is not None and predicate in DIRECTIONAL:
                    local, reason = None, "broadMatch or narrowMatch written opposite to SKOS"
                if local is None:
                    dropped[reason] += 1
                else:
                    kept[(str(concept), local)].add(predicate)
    # Two handles can land on one concept with different predicates; neither is then the published claim.
    conflicts = {pair for pair, preds in kept.items() if len(preds) > 1}
    for pair in conflicts:
        dropped["two handles give two predicates for one concept"] += len(kept.pop(pair))
    # An exactMatch to a concept another entry already matches exactly would make the two identical.
    exact_claims: dict[str, set[str]] = defaultdict(set)
    for (concept, local), preds in kept.items():
        if SKOS.exactMatch in preds:
            exact_claims[local].add(concept)
    for local, concepts_claiming in exact_claims.items():
        if local in claimed_exactly or len(concepts_claiming) > 1:
            for concept in concepts_claiming:
                kept.pop((concept, local))
                dropped["exactMatch would make two catalogues' entries identical"] += 1

    by_concept: dict[str, list[tuple[URIRef, str]]] = defaultdict(list)
    for (concept, local), preds in kept.items():
        by_concept[concept].append((next(iter(preds)), local))

    has_children = {str(o) for o in source.objects(None, SKOS.broader)}
    lines = [
        "# GENERATED FILE - do not edit by hand.",
        "# Regenerate with: python python/scripts/generate_eticas_layer.py",
        "# Source: data/eticas.ttl, the Eticas AI Risk Taxonomy as published.",
        "",
        "@prefix eticas:    <https://taxonomy.eticas.ai/risk/> .",
        "@prefix eticasont: <https://taxonomy.eticas.ai/ontology/> .",
        "@prefix mit:       <http://w3id.org/airiskkg/taxonomy/mit-ai-risk#> .",
        "@prefix atlas:     <http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#> .",
        "@prefix nist:      <http://w3id.org/airiskkg/taxonomy/nist-genai#> .",
        "@prefix dpvai:     <https://w3id.org/dpv/ai#> .",
        "@prefix aiact:     <https://w3id.org/dpv/legal/eu/aiact#> .",
        "@prefix nexus:     <http://w3id.org/airiskkg/taxonomy/nexus#> .",
        "@prefix skos:      <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix dct:       <http://purl.org/dc/terms/> .",
        "@prefix owl:       <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs:      <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
        "<http://w3id.org/airiskkg/taxonomy/eticas#> a owl:Ontology ;",
        '    rdfs:label "Eticas AI Risk Taxonomy for AI Risk KG" ;',
        '    dct:title "Eticas AI Risk Taxonomy for AI Risk KG" ;',
        '    dct:description """',
        "    The Eticas AI Risk Taxonomy, reproduced with its concept IRIs, labels and",
        "    definitions unchanged. It is a cross-walk: Eticas maps its own entries to the",
        "    MIT AI Risk Repository, IBM AI Risk Atlas, NIST AI 600-1, DPV-AI, the EU AI Act",
        "    and others, which is what makes it useful here.",
        "",
        "    A published mapping is kept only where its target is a concept this knowledge",
        "    base declares, or a DPV term, which resolves. Eticas names most catalogues by",
        "    handles of its own, several of which bundle two or three entries into one; those",
        "    have no single referent here and are left out rather than split by guesswork.",
        "    Its broadMatch and narrowMatch rows read opposite to SKOS (data-poisoning",
        "    narrowMatch MIT 2.2 means poisoning is the narrower one), and not uniformly, so",
        "    they are neither reproduced nor inverted.",
        f"    Kept: {sum(len(v) for v in by_concept.values())}. Left out, by reason:",
        *[f"      {reason}: {count}" for reason, count in sorted(dropped.items())],
        "",
        "    skos:narrower is omitted as the inverse of the skos:broader kept here.",
        "    Entries with children are typed nexus:RiskGroup and the rest nexus:Risk, so",
        "    the taxonomy reads the same way as the other catalogues in this directory.",
        '    """ ;',
        "    dct:license <https://creativecommons.org/licenses/by/4.0/> ;",
        '    dct:rights "Eticas AI Risk Taxonomy, published by Eticas under CC BY 4.0. Changes were made: '
        'the published mappings were filtered to targets this knowledge base declares, external handles '
        'were translated to this knowledge base\'s IRIs, and skos:narrower was dropped as redundant."@en ;',
        '    dct:bibliographicCitation "Eticas. (n.d.). Eticas AI risk taxonomy. https://taxonomy.eticas.ai/"@en ;',
        f"    dct:source <{scheme}> .",
        "",
        f"<{scheme}> a nexus:RiskTaxonomy, skos:ConceptScheme ;",
    ]
    for p in (SKOS.prefLabel, DCTERMS.description, DCTERMS.publisher):
        for value in source.objects(scheme, p):
            lines.append(f"    {_curie_pred(p)} {_lit(value)} ;")
    lines[-1] = lines[-1][:-2] + " ."
    lines.append("")

    for concept in concepts:
        c = str(concept)
        kind = "nexus:RiskGroup" if c in has_children else "nexus:Risk"
        lines.append(f"{_curie(c)} a {kind} ;")
        body = []
        for p in (SKOS.prefLabel, SKOS.altLabel, SKOS.definition, SKOS.note):
            for value in sorted(source.objects(concept, p)):
                body.append(f"    {_curie_pred(p)} {_lit(value)}")
        for parent in sorted(source.objects(concept, SKOS.broader)):
            body.append(f"    skos:broader {_curie(str(parent))}")
            body.append(f"    nexus:isPartOf {_curie(str(parent))}")
        if (concept, SKOS.topConceptOf, None) in source:
            body.append(f"    skos:topConceptOf <{scheme}>")
        body.append(f"    skos:inScheme <{scheme}>")
        body.append(f"    nexus:isDefinedByTaxonomy <{scheme}>")
        for p in (ETICAS_ONT.scope, ETICAS_ONT.maturity, ETICAS_ONT.perspective, ETICAS_ONT.lifecycleStage, DCTERMS.source):
            for value in sorted(source.objects(concept, p)):
                body.append(f"    {_curie_pred(p)} {_lit(value) if isinstance(value, Literal) else _curie(str(value))}")
        for predicate, local in sorted(by_concept.get(c, []), key=lambda x: (str(x[0]), x[1])):
            body.append(f"    {_curie_pred(predicate)} {_curie(local)}")
        lines.append(" ;\n".join(body) + " .")
        lines.append("")

    TARGET.write_text("\n".join(lines), encoding="utf-8")
    print(f"{TARGET.name}: {len(concepts)} concepts, {sum(len(v) for v in by_concept.values())} mappings kept")
    return 0


def _curie_pred(p: URIRef) -> str:
    s = str(p)
    for prefix, uri in (("skos", str(SKOS)), ("dct", str(DCTERMS)), ("eticasont", str(ETICAS_ONT))):
        if s.startswith(uri):
            return f"{prefix}:{s[len(uri):]}"
    return f"<{s}>"


if __name__ == "__main__":
    raise SystemExit(main())
