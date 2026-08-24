"""Process-wide concerns the route modules share: the SPARQL lock and start-up
warming.

Kept out of `app.py` so the blueprints can reach them without importing the app
that registers those blueprints.
"""

from __future__ import annotations

import os
import threading

from airiskkg.assessment_runner import run_assessment_from_text

# rdflib's SPARQL compiler keeps global pyparsing state, so two threads
# compiling at once corrupt it. Every route that runs an assessment holds this.
SPARQL_LOCK = threading.Lock()

_WARMUP_STARTED = False


def _warm_query_cache() -> None:
    """Pre-compile every assessment query once at startup (in the background) so
    the first Run assessment is as fast as the rest. Holds the SPARQL lock so it
    can't race a request that arrives mid-warmup."""
    try:
        with SPARQL_LOCK:
            run_assessment_from_text(
                "@prefix beam: <http://w3id.org/beam/core#> .\n<urn:warm> a beam:System .\n"
            )
    except Exception:  # noqa: BLE001 - warmup is best-effort; the lazy cache still works
        pass


def start_warmup() -> None:
    """Once per process, whatever creates the app.

    Importing the app module already builds an app for WSGI servers, and the CLI
    builds another - so an unguarded warm-up ran twice, and because it holds the
    SPARQL lock the second run delayed the first real request instead of
    shortening it."""
    global _WARMUP_STARTED
    if _WARMUP_STARTED:
        return
    _WARMUP_STARTED = True
    threading.Thread(target=_warm_query_cache, daemon=True).start()


def local_examples_default() -> bool:
    """Whether to offer ontology/example_local/ when the caller says nothing.

    Off. That folder is where confidential and NDA-covered architectures live,
    so exposure has to be something you asked for rather than something you
    forgot to switch off: a WSGI server importing ``app`` gets the safe answer
    without configuring anything, and `cli serve` opts in explicitly because it
    is by definition a local run. ``PAIR_AI_LOCAL_EXAMPLES=1`` opts a WSGI
    server in for the rare case where that is genuinely wanted."""
    return os.environ.get("PAIR_AI_LOCAL_EXAMPLES", "").strip().lower() in {"1", "true", "yes", "on"}
