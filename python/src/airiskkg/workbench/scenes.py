from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rdflib import RDF, Graph

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.paths import CONTEXT_EXAMPLE_DIR, EXAMPLE_DIR


@lru_cache(maxsize=1)
def _systems_by_example() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(EXAMPLE_DIR.glob("*.ttl")):
        graph = Graph()
        graph.parse(path, format="turtle")
        systems = sorted(str(s) for s in graph.subjects(RDF.type, BEAM.System))
        if systems:
            found[path.stem] = systems
    return found


def required_architectures(process_path: Path) -> list[dict]:
    process = Graph()
    process.parse(process_path, format="turtle")

    owner = {
        system: name
        for name, systems in _systems_by_example().items()
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


def scene_for(process_path: Path) -> dict:
    """Everything needed to open this process and get an assessable graph."""
    required = required_architectures(process_path)
    return {
        "requires": required,
        "missing": [row["system"] for row in required if row["example"] is None],
    }


def is_context_example(path: Path) -> bool:
    return path.parent == CONTEXT_EXAMPLE_DIR
