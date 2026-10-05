from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, RDFS, Graph, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.graph_view import source_lines
from airiskkg.workbench.terms import display_label, short

BPMN = "https://sBPMN.github.io/2.0/classes#"
BP = "https://sBPMN.github.io/2.0/properties#"
DPV = "https://w3id.org/dpv#"


@lru_cache(maxsize=1)
def system_context_options() -> tuple[dict, ...]:
    """What the editor offers for a system's domain and purpose.

    Read off the graph like the data classifications, so the list and the writer
    cannot disagree. Domain is empty on purpose: DPV publishes sector extensions
    rather than sector concepts, so there is nothing to assign yet.
    """
    from airiskkg.assessment_runner import load_base_graph

    graph = load_base_graph()
    rows = []
    for option in graph.subjects(RDF.type, PAIR.SystemContextOption):
        facet = graph.value(option, PAIR.contextFacet)
        value = graph.value(option, PAIR.contextValue)
        label = graph.value(option, RDFS.label)
        if facet is None or value is None or label is None:
            continue
        rows.append({
            "facet": str(facet),
            "value": str(value),
            "label": str(label),
        })
    return tuple(sorted(rows, key=lambda row: (row["facet"], row["label"])))


def context_values() -> set[str]:
    """Every term the editor is allowed to write, so the writer can refuse the rest."""
    return {row["value"] for row in system_context_options()}


@lru_cache(maxsize=1)
def data_classifications() -> tuple[dict, ...]:
    """What the editor offers, read off the graph rather than typed here.
    """
    from airiskkg.assessment_runner import load_base_graph

    graph = load_base_graph()
    rows = []
    for option in graph.subjects(RDF.type, PAIR.DataClassificationOption):
        term = graph.value(option, PAIR.classifiesAs)
        label = graph.value(option, RDFS.label)
        if term is None or label is None:
            continue
        personal = graph.value(option, PAIR.meansPersonalData)
        rows.append({
            "id": str(term).removeprefix(DPV),
            "iri": str(term),
            "label": str(label),
            "personal": bool(personal) and bool(personal.toPython()),
        })
    # Personal first, then the two claims that it is not; alphabetical inside.
    return tuple(sorted(rows, key=lambda row: (not row["personal"], row["label"])))


def data_class_names() -> frozenset[str]:
    """The local names the editor will accept, for validating an edit."""
    return frozenset(row["id"] for row in data_classifications())


def _cls(name: str) -> URIRef:
    return URIRef(BPMN + name)


def _prop(name: str) -> URIRef:
    return URIRef(BP + name)

_ACTIVITY_CLASSES = (
    "userTask",
    "manualTask",
    "serviceTask",
    "scriptTask",
    "sendTask",
    "receiveTask",
    "businessRuleTask",
    "callActivity",
    "transaction",
    "adHocSubProcess",
    "parallelAdHocSubProcess",
    "sequentialAdHocSubProcess",
    "subProcess",
    "task",
)

_HUMAN_KINDS = {"userTask", "manualTask"}
_EVENT_CLASSES = (
    "boundaryEvent",
    "startEvent",
    "endEvent",
    "intermediateCatchEvent",
    "intermediateThrowEvent",
    "implicitThrowEvent",
)

_THROWING = {"endEvent", "intermediateThrowEvent", "implicitThrowEvent"}

_GATEWAY_CLASSES = (
    "exclusiveEventBasedGateway",
    "parallelEventBasedGateway",
    "eventBasedGateway",
    "exclusiveGateway",
    "parallelGateway",
    "inclusiveGateway",
    "complexGateway",
)

_EVENT_DEFINITIONS = (
    "messageEventDefinition",
    "timerEventDefinition",
    "errorEventDefinition",
    "escalationEventDefinition",
    "signalEventDefinition",
    "conditionalEventDefinition",
    "compensateEventDefinition",
    "cancelEventDefinition",
    "terminateEventDefinition",
    "linkEventDefinition",
)


def _label_of(graph: Graph, node: URIRef) -> str:
    name = graph.value(node, _prop("name")) or graph.value(node, RDFS.label)
    return str(name) if name else display_label(short(node))


def _types(graph: Graph, node: URIRef) -> set[str]:
    return {short(t) for t in graph.objects(node, RDF.type)}


def _first_kind(types: set[str], candidates: tuple[str, ...], fallback: str) -> str:
    for candidate in candidates:
        if candidate in types:
            return candidate
    return fallback


def _activity_kind(graph: Graph, activity: URIRef) -> str:
    return _first_kind(_types(graph, activity), _ACTIVITY_CLASSES, "activity")


def _flag(graph: Graph, node: URIRef, name: str, default: bool = False) -> bool:
    value = graph.value(node, _prop(name))
    return default if value is None else bool(value.toPython())


@lru_cache(maxsize=1)
def _data_classes() -> frozenset:
    """Every class that counts as beam:Data, resolved once.

    load_base_graph() copies the knowledge base on each call, so asking it per
    resource cost seconds per request and slowed the browser suites enough to
    time them out.
    """
    from airiskkg.assessment_runner import load_base_graph

    ontology = load_base_graph()
    kinds = {BEAM.Data}
    for kind in set(ontology.subjects(RDFS.subClassOf, None)):
        if BEAM.Data in set(ontology.transitive_objects(kind, RDFS.subClassOf)):
            kinds.add(kind)
    return frozenset(kinds)


def _is_data(graph: Graph, resource: URIRef) -> bool:
    """Personal data is a property of data. facet:hasPersonalDataCategory is
    declared rdfs:domain beam:Data, and the bridge targets the same, so the
    picker must not offer a model or a prompt the bridge would then ignore."""
    return bool(set(graph.objects(resource, RDF.type)) & _data_classes())


def _resolve_data(graph: Graph, reference: URIRef) -> dict:
    store = graph.value(reference, _prop("dataStoreRef"))
    target = store or graph.value(reference, _prop("dataObjectRef")) or reference
    types = _types(graph, reference) | _types(graph, target)
    item = graph.value(target, _prop("itemSubjectRef"))
    kinds = [short(k) for k in graph.objects(item, _prop("structureRef"))] if item else []
    collection = graph.value(target, _prop("isCollection"))
    state = graph.value(target, _prop("dataState")) or graph.value(reference, _prop("dataState"))
    return {
        "id": str(reference),
        "label": _label_of(graph, target),
        # A store is drawn as a cylinder and an object as a folded page, so
        # the shape has to survive the trip rather than be guessed here.
        "store": bool(store) or "dataStore" in types or "dataStoreReference" in types,
        "collection": bool(collection and collection.toPython()),
        "input": "dataInput" in types,
        "output": "dataOutput" in types,
        "state": _label_of(graph, state) if state is not None else None,
        "item": str(item) if item is not None else None,
        "kinds": sorted(kinds),
        # The thing itself, not the appearance: a store drawn beside three
        # readers is three references to one object, and what it is annotated
        # with belongs to the object.
        "object": str(target),
        "realisedBy": sorted(str(e) for e in graph.objects(target, PAIR.realisedBy)),
    }


def _refined_systems(graph: Graph) -> list[dict]:
    """Every architecture a step of this process refines, with what it says
    about itself."""
    facets = {row["facet"] for row in system_context_options()}
    rows = []
    for system in sorted(set(graph.objects(None, PAIR.refinedBy)), key=str):
        entry = {"id": str(system), "label": _label_of(graph, system)}
        for facet in sorted(facets):
            entry[short(URIRef(facet))] = sorted(
                str(value) for value in graph.objects(system, URIRef(facet))
            )
        rows.append(entry)
    return sorted(rows, key=lambda row: (row["label"], row["id"]))


def _data_nodes(graph: Graph) -> list[dict]:
    """Every data reference in the model once, with everything it is joined to.
    """
    nodes: dict[str, dict] = {}
    for kind in ("dataObjectReference", "dataStoreReference"):
        for reference in graph.subjects(RDF.type, _cls(kind)):
            entry = _resolve_data(graph, reference)
            entry["links"] = []
            nodes[str(reference)] = entry

    ends = (
        (_prop("dataInputAssociation"), _prop("sourceRef"), "in"),
        (_prop("dataOutputAssociation"), _prop("targetRef"), "out"),
    )
    for held, end, direction in ends:
        for activity, _p, association in graph.triples((None, held, None)):
            for reference in graph.objects(association, end):
                entry = nodes.get(str(reference))
                if entry is None:
                    continue
                entry["links"].append({
                    "activity": str(activity),
                    "direction": direction,
                    "association": str(association),
                })

    # Which architecture elements this data object could be. The analyst does
    # not know the architecture's names, so the editor has to offer them rather
    # than ask - and only from the systems the activities reading it refine,
    # because anything else is not what this activity touches.
    for entry in nodes.values():
        systems = {
            system
            for link in entry["links"]
            for system in graph.objects(URIRef(link["activity"]), PAIR.refinedBy)
        }
        candidates = {
            resource
            for system in systems
            for resource in graph.objects(system, BEAM.hasResource)
            if _is_data(graph, resource)
        }
        entry["candidates"] = sorted(
            ({"id": str(c), "label": _label_of(graph, c)} for c in candidates),
            key=lambda row: (row["label"], row["id"]),
        )
    return sorted(nodes.values(), key=lambda row: (row["label"], row["id"]))


def _data_around(graph: Graph, activity: URIRef) -> tuple[list[dict], list[dict]]:
    def resolve(reference: URIRef) -> dict:
        return _resolve_data(graph, reference)

    reads = [
        resolve(source)
        for association in graph.objects(activity, _prop("dataInputAssociation"))
        for source in graph.objects(association, _prop("sourceRef"))
    ]
    writes = [
        resolve(target)
        for association in graph.objects(activity, _prop("dataOutputAssociation"))
        for target in graph.objects(association, _prop("targetRef"))
    ]
    return reads, writes


def _performers(graph: Graph, activity: URIRef) -> list[str]:
    names = []
    for role in graph.objects(activity, _prop("resourceRole")):
        human = any(
            short(t) in {"humanPerformer", "potentialOwner"} for t in graph.objects(role, RDF.type)
        )
        if human:
            names.append(_label_of(graph, role))
    return sorted(set(names))


def _markers(graph: Graph, activity: URIRef, kind: str) -> dict:
    """The glyph row along the bottom edge of an activity box."""
    loop = None
    for characteristics in graph.objects(activity, _prop("loopCharacteristics")):
        types = _types(graph, characteristics)
        if "multiInstanceLoopCharacteristics" in types:
            loop = "multiSequential" if _flag(graph, characteristics, "isSequential") \
                else "multiParallel"
        elif "standardLoopCharacteristics" in types:
            loop = "standard"
    types = _types(graph, activity)
    return {
        "loop": loop,
        "compensation": _flag(graph, activity, "isForCompensation"),
        "adHoc": any(t.endswith("dHocSubProcess") for t in types),
        "transaction": kind == "transaction",
        "call": kind == "callActivity",
        "eventSubProcess": _flag(graph, activity, "triggeredByEvent"),
    }


def _event_definition(graph: Graph, event: URIRef) -> tuple[str | None, str | None]:
    """Which trigger the circle carries, and what it names."""
    for definition in (
        *graph.objects(event, _prop("eventDefinition")),
        *graph.objects(event, _prop("eventDefinitionRef")),
    ):
        types = _types(graph, definition)
        for candidate in _EVENT_DEFINITIONS:
            if candidate in types:
                referenced = (
                    graph.value(definition, _prop("messageRef"))
                    or graph.value(definition, _prop("errorRef"))
                    or graph.value(definition, _prop("signalRef"))
                    or graph.value(definition, _prop("escalationRef"))
                )
                return (
                    candidate[: -len("EventDefinition")],
                    _label_of(graph, referenced) if referenced is not None else None,
                )
    # A send/receive-style event may name its message without a definition node.
    message = graph.value(event, _prop("messageRef"))
    if message is not None:
        return "message", _label_of(graph, message)
    return None, None


def _flow_nodes(graph: Graph, classes: tuple[str, ...]) -> list[URIRef]:
    found: list[URIRef] = []
    for name in classes:
        found.extend(graph.subjects(RDF.type, _cls(name)))
    return sorted(set(found), key=str)


def _direct_process(graph: Graph, node: URIRef) -> str | None:
    """The process that lists this node directly."""
    for holder in graph.subjects(_prop("contains"), node):
        if (holder, RDF.type, _cls("process")) in graph:
            return str(holder)
    return None


def _ordered(graph: Graph, nodes: list[URIRef]) -> list[URIRef]:
    """Topological order over sequence flow, ties broken by label so a redraw
    of the same model puts the same box in the same place."""
    successors: dict[URIRef, set[URIRef]] = {n: set() for n in nodes}
    incoming: dict[URIRef, int] = {n: 0 for n in nodes}
    for flow in graph.subjects(RDF.type, _cls("sequenceFlow")):
        for source in graph.objects(flow, _prop("sourceRef")):
            for target in graph.objects(flow, _prop("targetRef")):
                if source in successors and target in incoming and target not in successors[source]:
                    successors[source].add(target)
                    incoming[target] += 1

    ready = sorted((n for n in nodes if incoming[n] == 0), key=lambda n: _label_of(graph, n))
    ordered: list[URIRef] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for nxt in sorted(successors[current], key=lambda n: _label_of(graph, n)):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=lambda n: _label_of(graph, n))

    ordered.extend(n for n in nodes if n not in ordered)
    return ordered


def _band_key(graph: Graph, band: URIRef, label: str) -> tuple:
    """Where a band sits in the stack. Ordered bands lead, in their order; the
    rest keep the alphabetical place they had before one could be moved."""
    order = graph.value(band, PAIR.bandOrder)
    if order is None:
        return (1, 0, label)
    try:
        return (0, int(order), label)
    except (TypeError, ValueError):
        return (1, 0, label)


def _participants(graph: Graph) -> list[dict]:
    rows = []
    for participant in graph.subjects(RDF.type, _cls("participant")):
        process = graph.value(participant, _prop("processRef"))
        multiplicity = graph.value(participant, _prop("participantMultiplicity"))
        rows.append(
            {
                "id": str(participant),
                "label": _label_of(graph, participant),
                "process": str(process) if process is not None else None,
                "multiple": multiplicity is not None,
                "order": _band_key(graph, participant, _label_of(graph, participant)),
            }
        )
    rows.sort(key=lambda row: row["order"])
    for row in rows:
        del row["order"]
    return rows


def _sequence_flows(graph: Graph) -> list[dict]:
    """What the diagram must actually draw."""
    defaults = {
        str(flow) for node in graph.subjects() for flow in graph.objects(node, _prop("default"))
    }
    flows = []
    for flow in graph.subjects(RDF.type, _cls("sequenceFlow")):
        source = graph.value(flow, _prop("sourceRef"))
        target = graph.value(flow, _prop("targetRef"))
        if source is None or target is None:
            continue
        condition = graph.value(flow, _prop("conditionExpression"))
        name = graph.value(flow, _prop("name")) or graph.value(flow, RDFS.label)
        flows.append(
            {
                "id": str(flow),
                "label": str(name) if name else None,
                "source": str(source),
                "target": str(target),
                "default": str(flow) in defaults,
                # sBPMN models an expression as mixed content and gives it no
                # body property, so the readable condition is carried by a
                # plain rdfs:label rather than a bp: term that does not exist.
                "condition": _label_of(graph, condition) if condition is not None else None,
            }
        )
    return sorted(flows, key=lambda row: row["id"])


def _message_flows(graph: Graph) -> list[dict]:
    flows = []
    for flow in graph.subjects(RDF.type, _cls("messageFlow")):
        source = graph.value(flow, _prop("sourceRef"))
        target = graph.value(flow, _prop("targetRef"))
        if source is None or target is None:
            continue
        message = graph.value(flow, _prop("messageRef"))
        flows.append(
            {
                "id": str(flow),
                "label": _label_of(graph, flow),
                "source": str(source),
                "target": str(target),
                "message": _label_of(graph, message) if message is not None else None,
            }
        )
    return sorted(flows, key=lambda row: row["label"])


def _lanes(graph: Graph) -> list[dict]:
    """Lanes with the nodes they hold, so the canvas can band a pool."""
    owner: dict[URIRef, URIRef] = {}
    for process in graph.subjects(RDF.type, _cls("process")):
        for lane_set in graph.objects(process, _prop("laneSet")):
            for lane in (
                *graph.objects(lane_set, _prop("contains")),
                *graph.objects(lane_set, _prop("lane")),
            ):
                owner[lane] = process

    parent: dict[URIRef, URIRef] = {}
    for lane in graph.subjects(RDF.type, _cls("lane")):
        for child_set in graph.objects(lane, _prop("childLaneSet")):
            for child in (
                *graph.objects(child_set, _prop("contains")),
                *graph.objects(child_set, _prop("lane")),
            ):
                parent[child] = lane
                owner.setdefault(child, owner.get(lane))

    rows = []
    for lane in graph.subjects(RDF.type, _cls("lane")):
        members = [str(n) for n in graph.objects(lane, _prop("flowNodeRef"))]
        process = owner.get(lane)
        rows.append(
            {
                "id": str(lane),
                "label": _label_of(graph, lane),
                "process": str(process) if process is not None else None,
                "parent": str(parent[lane]) if lane in parent else None,
                "members": sorted(members),
                "order": _band_key(graph, lane, _label_of(graph, lane)),
            }
        )
    rows.sort(key=lambda row: row["order"])
    for row in rows:
        del row["order"]
    return rows


def _artifacts(graph: Graph) -> tuple[list[dict], list[dict]]:
    """Text annotations and groups, plus the dotted associations tying them to what they comment on."""
    notes = []
    for note in graph.subjects(RDF.type, _cls("textAnnotation")):
        body = graph.value(note, _prop("text"))
        notes.append(
            {
                "id": str(note),
                "kind": "textAnnotation",
                "text": str(body) if body is not None else _label_of(graph, note),
                "process": _direct_process(graph, note),
            }
        )
    for cluster in graph.subjects(RDF.type, _cls("group")):
        category = graph.value(cluster, _prop("categoryValueRef"))
        notes.append(
            {
                "id": str(cluster),
                "kind": "group",
                "text": _label_of(graph, category) if category is not None
                else _label_of(graph, cluster),
                "members": sorted(str(m) for m in graph.objects(cluster, _prop("contains"))),
                "process": _direct_process(graph, cluster),
            }
        )

    links = []
    for link in graph.subjects(RDF.type, _cls("association")):
        source = graph.value(link, _prop("sourceRef"))
        target = graph.value(link, _prop("targetRef"))
        if source is None or target is None:
            continue
        direction = graph.value(link, _prop("associationDirection"))
        links.append(
            {
                "id": str(link),
                "source": str(source),
                "target": str(target),
                "direction": short(direction) if direction is not None else "None",
            }
        )
    return sorted(notes, key=lambda row: row["id"]), sorted(links, key=lambda row: row["id"])


def _stamp_lines(view: dict, ttl_text: str | None) -> dict:
    """Say where each business element was written."""
    if not ttl_text:
        return view
    lines = source_lines(ttl_text)
    for key in (
        "participants", "processes", "activities", "lanes", "messageFlows",
        "sequenceFlows", "events", "gateways", "artifacts",
    ):
        for row in view.get(key, []):
            line = lines.get(row.get("id"))
            if line:
                row["line"] = line
    for row in view.get("activities", []):
        for reference in [*row.get("reads", []), *row.get("writes", [])]:
            line = lines.get(reference.get("id"))
            if line:
                reference["line"] = line
    return view


def process_view(graph: Graph, ttl_text: str | None = None) -> dict:
    lanes = _lanes(graph)
    lane_of: dict[str, str] = {}
    lane_name_of: dict[str, str] = {}
    for lane in lanes:
        for member in lane["members"]:
            lane_of[member] = lane["id"]
            lane_name_of[member] = lane["label"]

    pool_of: dict[URIRef, str] = {}
    for participant in graph.subjects(RDF.type, _cls("participant")):
        process = graph.value(participant, _prop("processRef"))
        if process is not None:
            pool_of[process] = _label_of(graph, participant)

    activities = _ordered(graph, _flow_nodes(graph, _ACTIVITY_CLASSES))
    events = _ordered(graph, _flow_nodes(graph, _EVENT_CLASSES))
    gateways = _ordered(graph, _flow_nodes(graph, _GATEWAY_CLASSES))

    activity_set = set(activities)
    nestable = activity_set | set(events) | set(gateways)
    parent_of: dict[URIRef, URIRef] = {}
    for container in activities:
        for child in graph.objects(container, _prop("contains")):
            if child in nestable and child != container:
                parent_of[child] = container

    boundary_of: dict[str, list[str]] = {}
    for event in events:
        host = graph.value(event, _prop("attachedToRef"))
        if host is not None:
            boundary_of.setdefault(str(host), []).append(str(event))

    rows = []
    for activity in activities:
        kind = _activity_kind(graph, activity)
        reads, writes = _data_around(graph, activity)
        parent = parent_of.get(activity)
        rows.append(
            {
                "id": str(activity),
                "label": _label_of(graph, activity),
                "kind": kind,
                "human": kind in _HUMAN_KINDS,
                "lane": lane_name_of.get(str(activity)),
                "laneId": lane_of.get(str(activity)),
                "performers": _performers(graph, activity),
                "reads": reads,
                "writes": writes,
                "refines": [str(s) for s in graph.objects(activity, PAIR.refinedBy)],
                "calls": [str(c) for c in graph.objects(activity, _prop("calledElement"))],
                "markers": _markers(graph, activity, kind),
                "boundary": sorted(boundary_of.get(str(activity), [])),
                "parent": str(parent) if parent is not None else None,
                "children": sorted(str(c) for c, p in parent_of.items() if p == activity),
                "process": _direct_process(graph, activity),
            }
        )

    event_rows = []
    for event in events:
        types = _types(graph, event)
        kind = _first_kind(types, _EVENT_CLASSES, "event")
        definition, referenced = _event_definition(graph, event)
        host = graph.value(event, _prop("attachedToRef"))
        name = graph.value(event, _prop("name")) or graph.value(event, RDFS.label)
        event_rows.append(
            {
                "id": str(event),
                "label": str(name) if name else "",
                "kind": kind,
                "throwing": kind in _THROWING,
                "definition": definition,
                "definitionLabel": referenced,
                # A boundary event that interrupts is a solid double ring; a
                # non-interrupting one is dashed, and BPMN reads them oppositely.
                "interrupting": _flag(graph, event, "cancelActivity", True)
                if kind == "boundaryEvent"
                else _flag(graph, event, "isInterrupting", True),
                "attachedTo": str(host) if host is not None else None,
                "lane": lane_name_of.get(str(event)),
                "laneId": lane_of.get(str(event)),
                "parent": str(parent_of[event]) if event in parent_of else None,
                "process": _direct_process(graph, event),
            }
        )

    gateway_rows = []
    for gateway in gateways:
        types = _types(graph, gateway)
        kind = _first_kind(types, _GATEWAY_CLASSES, "gateway")
        direction = graph.value(gateway, _prop("gatewayDirection"))
        name = graph.value(gateway, _prop("name")) or graph.value(gateway, RDFS.label)
        gateway_rows.append(
            {
                "id": str(gateway),
                "label": str(name) if name else "",
                "kind": kind,
                "direction": short(direction) if direction is not None else None,
                "instantiate": _flag(graph, gateway, "instantiate"),
                "lane": lane_name_of.get(str(gateway)),
                "laneId": lane_of.get(str(gateway)),
                "parent": str(parent_of[gateway]) if gateway in parent_of else None,
                "process": _direct_process(graph, gateway),
            }
        )

    artifacts, associations = _artifacts(graph)

    processes = []
    for process in graph.subjects(RDF.type, _cls("process")):
        executable = graph.value(process, _prop("isExecutable"))
        held = set(graph.objects(process, _prop("contains")))
        processes.append(
            {
                "id": str(process),
                "label": _label_of(graph, process),
                "participant": pool_of.get(process),
                "isExecutable": None if executable is None else bool(executable.toPython()),
                "activities": [str(a) for a in held & activity_set],
            }
        )
    processes.sort(key=lambda p: (p["participant"] or "", p["label"]))

    refined_systems = {
        str(system): _label_of(graph, system)
        for activity in activities
        for system in graph.objects(activity, PAIR.refinedBy)
    }
    unrefined = [
        {"id": str(system), "label": _label_of(graph, system)}
        for system in graph.subjects(RDF.type, BEAM.System)
        if str(system) not in refined_systems
    ]

    return _stamp_lines({
        "participants": _participants(graph),
        "processes": processes,
        "lanes": lanes,
        "activities": rows,
        "events": event_rows,
        "gateways": gateway_rows,
        "sequenceFlows": _sequence_flows(graph),
        "messageFlows": _message_flows(graph),
        "dataNodes": _data_nodes(graph),
        "artifacts": artifacts,
        "associations": associations,
        "unrefinedSystems": unrefined,
        # The situational context of each architecture a step refines, beside
        # the options the editor may write. Stated from here because the analyst
        # knows the sector and the purpose; held on the system because that is
        # what facet:hasDomain and facet:hasPurpose are declared about.
        "refinedSystems": _refined_systems(graph),
        "contextOptions": list(system_context_options()),
        "stats": {
            "participants": len(_participants(graph)),
            "processes": len(processes),
            "activities": len(rows),
            "events": len(event_rows),
            "gateways": len(gateway_rows),
            "lanes": len(lanes),
            "refined": sum(1 for r in rows if r["refines"]),
            "humanSteps": sum(1 for r in rows if r["human"]),
        },
    }, ttl_text)
