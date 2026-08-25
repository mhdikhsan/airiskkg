"""Which bundled graphs a process model needs in order to mean anything.

A business process names the AI systems its activities are carried out by, but
it does not contain them - that separation is the whole point of the layer, and
it is also a trap for whoever loads one. Opening the process example on its own
gives a diagram that refers to two architectures that are not there: no nodes,
no motifs, no findings, and nothing on screen saying why.

So a process says what it needs. The answer is derived, not listed: the process
declares `pair:refinedBy` targets, and a bundled graph either declares that
system or it does not.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rdflib import RDF, Graph

from airiskkg.assessment_runner import BEAM, PAIR
from airiskkg.paths import CONTEXT_EXAMPLE_DIR, EXAMPLE_DIR


@lru_cache(maxsize=1)
def _systems_by_example() -> dict[str, list[str]]:
    """Which bundled architecture declares which beam:System.

    Only `ontology/example/` is scanned. A process may not depend on a graph in
    `example_local/`: those are the user's own, absent from a fresh clone, and a
    shipped example that needed one would be broken for everyone else."""
    found: dict[str, list[str]] = {}
    for path in sorted(EXAMPLE_DIR.glob("*.ttl")):
        graph = Graph()
        graph.parse(path, format="turtle")
        systems = sorted(str(s) for s in graph.subjects(RDF.type, BEAM.System))
        if systems:
            found[path.stem] = systems
    return found


def required_architectures(process_path: Path) -> list[dict]:
    """The bundled architectures this process refines, in load order.

    A refinement whose system no bundled graph declares is reported with no
    example name rather than dropped: a process pointing at something that is
    not there is a fault in the process, and swallowing it would hide the fault
    behind an empty canvas."""
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
