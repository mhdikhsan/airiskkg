"""Mechanical consistency net for the AI-RKG pattern layer.

Cross-checks the five layers of the pattern knowledge for identifier drift -
the failure mode of LLM-assisted curation, where each layer looks plausible
in isolation but references URIs the other layers never declare or emit:

  A. declared vocabulary  (ontology/core/pair_ai_pattern.ttl)
  B. motif library        (ontology/patterns/motif.ttl)
  C. risk pattern library (ontology/patterns/risk_pattern_library.ttl)
  D. SPARQL queries       (ontology/patterns/implementation/{match,risk,propagation}/)
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
from rdflib import DCTERMS, RDF, Graph, Namespace, URIRef

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
    # keyed by "<kind>/<file>" (match/, risk/, propagation/) so tests can filter by
    # query kind. Filtering on a filename prefix would silently match nothing.
    return {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8")
            for p in sorted(IMPL.rglob("*.rq"))}


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
    """risk/*.rq joins on binding-node URIs; if no match/*.rq emits that URI,
    the join is silently empty (e.g. the pat:DirectPrompting_* vs pat:DP_*
    drift this test was born from)."""
    emitted = {n for f, t in query_texts.items() if f.startswith("match/") for n in _BINDS_RE.findall(t)}
    offenders = []
    for fname, text in query_texts.items():
        if not fname.startswith("risk/"):
            continue
        for node in set(_BINDS_RE.findall(text)):
            if node not in emitted:
                offenders.append(f"{fname}: pat:{node}")
    assert not offenders, "Risk queries reference binding nodes no match query emits:\n" + "\n".join(sorted(offenders))


def test_match_queries_emit_only_declared_pattern_nodes(libraries, query_texts) -> None:
    declared_nodes = set(libraries.subjects(RDF.type, PAIR.PatternNode))
    offenders = []
    for fname, text in query_texts.items():
        if not fname.startswith("match/"):
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
    orphans = [p.name for p in sorted(IMPL.rglob("*.rq")) if p.resolve() not in registered]
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


def test_suggested_controls_are_pat_only(aligned) -> None:
    """Single-vocabulary invariant (2026-07-21 refactor): pair:suggestedControl
    carries ONLY PAIR-AI's own actionable control catalogue (pat:Control_*). MIT
    mitigation families (mitctrl:*) are no longer mirrored in as peer controls -
    they live in taxonomy_mapping.ttl (owasp:* nexus:hasRelatedControl mitctrl:*)
    and reach a finding as an evidence layer via its taxonomy entries. This keeps
    one vocabulary per role and stops the altitude/redundancy muddle that mixing
    an actionable control with a taxonomy family in one bag produced."""
    control_prefix = str(NAMESPACES["pat"]) + "Control_"
    offenders = []
    for rp in aligned.subjects(RDF.type, PAIR.RiskPattern):
        for ctrl in aligned.objects(rp, PAIR.suggestedControl):
            if not str(ctrl).startswith(control_prefix):
                offenders.append(f"{rp}: suggestedControl {ctrl} is not a pat:Control_*")
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


# --- Library completeness (2026-07-21) --------------------------------------
#
# Every motif in the motif library must have a matching OQP, and every risk
# pattern must have a risk OQP - otherwise a declared pattern is inert
# knowledge the engine can never surface. The canonical-instance test also
# guards the always-empty-query failure mode: a registered query that matches
# nothing because its role/class constraints drifted from the motif's ODP.

def test_every_motif_has_a_matching_oqp(libraries) -> None:
    matched = set(libraries.objects(None, PAIR.implementsMotif))
    offenders = sorted(
        str(m) for m in libraries.subjects(RDF.type, PAIR.GraphMotif) if m not in matched
    )
    assert not offenders, "Motifs with no matching OQP:\n" + "\n".join(offenders)


def test_every_risk_pattern_has_an_oqp(libraries) -> None:
    implemented = set(libraries.objects(None, PAIR.implementsRiskPattern))
    offenders = sorted(
        str(r) for r in libraries.subjects(RDF.type, PAIR.RiskPattern) if r not in implemented
    )
    assert not offenders, "Risk patterns with no OQP:\n" + "\n".join(offenders)


# Documented ODP/OQP divergence: EmbeddingsMotif's OQP additionally requires an
# indexing step (uses chunk + vector, produces the index) that the motif does
# NOT declare as a pattern node - stated in its rdfs:comment in motif.ttl. A
# canonical instance built from the declared nodes therefore lacks that step and
# does not match; this is a deliberate, recorded exception (not drift).
CANONICAL_INSTANCE_EXCEPTIONS = {PAT.EmbeddingsMotif}


def test_each_motif_query_matches_its_canonical_instance(libraries) -> None:
    """Each motif's matching OQP must produce >=1 match on a canonical instance
    synthesized directly from the motif's declared PatternNode/PatternEdge
    structure (one element per node with its expectedClass + expectedRole, one
    beam edge per declared edge). Catches queries that are registered but match
    nothing - the ODP/OQP drift failure mode."""
    from airiskkg.assessment_runner import load_base_graph, run_construct_query

    synth = Namespace("http://example.org/synth-consistency#")
    impl_path: dict = {}
    for impl in libraries.subjects(RDF.type, PAIR.PatternImplementation):
        for motif in libraries.objects(impl, PAIR.implementsMotif):
            impl_path[motif] = str(libraries.value(impl, PAIR.implementationPath))

    base = load_base_graph()
    offenders = []
    for motif in libraries.subjects(RDF.type, PAIR.GraphMotif):
        if motif in CANONICAL_INSTANCE_EXCEPTIONS:
            continue
        path = impl_path.get(motif)
        if path is None:
            continue  # covered by test_every_motif_has_a_matching_oqp
        node_element = {}
        added = []
        for node in libraries.objects(motif, PAIR.hasPatternNode):
            element = URIRef(synth + str(node).split("#")[-1])
            node_element[node] = element
            expected_class = libraries.value(node, PAIR.expectedClass)
            expected_role = libraries.value(node, PAIR.expectedRole)
            if expected_class is not None:
                added.append((element, RDF.type, expected_class))
            if expected_role is not None:
                added.append((element, PAIR.playsRole, expected_role))
        for edge in libraries.objects(motif, PAIR.hasPatternEdge):
            source = libraries.value(edge, PAIR.sourcePatternNode)
            predicate = libraries.value(edge, PAIR.patternPredicate)
            target = libraries.value(edge, PAIR.targetPatternNode)
            added.append((node_element[source], predicate, node_element[target]))

        for triple in added:
            base.add(triple)
        result = run_construct_query(base, REPO_ROOT / path)
        if not set(result.subjects(PAIR.matchesMotif, motif)):
            offenders.append(str(motif))
        for triple in added:
            base.remove(triple)

    assert not offenders, (
        "Motif queries that match none of their own canonical instance:\n"
        + "\n".join(sorted(offenders))
    )


# Un-skip this (delete the xfail marker) once the provenance worklist has been
# filled in by hand and pair:maturity written back into the libraries. Generate
# the worklist with:
#     python python/scripts/pattern_provenance_worklist.py
# It reports, per motif / risk pattern, what source and maturity are already
# present. Sources must never be invented - leave an entry unsourced rather
# than attributing it to a document it did not come from.
@pytest.mark.xfail(
    strict=False,
    reason="pair:maturity is not curated yet; see /tmp/pattern_provenance_worklist.csv",
)
def test_every_motif_and_risk_pattern_has_source_and_maturity(libraries) -> None:
    """Every curated library entry states where it came from (dct:source) and how
    far its curation has got (pair:maturity)."""
    missing_source: list[str] = []
    missing_maturity: list[str] = []

    for rdf_type in (PAIR.GraphMotif, PAIR.RiskPattern):
        for subject in sorted(libraries.subjects(RDF.type, rdf_type), key=str):
            if libraries.value(subject, DCTERMS.source) is None:
                missing_source.append(str(subject))
            if libraries.value(subject, PAIR.maturity) is None:
                missing_maturity.append(str(subject))

    assert not missing_source, (
        f"{len(missing_source)} entries without dct:source: " + ", ".join(missing_source)
    )
    assert not missing_maturity, (
        f"{len(missing_maturity)} entries without pair:maturity: " + ", ".join(missing_maturity)
    )


def test_specific_roles_are_subroles_of_the_role_their_motif_queries(libraries) -> None:
    """A precise role must sit under the general role its motif actually queries.

    Match queries traverse pair:playsRole/pair:subRoleOf*, so a specific role
    parented directly to an abstract top-level role is inert: annotating an
    element with the obviously-correct precise term then silently prevents the
    motif from matching, and the graph has to double-tag with the general role
    to work. Regression guard for exactly that class of bug."""
    expected_parents = {
        # role -> the role its motif's pattern node requires
        PAIR.RewrittenQuery: PAIR.UserInput,
        PAIR.RerankedContext: PAIR.RetrievedContext,
    }
    for role, parent in expected_parents.items():
        ancestors = set(libraries.transitive_objects(role, PAIR.subRoleOf))
        assert parent in ancestors, (
            f"{role} must be a sub-role of {parent}, otherwise tagging an element "
            f"with {role} alone cannot satisfy the motif that queries {parent}"
        )
