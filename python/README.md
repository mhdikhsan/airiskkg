# Python Application

Python development environment for AI risk knowledge graph analysis and preprocessing.

## Structure

```text
src/airiskkg/  Reusable Python code and CLI
tests/         Test suite
notebooks/     Exploratory and preprocessing notebooks
scripts/       Command-line helper scripts
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
# CLI commands
airiskkg info

# Run tests
python -m pytest

# Run notebooks
jupyter lab notebooks/
```

## Development

Keep exploratory work in `notebooks/`. Move reusable functions into
`src/airiskkg/` once they are stable enough to share across notebooks.

Related data is stored in `../ontology/data/`.
