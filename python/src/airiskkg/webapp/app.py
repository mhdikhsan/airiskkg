"""Flask application serving the PAIR-AI risk assessment UI.

Endpoints
---------
``GET  /``                 Single-page UI (editor left, live graph preview right).
``GET  /api/vocabulary``   Roles, data categories, and element classes.
``GET  /api/examples``     Bundled example architecture graphs.
``GET  /api/examples/<n>`` Raw Turtle for one bundled example.
``POST /api/graph``        Architecture Turtle -> nodes/edges for the live preview.
``POST /api/validate``     Architecture Turtle -> SHACL input-contract report.
``POST /api/import/t4b``    Tool4Boxology export (N-Triples/Turtle) -> architecture Turtle + notes.
``POST /api/build``        Builder model (JSON) -> architecture Turtle (legacy).
``POST /api/assess``       Architecture Turtle -> structured risk findings (JSON).
"""

from __future__ import annotations

import re
from functools import lru_cache

from flask import Flask, jsonify, request, send_from_directory
from rdflib import RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

from airiskkg.architecture_builder import BuilderError, build_ttl
from airiskkg.t4b_import import T4bImportError, t4b_to_ttl
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
    (BEAM.StatisticalModel, "Statistical Model"),
    (BEAM.SemanticModel, "Semantic Model"),
    (BEAM.Symbol, "Symbol"),
]
PROCESS_CLASSES = [
    (BEAM.Transform, "Transform"),
    (BEAM.Infer, "Infer"),
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


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ACRONYM_BOUNDARY = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")


def _display_label(text: str) -> str:
    """Humanize identifier-style names so role/category labels read uniformly.
    Labels that already contain a space are curated and kept as-is; spaceless
    camelCase / underscore names are split ('GenerativeModel' -> 'Generative
    Model', 'LLMResponse' -> 'LLM Response')."""
    if " " in text:
        return text
    spaced = text.replace("_", " ").replace("-", " ")
    spaced = _ACRONYM_BOUNDARY.sub(" ", _CAMEL_BOUNDARY.sub(" ", spaced))
    return re.sub(r"\s+", " ", spaced).strip()


def _vocab_terms(graph: Graph, rdf_class: URIRef) -> list[dict[str, str]]:
    terms = [
        {"id": str(subject), "label": _display_label(_label(graph, subject))}
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

    @app.post("/api/import/t4b")
    def import_t4b() -> object:
        payload = request.get_json(silent=True) or {}
        data = (payload.get("data") or "").strip()
        fmt = "turtle" if payload.get("format") == "turtle" else "nt"
        if not data:
            return jsonify({"error": "Provide a Tool4Boxology export (N-Triples or Turtle) to import."}), 400
        try:
            ttl, warnings = t4b_to_ttl(data, fmt=fmt)
        except (T4bImportError, BuilderError) as error:
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

    @app.post("/api/annotate")
    def annotate() -> object:
        """Apply pair:playsRole / pair:containsDataCategory annotations to the
        elements of an architecture graph. This is the role-tagging step that
        turns an imported, structure-only graph (e.g. from Tool4Boxology /
        t4b-beam, which carry no pattern roles) into one motifs can match.

        Body: {ttl, annotations: {elementId: {roles: [uri...], categories: [uri...]}}}.
        Each element's existing role/category triples are replaced (idempotent),
        so re-applying reflects exactly the current selection.
        """
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        annotations = payload.get("annotations") or {}
        if not ttl:
            return jsonify({"error": "Provide an architecture graph (Turtle) to annotate."}), 400
        try:
            data = Graph()
            data.parse(data=ttl, format="turtle")
        except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
            return jsonify({"error": f"Could not parse the graph: {error}"}), 400

        for element_id, annotation in annotations.items():
            element = URIRef(element_id)
            data.remove((element, PAIR.playsRole, None))
            data.remove((element, PAIR.containsDataCategory, None))
            for role in annotation.get("roles") or []:
                data.add((element, PAIR.playsRole, URIRef(role)))
            for category in annotation.get("categories") or []:
                data.add((element, PAIR.containsDataCategory, URIRef(category)))

        data.bind("beam", BEAM)
        data.bind("pair", PAIR)
        return jsonify({"ttl": data.serialize(format="turtle")})

    @app.post("/api/graph-edit")
    def graph_edit() -> object:
        """Structural edits to the architecture graph from the interactive canvas:
        add an element, or connect two elements with a BEAM flow edge. Element
        identity/structure lives in the graph (rdflib keeps the Turtle clean);
        node positions are a canvas-only concern and never touch the graph.

        Body: {ttl, op, ...}. op="add-element" needs {classUri, category,
        label}; op="add-edge" needs {subject, predicate in use/produce/inform,
        object}. Returns {ttl, newId}.
        """
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        op = payload.get("op")
        if not ttl:
            return jsonify({"error": "Provide a graph to edit."}), 400
        try:
            data = Graph()
            data.parse(data=ttl, format="turtle")
        except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
            return jsonify({"error": f"Could not parse the graph: {error}"}), 400

        local = Namespace("http://w3id.org/airiskkg/local#")
        new_id = None
        if op == "add-element":
            class_uri = payload.get("classUri")
            if not class_uri:
                return jsonify({"error": "add-element needs a classUri."}), 400
            label = (payload.get("label") or "New element").strip()
            existing = {str(s) for s in data.subjects() if str(s).startswith(str(local))}
            index = 1
            while str(local[f"e{index}"]) in existing:
                index += 1
            element = local[f"e{index}"]
            data.add((element, RDF.type, URIRef(class_uri)))
            data.add((element, RDFS.label, Literal(label)))
            system = next(iter(data.subjects(RDF.type, BEAM.System)), None)
            if system is not None:
                predicate = BEAM.hasProcess if payload.get("category") == "process" else BEAM.hasResource
                data.add((system, predicate, element))
            new_id = str(element)
        elif op == "add-edge":
            subject = payload.get("subject")
            predicate = payload.get("predicate")
            obj = payload.get("object")
            if not (subject and predicate and obj):
                return jsonify({"error": "add-edge needs subject, predicate, object."}), 400
            if predicate not in ("use", "produce", "inform"):
                return jsonify({"error": "predicate must be use, produce, or inform."}), 400
            data.add((URIRef(subject), BEAM[predicate], URIRef(obj)))
        elif op == "edit-element":
            element_id = payload.get("element")
            if not element_id:
                return jsonify({"error": "edit-element needs an element."}), 400
            element = URIRef(element_id)
            if "label" in payload:
                data.remove((element, RDFS.label, None))
                if payload.get("label"):
                    data.add((element, RDFS.label, Literal(payload["label"])))
            if payload.get("classUri"):
                # replace the element's BEAM type(s) with the chosen class
                for existing_type in list(data.objects(element, RDF.type)):
                    if str(existing_type).startswith(str(BEAM)):
                        data.remove((element, RDF.type, existing_type))
                data.add((element, RDF.type, URIRef(payload["classUri"])))
            if "roles" in payload:
                data.remove((element, PAIR.playsRole, None))
                for role in payload.get("roles") or []:
                    data.add((element, PAIR.playsRole, URIRef(role)))
            if "categories" in payload:
                data.remove((element, PAIR.containsDataCategory, None))
                for category in payload.get("categories") or []:
                    data.add((element, PAIR.containsDataCategory, URIRef(category)))
            # optional URI rename: keep the namespace, swap the local part
            new_name = (payload.get("name") or "").strip()
            if new_name:
                old = str(element)
                cut = old.rfind("#") if "#" in old else old.rfind("/")
                base = old[: cut + 1]
                local = "".join(ch for ch in new_name if ch.isalnum() or ch in "_.-") or "element"
                renamed = URIRef(base + local)
                if renamed != element:
                    for s, p, o in list(data.triples((element, None, None))):
                        data.remove((s, p, o))
                        data.add((renamed, p, o))
                    for s, p, o in list(data.triples((None, None, element))):
                        data.remove((s, p, o))
                        data.add((s, p, renamed))
                    new_id = str(renamed)
        elif op == "delete-element":
            element_id = payload.get("element")
            if not element_id:
                return jsonify({"error": "delete-element needs an element."}), 400
            element = URIRef(element_id)
            # remove the element and every edge touching it (as subject or object)
            for s, p, o in list(data.triples((element, None, None))):
                data.remove((s, p, o))
            for s, p, o in list(data.triples((None, None, element))):
                data.remove((s, p, o))
        else:
            return jsonify({"error": f"Unknown edit op: {op}"}), 400

        data.bind("beam", BEAM)
        data.bind("pair", PAIR)
        data.bind("local", local)
        return jsonify({"ttl": data.serialize(format="turtle"), "newId": new_id})

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
