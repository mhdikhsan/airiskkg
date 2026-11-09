"""A generated document must still be generatable.

`risk_control_linkage.md` is checked in so a reader can see it without running
anything, and regenerated rather than hand-edited. Nothing checked the generator
still worked, so when `pair:derivedFrom` moved from naming a URL to naming a
`pair:DesignPatternCitation`, the catalogue grouping silently collapsed to
"unrecorded (26)" and only a hand-run noticed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "python" / "scripts"
TARGET = REPO_ROOT / "docs" / "reference" / "risk_control_linkage.md"

# Each script that rewrites a tracked file, and the file it rewrites. That is
# what earns a place in python/scripts/ rather than python/scripts/local/.
GENERATED = {
    "generate_risk_control_linkage.py": TARGET,
    "generate_catalogue.py": REPO_ROOT / "docs" / "reference" / "catalogue.md",
    "guide_starter_findings.py": REPO_ROOT / "python" / "src" / "airiskkg" / "webapp" / "static" / "guide_content.js",
    "generate_mit_action_layer.py": REPO_ROOT / "ontology" / "taxonomy" / "mit_mitigation_action.ttl",
    "generate_eticas_layer.py": REPO_ROOT / "ontology" / "taxonomy" / "eticas_risk.ttl",
}


@pytest.mark.parametrize("script, target", sorted(GENERATED.items()))
def test_a_generated_file_regenerates_to_what_is_checked_in(script, target) -> None:
    before = target.read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    after = target.read_text(encoding="utf-8")
    if after != before:
        # Put the file back before failing: a test must not edit the repository.
        target.write_text(before, encoding="utf-8")
    assert result.returncode == 0, f"{script} failed:\n{result.stderr[-2000:]}"
    assert after == before, (
        f"{target.relative_to(REPO_ROOT).as_posix()} differs from what {script} "
        "produces. Either the library changed and the file needs regenerating, or "
        "the file was hand-edited, which it never should be."
    )


def test_the_grouping_reads_the_catalogue_each_motif_came_from() -> None:
    """The specific breakage: every motif landing in "unrecorded" still produced a
    document, so only the section headings showed that the grouping had failed."""
    text = TARGET.read_text(encoding="utf-8")
    assert "### unrecorded" not in text, (
        "every motif fell through to 'unrecorded': the generator is reading "
        "pair:derivedFrom as a URL again instead of following it to the "
        "citation's own dct:source"
    )
    for catalogue in ("Gao et al.", "Mercari", "OWASP"):
        assert catalogue in text, f"no motif grouped under {catalogue}"


def test_the_catalogue_lists_every_motif_risk_pattern_and_role() -> None:
    """A section that falls through to empty still produces a document."""
    from airiskkg.assessment_runner import PAIR, load_base_graph
    from rdflib import RDF

    graph = load_base_graph()
    text = (REPO_ROOT / "docs" / "reference" / "catalogue.md").read_text(encoding="utf-8")
    for kind in (PAIR.GraphMotif, PAIR.RiskPattern, PAIR.PatternRole, PAIR.DataCategory):
        missing = [t for t in graph.subjects(RDF.type, kind) if str(t).split("#")[-1] not in text]
        roles_filed_as_headings = [t for t in missing if (t, RDF.type, PAIR.RoleCategory) in graph]
        assert len(missing) == len(roles_filed_as_headings), f"not in the catalogue: {missing}"
