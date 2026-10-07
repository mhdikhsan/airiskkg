from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, RDFS, SKOS, Graph, URIRef

from airiskkg.assessment_runner import BEAM, PAIR, load_base_graph
from airiskkg.workbench.process_view import data_classifications
from airiskkg.workbench.templates import motif_template_list
from airiskkg.workbench.terms import (
    EDGE_KINDS,
    PROCESS_CLASSES,
    RESOURCE_CLASSES,
    class_terms,
    display_label,
    label,
    short,
)

ANNOTATABLE_CLASSES = [uri for uri, _name in RESOURCE_CLASSES + PROCESS_CLASSES]


def _definition(graph: Graph, resource: URIRef) -> str | None:
    value = graph.value(resource, SKOS.definition)
    return " ".join(str(value).split()) if value else None


def vocab_terms(graph: Graph, rdf_class: URIRef) -> list[dict[str, str]]:
    terms = [
        {
            "id": str(subject),
            "label": display_label(label(graph, subject)),
            "definition": _definition(graph, subject),
        }
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


def _role_parents(graph: Graph) -> dict[URIRef, list[URIRef]]:
    # Sorted, because a role with several parents resolves through the first one
    # and rdflib hands them back in set order: ExternalModel shelved differently
    # from run to run.
    return {
        role: sorted(
            (p for p in graph.objects(role, PAIR.subRoleOf) if isinstance(p, URIRef)), key=str
        )
        for role in graph.subjects(RDF.type, PAIR.PatternRole)
    }


def _pattern_node_index(graph: Graph) -> tuple[dict, dict]:
    """What the library's pattern nodes say about each role: the BEAM class they
    expect it on, and the motifs that name it."""
    classes: dict[URIRef, set[URIRef]] = {}
    motifs: dict[URIRef, set[URIRef]] = {}
    for motif in graph.subjects(RDF.type, PAIR.GraphMotif):
        for node in graph.objects(motif, PAIR.hasPatternNode):
            role = graph.value(node, PAIR.expectedRole)
            if role is None:
                continue
            motifs.setdefault(role, set()).add(motif)
            expected = graph.value(node, PAIR.expectedClass)
            if expected is not None:
                classes.setdefault(role, set()).add(expected)
    return classes, motifs


def role_shelf(graph: Graph) -> dict[URIRef, URIRef]:
    """The BEAM class a role is annotated on, which is the one question a reader
    has to answer before any other: can this term go on this element at all?"""
    classes, _motifs = _pattern_node_index(graph)
    parents = _role_parents(graph)
    children: dict[URIRef, set[URIRef]] = {}
    for role, above in parents.items():
        for parent in above:
            children.setdefault(parent, set()).add(role)

    def most_general(candidates: set[URIRef]) -> URIRef:
        # GenerationStep is declared beam:Infer on one pattern node and
        # beam:Process on another; the shelf has to be the one that covers both.
        for candidate in sorted(candidates, key=str):
            if all(
                other == candidate
                or candidate in set(graph.transitive_objects(other, RDFS.subClassOf))
                for other in candidates
            ):
                return candidate
        return sorted(candidates, key=str)[0]

    def resolve(role: URIRef, seen: frozenset) -> URIRef | None:
        if role in classes:
            return most_general(classes[role])
        for parent in parents.get(role, ()):
            if parent not in seen:
                found = resolve(parent, seen | {role})
                if found is not None:
                    return found
        # An abstract role no pattern node names is shelved by what refines it,
        # which is the only evidence there is.
        for child in sorted(children.get(role, ()), key=str):
            if child not in seen:
                found = resolve(child, seen | {role})
                if found is not None:
                    return found
        return None

    shelves = {}
    for role in parents:
        found = resolve(role, frozenset())
        if found is not None:
            shelves[role] = found
    return shelves


def annotatable_under(graph: Graph, expected: URIRef) -> list[str]:
    """The classes an element can be typed as and still bind a pattern node
    expecting `expected` - which is what the queries write, not what the
    declaration says.

    A step is guarded `a/rdfs:subClassOf* beam:Process` in all 62 places one
    appears, so a declared `beam:Infer` binds a `beam:Generate` element and the
    role is the discriminator. A resource is typed with a bare `a beam:Data` or
    `a beam:StatisticalModel`, which walks nothing: a `beam:Symbol` binds
    neither, however it is annotated.
    """
    def under(top: URIRef) -> list[str]:
        return [
            str(candidate)
            for candidate in ANNOTATABLE_CLASSES
            if candidate == top or top in set(graph.transitive_objects(candidate, RDFS.subClassOf))
        ]

    # Process generalizes because the guard is always written at beam:Process.
    if BEAM.Process in set(graph.transitive_objects(expected, RDFS.subClassOf)):
        return under(BEAM.Process)
    # beam:Resource only when it is the declared class: beam:Data sits under it
    # too, and a node declared beam:Data is matched exactly.
    if expected == BEAM.Resource:
        return under(BEAM.Resource)
    return [str(expected)]


def role_reach(graph: Graph) -> dict[URIRef, dict[str, list[str]]]:
    """What a role reaches, kept as two separate facts.

    `motifs` are the motifs whose pattern nodes name the role itself, and the
    families and risk patterns are read off those. `serves` adds the motifs it
    reaches by refining a role they name, which is what a query matches on
    (`playsRole/subRoleOf*`) but is too generous to narrow a list by: one motif
    declares a `ResourceRole` wildcard, so inheriting through it would tag all
    53 resource-side roles Agentic.
    """
    _classes, motifs = _pattern_node_index(graph)
    parents = _role_parents(graph)

    def ancestors(role: URIRef) -> set[URIRef]:
        out, queue = set(), list(parents.get(role, ()))
        while queue:
            node = queue.pop()
            if node in out:
                continue
            out.add(node)
            queue.extend(parents.get(node, ()))
        return out

    reach = {}
    for role in parents:
        named = motifs.get(role, set())
        inherited = {m for a in ancestors(role) for m in motifs.get(a, set())} - named
        families, patterns = set(), set()
        for motif in named:
            families.update(label(graph, f) for f in graph.objects(motif, PAIR.motifFamily))
            patterns.update(short(p) for p in graph.objects(motif, PAIR.hasRiskPattern))
        reach[role] = {
            "motifs": sorted(short(m) for m in named),
            "families": sorted(families),
            "riskPatterns": sorted(patterns),
            "serves": sorted(short(m) for m in inherited),
        }
    return reach


def role_vocab_terms(graph: Graph) -> list[dict]:
    applies = role_applicability(graph)
    shelves = role_shelf(graph)
    reach = role_reach(graph)
    under: dict[URIRef, list[str]] = {}
    terms = []
    for subject in graph.subjects(RDF.type, PAIR.PatternRole):
        top = top_level_role(graph, subject)
        term = {
            "id": str(subject),
            "label": display_label(label(graph, subject)),
            "definition": _definition(graph, subject),
        }
        if top is not None:
            term["group"] = display_label(label(graph, top))
        if subject in applies:
            term["applies"] = applies[subject]
        expected = shelves.get(subject)
        if expected is not None:
            term["shelf"] = label(graph, expected)
            term["shelfId"] = str(expected)
            if expected not in under:
                under[expected] = annotatable_under(graph, expected)
            term["appliesTo"] = under[expected]
        term.update(reach.get(subject, {}))
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
        "dataClasses": list(data_classifications()),
    }
