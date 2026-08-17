"""Flask application serving the PAIR-AI risk assessment UI.
Reading the graph
    ``GET  /``                       Single-page UI (editor left, canvas right).
    ``GET  /api/vocabulary``         Pattern roles (grouped, with the element kind
                                     each applies to), data categories, BEAM
                                     element classes, edge kinds, motif templates.
    ``GET  /api/examples``           Names of the example graphs on offer, each
                                     flagged ``local`` or not.
    ``GET  /api/examples/<name>``    Raw Turtle for one of them.
    ``POST /api/graph``              Turtle -> nodes/edges/systems for the canvas.
Editing the graph — each returns the rewritten Turtle, which the editor adopts
    ``POST /api/annotate``           Replace roles/categories on named elements.
    ``POST /api/graph-edit``         One structural edit: add-element, add-edge,
                                     edit-element, add-motif, delete-element.
    ``POST /api/import/t4b``         Tool4Boxology export (N-Triples/Turtle) ->
                                     BEAM Turtle + normalizer notes.
Assessing the graph
    ``POST /api/validate``           SHACL input contract + annotation guidance,
                                     split into violations / warnings / hints.
    ``POST /api/assess``             Findings, motif matches, derived categories,
                                     and the near-miss motif gap report.
    ``POST /api/apply-control``      Insert a control onto the path a finding
                                     cites, via the registered SPARQL rewrite,
                                     and return the amended architecture.
    ``POST /api/export/assessment``  The whole run as a downloadable RDF graph
                                     (Turtle or JSON-LD).
"""

from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from rdflib import RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_export import EXPORT_FORMATS, build_export
from airiskkg.t4b_import import T4bImportError, t4b_to_ttl
from airiskkg.assessment_runner import (
    BEAM,
    PAIR,
    apply_control,
    load_base_graph,
    mitigation_implementations,
    run_assessment_from_text,
)
from airiskkg.assessment_view import summarize_result
from airiskkg.graph_view import graph_view
from airiskkg.paths import CORE_DIR, EXAMPLE_DIR, EXAMPLE_LOCAL_DIR, SHACL_DIR

# Element classes the guided builder offers, paired with the BEAM class they map to.
RESOURCE_CLASSES = [
    (BEAM.Data, "Data"),
    (BEAM.StatisticalModel, "Statistical Model"),
    (BEAM.SemanticModel, "Semantic Model"),
    (BEAM.Symbol, "Symbol"),
]
PROCESS_CLASSES = [
    (BEAM.Transform, "Transform"),
    (BEAM.Infer, "Infer"),
    (BEAM.Train, "Train"),
    (BEAM.Generate, "Generate"),
    (BEAM.Process, "Process (generic)"),
]
EDGE_KINDS = [
    {"id": "use", "label": "uses (process → resource)", "target": "resource"},
    {"id": "produce", "label": "produces (process → resource)", "target": "resource"},
    {"id": "inform", "label": "informs (process → process)", "target": "process"},
]

_SPARQL_LOCK = threading.Lock()

# BEAM process classes (everything else is a resource) - used to attach a
# templated node to its system via hasProcess vs hasResource.
_PROCESS_CLASS_NAMES = {"Transform", "Infer", "Train", "Generate", "Process"}

_MOTIF_SUPPLEMENTS = {
    "EmbeddingsMotif": {
        "nodes": [{"key": "Embedding_IndexingStep", "cls": "Transform", "label": "Indexing", "roles": []}],
        "edges": [
            ["Embedding_IndexingStep", "use", "Embedding_DocumentChunkNode"],
            ["Embedding_IndexingStep", "use", "Embedding_VectorNode"],
            ["Embedding_IndexingStep", "produce", "Embedding_VectorIndexNode"],
        ],
    },
}


@lru_cache(maxsize=1)
def _motif_templates() -> dict:
    graph = load_base_graph()

    def short(term: object) -> str:
        return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]

    templates: dict[str, dict] = {}
    for motif in graph.subjects(RDF.type, PAIR.GraphMotif):
        nodes = []
        node_cls: dict[str, str] = {}
        for pnode in graph.objects(motif, PAIR.hasPatternNode):
            cls = graph.value(pnode, PAIR.expectedClass)
            role = graph.value(pnode, PAIR.expectedRole)
            cls_name = short(cls) if cls is not None else "Data"
            key = short(pnode)
            node_cls[key] = cls_name
            node_label = _display_label(short(role)) if role else str(graph.value(pnode, RDFS.label) or key)
            nodes.append({
                "key": key,
                "cls": cls_name,
                "label": node_label,
                "roles": [short(role)] if role is not None else [],
            })
        edges = []
        for pedge in graph.objects(motif, PAIR.hasPatternEdge):
            src = graph.value(pedge, PAIR.sourcePatternNode)
            pred = graph.value(pedge, PAIR.patternPredicate)
            dst = graph.value(pedge, PAIR.targetPatternNode)
            if src is None or pred is None or dst is None:
                continue
            # BEAM flow edges (use/produce/inform) always originate at a process;
            # drop declaration shortcuts that start at a resource node.
            if node_cls.get(short(src)) not in _PROCESS_CLASS_NAMES:
                continue
            edges.append([short(src), short(pred), short(dst)])
        motif_id = short(motif)
        supplement = _MOTIF_SUPPLEMENTS.get(motif_id)
        if supplement:
            nodes.extend(supplement["nodes"])
            edges.extend(supplement["edges"])
        label = graph.value(motif, RDFS.label)
        templates[motif_id] = {
            "label": str(label) if label else _display_label(motif_id),
            "nodes": nodes,
            "edges": edges,
        }
    return templates


def _motif_template_list() -> list[dict[str, str]]:
    # Catalogue entries: motif name only (alphabetical), no description.
    return sorted(
        ({"id": key, "label": tpl["label"]} for key, tpl in _motif_templates().items()),
        key=lambda item: item["label"].lower(),
    )


def _elements_of_class(graph: Graph, class_name: str) -> set[URIRef]:
    """Elements satisfying a pattern node's expected class, matching what the
    queries accept.

    Step nodes ask for `a/rdfs:subClassOf* beam:Process`, so any process-family
    typing qualifies - beam:Infer, beam:Transform, beam:Train, beam:Generate, or
    beam:Process itself. The gap report must use the same rule or it will claim a
    node is unsatisfied while the assessment matches it."""
    if class_name in _PROCESS_CLASS_NAMES:
        elements: set[URIRef] = set()
        for name in _PROCESS_CLASS_NAMES:
            elements |= set(graph.subjects(RDF.type, BEAM[name]))
        return elements
    return set(graph.subjects(RDF.type, BEAM[class_name]))


def _role_closure(graph: Graph, role_name: str) -> set[URIRef]:
    """A role plus every role beneath it: match queries traverse
    pair:playsRole/pair:subRoleOf*, so a sub-role satisfies its parent."""
    root = PAIR[role_name]
    closure = {root}
    frontier = [root]
    while frontier:
        current = frontier.pop()
        for child in graph.subjects(PAIR.subRoleOf, current):
            if child not in closure:
                closure.add(child)
                frontier.append(child)
    return closure


def _motif_gaps(ttl: str) -> list[dict]:
    """Explain why motifs did NOT match: per motif, which pattern nodes and edges
    the submitted graph leaves unsatisfied.

    Mirrors the match queries deliberately - explicit rdf:type (no subclass
    inference, exactly like the queries) and pair:subRoleOf* for roles - so the
    report can never disagree with the assessment. Fully matched motifs are left
    out; they are already reported as matches."""
    graph = load_base_graph()
    graph.parse(data=ttl, format="turtle")

    def element_label(element: URIRef) -> str:
        return _label(graph, element)

    # elements by explicit type, and the roles each element plays
    roles_of: dict[URIRef, set[URIRef]] = {}
    for element, _p, role in graph.triples((None, PAIR.playsRole, None)):
        roles_of.setdefault(element, set()).add(role)

    gaps: list[dict] = []
    for motif_id, template in _motif_templates().items():
        node_matches: dict[str, set[URIRef]] = {}
        near_misses: dict[str, list[URIRef]] = {}

        for node in template["nodes"]:
            typed = _elements_of_class(graph, node["cls"])
            if node["roles"]:
                wanted = _role_closure(graph, node["roles"][0])
                matched = {e for e in typed if roles_of.get(e, set()) & wanted}
                # right type, missing the role: the actionable hint
                near_misses[node["key"]] = sorted(typed - matched, key=str)[:4]
            else:
                matched = typed
            node_matches[node["key"]] = matched

        edge_ok: dict[tuple, bool] = {}
        for source, predicate, target in template["edges"]:
            sources = node_matches.get(source, set())
            targets = node_matches.get(target, set())
            edge_ok[(source, predicate, target)] = any(
                (s, BEAM[predicate], t) in graph for s in sources for t in targets
            )

        satisfied_nodes = sum(1 for key, elements in node_matches.items() if elements)
        satisfied_edges = sum(1 for ok in edge_ok.values() if ok)
        total = len(node_matches) + len(edge_ok)
        satisfied = satisfied_nodes + satisfied_edges
        if total == 0 or satisfied == total:
            continue  # nothing to explain, or it matched

        label_of = {node["key"]: node["label"] for node in template["nodes"]}
        missing_nodes = [
            {
                "role": label_of[key],
                "candidates": [
                    {"id": str(e), "label": element_label(e)} for e in near_misses.get(key, [])
                ],
            }
            for key, elements in node_matches.items()
            if not elements
        ]
        missing_edges = [
            {
                "text": f"no {label_of.get(source, source)} {predicate}s "
                        f"a {label_of.get(target, target)}",
                "source": label_of.get(source, source),
                "predicate": predicate,
                "target": label_of.get(target, target),
            }
            for (source, predicate, target), ok in edge_ok.items()
            if not ok
        ]

        gaps.append({
            "motifId": motif_id,
            "label": template["label"],
            "satisfied": satisfied,
            "total": total,
            "missingNodes": missing_nodes,
            "missingEdges": missing_edges,
        })

    # closest first: the motifs a small annotation fix would complete
    gaps.sort(key=lambda g: (-(g["satisfied"] / g["total"]), g["label"].lower()))
    return gaps


def _label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, SKOS.prefLabel) or graph.value(resource, RDFS.label)
    if value:
        return str(value)
    return str(resource).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ACRONYM_BOUNDARY = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")


def _display_label(text: str) -> str:
    """Humanize identifier-style names so role/category labels read uniformly.
    Labels that already contain a space are curated and kept as-is; spaceless
    camelCase / underscore names are split ('GenerativeModel' -> 'Generative
    Model', 'LLMResponse' -> 'LLM Response')."""
    if " " in text:
        return text
    spaced = text.replace("_", " ").replace("-", " ")
    spaced = _ACRONYM_BOUNDARY.sub(" ", _CAMEL_BOUNDARY.sub(" ", spaced))
    return re.sub(r"\s+", " ", spaced).strip()


def _vocab_terms(graph: Graph, rdf_class: URIRef) -> list[dict[str, str]]:
    terms = [
        {"id": str(subject), "label": _display_label(_label(graph, subject))}
        for subject in graph.subjects(RDF.type, rdf_class)
    ]
    return sorted(terms, key=lambda item: item["label"].lower())


def _top_level_role(graph: Graph, role: URIRef) -> URIRef | None:
    """Walk pair:subRoleOf up to the role's top-level ancestor (the one with no
    parent). Top-level roles are read from the ontology, never hardcoded. A role
    with several parents resolves to the alphabetically first top ancestor so the
    grouping stays deterministic; cycles are guarded by the visited set."""
    tops: set[URIRef] = set()
    seen: set[URIRef] = {role}
    queue: list[URIRef] = [role]
    while queue:
        node = queue.pop()
        parents = [p for p in graph.objects(node, PAIR.subRoleOf) if isinstance(p, URIRef)]
        if not parents:
            tops.add(node)  # genuinely top-level: no parent at all
            continue
        for parent in parents:
            if parent not in seen:
                seen.add(parent)
                queue.append(parent)
    return sorted(tops, key=str)[0] if tops else None


def _role_applicability(graph: Graph) -> dict[URIRef, str]:
    """Map each pattern role to the kind of element it applies to ("process" or
    "resource").

    Derived, never hardcoded: motif pattern nodes pair an expectedRole with an
    expectedClass, so a role family's element kind is read off those classes via
    the BEAM subclass hierarchy. The evidence is pooled per top-level role family
    (every role under ProcessingStep is a process role, etc.), which also covers
    roles no motif references yet. A family with conflicting or no evidence is
    left unclassified, and the UI then shows those roles for any element."""
    evidence: dict[URIRef, set[str]] = {}
    for pattern_node in graph.subjects(RDF.type, PAIR.PatternNode):
        role = graph.value(pattern_node, PAIR.expectedRole)
        cls = graph.value(pattern_node, PAIR.expectedClass)
        if role is None or cls is None:
            continue
        supers = set(graph.transitive_objects(cls, RDFS.subClassOf)) | {cls}
        if BEAM.Process in supers:
            kind = "process"
        elif BEAM.Resource in supers:
            kind = "resource"
        else:
            continue
        family = _top_level_role(graph, role)
        if family is not None:
            evidence.setdefault(family, set()).add(kind)

    # a family counts as classified only when its evidence is unanimous
    family_kind = {family: next(iter(kinds)) for family, kinds in evidence.items() if len(kinds) == 1}

    applies: dict[URIRef, str] = {}
    for role in graph.subjects(RDF.type, PAIR.PatternRole):
        family = _top_level_role(graph, role)
        kind = family_kind.get(family)
        if kind:
            applies[role] = kind
    return applies


def _role_vocab_terms(graph: Graph) -> list[dict[str, str]]:
    """Pattern roles carry the label of their top-level ancestor as `group`, so
    the UI can render them under <optgroup> headings instead of one flat list,
    plus `applies` ("process" / "resource") so the picker can offer the roles
    that fit the selected element first."""
    applies = _role_applicability(graph)
    terms = []
    for subject in graph.subjects(RDF.type, PAIR.PatternRole):
        top = _top_level_role(graph, subject)
        term = {"id": str(subject), "label": _display_label(_label(graph, subject))}
        if top is not None:
            term["group"] = _display_label(_label(graph, top))
        if subject in applies:
            term["applies"] = applies[subject]
        terms.append(term)
    return sorted(terms, key=lambda item: item["label"].lower())


def _classes(pairs: list[tuple[URIRef, str]]) -> list[dict[str, str]]:
    return [{"id": str(uri), "label": label} for uri, label in pairs]


@lru_cache(maxsize=1)
def _vocabulary() -> dict:
    """Roles and data categories are read from the loaded ontology so the builder
    always reflects the current pattern vocabulary."""
    graph = load_base_graph()
    return {
        "roles": _role_vocab_terms(graph),
        "dataCategories": _vocab_terms(graph, PAIR.DataCategory),
        "resourceClasses": _classes(RESOURCE_CLASSES),
        "processClasses": _classes(PROCESS_CLASSES),
        "edgeKinds": EDGE_KINDS,
        "motifTemplates": _motif_template_list(),
    }


@lru_cache(maxsize=1)
def _shacl_shapes_and_ontology() -> tuple[Graph, Graph]:
    shapes = Graph()
    shapes.parse(SHACL_DIR / "architecture_input_contract.ttl", format="turtle")
    shapes.parse(SHACL_DIR / "annotation_guidance.ttl", format="turtle")
    ontology = Graph()
    for name in ("beam_core.ttl", "beam_core_risk.ttl", "pair_ai_pattern.ttl"):
        ontology.parse(CORE_DIR / name, format="turtle")
    return shapes, ontology


def _shacl_report(ttl: str) -> dict:
    """Validate Turtle against the architecture input contract (Rule R4)."""
    from pyshacl import validate as shacl_validate

    SH = URIRef("http://www.w3.org/ns/shacl#")

    def sh(term: str) -> URIRef:
        return URIRef(str(SH) + term)

    data = Graph()
    data.parse(data=ttl, format="turtle")
    shapes, ontology = _shacl_shapes_and_ontology()
    # The ontology is merged into the data graph, not passed as ont_graph. The
    # guidance shapes walk pair:subRoleOf* inside sh:sparql constraints, and
    # those constraints only see the data graph: with ont_graph the role
    # hierarchy is invisible to them and every Info-level hint silently
    # disappears (onyx_danswer drops from 8 hints to 0).
    _conforms, results_graph, _text = shacl_validate(
        data_graph=data + ontology,
        shacl_graph=shapes,
        advanced=True,
        inference="none",
    )

    def collect(severity: URIRef) -> list[dict]:
        items = []
        for result in results_graph.subjects(sh("resultSeverity"), severity):
            message = results_graph.value(result, sh("resultMessage"))
            focus = results_graph.value(result, sh("focusNode"))
            items.append(
                {
                    "message": str(message) if message else "Constraint violated.",
                    "focusNode": str(focus) if focus else None,
                }
            )
        return sorted(items, key=lambda item: (item["focusNode"] or "", item["message"]))

    violations = collect(sh("Violation"))
    warnings = collect(sh("Warning"))
    hints = collect(sh("Info"))
    return {
        "conforms": not violations,
        "violations": violations,
        "warnings": warnings,
        "hints": hints,
    }


_WARMUP_STARTED = False


def _warm_query_cache() -> None:
    """Pre-compile every assessment query once at startup (in the background) so
    the first Run assessment is as fast as the rest. Holds the SPARQL lock so it
    can't race a request that arrives mid-warmup."""
    try:
        with _SPARQL_LOCK:
            run_assessment_from_text(
                "@prefix beam: <http://w3id.org/beam/core#> .\n<urn:warm> a beam:System .\n"
            )
    except Exception:  # noqa: BLE001 - warmup is best-effort; the lazy cache still works
        pass


def _start_warmup() -> None:
    """Once per process, whatever creates the app.

    Importing this module already builds an app for WSGI servers, and the CLI
    builds another - so an unguarded warm-up ran twice, and because it holds the
    SPARQL lock the second run delayed the first real request instead of
    shortening it."""
    global _WARMUP_STARTED
    if _WARMUP_STARTED:
        return
    _WARMUP_STARTED = True
    threading.Thread(target=_warm_query_cache, daemon=True).start()


def _local_examples_default() -> bool:
    """Whether to offer ontology/example_local/ when the caller says nothing.

    Off. That folder is where confidential and NDA-covered architectures live,
    so exposure has to be something you asked for rather than something you
    forgot to switch off: a WSGI server importing ``app`` gets the safe answer
    without configuring anything, and `cli serve` opts in explicitly because it
    is by definition a local run. ``PAIR_AI_LOCAL_EXAMPLES=1`` opts a WSGI
    server in for the rare case where that is genuinely wanted."""
    return os.environ.get("PAIR_AI_LOCAL_EXAMPLES", "").strip().lower() in {"1", "true", "yes", "on"}


def create_app(*, local_examples: bool | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["LOCAL_EXAMPLES"] = (
        _local_examples_default() if local_examples is None else local_examples
    )
    _start_warmup()

    def _example_dirs() -> list[tuple[Path, bool]]:
        """Directories to offer examples from, each flagged local or not."""
        dirs = [(EXAMPLE_DIR, False)]
        if app.config["LOCAL_EXAMPLES"] and EXAMPLE_LOCAL_DIR.is_dir():
            dirs.append((EXAMPLE_LOCAL_DIR, True))
        return dirs

    @app.get("/")
    def index() -> object:
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/vocabulary")
    def vocabulary() -> object:
        return jsonify(_vocabulary())

    @app.get("/api/examples")
    def examples() -> object:
        items = [
            {"name": path.stem, "filename": path.name, "local": is_local}
            for directory, is_local in _example_dirs()
            for path in sorted(directory.glob("*.ttl"))
        ]
        return jsonify(items)

    @app.get("/api/examples/<name>")
    def example(name: str) -> object:
        # Same directories the listing offers, so a name the UI cannot see is a
        # name this cannot read either.
        for directory, _is_local in _example_dirs():
            path = (directory / f"{name}.ttl").resolve()
            if directory.resolve() in path.parents and path.is_file():
                return jsonify({"name": name, "ttl": path.read_text(encoding="utf-8")})
        return jsonify({"error": "Example not found."}), 404

    @app.post("/api/graph")
    def graph() -> object:
        payload = request.get_json(silent=True) or {}
        ttl = payload.get("ttl") or ""
        if not ttl.strip():
            return jsonify({"systems": [], "nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0}})
        try:
            return jsonify(graph_view(ttl))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.post("/api/validate")
    def validate_contract() -> object:
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        if not ttl:
            return jsonify({"error": "Provide an architecture graph (Turtle) to validate."}), 400
        try:
            with _SPARQL_LOCK:
                report = _shacl_report(ttl)
        except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
            return jsonify({"error": f"Could not validate: {error}"}), 400
        return jsonify(report)

    @app.post("/api/import/t4b")
    def import_t4b() -> object:
        payload = request.get_json(silent=True) or {}
        data = (payload.get("data") or "").strip()
        fmt = "turtle" if payload.get("format") == "turtle" else "nt"
        if not data:
            return jsonify({"error": "Provide a Tool4Boxology export (N-Triples or Turtle) to import."}), 400
        try:
            ttl, warnings = t4b_to_ttl(data, fmt=fmt)
        except T4bImportError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"ttl": ttl, "warnings": warnings})

    @app.post("/api/annotate")
    def annotate() -> object:
        """Apply pair:playsRole / pair:containsDataCategory annotations to the
        elements of an architecture graph. This is the role-tagging step that
        turns an imported, structure-only graph (e.g. from Tool4Boxology /
        t4b-beam, which carry no pattern roles) into one motifs can match.

        Body: {ttl, annotations: {elementId: {roles: [uri...], categories: [uri...]}}}.
        Each element's existing role/category triples are replaced (idempotent),
        so re-applying reflects exactly the current selection.
        """
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        annotations = payload.get("annotations") or {}
        if not ttl:
            return jsonify({"error": "Provide an architecture graph (Turtle) to annotate."}), 400
        try:
            data = Graph()
            data.parse(data=ttl, format="turtle")
        except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
            return jsonify({"error": f"Could not parse the graph: {error}"}), 400

        for element_id, annotation in annotations.items():
            element = URIRef(element_id)
            data.remove((element, PAIR.playsRole, None))
            data.remove((element, PAIR.containsDataCategory, None))
            for role in annotation.get("roles") or []:
                data.add((element, PAIR.playsRole, URIRef(role)))
            for category in annotation.get("categories") or []:
                data.add((element, PAIR.containsDataCategory, URIRef(category)))

        data.bind("beam", BEAM)
        data.bind("pair", PAIR)
        return jsonify({"ttl": data.serialize(format="turtle")})

    @app.post("/api/graph-edit")
    def graph_edit() -> object:
        """Structural edits to the architecture graph from the interactive canvas:
        add an element, or connect two elements with a BEAM flow edge. Element
        identity/structure lives in the graph (rdflib keeps the Turtle clean);
        node positions are a canvas-only concern and never touch the graph.

        Body: {ttl, op, ...}. op="add-element" needs {classUri, category,
        label}; op="add-edge" needs {subject, predicate in use/produce/inform,
        object}. Returns {ttl, newId}.
        """
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        op = payload.get("op")
        if not ttl:
            return jsonify({"error": "Provide a graph to edit."}), 400
        try:
            data = Graph()
            data.parse(data=ttl, format="turtle")
        except Exception as error:  # noqa: BLE001 - surface parse errors to the UI
            return jsonify({"error": f"Could not parse the graph: {error}"}), 400

        local = Namespace("http://w3id.org/airiskkg/local#")
        new_id = None
        if op == "add-element":
            class_uri = payload.get("classUri")
            if not class_uri:
                return jsonify({"error": "add-element needs a classUri."}), 400
            label = (payload.get("label") or "New element").strip()
            existing = {str(s) for s in data.subjects() if str(s).startswith(str(local))}
            index = 1
            while str(local[f"e{index}"]) in existing:
                index += 1
            element = local[f"e{index}"]
            data.add((element, RDF.type, URIRef(class_uri)))
            data.add((element, RDFS.label, Literal(label)))
            system = next(iter(data.subjects(RDF.type, BEAM.System)), None)
            if system is not None:
                predicate = BEAM.hasProcess if payload.get("category") == "process" else BEAM.hasResource
                data.add((system, predicate, element))
            new_id = str(element)
        elif op == "add-edge":
            subject = payload.get("subject")
            predicate = payload.get("predicate")
            obj = payload.get("object")
            if not (subject and predicate and obj):
                return jsonify({"error": "add-edge needs subject, predicate, object."}), 400
            if predicate not in ("use", "produce", "inform"):
                return jsonify({"error": "predicate must be use, produce, or inform."}), 400
            data.add((URIRef(subject), BEAM[predicate], URIRef(obj)))
        elif op == "edit-element":
            element_id = payload.get("element")
            if not element_id:
                return jsonify({"error": "edit-element needs an element."}), 400
            element = URIRef(element_id)
            if "label" in payload:
                data.remove((element, RDFS.label, None))
                if payload.get("label"):
                    data.add((element, RDFS.label, Literal(payload["label"])))
            if payload.get("classUri"):
                # replace the element's BEAM type(s) with the chosen class
                for existing_type in list(data.objects(element, RDF.type)):
                    if str(existing_type).startswith(str(BEAM)):
                        data.remove((element, RDF.type, existing_type))
                data.add((element, RDF.type, URIRef(payload["classUri"])))
            if "roles" in payload:
                data.remove((element, PAIR.playsRole, None))
                for role in payload.get("roles") or []:
                    data.add((element, PAIR.playsRole, URIRef(role)))
            if "categories" in payload:
                data.remove((element, PAIR.containsDataCategory, None))
                for category in payload.get("categories") or []:
                    data.add((element, PAIR.containsDataCategory, URIRef(category)))
            # optional URI rename: keep the namespace, swap the local part
            new_name = (payload.get("name") or "").strip()
            if new_name:
                old = str(element)
                cut = old.rfind("#") if "#" in old else old.rfind("/")
                base = old[: cut + 1]
                local = "".join(ch for ch in new_name if ch.isalnum() or ch in "_.-") or "element"
                renamed = URIRef(base + local)
                if renamed != element:
                    for s, p, o in list(data.triples((element, None, None))):
                        data.remove((s, p, o))
                        data.add((renamed, p, o))
                    for s, p, o in list(data.triples((None, None, element))):
                        data.remove((s, p, o))
                        data.add((s, p, renamed))
                    new_id = str(renamed)
        elif op == "add-motif":
            motif_id = payload.get("motif")
            template = _motif_templates().get(motif_id)
            if template is None:
                return jsonify({"error": f"Unknown motif template: {motif_id}"}), 400
            system = next(iter(data.subjects(RDF.type, BEAM.System)), None)
            if system is None:
                system = local["system"]
                data.add((system, RDF.type, BEAM.System))
                data.add((system, RDFS.label, Literal("My system")))
            existing = {str(s) for s in data.subjects() if str(s).startswith(str(local))}
            counter = [1]

            def _fresh() -> URIRef:
                while str(local[f"e{counter[0]}"]) in existing:
                    counter[0] += 1
                node = local[f"e{counter[0]}"]
                existing.add(str(node))
                counter[0] += 1
                return node

            key_to_uri: dict[str, URIRef] = {}
            new_ids: list[str] = []
            for node in template["nodes"]:
                uri = _fresh()
                key_to_uri[node["key"]] = uri
                is_process = node["cls"] in _PROCESS_CLASS_NAMES
                data.add((uri, RDF.type, BEAM[node["cls"]]))
                if is_process and node["cls"] != "Process":
                    data.add((uri, RDF.type, BEAM.Process))
                data.add((uri, RDFS.label, Literal(node["label"])))
                for role in node.get("roles", []):
                    data.add((uri, PAIR.playsRole, PAIR[role]))
                for category in node.get("cats", []):
                    data.add((uri, PAIR.containsDataCategory, PAIR[category]))
                predicate = BEAM.hasProcess if is_process else BEAM.hasResource
                data.add((system, predicate, uri))
                new_ids.append(str(uri))

            for src, edge, dst in template["edges"]:
                data.add((key_to_uri[src], BEAM[edge], key_to_uri[dst]))

            data.bind("beam", BEAM)
            data.bind("pair", PAIR)
            data.bind("local", local)
            return jsonify(
                {"ttl": data.serialize(format="turtle"), "newIds": new_ids, "groupLabel": template["label"]}
            )
        elif op == "delete-element":
            element_id = payload.get("element")
            if not element_id:
                return jsonify({"error": "delete-element needs an element."}), 400
            element = URIRef(element_id)
            # remove the element and every edge touching it (as subject or object)
            for s, p, o in list(data.triples((element, None, None))):
                data.remove((s, p, o))
            for s, p, o in list(data.triples((None, None, element))):
                data.remove((s, p, o))
        else:
            return jsonify({"error": f"Unknown edit op: {op}"}), 400

        data.bind("beam", BEAM)
        data.bind("pair", PAIR)
        data.bind("local", local)
        return jsonify({"ttl": data.serialize(format="turtle"), "newId": new_id})

    @app.post("/api/assess")
    def assess() -> object:
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        if not ttl:
            return jsonify({"error": "Provide an architecture graph (Turtle) to assess."}), 400
        try:
            with _SPARQL_LOCK:
                result = run_assessment_from_text(ttl)
            # Outside the lock on purpose: the gap report runs no SPARQL, it walks
            # the loaded graph directly, so holding the compiler lock across it
            # would serialize concurrent requests for nothing.
            gaps = _motif_gaps(ttl)
        except Exception as error:  # noqa: BLE001 - surface parse/query errors to the UI
            return jsonify({"error": f"Could not run assessment: {error}"}), 400
        summary = summarize_result(result)
        # why the near-miss motifs did not match, so an empty or thin result set
        # is actionable instead of silent
        summary["motifGaps"] = gaps
        return jsonify(summary)

    @app.post("/api/apply-control")
    def apply_control_endpoint() -> object:
        """Insert a control onto the path a finding cites, and hand back the
        amended architecture.

        The insertion is a registered SPARQL rewrite, not code here: it restates
        the vulnerable shape the risk query found and constructs the step that
        interrupts it, bound to the elements the finding already names. So the
        knowledge of where a control belongs stays in the library beside the
        rule that raised the finding.

        Nothing is asserted about the risk being resolved. The response is a
        graph; the assessor re-runs the assessment over it and the same rules
        speak again (Rule R4)."""
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        control = (payload.get("control") or "").strip()
        finding = (payload.get("finding") or "").strip()
        if not (ttl and control and finding):
            return jsonify({"error": "Provide ttl, control, and finding."}), 400
        try:
            architecture = Graph().parse(data=ttl, format="turtle")
            with _SPARQL_LOCK:
                # The rewrite reads the finding, so it runs against an assessed
                # graph - findings do not exist in the architecture alone.
                result = run_assessment_from_text(ttl)
                added = apply_control(result.combined_graph, URIRef(control), URIRef(finding))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except Exception as error:  # noqa: BLE001 - surface parse/query errors to the UI
            return jsonify({"error": f"Could not apply the control: {error}"}), 400

        new_ids = sorted({str(s) for s, _p, _o in added if (s, RDF.type, None) in added})
        for triple in added:
            architecture.add(triple)
        architecture.bind("beam", BEAM)
        architecture.bind("pair", PAIR)
        return jsonify(
            {
                "ttl": architecture.serialize(format="turtle"),
                "addedTriples": len(added),
                "newIds": new_ids,
            }
        )

    @app.post("/api/export/assessment")
    def export_assessment() -> object:
        """Re-run the assessment and return it as a downloadable RDF graph.

        The run is repeated rather than cached from /api/assess: the editor is
        live, so caching would risk handing back findings for a graph the user
        has since edited - an export that silently disagrees with the screen is
        worse than one that takes a second longer."""
        payload = request.get_json(silent=True) or {}
        ttl = (payload.get("ttl") or "").strip()
        export_format = (payload.get("format") or "turtle").strip()
        if not ttl:
            return jsonify({"error": "Provide an architecture graph (Turtle) to export."}), 400
        if export_format not in EXPORT_FORMATS:
            return jsonify(
                {"error": f"Unsupported format {export_format!r}. "
                          f"Use one of: {', '.join(sorted(EXPORT_FORMATS))}."}
            ), 400
        started_at = datetime.now(timezone.utc)
        try:
            architecture = Graph().parse(data=ttl, format="turtle")
            with _SPARQL_LOCK:
                result = run_assessment_from_text(ttl)
        except Exception as error:  # noqa: BLE001 - surface parse/query errors to the UI
            return jsonify({"error": f"Could not export assessment: {error}"}), 400

        export = build_export(
            result,
            architecture,
            source_label=payload.get("sourceLabel") or None,
            started_at=started_at,
        )
        media_type, extension = EXPORT_FORMATS[export_format]
        body = export.serialize(export_format)
        return Response(
            body,
            mimetype=media_type,
            headers={
                "Content-Disposition":
                    f'attachment; filename="pair-ai-assessment.{extension}"',
                "X-PAIR-AI-Findings": str(result.risk_finding_count),
                "X-PAIR-AI-Matches": str(result.motif_match_count),
            },
        )

    return app


app = create_app()
