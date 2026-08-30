from __future__ import annotations

import os
import threading

from airiskkg.assessment_runner import run_assessment_from_text

SPARQL_LOCK = threading.Lock()

_WARMUP_STARTED = False


def _warm_query_cache() -> None:
    try:
        with SPARQL_LOCK:
            run_assessment_from_text(
                "@prefix beam: <http://w3id.org/beam/core#> .\n<urn:warm> a beam:System .\n"
            )
    except Exception:  # noqa: BLE001 - warmup is best-effort; the lazy cache still works
        pass

def start_warmup() -> None:
    global _WARMUP_STARTED
    if _WARMUP_STARTED:
        return
    _WARMUP_STARTED = True
    threading.Thread(target=_warm_query_cache, daemon=True).start()


def local_examples_default() -> bool:
    return os.environ.get("PAIR_AI_LOCAL_EXAMPLES", "").strip().lower() in {"1", "true", "yes", "on"}
