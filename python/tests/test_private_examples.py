"""Nothing private leaves this machine."""

from __future__ import annotations

import re
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
    """The failure this exists for: a confidential graph committed by accident."""
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
    """The image is published; the working tree is not."""
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
    """The deployed case."""
    from airiskkg.webapp import app as module

    client = module.app.test_client()
    listed = client.get("/api/examples").get_json()
    assert listed, "expected the bundled examples to be offered"
    assert not any(item["local"] for item in listed), (
        "the module-level WSGI app is offering local examples: "
        + ", ".join(item["name"] for item in listed if item["local"])
    )


def test_a_wsgi_app_cannot_read_a_local_example_by_name() -> None:
    """Not listing them is not enough - the reader must refuse too, or the names are simply a guess away."""
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


# Namespaces anything published from this repository may mint IRIs under: the
# project's own, the vocabularies its graphs are written in, synthetic hosts,
# and sources already public. Compared case-insensitively.
PUBLISHABLE_NAMESPACES = (
    "http://w3id.org/airiskkg/",
    "http://w3id.org/beam/",
    "http://example.org/",
    "http://example.com/",
    "http://www.w3.org/",
    "https://www.w3.org/",
    "http://purl.org/dc/",
    "http://purl.org/vocab/",
    "https://w3id.org/dpv",
    "https://w3id.org/sssom",
    "https://w3id.org/semapv/",
    "https://sbpmn.github.io/",
    "http://tool4boxology.org/",
    "https://creativecommons.org/licenses/",
    "https://docs.onyx.app/",
    "https://github.com/onyx-dot-app/",
    "https://airov.at/",
)

_BRACKETED_IRI = re.compile(r"<\s*(https?://[^>\s]+)\s*>")
_ANY_IRI = re.compile(r"""https?://[^\s<>"'`)\]},;]+""")


def _iris_of(path: Path) -> set[str]:
    """A .ttl or .rq is RDF end to end, so every IRI in it is content."""
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = _ANY_IRI if path.suffix in {".ttl", ".rq"} else _BRACKETED_IRI
    return set(pattern.findall(text))


def test_no_published_graph_mints_iris_outside_the_allow_list() -> None:
    """The third channel: a confidential graph pasted inline rather than dropped in a folder."""
    tracked = [
        REPO_ROOT / name
        for name in _git("ls-files", "python/tests", "ontology/example").split()
    ]
    assert tracked, "expected tracked files to scan"
    offenders: list[str] = []
    for path in tracked:
        if not path.is_file():
            continue
        for iri in sorted(_iris_of(path)):
            if not iri.lower().startswith(PUBLISHABLE_NAMESPACES):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {iri}")
    assert not offenders, (
        "these tracked files mint IRIs under a namespace that is not on the "
        "publishable allow-list - if the namespace is genuinely public, add it "
        "to PUBLISHABLE_NAMESPACES; if it is a client's, it must not be "
        "committed:\n  " + "\n  ".join(offenders[:20])
    )
