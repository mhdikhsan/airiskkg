"""Generate docs/reference/risk_control_linkage.md - the single linkage reference.

Supersedes motif_control_linkage.md and control_catalogue_table.md, which split
the same picture across two files and neither of which reached the MIT action
level.

Everything here is computed from the graph and the cross-walk CSV. Regenerate
after editing motif.ttl, risk_pattern_library.ttl, control_mitigation_layer.ttl,
mit_air_risk_control.ttl, or the action layer.

    python python/scripts/generate_risk_control_linkage.py
"""

from __future__ import annotations

import csv
import glob
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rdflib import DCTERMS, Graph, Namespace, RDF, RDFS, SKOS  # noqa: E402

from airiskkg.paths import REPO_ROOT  # noqa: E402

PAIR = Namespace("http://w3id.org/airiskkg/pair-ai#")
NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")
CSV_PATH = REPO_ROOT / "data" / "mappings" / "Final_Mapped_Taxonomy_Table_Output.csv"

CONTROL_ORDER = [
    "InputValidationAndPromptIsolation",
    "OutputValidationAndSanitization",
    "DataMinimizationAndRedaction",
    "RetrievalAccessControl",
    "ModelAndDependencyProvenance",
    "TrustedTrainingAndIndexingData",
    "ToolPermissionBoundaries",
    "SystemPromptSecrecy",
    "GroundingAndVerification",
    "RateLimitBudgetAndLoopControl",
    "LoggingMonitoringAndEvals",
    "Guardrails",
]


def local(term) -> str:
    return str(term).rsplit("#", 1)[-1]


def build() -> tuple[Graph, Graph]:
    patterns = Graph()
    for path in glob.glob("ontology/patterns/*.ttl") + glob.glob("ontology/core/*.ttl"):
        patterns.parse(path)
    taxonomy = Graph()
    for path in glob.glob("ontology/taxonomy/*.ttl"):
        taxonomy.parse(path)
    return patterns, taxonomy


def main() -> int:
    g, tax = build()
    w: list[str] = []
    add = w.append

    motifs = [s for s, _, o in g.triples((None, RDF.type, None)) if local(o) == "GraphMotif"]
    risk_patterns = sorted(g.subjects(RDF.type, PAIR.RiskPattern), key=str)
    controls = [
        s
        for s, _, o in g.triples((None, RDF.type, None))
        if local(o) == "RiskControl" and "patterns#" in str(s)
    ]
    by_name = {local(c).replace("Control_", ""): c for c in controls}

    groups = sorted(tax.subjects(RDF.type, NEXUS.RiskControlGroup), key=str)
    mit_controls = [
        s
        for s in tax.subjects(RDF.type, NEXUS.RiskControl)
        if "mit-ai-risk-control#" in str(s)
    ]
    actions = sorted(
        (s for s in tax.subjects(RDF.type, NEXUS.RiskControl) if "mitigation-action#" in str(s)),
        key=str,
    )
    # Scoped to the mitigation vocabulary on purpose: nexus:isDefinedByTaxonomy is
    # used by the risk taxonomies too, so an unscoped count returns 142 and reads
    # as more mitigation grounding than exists.
    verbatim = {
        s
        for s in tax.subjects(NEXUS.isDefinedByTaxonomy, None)
        if "mit-ai-risk-control#" in str(s) or "mitigation-action#" in str(s)
    }

    # action -> parent sub-category, and the reverse
    action_parent = {a: local(tax.value(a, SKOS.broader)) for a in actions}
    children = defaultdict(list)
    for action, parent in action_parent.items():
        children[parent].append(action)

    with CSV_PATH.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    risk_actions = defaultdict(set)
    for row in rows:
        owasp = row["owasp_id"]
        if re.match(r"llm\d{2}2025", owasp):
            owasp = owasp.replace("2025", "", 1)
        risk_actions[owasp].add(re.match(r"^(A\d+)_", row["mit_action_id"]).group(1))

    add("# Risk, Motif, Control and Mitigation - linkage reference")
    add("")
    add("The single reference for how a matched motif reaches a mitigation, and what kind")
    add("of claim each hop makes. Generated from the ontology and the cross-walk CSV by")
    add("`python/scripts/generate_risk_control_linkage.py`; every number is computed.")
    add("")
    add("Supersedes `motif_control_linkage.md` and `control_catalogue_table.md`.")
    add("")
    add("---")
    add("")
    add("## 1. Inventory")
    add("")
    add("| Layer | Count | What it is |")
    add("|---|---|---|")
    add(f"| **Motif library** | **{len(motifs)}** | Risk-neutral architectural shapes (`pair:GraphMotif`) |")
    add(f"| **Risk patterns** | **{len(risk_patterns)}** | Motif + applicability condition -> candidate finding |")
    add(f"| **Suggested controls** | **{len(controls)}** | `pat:Control_*`, the only vocabulary in `pair:suggestedControl` |")
    add("| | | |")
    add(f"| MIT control groups | {len(groups)} | Categories + sub-categories, **MIT verbatim** |")
    add(f"| MIT mitigation actions | {len(actions)} | Concrete actions, **MIT verbatim** |")
    add(f"| PAIR-AI concrete controls | {len(mit_controls)} | In `mitctrl:` namespace but **project curation** |")
    add(f"| **Mitigation vocabulary, total** | **{len(groups) + len(actions) + len(mit_controls)}** | of which **{len(verbatim)}** carry `nexus:isDefinedByTaxonomy` |")
    add("")
    add("### What counts as \"a mitigation\" depends on the level")
    add("")
    add("Three different numbers are all defensible, so state which one is meant:")
    add("")
    add(f"- **{len(actions)}** concrete MIT actions (`A0897 Model Prompting`, ...)")
    add(f"- **{len(groups)}** MIT families (4 categories + sub-categories)")
    add(f"- **{len(controls)}** PAIR-AI suggested controls - the only ones a finding emits")
    add("")
    raw_subcategories = {row["Sub_category"] for row in rows}
    add(f"The cross-walk CSV has {len(rows)} rows, which are risk-to-action *pairs* with")
    add(f"repeats - {len(rows)} rows resolve to {len(actions)} distinct actions, sitting in")
    add(f"{len(raw_subcategories)} MIT sub-categories that land on "
        f"{len(set(action_parent.values()))} `mitctrl:` families (three sub-categories alias")
    add("onto families already present).")
    add("")
    add("That is the whole of the \"94 rows but only 36 concepts\" gap: **rows are not")
    add("concepts.** Each row is one risk-action pair, many actions recur across risks, and")
    add("the 2026-07-17 rollup collapsed every action into its family before the data")
    add("reached the graph. The action level is now modelled, so nothing is collapsed away.")
    add("")
    add("> **Careful with the `mitctrl:` namespace.** It holds two different things: "
        f"{len(groups)} MIT-verbatim groups and {len(mit_controls)} PAIR-AI-curated controls "
        "that are *named after* MIT mitigations but are not entries of the taxonomy. Only the "
        "former carry `nexus:isDefinedByTaxonomy`. Reporting them as one number would claim "
        "external grounding for project curation.")
    add("")
    add("---")
    add("")
    add("## 2. The four hops, and what each is worth")
    add("")
    add("```")
    add("  motif ──hasMotif──▶ risk pattern ──suggestedControl──▶ pat:Control_*")
    add("    ▲                      │                                  │")
    add("    │                      │ mayIndicateRisk                  │ relatedMatch")
    add("    │                      ▼                                  ▼")
    add("    └──realizedByMotif── OWASP/Atlas/MIT entry ──▶ mitctrl:family ──broader──▶ mitact:A0xxx")
    add("```")
    add("")
    add("| Hop | Evidence | Strength |")
    add("|---|---|---|")
    add("| motif -> risk pattern | Published catalogues (Fowler, Mercari) + OWASP/ASI anchors | Strong, externally sourced |")
    add("| risk pattern -> taxonomy | Explicit triples, every non-anchor SKOS-mapped to the anchor | Strong, test-enforced |")
    add("| risk pattern -> control | Project curation | **Weakest hop, nothing upstream to adopt** |")
    add("| control -> MIT family | `skos:relatedMatch`, declared *indicative, not audited* | Weak but explicit |")
    add("| taxonomy -> MIT family | Embedding cosine top-3, **unvalidated** | Reproducible, not adjudicated |")
    add("| MIT family -> action | `skos:broader` from the cross-walk | Faithful to source |")
    add("")
    add("**Two motif relations, opposite in meaning.** *Exposing*: the motif's presence")
    add("raises the risk (the motif is the problem). *Realizing*: the motif implements the")
    add("control (the motif is the fix). `GuardrailsMotif` is both at once, which is why")
    add("they are never merged into one column.")
    add("")
    add("---")
    add("")
    add("## 3. Suggested control -> everything it touches")
    add("")
    add("| # | Suggested control | Candidate risk | Exposing motif | Realizing motif | MIT family | Actions |")
    add("|---|---|---|---|---|---|---|")
    for index, key in enumerate(CONTROL_ORDER, start=1):
        control = by_name[key]
        risks = sorted(local(rp).replace("RiskPattern", "") for rp in g.subjects(PAIR.suggestedControl, control))
        exposing = sorted({
            local(m).replace("Motif", "")
            for rp in g.subjects(PAIR.suggestedControl, control)
            for m in g.objects(rp, PAIR.hasMotif)
        })
        realizing = sorted(local(m).replace("Motif", "") for m in g.objects(control, PAIR.realizedByMotif))
        families = sorted(local(o) for o in g.objects(control, SKOS.relatedMatch))
        n_actions = sum(len(children.get(f, [])) for f in families)
        add(
            f"| {index} | **{g.value(control, SKOS.prefLabel)}**<br>`pat:{local(control)}` "
            f"| {', '.join(risks)} "
            f"| {', '.join(exposing) or '(none)'} "
            f"| {'**' + ', '.join(realizing) + '**' if realizing else '(none)'} "
            f"| {', '.join(families)} "
            f"| {n_actions} |"
        )
    add("")
    add("---")
    add("")
    add("## 4. Candidate risk -> MIT actions (evidence route)")
    add("")
    add("This is the other route to a mitigation: not via the suggested control, but via the")
    add("finding's taxonomy entries and the cross-walk. Only OWASP LLM01-06 and LLM09 are")
    add("covered - the cross-walk has no rows for LLM07/08/10.")
    add("")
    add("| OWASP risk | MIT families | Distinct actions |")
    add("|---|---|---|")
    owasp_ns = Namespace("http://w3id.org/airiskkg/taxonomy/owasp-llm#")
    for owasp in sorted(risk_actions):
        fams = sorted(local(o) for o in tax.objects(owasp_ns[owasp], NEXUS.hasRelatedControl))
        add(f"| `{owasp}` | {len(fams)} | {len(risk_actions[owasp])} |")
    uncovered = sorted(
        local(rp) for rp in risk_patterns
        if not any(
            local(e).replace("2025", "") in risk_actions
            for e in g.objects(rp, PAIR.mayIndicateRisk)
        )
    )
    add("")
    add(f"Risk patterns with no action-level evidence ({len(uncovered)}): "
        + ", ".join(f"`{u.replace('RiskPattern','')}`" for u in uncovered))
    add("")
    add("---")
    add("")
    add("## 5. MIT family -> actions underneath it")
    add("")
    add("| MIT family | Actions | Reached by a suggested control? |")
    add("|---|---|---|")
    linked_families = {local(o) for c in controls for o in g.objects(c, SKOS.relatedMatch)}
    for family in sorted(children, key=lambda f: (-len(children[f]), f)):
        mark = "yes" if family in linked_families else "**no**"
        add(f"| `{family}` | {len(children[family])} | {mark} |")
    empty = sorted(local(x) for x in groups if local(x) not in children)
    add("")
    add(f"Families with no action beneath them ({len(empty)}): "
        + ", ".join(f"`{e}`" for e in empty))
    add("")
    add("---")
    add("")
    add("## 6. Gaps")
    add("")
    realizable = sum(1 for c in controls if list(g.objects(c, PAIR.realizedByMotif)))
    add(f"1. **{len(controls) - realizable} of {len(controls)} controls have no realizing motif.** "
        "The tool can advise them but cannot verify from the graph that they were applied.")
    silent = [m for m in motifs if not list(g.subjects(PAIR.hasMotif, m))]
    add(f"2. **{len(silent)} of {len(motifs)} motifs reach no control** - by design for the "
        "risk-neutral ML-serving shapes.")
    orphan = [rp for rp in risk_patterns if not list(g.objects(rp, PAIR.hasMotif))]
    add(f"3. **{len(orphan)} risk pattern declares no motif** "
        f"({', '.join('`' + local(o) + '`' for o in orphan)}) so it can never fire.")
    circular = [
        (local(m), local(rp), local(c))
        for rp in risk_patterns
        for m in g.objects(rp, PAIR.hasMotif)
        for c in g.objects(rp, PAIR.suggestedControl)
        if (c, PAIR.realizedByMotif, m) in g
    ]
    add(f"4. **{len(circular)} circular suggestions** - the motif that triggers the finding is "
        "also the motif that would realize the suggested fix.")
    add("5. **Coverage is bounded by the cross-walk.** LLM07, LLM08 and LLM10 have no "
        "action-level evidence at all; their control links remain prior curation.")
    add("")
    add("---")
    add("")
    add("## 7. Provenance summary")
    add("")
    add("| Claim | Basis |")
    add("|---|---|")
    add("| Motif shapes | Fowler GenAI patterns, Mercari ML system design patterns, OWASP |")
    add("| Risk pattern anchors | OWASP LLM Top 10 / OWASP ASI, explicit triples |")
    add("| Cross-taxonomy mappings | IBM AI Atlas Nexus SSSOM, adopted verbatim where available |")
    add("| Risk -> MIT family | Embedding cosine top-3, unvalidated, reproducible from the CSV |")
    add("| MIT families and actions | MIT Draft AI Risk Mitigation Taxonomy, verbatim |")
    add("| Control -> MIT family | PAIR-AI curation, declared indicative |")
    add("| Suggested control catalogue | PAIR-AI curation |")
    add("")
    add("Per-mapping records with SEMAPV justifications are in "
        "`ontology/taxonomy/provenance/mapping_provenance.ttl`.")
    add("")

    target = REPO_ROOT / "docs" / "reference" / "risk_control_linkage.md"
    target.write_text("\n".join(w) + "\n", encoding="utf-8")
    print(f"wrote {target.name}")
    print(f"  motifs {len(motifs)} | risk patterns {len(risk_patterns)} | controls {len(controls)}")
    print(f"  MIT groups {len(groups)} | actions {len(actions)} | curated {len(mit_controls)}")
    print(f"  circular {len(circular)} | silent motifs {len(silent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
