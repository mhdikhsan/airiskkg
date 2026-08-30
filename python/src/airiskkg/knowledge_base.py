from __future__ import annotations

import hashlib
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from rdflib import RDF, Graph, Namespace
from rdflib.compare import to_canonical_graph

from airiskkg.paths import (
    CONTEXT_DIR,
    CORE_DIR,
    FACETS_DIR,
    PATTERNS_DIR,
    REPO_ROOT,
    SBPMN_DIR,
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
      return [
        *CORE_FILES,
        *PATTERN_FILES,
        *sorted(FACETS_DIR.glob("*.ttl")),
        *sorted(TAXONOMY_DIR.glob("*.ttl")),
        *sorted(CONTEXT_DIR.glob("*.ttl")),
        *sorted(SBPMN_DIR.glob("*.ttl")),
    ]


def registered_query_files(graph: Graph) -> list[Path]:
 
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
  
    outer = hashlib.sha256()
    for path in sorted(paths, key=_sort_key):
        body = path.read_bytes().replace(b"\r\n", b"\n")
        outer.update(_sort_key(path).encode("utf-8"))
        outer.update(b"\0")
        outer.update(hashlib.sha256(body).digest())
    return outer.hexdigest()


def graph_fingerprint(graph: Graph) -> str:
 
    canonical = to_canonical_graph(graph)
    digest = hashlib.sha256()
    for line in sorted(canonical.serialize(format="nt").splitlines()):
        stripped = line.strip()
        if stripped:
            digest.update(stripped.encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def _git(*args: str) -> str | None:
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
