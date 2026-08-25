"""The business process layer: a control that lives in the process, not the pipeline.

Three claims, and each is a test below.

  1. The layer is additive. An architecture assessed alone gives exactly what it
     gave before the layer existed. This is the property everything else rests
     on - a context layer that silently moved the baseline would make every
     recorded assessment incomparable with every later one.
  2. A human review expressed only in the business process clears a finding the
     architecture cannot clear, without asserting anything into the architecture
     and without a negative facet condition (R10).
  3. It clears it for the right reasons. "Findings went down" proves nothing on
     its own: a condition that is merely too permissive clears just as
     thoroughly as a correct one.
"""

from __future__ import annotations

from collections import Counter

import pytest
from rdflib import RDF, Graph

from airiskkg.assessment_runner import PAIR, load_base_graph, run_assessment
from airiskkg.paths import EXAMPLE_DIR
from conftest import GRAPH_RAG_NS, example_path  # noqa: E402

PROCESS = EXAMPLE_DIR / "context" / "energy_customer_service.ttl"
IMPROPER_OUTPUT = "ImproperOutputHandlingRiskPattern"


def _short(term) -> str:
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _findings_by_pattern(result) -> Counter:
    counts: Counter = Counter()
    for finding in result.risk_findings.subjects(RDF.type, PAIR.RiskFinding):
        counts[_short(result.risk_findings.value(finding, PAIR.generatedByRiskPattern))] += 1
    return counts


@pytest.fixture(scope="module")
def architecture_only():
    return run_assessment(example_path(GRAPH_RAG_NS), write_outputs=False)


@pytest.fixture(scope="module")
def with_process():
    return run_assessment([example_path(GRAPH_RAG_NS), PROCESS], write_outputs=False)


def test_the_bridge_vocabulary_is_loaded_and_declared() -> None:
    """The context module and the vendored sBPMN ontology both reach the graph."""
    graph = load_base_graph()

    assert (PAIR.refinedBy, RDF.type, None) in graph
    assert (PAIR.businessFollows, RDF.type, None) in graph
    from rdflib import OWL, URIRef

    assert (URIRef("https://sBPMN.github.io/2.0/classes#userTask"), RDF.type, OWL.Class) in graph


def test_a_bpmn_activity_is_not_a_beam_process() -> None:
    """The layering mistake that would undo the whole idea. Every match query
    types its step as `a/rdfs:subClassOf* beam:Process`, so subsuming activities
    under it would make every business activity a candidate motif node - and the
    input contract, which requires each beam:Process to use or produce a
    resource, would reject every process model outright."""
    from rdflib import RDFS, URIRef

    graph = load_base_graph()
    beam_process = URIRef("http://w3id.org/beam/core#Process")
    activity = URIRef("https://sBPMN.github.io/2.0/classes#activity")

    assert beam_process not in set(graph.transitive_objects(activity, RDFS.subClassOf))


def test_the_architecture_alone_is_unchanged(architecture_only) -> None:
    """The baseline the whole library is measured against."""
    assert architecture_only.motif_match_count == 3
    assert architecture_only.risk_finding_count == 7


def test_context_carries_no_flow_facts_of_its_own(architecture_only) -> None:
    """Nothing is derived over a process that was never submitted."""
    derived = list(architecture_only.working_graph.triples((None, PAIR.businessFollows, None)))
    assert derived == []


def test_business_flow_closes_transitively(with_process) -> None:
    """Reachability closed over the retailer's chain and the customer's.

    A gateway or an intervening step between the AI activity and a later control
    must not hide it, and SPARQL cannot type the nodes a property path passes
    through - so the closure is built by the derivation loop instead."""
    derived = list(with_process.working_graph.triples((None, PAIR.businessFollows, None)))
    assert len(derived) > 10


def test_a_review_in_the_process_clears_what_the_pipeline_cannot(
    architecture_only, with_process
) -> None:
    before = _findings_by_pattern(architecture_only)
    after = _findings_by_pattern(with_process)

    assert before[IMPROPER_OUTPUT] == 1
    assert after[IMPROPER_OUTPUT] == 0

    # Onyx has one generation step and one user-facing output; the finding fires
    # four times because that step binds in four motif matches. They share a
    # sink, so they clear together - and nothing else moves.
    assert with_process.motif_match_count == architecture_only.motif_match_count
    for pattern in set(before) | set(after):
        if pattern != IMPROPER_OUTPUT:
            assert before[pattern] == after[pattern], f"{pattern} moved unexpectedly"


def test_the_architecture_gains_no_triples_from_being_reviewed(with_process) -> None:
    """The review clears the finding by being represented, not by being written
    into the pipeline. No control step is invented."""
    architecture = Graph().parse(example_path(GRAPH_RAG_NS), format="turtle")
    steps_before = set(architecture.subjects(PAIR.playsRole, None))
    steps_after = {
        subject
        for subject in with_process.working_graph.subjects(PAIR.playsRole, None)
        if str(subject).startswith("http://tool4boxology.org/Component/")
    }
    assert steps_after == steps_before


# --- the escape must be precise, not merely permissive -----------------------

MUTATIONS = {
    "the review is a serviceTask, not a userTask": (
        "ec:ReviewReply a bpmn:userTask ;",
        "ec:ReviewReply a bpmn:serviceTask ;",
    ),
    "the reviewer is not a person": (
        "ec:SupportAgent a bpmn:humanPerformer ;",
        "ec:SupportAgent a bpmn:resource ;",
    ),
    "the review reads the enquiry, not the drafted reply": (
        "    bp:sourceRef ec:DraftRef ; bp:targetRef ec:ReviewReply .",
        "    bp:sourceRef ec:EnquiryRef ; bp:targetRef ec:ReviewReply .",
    ),
    "the review happens before the AI drafts": (
        "    bp:sourceRef ec:CustomerService ; bp:targetRef ec:ReviewReply .",
        "    bp:sourceRef ec:ReviewReply ; bp:targetRef ec:CustomerService .",
    ),
    "the activity is not linked to the system": (
        "    pair:refinedBy sgr:graphrag-example ;",
        "    rdfs:seeAlso sgr:graphrag-example ;",
    ),
}


@pytest.mark.parametrize("description", sorted(MUTATIONS))
def test_breaking_one_thing_the_escape_requires_brings_the_finding_back(description) -> None:
    """Each mutation breaks exactly one claim the escape makes. The fourth is the
    one that matters: "close the ticket" is also a later human task, and it must
    not count as having reviewed anything."""
    original, replacement = MUTATIONS[description]
    process = PROCESS.read_text(encoding="utf-8")
    assert original in process, f"the example no longer contains: {original!r}"

    graph = load_base_graph()
    graph.parse(example_path(GRAPH_RAG_NS), format="turtle")
    graph.parse(data=process.replace(original, replacement), format="turtle")

    from airiskkg.assessment_runner import _run_assessment_on_graph

    result = _run_assessment_on_graph(graph, write_outputs=False, output_dir=".")
    assert _findings_by_pattern(result)[IMPROPER_OUTPUT] == 1, (
        f"the escape still fired after breaking: {description}"
    )


# --- actors, messages, and nesting -------------------------------------------
#
# "The retailer answers the customer" is two participants exchanging messages,
# not two lanes of one process. Modelled as lanes it would still draw, and the
# arrow between the two organisations would be inexpressible.

ENERGY_PROCESS = PROCESS


@pytest.fixture(scope="module")
def energy_view():
    from airiskkg.workbench.process_view import process_view

    graph = Graph()
    graph.parse(example_path(GRAPH_RAG_NS), format="turtle")
    graph.parse(PROCESS, format="turtle")
    return process_view(graph)


def test_two_actors_each_with_their_own_process(energy_view) -> None:
    labels = [p["label"] for p in energy_view["participants"]]
    assert labels == ["Customer", "Northwind Energy"]
    assert all(p["process"] for p in energy_view["participants"])


def test_messages_cross_the_boundary_between_actors(energy_view) -> None:
    """What a pool boundary is for. A message flow is the only way to say the
    company answered the customer; sequence flow cannot leave a process."""
    by_activity = {a["id"]: a["label"] for a in energy_view["activities"]}
    pairs = {
        (by_activity[m["source"]], by_activity[m["target"]])
        for m in energy_view["messageFlows"]
    }
    assert ("Ask a question", "Receive the enquiry") in pairs
    assert ("Send the reply", "Read the answer") in pairs


def test_the_ai_activity_is_a_subprocess_that_expands_two_ways(energy_view) -> None:
    """Both are true and they answer different questions: the inner flow says
    what the service does as business steps, pair:refinedBy says which AI system
    carries them out."""
    # Two sub-processes now - one per AI system - so name the one under test
    # rather than taking whichever comes first.
    chatbot = next(
        a for a in energy_view["activities"] if a["label"] == "Customer service chatbot"
    )

    assert chatbot["refines"], "the subprocess names no architecture"
    assert len(chatbot["children"]) == 3, "the subprocess has no business steps of its own"
    for child in chatbot["children"]:
        inner = next(a for a in energy_view["activities"] if a["id"] == child)
        assert inner["parent"] == chatbot["id"]


def test_the_customers_pool_is_not_confused_with_the_retailers(energy_view) -> None:
    processes = {p["participant"]: p["id"] for p in energy_view["processes"]}
    customer_side = [a for a in energy_view["activities"] if a["process"] == processes["Customer"]]

    assert {a["label"] for a in customer_side} == {"Ask a question", "Read the answer"}


def test_the_review_step_is_what_moves_the_count() -> None:
    """One business step is the whole difference. Without the process the reply
    goes out as generated; with it, an agent reads the draft first."""
    alone = run_assessment(example_path(GRAPH_RAG_NS), write_outputs=False)
    with_context = run_assessment(
        [example_path(GRAPH_RAG_NS), ENERGY_PROCESS], write_outputs=False
    )

    assert alone.risk_finding_count == 7 and with_context.risk_finding_count == 6
    assert alone.motif_match_count == with_context.motif_match_count == 3


def test_the_example_only_uses_sbpmn_terms_sbpmn_declares() -> None:
    """Conformance, checked rather than claimed.

    A process model is only interoperable if it says things the ontology
    actually defines - otherwise it is BPMN-shaped Turtle that no other tool
    reads. Every property is checked against the domain and range sBPMN itself
    declares, and every class against sBPMN's own class list."""
    from rdflib import OWL, RDFS, URIRef

    from airiskkg.paths import SBPMN_DIR

    onto = Graph()
    for path in sorted(SBPMN_DIR.glob("*.ttl")):
        onto.parse(path, format="turtle")
    example = Graph().parse(PROCESS, format="turtle")

    classes_ns = "https://sBPMN.github.io/2.0/classes#"
    props_ns = "https://sBPMN.github.io/2.0/properties#"

    def ancestors(cls):
        seen, frontier = {cls}, [cls]
        while frontier:
            for parent in onto.objects(frontier.pop(), RDFS.subClassOf):
                if parent not in seen:
                    seen.add(parent)
                    frontier.append(parent)
        return seen

    undeclared_classes = [
        str(o)
        for _s, _p, o in example.triples((None, RDF.type, None))
        if str(o).startswith(classes_ns) and (o, RDF.type, OWL.Class) not in onto
    ]
    assert not undeclared_classes, f"classes sBPMN does not define: {undeclared_classes}"

    violations = []
    for predicate in {p for _s, p, _o in example if str(p).startswith(props_ns)}:
        assert (predicate, RDF.type, None) in onto, f"undeclared property: {predicate}"
        domains = list(onto.objects(predicate, RDFS.domain))
        ranges = list(onto.objects(predicate, RDFS.range))
        for subject, _p, obj in example.triples((None, predicate, None)):
            types = set(example.objects(subject, RDF.type))
            if domains and not any(any(d in ancestors(t) for d in domains) for t in types):
                violations.append(f"domain: {predicate} on {subject}")
            if ranges and isinstance(obj, URIRef):
                obj_types = set(example.objects(obj, RDF.type))
                if obj_types and not any(any(r in ancestors(t) for r in ranges) for t in obj_types):
                    violations.append(f"range: {predicate} -> {obj}")
    assert not violations, "sBPMN violations:\n" + "\n".join(sorted(violations))


# --- one process, two AI systems ---------------------------------------------
#
# The case the layer exists for. A business process usually runs more than one
# AI capability, they are rarely the same kind of thing, and their risks have
# almost nothing in common - which nobody can see while each architecture is
# assessed in a window of its own.

ANOMALY_NS_LOCAL = "http://w3id.org/airiskkg/example/meter-anomaly#"


def test_the_process_points_two_activities_at_two_different_systems() -> None:
    from airiskkg.workbench.process_view import process_view

    graph = Graph()
    graph.parse(example_path(GRAPH_RAG_NS), format="turtle")
    graph.parse(example_path(ANOMALY_NS_LOCAL), format="turtle")
    graph.parse(PROCESS, format="turtle")
    view = process_view(graph)

    refined = {a["label"]: a["refines"] for a in view["activities"] if a["refines"]}
    assert len(refined) == 2, f"expected two AI activities, got {sorted(refined)}"
    systems = {system for targets in refined.values() for system in targets}
    assert len(systems) == 2, "both activities point at the same architecture"


def test_each_architecture_still_assesses_on_its_own() -> None:
    """Refinement adds context; it does not make an architecture dependent on the
    process. Either one alone is still a complete, assessable graph."""
    chatbot = run_assessment(example_path(GRAPH_RAG_NS), write_outputs=False)
    anomaly = run_assessment(example_path(ANOMALY_NS_LOCAL), write_outputs=False)

    assert (chatbot.motif_match_count, chatbot.risk_finding_count) == (3, 7)
    assert (anomaly.motif_match_count, anomaly.risk_finding_count) == (4, 1)


def test_the_two_systems_carry_different_risks() -> None:
    """An ML serving shape and a generative one are not the same problem, and a
    reader who sees them side by side should not have to be told so."""
    chatbot = _findings_by_pattern(run_assessment(example_path(GRAPH_RAG_NS), write_outputs=False))
    anomaly = _findings_by_pattern(run_assessment(example_path(ANOMALY_NS_LOCAL), write_outputs=False))

    assert "PromptInjectionRiskPattern" in chatbot
    assert "PromptInjectionRiskPattern" not in anomaly
    assert set(anomaly) == {"SupplyChainCompromiseRiskPattern"}


# --- context declared once, in the business model -----------------------------


def test_a_business_data_annotation_reaches_the_architecture_it_refines() -> None:
    """Route 1, and the reason the layer is worth having. Consumption data says
    when a household is in and when it is empty, so it names a person - but the
    scoring architecture never said so, and no architecture modeller would know
    to. It is stated once, on the process, by whoever owns it."""
    architectures = [example_path(GRAPH_RAG_NS), example_path(ANOMALY_NS_LOCAL)]

    alone = run_assessment(architectures, write_outputs=False)
    with_context = run_assessment(architectures + [PROCESS], write_outputs=False)

    def sensitive(result):
        return {
            _short(e)
            for e in result.working_graph.subjects(PAIR.containsDataCategory, PAIR.SensitiveInformation)
        }

    gained = sensitive(with_context) - sensitive(alone)
    assert "Reading" in gained, "the meter reading never became sensitive"
    assert "Score_Result" in gained, "sensitivity did not travel to what the scorer produces"


def test_the_bridge_records_where_the_annotation_came_from() -> None:
    """A derived category with no trace is a claim the modeller cannot argue
    with. The derivation names the business data object it came from."""
    from rdflib import Namespace

    prov = Namespace("http://www.w3.org/ns/prov#")
    result = run_assessment(
        [example_path(GRAPH_RAG_NS), example_path(ANOMALY_NS_LOCAL), PROCESS], write_outputs=False
    )

    derivations = list(result.working_graph.subjects(RDF.type, prov.Derivation))
    business = [
        d for d in derivations
        if any("energy-cs" in str(e) for e in result.working_graph.objects(d, prov.entity))
    ]
    assert business, "no derivation points back at a business data object"


def test_context_both_clears_and_raises() -> None:
    """The honest shape of it. A human review in the process clears an
    output-handling finding; a data annotation in the same process raises a
    disclosure the architecture could not have known about. Reporting only the
    total would hide both."""
    architectures = [example_path(GRAPH_RAG_NS), example_path(ANOMALY_NS_LOCAL)]
    before = _findings_by_pattern(run_assessment(architectures, write_outputs=False))
    after = _findings_by_pattern(run_assessment(architectures + [PROCESS], write_outputs=False))

    assert before[IMPROPER_OUTPUT] == 1 and after[IMPROPER_OUTPUT] == 0
    assert after["SensitiveInformationDisclosureRiskPattern"] > before["SensitiveInformationDisclosureRiskPattern"]
