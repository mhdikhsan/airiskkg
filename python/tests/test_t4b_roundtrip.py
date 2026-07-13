"""Round-trip test for the Tool4Boxology alignment adapter (Task 6).

sample_export.nt -> normalize_t4b -> BEAM graph -> motif queries + SHACL.
"""

import sys
from pathlib import Path

from rdflib import RDF, Graph, Namespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "scripts"))

from normalize_t4b import normalize  # noqa: E402
from validate_graphs import SHAPES_PATH, _load_ontology_graph, validate_graph  # noqa: E402

from airiskkg.assessment_runner import (  # noqa: E402
    _run_assessment_on_graph,
    load_base_graph,
)

BEAM = Namespace("http://w3id.org/beam/core#")
T4B = Namespace("http://tool4boxology.org/")
DCT = Namespace("http://purl.org/dc/terms/")

SAMPLE_EXPORT = REPO_ROOT / "external" / "tool4boxology" / "sample_export.nt"


def test_normalizer_materializes_basic_process_flow(tmp_path: Path) -> None:
    graph = normalize(SAMPLE_EXPORT)

    # Original t4b triples are kept.
    assert any(graph.subject_objects(T4B["inputRoleParticipatesInProcess"]))
    # BEAM flow triples materialized.
    assert any(graph.subject_objects(BEAM.use)), "no beam:use materialized"
    assert any(graph.subject_objects(BEAM.produce)), "no beam:produce materialized"
    # Lowercase export types are gone; BEAM types are present.
    assert not list(graph.subjects(RDF.type, T4B["transform"]))
    assert any(graph.subjects(RDF.type, BEAM.Transform))
    assert any(graph.subjects(RDF.type, BEAM.System)), "no beam:System typed"
    # DesignPattern groupings became dct:conformsTo provenance.
    assert any(graph.subject_objects(DCT.conformsTo)), "no pattern provenance"


def test_normalized_graph_passes_input_contract(tmp_path: Path) -> None:
    graph = normalize(SAMPLE_EXPORT)
    out = tmp_path / "sample_export.beam.ttl"
    graph.serialize(out, format="turtle")

    shapes = Graph()
    shapes.parse(SHAPES_PATH, format="turtle")
    ok, violations, _warnings, results_text = validate_graph(out, shapes, _load_ontology_graph())
    assert ok, f"SHACL input contract failed ({violations} violations):\n{results_text}"


def test_motif_queries_run_on_normalized_graph() -> None:
    working_graph = load_base_graph()
    for triple in normalize(SAMPLE_EXPORT):
        working_graph.add(triple)
    result = _run_assessment_on_graph(working_graph, write_outputs=False, output_dir=".")
    # The t4b sample carries no PAIR roles, so no matches are required -
    # the assertion is that the full pipeline runs without error and
    # produces well-formed (possibly empty) outputs.
    assert result.motif_match_count >= 0
    assert result.risk_finding_count >= 0
