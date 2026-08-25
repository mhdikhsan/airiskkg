"""Shared test fixtures.

The one thing here is example lookup. Tests used to name bundled graphs by
filename, and the filenames get renamed - `onyx_danswer.ttl` became
`onyx_danswer_rag_chatbot.ttl` became `ony_rag_chatbot.ttl` inside two days -
so every rename broke a handful of suites for reasons that had nothing to do
with what they test. A graph's namespace IRI is the stable thing about it: it
survives renames because renaming a file is a filing decision and changing a
namespace is a modelling one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.paths import EXAMPLE_DIR  # noqa: E402

# The IRI each bundled example mints its elements under. Only graphs the
# repository ships belong here: ontology/example_local/ is the user's own,
# absent from a fresh clone, and nothing in the suite may depend on it.
ONYX_NS = "http://w3id.org/airiskkg/example/onyx-danswer#"
GRAPH_RAG_NS = "http://tool4boxology.org/Boxology/graphrag-example"
ANOMALY_NS = "http://w3id.org/airiskkg/example/meter-anomaly#"


def example_path(namespace: str) -> Path:
    """The bundled example graph declaring `namespace`, whatever it is called."""
    hits = [
        path
        for path in sorted(EXAMPLE_DIR.glob("*.ttl"))
        if namespace in path.read_text(encoding="utf-8")
    ]
    if not hits:
        raise AssertionError(
            f"No bundled example declares {namespace}. "
            f"Present: {[p.name for p in sorted(EXAMPLE_DIR.glob('*.ttl'))]}"
        )
    if len(hits) > 1:
        raise AssertionError(
            f"{len(hits)} examples declare {namespace}: {[p.name for p in hits]}. "
            "Example namespaces must identify one graph."
        )
    return hits[0]


@pytest.fixture(scope="session")
def onyx_path() -> Path:
    """The annotated RAG chatbot example (Onyx / Danswer)."""
    return example_path(ONYX_NS)


@pytest.fixture(scope="session")
def graph_rag_path() -> Path:
    """The minimal graph-RAG example."""
    return example_path(GRAPH_RAG_NS)
