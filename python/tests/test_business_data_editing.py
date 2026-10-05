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


def test_a_data_association_joins_data_to_an_activity_and_nothing_else(client, tariff_ttl) -> None:
    """One gesture picks the connector from what it joins, so the ends have to be
    checked: dragging between two data boxes used to write a data association
    from data to data, which says nothing about who reads either one."""
    view = client.post("/api/process", json={"ttl": tariff_ttl}).get_json()
    data_ids = [row["id"] for row in view["dataNodes"]]
    activity = view["activities"][0]["id"]
    assert len(data_ids) >= 2, "this test needs two data boxes to drag between"

    def connect(source, target):
        return client.post("/api/process-edit", json={
            "ttl": tariff_ttl, "op": "connect", "source": source, "target": target,
        })

    refused = connect(data_ids[0], data_ids[1])
    assert refused.status_code == 400, "accepted a data-to-data association"

    # sBPMN declares the two data-association properties on activity plus one of
    # throwEvent / catchEvent; the canvas cannot tell those apart, so it joins
    # data to an activity only.
    for kind in ("events", "gateways"):
        for row in view.get(kind) or []:
            response = connect(data_ids[0], row["id"])
            assert response.status_code == 400, f"accepted a data association on a {kind[:-1]}"

    # The counterpart: joining data to an activity is still accepted, and where
    # it is not, the reason is that the step already reads it - never the ends.
    accepted = 0
    for reference in data_ids:
        for row in view["activities"]:
            response = connect(reference, row["id"])
            if response.status_code == 200:
                accepted += 1
                continue
            assert response.get_json()["error"] == "That step already uses this data.", (
                f"refused a well-formed data association: {response.get_json()}"
            )
    assert accepted, "no data box could be joined to any activity"


def test_an_unknown_classification_is_refused(client, tariff_ttl) -> None:
    """The picker is built from the same table the writer validates against, so
    anything else arriving here is a bug or a hand-made request."""
    response = client.post("/api/process-edit", json={
        "ttl": tariff_ttl, "op": "add-data", "activity": OFFER_HELP,
        "direction": "in", "label": "Whatever", "classification": "NotADpvTerm",
    })
    assert response.status_code == 400


def test_the_classification_is_what_moves_the_assessment(client, scene) -> None:
    """The whole reason the business layer exists.

    It is the classification that is taken away here, not the association. The
    fallback is coarse on purpose - one annotation marks every element content
    enters the refined system by - so detaching a reference from two of the
    activities that read it leaves the rest of them saying the same thing. What
    the annotation says is the thing under test.
    """
    shipped = findings(client, scene)

    without = edit(client, scene, "classify-data", reference=QUESTION_REF, classification="")
    assert findings(client, without) < shipped, (
        "removing the personal data the bridge reads changed no finding"
    )

    personal = edit(client, without, "classify-data",
                    reference=QUESTION_REF, classification="PersonalData")
    assert findings(client, personal) == shipped, (
        "re-declaring it as personal data did not bring the finding back"
    )

    anonymised = edit(client, without, "classify-data",
                      reference=QUESTION_REF, classification="AnonymisedData")
    assert findings(client, anonymised) == findings(client, without), (
        "anonymised data raised a sensitive-information category; the bridge excludes it"
    )


def test_the_picker_offers_exactly_what_the_writer_accepts(client) -> None:
    """Two lists that must not drift: one fills a dropdown, the other validates.

    Both are now read off the declarations in ontology/context/bpmn_context.ttl
    rather than typed in Python, which is what makes the offered set reviewable
    with the rest of the model - and what lets the bridge read the same fact
    instead of naming the non-personal terms a second time.
    """
    from airiskkg.workbench.process_view import data_class_names

    served = client.get("/api/vocabulary").get_json()["dataClasses"]
    offered = {row["id"] for row in served}
    assert offered == set(data_class_names())
    assert offered, "the editor offers no classification at all"
    for row in served:
        assert row["iri"].startswith("https://w3id.org/dpv#"), (
            f"{row['label']} does not write a DPV term: {row['iri']}"
        )
    # The distinction the bridge acts on has to survive the trip to the screen.
    assert {row["personal"] for row in served} == {True, False}


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


def test_the_editor_can_name_the_element_a_data_object_is(client, scene) -> None:
    """pair:realisedBy was declared, read by the bridge and tested, and nothing
    wrote it - so the only way to be exact was to hand-edit Turtle. The picker
    offers the resources of the architectures the reading activities refine, and
    nothing else: naming an element of a system this activity never touches
    would mark something the business layer says nothing about."""
    view = client.post("/api/process", json={"ttl": scene}).get_json()
    store = next(row for row in view["dataNodes"] if row["candidates"])
    chosen = store["candidates"][0]["id"]

    named = edit(client, scene, "realise-data", reference=store["id"], elements=[chosen])
    after = client.post("/api/process", json={"ttl": named}).get_json()
    row = next(r for r in after["dataNodes"] if r["id"] == store["id"])
    assert row["realisedBy"] == [chosen], "the element was not written"

    outside = next(
        row["id"]
        for row in view["dataNodes"]
        for row2 in [row]
        if row2["candidates"]
    )
    elsewhere = next(
        c["id"]
        for other in view["dataNodes"]
        for c in other["candidates"]
        if c["id"] not in {x["id"] for x in store["candidates"]}
    )
    refused = client.post("/api/process-edit", json={
        "ttl": scene, "op": "realise-data", "reference": outside, "elements": [elsewhere],
    })
    assert refused.status_code == 400, (
        "named an element of an architecture this activity does not refine"
    )

    cleared = edit(client, named, "realise-data", reference=store["id"], elements=[])
    back = client.post("/api/process", json={"ttl": cleared}).get_json()
    assert next(r for r in back["dataNodes"] if r["id"] == store["id"])["realisedBy"] == []


def test_a_system_says_what_it_is_for_from_the_business_view(client, scene) -> None:
    """Domain and purpose are declared about a beam:System, and an activity
    refines exactly one, so the business-to-architecture join is 1:1 - none of
    the ambiguity the data bridge has. The analyst knows the sector and the
    purpose; the architect knows how it was built.

    Written straight onto the system rather than derived from a business triple:
    a facet is an annotated base fact, and propagating one as a facet is the one
    thing the method does not do.
    """
    view = client.post("/api/process", json={"ttl": scene}).get_json()
    assert view["refinedSystems"], "no architecture is refined by this process"
    system = view["refinedSystems"][0]
    purposes = [o for o in view["contextOptions"] if o["facet"].endswith("hasPurpose")]
    assert purposes, "the editor offers no purpose to state"

    stated = edit(client, scene, "set-system-context",
                  system=system["id"], facet=purposes[0]["facet"], value=purposes[0]["value"])
    after = client.post("/api/process", json={"ttl": stated}).get_json()
    row = next(r for r in after["refinedSystems"] if r["id"] == system["id"])
    assert row["hasPurpose"] == [purposes[0]["value"]], "the purpose did not reach the system"

    invented = client.post("/api/process-edit", json={
        "ttl": scene, "op": "set-system-context", "system": system["id"],
        "facet": purposes[0]["facet"], "value": "https://example.org/made-up",
    })
    assert invented.status_code == 400, (
        "a term the editor does not offer was written: the picker and the writer "
        "have to read the same list"
    )

    cleared = edit(client, stated, "set-system-context",
                   system=system["id"], facet=purposes[0]["facet"], value="")
    back = client.post("/api/process", json={"ttl": cleared}).get_json()
    assert next(r for r in back["refinedSystems"] if r["id"] == system["id"])["hasPurpose"] == []
