from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "ontology").is_dir() and (candidate / "python").is_dir():
            return candidate
    raise RuntimeError(f"Could not locate repository root from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
PROJECT_ROOT = REPO_ROOT / "python"

DOCS_REFERENCE_DIR = REPO_ROOT / "docs" / "reference"
ONTOLOGY_DIR = REPO_ROOT / "ontology"
CORE_DIR = ONTOLOGY_DIR / "core"
PATTERNS_DIR = ONTOLOGY_DIR / "patterns"
IMPLEMENTATION_DIR = PATTERNS_DIR / "implementation"
FACETS_DIR = ONTOLOGY_DIR / "facets"
TAXONOMY_DIR = ONTOLOGY_DIR / "taxonomy"
EXAMPLE_DIR = ONTOLOGY_DIR / "example"
# The user's own graphs: gitignored, excluded from the Docker image, and served
# only by a local `cli serve`. Absent from a fresh clone apart from its README,
# so nothing in the test suite or the shipped library may read from it.
EXAMPLE_LOCAL_DIR = ONTOLOGY_DIR / "example_local"
EXAMPLE_UC_DIR = REPO_ROOT / "docs" / "example_UC"
SHACL_DIR = REPO_ROOT / "shacl"
OUTPUTS_DIR = REPO_ROOT / "outputs"
