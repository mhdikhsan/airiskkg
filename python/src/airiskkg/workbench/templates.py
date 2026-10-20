from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, RDFS, SKOS

from airiskkg.assessment_runner import PAIR, PAT, load_base_graph
from airiskkg.workbench.terms import PROCESS_CLASS_NAMES, definition_of, display_label, role_label, short


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
            declared = graph.value(pnode, RDFS.label)
            # a part is drawn under the name of the role it matches on, the terms' own name
            entry = {
                "key": key,
                "cls": cls_name,
                "label": role_label(role) if role is not None else str(declared or key),
                "roles": [short(role)] if role is not None else [],
                "roleLabel": role_label(role) if role is not None else None,
            }
            nodes.append(entry)
        edges = []
        for pedge in graph.objects(motif, PAIR.hasPatternEdge):
            src = graph.value(pedge, PAIR.sourcePatternNode)
            pred = graph.value(pedge, PAIR.patternPredicate)
            dst = graph.value(pedge, PAIR.targetPatternNode)
            if src is None or pred is None or dst is None:
                continue
            if node_cls.get(short(src)) not in PROCESS_CLASS_NAMES:
                continue
            edges.append([short(src), short(pred), short(dst)])
        motif_id = short(motif)
        label = graph.value(motif, RDFS.label)
        templates[motif_id] = {
            "label": str(label) if label else display_label(motif_id),
            "description": definition_of(graph, motif),
            "family": _shelf_label(graph, motif, PAIR.motifFamily),
            "group": _shelf_label(graph, motif, PAIR.motifGroup),
            "nodes": nodes,
            "edges": edges,
            # the general motifs this one is a more detailed form of (shown, never matched on)
            "refines": sorted(short(general) for general in graph.objects(motif, PAIR.refinesMotif)),
        }
    return templates


def _shelf_label(graph, motif, predicate) -> str | None:
    concept = next(iter(sorted(graph.objects(motif, predicate), key=str)), None)
    if concept is None:
        return None
    return str(graph.value(concept, SKOS.prefLabel) or short(concept))


def motif_template_list() -> list[dict[str, str]]:
    """The palette's list, shelved by family and then by group: a long
    alphabetical column says nothing about which kind of AI system each motif
    is a shape of, or which ones are variants of each other."""
    kb = load_base_graph()

    def carried(key: str) -> list[str]:
        """The risk patterns this motif carries, by name, for the tray's detail card."""
        motif = PAT[key]
        return sorted(display_label(str(kb.value(r, RDFS.label) or short(r))).removesuffix(" risk pattern")
                      for r in kb.objects(motif, PAIR.hasRiskPattern))

    return sorted(
        (
            {"id": key, "label": tpl["label"], "family": tpl["family"], "group": tpl["group"],
             # The tray's detail: the library's own words for the motif, not new ones.
             "description": tpl["description"],
             "nodes": tpl["nodes"], "edges": tpl["edges"], "risks": carried(key),
             "refines": tpl["refines"],
             "refinedBy": sorted(k for k, t in motif_templates().items() if key in t["refines"])}
            for key, tpl in motif_templates().items()
        ),
        key=lambda item: item["label"].lower(),
    )
