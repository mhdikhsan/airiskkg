"""Flask application serving the PAIR-AI risk assessment UI.
Reading the graph
    ``GET  /``                       Single-page UI.
    ``GET  /api/vocabulary``         Pattern roles, data categories, BEAM
                                     element classes, edge kinds, motif templates.
    ``GET  /api/examples``           Names of the example graphs on offer.
    ``GET  /api/examples/<name>``    Raw Turtle for one of them.
    ``POST /api/graph``              Turtle for the canvas.
    ``POST /api/process``            The business process layer, if the graph
                                     carries one: lanes, activities in flow
                                     order, which activity an AI system refines.
    ``POST /api/fingerprint``        Canonical fingerprint of a graph.
    ``POST /api/annotate``           Replace roles/categories on named elements.
    ``POST /api/graph-edit``         One structural edit: add-element, add-edge,
                                     edit-element, add-motif, delete-element.
    ``POST /api/import/t4b``         Tool4Boxology export (N-Triples/Turtle)
    ``POST /api/validate``           SHACL input contract + annotation guidance
    ``POST /api/assess``             Findings, motif matches, derived categories,
                                     and the near-miss motif gap report.
    ``POST /api/apply-control``      Insert a control onto the path a finding
                                     cites, via the registered SPARQL rewrite,
                                     and return the amended architecture.
    ``POST /api/export/assessment``  The whole run as a downloadable RDF graph
                                     (Turtle or JSON-LD).
"""

from __future__ import annotations

from flask import Flask, send_from_directory

from airiskkg.webapp.routes import BLUEPRINTS
from airiskkg.webapp.runtime import local_examples_default, start_warmup


def create_app(*, local_examples: bool | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["LOCAL_EXAMPLES"] = (
        local_examples_default() if local_examples is None else local_examples
    )
    start_warmup()

    @app.get("/")
    def index() -> object:
        return send_from_directory(app.static_folder, "index.html")

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app


app = create_app()
