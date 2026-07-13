# Running the PAIR-AI Web UI

`python/src/airiskkg/webapp/` is a small Flask app that wraps the assessment
runner in a browser UI: build an architecture graph visually (or paste/upload
Turtle), then run the same PAIR-AI motif-matching and risk-interpretation
assessment used by the CLI.

> As of this writing this required fixing several gaps before it would run —
> see [Fixes applied](#fixes-applied-to-get-this-running) below if you're
> comparing against an older checkout.

## Setup

```bash
# from the repo root
.venv/Scripts/python.exe -m pip install -e "python[web]"
```

This installs Flask (`[web]` extra in `python/pyproject.toml`) on top of the
base `rdflib` dependency.

## Run it

```bash
.venv/Scripts/airiskkg.exe serve
# or with options:
.venv/Scripts/airiskkg.exe serve --host 0.0.0.0 --port 5050 --debug
```

Then open `http://127.0.0.1:5000/` (or whichever host/port you passed).

## Using the UI

The page has two ways to get an architecture graph, and a results panel:

- **Visual builder tab** — add resources (`beam:Data`, `beam:StatisticalModel`,
  etc.) and processes (`beam:Transform`, `beam:Infer`, ...), assign each one
  PAIR pattern roles and data categories from the ontology's vocabulary, wire
  processes together with `use` / `produce` / `inform` edges, then click
  **Generate Turtle →** to compile the model into an architecture graph.
- **Turtle source tab** — load one of the bundled examples
  (`ontology/example/*.ttl`), upload your own `.ttl` file, or paste Turtle
  directly.
- **Run assessment** runs the same motif-matching + risk-interpretation
  pipeline as the CLI and renders findings grouped by OWASP LLM category, with
  evidence elements, candidate risk taxonomy entries, and suggested controls
  per finding.

Nothing is written to disk from the web UI — `POST /api/assess` runs
in-memory (`run_assessment_from_text`) and returns JSON.

## API surface

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Serves the single-page UI |
| `/api/vocabulary` | GET | Roles, data categories, resource/process classes, edge kinds for the builder |
| `/api/examples` | GET | List of bundled example architecture graphs |
| `/api/examples/<name>` | GET | Raw Turtle for one bundled example |
| `/api/build` | POST | Builder model (JSON) → architecture Turtle |
| `/api/assess` | POST | Architecture Turtle (JSON `{"ttl": "..."}`) → structured risk findings (JSON) |

## Fixes applied to get this running

The web app referenced code and files that didn't exist yet in this checkout.
Fixed as part of enabling it:

- `assessment_runner.py` was missing `load_base_graph()` (ontology without any
  architecture instance — used to build `/api/vocabulary`) and
  `run_assessment_from_text()` (assess a Turtle string in-memory, no disk
  writes). Both were added, and `run_assessment()` was refactored to share the
  motif/risk query loop with the new in-memory path.
- `airiskkg/assessment_view.py` didn't exist — added it. It turns an
  `AssessmentResult` into the JSON shape the frontend (`static/app.js`)
  expects (`summary`, `findings[]`, `motifMatches[]`), including grouping
  findings by OWASP LLM category and resolving `skos:prefLabel` /
  `rdfs:label` for every referenced resource.
- `airiskkg/architecture_builder.py` didn't exist — added it, implementing
  `build_ttl(model)` / `BuilderError` to turn the builder's JSON model into
  `beam:`/`pair:` Turtle.
- `webapp/static/index.html` and `webapp/static/style.css` didn't exist (only
  `app.js` was present) — added both, wired to the DOM ids/classes `app.js`
  already expects.
- `flask` wasn't installed in `.venv` even though it's listed as an optional
  dependency — install with `pip install -e "python[web]"` as above.
- `python/pyproject.toml` had invalid TOML (`"airiskkg.webapp" = [static/*]`,
  missing quotes around `static/*`), which broke `pytest` entirely (it reads
  `[tool.pytest.ini_options]` from the same file). Fixed to
  `["static/*"]`.

## Known gaps

- `/api/vocabulary` currently returns an empty `dataCategories` list. The core
  ontology declares `pair:DataCategory` as a class but never declares any
  actual category individuals (e.g. `pair:ProductInformation`,
  `pair:UntrustedContent`) — those only exist ad hoc inside example files
  (`ontology/example/*.ttl`). The data-category multi-select in the builder
  will be empty until the core ontology gets some canonical category
  individuals.
- Same motif-coverage gap as the CLI (see
  [running_assessment_runner.md](running_assessment_runner.md)): assessments
  built around a RAG-style generation step won't trigger
  `risk_system_prompt_leakage` / `risk_improper_output_handling` until a
  matching motif is authored.
