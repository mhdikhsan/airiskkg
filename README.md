# AI Risk Knowledge Graph

Research project combining Python analysis with semantic ontology development for AI risk knowledge graphs.

## Repository Structure

```
airiskkg/
├── python/              # Python application and analysis
│   ├── pyproject.toml
│   ├── src/
│   ├── tests/
│   ├── notebooks/
│   ├── scripts/
│   ├── configs/
│   └── README.md
├── ontology/            # Semantic ontology and data
│   ├── data/
│   │   ├── raw/
│   │   ├── processed/
│   │   └── taxonomy/
│   └── README.md
└── README.md (this file)
```

## Quick Start

### Python Development

```powershell
cd python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### Usage

```powershell
airiskkg info
python -m pytest
```

See [python/README.md](python/README.md) for detailed Python setup and usage.

