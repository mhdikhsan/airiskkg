"""Motif templates: a declared motif turned into something the canvas can drop in.

Generated from the `pair:hasPatternNode` / `pair:hasPatternEdge` declaration, not
from the match query, which is why a motif whose declaration drifts from its `.rq`
produces a template that cannot match itself. The catalogue and the gap report are
both built from these, so the two can never disagree with each other.
"""

from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, RDFS

from airiskkg.assessment_runner import PAIR, load_base_graph
from airiskkg.workbench.terms import PROCESS_CLASS_NAMES, display_label, short

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
def motif_templates() -> dict:
    graph = load_base_graph()

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
            node_label = display_label(short(role)) if role else str(graph.value(pnode, RDFS.label) or key)
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
            if node_cls.get(short(src)) not in PROCESS_CLASS_NAMES:
                continue
            edges.append([short(src), short(pred), short(dst)])
        motif_id = short(motif)
        supplement = _MOTIF_SUPPLEMENTS.get(motif_id)
        if supplement:
            nodes.extend(supplement["nodes"])
            edges.extend(supplement["edges"])
        label = graph.value(motif, RDFS.label)
        templates[motif_id] = {
            "label": str(label) if label else display_label(motif_id),
            "nodes": nodes,
            "edges": edges,
        }
    return templates


def motif_template_list() -> list[dict[str, str]]:
    # Catalogue entries: motif name only (alphabetical), no description.
    return sorted(
        ({"id": key, "label": tpl["label"]} for key, tpl in motif_templates().items()),
        key=lambda item: item["label"].lower(),
    )
