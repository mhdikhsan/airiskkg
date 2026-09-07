from __future__ import annotations
from pathlib import Path
from flask import Blueprint, current_app, jsonify
from airiskkg.paths import CONTEXT_EXAMPLE_DIR, EXAMPLE_DIR, EXAMPLE_LOCAL_DIR
from airiskkg.workbench.scenes import scene_for
from airiskkg.workbench.vocabulary import vocabulary

library_routes = Blueprint("library", __name__)


def example_dirs() -> list[tuple[Path, bool, str]]:
    dirs = [(EXAMPLE_DIR, False, "architecture")]
    if CONTEXT_EXAMPLE_DIR.is_dir():
        dirs.append((CONTEXT_EXAMPLE_DIR, False, "process"))
    if current_app.config["LOCAL_EXAMPLES"] and EXAMPLE_LOCAL_DIR.is_dir():
        dirs.append((EXAMPLE_LOCAL_DIR, True, "architecture"))
    # Only the browser tests pass these, and they are flagged local=False
    # because they are not the reader's own graphs - they are the suite's.
    for extra in current_app.config.get("EXTRA_EXAMPLE_DIRS", []):
        if extra.is_dir():
            dirs.append((extra, False, "architecture"))
        if (extra / "context").is_dir():
            dirs.append((extra / "context", False, "process"))
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
            body = {"name": name, "kind": kind, "ttl": path.read_text(encoding="utf-8")}
            if kind == "process":
                body.update(scene_for(
                    path, tuple(current_app.config.get("EXTRA_EXAMPLE_DIRS", []))))
            return jsonify(body)
    return jsonify({"error": "Example not found."}), 404
