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
