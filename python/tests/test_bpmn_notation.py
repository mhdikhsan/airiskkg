"""The BPMN 2.0 notation beyond plain process flow: what the view serves, and
what the editor writes for it."""

from __future__ import annotations

import pytest
from rdflib import Graph

from bpmn_notation import NOTATION_TTL, NS
from test_bpmn_authoring import CHATBOT_POOL, CONTEXT, edit, sbpmn_violations, view

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


@pytest.fixture(scope="module")
def drawn(client) -> dict:
    return view(client, NOTATION_TTL)


def row(rows: list[dict], name: str) -> dict:
    return next(r for r in rows if r["id"] == NS + name)


def test_the_notation_document_is_itself_sbpmn() -> None:
    """Otherwise the tests below would pin a reading of terms sBPMN never declared."""
    assert not sbpmn_violations(Graph().parse(data=NOTATION_TTL, format="turtle"))


# --- events --------------------------------------------------------------------

def test_an_event_with_several_triggers_is_multiple(drawn) -> None:
    """BPMN has no Multiple class: two definitions on one event are the claim,
    and drawing only the first one said the event waits for that alone."""
    start = row(drawn["events"], "Arrives")
    assert start["definition"] == "multiple"
    assert start["definitions"] == ["message", "signal"]

    end = row(drawn["events"], "Done")
    assert (end["definition"], end["throwing"]) == ("multiple", True)


def test_parallel_multiple_waits_for_all_of_them(drawn) -> None:
    both = row(drawn["events"], "Both")
    assert both["definition"] == "parallelMultiple"
    assert both["definitions"] == ["conditional", "message"]


def test_a_start_that_does_not_interrupt_says_so(drawn) -> None:
    changed = row(drawn["events"], "Changed")
    assert changed["interrupting"] is False
    assert changed["parent"] == NS + "Watch"
    assert row(drawn["activities"], "Watch")["markers"]["eventSubProcess"] is True
    assert row(drawn["events"], "Arrives")["interrupting"] is True, "unstated must mean interrupting"


def test_a_message_flow_names_its_message(drawn) -> None:
    assert [(f["id"], f["message"]) for f in drawn["messageFlows"]] == [(NS + "Ask", "Order")]


# --- choreography --------------------------------------------------------------

def test_a_choreography_task_has_a_band_per_participant(drawn) -> None:
    """The initiator goes on top: BPMNDI decides it in BPMN, and sBPMN does not
    carry BPMNDI. Each band says what its participant sends."""
    quote = row(drawn["choreographyActivities"], "Quote")
    assert quote["kind"] == "choreographyTask"
    assert quote["loop"] == "standard"
    assert [(b["label"], b["initiating"], b["multiple"], b["message"]) for b in quote["bands"]] == [
        ("Recipient", True, False, "Quote request"),
        ("Courier", False, True, "Quote"),
    ]


def test_every_kind_of_choreography_activity_is_served(drawn) -> None:
    kinds = {r["id"].removeprefix(NS): (r["kind"], r["loop"]) for r in drawn["choreographyActivities"]}
    assert kinds == {
        "Quote": ("choreographyTask", "standard"),
        "Settle": ("subChoreography", "multiParallel"),
        "Agree": ("callChoreography", None),
    }
    assert row(drawn["choreographyActivities"], "Agree")["bands"][0]["label"] == "Courier"


def test_a_choreography_is_laid_out_like_a_process(drawn) -> None:
    """Its events and its flow belong to it, so the canvas ranks them the same way."""
    assert [(c["id"], c["label"]) for c in drawn["choreographies"]] == [(NS + "Delivery", "Delivery")]
    for name in ("Begin", "End"):
        assert row(drawn["events"], name)["process"] == NS + "Delivery"
    for activity in drawn["choreographyActivities"]:
        assert activity["process"] == NS + "Delivery"
    flows = {(f["source"], f["target"]) for f in drawn["sequenceFlows"]}
    assert (NS + "Quote", NS + "Settle") in flows


def test_a_participant_named_only_on_bands_gets_no_pool(drawn) -> None:
    """A choreography diagram draws no pools. A participant something else reaches,
    by a message flow or a conversation, keeps its pool."""
    band_only = {p["label"] for p in drawn["participants"] if p["bandOnly"]}
    assert band_only == {"Courier", "Recipient"}
    assert NS + "QuoteAsked" not in {f["id"] for f in drawn["messageFlows"]}, (
        "a choreography task's own message flow was drawn again between pools"
    )


# --- conversation --------------------------------------------------------------

def test_a_conversation_is_joined_to_every_participant_it_names(drawn) -> None:
    """A link drawn is a conversationLink; a participant named with no link of
    its own is joined anyway, because the reference is the claim."""
    kinds = {c["id"].removeprefix(NS): c["kind"] for c in drawn["conversations"]}
    assert kinds == {"Talk": "conversation", "Pay": "subConversation", "Ship": "callConversation"}
    links = {(l["source"].removeprefix(NS), l["target"].removeprefix(NS), bool(l["id"]))
             for l in drawn["conversationLinks"]}
    assert links == {
        ("Shop", "Talk", True), ("Customer", "Talk", False),
        ("Shop", "Pay", False), ("Bank", "Pay", False), ("Shop", "Ship", False),
    }


# --- editing -------------------------------------------------------------------

def _event(client, ttl: str, label: str) -> dict:
    return next(e for e in view(client, ttl)["events"] if e["label"] == label)


def test_an_event_can_be_given_several_triggers(client) -> None:
    ttl = edit(client, CONTEXT.read_text(encoding="utf-8"), "add-event", pool=CHATBOT_POOL,
               kind="startEvent", label="Asked", definition="parallelMultiple",
               definitions=["timer", "message"])
    event = _event(client, ttl, "Asked")
    assert (event["definition"], event["definitions"]) == ("parallelMultiple", ["message", "timer"])

    # The editor sends back what it shows, so a rename keeps the triggers.
    renamed = edit(client, ttl, "set-node-type", element=event["id"], kind="startEvent",
                   label="Asked again", definition="parallelMultiple",
                   definitions=event["definitions"])
    assert _event(client, renamed, "Asked again")["definitions"] == ["message", "timer"]

    single = edit(client, renamed, "set-node-type", element=event["id"], kind="startEvent",
                  label="Asked again", definition="timer")
    again = _event(client, single, "Asked again")
    assert (again["definition"], again["definitions"]) == ("timer", ["timer"])
    assert "parallelMultiple" not in single, "a single trigger kept the parallel flag"


@pytest.mark.parametrize("kind, definition, definitions, why", [
    ("endEvent", "parallelMultiple", ["message", "signal"], "catching"),
    ("startEvent", "multiple", ["message"], "two triggers"),
])
def test_a_multiple_event_the_notation_cannot_say_is_refused(
        client, kind, definition, definitions, why) -> None:
    response = client.post("/api/process-edit", json={
        "ttl": CONTEXT.read_text(encoding="utf-8"), "op": "add-event", "pool": CHATBOT_POOL,
        "kind": kind, "definition": definition, "definitions": definitions,
    })
    assert response.status_code == 400
    assert why in response.get_json()["error"]


def test_a_start_event_can_say_it_does_not_interrupt(client) -> None:
    ttl = edit(client, NOTATION_TTL, "set-node-type", element=NS + "Changed", kind="startEvent",
               label="Order changed", definition="message")
    assert _event(client, ttl, "Order changed")["interrupting"] is False, (
        "an edit that did not mention interrupting dropped it"
    )
    ttl = edit(client, ttl, "set-node-type", element=NS + "Changed", kind="startEvent",
               label="Order changed", definition="message", interrupting=True)
    assert _event(client, ttl, "Order changed")["interrupting"] is True


def test_an_event_sub_process_can_be_added_and_retyped(client) -> None:
    before = view(client, CONTEXT.read_text(encoding="utf-8"))["activities"]
    ttl = edit(client, CONTEXT.read_text(encoding="utf-8"), "add-activity",
               pool=CHATBOT_POOL, kind="eventSubProcess")
    added = next(a for a in view(client, ttl)["activities"]
                 if a["id"] not in {b["id"] for b in before})
    assert (added["kind"], added["markers"]["eventSubProcess"]) == ("subProcess", True)

    retyped = edit(client, ttl, "set-node-type", element=added["id"], kind="task",
                   label=added["label"])
    assert not sbpmn_violations(Graph().parse(data=retyped, format="turtle")), (
        "a task kept bp:triggeredByEvent, which sBPMN declares on a sub-process only"
    )
