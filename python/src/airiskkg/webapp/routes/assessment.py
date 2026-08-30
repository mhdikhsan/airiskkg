from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request
from rdflib import RDF, Graph, URIRef

from airiskkg.assessment_export import EXPORT_FORMATS, build_export
from airiskkg.assessment_runner import (
    BEAM,
    PAIR,
    apply_control,
    run_assessment_from_text,
)
from airiskkg.assessment_view import summarize_result
from airiskkg.webapp.runtime import SPARQL_LOCK
from airiskkg.workbench.gaps import motif_gaps
from airiskkg.workbench.validation import shacl_report

assessment_routes = Blueprint("assessment", __name__)


@assessment_routes.post("/api/validate")
def validate_contract() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    if not ttl:
        return jsonify({"error": "Provide an architecture graph (Turtle) to validate."}), 400
    try:
        with SPARQL_LOCK:
            report = shacl_report(ttl)
    except Exception as error: 
        return jsonify({"error": f"Could not validate: {error}"}), 400
    return jsonify(report)


@assessment_routes.post("/api/assess")
def assess() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    if not ttl:
        return jsonify({"error": "Provide an architecture graph (Turtle) to assess."}), 400
    try:
        architecture = Graph().parse(data=ttl, format="turtle")
        with SPARQL_LOCK:
            result = run_assessment_from_text(ttl)
        gaps = motif_gaps(ttl)
    except Exception as error:  # noqa: BLE001 - surface parse/query errors to the UI
        return jsonify({"error": f"Could not run assessment: {error}"}), 400
    summary = summarize_result(result, architecture=architecture)
    summary["motifGaps"] = gaps
    return jsonify(summary)


@assessment_routes.post("/api/apply-control")
def apply_control_endpoint() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    control = (payload.get("control") or "").strip()
    finding = (payload.get("finding") or "").strip()
    if not (ttl and control and finding):
        return jsonify({"error": "Provide ttl, control, and finding."}), 400
    try:
        architecture = Graph().parse(data=ttl, format="turtle")
        with SPARQL_LOCK:
            result = run_assessment_from_text(ttl)
            added = apply_control(result.combined_graph, URIRef(control), URIRef(finding))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:  
        return jsonify({"error": f"Could not apply the control: {error}"}), 400

    new_ids = sorted({str(s) for s, _p, _o in added if (s, RDF.type, None) in added})
    for triple in added:
        architecture.add(triple)
    architecture.bind("beam", BEAM)
    architecture.bind("pair", PAIR)
    return jsonify(
        {
            "ttl": architecture.serialize(format="turtle"),
            "addedTriples": len(added),
            "newIds": new_ids,
        }
    )


@assessment_routes.post("/api/export/assessment")
def export_assessment() -> object:
    payload = request.get_json(silent=True) or {}
    ttl = (payload.get("ttl") or "").strip()
    export_format = (payload.get("format") or "turtle").strip()
    if not ttl:
        return jsonify({"error": "Provide an architecture graph (Turtle) to export."}), 400
    if export_format not in EXPORT_FORMATS:
        return jsonify(
            {"error": f"Unsupported format {export_format!r}. "
                      f"Use one of: {', '.join(sorted(EXPORT_FORMATS))}."}
        ), 400
    started_at = datetime.now(timezone.utc)
    try:
        architecture = Graph().parse(data=ttl, format="turtle")
        with SPARQL_LOCK:
            result = run_assessment_from_text(ttl)
    except Exception as error:  # noqa: BLE001 - surface parse/query errors to the UI
        return jsonify({"error": f"Could not export assessment: {error}"}), 400

    export = build_export(
        result,
        architecture,
        source_label=payload.get("sourceLabel") or None,
        started_at=started_at,
    )
    media_type, extension = EXPORT_FORMATS[export_format]
    body = export.serialize(export_format)
    return Response(
        body,
        mimetype=media_type,
        headers={
            "Content-Disposition":
                f'attachment; filename="pair-ai-assessment.{extension}"',
            "X-PAIR-AI-Findings": str(result.risk_finding_count),
            "X-PAIR-AI-Matches": str(result.motif_match_count),
        },
    )
