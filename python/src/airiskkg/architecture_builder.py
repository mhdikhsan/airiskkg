"""Convert the guided builder's structured model into an architecture graph (Turtle).

The web UI lets a developer describe their system as resources and processes with
roles, data categories, and ``use``/``produce``/``inform`` edges. This module turns
that JSON model into a valid BEAM/PAIR-AI Turtle document that the assessment engine
can consume, so TTL generation has a single, testable home.
"""

from __future__ import annotations

import re

from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR

APP = Namespace("http://w3id.org/airiskkg/example/app#")

# Edges the builder understands, mapped to their BEAM predicate. ``use``/``produce``
# connect a process to a resource; ``inform`` connects a process to another process.
EDGE_PREDICATES = {
    "use": BEAM.use,
    "produce": BEAM.produce,
    "inform": BEAM.inform,
}


class BuilderError(ValueError):
    """Raised when the builder model is malformed."""


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]", "", (name or "").strip().replace(" ", ""))
    if not cleaned:
        raise BuilderError("Every resource and process needs a non-empty name.")
    if cleaned[0].isdigit():
        cleaned = f"N{cleaned}"
    return cleaned


def _node(name: str) -> URIRef:
    return APP[_slug(name)]


def build_graph(model: dict) -> Graph:
    """Build an rdflib graph from a builder model dictionary."""
    graph = Graph()
    graph.bind("app", APP)
    graph.bind("beam", BEAM)
    graph.bind("pair", PAIR)
    graph.bind("rdfs", RDFS)

    resources = model.get("resources") or []
    processes = model.get("processes") or []
    if not resources and not processes:
        raise BuilderError("Add at least one resource or process before generating.")

    system = APP[_slug(model.get("systemName") or "System")]
    graph.add((system, RDF.type, BEAM.System))
    system_label = model.get("systemLabel") or "Assessed AI System"
    graph.add((system, RDFS.label, Literal(system_label, lang="en")))

    # Validate node names are unique so edges resolve unambiguously.
    seen: set[str] = set()

    def register(name: str) -> URIRef:
        slug = _slug(name)
        if slug in seen:
            raise BuilderError(f"Duplicate element name: {name!r}")
        seen.add(slug)
        return APP[slug]

    for resource in resources:
        node = register(resource.get("name", ""))
        graph.add((system, BEAM.hasResource, node))
        graph.add((node, RDF.type, URIRef(resource.get("class") or str(BEAM.Data))))
        if resource.get("label"):
            graph.add((node, RDFS.label, Literal(resource["label"], lang="en")))
        for role in resource.get("roles") or []:
            graph.add((node, PAIR.playsRole, URIRef(role)))
        for category in resource.get("dataCategories") or []:
            graph.add((node, PAIR.containsDataCategory, URIRef(category)))

    for process in processes:
        node = register(process.get("name", ""))
        graph.add((system, BEAM.hasProcess, node))
        graph.add((node, RDF.type, URIRef(process.get("class") or str(BEAM.Process))))
        if process.get("label"):
            graph.add((node, RDFS.label, Literal(process["label"], lang="en")))
        for role in process.get("roles") or []:
            graph.add((node, PAIR.playsRole, URIRef(role)))
        for edge_kind, predicate in EDGE_PREDICATES.items():
            for target in process.get(edge_kind) or []:
                target_node = _node(target)
                if str(target_node).rsplit("#", 1)[-1] not in seen:
                    raise BuilderError(
                        f"Process {process.get('name')!r} references unknown element {target!r}."
                    )
                graph.add((node, predicate, target_node))

    return graph


def build_ttl(model: dict) -> str:
    """Build a Turtle document from a builder model dictionary."""
    return build_graph(model).serialize(format="turtle")
