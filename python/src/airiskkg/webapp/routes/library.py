"""Reading the library: the builder vocabulary, and the example graphs on offer."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify

from airiskkg.paths import EXAMPLE_DIR, EXAMPLE_LOCAL_DIR
from airiskkg.workbench.vocabulary import vocabulary

library_routes = Blueprint("library", __name__)


def example_dirs() -> list[tuple[Path, bool]]:
    """Directories to offer examples from, each flagged local or not."""
    dirs = [(EXAMPLE_DIR, False)]
    if current_app.config["LOCAL_EXAMPLES"] and EXAMPLE_LOCAL_DIR.is_dir():
        dirs.append((EXAMPLE_LOCAL_DIR, True))
    return dirs


@library_routes.get("/api/vocabulary")
def get_vocabulary() -> object:
    return jsonify(vocabulary())


@library_routes.get("/api/examples")
def list_examples() -> object:
    items = [
        {"name": path.stem, "filename": path.name, "local": is_local}
        for directory, is_local in example_dirs()
        for path in sorted(directory.glob("*.ttl"))
    ]
    return jsonify(items)


@library_routes.get("/api/examples/<name>")
def get_example(name: str) -> object:
    # Same directories the listing offers, so a name the UI cannot see is a
    # name this cannot read either.
    for directory, _is_local in example_dirs():
        path = (directory / f"{name}.ttl").resolve()
        if directory.resolve() in path.parents and path.is_file():
            return jsonify({"name": name, "ttl": path.read_text(encoding="utf-8")})
    return jsonify({"error": "Example not found."}), 404
