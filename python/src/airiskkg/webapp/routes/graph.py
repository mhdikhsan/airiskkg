from __future__ import annotations

from flask import Blueprint, jsonify, request
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.graph_view import (
    _kind_and_type,
    _members_of,
    flow_endpoint_error,
    graph_view,
    node_kind,
)
from airiskkg.knowledge_base import graph_fingerprint
from airiskkg.t4b_import import T4bImportError, t4b_to_ttl
from airiskkg.workbench.process_view import (
    context_values,
    data_class_names,
    process_view,
    system_context_options,
)
from airiskkg.workbench.templates import motif_templates
from airiskkg.workbench.terms import PROCESS_CLASS_NAMES

graph_routes = Blueprint("graph", __name__)

LOCAL = Namespace("http://w3id.org/airiskkg/local#")


def _parsed(ttl: str) -> Graph:
    data = Graph()
    data.parse(data=ttl, format="turtle")
    return data


DRAWN_AS = {
    "use": ((BEAM.use, True), (BEAM.usedBy, False)),
    "produce": ((BEAM.produce, False), (BEAM.producedBy, True)),
    "participatedIn": ((BEAM.participatedIn, False),),
}


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
    """The business process layer of a submitted graph, if it carries one."""
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
        # The architecture the reader is looking at, when they say which.
        asked = payload.get("system")
        system = URIRef(asked) if asked else None
        if system is not None and (system, RDF.type, BEAM.System) not in data:
            return jsonify({"error": "That AI system is not in this graph."}), 400
        if system is None:
            system = next(iter(data.subjects(RDF.type, BEAM.System)), None)
        if system is not None:
            predicate = BEAM.hasProcess if payload.get("category") == "process" else BEAM.hasResource
            data.add((system, predicate, element))
        new_id = str(element)

    elif op == "add-system":
        label = (payload.get("label") or "New AI system").strip()
        system = _fresh(data, "system")
        data.add((system, RDF.type, BEAM.Element))
        data.add((system, RDF.type, BEAM.System))
        data.add((system, RDFS.label, Literal(label)))
        for key, prop in (("description", BEAM.description), ("context", BEAM.context)):
            value = (payload.get(key) or "").strip()
            if value:
                data.add((system, prop, Literal(value)))

        # Take in the elements that belong to nowhere.
        if payload.get("adopt"):
            claimed: set[URIRef] = set()
            for other in data.subjects(RDF.type, BEAM.System):
                claimed |= _members_of(data, other)

            typed: dict[URIRef, set[URIRef]] = {}
            for subject, obj in data.subject_objects(RDF.type):
                if isinstance(subject, URIRef) and isinstance(obj, URIRef):
                    typed.setdefault(subject, set()).add(obj)

            holder = {"agent": BEAM.hasAgent, "process": BEAM.hasProcess}
            for element, types in typed.items():
                if element in claimed:
                    continue
                kind, _unused = _kind_and_type(types)
                if kind in ("other", "system"):
                    continue
                data.add((system, holder.get(kind, BEAM.hasResource), element))
        new_id = str(system)

    elif op == "add-edge":
        subject = payload.get("subject")
        predicate = payload.get("predicate")
        obj = payload.get("object")
        if not (subject and predicate and obj):
            return jsonify({"error": "add-edge needs subject, predicate, object."}), 400
        if predicate not in DRAWN_AS:
            return jsonify({"error": f"{predicate} is not a flow this canvas draws."}), 400
        head, tail = URIRef(subject), URIRef(obj)
        # The editor is the source of truth, so a request can arrive without the
        # canvas having vetted the ends. The contract rejects a malformed edge on
        # assessment; refusing it here keeps it out of the document.
        wrong = flow_endpoint_error(data, predicate, head, tail)
        if wrong:
            return jsonify({"error": wrong}), 400
        data.add((head, BEAM[predicate], tail))
    elif op == "remove-edge":
        """A connector drawn wrong used to cost the elements at either end,
        because deleting an element was the only thing that took its edges with
        it.

        Named by the line as drawn - source, target, kind - and not by a triple.
        The canvas draws beam:use backwards on purpose, resource into process,
        and both use and produce have an inverse form that draws the same line;
        a client sending a triple would have to know all of that, and would get
        it wrong in exactly one of the four cases. The table below is the same
        one graph_view reads the edges with."""
        source = payload.get("source")
        target = payload.get("target")
        kind = payload.get("kind")
        if not (source and target and kind):
            return jsonify({"error": "remove-edge needs source, target, kind."}), 400
        if kind not in DRAWN_AS:
            return jsonify({"error": f"{kind} is not a flow this canvas draws."}), 400
        head, tail = URIRef(source), URIRef(target)
        gone = 0
        for predicate, inverted in DRAWN_AS[kind]:
            triple = (tail, predicate, head) if inverted else (head, predicate, tail)
            if triple in data:
                data.remove(triple)
                gone += 1
        if not gone:
            return jsonify({"error": "There is no such connection to remove."}), 400
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
        for key, prop in (("description", BEAM.description), ("context", BEAM.context)):
            if key in payload:
                data.remove((element, prop, None))
                value = (payload.get(key) or "").strip()
                if value:
                    data.add((element, prop, Literal(value)))
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

        # Named apart from the module-level _fresh: a nested def with the same
        # name makes it local to this whole view, so every other branch that
        # reached for the module one got an unbound local instead.
        def _fresh_template_id() -> URIRef:
            while str(local[f"e{counter[0]}"]) in existing:
                counter[0] += 1
            node = local[f"e{counter[0]}"]
            existing.add(str(node))
            counter[0] += 1
            return node

        key_to_uri: dict[str, URIRef] = {}
        new_ids: list[str] = []
        for node in template["nodes"]:
            uri = _fresh_template_id()
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

# Every kind of connector sBPMN declares, which is what `disconnect` will act
# on and nothing else.
CONNECTOR_CLASSES = {
    BPMN.sequenceFlow, BPMN.messageFlow, BPMN.association,
    BPMN.dataInputAssociation, BPMN.dataOutputAssociation,
}

# What the palette offers, restricted to what external/sbpmn/sbpmn_2.0.ttl declares.
ACTIVITY_KINDS = {
    "task": "Task",
    "userTask": "User task",
    "manualTask": "Manual task",
    "serviceTask": "Service task",
    "scriptTask": "Script task",
    "businessRuleTask": "Business rule task",
    "sendTask": "Send task",
    "receiveTask": "Receive task",
    "subProcess": "Sub-process",
    "adHocSubProcess": "Ad-hoc sub-process",
    "transaction": "Transaction",
    "callActivity": "Call activity",
}

EVENT_KINDS = {
    "startEvent": "Start",
    "intermediateCatchEvent": "Intermediate",
    "intermediateThrowEvent": "Intermediate",
    "endEvent": "End",
    "boundaryEvent": "Boundary",
}

EVENT_DEFINITIONS = {
    "message": "messageEventDefinition",
    "timer": "timerEventDefinition",
    "error": "errorEventDefinition",
    "escalation": "escalationEventDefinition",
    "signal": "signalEventDefinition",
    "conditional": "conditionalEventDefinition",
    "compensate": "compensateEventDefinition",
    "cancel": "cancelEventDefinition",
    "terminate": "terminateEventDefinition",
    "link": "linkEventDefinition",
}

GATEWAY_KINDS = {
    "exclusiveGateway": "Exclusive",
    "parallelGateway": "Parallel",
    "inclusiveGateway": "Inclusive",
    "eventBasedGateway": "Event-based",
    "parallelEventBasedGateway": "Event-based",
    "complexGateway": "Complex",
}

LOOP_KINDS = {
    "standard": ("standardLoopCharacteristics", None),
    "multiParallel": ("multiInstanceLoopCharacteristics", False),
    "multiSequential": ("multiInstanceLoopCharacteristics", True),
}

FLOW_NODE_KINDS = {*ACTIVITY_KINDS, *EVENT_KINDS, *GATEWAY_KINDS}


DPV = Namespace("https://w3id.org/dpv#")


DATA_REFS = frozenset({BPMN.dataObjectReference, BPMN.dataStoreReference})
# sBPMN declares bp:dataInputAssociation on activity and throwEvent, and
# bp:dataOutputAssociation on activity and catchEvent. The canvas does not tell
# throw from catch, so it joins data to an activity only rather than risk
# writing an association outside the property's domain.
ACTIVITY_CLASSES = frozenset(BPMN[kind] for kind in ACTIVITY_KINDS)


def _join_data(data: Graph, reference: URIRef, activity: URIRef, direction: str) -> str | None:
    """Join a data object or store to a step, as BPMN models it.

    The thing is declared once and shows up through references, so a reference
    nothing uses yet is the box the reader placed and gets joined, while one
    already in use is copied. Two readers of one store are two boxes and two
    short lines, not one box with lines across the diagram.
    """
    kinds = set(data.objects(reference, RDF.type))
    store = BPMN.dataStoreReference in kinds
    held = data.value(reference, BP.dataStoreRef if store else BP.dataObjectRef)
    if held is None:
        return None

    used = {
        data.value(end, BP.dataStoreRef) or data.value(end, BP.dataObjectRef)
        for prop, side in ((BP.dataInputAssociation, BP.sourceRef),
                           (BP.dataOutputAssociation, BP.targetRef))
        for association in data.objects(activity, prop)
        for end in data.objects(association, side)
    }
    if held in used:
        return None

    if _in_use(data, reference):
        appearance = _fresh(data, "dataref")
        data.add((appearance, RDF.type,
                  BPMN.dataStoreReference if store else BPMN.dataObjectReference))
        data.add((appearance, BP.dataStoreRef if store else BP.dataObjectRef, held))
        reference = appearance

    association = _fresh(data, "dassoc")
    if direction == "in":
        data.add((association, RDF.type, BPMN.dataInputAssociation))
        data.add((association, BP.sourceRef, reference))
        data.add((association, BP.targetRef, activity))
        data.add((activity, BP.dataInputAssociation, association))
    else:
        data.add((association, RDF.type, BPMN.dataOutputAssociation))
        data.add((association, BP.sourceRef, activity))
        data.add((association, BP.targetRef, reference))
        data.add((activity, BP.dataOutputAssociation, association))
    return str(association)


def _in_use(data: Graph, reference: URIRef) -> bool:
    """Whether any activity already reads or writes this appearance."""
    return any(
        reference in set(data.objects(association, side))
        for prop, side in ((BP.dataInputAssociation, BP.sourceRef),
                           (BP.dataOutputAssociation, BP.targetRef))
        for association in data.objects(None, prop)
    )


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
    deciding from it means the modeller never has to know the rule.

    A node nested in a sub-process, or pinned to the border of one as a boundary
    event, belongs to the process that holds its host."""
    seen: set[URIRef] = set()
    current: URIRef | None = node
    while current is not None and current not in seen:
        seen.add(current)
        parent = data.value(current, BP.attachedToRef)
        for holder in data.subjects(BP.contains, current):
            if (holder, RDF.type, BPMN.process) in data:
                return holder
            if parent is None:
                parent = holder
        current = parent
    return None


def _process_of_pool(data: Graph, pool: str | None) -> URIRef | None:
    return data.value(URIRef(pool), BP.processRef) if pool else None


def _place(data: Graph, process: URIRef, node: URIRef, lane: str | None) -> None:
    """Put a new flow node in its process, and in a lane when one is selected."""
    data.add((process, BP.contains, node))
    if lane:
        band = URIRef(lane)
        if (band, RDF.type, BPMN.lane) in data:
            data.add((band, BP.flowNodeRef, node))


def _retype(data: Graph, node: URIRef, kind: str) -> None:
    """Swap the BPMN class without disturbing anything else on the node - a
    retype must not drop the flows, the data or the refinement it carries."""
    for existing in list(data.objects(node, RDF.type)):
        if str(existing).startswith(str(BPMN)) and str(existing)[len(str(BPMN)):] in FLOW_NODE_KINDS:
            data.remove((node, RDF.type, existing))
    data.add((node, RDF.type, BPMN[kind]))


def _set_event_definition(data: Graph, event: URIRef, definition: str) -> None:
    for old in list(data.objects(event, BP.eventDefinition)):
        data.remove((event, BP.eventDefinition, old))
        for triple in list(data.triples((old, None, None))):
            data.remove(triple)
    if definition in EVENT_DEFINITIONS:
        node = _fresh(data, "evdef")
        data.add((node, RDF.type, BPMN[EVENT_DEFINITIONS[definition]]))
        data.add((event, BP.eventDefinition, node))


@graph_routes.post("/api/process-edit")
def process_edit() -> object:
    """Structural edits to the business layer, mirroring /api/graph-edit."""
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
        _place(data, process, activity, payload.get("lane"))
        new_id = str(activity)

    elif op == "add-event":
        kind = payload.get("kind")
        if kind not in EVENT_KINDS:
            return jsonify({"error": f"Unknown event kind: {kind}"}), 400
        definition = payload.get("definition") or ""
        if definition and definition not in EVENT_DEFINITIONS:
            return jsonify({"error": f"Unknown event trigger: {definition}"}), 400
        # A boundary event is placed by the activity it watches, not by a pool:
        # it has no position of its own and cannot exist without a host. Every
        # other event is placed by the pool, and sBPMN declares attachedToRef on
        # bpmn:boundaryEvent alone - so a host given for any other kind is
        # dropped rather than written outside the property's domain.
        host = payload.get("attachedTo") if kind == "boundaryEvent" else None
        if kind == "boundaryEvent" and not payload.get("attachedTo"):
            return jsonify(
                {"error": "A boundary event must name the activity it is attached to."}
            ), 400
        process = (
            _process_of(data, URIRef(host)) if host
            else _process_of_pool(data, payload.get("pool"))
        )
        if process is None:
            return jsonify({"error": "add-event needs a participant with a process."}), 400
        event = _fresh(data, "ev")
        data.add((event, RDF.type, BPMN[kind]))
        if payload.get("label"):
            data.add((event, BP.name, Literal(payload["label"].strip())))
        _set_event_definition(data, event, definition)
        if host:
            data.add((event, BP.attachedToRef, URIRef(host)))
            data.add((event, BP.cancelActivity, Literal(bool(payload.get("interrupting", True)))))
            data.add((process, BP.contains, event))
        else:
            _place(data, process, event, payload.get("lane"))
        new_id = str(event)

    elif op == "add-gateway":
        kind = payload.get("kind")
        if kind not in GATEWAY_KINDS:
            return jsonify({"error": f"Unknown gateway kind: {kind}"}), 400
        process = _process_of_pool(data, payload.get("pool"))
        if process is None:
            return jsonify({"error": "add-gateway needs a participant with a process."}), 400
        gateway = _fresh(data, "gw")
        data.add((gateway, RDF.type, BPMN[kind]))
        if payload.get("label"):
            data.add((gateway, BP.name, Literal(payload["label"].strip())))
        _place(data, process, gateway, payload.get("lane"))
        new_id = str(gateway)

    elif op == "add-lane":
        process = _process_of_pool(data, payload.get("pool"))
        if process is None:
            return jsonify({"error": "add-lane needs a participant with a process."}), 400
        lane_set = data.value(process, BP.laneSet)
        if lane_set is None:
            lane_set = _fresh(data, "laneset")
            data.add((lane_set, RDF.type, BPMN.laneSet))
            data.add((process, BP.laneSet, lane_set))
        lane = _fresh(data, "lane")
        data.add((lane, RDF.type, BPMN.lane))
        data.add((lane, BP.name, Literal((payload.get("label") or "Lane").strip())))
        data.add((lane_set, BP.contains, lane))
        new_id = str(lane)

    elif op == "add-annotation":
        process = _process_of_pool(data, payload.get("pool"))
        if process is None:
            return jsonify({"error": "add-annotation needs a participant with a process."}), 400
        note = _fresh(data, "note")
        data.add((note, RDF.type, BPMN.textAnnotation))
        data.add((note, BP.text, Literal((payload.get("text") or "").strip())))
        data.add((process, BP.contains, note))
        anchor = payload.get("attachedTo")
        if anchor:
            link = _fresh(data, "assoc")
            data.add((link, RDF.type, BPMN.association))
            data.add((link, BP.sourceRef, URIRef(anchor)))
            data.add((link, BP.targetRef, note))
            data.add((process, BP.contains, link))
        new_id = str(note)

    elif op == "set-node-type":
        element = payload.get("element")
        kind = payload.get("kind")
        if not element or kind not in FLOW_NODE_KINDS:
            return jsonify({"error": f"set-node-type needs an element and a known kind: {kind}"}), 400
        node = URIRef(element)
        _retype(data, node, kind)
        data.remove((node, BP.name, None))
        if payload.get("label"):
            data.add((node, BP.name, Literal(payload["label"].strip())))
        if kind in EVENT_KINDS:
            _set_event_definition(data, node, payload.get("definition") or "")
            data.remove((node, BP.cancelActivity, None))
            if kind == "boundaryEvent":
                data.add((node, BP.cancelActivity,
                          Literal(bool(payload.get("interrupting", True)))))
            else:
                data.remove((node, BP.attachedToRef, None))
        new_id = element

    elif op == "set-loop":
        activity = payload.get("activity")
        loop = payload.get("loop") or ""
        if not activity:
            return jsonify({"error": "set-loop needs an activity."}), 400
        node = URIRef(activity)
        for old in list(data.objects(node, BP.loopCharacteristics)):
            data.remove((node, BP.loopCharacteristics, old))
            for triple in list(data.triples((old, None, None))):
                data.remove(triple)
        if loop in LOOP_KINDS:
            name, sequential = LOOP_KINDS[loop]
            characteristics = _fresh(data, "loop")
            data.add((characteristics, RDF.type, BPMN[name]))
            if sequential is not None:
                data.add((characteristics, BP.isSequential, Literal(sequential)))
            data.add((node, BP.loopCharacteristics, characteristics))
        elif loop:
            return jsonify({"error": f"Unknown repetition: {loop}"}), 400
        new_id = activity

    elif op == "connect":
        source = payload.get("source")
        target = payload.get("target")
        if not (source and target):
            return jsonify({"error": "connect needs a source and a target."}), 400
        if source == target:
            return jsonify({"error": "An activity cannot flow to itself."}), 400
        source_ref, target_ref = URIRef(source), URIRef(target)
        from_kinds = set(data.objects(source_ref, RDF.type))
        to_kinds = set(data.objects(target_ref, RDF.type))

        """What the line is follows from what it joins.

        One gesture, four kinds of connector: BPMN does not let the reader pick
        between them anyway, because the ends decide. A step to a step is a
        sequence flow, across a pool a message flow, a data object either way
        round a data association, and anything touching a text annotation an
        undirected association.
        """
        # An annotation says something about whatever it is attached to,
        # including a data object, so it is read before the data branch.
        if BPMN.textAnnotation in from_kinds or BPMN.textAnnotation in to_kinds:
            link = _fresh(data, "assoc")
            data.add((link, RDF.type, BPMN.association))
            data.add((link, BP.sourceRef, source_ref))
            data.add((link, BP.targetRef, target_ref))
            # It says something about a step; it does not point at it. "None" is
            # the direction BPMN draws as a plain dotted line.
            data.add((link, BP.associationDirection, Literal("None")))
            return _serialized(data, newId=str(link))

        if from_kinds & DATA_REFS or to_kinds & DATA_REFS:
            reading = bool(from_kinds & DATA_REFS)
            reference = source_ref if reading else target_ref
            step = target_ref if reading else source_ref
            # A data association joins data to a step, never data to data: two
            # boxes side by side say nothing about who reads either.
            if from_kinds & DATA_REFS and to_kinds & DATA_REFS:
                return jsonify(
                    {"error": "Two data objects can't connect — a step reads one and writes the other."}
                ), 400
            if not (set(data.objects(step, RDF.type)) & ACTIVITY_CLASSES):
                return jsonify(
                    {"error": "Data is read or written by an activity, not by an event or gateway."}
                ), 400
            made = _join_data(data, reference, step, "in" if reading else "out")
            if made is None:
                return jsonify({"error": "That step already uses this data."}), 400
            return _serialized(data, newId=made)

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

    elif op == "add-system":
        # An architecture for an activity that has none yet. pair:refinedBy is
        # authored on the activity, so the business layer is where a system is
        # called for - and until now the only way to answer was to write
        # `a beam:System` in Turtle by hand. Created empty on purpose: what it
        # holds is drawn on the architecture canvas, and an empty system says
        # plainly that the shape is not modelled yet.
        label = (payload.get("label") or "New AI system").strip()
        system = _fresh(data, "system")
        data.add((system, RDF.type, BEAM.Element))
        data.add((system, RDF.type, BEAM.System))
        data.add((system, RDFS.label, Literal(label)))
        activity = payload.get("activity")
        if activity:
            data.remove((URIRef(activity), PAIR.refinedBy, None))
            data.add((URIRef(activity), PAIR.refinedBy, system))
        new_id = str(system)

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
        # Free-standing when no activity is named: a store is a thing in its own
        # right, and one drawn per reader reads as several different stores.
        activity = payload.get("activity")
        direction = payload.get("direction")
        if activity and direction not in ("in", "out"):
            return jsonify({"error": "add-data needs a direction when it names an activity."}), 400
        classification = payload.get("classification") or ""
        if classification and classification not in data_class_names():
            return jsonify({"error": f"Unknown data classification: {classification}"}), 400

        shape = payload.get("shape") or "object"
        if shape not in ("object", "store"):
            return jsonify({"error": f"Unknown data shape: {shape}"}), 400

        node = URIRef(activity) if activity else None
        label = (payload.get("label") or "Data").strip()
        obj = _fresh(data, "store" if shape == "store" else "data")
        reference = _fresh(data, "dataref")
        # A document and a database are different things and BPMN draws them
        # differently - a folded page and a cylinder. The editor could write
        # only the page, so a database had to be hand-written in Turtle.
        if shape == "store":
            data.add((obj, RDF.type, BPMN.dataStore))
            data.add((reference, RDF.type, BPMN.dataStoreReference))
            data.add((reference, BP.dataStoreRef, obj))
        else:
            data.add((obj, RDF.type, BPMN.dataObject))
            data.add((reference, RDF.type, BPMN.dataObjectReference))
            data.add((reference, BP.dataObjectRef, obj))
        data.add((obj, BP.name, Literal(label)))
        # isCollection is declared on dataObject, not on dataStore - a store is
        # already a collection and BPMN gives it capacity instead.
        if payload.get("collection") and shape == "object":
            data.add((obj, BP.isCollection, Literal(True)))
        if classification:
            item = _fresh(data, "item")
            data.add((item, RDF.type, BPMN.itemDefinition))
            data.add((item, BP.structureRef, DPV[classification]))
            data.add((obj, BP.itemSubjectRef, item))

        # BPMN puts the association on the activity and gives it both ends; the
        # bridge query reads sourceRef/targetRef, so writing only one side would
        # draw an arrow that derives nothing.
        if node is None:
            new_id = str(reference)
            return _serialized(data, newId=new_id)
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

    elif op == "connect-data":
        """One data node, joined to another activity.

        The whole point of a store existing on its own: two activities that read
        the same one are two lines to one box, not two boxes that happen to
        share a name.
        """
        reference = payload.get("data")
        activity = payload.get("activity")
        direction = payload.get("direction")
        if not reference or not activity or direction not in ("in", "out"):
            return jsonify({"error": "connect-data needs data, an activity and a direction."}), 400
        made = _join_data(data, URIRef(reference), URIRef(activity), direction)
        if made is None:
            return jsonify({"error": "That activity already uses this data."}), 400
        new_id = made

    elif op == "set-condition":
        """The words on a branch out of a gateway.

        sBPMN models a conditionExpression as its own node and gives it no body
        property - BPMN puts the expression in XML mixed content, which sBPMN
        does not model - so the readable text goes on rdfs:label. That is the
        rule this follows rather than inventing a bp: term for it.
        """
        flow = payload.get("flow")
        if not flow:
            return jsonify({"error": "set-condition needs a flow."}), 400
        node = URIRef(flow)
        if (node, RDF.type, BPMN.sequenceFlow) not in data:
            return jsonify({"error": "Only a sequence flow carries a condition."}), 400
        text = (payload.get("text") or "").strip()
        existing = data.value(node, BP.conditionExpression)
        if not text:
            if existing is not None:
                data.remove((existing, None, None))
                data.remove((node, BP.conditionExpression, existing))
            new_id = str(node)
        else:
            if existing is None:
                existing = _fresh(data, "cond")
                data.add((existing, RDF.type, BPMN.expression))
                data.add((node, BP.conditionExpression, existing))
            data.remove((existing, RDFS.label, None))
            data.add((existing, RDFS.label, Literal(text)))
            new_id = str(existing)

    elif op == "remove-data":
        """Take one appearance of a data object or store off the diagram.

        The last appearance takes the thing itself with it, and its item
        definition - otherwise a classification stays in the graph describing
        something no longer drawn, and the next reader cannot see it to correct
        it. Any other appearance is just that: one box, drawn elsewhere.
        """
        reference = payload.get("reference")
        if not reference:
            return jsonify({"error": "remove-data needs a data reference."}), 400
        ref = URIRef(reference)
        kinds = set(data.objects(ref, RDF.type))
        if not kinds & DATA_REFS:
            return jsonify({"error": "That is not a data object or a data store."}), 400
        held = data.value(ref, BP.dataObjectRef) or data.value(ref, BP.dataStoreRef)

        doomed = {ref}
        for prop, side in ((BP.dataInputAssociation, BP.sourceRef),
                           (BP.dataOutputAssociation, BP.targetRef)):
            for association in list(data.subjects(side, ref)):
                doomed.add(association)
        for association in list(data.subjects(BP.targetRef, ref)):
            doomed.add(association)

        others = {
            appearance
            for appearance in set(data.subjects(BP.dataObjectRef, held))
            | set(data.subjects(BP.dataStoreRef, held))
            if appearance != ref
        }
        if held is not None and not others:
            doomed.add(held)
            item = data.value(held, BP.itemSubjectRef)
            if item is not None:
                doomed.add(item)

        for victim in doomed:
            for triple in list(data.triples((victim, None, None))):
                data.remove(triple)
            for triple in list(data.triples((None, None, victim))):
                data.remove(triple)
        new_id = None

    elif op == "set-association-direction":
        # The one thing the ends cannot say: whether the association points.
        # BPMN draws no head for "None", an open head at the target for "One",
        # and one at each end for "Both".
        link = payload.get("association")
        direction = payload.get("direction")
        if not link or direction not in ("None", "One", "Both"):
            return jsonify({"error": "set-association-direction needs None, One or Both."}), 400
        node = URIRef(link)
        if (node, RDF.type, BPMN.association) not in data:
            return jsonify({"error": "That is not an association."}), 400
        data.remove((node, BP.associationDirection, None))
        data.add((node, BP.associationDirection, Literal(direction)))
        new_id = str(node)

    elif op == "classify-data":
        reference = payload.get("reference")
        classification = payload.get("classification") or ""
        if not reference:
            return jsonify({"error": "classify-data needs a data reference."}), 400
        if classification and classification not in data_class_names():
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

    elif op == "set-system-context":
        """The domain and the purpose, stated from the business view.

        Declared rdfs:domain beam:System, and an activity refines exactly one
        system, so the join is 1:1 - none of the ambiguity the data bridge has.
        Written straight onto the system rather than derived from a business
        triple: a facet is an annotated base fact (R8), and propagating one as a
        facet is the thing the method does not do. Where it is *authored* is the
        business view; what it is a property of is the system.
        """
        system = payload.get("system")
        if not system:
            return jsonify({"error": "set-system-context needs a system."}), 400
        node = URIRef(system)
        if (node, RDF.type, BEAM.System) not in data:
            return jsonify({"error": "That is not an AI system in this graph."}), 400
        allowed = {row["facet"] for row in system_context_options()}
        facet = payload.get("facet")
        if facet not in allowed:
            return jsonify({"error": "set-system-context needs a facet the editor offers."}), 400
        value = (payload.get("value") or "").strip()
        if value and value not in context_values():
            return jsonify({"error": f"Unknown value for {facet}: {value}"}), 400
        data.remove((node, URIRef(facet), None))
        if value:
            data.add((node, URIRef(facet), URIRef(value)))
        new_id = str(node)

    elif op == "reorder-band":
        """Drop a pool or a lane at a place in the stack.

        Order was read off the name, so a diagram could only be stacked
        alphabetically and a participant could not be put where the reader needs
        it. The whole run of siblings is rewritten on every drop, so a document
        is either fully ordered or not ordered at all - a half-ordered stack
        would leave bands interleaving by name in a way nobody chose.
        """
        band = payload.get("band")
        to_index = payload.get("toIndex")
        if not band or not isinstance(to_index, int):
            return jsonify({"error": "reorder-band needs a band and a toIndex."}), 400
        node = URIRef(band)

        kinds = set(data.objects(node, RDF.type))
        if BPMN.participant in kinds:
            siblings = list(data.subjects(RDF.type, BPMN.participant))
        elif BPMN.lane in kinds:
            # Only the lanes it shares a pool with: a lane moving past one in
            # another participant is not a move anybody can see.
            holder = next(iter(data.subjects(BP.flowNodeRef, node)), None)
            siblings = [
                other for other in data.subjects(RDF.type, BPMN.lane)
                if next(iter(data.subjects(BP.flowNodeRef, other)), None) == holder
            ]
        else:
            return jsonify({"error": "Only a pool or a lane is stacked."}), 400

        def at(element):
            order = data.value(element, PAIR.bandOrder)
            label = str(data.value(element, BP.name) or data.value(element, RDFS.label) or element)
            if order is None:
                return (1, 0, label)
            return (0, int(order), label)

        ordered = sorted(siblings, key=at)
        if node not in ordered:
            return jsonify({"error": "That band is not in this diagram."}), 400
        if not 0 <= to_index < len(ordered):
            return jsonify({"error": "That is not a place in the stack."}), 400

        ordered.remove(node)
        ordered.insert(to_index, node)
        for position, element in enumerate(ordered):
            data.remove((element, PAIR.bandOrder, None))
            data.add((element, PAIR.bandOrder, Literal(position)))
        new_id = str(node)

    elif op == "realise-data":
        """Which architecture elements this business data object is.

        The analyst knows the data; the bridge has to find the element. Where
        they do know, saying so beats being found: pair:realisedBy names the
        element and the derivation stops being a guess. Written on the object
        rather than the reference, because a store drawn beside three readers is
        three references to one thing.
        """
        reference = payload.get("reference")
        if not reference:
            return jsonify({"error": "realise-data needs a data reference."}), 400
        ref = URIRef(reference)
        obj = data.value(ref, BP.dataObjectRef) or data.value(ref, BP.dataStoreRef) or ref
        elements = payload.get("elements") or []
        if not isinstance(elements, list):
            return jsonify({"error": "realise-data needs a list of elements."}), 400
        chosen = [URIRef(e) for e in elements if e]
        # The architectures the activities reading this object refine, and no
        # others: naming an element of a system this activity never touches
        # would mark something the business layer says nothing about.
        reachable = set()
        for held, end in ((BP.dataInputAssociation, BP.sourceRef),
                          (BP.dataOutputAssociation, BP.targetRef)):
            for activity, _p, association in data.triples((None, held, None)):
                if ref not in set(data.objects(association, end)):
                    continue
                for system in data.objects(activity, PAIR.refinedBy):
                    reachable |= set(data.objects(system, BEAM.hasResource))
        outside = [str(e) for e in chosen if e not in reachable]
        if outside:
            return jsonify({
                "error": "That element is not in an architecture this activity refines.",
            }), 400
        data.remove((obj, PAIR.realisedBy, None))
        for element in chosen:
            data.add((obj, PAIR.realisedBy, element))
        new_id = str(ref)

    elif op == "set-data-shape":
        """Turn a document into a database or back, keeping everything else.

        The classification and the associations are the parts that matter to a
        finding, so a change of shape must not disturb them - retyping is a
        statement about what the data is, not about what reads it."""
        reference = payload.get("reference")
        shape = payload.get("shape")
        if not reference or shape not in ("object", "store"):
            return jsonify({"error": "set-data-shape needs a reference and a shape."}), 400
        ref = URIRef(reference)
        target = data.value(ref, BP.dataObjectRef) or data.value(ref, BP.dataStoreRef)
        if target is None:
            return jsonify({"error": "That data reference points at nothing."}), 400

        for old_type in (BPMN.dataObjectReference, BPMN.dataStoreReference):
            data.remove((ref, RDF.type, old_type))
        for old_type in (BPMN.dataObject, BPMN.dataStore):
            data.remove((target, RDF.type, old_type))
        data.remove((ref, BP.dataObjectRef, None))
        data.remove((ref, BP.dataStoreRef, None))
        if shape == "store":
            data.add((ref, RDF.type, BPMN.dataStoreReference))
            data.add((ref, BP.dataStoreRef, target))
            data.add((target, RDF.type, BPMN.dataStore))
            # Not declared on dataStore, so it cannot travel with the retype.
            data.remove((target, BP.isCollection, None))
        else:
            data.add((ref, RDF.type, BPMN.dataObjectReference))
            data.add((ref, BP.dataObjectRef, target))
            data.add((target, RDF.type, BPMN.dataObject))
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
            obj = data.value(ref, BP.dataObjectRef) or data.value(ref, BP.dataStoreRef)
            item = data.value(obj, BP.itemSubjectRef) if obj is not None else None
            for victim in [ref, obj, item]:
                if victim is None:
                    continue
                for triple in list(data.triples((victim, None, None))):
                    data.remove(triple)
                for triple in list(data.triples((None, None, victim))):
                    data.remove(triple)

    elif op == "disconnect":
        # Deliberately not `delete`, which takes an element and everything it
        # owns: the same field holding an activity IRI by accident would take
        # the activity. This one refuses anything that is not a connector.
        flow = payload.get("flow")
        if not flow:
            return jsonify({"error": "disconnect needs a flow."}), 400
        node = URIRef(flow)
        if not set(data.objects(node, RDF.type)) & CONNECTOR_CLASSES:
            return jsonify({"error": "That is not a connector."}), 400
        for triple in list(data.triples((node, None, None))):
            data.remove(triple)
        # bp:outgoing and bp:incoming on the two ends point back at it.
        for triple in list(data.triples((None, None, node))):
            data.remove(triple)

    elif op == "rename":
        element = payload.get("element")
        if not element:
            return jsonify({"error": "rename needs an element."}), 400
        node = URIRef(element)
        # A data reference is an appearance of something; the name is on the
        # thing. Renaming the appearance would change nothing on screen.
        node = data.value(node, BP.dataObjectRef) or data.value(node, BP.dataStoreRef) or node
        data.remove((node, BP.name, None))
        if payload.get("label"):
            data.add((node, BP.name, Literal(payload["label"].strip())))

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
            for lane_set in data.objects(process, BP.laneSet):
                doomed.add(lane_set)
                doomed.update(data.objects(lane_set, BP.contains))
        # A boundary event has no life apart from the activity it is pinned to.
        for event in list(data.subjects(BP.attachedToRef, None)):
            if set(data.objects(event, BP.attachedToRef)) & doomed:
                doomed.add(event)
                doomed.update(data.objects(event, BP.eventDefinition))
        doomed.update(
            definition
            for victim in list(doomed)
            for definition in data.objects(victim, BP.eventDefinition)
        )
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
