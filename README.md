# AI Risk Knowledge Graph

Python project for AI risk knowledge graph research.

## Structure

```text
data/          Research data and generated outputs
notebooks/     Exploratory and preprocessing notebooks
src/airiskkg/  Reusable Python code
tests/         Lightweight checks for reusable code
configs/       Example configuration files
scripts/       Small command-line helpers
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
airiskkg info
python -m pytest
```

Keep exploratory work in `notebooks/`. Move reusable functions into
`src/airiskkg/` once they are stable enough to share across notebooks.
