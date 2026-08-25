"""Does the front end's module graph still hold together?

The browser is the only thing that runs this code, and it reports a broken
import as one line in a console nobody is watching: the page loads, the panel
that needed the module is simply blank. Three separate breakages during the
split looked exactly like that - an export that was never written because a
regex did not match `$`, a name left pointing at a variable that had moved, and
a pair of panels that each needed the other to have loaded first.

None of those need a browser to find. They are all statements about the text.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath

import pytest

from airiskkg.paths import REPO_ROOT

STATIC = REPO_ROOT / "python" / "src" / "airiskkg" / "webapp" / "static"

IMPORT = re.compile(r'(?m)^import \{([^}]*)\} from "([^"]+)";')
EXPORT = re.compile(r"(?m)^export (?:async function|function|const|let|class) ([A-Za-z_$][\w$]*)")


def modules() -> dict[str, str]:
    """Every module the page can load, keyed by its path relative to static/."""
    found = {}
    for path in sorted(STATIC.rglob("*.js")):
        rel = path.relative_to(STATIC).as_posix()
        found[rel] = path.read_text(encoding="utf-8")
    return found


def imports_of(rel: str, source: str) -> list[tuple[str, list[str]]]:
    """(target module, names) for each import, with the target resolved to a
    path relative to static/ so it can be looked up like any other module."""
    here = PurePosixPath(rel).parent
    out = []
    for names, target in IMPORT.findall(source):
        resolved = posixpath.normpath(posixpath.join(str(here), target)).lstrip("./")
        out.append((resolved, [n.strip() for n in names.split(",") if n.strip()]))
    return out


def test_every_imported_name_is_actually_exported() -> None:
    """The failure this catches took a page down completely: `const $` never got
    its export, so core/api.js could not load, so nothing did."""
    files = modules()
    missing = []
    for rel, source in files.items():
        for target, names in imports_of(rel, source):
            if target not in files:
                missing.append(f"{rel} imports from {target}, which does not exist")
                continue
            exported = set(EXPORT.findall(files[target]))
            for name in names:
                if name not in exported:
                    missing.append(f"{rel} imports {name} from {target}, which does not export it")
    assert not missing, "\n".join(missing)


def test_the_module_graph_has_no_cycles() -> None:
    """Two panels that each import the other work by accident - the browser
    hoists function declarations, so it happens to hold - and stop working the
    moment either one needs the other at load time. The bus exists to keep this
    true; this is what says so."""
    files = modules()
    graph = {rel: {t for t, _ in imports_of(rel, src) if t in files} for rel, src in files.items()}

    state = {}  # 0 = visiting, 1 = done

    def walk(node, trail):
        if state.get(node) == 1:
            return None
        if state.get(node) == 0:
            return trail[trail.index(node):] + [node]
        state[node] = 0
        for nxt in sorted(graph[node]):
            found = walk(nxt, trail + [node])
            if found:
                return found
        state[node] = 1
        return None

    for start in sorted(graph):
        cycle = walk(start, [])
        assert not cycle, "import cycle: " + " -> ".join(cycle)


def test_the_page_puts_exactly_one_thing_on_window() -> None:
    """Module scope is the reason to have modules at all. One handle is left for
    the tests that drive the page from outside, and it is named so that it reads
    as a decision rather than as six leftovers."""
    assigned = set()
    for rel, source in modules().items():
        assigned |= {(rel, name) for name in re.findall(r"(?m)^\s*window\.([A-Za-z_$][\w$]*)\s*=", source)}
    assert {name for _, name in assigned} == {"PairAI"}, (
        "unexpected browser globals: " + ", ".join(sorted(f"{r}: window.{n}" for r, n in assigned))
    )


@pytest.mark.parametrize("panel", ["panels/findings.js", "panels/canvas.js", "core/dom.js"])
def test_a_panel_does_not_reach_for_globals_it_should_import(panel: str) -> None:
    """A module that reads `window.Editor` instead of importing Editor still
    works, right up until load order changes. There is no reason to allow it."""
    source = (STATIC / panel).read_text(encoding="utf-8")
    reached = re.findall(r"window\.(Editor|GraphView|ProcessCanvas|VersionHistory|Annotate)\b", source)
    assert not reached, f"{panel} reaches window.{reached[0]} instead of importing it"
