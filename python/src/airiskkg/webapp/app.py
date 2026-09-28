"""Flask application serving the PAIR-AI risk assessment UI.
Reading the graph
    ``GET  /``                       Single-page UI.
    ``GET  /api/library``            The risk pattern library and the motif
                                     library: what the knowledge base can
                                     recognise, before a graph is submitted.
    ``GET  /api/vocabulary``         Pattern roles, data categories, BEAM
                                     element classes, edge kinds, motif templates.
    ``GET  /api/examples``           Names of the example graphs on offer.
    ``GET  /api/examples/<name>``    Raw Turtle for one of them.
    ``POST /api/graph``              Turtle for the canvas.
    ``POST /api/process-edit``       One structural edit to the business layer:
                                     add-pool, add-activity, connect,
                                     set-refines, rename, delete.
    ``POST /api/process``            The business process layer, if the graph
                                     carries one: lanes, activities in flow
                                     order, which activity an AI system refines.
    ``POST /api/fingerprint``        Canonical fingerprint of a graph.
    ``POST /api/annotate``           Replace roles/categories on named elements.
    ``POST /api/graph-edit``         One structural edit: add-element, add-edge,
                                     edit-element, add-motif, delete-element.
    ``POST /api/import/t4b``         Tool4Boxology export (N-Triples/Turtle)
    ``POST /api/validate``           SHACL input contract + annotation guidance
    ``GET  /api/backward``           Reading the library right to left: the
                                     outcomes that must not happen and the
                                     capabilities a system has, each mapped to
                                     the risk patterns that reach them and the
                                     motifs those apply to. Needs no graph.
    ``POST /api/scope``              What a person has stated on this graph -
                                     the scope and the stated risks - read live
                                     from the editor without running anything.
    ``POST /api/scope-edit``         One edit to what a person stated before the
                                     run: set-scope, add-outcome, remove-outcome,
                                     scope-to-system, set-agenda, define-risk, state-risk,
                                     remove-risk,
                                     triage (record or clear a judgement about a
                                     finding; it replaces the emitted status).
    ``POST /api/assess``             Findings, motif matches, derived categories,
                                     the near-miss motif gap report, and the
                                     risk view: the same run grouped into
                                     concerns and read against the stated scope.
    ``POST /api/apply-control``      Insert a control onto the path a finding
                                     cites, via the registered SPARQL rewrite,
                                     and return the amended architecture.
    ``POST /api/export/assessment``  The whole run as a downloadable RDF graph
                                     (Turtle or JSON-LD).
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, send_from_directory

from airiskkg.webapp.routes import BLUEPRINTS
from airiskkg.webapp.runtime import local_examples_default, start_warmup


def create_app(
    *, local_examples: bool | None = None, extra_example_dirs: list | None = None
) -> Flask:
    """`extra_example_dirs` offers graphs from somewhere else as well."""
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["LOCAL_EXAMPLES"] = (
        local_examples_default() if local_examples is None else local_examples
    )
    app.config["EXTRA_EXAMPLE_DIRS"] = [Path(d) for d in (extra_example_dirs or [])]
    start_warmup()

    @app.get("/")
    def index() -> object:
        return send_from_directory(app.static_folder, "index.html")

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app


app = create_app()
