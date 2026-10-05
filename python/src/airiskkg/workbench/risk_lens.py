from __future__ import annotations

import re
from functools import lru_cache

from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR, load_base_graph
from airiskkg.graph_view import _members_of
from airiskkg.paths import REPO_ROOT
from airiskkg.workbench.process_view import process_view
from airiskkg.workbench.terms import label, short

BEAMR = Namespace("http://w3id.org/beam/risk#")
_BP = Namespace("https://sBPMN.github.io/2.0/properties#")
_BP_NAME = _BP.name
_PROV = Namespace("http://www.w3.org/ns/prov#")
_PAIR_TERM = re.compile(r"pair:([A-Za-z][A-Za-z0-9]*)")


# ---- what the library looks at: a fact about the library, cached ----


@lru_cache(maxsize=1)
def _category_tree() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Each data category's descendants, and its whole family.
    """
    graph = load_base_graph()
    parents: dict[str, set[str]] = {}
    for child, parent in graph.subject_objects(PAIR.subDataCategoryOf):
        parents.setdefault(short(child), set()).add(short(parent))
    categories = {short(c) for c in graph.subjects(RDF.type, PAIR.DataCategory)}

    def up(name: str) -> set[str]:
        seen, stack = set(), [name]
        while stack:
            for parent in parents.get(stack.pop(), set()):
                if parent not in seen:
                    seen.add(parent)
                    stack.append(parent)
        return seen

    ancestors = {name: up(name) for name in categories}
    below: dict[str, set[str]] = {}
    family: dict[str, set[str]] = {}
    for name in categories:
        below[name] = {name} | {other for other in categories if name in ancestors[other]}
        family[name] = below[name] | ancestors[name]
    return below, family


@lru_cache(maxsize=1)
def _categories_tested() -> dict[str, set[str]]:
    """Risk pattern -> the data categories its registered query tests.
    """
    graph = load_base_graph()
    categories = {short(c) for c in graph.subjects(RDF.type, PAIR.DataCategory)}
    tested: dict[str, set[str]] = {}
    for pattern in graph.subjects(RDF.type, PAIR.RiskPattern):
        found: set[str] = set()
        for implementation in graph.objects(pattern, PAIR.implementedBy):
            path = graph.value(implementation, PAIR.implementationPath)
            if path is None:
                continue
            query = REPO_ROOT / str(path)
            if query.is_file():
                found |= set(_PAIR_TERM.findall(query.read_text(encoding="utf-8"))) & categories
        tested[str(pattern)] = found
    return tested


# ---- the defined risks ----


def lens_risks(graph: Graph) -> list[dict]:
    """Risks a person defined by what they are about, rather than by where they were stuck."""
    rows = []
    for risk in sorted(graph.subjects(RDF.type, BEAMR.Risk), key=str):
        category = graph.value(risk, PAIR.concernsDataCategory)
        system = graph.value(risk, PAIR.concernsSystem)
        pattern = graph.value(risk, PAIR.concernsRiskPattern)
        if category is None and system is None and pattern is None:
            continue
        rows.append({
            "id": str(risk),
            "label": label(graph, risk),
            "dataCategory": ({"id": str(category), "label": label(graph, category)}
                             if category is not None else None),
            "system": ({"id": str(system), "label": label(graph, system)}
                       if system is not None else None),
            "riskPattern": ({"id": str(pattern), "label": label(graph, pattern)}
                            if pattern is not None else None),
        })
    return rows


# ---- one lens ----


def _carriers(graph: Graph, scope: set[URIRef] | None, family: set[str]) -> dict[URIRef, str]:
    """Elements holding content of this kind, and the kind they hold."""
    found: dict[URIRef, str] = {}
    for element, category in graph.subject_objects(PAIR.containsDataCategory):
        if scope is not None and element not in scope:
            continue
        if short(category) in family and isinstance(element, URIRef):
            found.setdefault(element, label(graph, category))
    return found


def _name(graph: Graph, node: URIRef) -> str:
    """A business element names itself with bp:name, not rdfs:label."""
    value = graph.value(node, _BP_NAME)
    return str(value) if value else label(graph, node)


def _how_it_got_there(graph: Graph, element: URIRef, family: set[str]) -> str | None:
    """The derivation trail, one hop: where the content came from and through what."""
    for derivation in graph.objects(element, _PROV.qualifiedDerivation):
        category = graph.value(derivation, PAIR.derivedCategory)
        if category is None or short(category) not in family:
            continue
        upstream = graph.value(derivation, _PROV.entity)
        step = graph.value(derivation, _PROV.hadActivity)
        if upstream is not None:
            via = f" via {_name(graph, step)}" if step is not None else ""
            return f"derived from {_name(graph, upstream)}{via}"
    return None


def _derived_from(graph: Graph, origin: URIRef) -> tuple[set[str], set[str]]:
    """What `origin` put into the architecture: the elements, and the categories.
    """
    seeds = {graph.value(d, PAIR.derivedCategory) for d in graph.subjects(_PROV.entity, origin)}
    seeds.discard(None)
    reached: set[URIRef] = set()
    frontier = [origin]
    while frontier:
        upstream = frontier.pop()
        for derivation in graph.subjects(_PROV.entity, upstream):
            if graph.value(derivation, PAIR.derivedCategory) not in seeds:
                continue
            for downstream in graph.subjects(_PROV.qualifiedDerivation, derivation):
                if downstream not in reached:
                    reached.add(downstream)
                    frontier.append(downstream)
    return {str(element) for element in reached}, {short(category) for category in seeds}


def _data_target(graph: Graph, reference: str) -> URIRef:
    """The object or store a process-view reference stands for: derivations name that."""
    node = URIRef(reference)
    return graph.value(node, _BP.dataStoreRef) or graph.value(node, _BP.dataObjectRef) or node


def _kind(graph: Graph, element: URIRef) -> str:
    types = set(graph.objects(element, RDF.type))
    process_like = {BEAM.Process, BEAM.Infer, BEAM.Transform, BEAM.Train, BEAM.Generate}
    if types & process_like:
        return "process"
    if BEAM.Agent in types:
        return "agent"
    if types & {BEAM.StatisticalModel, BEAM.SemanticModel, BEAM.Model}:
        return "model"
    if BEAM.Symbol in types:
        return "symbol"
    return "data"


def risk_lens(defined: dict, graph: Graph, groups: list[dict]) -> dict:
    """The design, seen from one defined risk outward."""
    chosen = short(defined["dataCategory"]["id"]) if defined.get("dataCategory") else None
    below, whole = _category_tree()
    family = below.get(chosen, set()) if chosen else set()   # what holds it
    reaches = whole.get(chosen, set()) if chosen else set()  # what a query about it tests
    system = URIRef(defined["system"]["id"]) if defined.get("system") else None
    members = _members_of(graph, system) if system is not None else None
    pattern_iri = defined["riskPattern"]["id"] if defined.get("riskPattern") else None

    # ---- architecture: what holds the content, and what handles it ----
    carriers = _carriers(graph, members, family) if family else {}
    architecture: dict[str, dict] = {}
    for element, category_label in carriers.items():
        trail = _how_it_got_there(graph, element, family)
        architecture[str(element)] = {
            "id": str(element), "label": label(graph, element), "kind": _kind(graph, element),
            "why": f"carries {category_label}" + (f", {trail}" if trail else ", stated on it"),
        }
    # The steps that read or write that content are where it is involved.
    for element in list(carriers):
        for step in set(graph.subjects(BEAM.use, element)) | set(graph.subjects(BEAM.produce, element)):
            if members is not None and step not in members:
                continue
            reads = (step, BEAM.use, element) in graph
            architecture.setdefault(str(step), {
                "id": str(step), "label": label(graph, step), "kind": "process",
                "why": f"{'reads' if reads else 'writes'} {label(graph, element)}",
            })
    if not family and members is not None:
        for element in members:
            if element == system or not isinstance(element, URIRef):
                continue
            architecture.setdefault(str(element), {
                "id": str(element), "label": label(graph, element),
                "kind": _kind(graph, element), "why": f"part of {label(graph, system)}",
            })

    arch_ids = set(architecture)
    flow = [
        {"source": str(s), "target": str(o), "kind": kind}
        for predicate, kind in ((BEAM.use, "use"), (BEAM.produce, "produce"))
        for s, o in graph.subject_objects(predicate)
        if str(s) in arch_ids and str(o) in arch_ids
    ]

    # ---- concerns: about the risk, or only passing through it ----
    tested = _categories_tested()
    about, through = [], []
    cited_by: dict[str, set[str]] = {}  # about-concern key -> every element it cites
    pattern_by: dict[str, str] = {}     # about-concern key -> the risk pattern that raised it
    for group in groups:
        pattern = (group.get("riskPattern") or {}).get("id")
        if pattern_iri and pattern != pattern_iri:
            continue
        cited = {element["id"] for element in group["evidence"]}
        if members is not None and not cited & {str(m) for m in members}:
            continue
        if family and not cited & arch_ids and pattern_iri is None:
            continue
        entry = {
            "key": group["key"], "label": group["label"], "status": group.get("status"),
            "settled": group.get("settled", False), "clearable": group["clearable"],
            "why": group.get("why", []),
            "evidence": [e for e in group["evidence"] if e["id"] in arch_ids] or group["evidence"],
            "controls": [c["label"] for c in group.get("applicableControls", [])]
                        + [c["label"] for c in group.get("otherControls", [])],
            "buildable": [c["label"] for c in group.get("applicableControls", [])],
        }
        if pattern_iri or not chosen or (reaches and tested.get(pattern or "", set()) & reaches):
            about.append(entry)
            cited_by[group["key"]] = cited
            pattern_by[group["key"]] = pattern or ""
        else:
            through.append(entry)

    # ---- process: where that architecture sits in the work ----
    held: dict[str, set[str]] = {}

    def held_by(system_id: str) -> set[str]:
        if system_id not in held:
            held[system_id] = {str(m) for m in _members_of(graph, URIRef(system_id))}
        return held[system_id]

    def bearing_on(elements: set[str]) -> set[str]:
        """The concerns on this view whose evidence is among `elements`."""
        return {key for key, cited in cited_by.items() if cited & elements}

    process: dict[str, dict] = {}
    view = process_view(graph)
    related_systems = {str(system)} if system is not None else {
        s for a in view["activities"] for s in a["refines"]
    }
    for activity in view["activities"]:
        carried_by = [s for s in activity["refines"] if s in related_systems]
        if not carried_by:
            continue
        carried = set().union(*(held_by(s) for s in carried_by))
        process[activity["id"]] = {
            "id": activity["id"], "label": activity["label"], "kind": "activity",
            "why": "carried out by " + ", ".join(
                label(graph, URIRef(s)) for s in carried_by),
            "lane": activity.get("lane"),
            "process": activity.get("process"),
            "concerns": bearing_on(carried),
        }
        for item in activity["reads"] + activity["writes"]:
            kinds = [k for k in item.get("kinds", []) if k]
            if family and not kinds:
                continue
            key = item["id"]
            point = process.setdefault(key, {
                "id": key, "label": item["label"], "kind": "data object",
                "why": ("classified " + ", ".join(kinds)
                        if kinds else "no classification stated")
                       + f", used by {activity['label']}",
                "activity": activity["id"],
                "concerns": set(),
            })
            reached, seeded = _derived_from(graph, _data_target(graph, key))
            about_seeded = set().union(*(whole.get(c, {c}) for c in seeded)) if seeded else set()
            point["concerns"] |= {
                concern for concern in bearing_on(reached)
                if tested.get(pattern_by[concern], set()) & about_seeded
            }
    # The people in that same work: the question the architecture cannot ask.
    lanes_in_play = {p["lane"] for p in process.values() if p.get("lane")}
    work = {a["process"] for a in view["activities"] if a["id"] in process}
    for activity in view["activities"]:
        if activity["human"] and (activity["process"] in work or activity.get("lane") in lanes_in_play):
            # A person acting in the same work bears on what that work's AI raised.
            alongside = set().union(*(
                point["concerns"] for point in process.values()
                if point["kind"] == "activity"
                and (point.get("process") == activity["process"]
                     or (point.get("lane") and point.get("lane") == activity.get("lane")))
            ))
            process.setdefault(activity["id"], {
                "id": activity["id"], "label": activity["label"], "kind": "human step",
                "why": "a person acts here"
                       + (f" ({', '.join(activity['performers'])})" if activity["performers"] else ""),
                "concerns": alongside,
            })
    for point in process.values():
        point["concerns"] = sorted(point.get("concerns", ()))
        point.pop("process", None)

    buildable = sorted({c for entry in about for c in entry["buildable"]})
    return {
        "risk": defined,
        "architecture": sorted(architecture.values(), key=lambda row: row["label"].lower()),
        "flow": flow,
        "process": sorted(process.values(), key=lambda row: (row["kind"], row["label"].lower())),
        "about": about,
        "passesThrough": through,
        "controls": sorted({c for entry in about for c in entry["controls"]}),
        "buildable": buildable,
        "summary": {
            "architecture": len(architecture),
            "process": len(process),
            "about": len(about),
            "passesThrough": len(through),
            "outOf": len(groups),
        },
    }
