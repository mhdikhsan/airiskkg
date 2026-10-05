from __future__ import annotations

from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.workbench.terms import label, source_pair

BEAMR = Namespace("http://w3id.org/beam/risk#")
_DESCRIPTIONS = (DCTERMS.description, BEAM.description, RDFS.comment, SKOS.definition)
_PRIORITIES = {
    str(PAIR.HighStatedPriority): ("high", 0),
    str(PAIR.MediumStatedPriority): ("medium", 1),
    str(PAIR.LowStatedPriority): ("low", 2),
}


def _present(value: object) -> object | None:
    if value is None or str(value).strip() in ("", "None"):
        return None
    return value


def _text(graph: Graph, resource: URIRef) -> str | None:
    for predicate in _DESCRIPTIONS:
        value = graph.value(resource, predicate)
        if value is not None:
            return " ".join(str(value).split()) or None
    return None


def _ref(graph: Graph, resource: URIRef) -> dict:
    full, brief = source_pair(resource)
    return {
        "id": str(resource),
        "label": label(graph, resource),
        "description": _text(graph, resource),
        "source": full,
        "sourceShort": brief,
    }


def _consequence(graph: Graph, consequence: URIRef) -> dict:
    ref = _ref(graph, consequence)
    ref["domains"] = sorted(
        (_ref(graph, domain) for domain in graph.objects(consequence, PAIR.concernsRiskDomain)),
        key=lambda row: row["label"].lower(),
    )
    return ref


def read_scope(graph: Graph) -> dict:
    """The frame of this assessment: what it is for, and what must not happen."""
    scopes = sorted(graph.subjects(RDF.type, PAIR.AssessmentScope), key=str)
    if not scopes:
        return {
            "present": False,
            "id": None,
            "desiredOutcome": None,
            "statedBy": None,
            "systems": [],
            "undesiredOutcomes": [],
            "checks": [],
        }

    scope = scopes[0]
    desired = _present(graph.value(scope, PAIR.desiredOutcome))
    stated_by = _present(graph.value(scope, PAIR.statedBy))
    return {
        "present": True,
        "id": str(scope),
        "desiredOutcome": " ".join(str(desired).split()) if desired else None,
        "statedBy": str(stated_by) if stated_by else None,
        "systems": sorted(
            (_ref(graph, system) for system in graph.objects(scope, PAIR.scopedToSystem)),
            key=lambda row: row["label"].lower(),
        ),
        "undesiredOutcomes": sorted(
            (_consequence(graph, outcome)
             for outcome in graph.objects(scope, PAIR.undesiredOutcome)),
            key=lambda row: row["label"].lower(),
        ),
        # The agenda, as short names: what this assessment set out to answer.
        "checks": sorted(
            str(pattern).rsplit("#", 1)[-1]
            for pattern in graph.objects(scope, PAIR.checksRiskPattern)
        ),
    }


def scoped_domain_ids(scope: dict) -> set[str]:
    """Catalogued domains the stated outcomes reach — what makes a finding answer this scope."""
    return {
        domain["id"]
        for outcome in scope.get("undesiredOutcomes", [])
        for domain in outcome.get("domains", [])
    }


def _priority(graph: Graph, risk: URIRef) -> dict | None:
    value = graph.value(risk, PAIR.statedPriority)
    if value is None:
        return None
    key, rank = _PRIORITIES.get(str(value), (None, 3))
    ref = _ref(graph, value)
    ref["key"] = key
    ref["rank"] = rank
    return ref


def stated_risks(graph: Graph) -> list[dict]:
    """Risks a person attached to elements — risk storming's sticky notes, as data.
    """
    rows: list[dict] = []
    for risk in sorted(graph.subjects(RDF.type, BEAMR.Risk), key=str):
        if any(graph.value(risk, p) is not None for p in (
                PAIR.concernsDataCategory, PAIR.concernsSystem, PAIR.concernsRiskPattern)):
            continue
        elements = sorted(graph.subjects(BEAMR.hasRisk, risk), key=str)
        priority = _priority(graph, risk)
        author = graph.value(risk, PAIR.statedBy)
        rows.append({
            "id": str(risk),
            "label": label(graph, risk),
            "description": _text(graph, risk),
            "priority": priority,
            "statedBy": str(author) if author else None,
            "elements": [_ref(graph, element) for element in elements],
            "consequences": sorted(
                (_consequence(graph, c) for c in graph.objects(risk, BEAMR.hasConsequence)),
                key=lambda row: row["label"].lower(),
            ),
        })
    # Highest stated priority first; an unscored risk sorts after a scored one.
    return sorted(rows, key=lambda row: ((row["priority"] or {}).get("rank", 3), row["label"].lower()))


def stated_notes(graph: Graph) -> list[dict]:
    """Free-text observations carried alongside a graph, typically from a drawing tool."""
    return sorted(
        (_ref(graph, note) for note in graph.subjects(RDF.type, BEAM.Note)),
        key=lambda row: row["label"].lower(),
    )


def scope_report(ttl: str) -> dict:
    """The register as it stands in the editor, without running anything.
    """
    from airiskkg.assessment_runner import load_base_graph

    graph = load_base_graph()
    graph.parse(data=ttl, format="turtle")
    return {
        "scope": read_scope(graph),
        "statedRisks": stated_risks(graph),
        "notes": stated_notes(graph),
        "triage": triage_decisions(graph),
    }


# The output contract's vocabulary, minus the candidate a run starts from.
TRIAGE_STATUSES = ("confirmed", "refuted", "mitigated", "accepted")


def triage_decisions(graph: Graph) -> dict[str, dict]:
    """What a person concluded about a finding, keyed by the finding they judged."""
    decisions: dict[str, dict] = {}
    for decision in sorted(graph.subjects(RDF.type, PAIR.TriageDecision), key=str):
        finding = graph.value(decision, PAIR.decidesFinding)
        status = graph.value(decision, PAIR.decidedStatus)
        if finding is None or status is None:
            continue
        author = graph.value(decision, PAIR.statedBy)
        when = graph.value(decision, DCTERMS.date)
        decisions[str(finding)] = {
            "id": str(decision),
            "status": str(status),
            "rationale": _text(graph, decision),
            "statedBy": str(author) if author else None,
            "date": str(when) if when else None,
        }
    return decisions
