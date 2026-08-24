"""Why a motif did *not* match: the near-miss report.

A thin or empty result set is otherwise silent, and silence reads as "nothing to
worry about" when it usually means "the annotation is incomplete". This says
which pattern nodes and edges the submitted graph leaves unsatisfied, closest
motifs first.
"""

from __future__ import annotations

from rdflib import RDF, Graph, URIRef

from airiskkg.assessment_runner import BEAM, PAIR, load_base_graph
from airiskkg.workbench.templates import motif_templates
from airiskkg.workbench.terms import PROCESS_CLASS_NAMES, label


def _elements_of_class(graph: Graph, class_name: str) -> set[URIRef]:
    """Elements satisfying a pattern node's expected class, matching what the
    queries accept.

    Step nodes ask for `a/rdfs:subClassOf* beam:Process`, so any process-family
    typing qualifies - beam:Infer, beam:Transform, beam:Train, beam:Generate, or
    beam:Process itself. The gap report must use the same rule or it will claim a
    node is unsatisfied while the assessment matches it."""
    if class_name in PROCESS_CLASS_NAMES:
        elements: set[URIRef] = set()
        for name in PROCESS_CLASS_NAMES:
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


def motif_gaps(ttl: str) -> list[dict]:
    """Explain why motifs did NOT match: per motif, which pattern nodes and edges
    the submitted graph leaves unsatisfied.

    Mirrors the match queries deliberately - explicit rdf:type (no subclass
    inference, exactly like the queries) and pair:subRoleOf* for roles - so the
    report can never disagree with the assessment. Fully matched motifs are left
    out; they are already reported as matches."""
    graph = load_base_graph()
    graph.parse(data=ttl, format="turtle")

    def element_label(element: URIRef) -> str:
        return label(graph, element)

    # elements by explicit type, and the roles each element plays
    roles_of: dict[URIRef, set[URIRef]] = {}
    for element, _p, role in graph.triples((None, PAIR.playsRole, None)):
        roles_of.setdefault(element, set()).add(role)

    gaps: list[dict] = []
    for motif_id, template in motif_templates().items():
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
