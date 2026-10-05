"""Backward entry, and the register a person writes before the assessment runs.

Every edit here is a server-side rewrite of the submitted Turtle, exactly like
``/api/graph-edit``: the editor stays the single source of truth, so a stated
risk travels with the graph and exports with the run.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from datetime import date

from rdflib import DCTERMS, RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.workbench.backward import backward_index
from airiskkg.workbench.library import library_catalogue
from airiskkg.workbench.risk_diagram import risk_diagram
from airiskkg.workbench.scope import TRIAGE_STATUSES, scope_report

risk_routes = Blueprint("risk", __name__)

BEAMR = Namespace("http://w3id.org/beam/risk#")
LOCAL = Namespace("http://w3id.org/airiskkg/local#")

_PRIORITIES = {
    "high": PAIR.HighStatedPriority,
    "medium": PAIR.MediumStatedPriority,
    "low": PAIR.LowStatedPriority,
}


@risk_routes.get("/api/backward")
def get_backward() -> object:
    """What to look for, given what must not happen. Needs no graph."""
    return jsonify(backward_index())


@risk_routes.post("/api/scope")
def get_scope() -> object:
    """What has been stated on this graph, live - no assessment is run."""
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    if not ttl:
        return jsonify({"scope": {"present": False, "undesiredOutcomes": [], "systems": []},
                        "statedRisks": [], "notes": []})
    try:
        report = scope_report(ttl)
        # The same notation, with nothing found in it: an assessment written by
        # hand is drawn before any query has matched anything.
        graph = Graph().parse(data=ttl, format="turtle")
        report["diagram"] = risk_diagram(graph, report["scope"], [])
        return jsonify(report)
    except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
        return jsonify({"error": f"Could not read the scope: {error}"}), 400


def _fresh(data: Graph, prefix: str) -> URIRef:
    existing = {str(s) for s in data.subjects()}
    index = 1
    while str(LOCAL[f"{prefix}{index}"]) in existing:
        index += 1
    return LOCAL[f"{prefix}{index}"]


_CONCEPT_CLASS = {
    "risk": BEAMR.Risk,
    "source": BEAMR.RiskSource,
    "consequence": BEAMR.Consequence,
    "impact": BEAMR.Impact,
    "control": BEAMR.RiskControl,
}

# What a control may modify, which is the range beamr:modifiesRiskConcept
# declares: every one of the four is a beamr:RiskConcept.
_RISK_CONCEPTS = (BEAMR.Risk, BEAMR.RiskSource, BEAMR.Consequence, BEAMR.Impact)


_RELATIONS = (BEAMR.hasRisk, BEAMR.originatedFrom, BEAMR.isRiskSourceFor,
              BEAMR.hasConsequence, BEAMR.hasImpact, BEAMR.modifiesRiskConcept)


def _library_index() -> tuple[dict, dict]:
    """What a person may pick instead of writing their own words.

    Read off the loaded library rather than listed here, so the choice offered
    cannot drift from the library the run uses - the same reason the front door
    counts its own shelves rather than carrying a hand-written list.
    """
    catalogue = library_catalogue()
    patterns: dict[str, tuple[str, str]] = {}
    controls: dict[str, tuple[str, str]] = {}

    def remember(into: dict, row: dict) -> None:
        # A risk pattern carries a short id and a full iri; a control's id is
        # already the iri. Both are accepted and both resolve to the iri, so a
        # caller that sends the short form does not end up writing a triple
        # whose object resolved against the working directory.
        iri = row.get("iri") or row.get("id")
        if not iri:
            return
        for key in {row.get("id"), iri}:
            if key:
                into[key] = (iri, row.get("label") or "")

    for row in catalogue.get("riskPatterns", []):
        remember(patterns, row)
        for control in row.get("controls", []):
            remember(controls, control)
    return patterns, controls


def _kind_of(data: Graph, node: URIRef) -> str | None:
    """Which of the five a node is. Impact first: it is a kind of Consequence,
    so testing the parent first would call every impact a consequence."""
    types = set(data.objects(node, RDF.type))
    for cls, kind in ((BEAMR.Impact, "impact"), (BEAMR.RiskSource, "source"),
                      (BEAMR.Risk, "risk"), (BEAMR.Consequence, "consequence"),
                      (BEAMR.RiskControl, "control")):
        if cls in types:
            return kind
    return None


def _attachment(data: Graph, kind: str, node: URIRef, target: URIRef) -> tuple:
    """The one triple that ties a hand-written concept to what it is about.

    AIRO says which way each of these runs, and the direction is not a detail: a
    risk hangs off the element that carries it, a source points back at the
    element it arises from, and a consequence hangs off the risk. Guessing from
    the target's type keeps the form to one field without writing a relation the
    vocabulary does not have.
    """
    types = set(data.objects(target, RDF.type))
    if kind == "risk":
        if types & set(_CONCEPT_CLASS.values()):
            raise ValueError("A risk attaches to an element of the design, not to another risk.")
        return (target, BEAMR.hasRisk, node)
    if kind == "source":
        if BEAMR.Risk in types:
            return (node, BEAMR.isRiskSourceFor, target)
        return (node, BEAMR.originatedFrom, target)
    if kind == "consequence":
        if BEAMR.Risk not in types:
            raise ValueError("A consequence follows from a risk, so attach it to one.")
        return (target, BEAMR.hasConsequence, node)
    if kind == "control":
        if not types & set(_RISK_CONCEPTS):
            raise ValueError(
                "A control modifies a risk, a source, a consequence or an impact.")
        return (node, BEAMR.modifiesRiskConcept, target)
    if BEAMR.Consequence not in types or BEAMR.Impact in types:
        raise ValueError("An impact is the impact of a consequence, so attach it to one.")
    return (target, BEAMR.hasImpact, node)


def _scope_node(data: Graph) -> URIRef:
    """One scope per document: a second frame would not say which one applied."""
    for scope in sorted(data.subjects(RDF.type, PAIR.AssessmentScope), key=str):
        return scope
    scope = LOCAL["scope"]
    data.add((scope, RDF.type, PAIR.AssessmentScope))
    data.add((scope, RDFS.label, Literal("Assessment scope", lang="en")))
    return scope


def _replace(data: Graph, subject: URIRef, predicate: URIRef, text: str | None) -> None:
    """Set a literal, or clear it when there is nothing to say.

    Takes the text rather than a Literal: Literal(None) is the string "None",
    not an absence, and it was being written into graphs as a value.
    """
    data.remove((subject, predicate, None))
    cleaned = (text or "").strip()
    if cleaned:
        data.add((subject, predicate, Literal(cleaned)))


@risk_routes.post("/api/scope-edit")
def scope_edit() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    op = payload.get("op")
    if not ttl:
        return jsonify({"error": "Provide a graph to edit."}), 400
    try:
        data = Graph().parse(data=ttl, format="turtle")
    except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
        return jsonify({"error": f"Could not parse the graph: {error}"}), 400

    new_id = None

    if op == "set-scope":
        scope = _scope_node(data)
        _replace(data, scope, PAIR.desiredOutcome, payload.get("desiredOutcome"))
        _replace(data, scope, PAIR.statedBy, payload.get("statedBy"))
        new_id = str(scope)

    elif op == "add-outcome":
        statement = (payload.get("statement") or "").strip()
        if not statement:
            return jsonify({"error": "add-outcome needs a statement of what must not happen."}), 400
        scope = _scope_node(data)
        outcome = _fresh(data, "outcome")
        data.add((outcome, RDF.type, BEAMR.Consequence))
        data.add((outcome, RDFS.label, Literal(statement, lang="en")))
        note = (payload.get("description") or "").strip()
        if note:
            data.add((outcome, DCTERMS.description, Literal(note, lang="en")))
        for domain in payload.get("domains") or []:
            data.add((outcome, PAIR.concernsRiskDomain, URIRef(domain)))
        data.add((scope, PAIR.undesiredOutcome, outcome))
        new_id = str(outcome)

    elif op == "remove-outcome":
        target = URIRef(payload.get("outcome") or "")
        data.remove((None, None, target))
        data.remove((target, None, None))

    elif op == "scope-to-system":
        scope = _scope_node(data)
        data.remove((scope, PAIR.scopedToSystem, None))
        for system in payload.get("systems") or []:
            data.add((scope, PAIR.scopedToSystem, URIRef(system)))
        new_id = str(scope)

    elif op == "state-risk":
        label = (payload.get("label") or "").strip()
        elements = payload.get("elements") or []
        if not label:
            return jsonify({"error": "state-risk needs a label."}), 400
        if not elements:
            return jsonify({"error": "state-risk needs at least one element to attach to."}), 400
        risk = _fresh(data, "risk")
        data.add((risk, RDF.type, BEAMR.Risk))
        data.add((risk, RDFS.label, Literal(label, lang="en")))
        note = (payload.get("description") or "").strip()
        if note:
            data.add((risk, DCTERMS.description, Literal(note, lang="en")))
        priority = _PRIORITIES.get((payload.get("priority") or "").lower())
        if priority is not None:
            data.add((risk, PAIR.statedPriority, priority))
        author = (payload.get("statedBy") or "").strip()
        if author:
            data.add((risk, PAIR.statedBy, Literal(author)))
        for outcome in payload.get("consequences") or []:
            data.add((risk, BEAMR.hasConsequence, URIRef(outcome)))
        for element in elements:
            data.add((URIRef(element), BEAMR.hasRisk, risk))
        new_id = str(risk)

    elif op == "state-concept":
        kind = (payload.get("kind") or "").strip().lower()
        if kind not in _CONCEPT_CLASS:
            return jsonify({
                "error": f"state-concept needs a kind: {', '.join(sorted(_CONCEPT_CLASS))}.",
            }), 400
        label = (payload.get("label") or "").strip()

        """Named from the library, or in the person's own words.

        Picking a risk the library already knows mints the person's own
        beamr:Risk and points it at the pattern with pair:concernsRiskPattern -
        a stated risk is a claim about this system, the pattern is a type, and
        the two must not be collapsed. Picking a control uses the library
        control's own IRI, because naming Guardrails is naming that control and
        nothing else; its type and label are written into the submitted graph so
        the graph still stands on its own.
        """
        chosen = (payload.get("fromLibrary") or "").strip()
        node = None
        if chosen:
            patterns, controls = _library_index()
            known = patterns if kind == "risk" else controls if kind == "control" else {}
            if not known:
                return jsonify({
                    "error": "Only a risk or a control can be picked from the library.",
                }), 400
            if chosen not in known:
                return jsonify({"error": "That is not in the library."}), 400
            chosen, known_label = known[chosen]
            label = label or known_label
            if kind == "control":
                node = URIRef(chosen)

        if not label:
            return jsonify({"error": "state-concept needs a label."}), 400

        if node is None:
            node = _fresh(data, kind)
        data.add((node, RDF.type, _CONCEPT_CLASS[kind]))
        data.add((node, RDFS.label, Literal(label, lang="en")))
        _replace(data, node, DCTERMS.description, payload.get("description"))
        _replace(data, node, PAIR.statedBy, payload.get("statedBy"))
        if kind == "risk":
            priority = _PRIORITIES.get((payload.get("priority") or "").lower())
            if priority is not None:
                data.add((node, PAIR.statedPriority, priority))
            if chosen:
                data.add((node, PAIR.concernsRiskPattern, URIRef(chosen)))

        for target in payload.get("attachTo") or []:
            try:
                triple = _attachment(data, kind, node, URIRef(target))
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            data.add(triple)
        new_id = str(node)

    elif op in {"link-concept", "unlink-concept"}:
        # A line drawn wrong should cost one line, not the whole assessment.
        source, target = payload.get("from"), payload.get("to")
        if not source or not target:
            return jsonify({"error": f"{op} needs a from and a to."}), 400
        node, other = URIRef(source), URIRef(target)
        kind = _kind_of(data, node)
        if kind is None:
            return jsonify({"error": "Only a hand-written risk concept can be joined up."}), 400
        if op == "unlink-concept":
            for predicate in _RELATIONS:
                data.remove((node, predicate, other))
                data.remove((other, predicate, node))
        else:
            try:
                data.add(_attachment(data, kind, node, other))
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
        new_id = str(node)

    elif op == "rename-concept":
        """What a hand-written concept is called, and which library entry it is.

        The box is drawn the moment it is dropped and named afterwards, the way
        a symbol dropped on the architecture canvas is - so naming has to be an
        edit of something that already exists rather than a question asked
        before it can.
        """
        target = payload.get("concept")
        if not target:
            return jsonify({"error": "rename-concept needs a concept."}), 400
        node = URIRef(target)
        kind = _kind_of(data, node)
        if kind is None:
            return jsonify({"error": "That is not a hand-written risk concept."}), 400

        label = (payload.get("label") or "").strip()
        chosen = (payload.get("fromLibrary") or "").strip()
        if chosen:
            patterns, controls = _library_index()
            known = patterns if kind == "risk" else controls if kind == "control" else {}
            if not known:
                return jsonify({
                    "error": "Only a risk or a control can be picked from the library.",
                }), 400
            if chosen not in known:
                return jsonify({"error": "That is not in the library."}), 400
            chosen, known_label = known[chosen]
            label = label or known_label
        if not label:
            return jsonify({"error": "rename-concept needs a label."}), 400

        """A control picked from the library becomes that control.
        """
        if kind == "control" and chosen and str(node) != chosen:
            moved = URIRef(chosen)
            for predicate, obj in list(data.predicate_objects(node)):
                data.add((moved, predicate, obj))
            for subject, predicate in list(data.subject_predicates(node)):
                data.add((subject, predicate, moved))
            data.remove((node, None, None))
            data.remove((None, None, node))
            node = moved

        data.remove((node, RDFS.label, None))
        data.add((node, RDFS.label, Literal(label, lang="en")))
        if kind == "risk":
            data.remove((node, PAIR.concernsRiskPattern, None))
            if chosen:
                data.add((node, PAIR.concernsRiskPattern, URIRef(chosen)))
        new_id = str(node)

    elif op == "remove-concept":
        target = payload.get("concept")
        if not target:
            return jsonify({"error": "remove-concept needs a concept."}), 400
        node = URIRef(target)
        if not any((node, RDF.type, cls) in data for cls in _CONCEPT_CLASS.values()):
            return jsonify({"error": "That is not a hand-written risk concept."}), 400
        # Both directions, or the graph keeps arrows into something gone.
        data.remove((node, None, None))
        data.remove((None, None, node))
        new_id = None

    elif op == "define-risk":
        criteria = {
            PAIR.concernsDataCategory: payload.get("dataCategory"),
            PAIR.concernsSystem: payload.get("system"),
            PAIR.concernsRiskPattern: payload.get("riskPattern"),
        }
        if not any(criteria.values()):
            return jsonify({"error": "define-risk needs a data category, a system, or a risk pattern."}), 400
        label = (payload.get("label") or "").strip() or "Defined risk"
        risk = _fresh(data, "lens")
        data.add((risk, RDF.type, BEAMR.Risk))
        data.add((risk, RDFS.label, Literal(label, lang="en")))
        for predicate, value in criteria.items():
            if value:
                data.add((risk, predicate, URIRef(value)))
        _replace(data, risk, DCTERMS.description, payload.get("description"))
        _replace(data, risk, PAIR.statedBy, payload.get("statedBy"))
        new_id = str(risk)

    elif op == "set-agenda":
        # What this assessment sets out to answer. Chooses what is reported on,
        # never what the pipeline is allowed to detect.
        scope = _scope_node(data)
        data.remove((scope, PAIR.checksRiskPattern, None))
        for pattern in payload.get("patterns") or []:
            data.add((scope, PAIR.checksRiskPattern, URIRef(pattern)))
        new_id = str(scope)

    elif op == "triage":
        # A concern is what a reader judges, and a concern is several findings
        # that co-matching motifs raised at one place - so a decision covers all
        # of them or the concern stays half-settled.
        findings = payload.get("findings") or [payload.get("finding") or ""]
        findings = [str(f).strip() for f in findings if str(f).strip()]
        status = (payload.get("status") or "").strip().lower()
        if not findings:
            return jsonify({"error": "triage needs at least one finding."}), 400
        if status and status not in TRIAGE_STATUSES:
            return jsonify({"error": f"status must be one of: {', '.join(TRIAGE_STATUSES)}."}), 400

        rationale = (payload.get("rationale") or "").strip()
        author = (payload.get("statedBy") or "").strip()
        today = Literal(date.today().isoformat())
        for finding in findings:
            target = URIRef(finding)
            # One decision per finding: a second would not say which one stood.
            for existing in list(data.subjects(PAIR.decidesFinding, target)):
                data.remove((existing, None, None))
            if not status:
                continue  # cleared back to the candidate the run emits
            decision = _fresh(data, "triage")
            data.add((decision, RDF.type, PAIR.TriageDecision))
            data.add((decision, PAIR.decidesFinding, target))
            data.add((decision, PAIR.decidedStatus, Literal(status)))
            data.add((decision, DCTERMS.date, today))
            if rationale:
                data.add((decision, DCTERMS.description, Literal(rationale, lang="en")))
            if author:
                data.add((decision, PAIR.statedBy, Literal(author)))
            new_id = str(decision)

    elif op == "remove-risk":
        target = URIRef(payload.get("risk") or "")
        data.remove((None, None, target))
        data.remove((target, None, None))

    else:
        return jsonify({"error": f"Unknown scope edit {op!r}."}), 400

    data.bind("beam", BEAM)
    data.bind("beamr", BEAMR)
    data.bind("pair", PAIR)
    data.bind("local", LOCAL)
    return jsonify({"ttl": data.serialize(format="turtle"), "newId": new_id})
