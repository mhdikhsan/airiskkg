"""What the loaded knowledge base is made of, and a stable identifier for it.

An assessment result only means something if you can say which library produced
it. Nothing recorded that until now: two runs a month apart were indistinguishable
in their output, so a set of evaluation results could not be tied back to the
state of the library it measured.

This module answers one question - *what was loaded?* - and answers it in a form
that survives being written to a file: a content fingerprint over every file that
decides an assessment's output, plus the git revision when there is one.

Two properties matter and neither is obvious:

**The fingerprint covers .rq files, not only .ttl.** Registered SPARQL queries are
read from disk at execution time and never parsed into the graph, so a digest over
the ontology alone would call two runs identical while a rewritten risk query
changed every finding between them - the exact confusion this exists to prevent.

**The git revision is optional, the fingerprint is not.** `.dockerignore` is an
allow-list and does not name `.git`, so the shipped container has no repository to
ask. The fingerprint is computed from file contents and works anywhere; the
revision is a convenience for reconstructing a run in a checkout.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from rdflib import RDF, Graph, Namespace
from rdflib.compare import to_canonical_graph

from airiskkg.paths import (
    CORE_DIR,
    FACETS_DIR,
    PATTERNS_DIR,
    REPO_ROOT,
    TAXONOMY_DIR,
)

PAIR = Namespace("http://w3id.org/airiskkg/pair-ai#")

CORE_FILES = [
    CORE_DIR / "beam_core.ttl",
    CORE_DIR / "beam_core_risk.ttl",
    CORE_DIR / "imports.ttl",
    CORE_DIR / "pair_ai_pattern.ttl",
]

PATTERN_FILES = [
    PATTERNS_DIR / "motif.ttl",
    PATTERNS_DIR / "risk_pattern_library.ttl",
    PATTERNS_DIR / "control_mitigation_layer.ttl",
]


def ontology_files() -> list[Path]:
    """Every .ttl parsed into the knowledge base, in load order.

    The single source of truth for what the library consists of: the loader walks
    exactly this list, so a file cannot be loaded without being fingerprinted, nor
    fingerprinted without being loaded. Adding a module directory is a change here
    and both follow it.

    Note what is absent. `shacl/` shapes answer whether a graph is acceptable and
    whether findings are well formed; they do not change what an assessment
    produces, so they are outside the identity of a run.
    """
    return [
        *CORE_FILES,
        *PATTERN_FILES,
        *sorted(FACETS_DIR.glob("*.ttl")),
        *sorted(TAXONOMY_DIR.glob("*.ttl")),
    ]


def registered_query_files(graph: Graph) -> list[Path]:
    """The .rq files the library registers, read off pair:implementationPath.

    Taken from the registrations rather than from a glob over the implementation
    directory, so the set grows with the library on its own and an unregistered
    stray file does not silently change the fingerprint. `test_library_consistency`
    already guarantees the two agree.
    """
    paths = {
        REPO_ROOT / str(value)
        for value in graph.objects(None, PAIR.implementationPath)
    }
    return sorted((path for path in paths if path.is_file()), key=_sort_key)


def _sort_key(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _digest(paths: list[Path]) -> str:
    """A content hash over a set of files, stable across platforms.

    Line endings are normalized before hashing. This repository is edited on
    Windows and its `.ttl` and `.rq` files churn between CRLF and LF on every
    checkout, so hashing raw bytes would report the same commit as two different
    libraries depending on which machine ran it - and an evaluation comparing a
    laptop run against a CI run would see a difference that is not there.
    """
    outer = hashlib.sha256()
    for path in sorted(paths, key=_sort_key):
        body = path.read_bytes().replace(b"\r\n", b"\n")
        outer.update(_sort_key(path).encode("utf-8"))
        outer.update(b"\0")
        outer.update(hashlib.sha256(body).digest())
    return outer.hexdigest()


def graph_fingerprint(graph: Graph) -> str:
    """A content hash of a graph, stable across parses, orderings and runs.

    The companion to `_digest`, which identifies the library by its files. An
    input graph reaches an assessment as triples in memory - typed into the
    editor, imported from a drawing tool, rewritten by a control - so there may
    be no file to hash, and two files that differ only in whitespace or triple
    order describe the same architecture.

    Blank nodes are canonicalized first, so two parses of the same document
    agree even though rdflib labels their blank nodes differently each time.
    Then N-Triples lines are sorted and hashed.

    Deliberately not `to_isomorphic(graph).graph_digest()`, which is the obvious
    one-liner: it returns rdflib's own hash, so an rdflib upgrade that changed
    the algorithm would silently make every fingerprint already written to an
    export incomparable with every fingerprint written after it. Canonicalize
    with rdflib, but hash with sha256 ourselves.
    """
    canonical = to_canonical_graph(graph)
    digest = hashlib.sha256()
    for line in sorted(canonical.serialize(format="nt").splitlines()):
        stripped = line.strip()
        if stripped:
            digest.update(stripped.encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def _git(*args: str) -> str | None:
    """Ask git something, or None if there is nothing to ask.

    None is a supported answer, not a failure: the container ships without a
    repository, and a source tarball has none either.
    """
    if not (REPO_ROOT / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _is_dirty() -> bool | None:
    """Whether the checkout differs from the revision it reports.

    Deliberately the whole tree, not just the fingerprinted files. The
    fingerprint already pins the knowledge base exactly; what `revision` claims
    is that checking out that commit reproduces the run, and an uncommitted edit
    to the runner breaks that claim while leaving every .ttl and .rq untouched.
    Scoping this to the library would report `clean` in precisely the case where
    the reader most needs to be told otherwise.

    Nothing spurious gets caught: `git diff` reports tracked modifications only,
    and the directories that churn locally - `docs/evaluation/`,
    `ontology/example_local/`, scratch scripts - are ignored or untracked.
    """
    if _git("rev-parse", "--git-dir") is None:
        return None
    try:
        completed = subprocess.run(
            ["git", "diff", "--quiet", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode not in (0, 1):
        return None
    return completed.returncode == 1


@dataclass(frozen=True)
class KnowledgeBaseVersion:
    """The identity of one loaded knowledge base."""

    fingerprint: str
    revision: str | None
    dirty: bool | None
    ontology_files: int
    query_files: int
    motifs: int
    risk_patterns: int
    pattern_roles: int

    @property
    def short(self) -> str:
        return self.fingerprint[:12]

    def as_dict(self) -> dict:
        data = asdict(self)
        data["short"] = self.short
        return data

    def summary(self) -> str:
        state = "" if self.dirty is None else (" +uncommitted" if self.dirty else " clean")
        revision = self.revision[:7] if self.revision else "no revision"
        return (
            f"knowledge base {self.short} - {revision}{state} - "
            f"{self.motifs} motifs, {self.risk_patterns} risk patterns, "
            f"{self.pattern_roles} roles, {self.query_files} queries"
        )


def knowledge_base_version(graph: Graph) -> KnowledgeBaseVersion:
    """Identify the knowledge base `graph` was loaded from.

    Counts are read off the graph rather than kept in a constant, for the reason
    the project already records about its own catalogue: every hand-maintained
    figure but one had drifted before anyone noticed. Stamping them onto each run
    means an evaluation records the library's size at the moment it measured it.
    """
    ontology = ontology_files()
    queries = registered_query_files(graph)
    fingerprinted = [*ontology, *queries]

    def count(rdf_class) -> int:
        return len(set(graph.subjects(RDF.type, rdf_class)))

    return KnowledgeBaseVersion(
        fingerprint=_digest(fingerprinted),
        revision=_git("rev-parse", "HEAD"),
        dirty=_is_dirty(),
        ontology_files=len(ontology),
        query_files=len(queries),
        motifs=count(PAIR.GraphMotif),
        risk_patterns=count(PAIR.RiskPattern),
        pattern_roles=count(PAIR.PatternRole),
    )
