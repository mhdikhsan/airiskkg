"""Flask application serving the PAIR-AI risk assessment UI.

Endpoints
---------
``GET  /``                 Single-page UI.
``GET  /api/vocabulary``   Roles, data categories, and element classes for the builder.
``GET  /api/examples``     Bundled example architecture graphs.
``GET  /api/examples/<n>`` Raw Turtle for one bundled example.
``POST /api/build``        Builder model (JSON) -> architecture Turtle.
``POST /api/assess``       Architecture Turtle -> structured risk findings (JSON).
"""

from __future__ import annotations

from functools import lru_cache

from flask import Flask, jsonify, request, send_from_directory
from rdflib import RDF, RDFS, SKOS, Graph, URIRef

from airiskkg.architecture_builder import BuilderError, build_ttl
from airiskkg.assessment_runner import (
    BEAM,
    PAIR,
    load_base_graph,
    run_assessment_from_text,
)
from airiskkg.assessment_view import summarize_result
from airiskkg.paths import EXAMPLE_DIR

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
