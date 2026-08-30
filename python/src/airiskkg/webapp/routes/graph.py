from __future__ import annotations

from flask import Blueprint, jsonify, request
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.graph_view import graph_view
from airiskkg.knowledge_base import graph_fingerprint
from airiskkg.t4b_import import T4bImportError, t4b_to_ttl
from airiskkg.workbench.process_view import DATA_CLASSES, process_view
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
        return jsonify({"systems": [], "nodes": [], "edges": [],
                        "scopedTo": None, "stats": {"nodes": 0, "edges": 0}})
    try:
        # `scope` is a beam:System IRI: the architecture behind one business
        # activity, rather than every architecture the document happens to hold.
        return jsonify(graph_view(ttl, scope=(payload.get("scope") or None)))
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
    return jsonify(process_view(parsed, ttl))


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


# --- authoring the business layer --------------------------------------------

BPMN = Namespace("https://sBPMN.github.io/2.0/classes#")
BP = Namespace("https://sBPMN.github.io/2.0/properties#")

# What the palette offers. Deliberately short: these are the constructs a risk
# assessment reads. Gateways and events draw well and say nothing this method
# can use, so offering them would invite effort that changes no finding.
ACTIVITY_KINDS = {
    "task": "Task",
    "userTask": "User task",
    "serviceTask": "Service task",
    "sendTask": "Send task",
    "receiveTask": "Receive task",
    "subProcess": "Sub-process",
}


DPV = Namespace("https://w3id.org/dpv#")


def _fresh(data: Graph, prefix: str) -> URIRef:
    existing = {str(s) for s in data.subjects()}
    index = 1
    while str(LOCAL[f"{prefix}{index}"]) in existing:
        index += 1
    return LOCAL[f"{prefix}{index}"]


def _process_of(data: Graph, node: URIRef) -> URIRef | None:
    """The process that contains a flow node - which is also what decides
    whether a connection between two nodes is a sequence flow or a message.

    In BPMN that is not a preference: sequence flow cannot leave a process, and
    a message flow only exists between participants. Reading the containment and
    deciding from it means the modeller never has to know the rule."""
    for process in data.subjects(BP.contains, node):
        if (process, RDF.type, BPMN.process) in data:
            return process
    return None


@graph_routes.post("/api/process-edit")
def process_edit() -> object:
    """Structural edits to the business layer, mirroring /api/graph-edit.

    Body: {ttl, op, ...}. Ops: add-pool, add-activity, connect, set-refines,
    add-data, classify-data, detach-data, rename, delete. Returns the rewritten
    Turtle, which the editor adopts.
    """
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    op = payload.get("op")
    try:
        data = _parsed(ttl) if ttl else Graph()
    except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
        return jsonify({"error": f"Could not parse the graph: {error}"}), 400

    new_id = None

    if op == "add-pool":
        label = (payload.get("label") or "New participant").strip()
        participant = _fresh(data, "pool")
        process = _fresh(data, "proc")
        data.add((participant, RDF.type, BPMN.participant))
        data.add((participant, BP.name, Literal(label)))
        data.add((participant, BP.processRef, process))
        data.add((process, RDF.type, BPMN.process))
        data.add((process, BP.name, Literal(f"{label} process")))
        new_id = str(participant)

    elif op == "add-activity":
        kind = payload.get("kind")
        if kind not in ACTIVITY_KINDS:
            return jsonify({"error": f"Unknown activity kind: {kind}"}), 400
        pool = payload.get("pool")
        if not pool:
            return jsonify({"error": "add-activity needs a pool."}), 400
        process = data.value(URIRef(pool), BP.processRef)
        if process is None:
            return jsonify({"error": "That participant has no process."}), 400
        activity = _fresh(data, "act")
        data.add((activity, RDF.type, BPMN[kind]))
        data.add((activity, BP.name, Literal((payload.get("label") or ACTIVITY_KINDS[kind]).strip())))
        data.add((process, BP.contains, activity))
        new_id = str(activity)

    elif op == "connect":
        source = payload.get("source")
        target = payload.get("target")
        if not (source and target):
            return jsonify({"error": "connect needs a source and a target."}), 400
        if source == target:
            return jsonify({"error": "An activity cannot flow to itself."}), 400
        source_ref, target_ref = URIRef(source), URIRef(target)
        same_process = _process_of(data, source_ref) == _process_of(data, target_ref)
        flow = _fresh(data, "sflow" if same_process else "mflow")
        data.add((flow, RDF.type, BPMN.sequenceFlow if same_process else BPMN.messageFlow))
        data.add((flow, BP.sourceRef, source_ref))
        data.add((flow, BP.targetRef, target_ref))
        if not same_process:
            data.add((flow, BP.name, Literal("sends")))
        data.add((source_ref, BP.outgoing, flow))
        data.add((target_ref, BP.incoming, flow))
        new_id = str(flow)

    elif op == "set-refines":
        activity = payload.get("activity")
        system = payload.get("system")
        if not activity:
            return jsonify({"error": "set-refines needs an activity."}), 400
        data.remove((URIRef(activity), PAIR.refinedBy, None))
        if system:
            data.add((URIRef(activity), PAIR.refinedBy, URIRef(system)))
        new_id = activity

    elif op == "add-data":
        activity = payload.get("activity")
        direction = payload.get("direction")
        if not activity or direction not in ("in", "out"):
            return jsonify({"error": "add-data needs an activity and a direction."}), 400
        classification = payload.get("classification") or ""
        if classification and classification not in DATA_CLASSES:
            return jsonify({"error": f"Unknown data classification: {classification}"}), 400

        node = URIRef(activity)
        label = (payload.get("label") or "Data").strip()
        obj = _fresh(data, "data")
        reference = _fresh(data, "dataref")
        data.add((obj, RDF.type, BPMN.dataObject))
        data.add((obj, BP.name, Literal(label)))
        data.add((reference, RDF.type, BPMN.dataObjectReference))
        data.add((reference, BP.dataObjectRef, obj))
        if payload.get("collection"):
            data.add((obj, BP.isCollection, Literal(True)))
        if classification:
            item = _fresh(data, "item")
            data.add((item, RDF.type, BPMN.itemDefinition))
            data.add((item, BP.structureRef, DPV[classification]))
            data.add((obj, BP.itemSubjectRef, item))

        # BPMN puts the association on the activity and gives it both ends; the
        # bridge query reads sourceRef/targetRef, so writing only one side would
        # draw an arrow that derives nothing.
        association = _fresh(data, "dassoc")
        if direction == "in":
            data.add((association, RDF.type, BPMN.dataInputAssociation))
            data.add((association, BP.sourceRef, reference))
            data.add((association, BP.targetRef, node))
            data.add((node, BP.dataInputAssociation, association))
        else:
            data.add((association, RDF.type, BPMN.dataOutputAssociation))
            data.add((association, BP.sourceRef, node))
            data.add((association, BP.targetRef, reference))
            data.add((node, BP.dataOutputAssociation, association))
        new_id = str(reference)

    elif op == "classify-data":
        reference = payload.get("reference")
        classification = payload.get("classification") or ""
        if not reference:
            return jsonify({"error": "classify-data needs a data reference."}), 400
        if classification and classification not in DATA_CLASSES:
            return jsonify({"error": f"Unknown data classification: {classification}"}), 400
        ref = URIRef(reference)
        obj = data.value(ref, BP.dataObjectRef) or data.value(ref, BP.dataStoreRef) or ref
        item = data.value(obj, BP.itemSubjectRef)
        if classification and item is None:
            item = _fresh(data, "item")
            data.add((item, RDF.type, BPMN.itemDefinition))
            data.add((obj, BP.itemSubjectRef, item))
        if item is not None:
            data.remove((item, BP.structureRef, None))
            if classification:
                data.add((item, BP.structureRef, DPV[classification]))
        new_id = str(ref)

    elif op == "detach-data":
        reference = payload.get("reference")
        activity = payload.get("activity")
        if not (reference and activity):
            return jsonify({"error": "detach-data needs a reference and an activity."}), 400
        ref, node = URIRef(reference), URIRef(activity)
        for prop in (BP.dataInputAssociation, BP.dataOutputAssociation):
            for association in list(data.objects(node, prop)):
                ends = set(data.objects(association, BP.sourceRef)) | set(
                    data.objects(association, BP.targetRef)
                )
                if ref not in ends:
                    continue
                data.remove((node, prop, association))
                for triple in list(data.triples((association, None, None))):
                    data.remove(triple)
        # The object itself goes only when nothing else reads or writes it: a
        # data object reference is shared on purpose, and removing it from one
        # activity must not take it away from another.
        still_used = any(
            ref in (set(data.objects(a, BP.sourceRef)) | set(data.objects(a, BP.targetRef)))
            for a in data.subjects(RDF.type, BPMN.dataInputAssociation)
        ) or any(
            ref in (set(data.objects(a, BP.sourceRef)) | set(data.objects(a, BP.targetRef)))
            for a in data.subjects(RDF.type, BPMN.dataOutputAssociation)
        )
        if not still_used:
            obj = data.value(ref, BP.dataObjectRef)
            item = data.value(obj, BP.itemSubjectRef) if obj is not None else None
            for victim in [ref, obj, item]:
                if victim is None:
                    continue
                for triple in list(data.triples((victim, None, None))):
                    data.remove(triple)
                for triple in list(data.triples((None, None, victim))):
                    data.remove(triple)

    elif op == "rename":
        element = payload.get("element")
        if not element:
            return jsonify({"error": "rename needs an element."}), 400
        data.remove((URIRef(element), BP.name, None))
        if payload.get("label"):
            data.add((URIRef(element), BP.name, Literal(payload["label"].strip())))

    elif op == "delete":
        element = payload.get("element")
        if not element:
            return jsonify({"error": "delete needs an element."}), 400
        node = URIRef(element)
        # A participant owns its process; deleting the pool without it would
        # leave a process nothing runs and activities nobody performs.
        doomed = {node}
        process = data.value(node, BP.processRef)
        if process is not None:
            doomed.add(process)
            doomed.update(data.objects(process, BP.contains))
        # Any connector that touched what is going.
        for flow in list(data.subjects(BP.sourceRef, None)) + list(data.subjects(BP.targetRef, None)):
            ends = set(data.objects(flow, BP.sourceRef)) | set(data.objects(flow, BP.targetRef))
            if ends & doomed:
                doomed.add(flow)
        for victim in doomed:
            for triple in list(data.triples((victim, None, None))):
                data.remove(triple)
            for triple in list(data.triples((None, None, victim))):
                data.remove(triple)

    else:
        return jsonify({"error": f"Unknown process edit op: {op}"}), 400

    data.bind("bpmn", BPMN)
    data.bind("bp", BP)
    return _serialized(data, newId=new_id)
