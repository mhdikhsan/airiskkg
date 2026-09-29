"""Backward reasoning: name a risk first, then ask the graph about that one.

The forward direction produces everything the library can see and leaves a
reader to decide what mattered. This is the other way round - an analyst says
what they are worried about, and each named risk comes back with a verdict.

The verdict is the point. A risk that does not fire is silent today, and silence
is where the method leaks: "we did not ask", "the design does not have that
shape", "the shape is there and something interrupts it" and "the shape is there
and nobody has said enough for it to be decided" are four different answers, and
a reader who cannot tell them apart will read all four as safe.

    raised                 a candidate finding stands, with evidence
    structure-present      the shape is here and the risk did not fire
    structure-incomplete   part of the shape is here; this is what is missing
    structure-absent       the design does not show this shape at all
    not-examined           nobody put it on the agenda

None of them is "safe", and none may be worded as one (R4): the closed-world
reading is over the submitted graph, never over the system.

The run itself stays whole. What is chosen here is the *agenda* - the risks this
assessment set out to answer - never what the pipeline is allowed to detect.
"""

from __future__ import annotations

from rdflib import RDF

from airiskkg.assessment_runner import PAIR
from airiskkg.workbench.backward import backward_index
from airiskkg.workbench.library import library_catalogue
from airiskkg.workbench.terms import short

RAISED = "raised"
PRESENT = "structure-present"
INCOMPLETE = "structure-incomplete"
ABSENT = "structure-absent"
NOT_EXAMINED = "not-examined"

# What each verdict licenses a reader to conclude. Carried with the verdict so
# a presentation layer cannot quietly turn "not raised" into "cleared".
VERDICT_MEANING = {
    RAISED: "A candidate finding stands here. It is a structural disposition, not a confirmed failure.",
    PRESENT: (
        "The structure this risk applies to is represented, and the risk did not fire. "
        "Either something represented interrupts it, or a fact it depends on was never "
        "stated. It does not mean the system is safe."
    ),
    INCOMPLETE: (
        "Part of the structure is represented and part is not, so this risk could not be "
        "decided either way. What is missing is a gap in the description, not in the system."
    ),
    ABSENT: (
        "Nothing of the structure this risk applies to is represented here. That is an "
        "answer about the drawing, and only about the drawing."
    ),
    NOT_EXAMINED: "Nobody put this risk on the agenda, so nothing was concluded about it.",
}


def _matched_motifs(result) -> set[str]:
    return {
        short(motif)
        for match in result.motif_matches.subjects(RDF.type, PAIR.MotifMatch)
        for motif in result.motif_matches.objects(match, PAIR.matchesMotif)
    }


def _gap_index(gaps: list[dict] | None) -> dict[str, dict]:
    return {gap["motifId"]: gap for gap in (gaps or [])}


def _motif_state(motif_id: str, matched: set[str], gap_index: dict[str, dict]) -> dict:
    """Where this motif stands against the graph: matched, partial, or absent."""
    gap = gap_index.get(motif_id)
    if motif_id in matched:
        return {"id": motif_id, "matched": True, "satisfied": None, "total": None,
                "missingNodes": [], "missingEdges": []}
    if gap is None:
        # Every node and edge is present somewhere, but no match was constructed:
        # the pieces do not join up into one instance.
        return {"id": motif_id, "matched": False, "satisfied": None, "total": None,
                "missingNodes": [], "missingEdges": [],
                "note": "every part is present, but not joined into one instance"}
    return {
        "id": motif_id,
        "matched": False,
        "satisfied": gap["satisfied"],
        "total": gap["total"],
        "missingNodes": gap.get("missingNodes", []),
        "missingEdges": gap.get("missingEdges", []),
    }


def _interrupting_controls(entry: dict, matched: set[str]) -> list[str]:
    """Controls whose realizing structure is represented here.

    A candidate answer to "why did this not fire" - and only a candidate: a
    control clears a finding by being built, and this says one was drawn, not
    that it covers the path.
    """
    return sorted({
        control["label"]
        for control in entry["controls"]
        for motif_id in control.get("realizedByMotifs", [])
        if motif_id in matched
    })


def check_risk(pattern_id: str, result, summary: dict, gaps: list[dict] | None) -> dict:
    """One named risk, asked of one graph."""
    catalogue = {entry["id"]: entry for entry in library_catalogue()["riskPatterns"]}
    entry = catalogue.get(pattern_id)
    if entry is None:
        return {"id": pattern_id, "verdict": NOT_EXAMINED, "unknown": True}

    matched = _matched_motifs(result)
    gap_index = _gap_index(gaps)

    findings = [
        finding for finding in summary.get("findings", [])
        if (finding.get("riskPattern") or {}).get("id") == entry["iri"]
    ]
    motif_states = [_motif_state(m, matched, gap_index) for m in entry["motifs"]]

    if findings:
        verdict = RAISED
    elif not entry["motifs"]:
        # Two risk patterns name no motif: they are evaluated over any match
        # whose conditions hold, so the question is whether anything matched.
        verdict = PRESENT if matched else ABSENT
    elif any(state["matched"] for state in motif_states):
        verdict = PRESENT
    elif any((state["satisfied"] or 0) > 0 for state in motif_states):
        verdict = INCOMPLETE
    else:
        verdict = ABSENT

    diagnosis = {
        "id": entry["id"],
        "iri": entry["iri"],
        "label": entry["label"],
        "description": entry["description"],
        "verdict": verdict,
        "meaning": VERDICT_MEANING[verdict],
        "riskDomains": [domain["label"] for domain in entry["riskDomains"]],
        "conditions": [condition["label"] for condition in entry["conditions"]],
        "motifs": motif_states,
        "findings": [
            {"id": finding["id"], "label": finding["label"],
             "evidence": [element["label"] for element in finding["evidence"]]}
            for finding in findings
        ],
        "controls": [control["label"] for control in entry["controls"]],
    }

    if verdict == PRESENT:
        diagnosis["represented"] = _interrupting_controls(entry, matched)
    if verdict == INCOMPLETE:
        # Closest first: the motif a small annotation would complete.
        diagnosis["motifs"].sort(
            key=lambda state: -((state["satisfied"] or 0) / (state["total"] or 1))
        )
    return diagnosis


def agenda_from_scope(scope: dict, checks: list[str]) -> list[str]:
    """What this assessment set out to answer.

    Stated risk patterns first; failing that, whatever the stated undesired
    outcomes reach, so naming a harm is enough to have an agenda.
    """
    if checks:
        return sorted(set(checks))
    wanted = {
        domain["id"]
        for outcome in scope.get("undesiredOutcomes", [])
        for domain in outcome.get("domains", [])
    }
    if not wanted:
        return []
    index = backward_index()
    reached: set[str] = set()
    for outcome in index["outcomes"]:
        if outcome["id"] in wanted:
            reached.update(outcome["riskPatterns"])
    return sorted(reached)


def check_agenda(agenda: list[str], result, summary: dict, gaps: list[dict] | None) -> dict:
    """Every risk that was asked about, and every one that was not.

    The second list is not padding. An assessment that reports only what it
    looked for reads as complete; naming what it did not look at is what makes
    the first list honest.
    """
    catalogue = library_catalogue()["riskPatterns"]
    on_agenda = [entry["id"] for entry in catalogue if entry["id"] in set(agenda)]
    checked = [check_risk(pattern_id, result, summary, gaps) for pattern_id in on_agenda]

    answered = {entry["id"] for entry in catalogue if entry["id"] in set(agenda)}
    raised_off_agenda = sorted({
        (finding.get("riskPattern") or {}).get("label")
        for finding in summary.get("findings", [])
        if (finding.get("riskPattern") or {}).get("id")
        not in {entry["iri"] for entry in catalogue if entry["id"] in answered}
    } - {None})

    counts = {verdict: 0 for verdict in VERDICT_MEANING}
    for diagnosis in checked:
        counts[diagnosis["verdict"]] += 1
    counts[NOT_EXAMINED] = len(catalogue) - len(checked)

    return {
        "checked": sorted(checked, key=lambda d: (_ORDER.index(d["verdict"]), d["label"].lower())),
        "notExamined": sorted(
            entry["label"] for entry in catalogue if entry["id"] not in answered
        ),
        # Raised without being asked for: the method's contribution beyond the
        # agenda, and the reason the run is never narrowed to it.
        "raisedOffAgenda": raised_off_agenda,
        "counts": counts,
    }


_ORDER = [RAISED, PRESENT, INCOMPLETE, ABSENT, NOT_EXAMINED]
