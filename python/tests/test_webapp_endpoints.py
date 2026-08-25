"""Endpoint tests for the workbench webapp (live preview + validation)."""

import re

import pytest

flask = pytest.importorskip("flask")

from airiskkg.paths import EXAMPLE_DIR, REPO_ROOT  # noqa: E402
from airiskkg.webapp.app import create_app  # noqa: E402
from conftest import ONYX_NS, example_path  # noqa: E402


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_graph_endpoint_returns_nodes_and_edges(client) -> None:
    ttl = example_path(ONYX_NS).read_text(encoding="utf-8")
    response = client.post("/api/graph", json={"ttl": ttl})
    assert response.status_code == 200
    data = response.get_json()
    assert data["stats"]["nodes"] > 0
    assert data["stats"]["edges"] > 0
    assert data["systems"], "system entry expected"
    kinds = {node["kind"] for node in data["nodes"]}
    assert {"process", "data", "model"} <= kinds
    node_ids = {node["id"] for node in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids


def test_graph_endpoint_use_edges_point_into_process(client) -> None:
    ttl = """
    @prefix beam: <http://w3id.org/beam/core#> .
    @prefix ex: <http://example.org/> .
    ex:S a beam:System .
    ex:Step a beam:Infer ; beam:use ex:In ; beam:produce ex:Out .
    ex:In a beam:Data . ex:Out a beam:Data .
    """
    data = client.post("/api/graph", json={"ttl": ttl}).get_json()
    edges = {(e["kind"], e["source"].split("/")[-1], e["target"].split("/")[-1]) for e in data["edges"]}
    assert ("use", "In", "Step") in edges       # drawn resource -> process
    assert ("produce", "Step", "Out") in edges  # drawn process -> resource


def test_graph_endpoint_reports_parse_error(client) -> None:
    response = client.post("/api/graph", json={"ttl": "@prefix broken <"})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_graph_endpoint_empty_ttl_is_empty_graph(client) -> None:
    response = client.post("/api/graph", json={"ttl": "   "})
    assert response.status_code == 200
    assert response.get_json()["stats"] == {"nodes": 0, "edges": 0}


def test_validate_endpoint_reports_contract(client) -> None:
    ttl = example_path(ONYX_NS).read_text(encoding="utf-8")
    response = client.post("/api/validate", json={"ttl": ttl})
    assert response.status_code == 200
    report = response.get_json()
    assert report["conforms"] is True
    assert report["violations"] == []

    broken = """
    @prefix beam: <http://w3id.org/beam/core#> .
    @prefix ex: <http://example.org/> .
    ex:Step a beam:Process .
    """
    report = client.post("/api/validate", json={"ttl": broken}).get_json()
    assert report["conforms"] is False
    assert report["violations"]


def test_export_endpoint_returns_a_downloadable_graph(client) -> None:
    """The export must arrive as a file, not JSON, and carry the run counts so
    the UI can report what it downloaded without re-running the assessment."""
    from rdflib import Graph

    ttl = example_path(ONYX_NS).read_text(encoding="utf-8")
    response = client.post(
        "/api/export/assessment", json={"ttl": ttl, "format": "turtle"}
    )
    assert response.status_code == 200
    assert response.mimetype == "text/turtle"
    assert "attachment" in response.headers["Content-Disposition"]
    assert int(response.headers["X-PAIR-AI-Findings"]) > 0

    parsed = Graph().parse(data=response.get_data(as_text=True), format="turtle")
    assert len(parsed) > 0


def test_export_endpoint_rejects_bad_input(client) -> None:
    """Errors stay JSON so the UI can show the message rather than download it."""
    empty = client.post("/api/export/assessment", json={"ttl": ""})
    assert empty.status_code == 400
    assert "error" in empty.get_json()

    # Inline, so the check does not depend on which examples are bundled.
    minimal = """
    @prefix ex: <http://example.org/x#> .
    @prefix beam: <http://w3id.org/beam/core#> .
    ex:sys a beam:System .
    """
    bad_format = client.post(
        "/api/export/assessment", json={"ttl": minimal, "format": "pdf"}
    )
    assert bad_format.status_code == 400
    assert "pdf" in bad_format.get_json()["error"]


def test_validate_endpoint_returns_annotation_guidance_hints(client) -> None:
    """The guidance shapes must actually reach the endpoint's output.

    They were loaded but inert once before: the shapes walk pair:subRoleOf*
    inside sh:sparql constraints, which only see the data graph, so passing the
    role hierarchy as pyshacl's ont_graph left every Info hint unproduced. The
    file parsed, the endpoint answered 200, and the hints were simply absent -
    nothing failed.

    A vector store no retrieval step uses is the trigger: annotated correctly,
    but no motif can bind it."""
    ttl = """
    @prefix ex: <http://example.org/hint#> .
    @prefix beam: <http://w3id.org/beam/core#> .
    @prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
    ex:sys a beam:System ; beam:contain ex:store, ex:step .
    ex:store a beam:Data ; pair:playsRole pair:VectorStore .
    ex:step a beam:Process ; pair:playsRole pair:ProcessingStep ; beam:produce ex:store .
    """
    report = client.post("/api/validate", json={"ttl": ttl}).get_json()
    assert report["conforms"] is True, "guidance must never affect conformance"
    assert report["hints"], "annotation-guidance hints are missing from the report"
    assert any("retrieval step" in hint["message"] for hint in report["hints"])


def test_assess_endpoint_still_works(client) -> None:
    ttl = example_path(ONYX_NS).read_text(encoding="utf-8")
    response = client.post("/api/assess", json={"ttl": ttl})
    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["riskFindingCount"] > 0


def test_import_t4b_endpoint_normalizes_sample_export(client) -> None:
    sample = (REPO_ROOT / "external" / "tool4boxology" / "sample_export.nt").read_text(encoding="utf-8")
    response = client.post("/api/import/t4b", json={"data": sample, "format": "nt"})
    assert response.status_code == 200
    data = response.get_json()
    assert "beam:System" in data["ttl"]
    assert "beam:use" in data["ttl"] or "beam:produce" in data["ttl"]
    assert data["warnings"]


def test_import_t4b_endpoint_rejects_empty_input(client) -> None:
    response = client.post("/api/import/t4b", json={"data": "  "})
    assert response.status_code == 400


def test_import_t4b_endpoint_reports_bad_input(client) -> None:
    response = client.post("/api/import/t4b", json={"data": "not a triple at all", "format": "nt"})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_vocabulary_roles_are_grouped_by_top_level_role(client) -> None:
    """Every pattern role carries the label of its top-level ancestor as `group`
    so the UI can render <optgroup> headings. Groups come from the ontology
    (roles with no pair:subRoleOf parent), never a hardcoded list."""
    response = client.get("/api/vocabulary")
    assert response.status_code == 200
    data = response.get_json()

    roles = data["roles"]
    assert roles, "roles expected"
    # every role is selectable and grouped
    assert all(role.get("group") for role in roles), "every role needs a group"
    assert len({role["id"] for role in roles}) == len(roles), "role ids unique"

    # groups are the ontology's top-level roles, which are their own group
    groups = {role["group"] for role in roles}
    by_id = {role["id"]: role for role in roles}
    for top in ("ProcessingStep", "ControlStep", "ResourceRole", "UserInput"):
        uri = f"http://w3id.org/airiskkg/pair-ai#{top}"
        assert by_id[uri]["group"] == by_id[uri]["label"]
        assert by_id[uri]["label"] in groups

    # a role with several parents still resolves to a single group
    external_model = by_id["http://w3id.org/airiskkg/pair-ai#ExternalModel"]
    assert external_model["group"] == "Resource Role"

    # data categories stay ungrouped so their dropdown is unaffected
    assert not any("group" in category for category in data["dataCategories"])


def test_vocabulary_roles_declare_which_element_kind_they_apply_to(client) -> None:
    """Roles carry `applies` ("process" / "resource") so the picker can offer the
    ones that fit the selected element. Derived from each role family's
    expectedClass, so process families never leak into resource families."""
    data = client.get("/api/vocabulary").get_json()
    roles = data["roles"]
    assert all(role.get("applies") in {"process", "resource"} for role in roles)

    by_group: dict[str, set[str]] = {}
    for role in roles:
        by_group.setdefault(role["group"], set()).add(role["applies"])
    # a family is process or resource, never both
    assert all(len(kinds) == 1 for kinds in by_group.values()), by_group
    assert by_group["Processing Step"] == {"process"}
    assert by_group["Control Step"] == {"process"}
    assert by_group["Resource Role"] == {"resource"}


# Inline RAG fixture. These three tests used to load a bundled example and then
# edit it by string replacement, which silently stopped testing anything the
# moment the example was renamed or its element names changed - the assertion
# that caught it was a guard someone had the foresight to add. Stating the graph
# here keeps the gap report under test regardless of how examples are organised.
_RAG_GRAPH = """
@prefix local: <http://example.org/rag#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

local:sys a beam:System ; rdfs:label "RAG probe" ;
    beam:contain local:userQuery, local:vectorStore, local:retrieve, local:retrievedContext,
                 local:promptBuild, local:prompt, local:llm, local:generate, local:response .

local:userQuery a beam:Data ; rdfs:label "User query" ;
    pair:playsRole pair:UserInput .
local:vectorStore a beam:Data ; rdfs:label "Vector store" ;
    pair:playsRole pair:VectorStore .
local:retrieve a beam:Transform, beam:Process ; rdfs:label "Retrieve" ;
    pair:playsRole pair:RetrievalStep ;
    beam:use local:userQuery ;
    beam:use local:vectorStore ;
    beam:produce local:retrievedContext .
local:retrievedContext a beam:Data ; rdfs:label "Retrieved context" ;
    pair:playsRole pair:RetrievedContext .
local:promptBuild a beam:Transform, beam:Process ; rdfs:label "Build prompt" ;
    pair:playsRole pair:PromptConstructionStep ;
    beam:use local:retrievedContext ;
    beam:produce local:prompt .
local:prompt a beam:Data ; rdfs:label "Prompt" ;
    pair:playsRole pair:PromptTemplate .
local:llm a beam:StatisticalModel ; rdfs:label "LLM" ;
    pair:playsRole pair:FoundationLLM .
local:generate a beam:Infer, beam:Process ; rdfs:label "Generate" ;
    pair:playsRole pair:GenerationStep ;
    beam:use local:prompt ; beam:use local:llm ;
    beam:produce local:response .
local:response a beam:Data ; rdfs:label "Response" ;
    pair:playsRole pair:LLMResponse, pair:PublicUserFacingOutput .
"""


def _rag_with_guardrails_ttl() -> str:
    return _RAG_GRAPH


def test_assess_reports_why_a_near_miss_motif_did_not_match(client) -> None:
    """Unwiring the retrieval step from the user query drops RAG and Vector-based
    IR; the gap report names the missing edge instead of failing silently."""
    ttl = _rag_with_guardrails_ttl()
    broken = ttl.replace(
        "    beam:use local:userQuery ;\n    beam:use local:vectorStore ;",
        "    beam:use local:vectorStore ;",
    )
    assert broken != ttl, "fixture no longer matches the example"

    data = client.post("/api/assess", json={"ttl": broken}).get_json()
    matched = {m["motif"]["label"] for m in data["motifMatches"]}
    assert not any("Retrieval Augmented" in label for label in matched)

    gaps = {gap["label"]: gap for gap in data["motifGaps"]}
    rag = next(gap for label, gap in gaps.items() if "Retrieval Augmented" in label)
    assert rag["satisfied"] < rag["total"]
    missing = " | ".join(edge["text"] for edge in rag["missingEdges"])
    assert "Retrieval Step" in missing and "User Input" in missing


def test_assess_gaps_exclude_motifs_that_matched(client) -> None:
    """A motif that matched is reported as a match, never as a gap."""
    data = client.post("/api/assess", json={"ttl": _rag_with_guardrails_ttl()}).get_json()
    matched = {m["motif"]["label"] for m in data["motifMatches"]}
    assert matched, "expected the example to match motifs"
    gap_labels = {gap["label"] for gap in data["motifGaps"]}
    assert not (matched & gap_labels)


def test_assess_gap_candidates_are_elements_of_the_submitted_graph(client) -> None:
    """Suggested candidates are real elements with the right type but no role, so
    the UI can highlight them."""
    ttl = _rag_with_guardrails_ttl().replace(
        "    pair:playsRole pair:VectorStore .", "."
    )
    data = client.post("/api/assess", json={"ttl": ttl}).get_json()
    candidates = [
        candidate
        for gap in data["motifGaps"]
        for node in gap["missingNodes"]
        for candidate in node["candidates"]
    ]
    assert candidates, "expected candidate elements for the untagged vector store"
    assert all(candidate["id"].startswith("http") for candidate in candidates)


def test_module_notes_list_every_registered_route(client) -> None:
    """The endpoint notes at the top of app.py are the first thing a reader of
    this webapp sees, and nothing regenerates them - ``/api/annotate`` and
    ``/api/graph-edit`` were both live for weeks without appearing there. A
    docstring that is silently incomplete is worse than none, so it is checked
    like any other claim the repository makes."""
    from airiskkg.webapp import app as module

    notes = module.__doc__ or ""
    routes = {
        rule.rule
        for rule in client.application.url_map.iter_rules()
        if not rule.rule.startswith("/static")
    }
    # Flask writes converters as <name>; the notes may say <name> or <n>.
    documented = {
        route
        for route in routes
        if route in notes or re.sub(r"<[^>]+>", "<", route) in re.sub(r"<[^>]+>", "<", notes)
    }
    assert documented == routes, (
        "endpoints missing from the notes in app.py: " + ", ".join(sorted(routes - documented))
    )


def test_graph_nodes_carry_the_line_that_declares_them(client) -> None:
    """The canvas and the Turtle are two views of one document. Without a line
    number the only way across is to read a label off a box and search for it,
    which fails the moment two elements share a label."""
    ttl = example_path(ONYX_NS).read_text(encoding="utf-8")
    data = client.post("/api/graph", json={"ttl": ttl}).get_json()
    assert data["nodes"], "expected nodes"
    missing = [n["label"] for n in data["nodes"] if not n.get("line")]
    assert not missing, "nodes with no source line: " + ", ".join(missing)

    # every reported line must actually declare that element
    source = ttl.splitlines()
    for node in data["nodes"]:
        local = node["id"].rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        line = source[node["line"] - 1]
        assert local in line, f"{node['label']} -> line {node['line']}: {line!r}"


def test_source_lines_ignore_continuations_and_comments() -> None:
    """A subject is where a statement starts. Indented predicate lines belong to
    a subject already recorded, and a term inside a comment is not a
    declaration."""
    from airiskkg.graph_view import source_lines

    ttl = (
        "@prefix ex: <http://example.org/x#> .\n"   # 1
        "# ex:decoy is only mentioned here\n"        # 2
        "\n"                                         # 3
        "ex:thing a <http://example.org/C> ;\n"      # 4
        "    ex:prop ex:other .\n"                   # 5
        "\n"                                         # 6
        "ex:other a <http://example.org/C> .\n"      # 7
    )
    lines = source_lines(ttl)
    assert lines["http://example.org/x#thing"] == 4
    assert lines["http://example.org/x#other"] == 7, "object position must not win over the declaration"
    assert "http://example.org/x#decoy" not in lines
    assert "http://example.org/x#prop" not in lines, "a predicate is not a subject"


_INJECTION_GRAPH = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:   <http://example.org/dp#> .
ex:sys a beam:System ; rdfs:label "Chatbot" ;
    beam:hasProcess ex:gen ; beam:hasResource ex:prompt, ex:llm, ex:answer .
ex:prompt a beam:Data ; rdfs:label "User prompt" ; pair:playsRole pair:PublicUserInput .
ex:llm a beam:StatisticalModel ; rdfs:label "LLM" ; pair:playsRole pair:FoundationLLM .
ex:answer a beam:Data ; rdfs:label "Answer" ;
    pair:playsRole pair:LLMResponse , pair:UserFacingOutput .
ex:gen a beam:Process ; rdfs:label "Generate" ; pair:playsRole pair:GenerationStep ;
    beam:use ex:prompt , ex:llm ; beam:produce ex:answer .
"""


def _finding(client, ttl, phrase):
    data = client.post("/api/assess", json={"ttl": ttl}).get_json()
    return next((f for f in data["findings"] if phrase in f["label"]), None)


def test_applying_a_control_clears_the_finding_it_answers(client) -> None:
    """The point of suggesting a control is that applying it changes the answer.

    The insertion is a registered SPARQL rewrite that restates the vulnerable
    shape and constructs the step interrupting it, so the screen lands on the
    path the finding cites - not beside the diagram, where it would be
    structurally present and on no path at all."""
    finding = _finding(client, _INJECTION_GRAPH, "prompt injection")
    assert finding is not None, "expected the bare graph to raise prompt injection"
    control = next(c for c in finding["suggestedControls"] if c["applicable"])

    applied = client.post("/api/apply-control", json={
        "ttl": _INJECTION_GRAPH, "control": control["id"], "finding": finding["id"],
    }).get_json()
    assert applied["addedTriples"] > 0
    assert _finding(client, applied["ttl"], "prompt injection") is None


def test_applying_the_same_control_twice_changes_nothing(client) -> None:
    """The inserted step's IRI is derived from the pair it screens, and the
    rewrite skips a path that is already screened, so a second application is a
    no-op rather than a second identical filter."""
    finding = _finding(client, _INJECTION_GRAPH, "prompt injection")
    control = next(c for c in finding["suggestedControls"] if c["applicable"])
    once = client.post("/api/apply-control", json={
        "ttl": _INJECTION_GRAPH, "control": control["id"], "finding": finding["id"],
    }).get_json()

    # the finding is gone, so re-applying has nothing to bind and adds nothing
    twice = client.post("/api/apply-control", json={
        "ttl": once["ttl"], "control": control["id"], "finding": finding["id"],
    }).get_json()
    assert twice["addedTriples"] == 0
    assert len(twice["ttl"]) == len(once["ttl"])


def test_a_mitigation_rewrite_never_runs_during_an_assessment(client) -> None:
    """The guard that makes this safe: mitigation queries produce their own
    output type, and the pipeline asks only for MotifMatch and RiskFinding. Were
    they run in the assessment loop, every finding would mitigate itself and
    none would ever be reported."""
    from airiskkg.assessment_runner import (
        PAIR, implementation_paths_for_output_type, load_base_graph, mitigation_implementations,
    )

    graph = load_base_graph()
    rewrites = set(mitigation_implementations(graph).values())
    assert rewrites, "expected at least one registered rewrite"
    for output_type in (PAIR.MotifMatch, PAIR.RiskFinding, PAIR.DataCategoryPropagation):
        assert not (rewrites & set(implementation_paths_for_output_type(graph, output_type))), (
            f"a mitigation rewrite is registered under {output_type}"
        )
    # and the finding it mitigates is still raised by a plain assessment
    assert _finding(client, _INJECTION_GRAPH, "prompt injection") is not None


def test_a_control_with_no_rewrite_is_reported_as_not_applicable(client) -> None:
    """A control the tool cannot insert is still worth suggesting; the UI just
    must not offer a button that does nothing."""
    finding = _finding(client, _INJECTION_GRAPH, "prompt injection")
    flags = {c["label"]: c["applicable"] for c in finding["suggestedControls"]}
    assert any(flags.values()) and not all(flags.values()), flags


def test_applying_a_control_that_has_no_rewrite_is_refused(client) -> None:
    finding = _finding(client, _INJECTION_GRAPH, "prompt injection")
    control = next(c for c in finding["suggestedControls"] if not c["applicable"])
    response = client.post("/api/apply-control", json={
        "ttl": _INJECTION_GRAPH, "control": control["id"], "finding": finding["id"],
    })
    assert response.status_code == 400
    assert "mitigation rewrite" in response.get_json()["error"]


def test_apply_is_offered_only_where_a_rewrite_targets_that_risk(client) -> None:
    """The bug this exists for: one control, several risks, one rewrite.

    Output validation is suggested by improper-output-handling, sensitive
    disclosure and system-prompt-leakage, but a rewrite is written against one
    vulnerable shape. Keyed on the control alone, every one of those findings
    offered an Apply button that ran the improper-output-handling rewrite: it
    found its own screen already in place, added nothing, reported "already in
    place on this path", and left the risk untouched."""
    ttl = example_path(ONYX_NS).read_text(encoding="utf-8")
    data = client.post("/api/assess", json={"ttl": ttl}).get_json()

    offers: dict[str, set[str]] = {}
    for finding in data["findings"]:
        for control in finding["suggestedControls"]:
            if control["applicable"]:
                offers.setdefault(control["label"], set()).add(finding["label"])

    output_validation = offers.get("Output validation and sanitization", set())
    assert output_validation, "expected output validation to be applicable somewhere"
    # Every finding that offers it must have a rewrite targeting its own risk
    # pattern; the check below proves each offer inserts something.
    assert output_validation <= {
        "Candidate improper LLM output handling",
        "Candidate sensitive information disclosure",
    }, "offered on a finding no rewrite targets: " + ", ".join(sorted(output_validation))

    # And every offer must actually do something when taken.
    for finding in data["findings"]:
        for control in finding["suggestedControls"]:
            if not control["applicable"]:
                continue
            applied = client.post("/api/apply-control", json={
                "ttl": ttl, "control": control["id"], "finding": finding["id"],
            }).get_json()
            assert applied.get("addedTriples"), (
                f"{control['label']} offered on {finding['label']} but inserted nothing"
            )


def test_a_risk_firing_on_several_paths_needs_a_control_on_each(client) -> None:
    """Applying once does not always clear a label. Prompt injection is raised
    per untrusted-content/generation pair, so a system with three such paths
    needs three screens - the count falls each time rather than in one step."""
    ttl = example_path(ONYX_NS).read_text(encoding="utf-8")
    counts = []
    for _ in range(3):
        data = client.post("/api/assess", json={"ttl": ttl}).get_json()
        counts.append(data["summary"]["riskFindingCount"])
        todo = [
            (f, c) for f in data["findings"]
            for c in f["suggestedControls"]
            if c["applicable"] and "prompt injection" in f["label"]
        ]
        if not todo:
            break
        finding, control = todo[0]
        ttl = client.post("/api/apply-control", json={
            "ttl": ttl, "control": control["id"], "finding": finding["id"],
        }).get_json()["ttl"]
    assert counts == sorted(counts, reverse=True) and counts[0] > counts[-1], counts


# --- run identity in the UI ---------------------------------------------------
#
# Two things about an assessment are invisible while you work, and both mislead:
# the drawer keeps showing the last run's findings while the editor moves on,
# and a .ttl edited on disk is not reloaded by a running server.


def _onyx_ttl() -> str:
    return example_path(ONYX_NS).read_text(encoding="utf-8")


def test_an_assessment_says_what_it_ran_on(client) -> None:
    response = client.post("/api/assess", json={"ttl": _onyx_ttl()})
    run = response.get_json()["run"]

    assert run["inputFingerprint"]
    assert run["knowledgeBase"]["motifs"] > 0
    assert run["knowledgeBase"]["riskPatterns"] > 0
    assert run["knowledgeBase"]["fingerprint"]


def test_the_fingerprint_endpoint_agrees_with_the_run(client) -> None:
    """Otherwise the staleness check compares two different things and either
    never fires or never stops firing."""
    ttl = _onyx_ttl()
    assessed = client.post("/api/assess", json={"ttl": ttl}).get_json()
    probed = client.post("/api/fingerprint", json={"ttl": ttl}).get_json()

    assert probed["fingerprint"] == assessed["run"]["inputFingerprint"]
    assert probed["tripleCount"] > 0


def test_reserializing_the_graph_does_not_look_like_an_edit(client) -> None:
    """Every canvas edit and every annotation re-serializes the whole document
    through rdflib, so the Turtle changes constantly while the graph does not. A
    staleness warning that fires on each click is one people learn to ignore."""
    ttl = _onyx_ttl()
    reserialized = flask.json.loads(
        client.post(
            "/api/graph-edit",
            json={"ttl": ttl, "op": "add-edge", "subject": "urn:x", "predicate": "inform", "object": "urn:y"},
        ).data
    )["ttl"]

    before = client.post("/api/fingerprint", json={"ttl": ttl}).get_json()["fingerprint"]
    after = client.post("/api/fingerprint", json={"ttl": reserialized}).get_json()["fingerprint"]
    assert before != after, "adding an edge is a real change and must register"

    round_tripped = flask.json.loads(
        client.post(
            "/api/annotate", json={"ttl": ttl, "annotations": {}}
        ).data
    )["ttl"]
    unchanged = client.post("/api/fingerprint", json={"ttl": round_tripped}).get_json()["fingerprint"]
    assert unchanged == before, "a no-op annotation reserialized the text but changed no triple"


def test_applying_a_control_moves_the_input_fingerprint_and_clears_findings(client) -> None:
    """The loop the drawer reports on: what did the control I just applied do?
    Answerable as a set difference because finding IRIs are deterministic."""
    ttl = _onyx_ttl()
    first = client.post("/api/assess", json={"ttl": ttl}).get_json()
    before = {finding["id"] for finding in first["findings"]}

    choice = next(
        (finding, control)
        for finding in first["findings"]
        for control in finding["suggestedControls"]
        if control.get("applicable")
    )
    finding, control = choice
    amended = client.post(
        "/api/apply-control",
        json={"ttl": ttl, "control": control["id"], "finding": finding["id"]},
    ).get_json()["ttl"]

    second = client.post("/api/assess", json={"ttl": amended}).get_json()
    after = {item["id"] for item in second["findings"]}

    assert second["run"]["inputFingerprint"] != first["run"]["inputFingerprint"]
    assert before - after, "applying a control cleared nothing"
    assert second["run"]["knowledgeBase"]["fingerprint"] == first["run"]["knowledgeBase"]["fingerprint"]


def test_fingerprinting_nothing_is_refused(client) -> None:
    assert client.post("/api/fingerprint", json={"ttl": "  "}).status_code == 400


# --- drawing the business layer ----------------------------------------------
#
# BEAM cannot express a pool, a lane, or a message between two organisations, so
# the business layer is authored with its own vocabulary and its own endpoint.


def _draw(client, ttl, **payload):
    response = client.post("/api/process-edit", json={"ttl": ttl, **payload})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    return body["ttl"], body["newId"]


def test_a_process_can_be_drawn_from_nothing(client) -> None:
    ttl = ""
    ttl, customer = _draw(client, ttl, op="add-pool", label="Customer")
    ttl, retailer = _draw(client, ttl, op="add-pool", label="Northwind Energy")
    ttl, ask = _draw(client, ttl, op="add-activity", pool=customer, kind="task", label="Ask")
    ttl, receive = _draw(client, ttl, op="add-activity", pool=retailer, kind="receiveTask", label="Receive")

    view = client.post("/api/process", json={"ttl": ttl}).get_json()
    assert view["stats"]["participants"] == 2
    assert {a["label"] for a in view["activities"]} == {"Ask", "Receive"}
    assert ask and receive


def test_whether_a_connection_is_a_message_follows_from_the_pools(client) -> None:
    """Not a preference the modeller has to know. Sequence flow cannot leave a
    process and a message flow only exists between participants, so the server
    reads the containment and decides."""
    ttl = ""
    ttl, customer = _draw(client, ttl, op="add-pool", label="Customer")
    ttl, retailer = _draw(client, ttl, op="add-pool", label="Retailer")
    ttl, ask = _draw(client, ttl, op="add-activity", pool=customer, kind="task", label="Ask")
    ttl, receive = _draw(client, ttl, op="add-activity", pool=retailer, kind="receiveTask", label="Receive")
    ttl, reply = _draw(client, ttl, op="add-activity", pool=retailer, kind="sendTask", label="Reply")

    ttl, _ = _draw(client, ttl, op="connect", source=ask, target=receive)      # across pools
    ttl, _ = _draw(client, ttl, op="connect", source=receive, target=reply)    # within one

    view = client.post("/api/process", json={"ttl": ttl}).get_json()
    assert len(view["messageFlows"]) == 1, "crossing a boundary must produce a message flow"
    assert view["messageFlows"][0]["source"] == ask


def test_deleting_a_participant_takes_its_process_and_connectors(client) -> None:
    """A pool owns its process. Removing the pool alone would leave a process
    nothing runs, activities nobody performs, and a message from nowhere."""
    ttl = ""
    ttl, customer = _draw(client, ttl, op="add-pool", label="Customer")
    ttl, retailer = _draw(client, ttl, op="add-pool", label="Retailer")
    ttl, ask = _draw(client, ttl, op="add-activity", pool=customer, kind="task", label="Ask")
    ttl, receive = _draw(client, ttl, op="add-activity", pool=retailer, kind="receiveTask", label="Receive")
    ttl, _ = _draw(client, ttl, op="connect", source=ask, target=receive)

    ttl, _ = _draw(client, ttl, op="delete", element=customer)
    view = client.post("/api/process", json={"ttl": ttl}).get_json()

    assert view["stats"]["participants"] == 1
    assert [a["label"] for a in view["activities"]] == ["Receive"]
    assert view["messageFlows"] == []


def test_an_activity_can_be_pointed_at_an_architecture(client) -> None:
    ttl = ""
    ttl, pool = _draw(client, ttl, op="add-pool", label="Retailer")
    ttl, activity = _draw(client, ttl, op="add-activity", pool=pool, kind="subProcess", label="Chatbot")
    system = "http://tool4boxology.org/Boxology/graphrag-example"
    ttl, _ = _draw(client, ttl, op="set-refines", activity=activity, system=system)

    view = client.post("/api/process", json={"ttl": ttl}).get_json()
    assert view["activities"][0]["refines"] == [system]

    ttl, _ = _draw(client, ttl, op="set-refines", activity=activity, system="")
    cleared = client.post("/api/process", json={"ttl": ttl}).get_json()
    assert cleared["activities"][0]["refines"] == []


def test_an_unknown_activity_kind_is_refused(client) -> None:
    assert client.post(
        "/api/process-edit", json={"ttl": "", "op": "add-activity", "pool": "x", "kind": "gateway"}
    ).status_code == 400


def test_findings_are_attributed_to_the_activity_they_arise_under(client) -> None:
    """What makes a finding communicable. "Three findings on Draft an answer" is
    a sentence a process owner acts on; the name of an inference step is not."""
    architecture = example_path(ONYX_NS).read_text(encoding="utf-8")
    process = (EXAMPLE_DIR / "context" / "onyx_support_process.ttl").read_text(encoding="utf-8")

    assessed = client.post("/api/assess", json={"ttl": architecture + "\n" + process}).get_json()
    rows = assessed["findingsByActivity"]

    assert rows, "no findings were attributed to any activity"
    assert rows[0]["label"] == "Draft an answer"
    assert rows[0]["findings"] == assessed["summary"]["riskFindingCount"]


def test_an_architecture_with_no_process_attributes_nothing(client) -> None:
    assessed = client.post(
        "/api/assess", json={"ttl": example_path(ONYX_NS).read_text(encoding="utf-8")}
    ).get_json()
    assert assessed["findingsByActivity"] == []
