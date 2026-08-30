from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.paths import REPO_ROOT  # noqa: E402

SOURCE = REPO_ROOT / "data" / "mappings" / "Final_Mapped_Taxonomy_Table_Output.csv"
TARGET = REPO_ROOT / "ontology" / "taxonomy" / "mit_mitigation_action.ttl"
SUBCATEGORY_ALIASES = {
    "model-alignment": "model-safety-engineering",
    "governance-disclosure": "risk-disclosure",
    "third-party-system-access": "access-management",
}


ADJUDICATED_REFINEMENTS = {
    "A0468": "data-curation-process",  # "Training Data Curation", the cited name
    "A0522": "red-teaming",            # "AI Red-Teaming Resilience"
    "A0531": "red-teaming",            # "Data Exposure Red-Teaming"
    "A0979": "post-deployment-behavior-monitoring",
}


def subcategory_slug(raw: str) -> str:
    slug = re.sub(r"^[0-9.]+\s*", "", raw).lower()
    slug = slug.replace(" & ", "-").replace(" ", "-").replace("&", "-")
    return SUBCATEGORY_ALIASES.get(slug, slug)


def split_action_id(raw: str) -> tuple[str, str]:
    """'A0897_UK Government2023' -> ('A0897', 'UK Government (2023)')."""
    match = re.match(r"^(A\d+)_(.*?)(\d{4})$", raw)
    if not match:
        return raw, ""
    return match.group(1), f"{match.group(2).strip()} ({match.group(3)})"


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def main() -> int:
    with SOURCE.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    actions: dict[str, dict] = {}
    for row in rows:
        code, citation = split_action_id(row["mit_action_id"])
        entry = actions.setdefault(
            code,
            {
                "name": row["mit_action_name"],
                "citation": citation,
                "subcategory": subcategory_slug(row["Sub_category"]),
                "raw_subcategory": row["Sub_category"],
                "risks": set(),
            },
        )
        entry["risks"].add(row["owasp_id"])

    lines = [
        "# GENERATED FILE - do not edit by hand.",
        "# Regenerate with: python python/scripts/generate_mit_action_layer.py",
        "#",
        "# The MIT mitigation taxonomy at ACTION level - the concrete mitigations that sit",
        "# beneath the sub-categories in mit_air_risk_control.ttl. Derived from",
        "# data/mappings/Final_Mapped_Taxonomy_Table_Output.csv, where each action already",
        "# carries the sub-category it belongs to and, in its identifier, the primary source",
        "# document MIT drew it from.",
        "#",
        "# These are genuine MIT taxonomy entries and carry nexus:isDefinedByTaxonomy, unlike",
        "# the 16 concrete mitctrl:* controls in mit_air_risk_control.ttl, which are PAIR-AI",
        "# curation named after MIT mitigations rather than entries of the taxonomy itself.",
        "#",
        "# Coverage is bounded by the cross-walk, which covers OWASP LLM01-06 and LLM09 only.",
        "# This is NOT the complete MIT mitigation database - it is every action the",
        "# cross-walk actually cites.",
        "#",
        "# LICENSING: reproduces MIT AI Risk Mitigation Database action ids and names. Same",
        "# unresolved item recorded in CLAUDE.md for mit_air_risk_control.ttl.",
        "",
        "@prefix mitact:  <http://w3id.org/airiskkg/taxonomy/mit-ai-risk-mitigation-action#> .",
        "@prefix mitctrl: <http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#> .",
        "@prefix nexus:   <http://w3id.org/airiskkg/taxonomy/nexus#> .",
        "@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix dct:     <http://purl.org/dc/terms/> .",
        "@prefix owl:     <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
        "<http://w3id.org/airiskkg/taxonomy/mit-ai-risk-mitigation-action#>",
        "    a owl:Ontology ;",
        '    rdfs:label "MIT AI Risk Mitigation Actions (cross-walk subset)"@en ;',
        '    dct:title "MIT AI Risk Mitigation Actions (cross-walk subset)"@en ;',
        "    dct:description \"\"\"",
        f"    The {len(actions)} individual MIT mitigation actions cited by the PAIR-AI",
        "    risk-to-mitigation cross-walk, placed under the sub-categories they belong to.",
        "    Adds the level that the 2026-07-17 rollup collapsed away.",
        '    """@en ;',
        "    dct:source <https://github.com/IBM/ai-atlas-nexus> ;",
        '    dct:source "MIT AI Risk Mitigation Database, via data/mappings/Final_Mapped_Taxonomy_Table_Output.csv"@en .',
        "",
    ]

    for code in sorted(actions):
        entry = actions[code]
        lines.append(f"mitact:{code}")
        lines.append("    a nexus:RiskControl ;")
        lines.append(f'    skos:prefLabel "{escape(entry["name"])}"@en ;')
        lines.append(f'    skos:notation "{code}" ;')
        lines.append(f"    skos:broader mitctrl:{entry['subcategory']} ;")
        refinement = ADJUDICATED_REFINEMENTS.get(code)
        if refinement:
            lines.append(f"    skos:broader mitctrl:{refinement} ;")
        lines.append("    skos:inScheme mitctrl:MIT_Draft_AI_Risk_Mitigation_Taxonomy ;")
        lines.append(
            "    nexus:isDefinedByTaxonomy mitctrl:MIT_Draft_AI_Risk_Mitigation_Taxonomy ;"
        )
        source = (
            f"MIT AI Risk Mitigation Database, action {code} "
            f"(sub-category '{escape(entry['raw_subcategory'])}')"
        )
        if entry["citation"]:
            source += f"; primary source: {escape(entry['citation'])}"
        if refinement:
            source += (
                f"; placed under mitctrl:{refinement} by review - lexical candidate "
                "generation over the 52 actions, adjudicated 2026-08-04"
            )
        lines.append(f'    dct:source "{source}"@en .')
        lines.append("")

    TARGET.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {TARGET.name}: {len(actions)} actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
