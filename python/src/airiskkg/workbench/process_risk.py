from __future__ import annotations

from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.graph_view import _members_of
from airiskkg.workbench.risk_lens import risk_lens
from airiskkg.workbench.terms import label

_BP = Namespace("https://sBPMN.github.io/2.0/properties#")


def _name(graph: Graph, node: URIRef) -> str:
    value = graph.value(node, _BP.name)
    return str(value) if value else label(graph, node)


def _lane_of(graph: Graph, activity: URIRef) -> str | None:
    for lane in graph.subjects(_BP.flowNodeRef, activity):
        return _name(graph, lane)
    return None


def _participant_of(graph: Graph, activity: URIRef) -> str | None:
    for process in graph.subjects(_BP.contains, activity):
        for participant in graph.subjects(_BP.processRef, process):
            return _name(graph, participant)
    return None


def _concern_view(group: dict) -> dict:
    return {
        "key": group["key"],
        "label": group["label"],
        "description": group["description"],
        "domains": [domain["label"] for domain in group["riskDomains"]],
        "why": group["why"][0] if group["why"] else None,
        "clearable": group["clearable"],
        "settled": group.get("settled", False),
        "status": group.get("status", "candidate"),
        "evidence": [element["label"] for element in group["evidence"]],
        "controls": [control["label"] for control in group.get("applicableControls", [])],
    }


def process_risk(graph: Graph, groups: list[dict]) -> dict:
    """Concerns placed on the capabilities this process calls."""
    refined = list(graph.subject_objects(PAIR.refinedBy))
    if not refined:
        return {"present": False, "systems": [], "offProcess": [], "summary": {}}

    carries: dict[URIRef, list[URIRef]] = {}
    for activity, system in refined:
        carries.setdefault(system, []).append(activity)

    rows: list[dict] = []
    reached: set[str] = set()
    for system, activities in carries.items():
        held = {str(member) for member in _members_of(graph, system)}
        mine = [
            group for group in groups
            if {element["id"] for element in group["evidence"]} & held
        ]
        reached.update(group["key"] for group in mine)
        concerns = [_concern_view(group) for group in mine]
        # The same lens the risk level draws, one per AI system, so opening one
        # on the overview needs no second run.
        lens = risk_lens({
            "id": str(system),
            "label": label(graph, system),
            "dataCategory": None,
            "system": {"id": str(system), "label": label(graph, system)},
            "riskPattern": None,
        }, graph, groups)
        rows.append({
            "id": str(system),
            "label": label(graph, system),
            "lens": lens,
            "activities": [
                {
                    "id": str(activity),
                    "label": _name(graph, activity),
                    "lane": _lane_of(graph, activity),
                    "participant": _participant_of(graph, activity),
                }
                for activity in sorted(set(activities), key=lambda a: _name(graph, a))
            ],
            "concerns": concerns,
            "domains": sorted({d for concern in concerns for d in concern["domains"]}),
            "clearable": sum(1 for concern in concerns if concern["clearable"]),
            "settled": sum(1 for concern in concerns if concern["settled"]),
        })

    # An architecture nobody carries out is a fact about the process model.
    carried = {str(system) for system in carries}
    off = []
    for group in groups:
        if group["key"] in reached:
            continue
        cited = {element["id"] for element in group["evidence"]}
        holders = sorted({
            label(graph, system)
            for system in graph.subjects(RDF.type, BEAM.System)
            if str(system) not in carried and cited & {str(m) for m in _members_of(graph, system)}
        })
        entry = _concern_view(group)
        entry["systems"] = holders
        off.append(entry)

    # A concern can cite elements of two capabilities, and it belongs under
    # both. The card counts then do not sum to the run's total, so each such
    # concern says what else it reaches rather than looking like a duplicate.
    where: dict[str, list[str]] = {}
    for row in rows:
        for concern in row["concerns"]:
            where.setdefault(concern["key"], []).append(row["label"])
    for row in rows:
        for concern in row["concerns"]:
            concern["spans"] = [
                other for other in where[concern["key"]] if other != row["label"]
            ]

    rows.sort(key=lambda row: (-len(row["concerns"]), row["label"].lower()))
    return {
        "present": True,
        "systems": rows,
        "offProcess": off,
        # Counted once each, whatever the activity attribution repeats.
        "summary": {
            "concerns": len(groups),
            "inProcess": len(reached),
            "offProcess": len(off),
            "aiSystems": len(rows),
            "withConcerns": len([row for row in rows if row["concerns"]]),
            # Rows on the page, which exceeds the concern count when one spans
            # two capabilities. Stated so a reader is never left to add up.
            "listed": sum(len(row["concerns"]) for row in rows),
            "spanning": len([key for key, names in where.items() if len(names) > 1]),
            "domains": sorted({d for row in rows for d in row["domains"]}),
        },
    }
