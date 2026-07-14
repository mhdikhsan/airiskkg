"""Flask application serving the PAIR-AI risk assessment UI.

Endpoints
---------
``GET  /``                 Single-page UI (editor left, live graph preview right).
``GET  /api/vocabulary``   Roles, data categories, and element classes.
``GET  /api/examples``     Bundled example architecture graphs.
``GET  /api/examples/<n>`` Raw Turtle for one bundled example.
``POST /api/graph``        Architecture Turtle -> nodes/edges for the live preview.
``POST /api/validate``     Architecture Turtle -> SHACL input-contract report.
``POST /api/import/drawio`` draw.io / diagrams.net XML -> architecture Turtle + warnings.
``POST /api/build``        Builder model (JSON) -> architecture Turtle (legacy).
``POST /api/assess``       Architecture Turtle -> structured risk findings (JSON).
"""

from __future__ import annotations

from functools import lru_cache

from flask import Flask, jsonify, request, send_from_directory
from rdflib import RDF, RDFS, SKOS, Graph, URIRef

from airiskkg.architecture_builder import BuilderError, build_ttl
from airiskkg.drawio_import import DrawioImportError, drawio_to_ttl
from airiskkg.assessment_runner import (
    BEAM,
    PAIR,
    load_base_graph,
    run_assessment_from_text,
)
from airiskkg.assessment_view import summarize_result
from airiskkg.graph_view import graph_view
from airiskkg.paths import CORE_DIR, EXAMPLE_DIR, SHACL_DIR

# Element classes the guided builder offers, paired with the BEAM class they map to.
RESOURCE_CLASSES = [
    (BEAM.Data, "Data"),
    (BEAM.StatisticalModel, "Statistical Model (LLM / ML model)"),
    (BEAM.Symbol, "Symbol"),
]
PROCESS_CLASSES = [
    (BEAM.Transform, "Transform (preprocessing, reformulation, prompting)"),
    (BEAM.Infer, "Infer (retrieval, prediction)"),
    (BEAM.Train, "Train"),
    (BEAM.Generate, "Generate"),
    (BEAM.Process, "Process (generic)"),
]
EDGE_KINDS = [
    {"id": "use", "label": "uses (process → resource)", "target": "resource"},
    {"id": "produce", "label": "produces (process → resource)", "target": "resource"},
    {"id": "inform", "label": "informs (process → process)", "target": "process"},
]


def _label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, SKOS.prefLabel) or graph.value(resource, RDFS.label)
    if value:
        return str(value)
    return str(resource).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _vocab_terms(graph: Graph, rdf_class: URIRef) -> list[dict[str, str]]:
    terms = [
        {"id": str(subject), "label": _label(graph, subject)}
        for subject in graph.subjects(RDF.type, rdf_class)
    ]
    return sorted(terms, key=lambda item: item["label"].lower())


def _classes(pairs: list[tuple[URIRef, str]]) -> list[dict[str, str]]:
    return [{"id": str(uri), "label": label} for uri, label in pairs]


@lru_cache(maxsize=1)
def _vocabulary() -> dict:
    """Roles and data categories are read from the loaded ontology so the builder
    always reflects the current pattern vocabulary."""
    graph = load_base_graph()
    return {
        "roles": _vocab_terms(graph, PAIR.PatternRole),
        "dataCategories": _vocab_terms(graph, PAIR.DataCategory),
        "resourceClasses": _classes(RESOURCE_CLASSES),
        "processClasses": _classes(PROCESS_CLASSES),
        "edgeKinds": EDGE_KINDS,
    }


@lru_cache(maxsize=1)
def _shacl_shapes_and_ontology() -> tuple[Graph, Graph]:
    shapes = Graph()
    shapes.parse(SHACL_DIR / "architecture_input_contract.ttl", format="turtle")
    ontology = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        ontology.parse(CORE_DIR / name, format="turtle")
    return shapes, ontology


def _shacl_report(ttl: str) -> dict:
    """Validate Turtle against the architecture input contract (Rule R4)."""
    from pyshacl import validate as shacl_validate

    SH = URIRef("http://www.w3.org/ns/shacl#")

    def sh(term: str) -> URIRef:
        return URIRef(str(SH) + term)

    data = Graph()
    data.parse(data=ttl, format="turtle")
    shapes, ontology = _shacl_shapes_and_ontology()
    _conforms, results_graph, _text = shacl_validate(
        data_graph=data,
        shacl_graph=shapes,
        ont_graph=ontology,
        advanced=True,
        inference="none",
    )

    def collect(severity: URIRef) -> list[dict]:
        items = []
        for result in results_graph.subjects(sh("resultSeverity"), severity):
            message = results_graph.value(result, sh("resultMessage"))
            focus = results_graph.value(result, sh("focusNode"))
            items.append(
                {
                    "message": str(message) if message else "Constraint violated.",
                    "focusNode": str(focus) if focus else None,
                }
            )
        return sorted(items, key=lambda item: (item["focusNode"] or "", item["message"]))

    violations = collect(sh("Violation"))
    warnings = collect(sh("Warning"))
    return {
        "conforms": not violations,
        "violations": violations,
        "warnings": warnings,
    }


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    @app.get("/")
    def index() -> object:
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/vocabulary")
    def vocabulary() -> object:
        return jsonify(_vocabulary())

    @app.get("/api/examples")
    def examples() -> object:
        items = [
            {"name": path.stem, "filename": path.name}
            for path in sorted(EXAMPLE_DIR.glob("*.ttl"))
        ]
        return jsonify(items)

    @app.get("/api/examples/<name>")
    def example(name: str) -> object:
        path = (EXAMPLE_DIR / f"{name}.ttl").resolve()
        # Guard against path traversal: the resolved file must stay inside EXAMPLE_DIR.
        if EXAMPLE_DIR.resolve() not in path.parents or not path.is_file():
            return jsonify({"error": "Example not found."}), 404
        return jsonify({"name": name, "ttl": path.read_text(encoding="utf-8")})

    @app.post("/api/graph")
    def graph() -> object:
        payload = request.get_json(silent=True) or {}
        ttl = payload.get("ttl") or ""
        if not ttl.strip():
            return jsonify({"systems": [], "nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0}})
        try:
            return jsonify(graph_view(ttl))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.post("/api/validate")
    def validate_contract() -> object:
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        if not ttl:
            return jsonify({"error": "Provide an architecture graph (Turtle) to validate."}), 400
        try:
            report = _shacl_report(ttl)
        except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
            return jsonify({"error": f"Could not validate: {error}"}), 400
        return jsonify(report)

    @app.post("/api/import/drawio")
    def import_drawio() -> object:
        payload = request.get_json(silent=True) or {}
        xml = (payload.get("xml") or "").strip()
        if not xml:
            return jsonify({"error": "Provide draw.io XML to import."}), 400
        try:
            ttl, warnings = drawio_to_ttl(xml)
        except (DrawioImportError, BuilderError) as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"ttl": ttl, "warnings": warnings})

    @app.post("/api/build")
    def build() -> object:
        model = request.get_json(silent=True) or {}
        try:
            ttl = build_ttl(model)
        except BuilderError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"ttl": ttl})

    @app.post("/api/assess")
    def assess() -> object:
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        if not ttl:
            return jsonify({"error": "Provide an architecture graph (Turtle) to assess."}), 400
        try:
            result = run_assessment_from_text(ttl)
        except Exception as error:  # noqa: BLE001 - surface parse/query errors to the UI
            return jsonify({"error": f"Could not run assessment: {error}"}), 400
        return jsonify(summarize_result(result))

    return app


app = create_app()
