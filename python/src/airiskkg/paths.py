from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]  # airiskkg/python
REPO_ROOT = PROJECT_ROOT.parent  # airiskkg (root)
DATA_DIR = REPO_ROOT / "ontology" / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
