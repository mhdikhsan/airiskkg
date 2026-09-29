"""Reading the constituent equation right to left.

Forward, the method runs motif -> conditions -> finding. An analyst who has not
drawn anything yet needs the other direction: name an outcome that must not
happen, and the library says which risk patterns reach it, what they ask, and
what structure would have to be present for them to fire.

Two entry axes, because one does not cover the library:

* by **outcome** - the catalogued domain of harm, traversed through
  pair:mayIndicateRisk. Two risk patterns reach no domain, because nothing
  upstream maps their OWASP entry to one, and a link must not be curated
  without a source.
* by **capability** - pair:motifFamily, which is how the library shelves its
  own motifs. It is a filing decision about this library, never a reading of a
  submitted architecture, so it is navigation only and no match query may read
  it (R2).
"""

from __future__ import annotations

from functools import lru_cache

from rdflib import RDF, SKOS, URIRef

from airiskkg.assessment_runner import PAIR, load_base_graph
from airiskkg.workbench.library import library_catalogue
from airiskkg.workbench.terms import domain_of, label, risk_domains, short


def _subdomains(graph, domain: URIRef) -> list[dict]:
    return sorted(
        (
            {"id": str(entry), "label": label(graph, entry)}
            for entry in graph.subjects(SKOS.broader, domain)
        ),
        key=lambda row: row["label"].lower(),
    )


@lru_cache(maxsize=1)
def backward_index() -> dict:
    """What to look for, given what must not happen."""
    graph = load_base_graph()
    catalogue = library_catalogue()
    domains = risk_domains(graph)

    patterns_by_id = {entry["id"]: entry for entry in catalogue["riskPatterns"]}
    motifs_by_id = {entry["id"]: entry for entry in catalogue["motifs"]}

    # outcome -> the risk patterns that may indicate it
    reach: dict[str, set[str]] = {}
    for pattern in graph.subjects(RDF.type, PAIR.RiskPattern):
        key = short(pattern)
        if key not in patterns_by_id:
            continue
        for term in graph.objects(pattern, PAIR.mayIndicateRisk):
            domain = domain_of(graph, term, domains)
            if domain is not None:
                reach.setdefault(str(domain), set()).add(key)

    outcomes = []
    for domain in sorted(domains, key=str):
        pattern_ids = sorted(reach.get(str(domain), set()))
        motif_ids = sorted({m for pid in pattern_ids for m in patterns_by_id[pid]["motifs"]})
        outcomes.append({
            "id": str(domain),
            "label": label(graph, domain),
            "subdomains": _subdomains(graph, domain),
            "riskPatterns": pattern_ids,
            "motifs": motif_ids,
            "reachable": bool(pattern_ids),
        })
    outcomes.sort(key=lambda row: (not row["reachable"], -len(row["riskPatterns"])))

    # capability -> its motifs -> the risk patterns they carry
    families: dict[str, dict] = {}
    for motif in catalogue["motifs"]:
        family = motif["family"]
        if not family:
            continue
        entry = families.setdefault(family["id"], {
            "id": family["id"],
            "label": family["label"],
            "definition": family["definition"],
            "motifs": [],
            "riskPatterns": set(),
        })
        entry["motifs"].append(motif["id"])
        entry["riskPatterns"].update(motif["riskPatterns"])

    capabilities = sorted(
        (
            {**entry,
             "motifs": sorted(entry["motifs"]),
             "riskPatterns": sorted(entry["riskPatterns"])}
            for entry in families.values()
        ),
        key=lambda row: (-len(row["riskPatterns"]), row["label"].lower()),
    )

    # Compact enough to travel with the two axes: an entry point is useless if
    # reading it needs a second round trip.
    return {
        "outcomes": outcomes,
        "capabilities": capabilities,
        "riskPatterns": {
            entry["id"]: {
                "id": entry["id"],
                "iri": entry["iri"],
                "label": entry["label"],
                "description": entry["description"],
                "conditions": [c["label"] for c in entry["conditions"]],
                "motifs": entry["motifs"],
                "controls": [c["label"] for c in entry["controls"]],
                "riskDomains": [d["label"] for d in entry["riskDomains"]],
                "derivedFrom": [d["label"] for d in entry["derivedFrom"]],
            }
            for entry in catalogue["riskPatterns"]
        },
        "motifs": {
            entry["id"]: {
                "id": entry["id"],
                "iri": entry["iri"],
                "label": entry["label"],
                "family": (entry["family"] or {}).get("label"),
                "nodes": len(entry["nodes"]),
                "edges": len(entry["edges"]),
            }
            for entry in motifs_by_id.values()
        },
    }
