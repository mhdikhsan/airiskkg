"""A submitted BPMN process, in the shape the workbench renders.

Deliberately not a diagram. sBPMN carries everything needed to draw one, but a
faithful BPMN renderer is a second `graph.js` and the licence of the one good
off-the-shelf option puts a permanent watermark in the page. What a risk
assessment actually needs from a process is narrower and reads better as a
list: which activity, in whose lane, what it reads and writes, what follows it,
and which of them is an AI capability.

Activities come back in flow order, so the reader sees the process rather than
an alphabetical set. Order is derived from `pair:businessFollows` when the
derivation has run, and falls back to declaration order when it has not.
"""

from __future__ import annotations

from rdflib import RDF, RDFS, Graph, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.workbench.terms import display_label, short

BPMN = "https://sBPMN.github.io/2.0/classes#"
BP = "https://sBPMN.github.io/2.0/properties#"


def _cls(name: str) -> URIRef:
    return URIRef(BPMN + name)


def _prop(name: str) -> URIRef:
    return URIRef(BP + name)


# Task kinds the workbench distinguishes, and what each says about autonomy.
# A userTask is a person doing the work; a serviceTask is an automated call.
# That distinction is the per-activity autonomy signal the facet layer never
# had a place to record.
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
    """What the activity reads and writes, resolved through BPMN's two hops.

    A data object reference points at a data object, which points at an item
    definition, which is where a DPV concept is attached. The UI shows the last
    of those, because that is the annotation a business analyst actually makes.
    """

    def resolve(reference: URIRef) -> dict:
        target = graph.value(reference, _prop("dataObjectRef")) or graph.value(
            reference, _prop("dataStoreRef")
        ) or reference
        item = graph.value(target, _prop("itemSubjectRef"))
        kinds = [short(k) for k in graph.objects(item, _prop("structureRef"))] if item else []
        return {
            "id": str(reference),
            "label": _label_of(graph, target),
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
    """Flow order, computed here rather than read from `pair:businessFollows`.

    The derived relation would do it, but only after an assessment has run, and
    a view that reads correctly only once the pipeline has been invoked is a
    view that reads wrongly the rest of the time - the first render would be
    alphabetical, which looks like a process in no particular order.

    Sequence flows are typed on the way in for the usual reason: bp:sourceRef
    and bp:targetRef are declared on five classes, and following them untyped
    would thread message flows and data associations into the ordering.

    Kahn's algorithm, ties broken by label so the result is stable. Anything
    left over - a cycle, or an activity no flow touches - keeps its place at the
    end rather than disappearing.
    """
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


def process_view(graph: Graph) -> dict:
    """Every process in the graph, with its lanes, activities and AI refinements."""
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

    rows = []
    for activity in activities:
        kind = _activity_kind(graph, activity)
        reads, writes = _data_around(graph, activity)
        refines = [str(s) for s in graph.objects(activity, PAIR.refinedBy)]
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
            }
        )

    refined_systems = {
        str(system): _label_of(graph, system)
        for activity in activities
        for system in graph.objects(activity, PAIR.refinedBy)
    }
    # A system present in the architecture that no activity claims. Worth saying:
    # it is assessed with no business context at all, which is the case the whole
    # layer exists to improve.
    unrefined = [
        {"id": str(system), "label": _label_of(graph, system)}
        for system in graph.subjects(RDF.type, BEAM.System)
        if str(system) not in refined_systems
    ]

    return {
        "processes": processes,
        "lanes": lanes,
        "activities": rows,
        "unrefinedSystems": unrefined,
        "stats": {
            "processes": len(processes),
            "activities": len(rows),
            "refined": sum(1 for r in rows if r["refines"]),
            "humanSteps": sum(1 for r in rows if r["human"]),
        },
    }
