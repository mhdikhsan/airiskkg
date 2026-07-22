"""Convert a JSON architecture-builder model (from the web UI) into architecture Turtle."""

from __future__ import annotations

import re

from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR

EX = Namespace("http://w3id.org/airiskkg/example/builder#")

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BuilderError(Exception):
    """Raised when a builder model cannot be turned into a valid architecture graph."""


def _require_name(kind: str, raw_name: str) -> str:
    name = (raw_name or "").strip()
    if not name:
        raise BuilderError(f"Every {kind} needs a name.")
    if not _NAME_RE.match(name):
        raise BuilderError(
            f"{kind.capitalize()} name '{name}' must start with a letter or underscore and contain only "
            "letters, digits, or underscores."
        )
    return name


def _resolve(element_uris: dict[str, URIRef], ref_name: str, owner: str) -> URIRef:
    ref_name = (ref_name or "").strip()
    if ref_name not in element_uris:
        raise BuilderError(f"Process '{owner}' references unknown element '{ref_name}'.")
    return element_uris[ref_name]


def build_ttl(model: dict) -> str:
    resources = model.get("resources") or []
    processes = model.get("processes") or []
    if not resources and not processes:
        raise BuilderError("Add at least one resource or process before generating Turtle.")

    system_name = _require_name("system", model.get("systemName") or "System")
    system_label = (model.get("systemLabel") or "").strip()

    element_uris: dict[str, URIRef] = {}
    for element in (*resources, *processes):
        name = _require_name("element", element.get("name", ""))
        if name in element_uris:
            raise BuilderError(f"Duplicate element name '{name}'.")
        element_uris[name] = EX[name]

    graph = Graph()
    graph.bind("beam", BEAM)
    graph.bind("pair", PAIR)
    graph.bind("rdfs", RDFS)
    graph.bind("ex", EX)

    system_uri = EX[system_name]
    graph.add((system_uri, RDF.type, BEAM.System))
    if system_label:
        graph.add((system_uri, RDFS.label, Literal(system_label, lang="en")))

    for resource in resources:
        name = resource["name"].strip()
        uri = element_uris[name]
        cls = resource.get("class")
        if not cls:
            raise BuilderError(f"Resource '{name}' needs a class.")
        graph.add((uri, RDF.type, URIRef(cls)))
        graph.add((system_uri, BEAM.hasResource, uri))
        label = (resource.get("label") or "").strip()
        if label:
            graph.add((uri, RDFS.label, Literal(label, lang="en")))
        for role in resource.get("roles") or []:
            graph.add((uri, PAIR.playsRole, URIRef(role)))
        for category in resource.get("dataCategories") or []:
            graph.add((uri, PAIR.containsDataCategory, URIRef(category)))

    for process in processes:
        name = process["name"].strip()
        uri = element_uris[name]
        cls = process.get("class")
        if not cls:
            raise BuilderError(f"Process '{name}' needs a class.")
        graph.add((uri, RDF.type, URIRef(cls)))
        graph.add((system_uri, BEAM.hasProcess, uri))
        label = (process.get("label") or "").strip()
        if label:
            graph.add((uri, RDFS.label, Literal(label, lang="en")))
        for role in process.get("roles") or []:
            graph.add((uri, PAIR.playsRole, URIRef(role)))
        for ref_name in process.get("use") or []:
            graph.add((uri, BEAM.use, _resolve(element_uris, ref_name, name)))
        for ref_name in process.get("produce") or []:
            graph.add((uri, BEAM.produce, _resolve(element_uris, ref_name, name)))
        for ref_name in process.get("inform") or []:
            graph.add((uri, BEAM.inform, _resolve(element_uris, ref_name, name)))

    return graph.serialize(format="turtle")
