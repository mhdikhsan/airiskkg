"""Flask application serving the PAIR-AI risk assessment UI.
Reading the graph
    ``GET  /``                       Single-page UI (editor left, canvas right).
    ``GET  /api/vocabulary``         Pattern roles (grouped, with the element kind
                                     each applies to), data categories, BEAM
                                     element classes, edge kinds, motif templates.
    ``GET  /api/examples``           Names of the example graphs on offer, each
                                     flagged ``local`` or not.
    ``GET  /api/examples/<name>``    Raw Turtle for one of them.
    ``POST /api/graph``              Turtle -> nodes/edges/systems for the canvas.
    ``POST /api/fingerprint``        Canonical fingerprint of a graph, without
                                     assessing it — so the UI can tell whether
                                     the findings on screen still describe the
                                     graph in the editor.
Editing the graph — each returns the rewritten Turtle, which the editor adopts
    ``POST /api/annotate``           Replace roles/categories on named elements.
    ``POST /api/graph-edit``         One structural edit: add-element, add-edge,
                                     edit-element, add-motif, delete-element.
    ``POST /api/import/t4b``         Tool4Boxology export (N-Triples/Turtle) ->
                                     BEAM Turtle + normalizer notes.
Assessing the graph
    ``POST /api/validate``           SHACL input contract + annotation guidance,
                                     split into violations / warnings / hints.
    ``POST /api/assess``             Findings, motif matches, derived categories,
                                     and the near-miss motif gap report.
    ``POST /api/apply-control``      Insert a control onto the path a finding
                                     cites, via the registered SPARQL rewrite,
                                     and return the amended architecture.
    ``POST /api/export/assessment``  The whole run as a downloadable RDF graph
                                     (Turtle or JSON-LD).

The handlers live in `routes/`, grouped by what the request does to the graph,
and everything they call that decides something about the library lives in
`airiskkg.workbench`. This module is the wiring: it builds the app, settles the
one piece of configuration that matters, and registers the blueprints.
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
