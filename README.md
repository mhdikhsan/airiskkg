# AI Risk Knowledge Graph

This repository supports the working paper *A Pattern-Based Method for AI Risk Assessment in System Design*.

It holds the knowledge base behind the method (PAIR-AI), the Python pipeline that
runs it, and a web workbench for drawing a system and assessing it. The method reads
a system's **design**, never its runtime behaviour: what it raises are candidate
risks in the represented structure, for a person to triage.

## The method in brief

An assessment works over three views of the same system:

| View | What it is | Vocabulary |
| --- | --- | --- |
| Architecture | The AI system as a graph of steps and the resources they use and produce | BEAM (Boxology notation) |
| Process | The business process that runs it, joined to the architecture by `pair:refinedBy` | sBPMN 2.0 |
| Risk | What a run raised and what people stated about it, reconciled on one diagram | AIRO chain in BEAM |

The knowledge base pairs two curated libraries:

- **Motif library**: architectural motifs, reusable structures of pattern roles and
  flow relations, each derived from an architecture design pattern (RAG, guardrails,
  agentic tool use, prediction serving, ...) or from a risk catalogue entry. A motif
  is risk-neutral: it says what structure is present, never whether it is dangerous.
- **Risk Pattern Library**: AI risk patterns, each one a motif plus applicability
  conditions, a curated risk mechanism, links into external risk taxonomies, and
  suggested controls.

An assessment runs in four steps:

1. **Match** every motif against the submitted graph (one SPARQL CONSTRUCT per motif).
2. **Propagate** derived facts, such as data categories travelling along the flow,
   to a fixed point.
3. **Evaluate** each AI risk pattern's applicability conditions over its motif matches.
4. **Emit** a candidate risk finding wherever they hold, with its evidence elements,
   mechanism, taxonomy entries and suggested controls.

Every finding is a **candidate**: a structural disposition in the submitted graph,
never a confirmed failure. An absence check ranges over what the graph represents,
so a finding says *no control is represented here*, not *this system has no control*.

The library currently holds **34 motifs** and **33 AI risk patterns** (GenAI,
agentic, ML serving and training, supply chain), **30 controls**, and **124 pattern
roles** filed under 17 categories. Findings link to the OWASP Top 10 for LLM Applications, the OWASP Top 10
for Agentic Applications, the IBM AI Risk Atlas, the MIT AI Risk Repository, NIST AI
600-1, the ML risks of Zhang et al. (2022), and the Eticas AI Risk Taxonomy.
[docs/reference/catalogue.md](docs/reference/catalogue.md) lists every one.

## Quick start

With Docker:

```bash
docker compose up --build      # then open http://localhost:8000
```

Or locally, from the `python/` directory:

```bash
cd python
pip install -e ".[web]"
airiskkg serve                 # then open http://127.0.0.1:5000
```

The **Starter** button loads the tutorial scene: a customer support process with the
support chatbot it runs on.

## The workbench

The editor and the canvas are two views of one Turtle document and stay in sync both
ways: type Turtle and the diagram redraws; draw, connect or rename on the canvas and
the Turtle updates. Three levels share the canvas.

- **Library.** The workbench opens on the libraries: every AI risk pattern with its
  mechanism, what it may lead to and its suggested controls, and every motif drawn
  from its own declaration. From a risk you can add the motif that raises it, with
  the context it needs, and run the assessment.
- **Process.** A BPMN canvas for the business process: pools and lanes, events,
  gateways, activities, data objects and stores, and text annotations. An activity
  names the AI system that carries it out; its chip opens that architecture. What the
  business analyst knows, such as whether a data object holds personal data, is
  stated here and reaches the architecture through a bridge, never copied.
- **Architecture.** A Boxology canvas for the AI system. Elements are connected with
  `use` and `produce`, and the graph stays bipartite: a step reaches a step only
  through the resource one produces and the other uses. Each element is tagged with
  pattern roles and data categories from a picker that offers what fits the element
  first. **Annotation is what makes a graph matchable**: structure says what shape a
  system is, roles say what each part means. Motifs can be dragged in from a tray,
  pre-wired and pre-annotated.
- **Risk.** The run on one diagram, in the notation of risk storming: each concern
  sits above the elements it concerns, stated risks are solid and derived ones dashed.
  Here a team states its own risks, records consequences, controls and priorities,
  and triages each candidate. Severity is never computed; it is a judgement recorded
  with who made it.

Around these:

- **Findings** are grouped into concerns, so the same weakness reached by nested
  motifs appears once. Selecting one highlights its evidence on the canvas.
- **Possible risks** help a drawing that says less than a motif does: an element
  tagged with a coarser role, left untagged, or missing. The workbench suggests the
  annotations that would raise a risk, and applying them re-runs the assessment.
  Suggestions never change what is detected.
- **Controls** can be applied as a registered rewrite that inserts the step a finding
  suggests, bound to the elements the finding cites.
- **Validation** checks the graph against the input contracts and warns when an
  annotation cannot match anything.

A Tool4Boxology export is recognised by its content and normalised to BEAM on load.
The full walkthrough is in [docs/user_guide.md](docs/user_guide.md).

## Command line

```bash
airiskkg assess graph.ttl      # writes motif matches and findings to outputs/output_N/
airiskkg kb-version --json     # fingerprint of the knowledge base, to record with results
airiskkg info                  # print the project paths
```

A run records what it ran on: the submitted graph and the knowledge base each carry
a content fingerprint, so two runs over the same inputs can be recognised as such.

## Repository structure

Three kinds of thing are kept apart on purpose: **knowledge** (the ontology),
**contracts** (SHACL shapes), and **code** (the Python package that runs them).

```text
ontology/                   KNOWLEDGE - the reusable AI risk knowledge base
  core/                     BEAM vocabulary + the PAIR-AI pattern meta-vocabulary
  patterns/                 Motif library, risk pattern library, control layer
    implementation/         Executable SPARQL: match/, risk/, propagation/, mitigation/
  context/                  The business layer bridge (sBPMN to BEAM)
  facets/                   SKOS characterization facets (task, autonomy, data, ...)
  taxonomy/                 External risk taxonomies + the cross-taxonomy mappings
  alignments/               Adapters for external vocabularies (Tool4Boxology, DPV)
  example/                  The graphs the workbench offers (and the Starter scene)
  visualization/            Standalone SPARQL run by hand, not by the pipeline

shacl/                      CONTRACTS - what a graph must satisfy
  architecture_input_contract.ttl   Is this architecture acceptable?
  process_input_contract.ttl        Is this business process well-formed BPMN?
  assessment_output_contract.ttl    Are the emitted findings well formed?
  annotation_guidance.ttl           Will these annotations match anything?

python/                     CODE - the pipeline that runs the knowledge base
  src/airiskkg/             Package: assessment runner, workbench, web app, CLI
  scripts/                  Tracked tooling: something depends on each of these
  tests/                    Test suite
    fixtures/               Graphs a test needs that the deployment does not offer
  pyproject.toml            Package configuration (installable from python/)

data/                       Source data the generated taxonomy layers are built from
docs/                       User guide and reference documents
external/                   Vendored third-party sources (see NOTICE.md)
outputs/                    Generated assessment runs (not knowledge; untracked)
```

Two details worth knowing before editing:

- **`.rq` paths are data.** Each query is registered by a `pair:PatternImplementation`
  whose `pair:implementationPath` is a literal string. Moving or renaming a query
  means updating its declaration too; `test_library_consistency.py` fails if the two
  drift apart.
- **The Python package root is `python/`, not the repository root.** Paths back to
  the knowledge base are resolved at runtime by `airiskkg.paths`, which walks up
  until it finds both `ontology/` and `python/`.

## Development

After any ontology change: parse every `.ttl` with RDFLib, run the SHACL shapes, and
re-run the assessment on the tracked example graphs, explaining any difference in the
set of findings. Every tracked graph has a pinned baseline in `test_propagation.py`.

```bash
cd python
pytest                # the default run: everything except the browser suites
pytest -m browser     # the suites that drive a real headless Chrome or Edge
pytest -m ""          # everything
```

The browser suites take most of the wall clock and need a browser installed, so they
are deselected by default. Run them before calling a change to the canvas, the page or
the endpoints done: they are the only checks that the diagram is actually drawn and
can actually be clicked.

## Documentation

| Document | What it covers |
| --- | --- |
| [User guide](docs/user_guide.md) | Using the workbench, and the annotation vocabulary |
| [Glossary](docs/reference/PAIR-AI_glossary_v1_3.md) | Terminology and the modelling rules R1 to R10 |
| [Method and construction](docs/reference/PAIR-AI_method_and_construction.md) | How the knowledge base was built and how an assessment runs |
| [Catalogue](docs/reference/catalogue.md) | Every motif, AI risk pattern, role and data category |
| [Risk and control linkage](docs/reference/risk_control_linkage.md) | How AI risk patterns reach controls (generated) |
| [Mitigation and gap mechanics](docs/reference/mitigation_and_gap_mechanics.md) | Applying controls and reading near-miss motif matches |

## Licence

The repository is licensed under [CC BY 4.0](LICENSE). Third-party sources keep their
own terms, recorded in [NOTICE.md](NOTICE.md): the OWASP catalogues are CC BY-SA 4.0
and are referenced by identifier and link only, never reproduced.
