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
        "applyTo": sorted(f["id"] for f in findings)[0],
    }


def group_findings(findings: list[dict]) -> list[dict]:
    buckets: dict[tuple, list[dict]] = {}
    for finding in findings:
        buckets.setdefault(_group_key(finding), []).append(finding)
    groups = [_merge(rows) for rows in buckets.values()]
    return sorted(
        groups,
        key=lambda row: (-row["corroboration"], not row["clearable"], row["label"].lower()),
    )


def _scope_match(group: dict, wanted_domains: set[str]) -> str:
    """Does this concern answer the question that was asked?
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


def _name_the_place(groups: list[dict]) -> None:
    """Tell concerns that share a name apart by where they are.

    Prompt injection is raised once per untrusted-content/generation pair, so
    three boxes reading "Candidate prompt injection exposure" are three true and
    different answers - and nothing on them said which was which. A concern is
    the (risk pattern, evidence set) group, so the evidence is what differs.
    The element fewest siblings cite says it in the fewest words; a set that is
    a subset of its siblings' has no element of its own, so "unique to me" alone
    would leave one of the three unnamed.
    """
    by_label: dict[str, list[dict]] = {}
    for group in groups:
        by_label.setdefault(group["label"], []).append(group)

    for shared in by_label.values():
        if len(shared) < 2:
            continue
        cited: dict[str, int] = {}
        for group in shared:
            for element in group["evidence"]:
                cited[element["id"]] = cited.get(element["id"], 0) + 1

        def named(element: dict) -> str:
            return element.get("label") or element["id"].rsplit("#", 1)[-1]

        ranked = {
            id(group): sorted(group["evidence"], key=lambda e: (cited[e["id"]], named(e)))
            for group in shared
        }
        for group in shared:
            if ranked[id(group)]:
                group["distinguisher"] = named(ranked[id(group)][0])

        # Two concerns landing on the same name have said nothing: walk each
        # down its own ranking until the names differ or the evidence runs out.
        for _ in range(4):
            taken: dict[str, list[dict]] = {}
            for group in shared:
                taken.setdefault(group.get("distinguisher", ""), []).append(group)
            clashes = [rows for rows in taken.values() if len(rows) > 1]
            if not clashes:
                break
            for rows in clashes:
                for offset, group in enumerate(rows[1:], start=1):
                    options = ranked[id(group)]
                    if offset < len(options):
                        group["distinguisher"] = named(options[offset])


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
        group["inScopedSystem"] = (
            any(cited & owned for owned in members.values()) if members else True
        )
        group["scopeMatch"] = "out" if not group["inScopedSystem"] else match
        group["decisions"] = [
            dict(decisions[fid], finding=fid)
            for fid in group["findingIds"] if fid in decisions
        ]
        group["settled"] = bool(group["decisions"]) and all(
            fid in decisions for fid in group["findingIds"]
        )

    _name_the_place(groups)
    reconciliation = _reconcile(groups, stated)
    buckets = {"in": 0, "out": 0, "unclassified": 0, "all": 0}
    for group in groups:
        buckets[group["scopeMatch"]] += 1

    questions = open_questions(groups, graph)
    agenda = agenda_from_scope(scope, scope.get("checks", []))
    verdicts = (
        check_agenda(agenda, result, summary, gaps) if result is not None and agenda else None
    )
    return {
        "byProcess": process_risk(graph, groups),
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
