from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rdflib import RDF, Graph

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.paths import CONTEXT_EXAMPLE_DIR, EXAMPLE_DIR


@lru_cache(maxsize=8)
def _systems_by_example(extra: tuple[Path, ...] = ()) -> dict[str, list[str]]:
    """Which example holds which architecture.

    `extra` is for a caller that offers graphs from somewhere else as well - the
    browser tests do, so a process can name an architecture the deployment does
    not ship. Cached per directory set rather than once, since the answer
    depends on which directories were asked about."""
    found: dict[str, list[str]] = {}
    for directory in (EXAMPLE_DIR, *extra):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.ttl")):
            graph = Graph()
            graph.parse(path, format="turtle")
            systems = sorted(str(s) for s in graph.subjects(RDF.type, BEAM.System))
            if systems:
                found[path.stem] = systems
    return found


def required_architectures(process_path: Path, extra: tuple[Path, ...] = ()) -> list[dict]:
    process = Graph()
    process.parse(process_path, format="turtle")

    owner = {
        system: name
        for name, systems in _systems_by_example(extra).items()
        for system in systems
    }

    seen: set[str] = set()
    required = []
    for system in sorted({str(s) for s in process.objects(None, PAIR.refinedBy)}):
        if system in seen:
            continue
        seen.add(system)
        required.append({"system": system, "example": owner.get(system)})
    return required


def scene_for(process_path: Path, extra: tuple[Path, ...] = ()) -> dict:
    """Everything needed to open this process and get an assessable graph."""
    required = required_architectures(process_path, extra)
    return {
        "requires": required,
        "missing": [row["system"] for row in required if row["example"] is None],
    }


def is_context_example(path: Path) -> bool:
    return path.parent == CONTEXT_EXAMPLE_DIR
