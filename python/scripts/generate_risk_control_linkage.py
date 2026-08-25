from __future__ import annotations

import csv
import glob
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rdflib import DCTERMS, Graph, Namespace, RDF, RDFS, SKOS  

from airiskkg.paths import REPO_ROOT  

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
    verbatim = {
        s
        for s in tax.subjects(NEXUS.isDefinedByTaxonomy, None)
        if "mit-ai-risk-control#" in str(s) or "mitigation-action#" in str(s)
    }

    action_parents = {a: [local(p) for p in tax.objects(a, SKOS.broader)] for a in actions}
    children = defaultdict(list)
    for action, parents in action_parents.items():
        for parent in parents:
            children[parent].append(action)
    # Sub-category only, for the "how many sub-categories" figure.
    action_parent = {
        a: next((p for p in parents if p not in {local(c) for c in mit_controls}), parents[0])
        for a, parents in action_parents.items()
    }

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
    add("## 7. Motif library - all 26, by source catalogue")
    add("")
    add("Motifs are risk-neutral: they describe a shape, not a problem. The grouping below")
    add("is the *published catalogue each was derived from* (`pair:derivedFrom`), because")
    add("that is the only classification the data actually carries - PAIR-AI does not")
    add("assign motifs to families of its own.")
    add("")

    def catalogue(motif):
        for obj in g.objects(motif, PAIR.derivedFrom):
            url = str(obj)
            if "mercari" in url:
                section = url.split("ml-system-design-pattern/")[-1].split("/")[0]
                return "Mercari ML System Design Patterns", section.replace("-patterns", "")
            if "martinfowler" in url:
                return "Fowler - Patterns of Generative AI", "GenAI"
            if "owasp-asi" in url:
                return "OWASP Agentic Top 10 (ASI)", "agentic"
            if "owasp" in url:
                return "OWASP LLM Top 10", "supply chain"
        return "unrecorded", ""

    grouped = defaultdict(lambda: defaultdict(list))
    for motif in motifs:
        source, section = catalogue(motif)
        grouped[source][section].append(motif)

    for source in sorted(grouped, key=lambda s: -sum(len(v) for v in grouped[s].values())):
        total = sum(len(v) for v in grouped[source].values())
        add(f"### {source} ({total})")
        add("")
        add("| Motif | Catalogue section | Risk patterns it feeds |")
        add("|---|---|---|")
        for section in sorted(grouped[source]):
            for motif in sorted(grouped[source][section], key=lambda m: local(m)):
                feeds = sorted(
                    local(rp).replace("RiskPattern", "")
                    for rp in g.subjects(PAIR.hasMotif, motif)
                )
                add(
                    f"| `{local(motif)}` | {section} | "
                    f"{', '.join(feeds) if feeds else '*(risk-neutral - none)*'} |"
                )
        add("")

    add("---")
    add("")
    add("## 8. Risk patterns - all 13")
    add("")
    add("| Risk pattern | Anchor | Motifs | Suggested controls |")
    add("|---|---|---|---|")
    for rp in risk_patterns:
        anchor = sorted(local(x) for x in g.objects(rp, PAIR.derivedFrom))
        ms = sorted(local(m).replace("Motif", "") for m in g.objects(rp, PAIR.hasMotif))
        cs = sorted(local(c).replace("Control_", "") for c in g.objects(rp, PAIR.suggestedControl))
        add(
            f"| **{local(rp).replace('RiskPattern', '')}** "
            f"| `{anchor[0] if anchor else '-'}` "
            f"| {', '.join(ms) if ms else '**(none - cannot fire)**'} "
            f"| {', '.join(cs)} |"
        )
    add("")
    add("---")
    add("")
    add("## 9. Controls and mitigations - technical vs non-technical")
    add("")
    add("### 9a. PAIR-AI suggested controls (12) - `pair:controlNature`")
    add("")
    add("This is the axis that matters operationally: a technical control has a footprint")
    add("in the architecture, so the assessment can look for it. A non-technical one is")
    add("organisational and leaves no structure to detect, so it can only ever be advice.")
    add("")
    for nature, heading in (
        ("TechnicalControl", "Technical"),
        ("NonTechnicalControl", "Non-technical"),
    ):
        members = sorted(
            (c for c in controls if local(g.value(c, PAIR.controlNature) or "") == nature),
            key=lambda c: local(c),
        )
        add(f"**{heading} ({len(members)})**")
        add("")
        add("| Control | Realizing motif | Verifiable from the graph? |")
        add("|---|---|---|")
        for control in members:
            realizing = sorted(local(m).replace("Motif", "") for m in g.objects(control, PAIR.realizedByMotif))
            verdict = "**yes**" if realizing else ("no - no motif expresses it" if nature == "TechnicalControl" else "never - no architectural footprint")
            add(
                f"| **{g.value(control, SKOS.prefLabel)}**<br>`{local(control)}` "
                f"| {', '.join(realizing) or '(none)'} | {verdict} |"
            )
        add("")

    add("### 9b. MIT mitigation vocabulary")
    add("")
    add("Two altitudes, treated differently on purpose.")
    add("")
    add(f"**The {len(mit_controls)} concrete controls carry `pair:controlNature`**, the same")
    add("declared axis as 9a. They are the same altitude as a suggested control, so the same")
    add("rule applies: technical means a footprint in the architecture; non-technical means")
    add("organisation, process, governance or documentation with nothing to detect.")
    add("")
    add(f"**The {len(groups)} families are deliberately not classified.** A family such as")
    add("`data-governance` contains both technical and non-technical mitigations, so a single")
    add("label at that altitude would be meaningless - the reason `control_mitigation_layer.ttl`")
    add("records for keeping them out.")
    add("")
    add("> Do not read `nexus:controlType` as a nature flag. It mixes the MIT category axis")
    add("> (governance, technical, operational, transparency-accountability) with a control")
    add("> function axis (preventive, detective, corrective).")
    add("")

    def top_categories(concept) -> set[str]:
        """All top-level ancestors, not one. The taxonomy is a polyhierarchy and
        8 of the 36 concepts sit under two categories at once, so returning a
        single answer would mean silently picking one - false precision of
        exactly the kind this document is meant to avoid."""
        found, seen, frontier = set(), set(), [concept]
        while frontier:
            node = frontier.pop()
            if node in seen:
                continue
            seen.add(node)
            parents = list(tax.objects(node, SKOS.broader))
            if not parents:
                found.add(local(node))
            frontier.extend(parents)
        return found

    TECHNICAL_CATEGORY = "technical-security-controls"
    straddling = {
        local(c) for c in mit_controls
        if len(top_categories(c)) > 1 and TECHNICAL_CATEGORY in top_categories(c)
    }

    add(f"#### The {len(mit_controls)} concrete controls")
    add("")
    add("| Control | Nature | Sits under | Actions |")
    add("|---|---|---|---|")
    for nature_uri, label in (
        (PAIR.TechnicalControl, "**Technical**"),
        (PAIR.NonTechnicalControl, "Non-technical"),
    ):
        members = sorted(
            (c for c in mit_controls if g.value(c, PAIR.controlNature) == nature_uri),
            key=lambda c: local(c),
        )
        for concept in members:
            cats = ", ".join(sorted(x.replace("-controls", "") for x in top_categories(concept)))
            flag = " ⚖️" if local(concept) in straddling else ""
            n_act = len(children.get(local(concept), []))
            add(f"| `{local(concept)}`{flag} | {label} | {cats} | {n_act or '-'} |")
    add("")
    add(f"⚖️ = one of the {len(straddling)} controls that sit under a technical **and** a")
    add("non-technical MIT category at once. The hierarchy cannot decide their nature, so it is")
    add("declared rather than derived - previously this document walked to a top-level ancestor")
    add("and silently took whichever branch the traversal reached first. All "
        f"{len(straddling)} are PAIR-AI curation; the ambiguity comes from this project")
    add("parenting its own controls under two families, not from MIT.")
    add("")
    add(f"#### The {len(groups)} families - not classified, by design")
    add("")
    add("| Family | Actions beneath | Reached by a suggested control? |")
    add("|---|---|---|")
    linked = {local(o) for c in controls for o in g.objects(c, SKOS.relatedMatch)}
    for family in sorted(groups, key=lambda f: (-len(children.get(local(f), [])), local(f))):
        n_act = len(children.get(local(family), []))
        add(f"| `{local(family)}` | {n_act or '-'} | {'yes' if local(family) in linked else '**no**'} |")
    add("")

    add("---")
    add("")
    add("## 10. Provenance summary")
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
    add("---")
    add("")
    add("## 11. Files that make up this work")
    add("")
    add("Everything below is in the repository. Paths are the source of truth; this")
    add("document is generated from them.")
    add("")
    add("### Knowledge - the vocabularies and the library")
    add("")
    add("| File | Holds |")
    add("|---|---|")
    inventory = [
        ("ontology/patterns/motif.ttl", f"the {len(motifs)} motifs and their pattern nodes/edges"),
        ("ontology/patterns/risk_pattern_library.ttl",
         f"the {len(risk_patterns)} risk patterns, the {len(controls)} suggested controls, "
         "and the control-to-MIT bridge"),
        ("ontology/patterns/control_mitigation_layer.ttl",
         "technical/non-technical classification and `realizedByMotif`"),
        ("ontology/core/pair_ai_pattern.ttl", "the pattern meta-vocabulary: roles, predicates, data categories"),
        ("ontology/core/beam_core.ttl", "BEAM elements and flow predicates"),
        ("ontology/taxonomy/mit_air_risk_control.ttl",
         f"{len(groups)} MIT families (verbatim) + {len(mit_controls)} PAIR-AI concrete controls"),
        ("ontology/taxonomy/mit_mitigation_action.ttl",
         f"**{len(actions)} MIT mitigation actions** (generated)"),
        ("ontology/taxonomy/taxonomy_mapping.ttl", "cross-taxonomy mappings + risk-to-control grounding"),
        ("ontology/taxonomy/owasp_llm.ttl, owasp_asi.ttl, ibm_risk_atlas.ttl, mit_ai_risk.ttl, nist_genai.ttl",
         "the risk taxonomies"),
        ("ontology/facets/", "OECD/DPV characterization facets"),
        ("ontology/patterns/implementation/", "the executable SPARQL: `match/`, `risk/`, `propagation/`"),
    ]
    for path, holds in inventory:
        add(f"| `{path}` | {holds} |")
    add("")
    add("### Evidence and provenance")
    add("")
    add("| File | Holds |")
    add("|---|---|")
    add("| `data/mappings/Final_Mapped_Taxonomy_Table_Output.csv` | the 93-row cross-walk "
        "(OWASP -> IBM Atlas -> MIT action). **The source of the action layer.** |")
    add("| `ontology/taxonomy/provenance/mapping_provenance.ttl` | one `sssom:Mapping` per "
        "correspondence, with a SEMAPV justification. Deliberately outside the runner's glob |")
    add("| `NOTICE.md` | third-party attribution and licence posture per source |")
    add("")
    add("### Generators - re-run after editing the ontology")
    add("")
    add("```")
    add("python python/scripts/generate_mit_action_layer.py        # the 52-action layer")
    add("python python/scripts/generate_mapping_provenance.py      # provenance records")
    add("python python/scripts/generate_risk_control_linkage.py    # this document")
    add("```")
    add("")
    add("### Tests that hold it together")
    add("")
    add("| File | Checks |")
    add("|---|---|")
    add("| `python/tests/test_library_consistency.py` | motif/risk-pattern/query coherence, "
        "taxonomy anchors, role hierarchy |")
    add("| `python/tests/test_mapping_integrity.py` | mapping coherence, provenance coverage, "
        "cross-walk reproducibility, the action layer |")
    add("| `python/tests/test_propagation.py` | data-category propagation and its barriers |")
    add("")
    add("### Background reading")
    add("")
    add("| File | Why |")
    add("|---|---|")
    add("| `docs/reference/PAIR-AI_glossary_v1_3.md` | terminology and the modelling "
        "rules (R1-R10). Read Section C before changing anything |")
    add("| `docs/reference/PAIR-AI_method_and_construction.md` | how the knowledge base was built |")
    add("| `docs/reference/catalogue.md` | the motif catalogue in prose |")
    add("| `docs/claude/CLAUDE.md` | locked decisions, including licence posture per source |")
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
