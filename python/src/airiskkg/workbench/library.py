from __future__ import annotations

from functools import lru_cache

from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, URIRef

from airiskkg.assessment_runner import PAIR, load_base_graph
from airiskkg.workbench.templates import motif_templates
from airiskkg.workbench.terms import (
    display_label,
    domain_of,
    label,
    risk_domains,
    short,
    source_pair,
)

_BEAMR_CONTROL = URIRef("http://w3id.org/beam/risk#RiskControl")
_PAT = "http://w3id.org/airiskkg/patterns#"
_TECHNICAL = PAIR.TechnicalControl
_NON_TECHNICAL = PAIR.NonTechnicalControl


def _text(value: object) -> str | None:
    """Curated descriptions are written as indented triple-quoted literals, and
    a reader gets them as one paragraph rather than as the source's line breaks."""
    if value is None:
        return None
    collapsed = " ".join(str(value).split())
    return collapsed or None


def _definition(graph: Graph, resource: URIRef) -> str | None:
    return _text(
        graph.value(resource, SKOS.definition)
        or graph.value(resource, DCTERMS.description)
    )


_OWN_NAMESPACES = ("http://w3id.org/airiskkg", "http://w3id.org/beam")


def _external(resource: URIRef) -> str | None:
    """The IRI, when it is a document somebody can actually open."""
    text = str(resource)
    if text.startswith(_OWN_NAMESPACES):
        return None
    return text if text.startswith(("http://", "https://")) else None


def _ref(graph: Graph, resource: URIRef) -> dict:
    full, brief = source_pair(resource)
    stated = graph.value(resource, SKOS.prefLabel) or graph.value(resource, RDFS.label)
    url = _external(resource)
    # Without this a source cited as a URL is named by its last path segment,
    # so half the motif library reported its provenance as "design_en.html".
    name = str(stated) if stated else (
        str(resource).split("//", 1)[-1].split("/", 1)[0] if url else label(graph, resource)
    )
    # A design pattern citation is minted in pat: but stands for somebody else's
    # catalogue, so its namespace is the wrong answer to "where did this come
    # from?" - reading it off the IRI would credit Fowler's patterns to PAIR-AI.
    if (resource, RDF.type, PAIR.DesignPatternCitation) in graph:
        cited = graph.value(resource, DCTERMS.source)
        if cited is not None:
            url = _external(cited) or url
            full = brief = str(cited).split("//", 1)[-1].split("/", 1)[0]
        # A DOI host says "doi.org", which reads as a peer of "martinfowler.com".
        # The venue is the answer to "where did this come from?", so prefer it.
        venue = graph.value(resource, DCTERMS.isPartOf)
        if venue is not None:
            full = brief = str(venue)
    return {
        "id": str(resource),
        "label": name,
        "definition": _definition(graph, resource),
        "source": full,
        "sourceShort": brief,
        "url": url,
    }


def _nature(graph: Graph, control: URIRef) -> str | None:
    nature = graph.value(control, PAIR.controlNature)
    if nature == _TECHNICAL:
        return "technical"
    if nature == _NON_TECHNICAL:
        return "non-technical"
    return None


def _control_ref(graph: Graph, control: URIRef) -> dict:
    ref = _ref(graph, control)
    ref["nature"] = _nature(graph, control)
    ref["realizedByMotifs"] = sorted(
        (short(motif) for motif in graph.objects(control, PAIR.realizedByMotif))
    )
    return ref


def _sorted_refs(graph: Graph, subject: URIRef, predicate: URIRef) -> list[dict]:
    refs = [_ref(graph, obj) for obj in graph.objects(subject, predicate)]
    return sorted(refs, key=lambda ref: (ref["sourceShort"], ref["label"].lower()))


def _family(graph: Graph, motif: URIRef) -> dict | None:
    """Which family of AI system this motif is a shape of, as the library shelves it."""
    family = next(iter(sorted(graph.objects(motif, PAIR.motifFamily), key=str)), None)
    if family is None:
        return None
    return {
        "id": short(family),
        "label": label(graph, family),
        "definition": _definition(graph, family),
    }


def _motif_entry(graph: Graph, motif: URIRef, template: dict | None) -> dict:
    nodes = (template or {}).get("nodes", [])
    edges = (template or {}).get("edges", [])
    roles = sorted({role for node in nodes for role in node.get("roles", [])})
    return {
        "id": short(motif),
        "iri": str(motif),
        "label": label(graph, motif),
        "description": _definition(graph, motif),
        "family": _family(graph, motif),
        "derivedFrom": _sorted_refs(graph, motif, PAIR.derivedFrom),
        "roles": [{"id": role, "label": display_label(role)} for role in roles],
        "nodes": nodes,
        "edges": edges,
        "riskPatterns": sorted(
            short(pattern) for pattern in graph.objects(motif, PAIR.hasRiskPattern)
        ),
    }


def _risk_pattern_entry(graph: Graph, pattern: URIRef, domains: set[URIRef]) -> dict:
    mechanism = graph.value(pattern, PAIR.hasMechanism)
    derived = _sorted_refs(graph, pattern, PAIR.derivedFrom)
    taxonomy: list[dict] = []
    reached: dict[str, dict] = {}
    for term in graph.objects(pattern, PAIR.mayIndicateRisk):
        ref = _ref(graph, term)
        domain = domain_of(graph, term, domains)
        ref["domain"] = label(graph, domain) if domain is not None else None
        taxonomy.append(ref)
        if domain is not None:
            reached.setdefault(short(domain), {
                "id": short(domain),
                "label": label(graph, domain),
                "definition": _definition(graph, domain),
            })
    taxonomy.sort(key=lambda ref: (ref["sourceShort"], ref["label"].lower()))
    return {
        "id": short(pattern),
        "iri": str(pattern),
        "label": label(graph, pattern),
        "description": _definition(graph, pattern),
        "derivedFrom": derived,
        "riskDomains": sorted(reached.values(), key=lambda d: d["label"].lower()),
        "mechanism": _ref(graph, mechanism) if mechanism is not None else None,
        "conditions": sorted(
            (_ref(graph, c) for c in graph.objects(pattern, PAIR.hasApplicabilityCondition)),
            key=lambda ref: ref["label"].lower(),
        ),
        "taxonomy": taxonomy,
        "controls": sorted(
            (_control_ref(graph, c) for c in graph.objects(pattern, PAIR.suggestedControl)),
            key=lambda ref: ref["label"].lower(),
        ),
        "motifs": sorted(short(motif) for motif in graph.objects(pattern, PAIR.hasMotif)),
    }


@lru_cache(maxsize=1)
def library_catalogue() -> dict:
    """What the knowledge base can recognise, read off the loaded graph."""
    graph = load_base_graph()
    templates = motif_templates()

    motifs = sorted(
        (_motif_entry(graph, motif, templates.get(short(motif)))
         for motif in set(graph.subjects(RDF.type, PAIR.GraphMotif))),
        key=lambda entry: entry["label"].lower(),
    )
    domains = risk_domains(graph)
    patterns = sorted(
        (_risk_pattern_entry(graph, pattern, domains)
         for pattern in set(graph.subjects(RDF.type, PAIR.RiskPattern))),
        key=lambda entry: entry["label"].lower(),
    )
    project_controls = {
        control
        for control in graph.subjects(RDF.type, _BEAMR_CONTROL)
        if str(control).startswith(_PAT)
    }
    return {
        "riskPatterns": patterns,
        "motifs": motifs,
        "stats": {
            "riskPatterns": len(patterns),
            "motifs": len(motifs),
            "patternRoles": len(set(graph.subjects(RDF.type, PAIR.PatternRole))),
            "dataCategories": len(set(graph.subjects(RDF.type, PAIR.DataCategory))),
            "controls": len(project_controls),
            "motifFamilies": len(
                {m["family"]["id"] for m in motifs if m["family"]}
            ),
            "riskDomains": len(
                {d["id"] for p in patterns for d in p["riskDomains"]}
            ),
            "taxonomyEntries": len(
                {entry["id"] for p in patterns for entry in p["taxonomy"]}
            ),
        },
    }
