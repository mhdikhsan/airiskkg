"""Mechanical consistency net for the AI-RKG pattern layer.

Cross-checks the five layers of the pattern knowledge for identifier drift -
the failure mode of LLM-assisted curation, where each layer looks plausible
in isolation but references URIs the other layers never declare or emit:

  A. declared vocabulary  (ontology/core/pair_ai_pattern.ttl)
  B. motif library        (ontology/patterns/motif.ttl)
  C. risk pattern library (ontology/patterns/risk_pattern_library.ttl)
  D. SPARQL queries       (ontology/patterns/implementation/*.rq)
  E. example graphs       (ontology/example/*.ttl)
  +  taxonomies           (ontology/taxonomy/*.ttl)

A hallucinated URI anywhere becomes a test failure here instead of a
silently dead (or unfalsifiable) rule. See
docs/claude/engine_consistency_cleanup_plan.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from rdflib import RDF, Graph, Namespace, URIRef

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "ontology" / "core"
PATTERNS = REPO_ROOT / "ontology" / "patterns"
IMPL = PATTERNS / "implementation"
EXAMPLES = REPO_ROOT / "ontology" / "example"
TAXONOMY = REPO_ROOT / "ontology" / "taxonomy"

PAIR = Namespace("http://w3id.org/airiskkg/pair-ai#")
PAT = Namespace("http://w3id.org/airiskkg/patterns#")

NAMESPACES = {
    "pair": PAIR,
    "pat": PAT,
    "beam": Namespace("http://w3id.org/beam/core#"),
    "beamr": Namespace("http://w3id.org/beam/risk#"),
    "owasp": Namespace("http://w3id.org/airiskkg/taxonomy/owasp-llm#"),
    "atlas": Namespace("http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#"),
    "mit": Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk#"),
    "mitctrl": Namespace("http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#"),
}

_TERM_RE = re.compile(r"\b(pair|pat|owasp|atlas|mit|mitctrl):([A-Za-z_][A-Za-z0-9_-]*)")
_BINDS_RE = re.compile(r"bindsPatternNode\s+pat:(\w+)")


@pytest.fixture(scope="module")
def libraries() -> Graph:
    g = Graph()
    for path in (
        CORE / "pair_ai_pattern.ttl",
        CORE / "beam_core.ttl",
        CORE / "beam_core_risk.ttl",
        PATTERNS / "motif.ttl",
        PATTERNS / "risk_pattern_library.ttl",
        PATTERNS / "control_mitigation_layer.ttl",
    ):
        g.parse(path, format="turtle")
    return g


@pytest.fixture(scope="module")
def taxonomies() -> Graph:
    g = Graph()
    for path in sorted(TAXONOMY.glob("*.ttl")):
        g.parse(path, format="turtle")
    return g


@pytest.fixture(scope="module")
def query_texts() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(IMPL.glob("*.rq"))}


def test_every_pair_and_pat_term_in_queries_is_declared(libraries, query_texts) -> None:
    """A pair:/pat: URI in a query that no library declares is a dead or
    unfalsifiable rule - the original hallucination failure mode."""
    declared = set(libraries.subjects())
    offenders = []
    for fname, text in query_texts.items():
        for prefix, local in set(_TERM_RE.findall(text)):
            if prefix not in ("pair", "pat"):
                continue
            uri = NAMESPACES[prefix][local]
            if uri not in declared:
                offenders.append(f"{fname}: {prefix}:{local}")
    assert not offenders, "URIs used in queries but declared nowhere:\n" + "\n".join(sorted(offenders))


def test_taxonomy_terms_in_queries_and_libraries_resolve(libraries, taxonomies, query_texts) -> None:
    tax_subjects = set(taxonomies.subjects())
    offenders = []
    for fname, text in query_texts.items():
        for prefix, local in set(_TERM_RE.findall(text)):
            if prefix in ("owasp", "atlas", "mit", "mitctrl"):
                uri = NAMESPACES[prefix][local]
                if uri not in tax_subjects:
                    offenders.append(f"{fname}: {prefix}:{local}")
    for pred in (PAIR.mayIndicateRisk, PAIR.suggestedControl, PAIR.derivedFrom,
                 PAIR.hasMechanism, PAIR.operationalizesRiskCondition):
        for subj, obj in libraries.subject_objects(pred):
            if isinstance(obj, URIRef) and "taxonomy" in str(obj) and obj not in tax_subjects:
                offenders.append(f"library: {subj.n3(libraries.namespace_manager)} {pred.n3(libraries.namespace_manager)} {obj}")
    assert not offenders, "Dangling taxonomy references:\n" + "\n".join(sorted(offenders))


def test_risk_queries_only_reference_pattern_nodes_that_match_queries_emit(query_texts) -> None:
    """risk_*.rq joins on binding-node URIs; if no match_*.rq emits that URI,
    the join is silently empty (e.g. the pat:DirectPrompting_* vs pat:DP_*
    drift this test was born from)."""
    emitted = {n for f, t in query_texts.items() if f.startswith("match_") for n in _BINDS_RE.findall(t)}
    offenders = []
    for fname, text in query_texts.items():
        if not fname.startswith("risk_"):
            continue
        for node in set(_BINDS_RE.findall(text)):
            if node not in emitted:
                offenders.append(f"{fname}: pat:{node}")
    assert not offenders, "Risk queries reference binding nodes no match query emits:\n" + "\n".join(sorted(offenders))


def test_match_queries_emit_only_declared_pattern_nodes(libraries, query_texts) -> None:
    declared_nodes = set(libraries.subjects(RDF.type, PAIR.PatternNode))
    offenders = []
    for fname, text in query_texts.items():
        if not fname.startswith("match_"):
            continue
        for node in set(_BINDS_RE.findall(text)):
            if PAT[node] not in declared_nodes:
                offenders.append(f"{fname}: pat:{node}")
    assert not offenders, "Match queries emit pattern nodes not declared in motif.ttl:\n" + "\n".join(sorted(offenders))


def test_implementation_paths_resolve_and_no_orphan_queries(libraries) -> None:
    registered: set[Path] = set()
    missing = []
    for impl in libraries.subjects(RDF.type, PAIR.PatternImplementation):
        value = libraries.value(impl, PAIR.implementationPath)
        assert value is not None, f"{impl} has no pair:implementationPath"
        path = (REPO_ROOT / str(value)).resolve()
        registered.add(path)
        if not path.is_file():
            missing.append(f"{impl} -> {value}")
    assert not missing, "implementationPath does not resolve:\n" + "\n".join(missing)
    orphans = [p.name for p in sorted(IMPL.glob("*.rq")) if p.resolve() not in registered]
    assert not orphans, "Query files on disk but registered by no PatternImplementation:\n" + "\n".join(orphans)


def test_implementation_targets_exist(libraries) -> None:
    motifs = set(libraries.subjects(RDF.type, PAIR.GraphMotif))
    risk_patterns = set(libraries.subjects(RDF.type, PAIR.RiskPattern))
    offenders = []
    for impl in libraries.subjects(RDF.type, PAIR.PatternImplementation):
        for m in libraries.objects(impl, PAIR.implementsMotif):
            if m not in motifs:
                offenders.append(f"{impl} implementsMotif {m}")
        for r in libraries.objects(impl, PAIR.implementsRiskPattern):
            if r not in risk_patterns:
                offenders.append(f"{impl} implementsRiskPattern {r}")
    assert not offenders, "\n".join(offenders)


def test_motif_riskpattern_links_are_symmetric(libraries) -> None:
    """Every motif-side hasRiskPattern must have a pattern-side hasMotif and
    vice versa (no OWL reasoning runs, so inverses are never materialized).
    ExcessiveAgencyRiskPattern is documented as deliberately motif-less."""
    offenders = []
    for motif, rp in libraries.subject_objects(PAIR.hasRiskPattern):
        if (rp, PAIR.hasMotif, motif) not in libraries:
            offenders.append(f"{rp} missing hasMotif {motif}")
    for rp, motif in libraries.subject_objects(PAIR.hasMotif):
        if (motif, PAIR.hasRiskPattern, rp) not in libraries:
            offenders.append(f"{motif} missing hasRiskPattern {rp}")
    assert not offenders, "Asymmetric motif<->risk-pattern links:\n" + "\n".join(sorted(offenders))


def test_example_roles_and_categories_are_declared(libraries) -> None:
    offenders = []
    for path in sorted(EXAMPLES.glob("*.ttl")):
        eg = Graph()
        eg.parse(path, format="turtle")
        local_roles = set(eg.subjects(RDF.type, PAIR.PatternRole))
        local_cats = set(eg.subjects(RDF.type, PAIR.DataCategory))
        declared_roles = set(libraries.subjects(RDF.type, PAIR.PatternRole)) | local_roles
        declared_cats = set(libraries.subjects(RDF.type, PAIR.DataCategory)) | local_cats
        for role in set(eg.objects(None, PAIR.playsRole)):
            if role not in declared_roles:
                offenders.append(f"{path.name}: role {role}")
        for cat in set(eg.objects(None, PAIR.containsDataCategory)):
            if cat not in declared_cats:
                offenders.append(f"{path.name}: category {cat}")
    assert not offenders, "Examples use roles/categories declared nowhere:\n" + "\n".join(sorted(offenders))


def test_risk_patterns_have_condition_mechanism_and_taxonomy_anchor(libraries) -> None:
    offenders = []
    for rp in libraries.subjects(RDF.type, PAIR.RiskPattern):
        if libraries.value(rp, PAIR.hasApplicabilityCondition) is None:
            offenders.append(f"{rp} has no applicability condition")
        if libraries.value(rp, PAIR.hasMechanism) is None:
            offenders.append(f"{rp} has no mechanism")
        if libraries.value(rp, PAIR.mayIndicateRisk) is None:
            offenders.append(f"{rp} has no taxonomy anchor")
    assert not offenders, "\n".join(sorted(offenders))


# --- Anchor-alignment checks (2026-07-17 taxonomy audit) -------------------
#
# Every risk pattern anchors to one OWASP entry via pair:derivedFrom. Its
# mechanism, applicability conditions, direct mitctrl suggestions, and
# taxonomy links must all be reachable from that anchor through the curated
# taxonomy/mapping layer - otherwise the pattern free-rides on links that
# nothing in the aligned knowledge supports (the LLM-fabrication failure
# mode this audit removed).

NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")
SKOS_NS = Namespace("http://www.w3.org/2004/02/skos/core#")

# Documented exception: the sensitive-retrieval pattern (LLM02 anchor)
# deliberately reuses the LLM08-defined retrieval conditions because its OQP
# gates on vector-store retrieval; see the comment in risk_pattern_library.ttl.
CONDITION_EXCEPTIONS = {
    (PAT.SensitiveDataRetrievalExposureRiskPattern,
     PAT.VectorEmbeddingWeakness_RetrievalCondition),
}


@pytest.fixture(scope="module")
def aligned(libraries, taxonomies) -> Graph:
    g = Graph()
    for other in (libraries, taxonomies):
        for t in other:
            g.add(t)
    return g


def _anchor(g: Graph, rp) -> URIRef:
    return g.value(rp, PAIR.derivedFrom)


def test_pattern_mechanism_belongs_to_its_anchor(aligned) -> None:
    offenders = []
    for rp in aligned.subjects(RDF.type, PAIR.RiskPattern):
        anchor = _anchor(aligned, rp)
        mech = aligned.value(rp, PAIR.hasMechanism)
        if anchor is None or mech is None:
            continue
        if (anchor, NEXUS.hasRiskMechanism, mech) not in aligned:
            offenders.append(f"{rp}: mechanism {mech} is not the mechanism of anchor {anchor}")
    assert not offenders, "\n".join(sorted(offenders))


def test_pattern_conditions_operationalize_anchor_conditions(aligned) -> None:
    offenders = []
    for rp in aligned.subjects(RDF.type, PAIR.RiskPattern):
        anchor = _anchor(aligned, rp)
        if anchor is None:
            continue
        anchor_conditions = set(aligned.objects(anchor, NEXUS.hasRiskCondition))
        for cond in aligned.objects(rp, PAIR.hasApplicabilityCondition):
            if (rp, cond) in CONDITION_EXCEPTIONS:
                continue
            sources = set(aligned.objects(cond, PAIR.operationalizesRiskCondition))
            if sources and not (sources & anchor_conditions):
                offenders.append(
                    f"{rp}: condition {cond} operationalizes none of its anchor's risk conditions"
                )
    assert not offenders, "\n".join(sorted(offenders))


def test_direct_mitctrl_suggestions_agree_with_anchor_mapping(aligned) -> None:
    """Every mitctrl:* control a pattern suggests must be a
    nexus:hasRelatedControl of the pattern's OWASP anchor - i.e. what a
    finding recommends agrees with the taxonomy mapping.

    NOTE (2026-07-17): as of the CSV regrounding, both sides are grounded in
    the same evidence: taxonomy_mapping.ttl's owasp->hasRelatedControl links
    for LLM01-06/09 are derived from the risk-to-mitigation CSV rollup, and
    the risk patterns' mitctrl:* suggestedControl were regrounded to match
    (LLM07/08/10 kept their prior curation, which already agreed). pat:Control_*
    aggregates are exempt - they are PAIR-AI's own actionable control layer."""
    mitctrl_ns = str(NAMESPACES["mitctrl"])
    offenders = []
    for rp in aligned.subjects(RDF.type, PAIR.RiskPattern):
        anchor = _anchor(aligned, rp)
        if anchor is None:
            continue
        related = set(aligned.objects(anchor, NEXUS.hasRelatedControl))
        for ctrl in aligned.objects(rp, PAIR.suggestedControl):
            if str(ctrl).startswith(mitctrl_ns) and ctrl not in related:
                offenders.append(f"{rp}: {ctrl} is not a related control of anchor {anchor}")
    assert not offenders, "\n".join(sorted(offenders))


def test_may_indicate_risk_entries_are_mapped_to_anchor(aligned) -> None:
    """Every non-anchor mayIndicateRisk entry must be connected to the
    pattern's anchor by a SKOS mapping triple (either direction) in the
    taxonomy/mapping layer."""
    mapping_preds = [SKOS_NS.exactMatch, SKOS_NS.closeMatch, SKOS_NS.broadMatch,
                     SKOS_NS.narrowMatch, SKOS_NS.relatedMatch]
    offenders = []
    for rp in aligned.subjects(RDF.type, PAIR.RiskPattern):
        anchor = _anchor(aligned, rp)
        if anchor is None:
            continue
        for entry in aligned.objects(rp, PAIR.mayIndicateRisk):
            if entry == anchor:
                continue
            linked = any(
                (entry, p, anchor) in aligned or (anchor, p, entry) in aligned
                for p in mapping_preds
            )
            if not linked:
                offenders.append(f"{rp}: {entry} has no SKOS mapping to anchor {anchor}")
    assert not offenders, "\n".join(sorted(offenders))


# --- Control mitigation layer (2026-07-17) --------------------------------

def test_every_suggested_control_has_a_nature(libraries) -> None:
    """Every control a risk pattern suggests must be classified
    technical/non-technical, so the workbench never shows an unclassified
    mitigation."""
    offenders = []
    for control in set(libraries.objects(None, PAIR.suggestedControl)):
        if libraries.value(control, PAIR.controlNature) is None:
            offenders.append(f"{control} is suggested but has no pair:controlNature")
    assert not offenders, "\n".join(sorted(offenders))


def test_realized_by_motif_targets_are_declared_motifs(libraries) -> None:
    """A control's structural-mitigation link must point at a real motif."""
    motifs = set(libraries.subjects(RDF.type, PAIR.GraphMotif))
    offenders = [
        f"{control} pair:realizedByMotif {motif} - not a declared pair:GraphMotif"
        for control, motif in libraries.subject_objects(PAIR.realizedByMotif)
        if motif not in motifs
    ]
    assert not offenders, "\n".join(sorted(offenders))
