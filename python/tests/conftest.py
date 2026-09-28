"""Shared test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.paths import EXAMPLE_DIR  # noqa: E402

# Graphs a test needs but the deployment does not offer.
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

# The IRI each bundled example mints its elements under.
ONYX_NS = "http://w3id.org/airiskkg/example/onyx-danswer#"
GRAPH_RAG_NS = "http://tool4boxology.org/Boxology/graphrag-example"
WIEN_ENERGIE_NS = "http://w3id.org/airiskkg/example/wien-energie#"
TARIFF_NS = "http://w3id.org/airiskkg/example/wien-energie-tariff#"
AGENT_NS = "http://w3id.org/airiskkg/example/it-support#"
PROMPT_INJECTION_NS = "http://w3id.org/airiskkg/example/prompt-injection#"


def _declaring(directory: Path, namespace: str) -> list[Path]:
    if not directory.is_dir():
        return []
    return [
        path
        for path in sorted(directory.glob("*.ttl"))
        if namespace in path.read_text(encoding="utf-8")
    ]


def example_path(namespace: str) -> Path:
    """The graph declaring `namespace`: the shipped example if there is one,
    otherwise the test fixture kept for it."""
    hits = _declaring(EXAMPLE_DIR, namespace) or _declaring(FIXTURE_DIR, namespace)
    if not hits:
        raise AssertionError(
            f"No example or fixture declares {namespace}. "
            f"Shipped: {[p.name for p in sorted(EXAMPLE_DIR.glob('*.ttl'))]}; "
            f"fixtures: {[p.name for p in sorted(FIXTURE_DIR.glob('*.ttl'))]}"
        )
    if len(hits) > 1:
        raise AssertionError(
            f"{len(hits)} graphs declare {namespace}: {[p.name for p in hits]}. "
            "Example namespaces must identify one graph."
        )
    return hits[0]


def process_path(name: str) -> Path:
    """A business process model, shipped or kept as a fixture."""
    for directory in (EXAMPLE_DIR / "context", FIXTURE_DIR / "context"):
        candidate = directory / f"{name}.ttl"
        if candidate.is_file():
            return candidate
    raise AssertionError(f"No process model called {name}.ttl is shipped or kept as a fixture.")


@pytest.fixture(scope="session")
def onyx_path() -> Path:
    """The annotated RAG chatbot example (Onyx / Danswer)."""
    return example_path(ONYX_NS)


@pytest.fixture(scope="session")
def graph_rag_path() -> Path:
    """The minimal graph-RAG example."""
    return example_path(GRAPH_RAG_NS)


@pytest.fixture(scope="session")
def wien_energie_path() -> Path:
    """The Wien Energie chatbot (BotTina): the graph the bundled process refines."""
    return example_path(WIEN_ENERGIE_NS)
