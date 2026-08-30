"""Nothing private leaves this machine.

`ontology/example_local/` is where the user's own architecture graphs live -
confidential systems, NDA-covered use cases, work in progress. Two channels can
publish them, and each has been a real leak in this project:

  * **git** - a forgotten `git add .` before a push.
  * **the image** - `.gitignore` and `.dockerignore` are unrelated files, and
    `COPY . /app` shipped whatever the first one was quietly keeping out.

So the rule is enforced rather than remembered: the folder is ignored, only its
README is tracked, the Docker context is an allow-list, and the webapp offers
the folder only when someone asks for it. A test suite that passes on a fresh
clone is the other half - nothing here may read from the folder either.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.paths import EXAMPLE_DIR, EXAMPLE_LOCAL_DIR, REPO_ROOT  # noqa: E402

flask = pytest.importorskip("flask")

from airiskkg.webapp.app import create_app  # noqa: E402

LOCAL_REL = EXAMPLE_LOCAL_DIR.relative_to(REPO_ROOT).as_posix()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return result.stdout


def test_only_the_readme_is_tracked_under_example_local() -> None:
    """The failure this exists for: a confidential graph committed by accident.

    `git add .` cannot do it while the ignore rule holds, but `git add -f` can,
    and so can an ignore rule that stops matching after someone edits it. This
    reads what git actually tracks rather than what .gitignore says."""
    tracked = [line for line in _git("ls-files", LOCAL_REL).splitlines() if line.strip()]
    assert tracked == [f"{LOCAL_REL}/README.md"], (
        "only the README may be tracked under example_local; found: " + ", ".join(tracked)
    )


def test_a_graph_dropped_into_example_local_is_ignored() -> None:
    """Ask git directly about a path that does not exist yet, which is the case
    that matters: the next file the user drops in."""
    probe = f"{LOCAL_REL}/some_confidential_system.ttl"
    result = subprocess.run(
        ["git", "check-ignore", "-q", probe], cwd=REPO_ROOT, capture_output=True
    )
    assert result.returncode == 0, f"{probe} would NOT be ignored by git"


def test_the_docker_context_excludes_private_paths() -> None:
    """The image is published; the working tree is not.

    Checked as text because building requires a daemon. The allow-list form is
    the point: `*` first, then the paths the app reads. A deny-list would need
    editing every time a private folder is added, which is exactly the habit
    that put NDA graphs in an image once already."""
    lines = [
        line.strip()
        for line in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines[0] == "*", ".dockerignore must start by excluding everything"
    assert f"{LOCAL_REL}" in lines, "example_local must be excluded from inside ontology/"
    allowed = {line[1:] for line in lines if line.startswith("!")}
    # Whatever the app reads at runtime has to survive the allow-list, or the
    # image builds and then fails on the first request.
    for needed in ("python/src", "ontology", "shacl"):
        assert needed in allowed, f".dockerignore drops {needed}, which the app reads"
    assert not any(line.startswith("!docs") for line in lines), (
        "docs/ must stay out: docs/example_UC/ holds NDA-covered graphs"
    )


def test_a_wsgi_app_never_offers_local_examples() -> None:
    """The deployed case. `airiskkg.webapp.app:app` is what gunicorn imports and
    what the Dockerfile runs, and it takes no arguments - so the default has to
    be the safe one, not something a deployment remembers to set."""
    from airiskkg.webapp import app as module

    client = module.app.test_client()
    listed = client.get("/api/examples").get_json()
    assert listed, "expected the bundled examples to be offered"
    assert not any(item["local"] for item in listed), (
        "the module-level WSGI app is offering local examples: "
        + ", ".join(item["name"] for item in listed if item["local"])
    )


def test_a_wsgi_app_cannot_read_a_local_example_by_name() -> None:
    """Not listing them is not enough - the reader must refuse too, or the names
    are simply a guess away.

    Only names that exist *only* locally count. Keeping a working copy of a
    bundled graph in the folder is normal, and that name resolving to the
    bundled file is correct, not a leak."""
    bundled = {path.stem for path in EXAMPLE_DIR.glob("*.ttl")}
    local_graphs = (
        [path for path in sorted(EXAMPLE_LOCAL_DIR.glob("*.ttl")) if path.stem not in bundled]
        if EXAMPLE_LOCAL_DIR.is_dir()
        else []
    )
    if not local_graphs:
        pytest.skip("no local-only graphs on this machine to attempt")
    from airiskkg.webapp import app as module

    client = module.app.test_client()
    for graph in local_graphs:
        response = client.get(f"/api/examples/{graph.stem}")
        assert response.status_code == 404, (
            f"{graph.name} was served by an app that does not offer local examples"
        )


def test_opting_in_offers_them_and_flags_them_as_local() -> None:
    """The other half: a local run must actually work, and must say which graphs
    are the user's own so a loaded one is never mistaken for a shipped one."""
    if not (EXAMPLE_LOCAL_DIR.is_dir() and any(EXAMPLE_LOCAL_DIR.glob("*.ttl"))):
        pytest.skip("no local graphs on this machine to offer")
    client = create_app(local_examples=True).test_client()
    listed = client.get("/api/examples").get_json()
    assert any(item["local"] for item in listed), "opting in offered nothing local"
    for item in listed:
        # Shipped graphs come from two directories now: architectures from
        # example/, and the business processes that go with them from
        # example/context/. The flag that matters is `local` - whose graph it is -
        # so both shipped directories are acceptable homes for local=False.
        homes = (
            [EXAMPLE_LOCAL_DIR]
            if item["local"]
            else [EXAMPLE_DIR, EXAMPLE_DIR / "context"]
        )
        assert any((home / item["filename"]).is_file() for home in homes), (
            f"{item['name']} is flagged local={item['local']} but does not live there"
        )


def test_the_suite_reads_no_local_graph() -> None:
    """A fresh clone has an empty example_local/, so a test that reached into it
    would pass here and fail for everyone else - and would be quietly asserting
    things about a graph nobody else can see."""
    offenders = []
    for path in sorted(Path(__file__).parent.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "EXAMPLE_LOCAL_DIR" in text and path.name != Path(__file__).name:
            offenders.append(path.name)
    assert not offenders, (
        "these tests read ontology/example_local/, which a fresh clone does not have: "
        + ", ".join(offenders)
    )
