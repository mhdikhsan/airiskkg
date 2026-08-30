from __future__ import annotations

from rdflib import RDF, RDFS, Graph, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.graph_view import source_lines
from airiskkg.workbench.terms import display_label, short

BPMN = "https://sBPMN.github.io/2.0/classes#"
BP = "https://sBPMN.github.io/2.0/properties#"
DATA_CLASSES = {
    "PersonalData": "Personal data",
    "SensitivePersonalData": "Sensitive personal data",
    "SpecialCategoryPersonalData": "Special category personal data",
    "PseudonymisedData": "Pseudonymised (still personal)",
    "AnonymisedData": "Anonymised - not personal",
    "NonPersonalData": "Not personal",
}


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
    "subProcess",
    "task",
)

_HUMAN_KINDS = {"userTask", "manualTask"}


def _label_of(graph: Graph, node: URIRef) -> str:
    name = graph.value(node, _prop("name")) or graph.value(node, RDFS.label)
    return str(name) if name else display_label(short(node))


def _activity_kind(graph: Graph, activity: URIRef) -> str:
    types = {short(t) for t in graph.objects(activity, RDF.type)}
    for candidate in _ACTIVITY_CLASSES:
        if candidate in types:
            return candidate
    return "activity"


def _data_around(graph: Graph, activity: URIRef) -> tuple[list[dict], list[dict]]:
    def resolve(reference: URIRef) -> dict:
        store = graph.value(reference, _prop("dataStoreRef"))
        target = store or graph.value(reference, _prop("dataObjectRef")) or reference
        types = {short(t) for t in graph.objects(reference, RDF.type)} | {
            short(t) for t in graph.objects(target, RDF.type)
        }
        item = graph.value(target, _prop("itemSubjectRef"))
        kinds = [short(k) for k in graph.objects(item, _prop("structureRef"))] if item else []
        collection = graph.value(target, _prop("isCollection"))
        return {
            "id": str(reference),
            "label": _label_of(graph, target),
            # A store is drawn as a cylinder and an object as a folded page, so
            # the shape has to survive the trip rather than be guessed here.
            "store": bool(store) or "dataStore" in types or "dataStoreReference" in types,
            "collection": bool(collection and collection.toPython()),
            "item": str(item) if item is not None else None,
            "kinds": sorted(kinds),
        }

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


def _ordered(graph: Graph, activities: list[URIRef]) -> list[URIRef]:
    successors: dict[URIRef, set[URIRef]] = {a: set() for a in activities}
    incoming: dict[URIRef, int] = {a: 0 for a in activities}
    for flow in graph.subjects(RDF.type, _cls("sequenceFlow")):
        for source in graph.objects(flow, _prop("sourceRef")):
            for target in graph.objects(flow, _prop("targetRef")):
                if source in successors and target in incoming and target not in successors[source]:
                    successors[source].add(target)
                    incoming[target] += 1

    ready = sorted((a for a in activities if incoming[a] == 0), key=lambda a: _label_of(graph, a))
    ordered: list[URIRef] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for nxt in sorted(successors[current], key=lambda a: _label_of(graph, a)):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=lambda a: _label_of(graph, a))

    ordered.extend(a for a in activities if a not in ordered)
    return ordered


def _participants(graph: Graph) -> list[dict]:
    rows = []
    for participant in graph.subjects(RDF.type, _cls("participant")):
        process = graph.value(participant, _prop("processRef"))
        rows.append(
            {
                "id": str(participant),
                "label": _label_of(graph, participant),
                "process": str(process) if process is not None else None,
            }
        )
    return sorted(rows, key=lambda row: row["label"])


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


def _stamp_lines(view: dict, ttl_text: str | None) -> dict:
    """Say where each business element was written.

    Without this a click on a pool or an activity had nowhere to go: the source
    map is fed from /api/graph, which knows the architecture only, so selecting
    anything on the business canvas quietly did nothing."""
    if not ttl_text:
        return view
    lines = source_lines(ttl_text)
    for key in ("participants", "processes", "activities", "lanes", "messageFlows"):
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
    lane_of: dict[URIRef, str] = {}
    lanes: list[dict] = []
    for lane in graph.subjects(RDF.type, _cls("lane")):
        members = [n for n in graph.objects(lane, _prop("flowNodeRef"))]
        lanes.append({"id": str(lane), "label": _label_of(graph, lane), "members": len(members)})
        for node in members:
            lane_of[node] = _label_of(graph, lane)

    pool_of: dict[URIRef, str] = {}
    for participant in graph.subjects(RDF.type, _cls("participant")):
        process = graph.value(participant, _prop("processRef"))
        if process is not None:
            pool_of[process] = _label_of(graph, participant)

    activities: list[URIRef] = []
    for name in _ACTIVITY_CLASSES:
        activities.extend(graph.subjects(RDF.type, _cls(name)))
    activities = _ordered(graph, sorted(set(activities), key=str))
    parent_of: dict[URIRef, URIRef] = {}
    activity_set = set(activities)
    for container in activities:
        for child in graph.objects(container, _prop("contains")):
            if child in activity_set and child != container:
                parent_of[child] = container

    rows = []
    for activity in activities:
        kind = _activity_kind(graph, activity)
        reads, writes = _data_around(graph, activity)
        refines = [str(s) for s in graph.objects(activity, PAIR.refinedBy)]
        children = [str(c) for c, p in parent_of.items() if p == activity]
        parent = parent_of.get(activity)
        rows.append(
            {
                "id": str(activity),
                "label": _label_of(graph, activity),
                "kind": kind,
                "human": kind in _HUMAN_KINDS,
                "lane": lane_of.get(activity),
                "performers": _performers(graph, activity),
                "reads": reads,
                "writes": writes,
                "refines": refines,
                "parent": str(parent) if parent is not None else None,
                "children": sorted(children),
                "process": next(
                    (
                        str(p)
                        for p in graph.subjects(_prop("contains"), activity)
                        if (p, RDF.type, _cls("process")) in graph
                    ),
                    None,
                ),
            }
        )

    processes = []
    for process in graph.subjects(RDF.type, _cls("process")):
        executable = graph.value(process, _prop("isExecutable"))
        processes.append(
            {
                "id": str(process),
                "label": _label_of(graph, process),
                "participant": pool_of.get(process),
                "isExecutable": None if executable is None else bool(executable.toPython()),
                "activities": [
                    str(a) for a in graph.objects(process, _prop("contains")) if a in set(activities)
                ],
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
        "messageFlows": _message_flows(graph),
        "unrefinedSystems": unrefined,
        "stats": {
            "participants": len(_participants(graph)),
            "processes": len(processes),
            "activities": len(rows),
            "refined": sum(1 for r in rows if r["refines"]),
            "humanSteps": sum(1 for r in rows if r["human"]),
        },
    }, ttl_text)
