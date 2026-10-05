from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR, load_base_graph
from airiskkg.graph_view import _members_of
from airiskkg.workbench.terms import label

_BP = Namespace("https://sBPMN.github.io/2.0/properties#")
_BPMN = Namespace("https://sBPMN.github.io/2.0/classes#")
_HUMAN_TASKS = ("userTask", "manualTask")


def _name(graph: Graph, node: URIRef) -> str:
    value = graph.value(node, _BP.name)
    return str(value) if value else label(graph, node)


def _human_steps(graph: Graph) -> list[URIRef]:
    steps: list[URIRef] = []
    for kind in _HUMAN_TASKS:
        steps.extend(graph.subjects(RDF.type, _BPMN[kind]))
    return sorted(set(steps), key=str)


def _performers(graph: Graph, activity: URIRef) -> list[str]:
    names = []
    for role in graph.objects(activity, _BP.resourceRole):
        value = graph.value(role, _BP.name)
        if value:
            names.append(str(value))
    return sorted(set(names))


def _process_of(graph: Graph, node: URIRef) -> URIRef | None:
    for process in graph.subjects(_BP.contains, node):
        return process
    return None


def open_questions(groups: list[dict], graph: Graph) -> list[dict]:
    """Concerns the process may already answer — asked, never assumed.

    Raised only where the concern has no structural escape available, because a
    concern a rewrite can clear has a better answer than a conversation.
    """
    humans = _human_steps(graph)
    if not humans:
        return []

    # Which architecture each business activity stands for, and who is in its process.
    refined: dict[str, list[dict]] = {}
    for activity, _p, system in graph.triples((None, PAIR.refinedBy, None)):
        process = _process_of(graph, activity)
        nearby = [
            {
                "id": str(step),
                "label": _name(graph, step),
                "performers": _performers(graph, step),
            }
            for step in humans
            if process is not None and _process_of(graph, step) == process
        ]
        if not nearby:
            continue
        members = {str(m) for m in _members_of(graph, system)}
        refined.setdefault(str(system), []).append({
            "system": str(system),
            "systemLabel": label(graph, system),
            "activity": _name(graph, activity),
            "members": members,
            "humanSteps": nearby,
        })

    questions: list[dict] = []
    for group in groups:
        if group.get("clearable"):
            continue  # a rewrite is a better answer than a conversation
        cited = {element["id"] for element in group["evidence"]}
        for entries in refined.values():
            for entry in entries:
                if not (cited & entry["members"]):
                    continue
                steps = entry["humanSteps"]
                who = sorted({p for step in steps for p in step["performers"]})
                questions.append({
                    "concern": group["key"],
                    "concernLabel": group["label"],
                    "activity": entry["activity"],
                    "system": entry["systemLabel"],
                    "humanSteps": [step["label"] for step in steps],
                    "performers": who,
                    "question": (
                        f"The process shows {_join(step['label'] for step in steps)}"
                        + (f", performed by {_join(who)}" if who else "")
                        + ". The architecture represents no such step on the path this "
                          "concern cites. Is the architecture under-described, or does "
                          "the approval not cover this path?"
                    ),
                })
                break
    return questions


def _join(items) -> str:
    values = list(items)
    if len(values) <= 1:
        return values[0] if values else ""
    return ", ".join(values[:-1]) + " and " + values[-1]


@lru_cache(maxsize=1)
def _control_motifs() -> dict[str, list[str]]:
    """Which motifs realize a control, and which controls each stands for.

    Cached: this is a fact about the library, not about a submitted graph, and
    reading it took a full knowledge-base copy on every assessment.
    """
    library = load_base_graph()
    realizing: dict[str, list[str]] = {}
    for control, motif in library.subject_objects(PAIR.realizedByMotif):
        key = str(motif).rsplit("#", 1)[-1]
        realizing.setdefault(key, []).append(label(library, control))
    return {key: sorted(set(values)) for key, values in realizing.items()}


def assurance_gaps(gaps: list[dict] | None) -> list[dict]:
    """Controls this design does not represent — the reason findings stand.

    The near-miss report is noisy read whole: a tool-using agent shape scores
    1/5 against a RAG system and means nothing. Filtered to the motifs that
    realize a control, the same data says which safeguards were never described
    - and under R4 that is a gap in the description, never a claim about the
    system.
    """
    if not gaps:
        return []
    realizing = _control_motifs()
    rows = []
    for gap in gaps:
        controls = realizing.get(gap["motifId"])
        if not controls:
            continue
        rows.append({
            "motifId": gap["motifId"],
            "label": gap["label"],
            "satisfied": gap["satisfied"],
            "total": gap["total"],
            "controls": controls,
            "missing": [node["role"] for node in gap.get("missingNodes", [])],
        })
    # Closest to complete first: those are the ones a small annotation finishes.
    return sorted(rows, key=lambda row: (-(row["satisfied"] / row["total"]), row["label"]))
