"""Attaching data to a business activity, without writing Turtle by hand."""

from __future__ import annotations

import pytest

from airiskkg.paths import EXAMPLE_DIR, REPO_ROOT
from conftest import (  # noqa: E402
    TARIFF_NS,
    WIEN_ENERGIE_NS,
    example_path,
    process_path,
)

pytestmark = pytest.mark.ui

# Resolved, not located: both retired from the shipped example set and are kept
# as test fixtures, so the coverage they back did not retire with them.
CONTEXT = process_path("energy_customer_service")
TARIFF = process_path("energy_tariff_change")
EC = "http://w3id.org/airiskkg/example/energy-cs#"
# One activity whose only data input is the one under test, so clearing a
# classification can be checked by looking at everything the activity reads.
OFFER_HELP = EC + "OfferHelp"
CHAT_MESSAGE_REF = EC + "ChatMessageRef"
# The question, which several AI steps read: detaching it takes two edits.
DOMAIN_CLASSIFICATION = EC + "DomainClassification"
QUERY_EXTRACTION = EC + "QueryParameterExtraction"
QUESTION_REF = EC + "QuestionRef"


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


@pytest.fixture(scope="module")
def process_ttl() -> str:
    return CONTEXT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tariff_ttl() -> str:
    """The tariff process, which has an activity whose only data input is the
    one under test - so clearing a classification can be checked by looking at
    everything the activity reads."""
    return TARIFF.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def scene(process_ttl) -> str:
    """The process plus both architectures it refines - what the workbench holds
    when someone opens the business example."""
    return "\n\n".join([
        example_path(WIEN_ENERGIE_NS).read_text(encoding="utf-8"),
        example_path(TARIFF_NS).read_text(encoding="utf-8"),
        process_ttl,
        TARIFF.read_text(encoding="utf-8"),
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


def test_added_data_comes_back_through_the_process_view(client, tariff_ttl) -> None:
    after = edit(client, tariff_ttl, "add-data", activity=OFFER_HELP, direction="in",
                 label="Tariff record", classification="PersonalData")
    reads, _ = data_of(client, after, OFFER_HELP)
    added = [row for row in reads if row["label"] == "Tariff record"]
    assert added, f"the new data object is not attached to the activity: {reads}"
    assert added[0]["kinds"] == ["PersonalData"], "the classification did not survive the round trip"


def test_a_classification_can_be_changed_and_cleared(client, tariff_ttl) -> None:
    after = edit(client, tariff_ttl, "classify-data", reference=CHAT_MESSAGE_REF,
                 classification="SensitivePersonalData")
    reads, _ = data_of(client, after, OFFER_HELP)
    assert [r for r in reads if r["kinds"] == ["SensitivePersonalData"]], "reclassifying did nothing"

    cleared = edit(client, after, "classify-data", reference=CHAT_MESSAGE_REF, classification="")
    reads, _ = data_of(client, cleared, OFFER_HELP)
    assert all(not r["kinds"] for r in reads), "clearing the classification left it in place"


def test_detaching_data_leaves_nothing_behind(client, tariff_ttl) -> None:
    """A data object nothing reads or writes is litter, and it would keep drawing on the diagram."""
    after = edit(client, tariff_ttl, "detach-data",
                 reference=CHAT_MESSAGE_REF, activity=OFFER_HELP)
    reads, _ = data_of(client, after, OFFER_HELP)
    assert not [r for r in reads if r["id"] == CHAT_MESSAGE_REF], "the data is still attached"
    assert "ChatMessageRef" not in after, "the reference outlived its only association"
    assert "CustomerChatMessage" not in after, "the data object outlived its only reference"


def test_an_unknown_classification_is_refused(client, tariff_ttl) -> None:
    """The picker is built from the same table the writer validates against, so
    anything else arriving here is a bug or a hand-made request."""
    response = client.post("/api/process-edit", json={
        "ttl": tariff_ttl, "op": "add-data", "activity": OFFER_HELP,
        "direction": "in", "label": "Whatever", "classification": "NotADpvTerm",
    })
    assert response.status_code == 400


def test_the_classification_is_what_moves_the_assessment(client, scene) -> None:
    """The whole reason the business layer exists."""
    shipped = findings(client, scene)

    without = scene
    for activity in (DOMAIN_CLASSIFICATION, QUERY_EXTRACTION):
        without = edit(client, without, "detach-data", reference=QUESTION_REF, activity=activity)
    assert findings(client, without) < shipped, (
        "removing the personal data the bridge reads changed no finding"
    )

    personal = edit(client, without, "add-data", activity=DOMAIN_CLASSIFICATION, direction="in",
                    label="Customer question", classification="PersonalData")
    assert findings(client, personal) == shipped, (
        "re-declaring it as personal data did not bring the finding back"
    )

    anonymised = edit(client, without, "add-data", activity=DOMAIN_CLASSIFICATION, direction="in",
                      label="Customer question", classification="AnonymisedData")
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
    """Deleting one architecture from a two-system scene."""
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


def test_a_database_classified_on_the_process_reaches_the_architecture(client) -> None:
    """A data store carries its classification like a data object does."""
    base = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix dpv:  <https://w3id.org/dpv#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:   <http://example.org/store-bridge#> .

ex:Sys a beam:Element , beam:System ; rdfs:label "S" ;
    beam:hasProcess ex:Step ; beam:hasResource ex:In .
ex:In a beam:Element , beam:Data ; rdfs:label "In" ; pair:playsRole pair:UserInput .
ex:Step a beam:Element , beam:Infer ; rdfs:label "Step" ;
    pair:playsRole pair:PredictionStep ; beam:use ex:In ; beam:produce ex:Out .
ex:Out a beam:Element , beam:Data ; rdfs:label "Out" ; pair:playsRole pair:PredictionResult .

ex:Proc a bpmn:process ; bp:name "P" ; bp:contains ex:Act .
ex:Act a bpmn:serviceTask ; bp:name "A" ; pair:refinedBy ex:Sys ;
    bp:dataInputAssociation ex:Assoc .
ex:Assoc a bpmn:dataInputAssociation ; bp:sourceRef ex:Ref ; bp:targetRef ex:Act .
ex:Item a bpmn:itemDefinition ; bp:structureRef dpv:PersonalData .
"""
    shapes = {
        "store": base + """
ex:Ref a bpmn:dataStoreReference ; bp:dataStoreRef ex:Thing .
ex:Thing a bpmn:dataStore ; bp:name "Customer DB" ; bp:itemSubjectRef ex:Item .
""",
        "object": base + """
ex:Ref a bpmn:dataObjectReference ; bp:dataObjectRef ex:Thing .
ex:Thing a bpmn:dataObject ; bp:name "Customer DB" ; bp:itemSubjectRef ex:Item .
""",
    }

    def derived(ttl: str) -> int:
        summary = client.post("/api/assess", json={"ttl": ttl}).get_json()["summary"]
        return summary["derivedCategoryCount"]

    for label, ttl in shapes.items():
        assert derived(ttl) > 0, (
            f"a {label} classified as personal data derived no data category"
        )

    # And the exclusion still holds: saying it is not personal is a claim too,
    # and it must not collapse into the silence of never having said anything.
    assert derived(shapes["store"].replace("dpv:PersonalData", "dpv:AnonymisedData")) == 0, (
        "an anonymised store still derived a category"
    )
