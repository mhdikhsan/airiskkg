"""Mechanical consistency net for the AI-RKG pattern layer."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from rdflib import DCTERMS, RDF, RDFS, Graph, Namespace, URIRef

from airiskkg.knowledge_base import ontology_files  # noqa: E402

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
    """Everything the runner loads, resolved the way the runner resolves it."""
    g = Graph()
    for path in ontology_files():
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


def test_implementation_links_are_symmetric(libraries) -> None:
    """pair:implementedBy and pair:implementsMotif / pair:implementsRiskPattern
    must both be present, for the same reason the hasMotif mirror must be: no
    OWL reasoning runs, so an inverse is never materialized and a one-sided
    assertion is invisible to any consumer reading the other side.

    This is not hypothetical. A comment-stripping pass on 2026-08-06 dropped
    pair:implementedBy from 17 of 28 motifs. Every test still passed - the
    library-consistency checks all read the OQP->motif direction, which
    survived - while ontology/visualization/motif_visual_graph.rq, which reads
    motif->OQP, silently lost 17 motifs from its output. Nothing failed; the
    view just quietly got smaller."""
    offenders = []
    for subject, implementation in libraries.subject_objects(PAIR.implementedBy):
        back = (implementation, PAIR.implementsMotif, subject) in libraries or (
            implementation,
            PAIR.implementsRiskPattern,
            subject,
        ) in libraries
        if not back:
            offenders.append(f"{subject} -> implementedBy {implementation} has no reverse link")
    for predicate in (PAIR.implementsMotif, PAIR.implementsRiskPattern):
        for implementation, subject in libraries.subject_objects(predicate):
            if (subject, PAIR.implementedBy, implementation) not in libraries:
                offenders.append(f"{subject} missing implementedBy {implementation}")
    assert not offenders, "Asymmetric implementation links:\n" + "\n".join(sorted(offenders))


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


NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")
SKOS_NS = Namespace("http://www.w3.org/2004/02/skos/core#")

CONDITION_EXCEPTIONS = {
    (PAT.SensitiveInformationDisclosureRiskPattern,
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


def test_every_motif_is_shelved_under_exactly_one_family(libraries) -> None:
    """`pair:motifFamily` is what the library browser groups by, so a motif with
    none lands in a group called "Unshelved" and one with two is listed twice.

    The families are a shelving of this library - which family of AI system a
    shape belongs to - read off each motif's own provenance. They are never
    consulted during matching: R2 keeps that to roles and flow relations, and a
    real system matches several families at once.
    """
    families = set(libraries.subjects(SKOS_NS.inScheme, PAIR.MotifFamilyScheme))
    assert families, "no motif families are declared"

    offenders = []
    for motif in set(libraries.subjects(RDF.type, PAIR.GraphMotif)):
        shelved = list(libraries.objects(motif, PAIR.motifFamily))
        if len(shelved) != 1:
            offenders.append(f"{motif} has {len(shelved)} families")
        elif shelved[0] not in families:
            offenders.append(f"{motif} names {shelved[0]}, which is not in the scheme")
    assert not offenders, "\n".join(offenders)


def test_a_motif_family_says_what_it_covers_and_where_it_came_from(libraries) -> None:
    """A group heading with no definition asks the reader to guess what
    "Agentic" means here, and the panel prints the definition under it."""
    for family in sorted(libraries.subjects(SKOS_NS.inScheme, PAIR.MotifFamilyScheme), key=str):
        assert libraries.value(family, SKOS_NS.prefLabel), f"{family} has no label"
        assert libraries.value(family, SKOS_NS.definition), f"{family} says nothing about what it covers"
        assert libraries.value(family, DCTERMS.source), f"{family} states no source"


def test_no_match_query_reads_the_motif_family(libraries) -> None:
    """Shelving is not matching."""
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted((REPO_ROOT / "ontology").rglob("*.rq"))
        if "motifFamily" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, "motif family read during matching: " + ", ".join(offenders)


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


def test_every_motif_and_risk_pattern_states_its_source(libraries) -> None:
    """Every curated library entry states where it came from (Rule R6)."""
    missing_source = [
        str(subject)
        for rdf_type in (PAIR.GraphMotif, PAIR.RiskPattern)
        for subject in sorted(libraries.subjects(RDF.type, rdf_type), key=str)
        if libraries.value(subject, DCTERMS.source) is None
        and libraries.value(subject, PAIR.derivedFrom) is None
    ]
    assert not missing_source, (
        f"{len(missing_source)} entries without dct:source or pair:derivedFrom: "
        + ", ".join(missing_source)
    )


def test_derived_from_points_at_an_entity_never_at_a_document(libraries) -> None:
    """Pointed at a URL it repeats dct:source, and "which motifs came from this
    design pattern?" stops being answerable - what 23 references to one Fowler
    article URL cost."""
    offenders = [
        f"{subject} derivedFrom {origin}"
        for rdf_type in (PAIR.GraphMotif, PAIR.RiskPattern)
        for subject in sorted(libraries.subjects(RDF.type, rdf_type), key=str)
        for origin in libraries.objects(subject, PAIR.derivedFrom)
        if not str(origin).startswith(("http://w3id.org/airiskkg", "http://w3id.org/beam"))
    ]
    assert not offenders, (
        "pair:derivedFrom must name an entity (a taxonomy concept or a "
        "pair:DesignPatternCitation), not a document URL:\n" + "\n".join(offenders)
    )


def test_a_design_pattern_citation_stays_a_citation(libraries) -> None:
    """A description here would start modelling the design pattern, which the
    method says it does not: structure belongs to the motif, consequences to the
    risk pattern, intent and applicability nowhere."""
    allowed = {RDF.type, RDFS.label, SKOS_NS.prefLabel, DCTERMS.source,
               DCTERMS.isPartOf, DCTERMS.bibliographicCitation}
    citations = set(libraries.subjects(RDF.type, PAIR.DesignPatternCitation))
    assert citations, "the citation layer is registered but loaded nothing"
    offenders = [
        f"{subject} carries {predicate}"
        for subject in sorted(citations, key=str)
        for predicate in libraries.predicates(subject, None)
        if predicate not in allowed
    ]
    assert not offenders, (
        "A pair:DesignPatternCitation may carry only a label and dct:source:\n"
        + "\n".join(sorted(set(offenders)))
    )
    unsourced = [str(c) for c in sorted(citations, key=str)
                 if libraries.value(c, DCTERMS.source) is None]
    assert not unsourced, "citations with no document to cite: " + ", ".join(unsourced)


def test_every_pattern_role_states_its_provenance(libraries) -> None:
    """Rule R6 reaches the role vocabulary too: every role traces to an origin."""
    mapping_predicates = (
        SKOS_NS.exactMatch,
        SKOS_NS.closeMatch,
        SKOS_NS.broadMatch,
        SKOS_NS.narrowMatch,
        SKOS_NS.relatedMatch,
    )

    def states_its_own(role) -> bool:
        return libraries.value(role, DCTERMS.source) is not None or any(
            libraries.value(role, predicate) for predicate in mapping_predicates
        )

    def traces_to_an_origin(role, seen=None) -> bool:
        seen = seen if seen is not None else set()
        if role in seen:
            return False  # a cycle grounds nothing
        seen.add(role)
        if states_its_own(role):
            return True
        return any(
            traces_to_an_origin(parent, seen)
            for parent in libraries.objects(role, PAIR.subRoleOf)
        )

    unsourced = [
        str(role).rsplit("#", 1)[-1]
        for role in sorted(libraries.subjects(RDF.type, PAIR.PatternRole), key=str)
        if not traces_to_an_origin(role)
    ]
    assert not unsourced, (
        f"{len(unsourced)} pattern roles trace to no origin: " + ", ".join(unsourced)
    )


def test_queries_check_process_typing_one_way(query_texts) -> None:
    """Process typing must not decide whether a motif matches."""
    offenders = []
    for fname, text in query_texts.items():
        _, _, where = text.partition("WHERE")
        for leaf in ("Infer", "Transform", "Train", "Generate", "Process"):
            for match in re.finditer(rf"\ba\s+beam:{leaf}\b", where):
                offenders.append(f"{fname}: bare 'a beam:{leaf}'")
    assert not offenders, (
        "Step class checks must use 'a/rdfs:subClassOf* beam:Process' so any "
        "process-family typing binds:\n" + "\n".join(sorted(set(offenders)))
    )


def test_process_typing_does_not_change_what_matches() -> None:
    """The unification, end to end: the same architecture typed with leaf classes
    and with beam:Process must produce identical matches."""
    from airiskkg.assessment_runner import run_assessment_from_text

    graph = """
    @prefix ex: <http://example.org/typing#> .
    @prefix beam: <http://w3id.org/beam/core#> .
    @prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
    ex:sys a beam:System ; beam:contain ex:plan, ex:act, ex:res .
    ex:plan a beam:%s ; pair:playsRole pair:PlanningStep ; beam:inform ex:act .
    ex:act a beam:%s ; pair:playsRole pair:ToolInvocationStep ; beam:produce ex:res .
    ex:res a beam:Data ; pair:playsRole pair:RetrievedContext .
    """

    def motifs(typing: tuple[str, str]) -> set[str]:
        result = run_assessment_from_text(graph % typing)
        return {
            str(m).rsplit("#", 1)[-1]
            for m in result.combined_graph.objects(None, PAIR.matchesMotif)
        }

    leaf = motifs(("Infer", "Transform"))
    generic = motifs(("Process", "Process"))
    assert leaf, "a leaf-typed agent must match the agentic motifs"
    assert leaf == generic, f"typing changed what matched: leaf={leaf} generic={generic}"


def test_specific_roles_are_subroles_of_the_role_their_motif_queries(libraries) -> None:
    """A precise role must sit under the general role its motif actually queries."""
    expected_parents = {
        # role -> the role its motif's pattern node requires
        PAIR.RewrittenQuery: PAIR.UserInput,
        PAIR.RerankedContext: PAIR.RetrievedContext,
        # A foundation LLM generates content by definition, so a graph naming
        # only the precise role must still satisfy the motifs that ask for a
        # generative model. Sitting under Model instead forced every example to
        # double-tag, and any that did not silently lost generation-side matches.
        PAIR.FoundationLLM: PAIR.GenerativeModel,
    }
    for role, parent in expected_parents.items():
        ancestors = set(libraries.transitive_objects(role, PAIR.subRoleOf))
        assert parent in ancestors, (
            f"{role} must be a sub-role of {parent}, otherwise tagging an element "
            f"with {role} alone cannot satisfy the motif that queries {parent}"
        )
