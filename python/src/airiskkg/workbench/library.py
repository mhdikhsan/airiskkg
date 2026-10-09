from __future__ import annotations

from functools import lru_cache

from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, URIRef

from airiskkg.assessment_runner import PAIR, load_base_graph
from airiskkg.workbench.risk_context import link_context
from airiskkg.workbench.templates import motif_templates
from airiskkg.workbench.terms import (
    display_label,
    domain_of,
    label,
    risk_domains,
    short,
    source_pair,
)
from airiskkg.workbench.vocabulary import (
    annotatable_under,
    role_reach,
    role_shelf,
)

_MAPPING_PREDICATES = (
    SKOS.exactMatch,
    SKOS.closeMatch,
    SKOS.broadMatch,
    SKOS.narrowMatch,
    SKOS.relatedMatch,
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


def _doi(resource: URIRef) -> str | None:
    """`10.1016/j.jss.2024.112278`, when the source is a DOI handle."""
    host, _, rest = str(resource).partition("doi.org/")
    return rest if rest and host in ("https://", "http://", "https://dx.", "http://dx.") else None


def _ref(graph: Graph, resource: URIRef) -> dict:
    full, brief = source_pair(resource)
    stated = graph.value(resource, SKOS.prefLabel) or graph.value(resource, RDFS.label)
    url = _external(resource)
    name = str(stated) if stated else (
        str(resource).split("//", 1)[-1].split("/", 1)[0] if url else label(graph, resource)
    )
    doi = None
    if (resource, RDF.type, PAIR.DesignPatternCitation) in graph:
        cited = graph.value(resource, DCTERMS.source)
        if cited is not None:
            url = _external(cited) or url
            full = brief = str(cited).split("//", 1)[-1].split("/", 1)[0]
            doi = _doi(cited)
            if doi:
                full, brief = str(cited), doi
    ref = {
        "id": str(resource),
        "label": name,
        "definition": _definition(graph, resource),
        "source": full,
        "sourceShort": brief,
        "url": url,
    }
    if doi:
        ref["doi"] = doi
    return ref


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


def _evidence_rank(ref: dict) -> int:
    """A paper with a DOI is the most checkable source, then a published
    catalogue or article, then a taxonomy entry the shape was inferred from."""
    if ref.get("doi"):
        return 0
    return 1 if ref.get("url") else 2


def _sorted_refs(graph: Graph, subject: URIRef, predicate: URIRef) -> list[dict]:
    refs = [_ref(graph, obj) for obj in graph.objects(subject, predicate)]
    return sorted(
        refs, key=lambda ref: (_evidence_rank(ref), ref["sourceShort"], ref["label"].lower())
    )


def _shelf(graph: Graph, motif: URIRef, predicate: URIRef) -> dict | None:
    concept = next(iter(sorted(graph.objects(motif, predicate), key=str)), None)
    if concept is None:
        return None
    return {
        "id": short(concept),
        "label": label(graph, concept),
        "definition": _definition(graph, concept),
    }


def _family(graph: Graph, motif: URIRef) -> dict | None:
    """Which family of AI system this motif is a shape of, as the library shelves it."""
    return _shelf(graph, motif, PAIR.motifFamily)


def _group(graph: Graph, motif: URIRef) -> dict | None:
    """The related motifs it is filed with inside its family."""
    return _shelf(graph, motif, PAIR.motifGroup)


def _has_control_step(graph: Graph, motif: URIRef) -> bool:
    """A structure that contains a control step exists to clear risk patterns,
    so the library presents it by the controls it realizes rather than by risk."""
    for node in graph.objects(motif, PAIR.hasPatternNode):
        role = graph.value(node, PAIR.expectedRole)
        if role is not None and (
            role == PAIR.ControlStep
            or PAIR.ControlStep in set(graph.transitive_objects(role, PAIR.subRoleOf))
        ):
            return True
    return False


def _realized_controls(graph: Graph, motif: URIRef) -> list[dict]:
    controls = []
    for control in graph.subjects(PAIR.realizedByMotif, motif):
        ref = _control_ref(graph, control)
        ref["suggestedBy"] = sorted(
            short(pattern) for pattern in graph.subjects(PAIR.suggestedControl, control)
        )
        controls.append(ref)
    return sorted(controls, key=lambda ref: ref["label"].lower())


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
        "group": _group(graph, motif),
        "derivedFrom": _sorted_refs(graph, motif, PAIR.derivedFrom),
        "roles": [{"id": role, "label": display_label(role)} for role in roles],
        "nodes": nodes,
        "edges": edges,
        "riskPatterns": sorted(
            short(pattern) for pattern in graph.objects(motif, PAIR.hasRiskPattern)
        ),
        "control": _has_control_step(graph, motif),
        "controls": _realized_controls(graph, motif),
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
        "family": _shelf(graph, pattern, PAIR.riskPatternFamily),
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
        # Empty where the motif raises the risk pattern by itself.
        "motifContext": {
            short(motif): (link_context(short(pattern), short(motif)) or {}).get("says", [])
            for motif in graph.objects(pattern, PAIR.hasMotif)
        },
    }


def _provenance(graph: Graph, role: URIRef) -> dict:
    """Where a role came from, by R6's three routes, naming which one answered.

    A role introduced to refine another is grounded by the role it specializes,
    so the chain is walked rather than reported as absent.
    """
    own = [_ref(graph, s) for s in graph.objects(role, DCTERMS.source) if isinstance(s, URIRef)]
    mapped = [
        _ref(graph, target)
        for predicate in _MAPPING_PREDICATES
        for target in graph.objects(role, predicate)
        if isinstance(target, URIRef)
    ]
    if own or mapped:
        return {"route": "stated" if own else "mapped", "refs": own + mapped, "via": None}

    seen = {role}
    queue = [p for p in graph.objects(role, PAIR.subRoleOf) if isinstance(p, URIRef)]
    while queue:
        parent = queue.pop(0)
        if parent in seen:
            continue
        seen.add(parent)
        inherited = _provenance(graph, parent)
        if inherited["refs"]:
            return {
                "route": "inherited",
                "refs": inherited["refs"],
                "via": {"id": short(parent), "label": display_label(label(graph, parent))},
            }
        queue.extend(p for p in graph.objects(parent, PAIR.subRoleOf) if isinstance(p, URIRef))
    return {"route": None, "refs": [], "via": None}


def _role_entry(graph: Graph, role: URIRef, shelf: URIRef | None, reach: dict) -> dict:
    return {
        "id": short(role),
        "iri": str(role),
        "label": display_label(label(graph, role)),
        "definition": _definition(graph, role),
        "shelf": label(graph, shelf) if shelf is not None else None,
        "shelfId": str(shelf) if shelf is not None else None,
        "appliesTo": annotatable_under(graph, shelf) if shelf is not None else [],
        "refines": sorted(
            (
                {"id": short(parent), "label": display_label(label(graph, parent))}
                for parent in graph.objects(role, PAIR.subRoleOf)
                if isinstance(parent, URIRef)
            ),
            key=lambda ref: ref["label"].lower(),
        ),
        "provenance": _provenance(graph, role),
        "motifs": reach.get("motifs", []),
        "serves": reach.get("serves", []),
        "families": reach.get("families", []),
        "riskPatterns": reach.get("riskPatterns", []),
        "controlFor": reach.get("controlFor", []),
    }


def _vocabulary_section(graph: Graph) -> dict:
    """The annotation vocabulary, shelved by the BEAM class a term goes on.

    The shelf answers the question a reader has first - can this term go on this
    element at all - which the role hierarchy's four top-level terms cannot:
    half of them sit under one.
    """
    shelves = role_shelf(graph)
    reach = role_reach(graph)
    roles = sorted(
        (
            _role_entry(graph, role, shelves.get(role), reach.get(role, {}))
            for role in set(graph.subjects(RDF.type, PAIR.PatternRole))
        ),
        key=lambda entry: entry["label"].lower(),
    )
    categories = sorted(
        (
            {
                "id": short(category),
                "iri": str(category),
                "label": display_label(label(graph, category)),
                "definition": _definition(graph, category),
                "derived": True,
            }
            for category in set(graph.subjects(RDF.type, PAIR.DataCategory))
        ),
        key=lambda entry: entry["label"].lower(),
    )
    return {"roles": roles, "dataCategories": categories}


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
    vocabulary = _vocabulary_section(graph)
    return {
        "riskPatterns": patterns,
        "motifs": motifs,
        "vocabulary": vocabulary,
        "stats": {
            "riskPatterns": len(patterns),
            "motifs": len(motifs),
            "patternRoles": len(vocabulary["roles"]),
            "dataCategories": len(vocabulary["dataCategories"]),
            "roleShelves": len({r["shelf"] for r in vocabulary["roles"] if r["shelf"]}),
            "controls": len(project_controls),
            "motifFamilies": len(
                {m["family"]["id"] for m in motifs if m["family"]}
            ),
            "motifGroups": len(
                {m["group"]["id"] for m in motifs if m["group"]}
            ),
            "riskDomains": len(
                {d["id"] for p in patterns for d in p["riskDomains"]}
            ),
            "taxonomyEntries": len(
                {entry["id"] for p in patterns for entry in p["taxonomy"]}
            ),
        },
    }
