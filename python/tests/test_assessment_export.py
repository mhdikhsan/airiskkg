"""The assessment export: is the exported file usable on its own?

An export is only worth having if someone who receives it, with no access to
this repository, can read it. That means three properties, and each is a test
below:

  1. It carries the evidence. Findings reference elements by URI, so the
     architecture graph has to travel with them or the evidence is unresolvable.
  2. It does NOT carry the library. The motif, risk-pattern, and taxonomy layers
     are the reusable knowledge resource, not this run's output; bundling them
     would republish the whole corpus into every export.
  3. It says where it came from. Findings without provenance read as standing
     facts about a system rather than the output of one analysis of one graph,
     which is exactly the reading candidate framing rejects.
"""

from __future__ import annotations

from rdflib import DCTERMS, RDF, RDFS, Graph, Namespace, URIRef

from airiskkg.assessment_export import (
    EXPORT_FORMATS,
    OUTPUT_CONTRACT,
    PAIR_AI_AGENT,
    build_export,
)
from airiskkg.assessment_runner import PAIR, run_assessment_from_text
from airiskkg.paths import EXAMPLE_DIR, SHACL_DIR
from conftest import ONYX_NS, example_path  # noqa: E402

PROV = Namespace("http://www.w3.org/ns/prov#")
BEAM = Namespace("http://w3id.org/beam/core#")

GRAPH = """
@prefix ex: <http://example.org/export#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:sys a beam:System ; rdfs:label "Export probe" ;
    beam:contain ex:query, ex:gen, ex:llm, ex:answer .
ex:query a beam:Data ; rdfs:label "Query" ; pair:playsRole pair:PublicUserInput .
ex:llm a beam:StatisticalModel ; rdfs:label "LLM" ;
    pair:playsRole pair:GenerativeModel, pair:FoundationLLM .
ex:gen a beam:Infer, beam:Process ; rdfs:label "Generate" ;
    pair:playsRole pair:GenerationStep ;
    beam:use ex:query, ex:llm ; beam:produce ex:answer .
ex:answer a beam:Data ; rdfs:label "Answer" ; pair:playsRole pair:UserFacingOutput .
"""


def _export(turtle: str = GRAPH):
    result = run_assessment_from_text(turtle)
    architecture = Graph().parse(data=turtle, format="turtle")
    return result, build_export(result, architecture, source_label="probe")


def test_export_carries_the_evidence_it_references() -> None:
    """Every element a finding cites as evidence must be described in the file."""
    _result, export = _export()
    findings = set(export.graph.subjects(RDF.type, PAIR.RiskFinding))
    assert findings, "the probe graph should produce findings"

    dangling = [
        str(evidence)
        for finding in findings
        for evidence in export.graph.objects(finding, PAIR.hasEvidence)
        if (evidence, RDF.type, None) not in export.graph
    ]
    assert not dangling, "evidence with no description in the export: " + ", ".join(dangling)


def test_export_does_not_republish_the_library() -> None:
    """The library is referenced by URI, never bundled.

    Without this the export balloons from ~1k to ~7k triples and every download
    ships the motif, risk-pattern, and taxonomy layers again."""
    _result, export = _export()
    assert not set(export.graph.subjects(RDF.type, PAIR.GraphMotif)), "motif library leaked"
    assert not set(export.graph.subjects(RDF.type, PAIR.RiskPattern)), "risk pattern library leaked"
    assert not set(export.graph.subjects(RDF.type, PAIR.PatternRole)), "role vocabulary leaked"


def test_export_records_the_run_that_produced_it() -> None:
    """PROV-O, so a consumer needs no PAIR-AI vocabulary to see what this is."""
    _result, export = _export()
    graph, activity = export.graph, export.activity

    assert (activity, RDF.type, PROV.Activity) in graph
    assert (activity, PROV.wasAssociatedWith, PAIR_AI_AGENT) in graph
    assert (PAIR_AI_AGENT, RDF.type, PROV.SoftwareAgent) in graph
    assert graph.value(activity, PROV.endedAtTime) is not None
    assert (activity, DCTERMS.conformsTo, OUTPUT_CONTRACT) in graph

    systems = set(graph.subjects(RDF.type, BEAM.System))
    assert systems, "the probe declares a system"
    for system in systems:
        assert (activity, PROV.used, system) in graph, "the assessed system must be prov:used"

    for rdf_type in (PAIR.RiskFinding, PAIR.MotifMatch):
        subjects = set(graph.subjects(RDF.type, rdf_type))
        assert subjects, f"expected some {rdf_type}"
        for subject in subjects:
            assert (subject, PROV.wasGeneratedBy, activity) in graph


def test_export_satisfies_the_assessment_output_contract() -> None:
    """The export advertises dct:conformsTo; this checks the claim is true."""
    from pyshacl import validate

    _result, export = _export()
    shapes = Graph().parse(SHACL_DIR / "assessment_output_contract.ttl", format="turtle")
    conforms, _results, text = validate(
        data_graph=export.graph, shacl_graph=shapes, advanced=True, inference="none"
    )
    assert conforms, f"export violates the output contract it claims to conform to:\n{text}"


def test_every_advertised_format_round_trips() -> None:
    """A format we offer in the UI must parse back to the same graph."""
    _result, export = _export()
    for export_format in EXPORT_FORMATS:
        text = export.serialize(export_format)
        parse_format = "nt" if export_format == "nt" else export_format
        reparsed = Graph().parse(data=text, format=parse_format)
        assert len(reparsed) == len(export.graph), f"{export_format} lost triples"


def test_unknown_format_is_rejected() -> None:
    _result, export = _export()
    try:
        export.serialize("pdf")
    except ValueError as error:
        assert "pdf" in str(error)
    else:
        raise AssertionError("an unsupported format must raise")


def test_export_without_the_parsed_architecture_still_excludes_the_library() -> None:
    """The convenience path recovers the architecture by subtracting the base
    graph. If that subtraction regressed, the export would silently include the
    entire library - the exact failure this fallback is most likely to hide."""
    result = run_assessment_from_text(GRAPH)
    recovered = build_export(result, None)
    assert not set(recovered.graph.subjects(RDF.type, PAIR.GraphMotif))
    assert len(recovered.graph) < len(result.working_graph) / 2


def test_bundled_example_exports_and_stays_small() -> None:
    """End to end on a real example, and a guard on the size claim."""
    turtle = example_path(ONYX_NS).read_text(encoding="utf-8")
    result, export = _export(turtle)
    assert result.risk_finding_count > 0
    assert len(export.graph) < len(result.working_graph) / 2, (
        "export should be a fraction of the working graph, not a dump of it"
    )
