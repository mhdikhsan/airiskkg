"""Static wiring checks for the workbench front end.

There is no JavaScript test runner in this repository, so the browser code is
only ever exercised by hand. That leaves one failure mode wide open and cheap to
close from here: a control that is wired to an element id which does not exist.
`document.querySelector("#btn-typo")` returns null, `addEventListener` throws
once at startup, and every handler registered after it silently never binds - so
a single typo can disable unrelated buttons with no visible error.

These tests read the static files as text. They cannot tell you the export
produces a good SVG; they can tell you the button is connected and that the
export code's assumptions about class names still hold.
"""

from __future__ import annotations

import re

import pytest

from airiskkg.paths import REPO_ROOT

STATIC = REPO_ROOT / "python" / "src" / "airiskkg" / "webapp" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_every_element_id_the_app_wires_exists_in_the_page() -> None:
    """A `$("#id")` with no matching element throws at startup and silently
    kills every listener registered after it."""
    page_ids = set(re.findall(r'id="([\w-]+)"', _read("index.html")))
    referenced = set(re.findall(r'\$\("#([\w-]+)"\)', _read("app.js")))
    missing = sorted(referenced - page_ids)
    assert not missing, "app.js wires ids that index.html does not define: " + ", ".join(missing)


def test_export_controls_are_present_and_wired() -> None:
    """Both export entry points exist in the page and have a handler."""
    html, app = _read("index.html"), _read("app.js")
    for element_id in ("btn-export-svg", "btn-export-kg", "export-format"):
        assert f'id="{element_id}"' in html, f"{element_id} missing from index.html"
    for element_id in ("btn-export-svg", "btn-export-kg"):
        assert re.search(rf'\$\("#{element_id}"\)\.addEventListener', app), (
            f"{element_id} has no click handler in app.js"
        )
    assert "/api/export/assessment" in app, "the KG export button calls no endpoint"


def test_graph_view_exposes_the_export_api_the_app_calls() -> None:
    """app.js calls GraphView.exportSvg; graph.js must actually export it."""
    graph, app = _read("graph.js"), _read("app.js")
    # The last assignment, not the first mention: a header comment describing
    # the API would otherwise be matched, and a stale comment would then decide
    # what the test believes is exported.
    assignments = re.findall(r"window\.GraphView\s*=\s*\{([^}]*)\}", graph, re.S)
    assert assignments, "graph.js no longer assigns window.GraphView"
    names = {name.strip() for name in assignments[-1].replace("\n", " ").split(",")}
    for called in re.findall(r"GraphView\.(\w+)\(", app):
        assert called in names, f"app.js calls GraphView.{called}, which graph.js does not expose"


def test_svg_export_strips_classes_that_the_renderer_actually_emits() -> None:
    """The strip list must track the renderer.

    If a class is renamed in the drawing code but not in EXPORT_STRIPPED_CLASSES,
    interaction-only elements start appearing in exported files as invisible
    shapes - the kind of defect nobody notices until a designer opens the SVG."""
    graph = _read("graph.js")
    stripped = re.search(r"EXPORT_STRIPPED_CLASSES\s*=\s*\[(.*?)\]", graph, re.S)
    assert stripped, "EXPORT_STRIPPED_CLASSES is gone; the export would keep hit-areas"
    listed = set(re.findall(r'"([\w-]+)"', stripped.group(1)))

    # These two are emitted by the renderer purely for interaction and must be
    # removed from any export.
    for interaction_class in ("edge-hit", "port"):
        assert f'"{interaction_class}"' in graph, (
            f"the renderer no longer emits .{interaction_class}; "
            "update EXPORT_STRIPPED_CLASSES rather than leaving a stale entry"
        )
        assert interaction_class in listed, (
            f".{interaction_class} is rendered but not stripped from the export"
        )


def test_export_resolves_css_variables_rather_than_hardcoding_them() -> None:
    """Regression guard for a real bug: the first version listed the custom
    properties by hand and missed --accent, so a kept rule referenced a variable
    the exported file never defined and rendered with no colour. The list is now
    derived from the rules themselves."""
    graph = _read("graph.js")
    assert "matchAll(/var\\((--[\\w-]+)\\)/g)" in graph or "var\\((--" in graph, (
        "the exporter no longer derives its custom properties from the kept rules"
    )


def test_every_script_parses() -> None:
    """A syntax error anywhere in a file kills the whole file.

    This is not hypothetical. An escaped newline that survived into the source
    as a real line break left `app.js` unparsable, so nothing in the workbench
    worked at all - no preview, no assessment, no buttons - while the entire
    Python suite stayed green, because none of it loads the browser code. The
    only visible symptom was 304s in the network tab, which are not an error and
    sent the search in the wrong direction.

    Node is used when present rather than required: the check is worth having on
    any machine that can run it, and skipping is honest about the rest.
    """
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; cannot parse-check the browser code")

    broken = []
    scripts = sorted(STATIC.glob("*.js"))
    assert scripts, "expected browser sources to check"
    for path in scripts:
        result = subprocess.run(
            [node, "--check", str(path)], capture_output=True, text=True
        )
        if result.returncode != 0:
            first = (result.stderr.strip().splitlines() or ["parse error"])[0]
            broken.append(f"{path.name}: {first}")
    assert not broken, "browser sources that do not parse:\n" + "\n".join(broken)
