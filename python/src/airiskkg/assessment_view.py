"""Turn an AssessmentResult into JSON-friendly data for the web UI."""

from __future__ import annotations

from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, Namespace, URIRef

from airiskkg.assessment_runner import PAIR, AssessmentResult

_NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")
PROV = Namespace("http://www.w3.org/ns/prov#")
_MITCTRL_PREFIX = "http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#"
# skos:*Match predicates by which a pat:Control_* points at the MIT mitigation
# family it corresponds to (indicative bridge, not an audited SSSOM mapping).
_MIT_MAPPING_PREDS = (
    SKOS.relatedMatch,
    SKOS.closeMatch,
    SKOS.exactMatch,
    SKOS.broadMatch,
    SKOS.narrowMatch,
)

_SOURCE_PREFIXES = {
    "http://w3id.org/airiskkg/taxonomy/owasp-llm#": "OWASP LLM Top 10",
    "http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#": "IBM Risk Atlas",
    "http://w3id.org/airiskkg/taxonomy/mit-ai-risk#": "MIT AI Risk Repository",
    "http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#": "MIT AI Risk Control",
    "http://w3id.org/airiskkg/patterns#": "PAIR-AI Pattern Library",
}


def _local_name(uri: URIRef) -> str:
    text = str(uri)
    return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, SKOS.prefLabel) or graph.value(resource, RDFS.label)
    return str(value) if value else _local_name(resource)


def _definition(graph: Graph, resource: URIRef) -> str | None:
    value = (
        graph.value(resource, SKOS.definition)
        or graph.value(resource, DCTERMS.description)
    )
    return str(value) if value else None


def _source(uri: URIRef) -> str:
    text = str(uri)
    for prefix, label in _SOURCE_PREFIXES.items():
        if text.startswith(prefix):
            return label
    return "Other"


def _ref(graph: Graph, resource: URIRef) -> dict:
    return {
        "id": str(resource),
        "label": _label(graph, resource),
        "definition": _definition(graph, resource),
        "source": _source(resource),
    }


def _element_ref(graph: Graph, resource: URIRef) -> dict:
    return {"id": str(resource), "label": _label(graph, resource)}


_TECHNICAL = URIRef("http://w3id.org/airiskkg/pair-ai#TechnicalControl")
_NON_TECHNICAL = URIRef("http://w3id.org/airiskkg/pair-ai#NonTechnicalControl")


def _control_nature(graph: Graph, control: URIRef) -> str | None:
    """'technical' / 'non-technical' from pair:controlNature, or None if the
    control carries no classification (surfaced as 'unclassified' by the UI)."""
    nature = graph.value(control, PAIR.controlNature)
    if nature == _TECHNICAL:
        return "technical"
    if nature == _NON_TECHNICAL:
        return "non-technical"
    return None


def _mit_alignments(graph: Graph, control: URIRef) -> list[dict]:
    """The MIT mitigation family(ies) this actionable control corresponds to,
    via its skos:*Match bridge. Indicative provenance ('aligns with MIT: ...'),
    not an audited mapping - kept on the control, not mixed into the suggestion
    list itself."""
    families: set[URIRef] = set()
    for pred in _MIT_MAPPING_PREDS:
        for target in graph.objects(control, pred):
            if isinstance(target, URIRef) and str(target).startswith(_MITCTRL_PREFIX):
                families.add(target)
    return [_element_ref(graph, family) for family in sorted(families, key=str)]


def _control_ref(graph: Graph, control: URIRef) -> dict:
    """A suggested control, extended with its technical/non-technical nature, the
    motif(s) that can structurally realize it (candidate structural mitigations -
    the control stays the mitigation plan; the motif is how to realize it in the
    architecture), and the MIT mitigation family it aligns with (provenance)."""
    ref = _ref(graph, control)
    ref["nature"] = _control_nature(graph, control)
    realizing_motifs = sorted(graph.objects(control, PAIR.realizedByMotif), key=str)
    ref["realizedByMotifs"] = [_element_ref(graph, motif) for motif in realizing_motifs]
    ref["mitAlignments"] = _mit_alignments(graph, control)
    return ref


def _grounded_control_families(graph: Graph, taxonomy_entries: list[URIRef]) -> list[dict]:
    """The MIT control families the taxonomy grounds for this finding's risks
    (each risk taxonomy entry -> nexus:hasRelatedControl). This is the EVIDENCE
    layer - CSV-grounded / curated in taxonomy_mapping.ttl - surfaced distinctly
    from PAIR-AI's own actionable pat:Control_* suggestions, never mixed into
    them."""
    families: set[URIRef] = set()
    for entry in taxonomy_entries:
        families.update(graph.objects(entry, _NEXUS.hasRelatedControl))
    return [_ref(graph, family) for family in sorted(families, key=str)]


def _motif_ref(graph: Graph, motif: URIRef | None) -> dict | None:
    return _element_ref(graph, motif) if motif is not None else None


def _finding_view(graph: Graph, finding: URIRef) -> dict:
    motif = graph.value(finding, PAIR.generatedByMotif)
    mechanism = graph.value(finding, PAIR.hasDerivedMechanism)
    status = graph.value(finding, PAIR.findingStatus)
    description = graph.value(finding, DCTERMS.description)

    taxonomy_entries = sorted(
        graph.objects(finding, PAIR.hasCandidateRiskTaxonomyEntry), key=str
    )
    suggested_controls = sorted(graph.objects(finding, PAIR.hasSuggestedControl), key=str)
    evidence = sorted(graph.objects(finding, PAIR.hasEvidence), key=str)

    return {
        "id": str(finding),
        "label": _label(graph, finding),
        "description": str(description) if description else None,
        "motif": _motif_ref(graph, motif),
        "mechanism": _element_ref(graph, mechanism) if mechanism is not None else None,
        "status": str(status) if status else None,
        "taxonomyEntries": [_ref(graph, entry) for entry in taxonomy_entries],
        "suggestedControls": [_control_ref(graph, control) for control in suggested_controls],
        "groundedControlFamilies": _grounded_control_families(graph, taxonomy_entries),
        "evidence": [_element_ref(graph, element) for element in evidence],
    }


def _motif_match_view(graph: Graph, match: URIRef) -> dict:
    motif = graph.value(match, PAIR.matchesMotif)
    bindings = sorted(graph.objects(match, PAIR.hasNodeBinding), key=str)

    bound_elements = []
    node_ids: list[str] = []
    for binding in bindings:
        pattern_node = graph.value(binding, PAIR.bindsPatternNode)
        matched_element = graph.value(binding, PAIR.matchedElement)
        if pattern_node is None or matched_element is None:
            continue
        node_ids.append(str(matched_element))
        bound_elements.append(
            {
                "patternNode": _local_name(pattern_node),
                "element": _label(graph, matched_element),
                "elementId": str(matched_element),
            }
        )

    return {
        "id": str(match),
        "motif": _motif_ref(graph, motif),
        "boundElements": bound_elements,
        "nodeIds": sorted(set(node_ids)),
    }


def _findings_by_owasp_category(graph: Graph, findings: list[URIRef]) -> list[dict]:
    counts: dict[URIRef, int] = {}
    for finding in findings:
        categories = {
            entry
            for entry in graph.objects(finding, PAIR.hasCandidateRiskTaxonomyEntry)
            if _source(entry) == "OWASP LLM Top 10"
        }
        for category in categories:
            counts[category] = counts.get(category, 0) + 1

    return [
        {"id": str(category), "label": _label(graph, category), "count": count}
        for category, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    ]


def _derived_categories(result: AssessmentResult) -> list[dict]:
    """Every data category the engine inferred, with the hop that produced it.

    A derived fact the modeler cannot check is a fact they have to trust. The
    propagation rules record, per hop, which element the category came from and
    which step it passed through, so "the answer is sensitive" can be traced back
    to the annotation a human actually made.

    Each hop also says whether its source holds the category as an ANNOTATION
    rather than by derivation. Without that the consumer cannot tell where a
    trail ends, and in a graph with a memory loop there is no end to find: the
    category circulates, so following hops backwards runs in a circle and any
    "origin" picked from it is an artefact of traversal order rather than a fact
    about the system. Knowing which sources are annotated gives the walk a
    truthful place to stop - the element a human actually tagged."""
    graph = result.combined_graph
    # A category is annotated when the modeler stated it: present in the working
    # graph but not among the triples propagation added.
    inferred = {
        (subject, obj)
        for subject, obj in result.inferred_annotations.subject_objects(PAIR.containsDataCategory)
    }

    def is_annotated(element, category) -> bool:
        return (
            element is not None
            and (element, PAIR.containsDataCategory, category) in graph
            and (element, category) not in inferred
        )

    rows: list[dict] = []
    for element, derivation in graph.subject_objects(PROV.qualifiedDerivation):
        category = graph.value(derivation, PAIR.derivedCategory)
        if category is None:
            continue
        upstream = graph.value(derivation, PROV.entity)
        step = graph.value(derivation, PROV.hadActivity)
        rows.append(
            {
                "element": _ref(graph, element),
                "category": _ref(graph, category),
                "from": _ref(graph, upstream) if upstream is not None else None,
                "via": _ref(graph, step) if step is not None else None,
                "fromAnnotated": is_annotated(upstream, category),
            }
        )
    return sorted(
        rows,
        key=lambda row: (row["element"]["label"], row["category"]["label"], (row["from"] or {}).get("label", "")),
    )


def summarize_result(result: AssessmentResult) -> dict:
    findings = sorted(result.risk_findings.subjects(RDF.type, PAIR.RiskFinding), key=str)
    matches = sorted(result.motif_matches.subjects(RDF.type, PAIR.MotifMatch), key=str)
    derived = _derived_categories(result)

    return {
        "summary": {
            "riskFindingCount": len(findings),
            "motifMatchCount": len(matches),
            "derivedCategoryCount": len(derived),
            "findingsByOwaspCategory": _findings_by_owasp_category(result.combined_graph, findings),
        },
        "findings": [_finding_view(result.combined_graph, finding) for finding in findings],
        "motifMatches": [_motif_match_view(result.combined_graph, match) for match in matches],
        "derivedCategories": derived,
    }
