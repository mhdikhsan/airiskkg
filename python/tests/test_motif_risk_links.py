"""Every link from a risk pattern to a motif is proven on the motif itself.

A motif carries a risk pattern when inserting it alone raises the pattern
through its own match. Where the risk depends on what the elements are about
(public input, personal data, a hosted model), the link names that context in
`workbench.risk_context`, and the motif inserted with it raises the pattern. A
link that is neither is a promise the library does not keep: the reader picks
the risk, adds the motif, runs the assessment, and nothing comes back.
"""

from __future__ import annotations

import pytest
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from airiskkg.assessment_runner import PAIR, load_base_graph, run_assessment_from_text
from airiskkg.workbench.risk_context import LINK_CONTEXT, link_context, template_in_context
from airiskkg.workbench.templates import motif_templates
from airiskkg.workbench.terms import PROCESS_CLASS_NAMES

BEAM = Namespace("http://w3id.org/beam/core#")
PAT = Namespace("http://w3id.org/airiskkg/patterns#")
LOCAL = Namespace("http://example.org/link-probe#")


def _built(template: dict) -> str:
    # The same construction /api/graph-edit add-motif performs.
    data = Graph()
    system = LOCAL["system"]
    data.add((system, RDF.type, BEAM.System))
    data.add((system, RDFS.label, Literal("link probe")))
    key_to_uri = {}
    for index, node in enumerate(template["nodes"], start=1):
        uri = LOCAL[f"e{index}"]
        key_to_uri[node["key"]] = uri
        is_process = node["cls"] in PROCESS_CLASS_NAMES
        data.add((uri, RDF.type, BEAM[node["cls"]]))
        if is_process and node["cls"] != "Process":
            data.add((uri, RDF.type, BEAM.Process))
        data.add((uri, RDFS.label, Literal(node["label"])))
        for role in node.get("roles") or []:
            data.add((uri, PAIR.playsRole, PAIR[role]))
        for category in node.get("cats") or []:
            data.add((uri, PAIR.containsDataCategory, PAIR[category]))
        data.add((system, BEAM.hasProcess if is_process else BEAM.hasResource, uri))
    for source, edge, target in template["edges"]:
        data.add((key_to_uri[source], BEAM[edge], key_to_uri[target]))
    return data.serialize(format="turtle")


def _raised_through(template: dict) -> set[tuple[str, str]]:
    findings = run_assessment_from_text(_built(template)).risk_findings
    return {
        (str(findings.value(f, PAIR.generatedByRiskPattern)).rsplit("#", 1)[-1],
         str(findings.value(f, PAIR.generatedByMotif)).rsplit("#", 1)[-1])
        for f in findings.subjects(RDF.type, PAIR.RiskFinding)
    }


def _declared() -> list[tuple[str, str]]:
    graph = load_base_graph()
    return sorted(
        (str(pattern).rsplit("#", 1)[-1], str(motif).rsplit("#", 1)[-1])
        for pattern, motif in graph.subject_objects(PAIR.hasMotif)
    )


@pytest.fixture(scope="module")
def bare() -> dict[str, set[tuple[str, str]]]:
    return {motif: _raised_through(template) for motif, template in motif_templates().items()}


def test_every_motif_risk_link_fires(bare) -> None:
    """Carried links fire on the bare motif; the rest fire once their context is added."""
    offenders = []
    for pattern, motif in _declared():
        if link_context(pattern, motif) is None:
            if (pattern, motif) not in bare[motif]:
                offenders.append(f"{pattern} via {motif}: not raised by the motif alone, and no context is named")
        elif (pattern, motif) not in _raised_through(template_in_context(motif, pattern)):
            offenders.append(f"{pattern} via {motif}: not raised even with its context")
    assert not offenders, "\n".join(offenders)


def test_a_context_is_named_only_where_the_motif_needs_it(bare) -> None:
    """Naming a context for a link the motif already carries would tell the reader
    the risk depends on something it does not."""
    needless = [
        f"{pattern} via {motif}"
        for (pattern, motif) in LINK_CONTEXT
        if (pattern, motif) in bare[motif]
    ]
    assert not needless, "context named for links the motif carries alone:\n" + "\n".join(needless)


def test_every_named_context_belongs_to_a_declared_link() -> None:
    declared = set(_declared())
    stale = sorted(f"{pattern} via {motif}" for pattern, motif in LINK_CONTEXT if (pattern, motif) not in declared)
    assert not stale, "context for links the library does not declare:\n" + "\n".join(stale)


def test_a_context_marks_only_elements_the_motif_has() -> None:
    templates = motif_templates()
    offenders = []
    for (pattern, motif), context in LINK_CONTEXT.items():
        keys = {node["key"] for node in templates[motif]["nodes"]} | {n["key"] for n in context["nodes"]}
        offenders += [f"{pattern} via {motif}: {key}" for key, _, _ in context["marks"] if key not in keys]
        offenders += [f"{pattern} via {motif}: {s}->{t}" for s, _, t in context["edges"] if s not in keys or t not in keys]
        if not context["says"]:
            offenders.append(f"{pattern} via {motif}: the context says nothing a reader can read")
    assert not offenders, "\n".join(offenders)


def test_inserting_from_a_risk_page_adds_the_context() -> None:
    """The add-motif edit applies a link's context when it is given the risk pattern."""
    from airiskkg.webapp.app import create_app

    pattern, motif = next(iter(sorted(LINK_CONTEXT)))
    empty = "@prefix beam: <http://w3id.org/beam/core#> .\n"  # what the canvas sends for a new graph
    app = create_app()
    with app.test_client() as http:
        plain = http.post("/api/graph-edit", json={"ttl": empty, "op": "add-motif", "motif": motif}).get_json()
        framed = http.post("/api/graph-edit", json={
            "ttl": empty, "op": "add-motif", "motif": motif, "riskPattern": str(PAT[pattern]),
        }).get_json()
    assert (pattern, motif) not in _raised_from_ttl(plain["ttl"])
    assert (pattern, motif) in _raised_from_ttl(framed["ttl"])


def _raised_from_ttl(ttl: str) -> set[tuple[str, str]]:
    findings = run_assessment_from_text(ttl).risk_findings
    return {
        (str(findings.value(f, PAIR.generatedByRiskPattern)).rsplit("#", 1)[-1],
         str(findings.value(f, PAIR.generatedByMotif)).rsplit("#", 1)[-1])
        for f in findings.subjects(RDF.type, PAIR.RiskFinding)
    }


def test_the_library_says_which_links_need_context() -> None:
    from airiskkg.workbench.library import library_catalogue

    for entry in library_catalogue()["riskPatterns"]:
        assert set(entry["motifContext"]) == set(entry["motifs"]), entry["id"]
        for motif, says in entry["motifContext"].items():
            context = link_context(entry["id"], motif)
            assert says == (context["says"] if context else []), (entry["id"], motif)
