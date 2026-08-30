"""The stamp that ties a set of results to the library that produced them."""

import json

from airiskkg.assessment_runner import (
    knowledge_base_fingerprint,
    load_base_graph,
    reload_knowledge_base,
    run_assessment,
)
from airiskkg.knowledge_base import (
    _digest,
    knowledge_base_version,
    ontology_files,
    registered_query_files,
)
from conftest import GRAPH_RAG_NS, example_path


def test_the_fingerprint_is_stable_across_calls():
    """Nothing about identifying a library may vary between two reads of it."""
    assert knowledge_base_fingerprint().fingerprint == knowledge_base_fingerprint().fingerprint


def test_the_fingerprint_survives_a_reload():
    """The cache is dropped and recomputed, not merely re-handed."""
    before = knowledge_base_fingerprint().fingerprint
    reload_knowledge_base()
    assert knowledge_base_fingerprint().fingerprint == before


def test_registered_queries_are_fingerprinted_not_only_the_ontology():
    """A risk query rewritten in place changes every finding while leaving the
    ontology untouched. If the stamp missed .rq files it would report the two
    libraries as one, which is the confusion it exists to prevent."""
    queries = registered_query_files(load_base_graph())
    names = {path.name for path in queries}

    assert "prompt_injection.rq" in names
    assert "rag.rq" in names
    assert all(path.suffix == ".rq" for path in queries)
    assert len(queries) > 40


def test_ontology_and_query_sets_do_not_overlap_and_all_exist():
    files = [*ontology_files(), *registered_query_files(load_base_graph())]

    assert all(path.is_file() for path in files)
    assert len(files) == len(set(files))


def test_line_endings_do_not_change_the_fingerprint(tmp_path):
    """This repository is edited on Windows and its .ttl and .rq files churn
    between CRLF and LF on checkout. Hashing raw bytes would report the same
    commit as two different libraries depending on which machine ran it, and an
    evaluation comparing a laptop run against CI would see a difference that is
    not there."""
    # One path, rewritten - the digest mixes in each file's name, so comparing
    # two differently-named files would prove nothing about line endings.
    path = tmp_path / "a.ttl"

    path.write_bytes(b"# one\n# two\n")
    with_lf = _digest([path])
    path.write_bytes(b"# one\r\n# two\r\n")
    with_crlf = _digest([path])

    assert with_lf == with_crlf


def test_a_changed_file_changes_the_fingerprint(tmp_path):
    first = tmp_path / "a.ttl"
    first.write_bytes(b"# one\n")
    before = _digest([first])
    first.write_bytes(b"# two\n")

    assert _digest([first]) != before


def test_the_counts_are_read_off_the_graph():
    """Stamped rather than kept in a constant, for the reason the project already
    records about its catalogue: every hand-maintained figure but one had drifted
    before anyone noticed."""
    version = knowledge_base_version(load_base_graph())

    assert version.motifs > 0
    assert version.risk_patterns > 0
    assert version.pattern_roles > 0
    assert version.ontology_files == len(ontology_files())


def test_a_run_carries_and_records_its_version(tmp_path):
    """The point of the whole thing: a set of results on disk says what produced
    it, without anyone having to remember."""
    result = run_assessment(example_path(GRAPH_RAG_NS), write_outputs=True, output_dir=tmp_path)

    assert result.version is not None
    assert result.output_dir is not None

    recorded = json.loads((result.output_dir / "knowledge_base_version.json").read_text(encoding="utf-8"))
    assert recorded["fingerprint"] == result.version.fingerprint
    assert recorded["short"] == result.version.fingerprint[:12]
    assert recorded["risk_patterns"] == result.version.risk_patterns


def test_the_version_is_json_serializable_without_coaxing():
    """It has to survive being written next to a run, so no value may be a Path,
    a URIRef, or anything else that needs a custom encoder."""
    json.dumps(knowledge_base_fingerprint().as_dict())
