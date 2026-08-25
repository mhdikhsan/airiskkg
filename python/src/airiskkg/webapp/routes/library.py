from __future__ import annotations
from pathlib import Path
from flask import Blueprint, current_app, jsonify
from airiskkg.paths import CONTEXT_EXAMPLE_DIR, EXAMPLE_DIR, EXAMPLE_LOCAL_DIR
from airiskkg.workbench.vocabulary import vocabulary

library_routes = Blueprint("library", __name__)


def example_dirs() -> list[tuple[Path, bool, str]]:
    """Directories to offer graphs from: the path, whether it is local, and what
    kind of graph it holds.

    Business processes are offered separately and are not architectures: one
    describes an AI system, the other describes where a system sits. Loading a
    process must therefore ADD to the graph on screen rather than replace it -
    an assessment reads both together - which is why the kind travels with the
    listing instead of being guessed from the filename."""
    dirs = [(EXAMPLE_DIR, False, "architecture")]
    if CONTEXT_EXAMPLE_DIR.is_dir():
        dirs.append((CONTEXT_EXAMPLE_DIR, False, "process"))
    if current_app.config["LOCAL_EXAMPLES"] and EXAMPLE_LOCAL_DIR.is_dir():
        dirs.append((EXAMPLE_LOCAL_DIR, True, "architecture"))
    return dirs


@library_routes.get("/api/vocabulary")
def get_vocabulary() -> object:
    return jsonify(vocabulary())


@library_routes.get("/api/examples")
def list_examples() -> object:
    items = [
        {"name": path.stem, "filename": path.name, "local": is_local, "kind": kind}
        for directory, is_local, kind in example_dirs()
        for path in sorted(directory.glob("*.ttl"))
    ]
    return jsonify(items)


@library_routes.get("/api/examples/<name>")
def get_example(name: str) -> object:
    for directory, _is_local, kind in example_dirs():
        path = (directory / f"{name}.ttl").resolve()
        if directory.resolve() in path.parents and path.is_file():
            return jsonify(
                {"name": name, "kind": kind, "ttl": path.read_text(encoding="utf-8")}
            )
    return jsonify({"error": "Example not found."}), 404
