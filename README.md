# AI Risk Knowledge Graph Python Workspace

This folder contains the  workspace for the working paper:

**A Pattern-Based Method for Design-Time AI Risk Assessment Using Knowledge Graphs Operationalization**

The code supports simple analysis, preprocessing, and experimentation around
AI risk knowledge graphs and ontology patterns.

## Structure

```text
src/airiskkg/  Reusable Python code and CLI tools
tests/         Tests
notebooks/     Exploratory notebooks
scripts/       Helper scripts
configs/       Configuration examples
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m ipykernel install --user --name airiskkg
```

## Usage

```powershell
# Show project information
airiskkg info

# Run tests
python -m pytest

# Run notebooks
jupyter lab notebooks/
```

## Development

Keep exploratory work in `notebooks/`. Move reusable code into
`src/airiskkg/` when it becomes useful across notebooks or scripts.

The related ontology files are stored in `../ontology/`.
