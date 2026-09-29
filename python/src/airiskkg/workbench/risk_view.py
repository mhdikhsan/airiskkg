"""The risk view: candidate findings read as concerns rather than as rows.

Three things the findings list cannot do, because it is one row per motif match:

* **Group.** Nested motifs co-match by design, so the same weakness at the same
  place is reported once per structure that reached it. Collapsing to
  (risk pattern, evidence set) turns four identical rows into one row that says
  four structures corroborate it.
* **Scope.** A stated undesired outcome says which findings answer the question
  that was asked. It never removes one: an out-of-scope finding is set aside
  and counted, and a finding that reaches no catalogued domain is neither in
  nor out - saying so is the only honest option, since the two risk patterns
  with no upstream domain mapping are agentic ones.
* **Reconcile.** A person's stated risk and a structural candidate are
  different claims about the same design. Where they meet is the strongest
  evidence in the method; where they do not is what each side contributes.
"""

from __future__ import annotations

from rdflib import Graph, URIRef

from airiskkg.graph_view import _members_of
from airiskkg.workbench.cross_view import assurance_gaps, open_questions
from airiskkg.workbench.hypothesis import agenda_from_scope, check_agenda
from airiskkg.workbench.process_risk import process_risk
from airiskkg.workbench.risk_diagram import risk_diagram
from airiskkg.workbench.risk_lens import lens_risks, risk_lens
from airiskkg.workbench.scope import (
    read_scope,
    scoped_domain_ids,
    stated_notes,
    stated_risks,
    triage_decisions,
)


def _group_key(finding: dict) -> tuple:
    """One concern is one risk pattern at one place, however many motifs reached it."""
    pattern = (finding.get("riskPattern") or {}).get("id") or finding["label"]
    evidence = tuple(sorted(element["id"] for element in finding["evidence"]))
    return (pattern, evidence)


def _merge(findings: list[dict]) -> dict:
    """Fold the findings sharing a key into the one concern they describe."""
    first = findings[0]
    motifs = sorted({(f.get("motif") or {}).get("label") for f in findings} - {None})

    conditions: dict[str, dict] = {}
    domains: dict[str, dict] = {}
    applicable: dict[str, dict] = {}
    other: dict[str, dict] = {}
    for finding in findings:
        for condition in finding.get("satisfiedConditions", []):
            conditions.setdefault(condition["id"], condition)
        for domain in finding.get("riskDomains", []):
            domains.setdefault(domain["id"], domain)
        for control in finding.get("suggestedControls", []):
            bucket = applicable if control.get("applicable") else other
            bucket.setdefault(control["id"], control)
    for control_id in applicable:
        other.pop(control_id, None)

    return {
        "key": "|".join(str(part) for part in _group_key(first)),
        "label": first["label"],
        "description": first["description"],
        "riskPattern": first.get("riskPattern"),
        "mechanism": first.get("mechanism"),
        "corroboration": len(findings),
        "motifs": motifs,
        # By label, not by condition: two conditions in the library carry the
        # same sentence, and a panel that prints it twice reads as noise. What
        # is kept is what the reader could tell apart.
        "why": sorted({c["label"] for c in conditions.values()}, key=str.lower),
        "riskDomains": sorted(domains.values(), key=lambda row: row["label"].lower()),
        "taxonomyEntries": first.get("taxonomyEntries", []),
        "evidence": first["evidence"],
        "clearable": bool(applicable),
        "applicableControls": sorted(
            ({"id": c["id"], "label": c["label"], "nature": c.get("nature")}
             for c in applicable.values()),
            key=lambda c: c["label"].lower(),
        ),
        "otherControls": sorted(
            ({"id": c["id"], "label": c["label"], "nature": c.get("nature")}
             for c in other.values()),
            key=lambda c: c["label"].lower(),
        ),
        "status": first.get("status") or "candidate",
        "findingIds": sorted(f["id"] for f in findings),
        # The finding a control is applied against: the rewrite is keyed on
        # (control, risk pattern), so any member of the group routes the same.
        "applyTo": sorted(f["id"] for f in findings)[0],
    }


def group_findings(findings: list[dict]) -> list[dict]:
    buckets: dict[tuple, list[dict]] = {}
    for finding in findings:
        buckets.setdefault(_group_key(finding), []).append(finding)
    groups = [_merge(rows) for rows in buckets.values()]
    # Most corroborated first, then clearable ahead of triage-only: both are
    # facts about the group, not a computed severity.
    return sorted(
        groups,
        key=lambda row: (-row["corroboration"], not row["clearable"], row["label"].lower()),
    )


def _scope_match(group: dict, wanted_domains: set[str]) -> str:
    """Does this concern answer the question that was asked?

    ``unclassified`` is not a polite ``out``: nothing upstream maps the entry to
    a domain of harm, so the scope simply cannot speak to it.
    """
    if not wanted_domains:
        return "all"
    reached = {domain["id"] for domain in group["riskDomains"]}
    if not reached:
        return "unclassified"
    return "in" if reached & wanted_domains else "out"


def _systems_of(graph: Graph, scope: dict) -> dict[str, set[str]]:
    return {
        system["id"]: {str(member) for member in _members_of(graph, URIRef(system["id"]))}
        for system in scope.get("systems", [])
    }


def _reconcile(groups: list[dict], stated: list[dict]) -> dict:
    """Where a person's claim and a structural candidate meet, and where they do not."""
    stated_by_element: dict[str, list[dict]] = {}
    for risk in stated:
        for element in risk["elements"]:
            stated_by_element.setdefault(element["id"], []).append(risk)

    matched_risk_ids: set[str] = set()
    for group in groups:
        touching: dict[str, dict] = {}
        for element in group["evidence"]:
            for risk in stated_by_element.get(element["id"], []):
                touching[risk["id"]] = risk
        group["statedRisks"] = [
            {"id": r["id"], "label": r["label"], "priority": r["priority"]}
            for r in sorted(touching.values(), key=lambda r: r["label"].lower())
        ]
        matched_risk_ids.update(touching)

    corroborated = [g for g in groups if g["statedRisks"]]
    raised_only = [g for g in groups if not g["statedRisks"]]
    stated_only = [r for r in stated if r["id"] not in matched_risk_ids]

    return {
        "corroborated": len(corroborated),
        "raisedOnly": len(raised_only),
        "statedOnly": [
            {
                "id": r["id"],
                "label": r["label"],
                "description": r["description"],
                "priority": r["priority"],
                "statedBy": r["statedBy"],
                "elements": r["elements"],
            }
            for r in stated_only
        ],
        "statedTotal": len(stated),
    }


def risk_view(summary: dict, graph: Graph, *, gaps: list[dict] | None = None,
              result=None) -> dict:
    """The assessment, read against what somebody asked it to answer."""
    scope = read_scope(graph)
    stated = stated_risks(graph)
    decisions = triage_decisions(graph)
    groups = group_findings(summary.get("findings", []))

    wanted = scoped_domain_ids(scope)
    members = _systems_of(graph, scope)
    for group in groups:
        match = _scope_match(group, wanted)
        cited = {element["id"] for element in group["evidence"]}
        # Naming a system is the sharpest narrowing the method has, and it
        # settles the question on its own: a concern in an architecture nobody
        # asked about is outside the scope however it rolls up.
        group["inScopedSystem"] = (
            any(cited & owned for owned in members.values()) if members else True
        )
        group["scopeMatch"] = "out" if not group["inScopedSystem"] else match
        # A judgement is recorded against a finding, so a group carries the
        # decisions made about the findings it collapsed.
        group["decisions"] = [
            dict(decisions[fid], finding=fid)
            for fid in group["findingIds"] if fid in decisions
        ]
        group["settled"] = bool(group["decisions"]) and all(
            fid in decisions for fid in group["findingIds"]
        )

    reconciliation = _reconcile(groups, stated)
    buckets = {"in": 0, "out": 0, "unclassified": 0, "all": 0}
    for group in groups:
        buckets[group["scopeMatch"]] += 1

    questions = open_questions(groups, graph)
    # Backward: the risks this assessment set out to answer, each with a verdict
    # - including the ones that did not fire, which are silent everywhere else.
    agenda = agenda_from_scope(scope, scope.get("checks", []))
    verdicts = (
        check_agenda(agenda, result, summary, gaps) if result is not None and agenda else None
    )
    return {
        # The same concerns placed on the work, for the page shown to people who
        # are not editing the graph.
        "byProcess": process_risk(graph, groups),
        # Risks defined first, each seen outward to the process and the
        # architecture - the view that is not the architecture view again.
        "lenses": [risk_lens(defined, graph, groups) for defined in lens_risks(graph)],
        "agenda": verdicts,
        "scope": scope,
        # The same concerns in the notation BEAM declares, for the canvas.
        "diagram": risk_diagram(graph, scope, groups),
        "statedRisks": stated,
        "notes": stated_notes(graph),
        "groups": groups,
        "reconciliation": reconciliation,
        "questions": questions,
        "assuranceGaps": assurance_gaps(gaps),
        "summary": {
            "findings": len(summary.get("findings", [])),
            "concerns": len(groups),
            "clearable": sum(1 for g in groups if g["clearable"]),
            "triageOnly": sum(1 for g in groups if not g["clearable"]),
            "settled": sum(1 for g in groups if g["settled"]),
            "openQuestions": len(questions),
            "scope": buckets,
            "domains": sorted(
                {d["label"] for g in groups for d in g["riskDomains"]}, key=str.lower
            ),
            "unclassified": sum(1 for g in groups if not g["riskDomains"]),
        },
    }
