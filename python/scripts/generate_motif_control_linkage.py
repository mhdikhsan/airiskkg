"""Generate docs/reference/motif_control_linkage.md from the ontology itself.

The motif -> control relationship is spread across three files and two different
predicates that point in opposite directions, so the whole picture is not
readable anywhere. This assembles it, and derives a checkability tier per link
rather than inventing a confidence score - see the generated document for why a
number would be false precision here.

Regenerate after editing motif.ttl, risk_pattern_library.ttl, or
control_mitigation_layer.ttl:

    python python/scripts/generate_motif_control_linkage.py
"""
import glob
import sys
from collections import defaultdict

sys.path.insert(0, "python/src")
from rdflib import DCTERMS, Graph, Namespace, RDF, RDFS

from airiskkg.paths import REPO_ROOT

P = Namespace("http://w3id.org/airiskkg/pair-ai#")
g = Graph()
for f in glob.glob("ontology/patterns/*.ttl") + glob.glob("ontology/core/*.ttl"):
    g.parse(f)

n = lambda t: str(t).rsplit("#", 1)[-1]
label = lambda t: str(g.value(t, RDFS.label) or n(t))

motifs = sorted([s for s, _, o in g.triples((None, RDF.type, None)) if n(o) == "GraphMotif"], key=str)
rps = sorted(g.subjects(RDF.type, P.RiskPattern), key=str)
ctrls = sorted([s for s, _, o in g.triples((None, RDF.type, None)) if n(o) == "RiskControl"], key=str)

nature = {c: n(g.value(c, P.controlNature) or "") for c in ctrls}
realized = {c: [m for m in g.objects(c, P.realizedByMotif)] for c in ctrls}
realizes = defaultdict(list)          # motif -> controls it realizes
for c, ms in realized.items():
    for m in ms:
        realizes[m].append(c)


def motif_source(m):
    for x in g.objects(m, P.derivedFrom):
        s = str(x)
        if "martinfowler" in s:
            return "Fowler GenAI patterns"
        if "mercari" in s:
            return "Mercari ML system design patterns"
        if "owasp-asi" in s:
            return "OWASP ASI (taxonomy-derived)"
        if "genai.owasp" in s:
            return "OWASP LLM Top 10"
    return "unrecorded"


def anchors(rp):
    out = []
    for pred in (P.hasCandidateRiskTaxonomyEntry, P.mayIndicateRisk, P.primaryRiskTaxonomyEntry):
        out += [n(x) for x in g.objects(rp, pred)]
    return sorted(set(out))


# ---- exposure links: motif --(risk pattern)--> control
exposure = []
for rp in rps:
    ms = list(g.objects(rp, P.hasMotif))
    cs = list(g.objects(rp, P.suggestedControl))
    for m in ms:
        for c in cs:
            exposure.append((m, rp, c))

# ---- confidence tiers, computed
def tier(m, rp, c):
    if nature[c] == "NonTechnicalControl":
        return "C"
    return "A" if realized[c] else "B"


rows = defaultdict(list)
for m, rp, c in exposure:
    rows[tier(m, rp, c)].append((m, rp, c))

TIER_DESC = {
    "A": "Technical control, and the motif library contains a structure that realizes it",
    "B": "Technical control, but no motif in the library realizes it",
    "C": "Non-technical control - no architectural footprint at all",
}

out = []
w = out.append

w("# Motif → Control Linkage")
w("")
w("How a matched motif reaches a suggested control, what kind of claim each link")
w("makes, and how much of that claim rests on evidence rather than on our own say-so.")
w("")
w("**Generated from the ontology** by `python/scripts/generate_motif_control_linkage.py`; every count and")
w("every tier below is computed from the graph, not transcribed. Regenerate after")
w("changing `motif.ttl`, `risk_pattern_library.ttl`, or `control_mitigation_layer.ttl`.")
w("")
w("---")
w("")
w("## The two links are different claims")
w("")
w("A motif and a control can be related in two ways, and conflating them is the")
w("main modelling hazard here.")
w("")
w("```")
w("  EXPOSURE     motif --hasMotif--> risk pattern --suggestedControl--> control")
w('               \"this shape exposes a risk that this control mitigates\"')
w("")
w("  REALIZATION  control --realizedByMotif--> motif")
w('               \"this shape IS the control\"')
w("```")
w("")
w("The direction of benefit is opposite. In an **exposure** link the motif is the")
w("problem; in a **realization** link the motif is the fix. `GuardrailsMotif` is both,")
w("depending on which risk pattern you approach it from — it realizes")
w("`Control_Guardrails` while itself exposing `SystemPromptLeakageRiskPattern`.")
w("A document that merged the two would suggest guardrails as a mitigation for")
w("guardrails.")
w("")
w("Counts today:")
w("")
w(f"| | |")
w(f"|---|---|")
w(f"| Motifs in the library | {len(motifs)} |")
w(f"| Risk patterns | {len(rps)} |")
w(f"| Controls (`pat:Control_*`) | {len(ctrls)} |")
w(f"| Exposure links (motif × control, via a risk pattern) | {len(exposure)} |")
w(f"| Realization links (`pair:realizedByMotif`) | {sum(len(v) for v in realized.values())} |")
w("")
w("---")
w("")
w("## Confidence: what it means and how it is derived")
w("")
w("**No confidence number here is asserted.** Every link in this file is project")
w("curation — nobody publishes a motif→control mapping we could adopt — so a")
w("numeric score would be false precision of exactly the kind the mapping")
w("provenance layer exists to expose (`ontology/taxonomy/provenance/`).")
w("")
w("What *can* be derived is how **checkable** a link is: whether its truth or")
w("falsity could be established from a submitted architecture graph. That is a")
w("property of the control, not an opinion about the link, and it is computed:")
w("")
w("| Tier | Meaning | Can the assessment verify the fix landed? |")
w("|---|---|---|")
w("| **A** | Technical control **and** a motif realizes it | **Yes** — the fix is expressible in the same vocabulary, so its presence or absence is decidable |")
w("| **B** | Technical control, no realizing motif | **No** — the fix has an architectural footprint but the library cannot express it |")
w("| **C** | Non-technical control | **No, and never** — governance/process, no architectural footprint by definition |")
w("")
w("Tier A is the only one where *\"you applied this control\"* is a falsifiable")
w("statement. Tiers B and C are advice: correct, possibly essential, but the tool")
w("cannot confirm or refute that they were acted on. Reporting them at the same")
w("visual weight as tier A would overstate what the method knows.")
w("")
w("This mirrors Rule R4. Absence is closed-world over the submitted graph only, so")
w("the assessment can say *\"no guardrail motif is present\"* (tier A) but can never")
w("say *\"no model provenance process exists\"* (tier C) — that fact simply is not in")
w("the graph.")
w("")
c_counts = {t: len(rows[t]) for t in "ABC"}
total = sum(c_counts.values())
w("Distribution of the " + str(total) + " exposure links:")
w("")
w("| Tier | Links | Share |")
w("|---|---|---|")
for t in "ABC":
    w(f"| {t} | {c_counts[t]} | {100*c_counts[t]/total:.0f}% |")
w("")
w(f"So **{100*c_counts['A']/total:.0f}%** of what the tool suggests is structurally")
w("verifiable; the rest is advice it cannot follow up on.")
w("")
# That headline is flattering, and one control does most of the work. Say so:
# a reader who acts on 59% without this caveat is over-trusting the number.
tier_a = [c for _, _, c in exposure if realized[c]]
dom = max(set(tier_a), key=tier_a.count)
dom_n = tier_a.count(dom)
rest = len(tier_a) - dom_n
w("**Read that number with a caveat.** One control does most of the work:")
w(f"`{n(dom).replace('Control_','')}` alone accounts for **{dom_n} of the {c_counts['A']}**")
w(f"tier-A links, because {len(set(r for r in rps if dom in set(g.objects(r, P.suggestedControl))))} of the")
w(f"{len(rps)} risk patterns suggest it — logging and evaluation are close to")
w("universally applicable, so they attach almost everywhere and are cheap to")
w(f"verify. Excluding it, structurally verifiable suggestions drop to **{rest} of")
w(f"{total}** ({100*rest/total:.0f}%).")
w("")
w(f"Only **{len(set(tier_a))} of the {len(ctrls)} controls** are ever tier A. That is the")
w("more useful figure for planning: it is the size of the vocabulary in which the")
w("method can currently express a *checkable* fix.")
w("")
w("---")
w("")
w("## Realization links — the motifs that ARE controls")
w("")
w("These are the tier-A enablers: insert this motif and the control is, structurally,")
w("in place.")
w("")
w("| Control | Nature | Realized by motif |")
w("|---|---|---|")
for c in ctrls:
    if realized[c]:
        w(f"| `{n(c)}` | {nature[c].replace('Control','')} | " + ", ".join(f"`{n(m)}`" for m in sorted(realized[c], key=str)) + " |")
w("")
w("Controls with **no** realizing motif — every suggestion naming one is tier B or C:")
w("")
w("| Control | Nature | Why nothing realizes it |")
w("|---|---|---|")
gapnote = {
    "Control_DataMinimizationAndRedaction": "`pair:RedactionStep` exists as a *role* and acts as the propagation barrier, but no motif declares the surrounding shape",
    "Control_RateLimitBudgetAndLoopControl": "no motif expresses budget or loop bounding",
    "Control_RetrievalAccessControl": "no motif expresses per-user authorization on retrieval",
    "Control_SystemPromptSecrecy": "no motif expresses prompt/secret separation",
    "Control_ToolPermissionBoundaries": "no motif expresses tool scoping; `ToolUsingAgentMotif` is the exposure, not the boundary",
    "Control_ModelAndDependencyProvenance": "supplier attestation and review process - no structure to detect",
    "Control_TrustedTrainingAndIndexingData": "data sourcing and vetting process - no structure to detect",
}
for c in ctrls:
    if not realized[c]:
        w(f"| `{n(c)}` | {nature[c].replace('Control','')} | {gapnote.get(n(c),'—')} |")
w("")
w("The five technical ones are the **actionable backlog**: each is a motif that,")
w("if added, would move every link naming it from tier B to tier A.")
w("")
w("---")
w("")
w("## Exposure links by motif")
w("")
w("Read as: *if this motif matches, these controls are suggested, at this tier.*")
w("")
by_motif = defaultdict(list)
for m, rp, c in exposure:
    by_motif[m].append((rp, c))
w("| Motif | Provenance | Via risk pattern | Suggested control | Tier |")
w("|---|---|---|---|---|")
for m in sorted(by_motif, key=lambda x: n(x)):
    first = True
    for rp, c in sorted(by_motif[m], key=lambda x: (n(x[0]), n(x[1]))):
        cells = (f"`{n(m)}`", motif_source(m)) if first else ("", "")
        w(f"| {cells[0]} | {cells[1]} | `{n(rp).replace('RiskPattern','')}` | `{n(c).replace('Control_','')}` | {tier(m,rp,c)} |")
        first = False
w("")
w("---")
w("")
w("## Motifs that reach no control")
w("")
silent = [m for m in motifs if m not in by_motif]
w(f"{len(silent)} of {len(motifs)} motifs participate in no risk pattern, so matching them")
w("suggests nothing. This is by design for the neutral ML-serving shapes — the Motif")
w("Library is risk-neutral and a motif is not obliged to carry risk.")
w("")
for m in silent:
    extra = ""
    if m in realizes:
        extra = " — but realizes " + ", ".join(f"`{n(c).replace('Control_','')}`" for c in sorted(realizes[m], key=str))
    w(f"- `{n(m)}`{extra}")
w("")
noneed = [m for m in silent if m in realizes]
w(f"Note that {len(noneed)} of them are not idle: they realize controls, so they are")
w("*fixes* that the library can recognise even though they expose nothing.")
w("")
w("---")
w("")
w("## Known gaps")
w("")
orphan_rp = [rp for rp in rps if not list(g.objects(rp, P.hasMotif))]
reachable = {c for _, _, c in exposure}
for rp in orphan_rp:
    cs = sorted(g.objects(rp, P.suggestedControl), key=str)
    stranded = [c for c in cs if c not in reachable]
    others = sorted(
        {
            n(other)
            for other in rps
            if other != rp
            and list(g.objects(other, P.hasMotif))
            and set(cs) <= set(g.objects(other, P.suggestedControl))
        }
    )
    w(f"1. **`{n(rp)}` declares no motif**, so it can never fire. Its controls —")
    w("   " + ", ".join(f"`{n(c).replace('Control_','')}`" for c in cs) + " —")
    if stranded:
        w("   include " + ", ".join(f"`{n(c).replace('Control_','')}`" for c in stranded))
        w("   , which no other risk pattern reaches.")
    elif others:
        w(f"   are still reachable: `{others[0]}` suggests the same set and does")
        w("   have a motif. So no control is stranded. What is lost is the *excessive")
        w("   agency* reading of an architecture, not the advice attached to it.")
    else:
        w("   are reachable through other risk patterns.")
w("")
w("2. **No risk pattern declares `pair:maturity`.** The property exists and a test")
w("   is marked xfail against it, so link quality cannot yet be filtered by")
w("   maturity — the tiers here are the only quality signal available.")
w("")
w("3. **Every link in this file is project curation.** No upstream publishes")
w("   motif→control mappings. Unlike the taxonomy layer, there is nothing to adopt,")
w("   so these cannot be corroborated against a third party — only reviewed.")
w("")

path = REPO_ROOT / "docs" / "reference" / "motif_control_linkage.md"
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"wrote {path}  ({len(out)} lines)")
print("tiers:", c_counts, "exposure:", len(exposure), "realization:", sum(len(v) for v in realized.values()))
print("silent motifs:", len(silent), "orphan risk patterns:", [n(r) for r in orphan_rp])
