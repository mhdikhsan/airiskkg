from __future__ import annotations
from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, Namespace, URIRef
from airiskkg.assessment_runner import PAIR, AssessmentResult, applicable_controls
from airiskkg.knowledge_base import graph_fingerprint

_NEXUS = Namespace("http://w3id.org/airiskkg/taxonomy/nexus#")
PROV = Namespace("http://www.w3.org/ns/prov#")
_BP_NAME = Namespace("https://sBPMN.github.io/2.0/properties#").name
BEAM = Namespace("http://w3id.org/beam/core#")
_MITCTRL_PREFIX = "http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#"
_MIT_MAPPING_PREDS = (
    SKOS.relatedMatch,
    SKOS.closeMatch,
    SKOS.exactMatch,
    SKOS.broadMatch,
    SKOS.narrowMatch,
)

_SOURCE_PREFIXES = {
    "http://w3id.org/airiskkg/taxonomy/owasp-llm#": ("OWASP LLM Top 10", "OWASP LLM"),
    "http://w3id.org/airiskkg/taxonomy/owasp-asi#": ("OWASP Agentic Top 10", "OWASP ASI"),
    "http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#": ("IBM AI Risk Atlas", "IBM"),
    "http://w3id.org/airiskkg/taxonomy/mit-ai-risk#": ("MIT AI Risk Repository", "MIT"),
    "http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#": ("MIT AI Risk Control", "MIT"),
    "http://w3id.org/airiskkg/taxonomy/nist-genai#": ("NIST AI 600-1", "NIST"),
    "http://w3id.org/airiskkg/patterns#": ("PAIR-AI Pattern Library", "PAIR-AI"),
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
    return _source_pair(uri)[0]


def _source_pair(uri: URIRef) -> tuple[str, str]:
    text = str(uri)
    for prefix, names in _SOURCE_PREFIXES.items():
        if text.startswith(prefix):
            return names
    return ("Other", "Other")


def _ref(graph: Graph, resource: URIRef) -> dict:
    return {
        "id": str(resource),
        "label": _label(graph, resource),
        "definition": _definition(graph, resource),
        "source": _source(resource),
        "sourceShort": _source_pair(resource)[1],
    }


def _element_ref(graph: Graph, resource: URIRef) -> dict:
    return {"id": str(resource), "label": _label(graph, resource)}


_TECHNICAL = URIRef("http://w3id.org/airiskkg/pair-ai#TechnicalControl")
_NON_TECHNICAL = URIRef("http://w3id.org/airiskkg/pair-ai#NonTechnicalControl")


def _control_nature(graph: Graph, control: URIRef) -> str | None:
    nature = graph.value(control, PAIR.controlNature)
    if nature == _TECHNICAL:
        return "technical"
    if nature == _NON_TECHNICAL:
        return "non-technical"
    return None


def _mit_alignments(graph: Graph, control: URIRef) -> list[dict]:
    families: set[URIRef] = set()
    for pred in _MIT_MAPPING_PREDS:
        for target in graph.objects(control, pred):
            if isinstance(target, URIRef) and str(target).startswith(_MITCTRL_PREFIX):
                families.add(target)
    return [_element_ref(graph, family) for family in sorted(families, key=str)]


def _control_ref(graph: Graph, control: URIRef, applicable: set[URIRef]) -> dict:
    ref = _ref(graph, control)
    ref["nature"] = _control_nature(graph, control)
    ref["applicable"] = control in applicable
    realizing_motifs = sorted(graph.objects(control, PAIR.realizedByMotif), key=str)
    ref["realizedByMotifs"] = [_element_ref(graph, motif) for motif in realizing_motifs]
    ref["mitAlignments"] = _mit_alignments(graph, control)
    return ref


def _grounded_control_families(graph: Graph, taxonomy_entries: list[URIRef]) -> list[dict]:
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
    applicable = applicable_controls(graph, finding)
    evidence = sorted(graph.objects(finding, PAIR.hasEvidence), key=str)

    return {
        "id": str(finding),
        "label": _label(graph, finding),
        "description": str(description) if description else None,
        "motif": _motif_ref(graph, motif),
        "mechanism": _element_ref(graph, mechanism) if mechanism is not None else None,
        "status": str(status) if status else None,
        "taxonomyEntries": [_ref(graph, entry) for entry in taxonomy_entries],
        "suggestedControls": [_control_ref(graph, c, applicable) for c in suggested_controls],
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
    graph = result.combined_graph
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


def _findings_by_activity(result: AssessmentResult, findings: list) -> list[dict]:
    system_of_element: dict = {}
    for system in result.working_graph.subjects(RDF.type, BEAM.System):
        for predicate in (BEAM.hasProcess, BEAM.hasResource, BEAM.contain):
            for element in result.working_graph.objects(system, predicate):
                system_of_element.setdefault(element, set()).add(system)

    rows = []
    for activity in result.working_graph.subjects(PAIR.refinedBy, None):
        systems = set(result.working_graph.objects(activity, PAIR.refinedBy))
        attributed = []
        for finding in findings:
            evidence = set(result.risk_findings.objects(finding, PAIR.hasEvidence))
            if any(system_of_element.get(element, set()) & systems for element in evidence):
                attributed.append(finding)
        name = result.working_graph.value(activity, _BP_NAME) or result.working_graph.value(
            activity, RDFS.label
        )
        rows.append(
            {
                "id": str(activity),
                "label": str(name) if name else str(activity).rsplit("#", 1)[-1],
                "systems": [str(s) for s in sorted(systems, key=str)],
                "findings": len(attributed),
                "items": sorted(
                    (
                        {
                            "id": str(finding),
                            "label": _label(result.combined_graph, finding),
                            "status": str(result.risk_findings.value(finding, PAIR.findingStatus) or ""),
                        }
                        for finding in attributed
                    ),
                    key=lambda row: row["label"],
                ),
            }
        )
    return sorted(rows, key=lambda row: (-row["findings"], row["label"]))


def _run_view(result: AssessmentResult, architecture: Graph | None) -> dict:
    view: dict = {}
    if architecture is not None:
        view["inputFingerprint"] = graph_fingerprint(architecture)
    if result.version is not None:
        view["knowledgeBase"] = {
            "fingerprint": result.version.short,
            "revision": (result.version.revision or "")[:7] or None,
            "dirty": result.version.dirty,
            "motifs": result.version.motifs,
            "riskPatterns": result.version.risk_patterns,
        }
    return view


def summarize_result(result: AssessmentResult, *, architecture: Graph | None = None) -> dict:
    findings = sorted(result.risk_findings.subjects(RDF.type, PAIR.RiskFinding), key=str)
    matches = sorted(result.motif_matches.subjects(RDF.type, PAIR.MotifMatch), key=str)
    derived = _derived_categories(result)
    derived_facts = {(row["element"]["id"], row["category"]["id"]) for row in derived}

    return {
        "summary": {
            "riskFindingCount": len(findings),
            "motifMatchCount": len(matches),
            "derivedCategoryCount": len(derived_facts),
            "findingsByOwaspCategory": _findings_by_owasp_category(result.combined_graph, findings),
        },
        "findings": [_finding_view(result.combined_graph, finding) for finding in findings],
        "motifMatches": [_motif_match_view(result.combined_graph, match) for match in matches],
        "derivedCategories": derived,
        "run": _run_view(result, architecture),
        "findingsByActivity": _findings_by_activity(result, findings),
    }
