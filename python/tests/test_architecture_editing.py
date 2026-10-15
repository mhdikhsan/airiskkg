"""Drawing an architecture from nothing, and taking it apart again."""

from __future__ import annotations

import pytest
from rdflib import RDF, Graph, URIRef

pytestmark = pytest.mark.ui

BEAM = "http://w3id.org/beam/core#"
EX = "http://example.org/two-systems#"


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("flask")
    from airiskkg.webapp.app import create_app

    return create_app(local_examples=False).test_client()


def edit(client, ttl: str, op: str, **payload) -> dict:
    response = client.post("/api/graph-edit", json={"ttl": ttl, "op": op, **payload})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def add_data(client, ttl: str) -> dict:
    return edit(client, ttl, "add-element", classUri=BEAM + "Data", category="resource", label="Data")


def systems_of(ttl: str) -> set[URIRef]:
    return set(Graph().parse(data=ttl, format="turtle").subjects(RDF.type, URIRef(BEAM + "System")))


def test_deleting_the_last_element_does_not_lock_the_canvas(client) -> None:
    """Deleting the last element serializes to a bare newline, and every edit
    after that was refused with "Provide a graph to edit" until the page was
    reloaded: elements and motifs alike."""
    added = add_data(client, "")
    emptied = edit(client, added["ttl"], "delete-element", element=added["newId"])
    blank = emptied["ttl"] if emptied["ttl"].strip() else "\n"
    assert add_data(client, blank)["newId"]
    assert edit(client, "\n", "add-motif", motif="RetrievalAugmentedGenerationMotif")["newIds"]


def test_an_element_on_a_blank_canvas_lands_in_a_system(client) -> None:
    """An element in no system cannot be named by a business activity, and a
    blank canvas offered no way to draw the container first."""
    first = add_data(client, "")
    assert first["newSystem"], "no system was made for the first element"
    assert systems_of(first["ttl"]) == {URIRef(first["newSystem"])}
    view = client.post("/api/graph", json={"ttl": first["ttl"]}).get_json()
    assert view["unclaimed"] == [], "the first element was left in no system"

    second = add_data(client, first["ttl"])
    assert second["newSystem"] is None, "a second system was made while one was there"
    assert systems_of(second["ttl"]) == {URIRef(first["newSystem"])}


TWO_SYSTEMS = f"""
@prefix beam: <{BEAM}> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex:   <{EX}> .

ex:Chatbot a beam:System ; rdfs:label "Chatbot" ;
    beam:hasProcess ex:Answer ; beam:hasResource ex:Question, ex:Archive .
ex:Search a beam:System ; rdfs:label "Search" ;
    beam:hasProcess ex:Index ; beam:hasResource ex:Archive .
ex:Answer a beam:Infer ; rdfs:label "Answer" ; beam:use ex:Question, ex:Archive .
ex:Question a beam:Data ; rdfs:label "Question" .
ex:Archive a beam:Data ; rdfs:label "Archive" .
ex:Index a beam:Transform ; rdfs:label "Index" ; beam:produce ex:Archive .
"""


def test_deleting_a_system_takes_what_it_holds_and_keeps_what_another_holds(client) -> None:
    """A system is a container: deleting it left every element it held on the
    canvas, belonging to nothing."""
    after = Graph().parse(
        data=edit(client, TWO_SYSTEMS, "delete-element", element=EX + "Chatbot")["ttl"],
        format="turtle")
    subjects = {str(s).removeprefix(EX) for s in after.subjects()}

    assert not {"Chatbot", "Answer", "Question"} & subjects, "the system's own elements stayed"
    assert {"Search", "Index", "Archive"} <= subjects, "an element another system holds went too"
    assert (URIRef(EX + "Search"), URIRef(BEAM + "hasResource"), URIRef(EX + "Archive")) in after
