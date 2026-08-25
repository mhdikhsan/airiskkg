from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, RDFS, Graph, URIRef

from airiskkg.assessment_runner import BEAM, PAIR, load_base_graph
from airiskkg.workbench.process_view import DATA_CLASSES
from airiskkg.workbench.templates import motif_template_list
from airiskkg.workbench.terms import (
    EDGE_KINDS,
    PROCESS_CLASSES,
    RESOURCE_CLASSES,
    class_terms,
    display_label,
    label,
)


def vocab_terms(graph: Graph, rdf_class: URIRef) -> list[dict[str, str]]:
    terms = [
        {"id": str(subject), "label": display_label(label(graph, subject))}
        for subject in graph.subjects(RDF.type, rdf_class)
    ]
    return sorted(terms, key=lambda item: item["label"].lower())


def top_level_role(graph: Graph, role: URIRef) -> URIRef | None:
    tops: set[URIRef] = set()
    seen: set[URIRef] = {role}
    queue: list[URIRef] = [role]
    while queue:
        node = queue.pop()
        parents = [p for p in graph.objects(node, PAIR.subRoleOf) if isinstance(p, URIRef)]
        if not parents:
            tops.add(node)  # genuinely top-level: no parent at all
            continue
        for parent in parents:
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)
    return sorted(tops, key=str)[0] if tops else None


def role_applicability(graph: Graph) -> dict[URIRef, str]:
    evidence: dict[URIRef, set[str]] = {}
    for pattern_node in graph.subjects(RDF.type, PAIR.PatternNode):
        role = graph.value(pattern_node, PAIR.expectedRole)
        cls = graph.value(pattern_node, PAIR.expectedClass)
        if role is None or cls is None:
            continue
        supers = set(graph.transitive_objects(cls, RDFS.subClassOf)) | {cls}
        if BEAM.Process in supers:
            kind = "process"
        elif BEAM.Resource in supers:
            kind = "resource"
        else:
            continue
        family = top_level_role(graph, role)
        if family is not None:
            evidence.setdefault(family, set()).add(kind)

    # a family counts as classified only when its evidence is unanimous
    family_kind = {family: next(iter(kinds)) for family, kinds in evidence.items() if len(kinds) == 1}

    applies: dict[URIRef, str] = {}
    for role in graph.subjects(RDF.type, PAIR.PatternRole):
        family = top_level_role(graph, role)
        kind = family_kind.get(family)
        if kind:
            applies[role] = kind
    return applies


def role_vocab_terms(graph: Graph) -> list[dict[str, str]]:
    applies = role_applicability(graph)
    terms = []
    for subject in graph.subjects(RDF.type, PAIR.PatternRole):
        top = top_level_role(graph, subject)
        term = {"id": str(subject), "label": display_label(label(graph, subject))}
        if top is not None:
            term["group"] = display_label(label(graph, top))
        if subject in applies:
            term["applies"] = applies[subject]
        terms.append(term)
    return sorted(terms, key=lambda item: item["label"].lower())


@lru_cache(maxsize=1)
def vocabulary() -> dict:
    graph = load_base_graph()
    return {
        "roles": role_vocab_terms(graph),
        "dataCategories": vocab_terms(graph, PAIR.DataCategory),
        "resourceClasses": class_terms(RESOURCE_CLASSES),
        "processClasses": class_terms(PROCESS_CLASSES),
        "edgeKinds": EDGE_KINDS,
        "motifTemplates": motif_template_list(),
        # What a business analyst may say about a data object. Sourced from the
        # route that writes it, so the picker cannot offer a term the server
        # would reject.
        "dataClasses": [
            {"id": name, "label": label} for name, label in DATA_CLASSES.items()
        ],
    }
