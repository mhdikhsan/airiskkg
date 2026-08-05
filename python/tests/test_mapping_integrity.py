"""Mechanical falsifiability checks on the cross-taxonomy mapping layer.

Cross-vocabulary alignment is the part of this knowledge base that rests most
heavily on judgement, and judgement is exactly what a test suite cannot audit.
What it CAN audit is logical coherence: a set of mappings can be internally
contradictory regardless of who or what produced it, and those contradictions
are decidable. These checks catch the errors that survive review because they
look plausible in isolation and only conflict with a statement made elsewhere.

The direction-sensitive failure mode is the one worth designing against. In this
repo an ASI -> OWASP link was once curated in the inverse direction and read as
entirely reasonable; it was caught only by comparing against upstream. Hierarchy
predicates are easy to state backwards and hard to eyeball, so most of what
follows is about direction.

SKOS direction, since every check below depends on it:

    A skos:broader  B   -- B is the more general concept (B is A's parent)
    A skos:broadMatch B -- same, across schemes: A is a subset of B
    A skos:narrowMatch B -- B is a subset of A

These are guards, not bug reports: the mapping layer satisfies all of them
today. They exist so that the next mapping added - by a human, from upstream, or
LLM-assisted - cannot silently contradict one already present.
"""

from __future__ import annotations

import glob

import pytest
from rdflib import DCTERMS, Graph, Namespace, RDF, SKOS, URIRef
from rdflib.namespace import PROV

from airiskkg.paths import REPO_ROOT

# skos:noMatch is not in rdflib's SKOS namespace object but is used by SSSOM to
# record a checked non-correspondence, which is a result worth keeping.
NO_MATCH = URIRef(str(SKOS) + "noMatch")

# Risk -> control grounding is a correspondence claim too, and the larger half of
# the mapping layer. It is excluded from the coherence checks above (it is not a
# SKOS hierarchy) but included in the provenance coverage check below.
HAS_RELATED_CONTROL = URIRef("http://w3id.org/airiskkg/taxonomy/nexus#hasRelatedControl")

MAPPING_PREDICATES = (
    SKOS.exactMatch,
    SKOS.closeMatch,
    SKOS.broadMatch,
    SKOS.narrowMatch,
    SKOS.relatedMatch,
)


@pytest.fixture(scope="module")
def taxonomy() -> Graph:
    graph = Graph()
    for path in sorted(glob.glob(str(REPO_ROOT / "ontology" / "taxonomy" / "*.ttl"))):
        graph.parse(path)
    return graph


def _name(term) -> str:
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _mappings(graph: Graph) -> list[tuple[URIRef, URIRef, URIRef]]:
    return [
        (s, p, o)
        for p in MAPPING_PREDICATES
        for s, _, o in graph.triples((None, p, None))
    ]


def test_the_mapping_layer_is_not_empty(taxonomy: Graph) -> None:
    """Guard against the whole file silently vacuuming out - every check below
    passes trivially on an empty graph."""
    assert len(_mappings(taxonomy)) > 50


def test_mapping_predicates_are_used_only_across_schemes(taxonomy: Graph) -> None:
    """skos:*Match states a correspondence between two vocabularies; skos:broader
    states a hierarchy inside one. Using a match predicate within a single scheme
    claims an alignment where there is only a parent."""
    scheme = dict(taxonomy.subject_objects(SKOS.inScheme))
    offenders = [
        (s, p, o)
        for s, p, o in _mappings(taxonomy)
        if scheme.get(s) is not None and scheme.get(s) == scheme.get(o)
    ]
    assert not offenders, "\n".join(
        f"{_name(s)} {_name(p)} {_name(o)} - same scheme, use skos:broader"
        for s, p, o in offenders
    )


def test_no_pair_of_concepts_carries_two_mapping_predicates(taxonomy: Graph) -> None:
    """The predicates are mutually exclusive readings of one relationship. Two of
    them on the same ordered pair means two incompatible claims, typically from
    one mapping being added without noticing another already existed."""
    seen: dict[tuple[URIRef, URIRef], set[str]] = {}
    for s, p, o in _mappings(taxonomy):
        seen.setdefault((s, o), set()).add(_name(p))
    conflicts = {pair: preds for pair, preds in seen.items() if len(preds) > 1}
    assert not conflicts, "\n".join(
        f"{_name(s)} -> {_name(o)}: {sorted(preds)}" for (s, o), preds in conflicts.items()
    )


def test_no_mapping_contradicts_a_recorded_non_correspondence(taxonomy: Graph) -> None:
    """Upstream SSSOM sets record skos:noMatch - 'we checked, there is no
    correspondence'. A positive mapping over the same pair overrides a negative
    result somebody deliberately recorded, in either direction."""
    denied = {frozenset((s, o)) for s, _, o in taxonomy.triples((None, NO_MATCH, None))}
    offenders = [(s, p, o) for s, p, o in _mappings(taxonomy) if frozenset((s, o)) in denied]
    assert not offenders, "\n".join(
        f"{_name(s)} {_name(p)} {_name(o)} contradicts a recorded noMatch"
        for s, p, o in offenders
    )


def test_nothing_is_transitively_broader_than_itself(taxonomy: Graph) -> None:
    """The inversion guard. Read every hierarchical mapping as one edge 'is a
    subset of' and look for a cycle: a cycle means some concept ends up strictly
    broader than itself, which is the shape a backwards mapping makes once it
    meets the mappings around it. A single inverted link is invisible on its own
    and only becomes decidable in combination - which is precisely why review
    misses it."""
    edges: dict[URIRef, set[URIRef]] = {}
    for subject, _, obj in taxonomy.triples((None, SKOS.broadMatch, None)):
        edges.setdefault(subject, set()).add(obj)  # subject is a subset of obj
    for subject, _, obj in taxonomy.triples((None, SKOS.narrowMatch, None)):
        edges.setdefault(obj, set()).add(subject)  # obj is a subset of subject
    for subject, _, obj in taxonomy.triples((None, SKOS.broader, None)):
        edges.setdefault(subject, set()).add(obj)

    cycles: list[list[URIRef]] = []
    visiting: set[URIRef] = set()
    done: set[URIRef] = set()

    def walk(node: URIRef, trail: list[URIRef]) -> None:
        if node in visiting:
            cycles.append(trail[trail.index(node) :] + [node])
            return
        if node in done:
            return
        visiting.add(node)
        for nxt in edges.get(node, ()):
            walk(nxt, trail + [nxt])
        visiting.discard(node)
        done.add(node)

    for start in list(edges):
        walk(start, [start])

    assert not cycles, "\n".join(" -> ".join(_name(n) for n in c) for c in cycles)


def test_no_two_concepts_claim_to_be_exactly_the_same_external_concept(
    taxonomy: Graph,
) -> None:
    """skos:exactMatch is transitive enough to be dangerous: if two of our
    concepts are both exactly X, they are exactly each other. Whenever that is
    not intended, one of the two is really a closeMatch or a broadMatch."""
    claimants: dict[URIRef, set[URIRef]] = {}
    for subject, _, obj in taxonomy.triples((None, SKOS.exactMatch, None)):
        claimants.setdefault(obj, set()).add(subject)
    collisions = {t: c for t, c in claimants.items() if len(c) > 1}
    assert not collisions, "\n".join(
        f"{_name(target)} claimed by {sorted(_name(c) for c in concepts)}"
        for target, concepts in collisions.items()
    )


def test_a_child_never_maps_more_broadly_than_its_own_parent(taxonomy: Graph) -> None:
    """Coherence between the hierarchy and the mappings laid over it.

    Given child C under parent P, C is a subset of P. If C claims some external T
    is a subset of C (narrowMatch) while P claims P is a subset of that same T
    (broadMatch or exactMatch), then P <= T <= C <= P forces C, P and T to be the
    same concept - the child collapses into its parent. That is always an error
    in one of the two mappings, and it is invisible unless the pair is inspected
    together."""
    relation: dict[URIRef, dict[URIRef, str]] = {}
    for subject, predicate, obj in _mappings(taxonomy):
        relation.setdefault(subject, {})[obj] = _name(predicate)

    offenders = []
    for child, _, parent in taxonomy.triples((None, SKOS.broader, None)):
        for target, child_rel in relation.get(child, {}).items():
            parent_rel = relation.get(parent, {}).get(target)
            if child_rel == "narrowMatch" and parent_rel in {"broadMatch", "exactMatch"}:
                offenders.append((child, parent, target, child_rel, parent_rel))

    assert not offenders, "\n".join(
        f"{_name(c)} {cr} {_name(t)} but parent {_name(p)} {pr} {_name(t)}"
        f" - collapses {_name(c)} into {_name(p)}"
        for c, p, t, cr, pr in offenders
    )


def test_every_mapped_concept_is_declared_somewhere(taxonomy: Graph) -> None:
    """A mapping to a URI that no file declares is a typo or a stale identifier,
    and it fails open: the mapping simply never matches anything."""
    declared = set(taxonomy.subjects(SKOS.inScheme, None)) | set(
        taxonomy.subjects(SKOS.prefLabel, None)
    )
    external_ok = ("dpv", "w3.org", "purl.org", "semanticscience")
    dangling = {
        term
        for s, _, o in _mappings(taxonomy)
        for term in (s, o)
        if term not in declared and not any(k in str(term) for k in external_ok)
    }
    assert not dangling, "undeclared concepts in mappings: " + ", ".join(
        sorted(_name(d) for d in dangling)
    )


# --- Provenance layer ------------------------------------------------------
# Every mapping carries how it was produced, as data rather than as a section
# comment. See python/scripts/generate_mapping_provenance.py.

SSSOM = Namespace("https://w3id.org/sssom/")
SEMAPV = Namespace("https://w3id.org/semapv/vocab/")
PROVENANCE = REPO_ROOT / "ontology" / "taxonomy" / "provenance" / "mapping_provenance.ttl"

# The closed set of SEMAPV justifications this project uses. Restricting it is
# the point: an unlisted value means someone recorded a method nobody agreed to.
ALLOWED_JUSTIFICATIONS = {
    "ManualMappingCuration",
    "SemanticSimilarityThresholdMatching",
    "UnspecifiedMatching",
    "LexicalMatching",
    "LogicalReasoning",
    "MappingReview",
}


@pytest.fixture(scope="module")
def provenance() -> Graph:
    graph = Graph()
    graph.parse(PROVENANCE)
    return graph


def test_the_provenance_layer_is_not_loaded_by_the_assessment(taxonomy: Graph) -> None:
    """The load-bearing half of 'keep it away from production'.

    This layer is evidence ABOUT the knowledge base, not knowledge the pipeline
    may reason over - a risk finding must never be able to cite its own
    provenance record as support. The runner globs ontology/taxonomy/*.ttl
    non-recursively, so living one directory down excludes it by construction
    rather than by anyone remembering to. This test pins that: move the file up a
    level and it fails."""
    from airiskkg.paths import TAXONOMY_DIR

    assert PROVENANCE.exists(), "provenance layer is missing"
    assert PROVENANCE.parent != TAXONOMY_DIR, "must not sit in the globbed directory"
    assert PROVENANCE not in set(TAXONOMY_DIR.glob("*.ttl"))
    # ...and nothing it declares leaked into the graph the pipeline reads.
    assert not list(taxonomy.triples((None, SSSOM.mapping_justification, None)))


@pytest.fixture(scope="module")
def all_mapped() -> Graph:
    """Every directory that can declare a mapping, not just ontology/taxonomy/.

    The first version of this fixture read taxonomy/ alone, so the coverage test
    below passed while 80 mappings in patterns/ and core/ had no provenance at
    all - a green test asserting a guarantee it was not making. Scoping a
    coverage check to the place you already looked is worse than having none,
    because it converts an unknown into a false assurance."""
    graph = Graph()
    for sub in ("taxonomy", "patterns", "core"):
        for path in sorted((REPO_ROOT / "ontology" / sub).glob("*.ttl")):
            graph.parse(path)
    return graph


def test_every_mapping_has_exactly_one_provenance_record(
    all_mapped: Graph, provenance: Graph
) -> None:
    """Coverage. An unrecorded mapping is indistinguishable from a curated one
    once loaded, which is the failure this layer exists to prevent - so silence
    is not an acceptable default for any mapping anywhere in the ontology."""
    taxonomy = all_mapped
    recorded = {
        (s, p, o)
        for record in provenance.subjects(RDF.type, SSSOM.Mapping)
        for s in [provenance.value(record, SSSOM.subject_id)]
        for p in [provenance.value(record, SSSOM.predicate_id)]
        for o in [provenance.value(record, SSSOM.object_id)]
    }
    actual = {(s, p, o) for s, p, o in _mappings(taxonomy)}
    actual |= {
        (s, HAS_RELATED_CONTROL, o)
        for s, _, o in taxonomy.triples((None, HAS_RELATED_CONTROL, None))
    }
    missing = actual - recorded
    assert not missing, "mappings with no provenance record:\n" + "\n".join(
        f"  {_name(s)} {_name(p)} {_name(o)}" for s, p, o in sorted(missing, key=str)
    )
    stale = recorded - actual
    assert not stale, "provenance records for mappings that no longer exist:\n" + "\n".join(
        f"  {_name(s)} {_name(p)} {_name(o)}" for s, p, o in sorted(stale, key=str)
    )


def test_justifications_come_from_the_agreed_semapv_set(provenance: Graph) -> None:
    """Justification is only useful if the vocabulary is closed; free text would
    let 'reviewed', 'checked' and 'curated' all mean whatever the writer meant."""
    used = {
        str(o)
        for _, _, o in provenance.triples((None, SSSOM.mapping_justification, None))
    }
    unknown = {u for u in used if u.rsplit("/", 1)[-1] not in ALLOWED_JUSTIFICATIONS}
    assert not unknown, f"unrecognised justifications: {sorted(unknown)}"
    assert all(u.startswith(str(SEMAPV)) for u in used), "justifications must be SEMAPV terms"


def test_no_confidence_is_asserted_without_an_upstream_source(provenance: Graph) -> None:
    """A confidence number we did not measure is false precision, and it is worse
    than none because it reads as evidence. Only mappings adopted from a set that
    published confidences may carry one."""
    offenders = []
    for record in provenance.subjects(RDF.type, SSSOM.Mapping):
        confidence = provenance.value(record, SSSOM.confidence)
        if confidence is None:
            continue
        mapping_set = provenance.value(record, PROV.wasDerivedFrom)
        if provenance.value(mapping_set, DCTERMS.source) is None:
            offenders.append((record, mapping_set, confidence))
    assert not offenders, "\n".join(
        f"{_name(r)} claims confidence {c} but {_name(s)} has no upstream source"
        for r, s, c in offenders
    )


def test_the_provenance_layer_is_in_sync_with_its_generator() -> None:
    """The file is generated, so it can drift from the mappings it describes the
    moment someone edits one and not the other. Regenerating and comparing makes
    that impossible to miss."""
    import subprocess
    import sys

    before = PROVENANCE.read_text(encoding="utf-8")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "python" / "scripts" / "generate_mapping_provenance.py")],
        check=True,
        capture_output=True,
    )
    assert PROVENANCE.read_text(encoding="utf-8") == before, (
        "mapping_provenance.ttl is stale - regenerate it with\n"
        "  python python/scripts/generate_mapping_provenance.py"
    )


# --- Facet grounding -------------------------------------------------------
# The characterization facets carry the project's strongest provenance claim, so
# the claim itself needs guarding. The layer is NOT wholesale "OECD/DPV-derived":
# it is a documented mixture, and the tests below keep it honestly labelled
# rather than letting curation drift into looking like external grounding.

FACET_DIR = REPO_ROOT / "ontology" / "facets"


@pytest.fixture(scope="module")
def facets() -> Graph:
    graph = Graph()
    for path in sorted(FACET_DIR.glob("*.ttl")):
        graph.parse(path)
    return graph


def test_every_facet_concept_declares_a_source(facets: Graph) -> None:
    """A facet value with no stated origin is indistinguishable from one lifted
    from a published framework, which is the confusion the whole facet layer is
    supposed to resolve."""
    unsourced = [
        c
        for c in facets.subjects(SKOS.inScheme, None)
        if not list(facets.objects(c, DCTERMS.source))
    ]
    assert not unsourced, "facet concepts with no dct:source: " + ", ".join(
        sorted(_name(c) for c in unsourced)
    )


def test_facet_sources_are_of_a_recognised_kind(facets: Graph) -> None:
    """Closed set of four forms: a citable work, a resolvable vocabulary URI, an
    internal document with a section locus, or an explicit statement that this is
    project curation. Free text would let 'based on OECD' sit next to 'OECD
    (2022), Table 4' and read as equally grounded."""
    import re

    unclassified = []
    for source in facets.objects(None, DCTERMS.source):
        text = str(source)
        citable = "doi.org" in text or re.search(r"\(\d{4}\)", text)
        resolvable = text.startswith("http") or "w3id.org" in text
        internal = "glossary" in text.lower() and "Section" in text
        curated = "curation" in text.lower()
        if not (citable or resolvable or internal or curated):
            unclassified.append(text)
    assert not unclassified, "unclassifiable facet sources:\n" + "\n".join(
        f"  {t[:90]}" for t in unclassified
    )


def test_citing_dpv_requires_actually_linking_to_dpv(facets: Graph) -> None:
    """The difference between alignment and name-dropping. DPV publishes
    resolvable URIs, so a concept that claims DPV as its source can carry a
    mapping a third party can check - and if it cannot, the citation is doing
    rhetorical work its evidence does not support.

    This is the check that would not survive minting an OECD concept scheme:
    OECD publishes no URIs, so an oecd:* concept could only ever be one we wrote
    ourselves from the same reading that produced the facet value. The mapping
    would be true by construction and would prove nothing. That asymmetry is why
    OECD stays a cited documentary source while DPV is an alignment target."""
    offenders = []
    for concept in facets.subjects(SKOS.inScheme, None):
        sources = " ".join(str(o) for o in facets.objects(concept, DCTERMS.source))
        if "dpv" not in sources.lower():
            continue
        linked = any(
            "dpv" in str(o)
            for predicate in MAPPING_PREDICATES
            for o in facets.objects(concept, predicate)
        )
        if not linked:
            offenders.append(concept)
    assert not offenders, "cite DPV but carry no DPV mapping: " + ", ".join(
        sorted(_name(c) for c in offenders)
    )


# --- Section 3 reproducibility --------------------------------------------
# The 32 embedding-derived risk -> control links were the weakest block in the
# knowledge base and, until the source CSV was recovered, could not be checked by
# anyone. Now they can, so this pins it: the committed links must remain exactly
# what the CSV rolls up to, or one of the two has drifted.

RISK_TO_MITIGATION_CSV = (
    REPO_ROOT / "data" / "mappings" / "Final_Mapped_Taxonomy_Table_Output.csv"
)
OWASP_NS = Namespace("http://w3id.org/airiskkg/taxonomy/owasp-llm#")

# Three MIT sub-categories have no same-named control concept here; these are the
# approximations recorded when the rollup was first applied (2026-07-17).
SUBCATEGORY_ALIASES = {
    "model-alignment": "model-safety-engineering",
    "governance-disclosure": "risk-disclosure",
    "third-party-system-access": "access-management",
}


def _rollup_from_csv() -> dict[str, set[str]]:
    """Reproduce the documented method: for each OWASP risk, collect its mapped
    MIT actions' sub-categories and map them 1:1 onto mitctrl:* concepts."""
    import csv
    import re

    rolled: dict[str, set[str]] = {}
    with RISK_TO_MITIGATION_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            # The CSV carries the OWASP year inline (llm022025-...); the ontology
            # does not. This drift is in the source, not introduced here.
            owasp = row["owasp_id"]
            if re.match(r"llm\d{2}2025", owasp):
                owasp = owasp.replace("2025", "", 1)
            slug = re.sub(r"^[0-9.]+\s*", "", row["Sub_category"]).lower()
            slug = slug.replace(" & ", "-").replace(" ", "-").replace("&", "-")
            rolled.setdefault(owasp, set()).add(SUBCATEGORY_ALIASES.get(slug, slug))
    return rolled


def test_the_risk_to_mitigation_csv_is_present() -> None:
    """Without it the block below is unverifiable, which was the situation until
    the file was recovered. Losing it again should fail loudly, not silently
    reduce these links back to unfalsifiable assertions."""
    assert RISK_TO_MITIGATION_CSV.exists(), (
        f"{RISK_TO_MITIGATION_CSV.name} is missing - the 32 embedding-derived "
        "risk-to-control links can no longer be re-derived or checked"
    )


def test_section_3_control_links_reproduce_from_the_csv(taxonomy: Graph) -> None:
    """The committed links must equal the CSV rollup exactly, in both directions.

    Extra links would mean curation crept in under an evidence-grounded label;
    missing links would mean the rollup was applied selectively. Either way the
    stated provenance would no longer describe the data."""
    offenders = []
    for owasp, expected in sorted(_rollup_from_csv().items()):
        actual = {
            _name(o)
            for o in taxonomy.objects(OWASP_NS[owasp], HAS_RELATED_CONTROL)
        }
        if missing := expected - actual:
            offenders.append(f"{owasp}: in CSV but not in repo - {sorted(missing)}")
        if extra := actual - expected:
            offenders.append(f"{owasp}: in repo but not in CSV - {sorted(extra)}")
    assert not offenders, "\n".join(offenders)


def test_the_csv_defect_is_still_the_known_one(taxonomy: Graph) -> None:
    """The source has a recorded internal inconsistency: action A0973 sits in
    sub-category '2.3 Model Safety Engineering' but is tagged Category 3. The
    rollup keys on Sub_category, so this does not affect any mapping - but if the
    defect ever disappears the CSV has been edited, and the provenance note
    describing it would be stale."""
    import csv

    with RISK_TO_MITIGATION_CSV.open(encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if "A0973" in r["mit_action_id"]]
    assert rows, "A0973 is gone - the CSV changed; re-check the provenance note"
    for row in rows:
        assert row["Sub_category"].startswith("2.3"), row
        assert row["Category"].startswith("3."), (
            "the known Category/Sub_category mismatch on A0973 is no longer "
            "present; the provenance note needs updating"
        )


# --- MIT action layer ------------------------------------------------------
# The mitigation taxonomy is modelled at two levels: families (verbatim MIT) and
# the concrete actions beneath them, generated from the cross-walk. Before the
# action layer existed the rollup collapsed 52 actions into their families before
# the data reached the graph, which is why "93 rows" and "36 concepts" looked
# irreconcilable.

MIT_ACTION_FILE = REPO_ROOT / "ontology" / "taxonomy" / "mit_mitigation_action.ttl"
NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")


@pytest.fixture(scope="module")
def actions() -> Graph:
    graph = Graph()
    graph.parse(MIT_ACTION_FILE)
    return graph


def test_every_action_in_the_crosswalk_is_modelled(actions: Graph) -> None:
    """Both directions. A missing action means the layer was generated from a
    stale CSV; an extra one means it was hand-edited, which the header forbids."""
    import csv
    import re

    with RISK_TO_MITIGATION_CSV.open(encoding="utf-8") as handle:
        expected = {
            re.match(r"^(A\d+)_", row["mit_action_id"]).group(1)
            for row in csv.DictReader(handle)
        }
    modelled = {str(o) for _, _, o in actions.triples((None, SKOS.notation, None))}
    assert modelled == expected, (
        f"missing {sorted(expected - modelled)}, unexpected {sorted(modelled - expected)}"
    )


def test_every_action_hangs_off_a_declared_family(taxonomy: Graph, actions: Graph) -> None:
    """An action whose parent does not exist is unreachable from a finding, which
    silently undoes the point of adding the level at all."""
    families = {
        s for s in taxonomy.subjects(RDF.type, NEXUS.RiskControlGroup)
    } | {
        s for s in taxonomy.subjects(RDF.type, NEXUS.RiskControl)
        if "mit-ai-risk-control#" in str(s)
    }
    dangling = [
        (a, parent)
        for a, _, parent in actions.triples((None, SKOS.broader, None))
        if parent not in families
    ]
    assert not dangling, "\n".join(
        f"{_name(a)} -> {_name(p)} (no such family)" for a, p in dangling
    )


def test_actions_are_marked_as_genuine_mit_entries(actions: Graph) -> None:
    """These ARE taxonomy entries, unlike the 16 concrete mitctrl:* controls,
    which are project curation named after MIT mitigations. Conflating the two
    would claim external grounding for our own work."""
    for action in actions.subjects(SKOS.notation, None):
        assert list(actions.objects(action, NEXUS.isDefinedByTaxonomy)), _name(action)
        assert list(actions.objects(action, DCTERMS.source)), _name(action)
