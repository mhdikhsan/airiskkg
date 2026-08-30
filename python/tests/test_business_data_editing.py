"""Attaching data to a business activity, without writing Turtle by hand.

A data object is three BPMN nodes and two associations - a reference, an object,
an item definition - and the one that matters for risk is the last, because
business_data_bridge.rq reads `bp:structureRef` off it. Asking a process owner
to write that by hand is asking them to learn RDF to say "this is personal
data", which is the one thing the business layer exists to let them say.

So these check the whole round trip: the edit writes BPMN a reader can parse,
the process view shows it back, and the assessment moves because of it. The
last one is the point. An edit that draws a box and changes no finding would be
decoration.
"""

from __future__ import annotations

import pytest

from airiskkg.paths import EXAMPLE_DIR, REPO_ROOT

CONTEXT = REPO_ROOT / "ontology" / "example" / "context" / "energy_customer_service.ttl"
CHECK_READING = "http://w3id.org/airiskkg/example/energy-cs#CheckReading"
METER_READING_REF = "http://w3id.org/airiskkg/example/energy-cs#MeterReadingRef"


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


@pytest.fixture(scope="module")
def process_ttl() -> str:
    return CONTEXT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def scene(process_ttl) -> str:
    """The process plus both architectures it refines - what the workbench holds
    when someone opens the business example."""
    return "\n\n".join([
        (EXAMPLE_DIR / "meter_anomaly_scoring.ttl").read_text(encoding="utf-8"),
        (EXAMPLE_DIR / "simple_graph_rag.ttl").read_text(encoding="utf-8"),
        process_ttl,
    ])


def edit(client, ttl: str, op: str, **payload) -> str:
    response = client.post("/api/process-edit", json={"ttl": ttl, "op": op, **payload})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["ttl"]


def data_of(client, ttl: str, activity: str) -> tuple[list, list]:
    view = client.post("/api/process", json={"ttl": ttl}).get_json()
    row = next(a for a in view["activities"] if a["id"] == activity)
    return row["reads"], row["writes"]


def findings(client, ttl: str) -> int:
    return client.post("/api/assess", json={"ttl": ttl}).get_json()["summary"]["riskFindingCount"]


def test_added_data_comes_back_through_the_process_view(client, process_ttl) -> None:
    after = edit(client, process_ttl, "add-data", activity=CHECK_READING, direction="in",
                 label="Tariff record", classification="PersonalData")
    reads, _ = data_of(client, after, CHECK_READING)
    added = [row for row in reads if row["label"] == "Tariff record"]
    assert added, f"the new data object is not attached to the activity: {reads}"
    assert added[0]["kinds"] == ["PersonalData"], "the classification did not survive the round trip"


def test_a_classification_can_be_changed_and_cleared(client, process_ttl) -> None:
    after = edit(client, process_ttl, "classify-data", reference=METER_READING_REF,
                 classification="SensitivePersonalData")
    reads, _ = data_of(client, after, CHECK_READING)
    assert [r for r in reads if r["kinds"] == ["SensitivePersonalData"]], "reclassifying did nothing"

    cleared = edit(client, after, "classify-data", reference=METER_READING_REF, classification="")
    reads, _ = data_of(client, cleared, CHECK_READING)
    assert all(not r["kinds"] for r in reads), "clearing the classification left it in place"


def test_detaching_data_leaves_nothing_behind(client, process_ttl) -> None:
    """A data object nothing reads or writes is litter, and it would keep
    drawing on the diagram."""
    after = edit(client, process_ttl, "detach-data",
                 reference=METER_READING_REF, activity=CHECK_READING)
    reads, _ = data_of(client, after, CHECK_READING)
    assert not [r for r in reads if r["id"] == METER_READING_REF], "the data is still attached"
    assert "MeterReadingRef" not in after, "the reference outlived its only association"
    assert "Smart meter reading" not in after, "the data object outlived its only reference"


def test_an_unknown_classification_is_refused(client, process_ttl) -> None:
    """The picker is built from the same table the writer validates against, so
    anything else arriving here is a bug or a hand-made request."""
    response = client.post("/api/process-edit", json={
        "ttl": process_ttl, "op": "add-data", "activity": CHECK_READING,
        "direction": "in", "label": "Whatever", "classification": "NotADpvTerm",
    })
    assert response.status_code == 400


def test_the_classification_is_what_moves_the_assessment(client, scene) -> None:
    """The whole reason the business layer exists.

    Detaching the personal-data input drops a finding; putting it back restores
    it; putting it back as anonymised does not - which is exactly what
    business_data_bridge.rq says, since dpv:AnonymisedData is one of the two
    values it excludes.
    """
    shipped = findings(client, scene)

    without = edit(client, scene, "detach-data",
                   reference=METER_READING_REF, activity=CHECK_READING)
    assert findings(client, without) < shipped, (
        "removing the personal data the bridge reads changed no finding"
    )

    personal = edit(client, without, "add-data", activity=CHECK_READING, direction="in",
                    label="Smart meter reading", classification="PersonalData")
    assert findings(client, personal) == shipped, (
        "re-declaring it as personal data did not bring the finding back"
    )

    anonymised = edit(client, without, "add-data", activity=CHECK_READING, direction="in",
                      label="Smart meter reading", classification="AnonymisedData")
    assert findings(client, anonymised) == findings(client, without), (
        "anonymised data raised a sensitive-information category; the bridge excludes it"
    )


def test_the_picker_offers_exactly_what_the_writer_accepts(client) -> None:
    """Two lists that must not drift: one fills a dropdown, the other validates."""
    from airiskkg.workbench.process_view import DATA_CLASSES

    offered = {row["id"] for row in client.get("/api/vocabulary").get_json()["dataClasses"]}
    assert offered == set(DATA_CLASSES)


def test_each_architecture_says_which_elements_are_its_own(scene) -> None:
    """Two architectures in one document arrived as one field of nodes, and
    which cluster was which was left to the reader to infer from the labels.

    Membership is not a layout guess: beam:hasProcess / hasResource / hasAgent /
    contain already say what belongs to what, so the boundary the canvas draws
    is read off the graph."""
    from airiskkg.graph_view import graph_view

    view = graph_view(scene)
    systems = {s["label"]: s for s in view["systems"]}
    assert len(systems) >= 2, f"expected both architectures, got {list(systems)}"
    for label, system in systems.items():
        assert system["members"], f"{label} claims no elements"

    drawn = {n["id"] for n in view["nodes"]}
    claimed = [m for s in view["systems"] for m in s["members"]]
    assert set(claimed) <= drawn, "a system claims an element the canvas does not draw"
    assert len(claimed) == len(set(claimed)), (
        "an element is claimed by two systems; the boundaries would overlap"
    )
    assert not view["unclaimed"], f"elements belong to no system: {view['unclaimed']}"


def test_a_narrowed_canvas_reports_only_the_system_it_shows(scene) -> None:
    """Scoped to one architecture there is nothing to tell apart, and a boundary
    round everything on screen would say nothing."""
    from airiskkg.graph_view import graph_view

    everything = graph_view(scene)
    one = everything["systems"][0]
    scoped = graph_view(scene, scope=one["id"])
    assert scoped["scopedTo"] == one["id"]
    drawn = {n["id"] for n in scoped["nodes"]}
    assert drawn == set(one["members"]), "narrowing did not leave exactly that system's elements"


def test_an_absent_architecture_is_reported_not_substituted(scene) -> None:
    """Deleting one architecture from a two-system scene.

    The chatbot activity still says which system carries it out. With that
    system gone, narrowing to it used to be ignored and the canvas drew
    everything left - so opening the chatbot landed the reader on the meter
    scorer. That is not an empty answer, it is the wrong one.
    """
    from airiskkg.graph_view import graph_view

    everything = graph_view(scene)
    gone, kept = everything["systems"][0], everything["systems"][1]

    without = graph_view(scene, scope=gone["id"])
    assert without["scopedTo"] == gone["id"], "the system is present, so it should scope normally"

    # Now the same request against a graph that no longer holds it.
    trimmed = "\n\n".join(
        line for line in scene.split("\n\n") if gone["id"].split("#")[-1] not in line
    )
    missing = graph_view(trimmed, scope=gone["id"])
    assert missing["scopeMissing"] == gone["id"], (
        "asking for an architecture the graph does not hold was reported as an ordinary view"
    )
    assert missing["nodes"] == [], (
        f"{len(missing['nodes'])} nodes were drawn for a system that is not there - "
        "they belong to some other architecture"
    )
    assert kept["id"] != gone["id"]


def test_every_taxonomy_entry_names_the_catalogue_it_came_from() -> None:
    """A finding lists entries from several catalogues at once, and only OWASP
    numbers its own ("LLM01:2025 Prompt Injection"). "Prompt injection attack"
    and "AI system security vulnerabilities" gave no clue they are IBM and MIT.

    Worse, a scheme missing from the table falls through to "Other" - which is
    how every ASI entry was presented for as long as the agentic layer existed.
    """
    from rdflib import RDF, URIRef

    from airiskkg.assessment_runner import load_base_graph
    from airiskkg.assessment_view import _source

    graph = load_base_graph()
    entries = set(graph.subjects(RDF.type, URIRef("http://w3id.org/airiskkg/taxonomy/nexus#Risk")))
    assert entries, "no taxonomy entries are loaded at all"

    unnamed = sorted({str(e).rsplit("#", 1)[0] for e in entries if _source(e) == "Other"})
    assert not unnamed, (
        "these taxonomy schemes have no entry in _SOURCE_PREFIXES, so their risks "
        "are shown as coming from \"Other\": " + ", ".join(unnamed)
    )
