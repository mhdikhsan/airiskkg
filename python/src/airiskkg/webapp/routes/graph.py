from __future__ import annotations

from flask import Blueprint, jsonify, request
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.graph_view import graph_view
from airiskkg.knowledge_base import graph_fingerprint
from airiskkg.t4b_import import T4bImportError, t4b_to_ttl
from airiskkg.workbench.process_view import process_view
from airiskkg.workbench.templates import motif_templates
from airiskkg.workbench.terms import PROCESS_CLASS_NAMES

graph_routes = Blueprint("graph", __name__)

LOCAL = Namespace("http://w3id.org/airiskkg/local#")


def _parsed(ttl: str) -> Graph:
    data = Graph()
    data.parse(data=ttl, format="turtle")
    return data


def _serialized(data: Graph, **extra: object) -> object:
    data.bind("beam", BEAM)
    data.bind("pair", PAIR)
    data.bind("local", LOCAL)
    return jsonify({"ttl": data.serialize(format="turtle"), **extra})


@graph_routes.post("/api/graph")
def read_graph() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = payload.get("ttl") or ""
    if not ttl.strip():
        return jsonify({"systems": [], "nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0}})
    try:
        return jsonify(graph_view(ttl))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@graph_routes.post("/api/process")
def read_process() -> object:
    """The business process layer of a submitted graph, if it carries one.

    Separate from /api/graph because the two answer different questions and one
    graph may hold both: /api/graph draws the architecture, this lists the
    process the architecture sits in. A graph with no BPMN triples comes back
    empty rather than as an error - most graphs have no process, and that is not
    a fault."""
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    if not ttl:
        return jsonify(process_view(Graph()))
    try:
        parsed = _parsed(ttl)
    except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
        return jsonify({"error": f"Could not parse the graph: {error}"}), 400
    return jsonify(process_view(parsed))


@graph_routes.post("/api/fingerprint")
def fingerprint() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    if not ttl:
        return jsonify({"error": "Provide an architecture graph (Turtle) to fingerprint."}), 400
    try:
        parsed = _parsed(ttl)
    except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
        return jsonify({"error": f"Could not parse the graph: {error}"}), 400
    return jsonify({"fingerprint": graph_fingerprint(parsed), "tripleCount": len(parsed)})


@graph_routes.post("/api/import/t4b")
def import_t4b() -> object:
    payload = request.get_json(silent=True) or {}
    data = (payload.get("data") or "").strip()
    fmt = "turtle" if payload.get("format") == "turtle" else "nt"
    if not data:
        return jsonify({"error": "Provide a Tool4Boxology export (N-Triples or Turtle) to import."}), 400
    try:
        ttl, warnings = t4b_to_ttl(data, fmt=fmt)
    except T4bImportError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"ttl": ttl, "warnings": warnings})


@graph_routes.post("/api/annotate")
def annotate() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    annotations = payload.get("annotations") or {}
    if not ttl:
        return jsonify({"error": "Provide an architecture graph (Turtle) to annotate."}), 400
    try:
        data = _parsed(ttl)
    except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
        return jsonify({"error": f"Could not parse the graph: {error}"}), 400

    for element_id, annotation in annotations.items():
        element = URIRef(element_id)
        data.remove((element, PAIR.playsRole, None))
        data.remove((element, PAIR.containsDataCategory, None))
        for role in annotation.get("roles") or []:
            data.add((element, PAIR.playsRole, URIRef(role)))
        for category in annotation.get("categories") or []:
            data.add((element, PAIR.containsDataCategory, URIRef(category)))

    data.bind("beam", BEAM)
    data.bind("pair", PAIR)
    return jsonify({"ttl": data.serialize(format="turtle")})


@graph_routes.post("/api/graph-edit")
def graph_edit() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    op = payload.get("op")
    if not ttl:
        return jsonify({"error": "Provide a graph to edit."}), 400
    try:
        data = _parsed(ttl)
    except Exception as error: 
        return jsonify({"error": f"Could not parse the graph: {error}"}), 400

    local = LOCAL
    new_id = None
    if op == "add-element":
        class_uri = payload.get("classUri")
        if not class_uri:
            return jsonify({"error": "add-element needs a classUri."}), 400
        label = (payload.get("label") or "New element").strip()
        existing = {str(s) for s in data.subjects() if str(s).startswith(str(local))}
        index = 1
        while str(local[f"e{index}"]) in existing:
            index += 1
        element = local[f"e{index}"]
        data.add((element, RDF.type, URIRef(class_uri)))
        data.add((element, RDFS.label, Literal(label)))
        system = next(iter(data.subjects(RDF.type, BEAM.System)), None)
        if system is not None:
            predicate = BEAM.hasProcess if payload.get("category") == "process" else BEAM.hasResource
            data.add((system, predicate, element))
        new_id = str(element)
    elif op == "add-edge":
        subject = payload.get("subject")
        predicate = payload.get("predicate")
        obj = payload.get("object")
        if not (subject and predicate and obj):
            return jsonify({"error": "add-edge needs subject, predicate, object."}), 400
        if predicate not in ("use", "produce", "inform"):
            return jsonify({"error": "predicate must be use, produce, or inform."}), 400
        data.add((URIRef(subject), BEAM[predicate], URIRef(obj)))
    elif op == "edit-element":
        element_id = payload.get("element")
        if not element_id:
            return jsonify({"error": "edit-element needs an element."}), 400
        element = URIRef(element_id)
        if "label" in payload:
            data.remove((element, RDFS.label, None))
            if payload.get("label"):
                data.add((element, RDFS.label, Literal(payload["label"])))
        if payload.get("classUri"):
            # replace the element's BEAM type(s) with the chosen class
            for existing_type in list(data.objects(element, RDF.type)):
                if str(existing_type).startswith(str(BEAM)):
                    data.remove((element, RDF.type, existing_type))
            data.add((element, RDF.type, URIRef(payload["classUri"])))
        if "roles" in payload:
            data.remove((element, PAIR.playsRole, None))
            for role in payload.get("roles") or []:
                data.add((element, PAIR.playsRole, URIRef(role)))
        if "categories" in payload:
            data.remove((element, PAIR.containsDataCategory, None))
            for category in payload.get("categories") or []:
                data.add((element, PAIR.containsDataCategory, URIRef(category)))
        new_name = (payload.get("name") or "").strip()
        if new_name:
            old = str(element)
            cut = old.rfind("#") if "#" in old else old.rfind("/")
            base = old[: cut + 1]
            local_part = "".join(ch for ch in new_name if ch.isalnum() or ch in "_.-") or "element"
            renamed = URIRef(base + local_part)
            if renamed != element:
                for s, p, o in list(data.triples((element, None, None))):
                    data.remove((s, p, o))
                    data.add((renamed, p, o))
                for s, p, o in list(data.triples((None, None, element))):
                    data.remove((s, p, o))
                    data.add((s, p, renamed))
                new_id = str(renamed)
    elif op == "add-motif":
        motif_id = payload.get("motif")
        template = motif_templates().get(motif_id)
        if template is None:
            return jsonify({"error": f"Unknown motif template: {motif_id}"}), 400
        system = next(iter(data.subjects(RDF.type, BEAM.System)), None)
        if system is None:
            system = local["system"]
            data.add((system, RDF.type, BEAM.System))
            data.add((system, RDFS.label, Literal("My system")))
        existing = {str(s) for s in data.subjects() if str(s).startswith(str(local))}
        counter = [1]

        def _fresh() -> URIRef:
            while str(local[f"e{counter[0]}"]) in existing:
                counter[0] += 1
            node = local[f"e{counter[0]}"]
            existing.add(str(node))
            counter[0] += 1
            return node

        key_to_uri: dict[str, URIRef] = {}
        new_ids: list[str] = []
        for node in template["nodes"]:
            uri = _fresh()
            key_to_uri[node["key"]] = uri
            is_process = node["cls"] in PROCESS_CLASS_NAMES
            data.add((uri, RDF.type, BEAM[node["cls"]]))
            if is_process and node["cls"] != "Process":
                data.add((uri, RDF.type, BEAM.Process))
            data.add((uri, RDFS.label, Literal(node["label"])))
            for role in node.get("roles", []):
                data.add((uri, PAIR.playsRole, PAIR[role]))
            for category in node.get("cats", []):
                data.add((uri, PAIR.containsDataCategory, PAIR[category]))
            predicate = BEAM.hasProcess if is_process else BEAM.hasResource
            data.add((system, predicate, uri))
            new_ids.append(str(uri))

        for src, edge, dst in template["edges"]:
            data.add((key_to_uri[src], BEAM[edge], key_to_uri[dst]))

        return _serialized(data, newIds=new_ids, groupLabel=template["label"])
    elif op == "delete-element":
        element_id = payload.get("element")
        if not element_id:
            return jsonify({"error": "delete-element needs an element."}), 400
        element = URIRef(element_id)
        # remove the element and every edge touching it (as subject or object)
        for s, p, o in list(data.triples((element, None, None))):
            data.remove((s, p, o))
        for s, p, o in list(data.triples((None, None, element))):
            data.remove((s, p, o))
    else:
        return jsonify({"error": f"Unknown edit op: {op}"}), 400

    return _serialized(data, newId=new_id)
