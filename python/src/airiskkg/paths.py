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
TAXONOMY_DIR = ONTOLOGY_DIR / "taxonomy"
EXAMPLE_DIR = ONTOLOGY_DIR / "example"
OUTPUTS_DIR = REPO_ROOT / "outputs"

DATA_DIR = REPO_ROOT / "ontology" / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
