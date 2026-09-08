"""Drawing the rest of BPMN, not only the boxes a motif reads."""

from __future__ import annotations

import pytest
from rdflib import RDF, RDFS, Graph, URIRef

from airiskkg.paths import REPO_ROOT, SBPMN_DIR
from conftest import process_path  # noqa: E402

pytestmark = pytest.mark.ui

CONTEXT = process_path("energy_customer_service")
EC = "http://w3id.org/airiskkg/example/energy-cs#"
CHATBOT_POOL = EC + "ChatbotPool"
AGENT_CHAIN_LANE = EC + "AgentChainLane"
SEND_ANSWER = EC + "SendAnswer"
DOCUMENT_RETRIEVAL = EC + "DocumentRetrieval"
DOMAIN_CLASSIFICATION = EC + "DomainClassification"
PAIR_REFINED_BY = URIRef("http://w3id.org/airiskkg/pair-ai#refinedBy")
BEAM_NS = "http://w3id.org/beam/core#"
CLASSES = "https://sBPMN.github.io/2.0/classes#"
PROPS = "https://sBPMN.github.io/2.0/properties#"


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


@pytest.fixture(scope="module")
def process_ttl() -> str:
    return CONTEXT.read_text(encoding="utf-8")


def edit(client, ttl: str, op: str, **payload) -> str:
    response = client.post("/api/process-edit", json={"ttl": ttl, "op": op, **payload})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["ttl"]


def view(client, ttl: str) -> dict:
    return client.post("/api/process", json={"ttl": ttl}).get_json()


def added(before: list, after: list) -> dict:
    """The one row the edit created, found by id rather than by position."""
    fresh = [row for row in after if row["id"] not in {r["id"] for r in before}]
    assert len(fresh) == 1, f"expected exactly one new element, got {len(fresh)}"
    return fresh[0]


# --- what the palette can now put on the canvas -------------------------------

def test_an_event_arrives_with_the_trigger_it_was_asked_for(client, process_ttl) -> None:
    before = view(client, process_ttl)
    after = view(client, edit(client, process_ttl, "add-event", pool=CHATBOT_POOL,
                              kind="intermediateCatchEvent", definition="timer", label="Wait a day"))
    event = added(before["events"], after["events"])

    assert event["kind"] == "intermediateCatchEvent"
    assert event["definition"] == "timer", "the trigger did not survive the round trip"
    assert event["throwing"] is False, "a catching event must not be drawn as a throwing one"


def test_a_gateway_keeps_the_kind_that_decides_how_it_is_drawn(client, process_ttl) -> None:
    """Exclusive and inclusive are different claims - one path or several - and
    the diamond glyph is the only place a reader is told which."""
    before = view(client, process_ttl)
    after = view(client, edit(client, process_ttl, "add-gateway", pool=CHATBOT_POOL,
                              kind="parallelGateway", label="Both at once"))
    gateway = added(before["gateways"], after["gateways"])

    assert gateway["kind"] == "parallelGateway"
    assert gateway["label"] == "Both at once"


def test_a_new_node_lands_in_the_lane_that_was_selected(client, process_ttl) -> None:
    """A lane says who does the work."""
    before = view(client, process_ttl)
    after = view(client, edit(client, process_ttl, "add-gateway", pool=CHATBOT_POOL,
                              lane=AGENT_CHAIN_LANE, kind="exclusiveGateway", label="Answered?"))
    gateway = added(before["gateways"], after["gateways"])

    assert gateway["laneId"] == AGENT_CHAIN_LANE
    lane = next(row for row in after["lanes"] if row["id"] == AGENT_CHAIN_LANE)
    assert gateway["id"] in lane["members"]


def test_a_lane_can_be_added_to_a_pool_that_has_lanes_already(client, process_ttl) -> None:
    before = view(client, process_ttl)
    after = view(client, edit(client, process_ttl, "add-lane", pool=CHATBOT_POOL, label="Escalation"))
    lane = added(before["lanes"], after["lanes"])

    assert lane["label"] == "Escalation"
    assert lane["process"], "the lane was created outside any process"


def test_a_boundary_event_is_pinned_to_the_activity_it_watches(client, process_ttl) -> None:
    """It has no position of its own: drawn anywhere but on the border of its
    host it says nothing about which step can be interrupted."""
    before = view(client, process_ttl)
    after = view(client, edit(client, process_ttl, "add-event", kind="boundaryEvent",
                              definition="error", attachedTo=SEND_ANSWER, interrupting=True))
    event = added(before["events"], after["events"])

    assert event["attachedTo"] == SEND_ANSWER
    assert event["interrupting"] is True
    host = next(a for a in after["activities"] if a["id"] == SEND_ANSWER)
    assert event["id"] in host["boundary"], "the host does not know what is attached to it"


def test_a_boundary_event_without_a_host_is_refused(client, process_ttl) -> None:
    response = client.post("/api/process-edit", json={
        "ttl": process_ttl, "op": "add-event", "pool": CHATBOT_POOL, "kind": "boundaryEvent",
    })
    assert response.status_code == 400
    assert "attached" in response.get_json()["error"]


def test_a_note_says_something_about_a_step_without_being_one(client, process_ttl) -> None:
    after = view(client, edit(client, process_ttl, "add-annotation", pool=CHATBOT_POOL,
                              attachedTo=SEND_ANSWER, text="Nobody reads this before it goes out"))
    note = next(a for a in after["artifacts"] if a["kind"] == "textAnnotation")

    assert note["text"] == "Nobody reads this before it goes out"
    assert any(link["target"] == note["id"] for link in after["associations"])
    assert note["id"] not in {a["id"] for a in after["activities"]}, "a note is not a step of work"


# --- changing what is already there -------------------------------------------

def test_retyping_a_node_keeps_everything_else_it_carries(client, process_ttl) -> None:
    """A retype that dropped the flows would silently detach the step from the
    process, and the canvas would still draw a box."""
    before = next(g for g in view(client, process_ttl)["gateways"] if g["label"])
    joined = [f for f in view(client, process_ttl)["sequenceFlows"]
              if before["id"] in (f["source"], f["target"])]

    after = view(client, edit(client, process_ttl, "set-node-type", element=before["id"],
                              kind="exclusiveGateway", label=before["label"]))
    retyped = next(g for g in after["gateways"] if g["id"] == before["id"])

    assert retyped["kind"] == "exclusiveGateway"
    assert retyped["label"] == before["label"]
    still = [f for f in after["sequenceFlows"] if before["id"] in (f["source"], f["target"])]
    assert len(still) == len(joined), "the retype dropped the flows the node was on"


def test_a_repetition_marker_survives_the_round_trip(client, process_ttl) -> None:
    after = view(client, edit(client, process_ttl, "set-loop",
                              activity=EC + "DocumentRetrieval", loop="multiParallel"))
    activity = next(a for a in after["activities"] if a["id"] == EC + "DocumentRetrieval")
    assert activity["markers"]["loop"] == "multiParallel"

    cleared = view(client, edit(client, process_ttl, "set-loop",
                                activity=EC + "DocumentRetrieval", loop=""))
    activity = next(a for a in cleared["activities"] if a["id"] == EC + "DocumentRetrieval")
    assert activity["markers"]["loop"] is None


def test_deleting_an_activity_takes_its_boundary_events_with_it(client, process_ttl) -> None:
    """A boundary event outliving its host is attached to nothing, and would be
    drawn floating at the coordinates of a box that is gone."""
    with_event = edit(client, process_ttl, "add-event", kind="boundaryEvent",
                      definition="error", attachedTo=SEND_ANSWER)
    event = next(e for e in view(client, with_event)["events"] if e["attachedTo"] == SEND_ANSWER)

    after = view(client, edit(client, with_event, "delete", element=SEND_ANSWER))
    assert event["id"] not in {e["id"] for e in after["events"]}


# --- a document is not a database --------------------------------------------

def test_data_can_be_created_as_a_store_rather_than_a_document(client, process_ttl) -> None:
    """BPMN draws a document as a folded page and a database as a cylinder, and
    they are different claims about where the data lives. The editor could
    write only the page, so saying "this comes out of a database" meant
    hand-writing three BPMN nodes in Turtle."""
    after = view(client, edit(client, process_ttl, "add-data", activity=DOCUMENT_RETRIEVAL,
                              direction="in", label="Ticket archive", shape="store",
                              classification="PersonalData"))
    row = next(r for a in after["activities"] if a["id"] == DOCUMENT_RETRIEVAL
               for r in a["reads"] if r["label"] == "Ticket archive")

    assert row["store"] is True, "asked for a data store and got a document"
    assert row["kinds"] == ["PersonalData"], "a store cannot carry its classification"


def test_changing_the_shape_keeps_what_a_finding_reads(client, process_ttl) -> None:
    """The classification and the associations are what reach the assessment, so
    a change of shape must not disturb them: it is a statement about what the
    data is, not about what reads it."""
    before = view(client, process_ttl)
    document = next(r for a in before["activities"] if a["id"] == DOMAIN_CLASSIFICATION
                    for r in a["reads"] if r["kinds"])
    assert document["store"] is False, "the fixture no longer starts from a document"

    after = view(client, edit(client, process_ttl, "set-data-shape",
                              reference=document["id"], shape="store"))
    row = next(r for a in after["activities"] if a["id"] == DOMAIN_CLASSIFICATION
               for r in a["reads"] if r["id"] == document["id"])

    assert row["store"] is True, "the document was not retyped as a store"
    assert row["kinds"] == document["kinds"], "the classification was lost in the retype"
    assert row["label"] == document["label"], "the name was lost in the retype"

    back = view(client, edit(client, after and process_ttl, "set-data-shape",
                             reference=document["id"], shape="object"))
    restored = next(r for a in back["activities"] if a["id"] == DOMAIN_CLASSIFICATION
                    for r in a["reads"] if r["id"] == document["id"])
    assert restored["store"] is False, "a store cannot be turned back into a document"


# --- giving an activity an architecture ---------------------------------------

def test_an_activity_can_be_given_a_new_architecture(client, process_ttl) -> None:
    """The business layer is where a system is called for."""
    after = edit(client, process_ttl, "add-system",
                 activity=DOMAIN_CLASSIFICATION, label="Domain classifier")
    graph = Graph().parse(data=after, format="turtle")

    minted = [
        s for s in graph.subjects(RDF.type, URIRef("http://w3id.org/beam/core#System"))
        if str(s).startswith("http://w3id.org/airiskkg/local#")
    ]
    assert len(minted) == 1, f"expected one new system, got {minted}"
    system = minted[0]
    assert str(graph.value(system, RDFS.label)) == "Domain classifier"
    assert (URIRef(DOMAIN_CLASSIFICATION), PAIR_REFINED_BY, system) in graph, (
        "the new system is not bound to the activity that asked for it"
    )


def test_a_new_element_lands_in_the_architecture_on_screen(client, process_ttl) -> None:
    """A document carries several architectures once a business process runs
    more than one system. add-element fell back to the first `beam:System`
    rdflib happened to yield, so drawing inside the second one filed every
    element under the first, silently."""
    two = edit(client, process_ttl, "add-system", activity=DOMAIN_CLASSIFICATION, label="First")
    two = edit(client, two, "add-system", activity=DOCUMENT_RETRIEVAL, label="Second")
    graph = Graph().parse(data=two, format="turtle")
    systems = {
        str(graph.value(s, RDFS.label)): s
        for s in graph.subjects(RDF.type, URIRef("http://w3id.org/beam/core#System"))
        if str(s).startswith("http://w3id.org/airiskkg/local#")
    }
    assert set(systems) == {"First", "Second"}, f"expected two systems, got {sorted(systems)}"

    response = client.post("/api/graph-edit", json={
        "ttl": two, "op": "add-element", "label": "Draft the reply", "category": "process",
        "classUri": "http://w3id.org/beam/core#Infer", "system": str(systems["Second"]),
    })
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    grown = Graph().parse(data=body["ttl"], format="turtle")
    element = URIRef(body["newId"])
    has_process = URIRef("http://w3id.org/beam/core#hasProcess")

    assert (systems["Second"], has_process, element) in grown, (
        "the element did not land in the architecture it was added to"
    )
    assert (systems["First"], has_process, element) not in grown, (
        "the element was filed under the other architecture as well"
    )


def test_adding_to_a_system_that_is_not_there_is_refused(client, process_ttl) -> None:
    response = client.post("/api/graph-edit", json={
        "ttl": process_ttl, "op": "add-element", "label": "Stray", "category": "process",
        "classUri": "http://w3id.org/beam/core#Infer",
        "system": "http://w3id.org/airiskkg/local#nosuchsystem",
    })
    assert response.status_code == 400
    assert "not in this graph" in response.get_json()["error"]


# --- drawing the architecture first -------------------------------------------

def test_a_system_can_be_created_named_and_described_from_the_canvas(client) -> None:
    """The architecture-first route, and what a system says about itself.

    add-system on /api/process-edit needs an activity to bind, which is the
    wrong way round for someone who draws the architecture and only then models
    the process it serves: elements landed in no system, and the business layer
    then had nothing to offer under "Carried out by".

    `beam:description` and `beam:context` are declared on System and every
    shipped example fills them in, but graph_view served neither and nothing
    edited them - so naming an architecture meant writing Turtle by hand."""
    empty = "@prefix beam: <http://w3id.org/beam/core#> ." + chr(10)
    created = client.post("/api/graph-edit", json={
        "ttl": empty, "op": "add-system", "label": "Tariff conversation agent",
    })
    assert created.status_code == 200, created.get_json()
    ttl = created.get_json()["ttl"]
    system = created.get_json()["newId"]

    # An element added while it is on screen belongs to it.
    grown = client.post("/api/graph-edit", json={
        "ttl": ttl, "op": "add-element", "category": "process",
        "classUri": "http://w3id.org/beam/core#Infer", "label": "Explain conditions",
        "system": system,
    })
    assert grown.status_code == 200, grown.get_json()
    ttl = grown.get_json()["ttl"]

    described = client.post("/api/graph-edit", json={
        "ttl": ttl, "op": "edit-element", "element": system,
        "label": "Tariff conversation agent",
        "description": "Answers the customer in chat.",
        "context": "Public self-service portal.",
    })
    assert described.status_code == 200, described.get_json()
    ttl = described.get_json()["ttl"]

    view = client.post("/api/graph", json={"ttl": ttl}).get_json()
    assert len(view["systems"]) == 1, view["systems"]
    row = view["systems"][0]
    assert row["label"] == "Tariff conversation agent"
    assert row["description"] == "Answers the customer in chat.", (
        "a system's description is not served, so the canvas cannot show it"
    )
    assert row["context"] == "Public self-service portal."
    assert len(row["members"]) == 1, "the element did not land in the system on screen"

    # And the business layer can now point an activity at it.
    process = ttl + """
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix local: <http://w3id.org/airiskkg/local#> .
local:poolX a bpmn:participant ; bp:name "Wien Energie" ; bp:processRef local:procX .
local:procX a bpmn:process ; bp:name "P" ; bp:contains local:actX .
local:actX a bpmn:serviceTask ; bp:name "Explain condition" .
"""
    offered = client.post("/api/process", json={"ttl": process}).get_json()
    assert "Tariff conversation agent" in {s["label"] for s in offered["unrefinedSystems"]}, (
        "an architecture drawn first is not offered under 'Carried out by'"
    )

    joined = client.post("/api/process-edit", json={
        "ttl": process, "op": "set-refines",
        "activity": "http://w3id.org/airiskkg/local#actX", "system": system,
    })
    assert joined.status_code == 200, joined.get_json()
    after = client.post("/api/process", json={"ttl": joined.get_json()["ttl"]}).get_json()
    activity = next(a for a in after["activities"] if a["id"].endswith("actX"))
    assert activity["refines"] == [system], (
        f"the activity was not connected to the architecture: {activity['refines']}"
    )


def test_a_new_system_can_take_in_the_elements_that_belong_to_nowhere(client) -> None:
    """Naming an architecture you have just opened means "this is it"."""
    ttl = (
        '@prefix beam: <http://w3id.org/beam/core#> .' + chr(10)
        + '@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .' + chr(10)
        + '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .' + chr(10)
        + '@prefix ex:   <http://example.org/orphans#> .' + chr(10)
        + 'ex:Doc a beam:Data ; rdfs:label "Doc" ;' + chr(10)
        + '    pair:playsRole pair:UserInput .' + chr(10)
        + 'ex:Step a beam:Transform ; rdfs:label "Step" ;' + chr(10)
        + '    pair:playsRole pair:RetrievalStep ;' + chr(10)
        + '    beam:use ex:Doc ; beam:produce ex:Out .' + chr(10)
        + 'ex:Out a beam:Data ; rdfs:label "Out" ;' + chr(10)
        + '    pair:playsRole pair:RetrievedContext .' + chr(10)
    )
    before = client.post("/api/graph", json={"ttl": ttl}).get_json()
    assert before["systems"] == [], "the fixture already has a system"
    assert len(before["unclaimed"]) == 3, before["unclaimed"]

    # Typed the way a BEAM export types them: beam:Data and beam:Transform, no
    # beam:Element anywhere. Keying adoption on beam:Element adopted nothing.
    assert "beam:Element" not in ttl

    adopted = client.post("/api/graph-edit", json={
        "ttl": ttl, "op": "add-system", "label": "Taxonomy Expansion", "adopt": True,
    })
    assert adopted.status_code == 200, adopted.get_json()
    after = client.post("/api/graph", json={"ttl": adopted.get_json()["ttl"]}).get_json()

    assert after["unclaimed"] == [], (
        f"the new system left {len(after['unclaimed'])} element(s) belonging to nowhere"
    )
    assert len(after["systems"]) == 1
    assert len(after["systems"][0]["members"]) == 3, after["systems"][0]

    # A process is held as a process and data as a resource, not all as one.
    graph = Graph().parse(data=adopted.get_json()["ttl"], format="turtle")
    system = URIRef(adopted.get_json()["newId"])
    processes = {str(o) for o in graph.objects(system, URIRef(BEAM_NS + "hasProcess"))}
    resources = {str(o) for o in graph.objects(system, URIRef(BEAM_NS + "hasResource"))}
    assert processes == {"http://example.org/orphans#Step"}, processes
    assert resources == {"http://example.org/orphans#Doc", "http://example.org/orphans#Out"}

    # And not adopting stays available, for splitting one architecture in two.
    plain = client.post("/api/graph-edit", json={
        "ttl": ttl, "op": "add-system", "label": "Second half",
    })
    still = client.post("/api/graph", json={"ttl": plain.get_json()["ttl"]}).get_json()
    assert len(still["unclaimed"]) == 3, "add-system adopted without being asked"


# --- and it must still be sBPMN ----------------------------------------------

def test_every_edit_writes_only_terms_sbpmn_declares(client, process_ttl) -> None:
    """The bundled examples are checked for this in test_business_context.py."""
    onto = Graph()
    for path in sorted(SBPMN_DIR.glob("*.ttl")):
        onto.parse(path, format="turtle")

    ttl = process_ttl
    for op, payload in [
        ("add-lane", {"pool": CHATBOT_POOL, "label": "Escalation"}),
        ("add-event", {"pool": CHATBOT_POOL, "kind": "endEvent", "definition": "terminate"}),
        ("add-event", {"kind": "boundaryEvent", "definition": "timer", "attachedTo": SEND_ANSWER}),
        ("add-gateway", {"pool": CHATBOT_POOL, "kind": "eventBasedGateway"}),
        ("add-annotation", {"pool": CHATBOT_POOL, "text": "A note", "attachedTo": SEND_ANSWER}),
        ("add-data", {"activity": DOCUMENT_RETRIEVAL, "direction": "in",
                      "label": "Archive", "shape": "store", "classification": "PersonalData"}),
        ("set-loop", {"activity": EC + "DocumentRetrieval", "loop": "multiSequential"}),
    ]:
        ttl = edit(client, ttl, op, **payload)

    written = Graph().parse(data=ttl, format="turtle")
    undeclared = sorted({
        str(o) for _s, _p, o in written.triples((None, RDF.type, None))
        if str(o).startswith(CLASSES) and (o, RDF.type, URIRef(
            "http://www.w3.org/2002/07/owl#Class")) not in onto
    })
    assert not undeclared, f"classes sBPMN does not define: {undeclared}"

    unknown = sorted({
        str(p) for _s, p, _o in written
        if str(p).startswith(PROPS) and (URIRef(str(p)), RDF.type, None) not in onto
    })
    assert not unknown, f"properties sBPMN does not declare: {unknown}"

    # Declared is not enough: bp:cancelActivity is real and means nothing on a
    # start event, and bp:default is refused on a parallel gateway.
    from rdflib import RDFS

    def ancestors(cls):
        seen, frontier = {cls}, [cls]
        while frontier:
            for parent in onto.objects(frontier.pop(), RDFS.subClassOf):
                if parent not in seen:
                    seen.add(parent)
                    frontier.append(parent)
        return seen

    violations = []
    for predicate in {p for _s, p, _o in written if str(p).startswith(PROPS)}:
        domains = list(onto.objects(predicate, RDFS.domain))
        if not domains:
            continue
        for subject, _p, _o in written.triples((None, predicate, None)):
            types = set(written.objects(subject, RDF.type))
            if types and not any(any(d in ancestors(t) for d in domains) for t in types):
                violations.append(f"{predicate} on {subject}")
    assert not violations, "written outside the domain sBPMN declares: " + "; ".join(
        sorted(violations))
