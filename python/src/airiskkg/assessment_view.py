"""Turn an :class:`AssessmentResult` RDF graph into plain JSON-serializable data.

The assessment engine speaks RDF/Turtle. The web UI speaks JSON. This module is the
bridge: it resolves human-readable labels, groups taxonomy references by source, and
flattens each risk finding into a dictionary that a frontend can render directly.
"""

from __future__ import annotations

from rdflib import DCTERMS, RDF, RDFS, SKOS, Graph, URIRef

from airiskkg.assessment_runner import AssessmentResult, PAIR

# Human-friendly names for the taxonomy/source namespaces a finding can reference.
TAXONOMY_SOURCES: list[tuple[str, str]] = [
    ("http://w3id.org/airiskkg/taxonomy/owasp-llm#", "OWASP LLM Top 10"),
    ("http://w3id.org/airiskkg/taxonomy/mit-ai-risk-control#", "MIT AI Risk Controls"),
    ("http://w3id.org/airiskkg/taxonomy/mit-ai-risk#", "MIT AI Risk Repository"),
    ("http://w3id.org/airiskkg/taxonomy/ibm-risk-atlas#", "IBM Risk Atlas"),
    ("http://w3id.org/airiskkg/taxonomy/nexus#", "AI Atlas Nexus"),
    ("http://w3id.org/airiskkg/patterns#", "PAIR-AI Pattern Library"),
    ("http://w3id.org/beam/risk#", "BEAM Risk"),
]


def _local_name(uri: str) -> str:
    """Best-effort readable fallback when a resource has no label."""
    fragment = uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return fragment.replace("-", " ").replace("_", " ").strip() or uri


def _label(graph: Graph, resource: URIRef) -> str:
    value = graph.value(resource, RDFS.label) or graph.value(resource, SKOS.prefLabel)
    return str(value) if value else _local_name(str(resource))


def _source_name(uri: str) -> str:
    for namespace, name in TAXONOMY_SOURCES:
        if uri.startswith(namespace):
            return name
    return "Other"


def _ref(graph: Graph, resource: URIRef) -> dict[str, str]:
    return {
        "id": str(resource),
        "label": _label(graph, resource),
        "source": _source_name(str(resource)),
    }


def _definition(graph: Graph, resource: URIRef) -> str | None:
    value = (
        graph.value(resource, SKOS.definition)
        or graph.value(resource, DCTERMS.description)
        or graph.value(resource, RDFS.comment)
    )
    return str(value) if value else None


def _refs(graph: Graph, finding: URIRef, predicate: URIRef) -> list[dict[str, str]]:
    refs = [_ref(graph, obj) for obj in graph.objects(finding, predicate) if isinstance(obj, URIRef)]
    return sorted(refs, key=lambda item: (item["source"], item["label"].lower()))


def summarize_finding(graph: Graph, finding: URIRef) -> dict:
    """Flatten a single ``pair:RiskFinding`` into a render-ready dictionary."""
    mechanism = graph.value(finding, PAIR.hasInterpretedMechanism)
    motif = graph.value(finding, PAIR.generatedByMotif)

    taxonomy = _refs(graph, finding, PAIR.hasCandidateRiskTaxonomyEntry)
    # Attach a short definition to each taxonomy entry where one is available.
    for entry in taxonomy:
        definition = _definition(graph, URIRef(entry["id"]))
        if definition:
            entry["definition"] = definition

    return {
        "id": str(finding),
        "label": _label(graph, finding),
        "description": str(graph.value(finding, DCTERMS.description) or ""),
        "status": str(graph.value(finding, PAIR.findingStatus) or ""),
        "motif": _ref(graph, motif) if isinstance(motif, URIRef) else None,
        "mechanism": _ref(graph, mechanism) if isinstance(mechanism, URIRef) else None,
        "taxonomyEntries": taxonomy,
        "evidence": _refs(graph, finding, PAIR.hasEvidenceElement),
        "satisfiedConditions": _refs(graph, finding, PAIR.hasSatisfiedCondition),
        "suggestedControls": _refs(graph, finding, PAIR.hasSuggestedControl),
    }


def summarize_motif_match(graph: Graph, match: URIRef) -> dict:
    motif = graph.value(match, PAIR.matchesMotif)
    bound_elements: list[dict[str, str]] = []
    for binding in graph.objects(match, PAIR.hasNodeBinding):
        element = graph.value(binding, PAIR.matchedElement)
        pattern_node = graph.value(binding, PAIR.bindsPatternNode)
        if isinstance(element, URIRef):
            bound_elements.append(
                {
                    "patternNode": _label(graph, pattern_node) if isinstance(pattern_node, URIRef) else "",
                    "element": _label(graph, element),
                    "elementId": str(element),
                }
            )
    bound_elements.sort(key=lambda item: item["patternNode"].lower())
    return {
        "id": str(match),
        "motif": _ref(graph, motif) if isinstance(motif, URIRef) else None,
        "boundElements": bound_elements,
    }


def summarize_result(result: AssessmentResult) -> dict:
    """Produce the full JSON payload consumed by the web UI."""
    findings_graph = result.risk_findings
    # The findings graph only carries finding triples; labels for taxonomy entries,
    # controls and evidence elements live in the combined graph.
    combined = result.combined_graph

    findings = [
        summarize_finding(combined, finding)
        for finding in findings_graph.subjects(RDF.type, PAIR.RiskFinding)
    ]
    findings.sort(key=lambda item: (item["label"].lower(), item["id"]))

    matches = [
        summarize_motif_match(combined, match)
        for match in result.motif_matches.subjects(RDF.type, PAIR.MotifMatch)
    ]
    matches.sort(key=lambda item: ((item["motif"] or {}).get("label", "").lower(), item["id"]))

    # Roll findings up by the OWASP-style risk category they most relate to so the UI
    # can show a severity-free "how many findings per risk area" overview.
    by_taxonomy: dict[str, int] = {}
    for finding in findings:
        for entry in finding["taxonomyEntries"]:
            if entry["source"] == "OWASP LLM Top 10":
                by_taxonomy[entry["label"]] = by_taxonomy.get(entry["label"], 0) + 1

    return {
        "summary": {
            "motifMatchCount": result.motif_match_count,
            "riskFindingCount": result.risk_finding_count,
            "findingsByOwaspCategory": [
                {"label": label, "count": count}
                for label, count in sorted(by_taxonomy.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
        },
        "findings": findings,
        "motifMatches": matches,
    }
