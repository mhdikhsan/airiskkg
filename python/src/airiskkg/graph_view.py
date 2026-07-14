"""Turn architecture Turtle into a nodes/edges structure for the live preview.

The web editor posts the Turtle source on every (debounced) edit; this module
parses it and returns a JSON-friendly view of the BEAM architecture graph:
typed nodes (process / data / symbol / model / agent / system) with their
pattern roles and data categories, and flow edges (use / produce / inform /
participatedIn). Classification uses the BEAM class hierarchy plus the label
vocabulary of the pattern module, both loaded once and cached.
"""

from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, RDFS, SKOS, Graph, URIRef
from rdflib.namespace import OWL

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.paths import CORE_DIR, FACETS_DIR

# Node kind per BEAM top class, most specific wins via subclass closure.
_KIND_ROOTS = [
    ("model", BEAM.Model),
    ("data", BEAM.Data),
    ("symbol", BEAM.Symbol),
    ("process", BEAM.Process),
    ("agent", BEAM.Agent),
    ("system", BEAM.System),
    ("task", BEAM.Task),
    ("resource", BEAM.Resource),
]

# Edges are emitted in DRAW direction (left-to-right data flow, boxology
# style): inputs point into the process, the process points at its outputs.
_FLOW_EDGES = [
    (BEAM.use, "use", True),            # beam:use is process->resource; drawn resource->process
    (BEAM.usedBy, "use", False),        # already resource->process
    (BEAM.produce, "produce", False),   # process->resource
    (BEAM.producedBy, "produce", True),
    (BEAM.inform, "inform", False),     # process->process
    (BEAM.participatedIn, "participatedIn", False),  # agent->process
]


@lru_cache(maxsize=1)
def _ontology() -> Graph:
    """BEAM class hierarchy + pattern/facet vocabulary labels (cached)."""
    graph = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        graph.parse(CORE_DIR / name, format="turtle")
    for path in sorted(FACETS_DIR.glob("*.ttl")):
        graph.parse(path, format="turtle")
    return graph


@lru_cache(maxsize=1)
def _superclasses() -> dict[URIRef, set[URIRef]]:
    """Transitive rdfs:subClassOf closure of the BEAM ontology."""
    ontology = _ontology()
    closure: dict[URIRef, set[URIRef]] = {}

    def supers(cls: URIRef, seen: set[URIRef]) -> set[URIRef]:
        if cls in closure:
            return closure[cls]
        result: set[URIRef] = set()
        for parent in ontology.objects(cls, RDFS.subClassOf):
            if isinstance(parent, URIRef) and parent not in seen:
                seen.add(parent)
                result.add(parent)
                result |= supers(parent, seen)
        closure[cls] = result
        return result

    for cls in set(ontology.subjects(RDF.type, OWL.Class)):
        if isinstance(cls, URIRef):
            supers(cls, {cls})
    return closure


def _local_name(uri: URIRef) -> str:
    text = str(uri)
    return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _label(graph: Graph, ontology: Graph, resource: URIRef) -> str:
    value = (
        graph.value(resource, RDFS.label)
        or graph.value(resource, SKOS.prefLabel)
        or ontology.value(resource, SKOS.prefLabel)
        or ontology.value(resource, RDFS.label)
    )
    return str(value) if value else _local_name(resource)


def _kind_and_type(types: set[URIRef]) -> tuple[str, str | None]:
    """Node kind + most specific BEAM type label for a set of rdf:types."""
    closure = _superclasses()
    beam_types = {
        t for t in types
        if str(t).startswith(str(BEAM)) or any(
            str(s).startswith(str(BEAM)) for s in closure.get(t, ())
        )
    }
    if not beam_types:
        return "other", None
    # most specific = a type that is not a superclass of any other held type
    all_supers: set[URIRef] = set()
    for t in beam_types:
        all_supers |= closure.get(t, set())
    specific = [t for t in beam_types if t not in all_supers] or sorted(beam_types, key=str)
    chosen = sorted(specific, key=str)[0]
    ancestry = {chosen} | closure.get(chosen, set())
    for kind, root in _KIND_ROOTS:
        if root in ancestry:
            return kind, _local_name(chosen)
    return "other", _local_name(chosen)


def graph_view(ttl_text: str) -> dict:
    """Parse architecture Turtle and return {system, nodes, edges}.

    Raises ValueError with the parser message when the Turtle is invalid.
    """
    graph = Graph()
    try:
        graph.parse(data=ttl_text, format="turtle")
    except Exception as error:  # noqa: BLE001 - surfaced verbatim to the editor
        raise ValueError(str(error)) from error

    ontology = _ontology()

    # candidate nodes: everything typed with a BEAM class or touched by a flow edge
    node_ids: set[URIRef] = set()
    typed: dict[URIRef, set[URIRef]] = {}
    for subject, obj in graph.subject_objects(RDF.type):
        if isinstance(subject, URIRef) and isinstance(obj, URIRef):
            typed.setdefault(subject, set()).add(obj)

    edges: list[dict] = []
    seen_edges: set[tuple] = set()
    for predicate, kind, inverted in _FLOW_EDGES:
        for s, o in graph.subject_objects(predicate):
            if not (isinstance(s, URIRef) and isinstance(o, URIRef)):
                continue
            source, target = (o, s) if inverted else (s, o)
            key = (source, target, kind)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({"source": str(source), "target": str(target), "kind": kind})
            node_ids.update((source, target))

    for subject, types in typed.items():
        kind, _ = _kind_and_type(types)
        if kind != "other":
            node_ids.add(subject)

    systems = []
    nodes = []
    for node in sorted(node_ids, key=str):
        kind, type_label = _kind_and_type(typed.get(node, set()))
        roles = sorted(
            _label(graph, ontology, r)
            for r in graph.objects(node, PAIR.playsRole)
            if isinstance(r, URIRef)
        )
        categories = sorted(
            _label(graph, ontology, c)
            for c in graph.objects(node, PAIR.containsDataCategory)
            if isinstance(c, URIRef)
        )
        entry = {
            "id": str(node),
            "label": _label(graph, ontology, node),
            "kind": kind,
            "typeLabel": type_label,
            "roles": roles,
            "categories": categories,
        }
        if kind == "system":
            systems.append(entry)
        else:
            nodes.append(entry)

    node_set = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in node_set and e["target"] in node_set]

    return {
        "systems": [{"id": s["id"], "label": s["label"]} for s in systems],
        "nodes": nodes,
        "edges": edges,
        "stats": {"nodes": len(nodes), "edges": len(edges)},
    }
