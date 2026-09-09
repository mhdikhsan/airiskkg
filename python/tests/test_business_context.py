"""The business process layer, over a process that really exists."""

from __future__ import annotations

from collections import Counter

import pytest
from rdflib import RDF, Graph

from airiskkg.assessment_runner import PAIR, load_base_graph, run_assessment
from airiskkg.paths import EXAMPLE_DIR
from conftest import TARIFF_NS, WIEN_ENERGIE_NS, example_path, process_path  # noqa: E402

# Resolved rather than located: these two retired from the shipped example set
# and are kept as test fixtures, so the coverage they back did not retire with
# them. process_path finds either home.
PROCESS = process_path("energy_customer_service")
TARIFF_PROCESS = process_path("energy_tariff_change")
IMPROPER_OUTPUT = "ImproperOutputHandlingRiskPattern"
DISCLOSURE = "SensitiveInformationDisclosureRiskPattern"

# An approval the shipped process does not have.
REVIEW = """
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix ec:   <http://w3id.org/airiskkg/example/energy-cs#> .

ec:ApproveAnswer a bpmn:userTask ;
    bp:name "Check the answer before it goes out" ;
    bp:incoming ec:RFlow1 ;
    bp:outgoing ec:RFlow2 ;
    bp:dataInputAssociation ec:AnswerToApprove ;
    bp:resourceRole ec:ChatbotAdministrator .

ec:AnswerToApprove a bpmn:dataInputAssociation ;
    bp:sourceRef ec:AnswerRef ; bp:targetRef ec:ApproveAnswer .

ec:RFlow1 a bpmn:sequenceFlow ;
    bp:sourceRef ec:ExplanationGeneration ; bp:targetRef ec:ApproveAnswer .

ec:RFlow2 a bpmn:sequenceFlow ;
    bp:sourceRef ec:ApproveAnswer ; bp:targetRef ec:SendAnswer .
"""


def _short(term) -> str:
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _findings_by_pattern(result) -> Counter:
    counts: Counter = Counter()
    for finding in result.risk_findings.subjects(RDF.type, PAIR.RiskFinding):
        counts[_short(result.risk_findings.value(finding, PAIR.generatedByRiskPattern))] += 1
    return counts


def _assess(process_turtle: str):
    """Assess the architecture together with a process given as text."""
    from airiskkg.assessment_runner import _run_assessment_on_graph

    graph = load_base_graph()
    graph.parse(example_path(WIEN_ENERGIE_NS), format="turtle")
    graph.parse(data=process_turtle, format="turtle")
    return _run_assessment_on_graph(graph, write_outputs=False, output_dir=".")


@pytest.fixture(scope="module")
def architecture_only():
    return run_assessment(example_path(WIEN_ENERGIE_NS), write_outputs=False)


@pytest.fixture(scope="module")
def with_process():
    return run_assessment([example_path(WIEN_ENERGIE_NS), PROCESS], write_outputs=False)


def test_the_bridge_vocabulary_is_loaded_and_declared() -> None:
    """The context module and the vendored sBPMN ontology both reach the graph."""
    graph = load_base_graph()

    assert (PAIR.refinedBy, RDF.type, None) in graph
    assert (PAIR.businessFollows, RDF.type, None) in graph
    from rdflib import OWL, URIRef

    assert (URIRef("https://sBPMN.github.io/2.0/classes#userTask"), RDF.type, OWL.Class) in graph


def test_a_bpmn_activity_is_not_a_beam_process() -> None:
    """The layering mistake that would undo the whole idea."""
    from rdflib import RDFS, URIRef

    graph = load_base_graph()
    beam_process = URIRef("http://w3id.org/beam/core#Process")
    activity = URIRef("https://sBPMN.github.io/2.0/classes#activity")

    assert beam_process not in set(graph.transitive_objects(activity, RDFS.subClassOf))


def test_the_architecture_alone_is_unchanged(architecture_only) -> None:
    """The baseline the whole library is measured against."""
    assert architecture_only.motif_match_count == 5
    assert architecture_only.risk_finding_count == 9


def test_context_carries_no_flow_facts_of_its_own(architecture_only) -> None:
    """Nothing is derived over a process that was never submitted."""
    derived = list(architecture_only.working_graph.triples((None, PAIR.businessFollows, None)))
    assert derived == []


def test_business_flow_closes_transitively(with_process) -> None:
    """Reachability closed over the chatbot's chain and the customer's."""
    derived = list(with_process.working_graph.triples((None, PAIR.businessFollows, None)))
    assert len(derived) > 10


# --- what the process raises --------------------------------------------------


def test_the_process_raises_what_the_pipeline_could_not(architecture_only, with_process) -> None:
    """Route 1, and the reason the layer is worth having."""
    before = _findings_by_pattern(architecture_only)
    after = _findings_by_pattern(with_process)

    assert before[DISCLOSURE] == 0
    assert after[DISCLOSURE] == 1

    assert with_process.motif_match_count == architecture_only.motif_match_count
    for pattern in set(before) | set(after):
        if pattern != DISCLOSURE:
            assert before[pattern] == after[pattern], f"{pattern} moved unexpectedly"


def test_the_architecture_gains_no_triples_from_being_described(with_process) -> None:
    """The process is read, not merged. No step is invented in the pipeline."""
    architecture = Graph().parse(example_path(WIEN_ENERGIE_NS), format="turtle")
    steps_before = set(architecture.subjects(PAIR.playsRole, None))
    steps_after = {
        subject
        for subject in with_process.working_graph.subjects(PAIR.playsRole, None)
        if str(subject).startswith("http://w3id.org/airiskkg/example/wien-energie#")
    }
    assert steps_after == steps_before


def test_a_business_data_annotation_reaches_the_architecture_it_refines() -> None:
    """The annotation is made on the business data object; the category lands on
    the architecture's input and travels from there like any other."""
    alone = run_assessment(example_path(WIEN_ENERGIE_NS), write_outputs=False)
    with_context = run_assessment([example_path(WIEN_ENERGIE_NS), PROCESS], write_outputs=False)

    def sensitive(result):
        return {
            _short(e)
            for e in result.working_graph.subjects(
                PAIR.containsDataCategory, PAIR.SensitiveInformation
            )
        }

    gained = sensitive(with_context) - sensitive(alone)
    assert "Question" in gained, "the customer question never became sensitive"
    assert "Answer" in gained, "sensitivity did not travel to what the chatbot says back"


def test_the_bridge_records_where_the_annotation_came_from() -> None:
    """A derived category with no trace is a claim the modeller cannot argue with."""
    from rdflib import Namespace

    prov = Namespace("http://www.w3.org/ns/prov#")
    result = run_assessment([example_path(WIEN_ENERGIE_NS), PROCESS], write_outputs=False)

    derivations = list(result.working_graph.subjects(RDF.type, prov.Derivation))
    business = [
        d
        for d in derivations
        if any("energy-cs" in str(e) for e in result.working_graph.objects(d, prov.entity))
    ]
    assert business, "no derivation points back at a business data object"


# --- what the process does not clear ------------------------------------------


def test_a_human_step_that_is_not_a_review_clears_nothing(with_process) -> None:
    """The shipped process has a human in it: when the chatbot cannot answer, an
    administrator takes the conversation over in live chat. It is a userTask, it
    is performed by a person, and it is downstream of an activity the chatbot
    carries out - three of the four things the escape asks for. It still must
    not clear the finding, because it never reads what was generated."""
    view = _process_activities()
    takeover = next(a for a in view if a["label"] == "Take over the conversation in live chat")
    assert takeover["human"], "the takeover stopped being a human task"

    assert _findings_by_pattern(with_process)[IMPROPER_OUTPUT] == 1


def test_an_approval_that_reads_the_answer_clears_what_the_pipeline_cannot() -> None:
    """And the other half: a review that does read the draft does clear it,
    without asserting anything into the architecture and without a negative
    facet condition (R10)."""
    process = PROCESS.read_text(encoding="utf-8")

    assert _findings_by_pattern(_assess(process))[IMPROPER_OUTPUT] == 1
    assert _findings_by_pattern(_assess(process + REVIEW))[IMPROPER_OUTPUT] == 0


# --- the escape must be precise, not merely permissive -----------------------

MUTATIONS = {
    "the review is a serviceTask, not a userTask": (
        "ec:ApproveAnswer a bpmn:userTask ;",
        "ec:ApproveAnswer a bpmn:serviceTask ;",
    ),
    "the review reads the question, not the drafted answer": (
        "    bp:sourceRef ec:AnswerRef ; bp:targetRef ec:ApproveAnswer .",
        "    bp:sourceRef ec:QuestionRef ; bp:targetRef ec:ApproveAnswer .",
    ),
    "the review happens before the answer is generated": (
        "    bp:sourceRef ec:ExplanationGeneration ; bp:targetRef ec:ApproveAnswer .",
        "    bp:sourceRef ec:ApproveAnswer ; bp:targetRef ec:ExplanationGeneration .",
    ),
}

PROCESS_MUTATIONS = {
    "the reviewer is not a person": (
        "ec:ChatbotAdministrator a bpmn:humanPerformer ;",
        "ec:ChatbotAdministrator a bpmn:resource ;",
    ),
    "the activity is not linked to the system": (
        "    pair:refinedBy we:AgentChain ;\n    bp:incoming ec:SFlowMerged ;",
        "    rdfs:seeAlso we:AgentChain ;\n    bp:incoming ec:SFlowMerged ;",
    ),
}


@pytest.mark.parametrize("description", sorted(MUTATIONS))
def test_breaking_one_thing_the_review_claims_brings_the_finding_back(description) -> None:
    """Each mutation breaks exactly one claim the approval makes."""
    original, replacement = MUTATIONS[description]
    assert original in REVIEW, f"the review no longer contains: {original!r}"
    process = PROCESS.read_text(encoding="utf-8") + REVIEW.replace(original, replacement)

    assert _findings_by_pattern(_assess(process))[IMPROPER_OUTPUT] == 1, (
        f"the escape still fired after breaking: {description}"
    )


@pytest.mark.parametrize("description", sorted(PROCESS_MUTATIONS))
def test_breaking_one_thing_the_process_provides_brings_the_finding_back(description) -> None:
    """The other two claims are made by the shipped process rather than by the
    review: who the performer is, and whether the activity names an
    architecture at all."""
    original, replacement = PROCESS_MUTATIONS[description]
    process = PROCESS.read_text(encoding="utf-8")
    assert original in process, f"the example no longer contains: {original!r}"

    mutated = process.replace(original, replacement) + REVIEW
    assert _findings_by_pattern(_assess(mutated))[IMPROPER_OUTPUT] == 1, (
        f"the escape still fired after breaking: {description}"
    )


# --- actors, messages, and nesting -------------------------------------------
#
# "The chatbot answers the customer" is two participants exchanging messages,
# not two lanes of one process. Modelled as lanes it would still draw, and the
# arrow between the customer and the company would be inexpressible.


def _process_view():
    from airiskkg.workbench.process_view import process_view

    graph = Graph()
    graph.parse(example_path(WIEN_ENERGIE_NS), format="turtle")
    graph.parse(PROCESS, format="turtle")
    return process_view(graph)


def _process_activities():
    return _process_view()["activities"]


@pytest.fixture(scope="module")
def energy_view():
    return _process_view()


def test_two_actors_each_with_their_own_process(energy_view) -> None:
    """One scenario per file: the customer asking, and the chatbot answering."""
    labels = [p["label"] for p in energy_view["participants"]]
    assert labels == ["Wien Energie Chatbot", "Wien Energie customer"]
    assert all(p["process"] for p in energy_view["participants"])


def test_messages_cross_the_boundary_between_actors(energy_view) -> None:
    """What a pool boundary is for."""
    by_activity = {a["id"]: a["label"] for a in energy_view["activities"]}
    pairs = {
        (by_activity[m["source"]], by_activity[m["target"]]) for m in energy_view["messageFlows"]
    }
    assert ("Ask a question", "Receive the question") in pairs
    assert ("Send the answer", "Read the answer") in pairs


def test_the_ai_activity_is_a_subprocess_that_expands_two_ways(energy_view) -> None:
    """Both are true and they answer different questions: the inner flow says
    what the step does as business steps, pair:refinedBy says which AI system
    carries them out. The diagram gives both - Figure 2 draws the steps, and the
    page behind it expands two of them."""
    classification = next(
        a for a in energy_view["activities"] if a["label"] == "Domain classification"
    )

    assert classification["refines"], "the subprocess names no architecture"
    assert len(classification["children"]) == 2, "the subprocess has no business steps of its own"
    for child in classification["children"]:
        inner = next(a for a in energy_view["activities"] if a["id"] == child)
        assert inner["parent"] == classification["id"]


def test_a_choice_between_sources_is_a_gateway_not_three_tasks(energy_view) -> None:
    """The routing step decides which source answers, and the paper says a question may need both at once."""
    gateway = next(
        g for g in energy_view["gateways"] if g["label"] == "Which source can answer?"
    )
    assert gateway["kind"] == "inclusiveGateway", "an exclusive split cannot use both sources"

    leaving = [f for f in energy_view["sequenceFlows"] if f["source"] == gateway["id"]]
    assert len(leaving) == 3
    assert all(f["condition"] for f in leaving), "a branch with no condition says nothing"

    routing = next(
        a for a in energy_view["activities"] if a["label"] == "Answer source identification"
    )
    assert routing["refines"], "the step still names the architecture that decides"
    assert not routing["children"], "the choice belongs to the gateway now"


def test_the_customers_pool_is_not_confused_with_the_chatbots(energy_view) -> None:
    processes = {p["participant"]: p["id"] for p in energy_view["processes"]}
    customer_side = [
        a for a in energy_view["activities"] if a["process"] == processes["Wien Energie customer"]
    ]

    assert {a["label"] for a in customer_side} == {"Ask a question", "Read the answer"}


def test_the_lanes_of_the_diagram_survive(energy_view) -> None:
    """The two lanes are the shape of the paper's Figure 2: a chain of LLM
    agents, and the sources it queries. The third holds the human."""
    lanes = {lane["label"] for lane in energy_view["lanes"]}
    assert {"LLM agent chain", "Answer source", "Chatbot administration"} <= lanes


def test_the_example_only_uses_sbpmn_terms_sbpmn_declares() -> None:
    """Conformance, checked rather than claimed."""
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


# --- one process, several AI systems -----------------------------------------
#
# The case the layer exists for, and the paper counts them the same way: an LLM
# agent chain that decides where an answer comes from, and the two answer
# sources it queries. Nobody can see that while each is assessed in a window of
# its own.


def test_the_process_points_its_activities_at_more_than_one_system(energy_view) -> None:
    refined = {a["label"]: a["refines"] for a in energy_view["activities"] if a["refines"]}
    systems = {system for targets in refined.values() for system in targets}

    assert len(systems) == 3, f"expected three systems, got {sorted(systems)}"
    assert refined["Knowledge graph query"] != refined["Document retrieval (RAG)"], (
        "the two answer sources point at the same architecture"
    )


def test_the_two_answer_sources_carry_different_risks() -> None:
    """A curated graph and a pile of vectorised PDFs are not the same problem,
    and a reader who sees them side by side should not have to be told so."""
    result = run_assessment([example_path(WIEN_ENERGIE_NS), PROCESS], write_outputs=False)

    vector_findings = [
        finding
        for finding in result.risk_findings.subjects(RDF.type, PAIR.RiskFinding)
        if _short(result.risk_findings.value(finding, PAIR.generatedByRiskPattern))
        == "VectorAndEmbeddingWeaknessRiskPattern"
    ]
    assert vector_findings, "the document store raised no vector-side finding"

    evidence = {
        _short(e)
        for finding in vector_findings
        for e in result.risk_findings.objects(finding, PAIR.hasEvidence)
    }
    assert "DocumentStore" in evidence
    assert "KnowledgeGraph" not in evidence, "a knowledge graph has no embeddings to be weak"


def test_findings_reach_the_activity_each_system_carries_out() -> None:
    """What makes a finding communicable: the box in the process it arises
    under, not the name of a step inside an architecture."""
    from airiskkg.assessment_view import summarize_result

    result = run_assessment([example_path(WIEN_ENERGIE_NS), PROCESS], write_outputs=False)
    rows = {row["label"]: row for row in summarize_result(result)["findingsByActivity"]}

    assert rows["Document retrieval (RAG)"]["findings"], "the RAG source was attributed nothing"
    assert rows["Knowledge graph query"]["findings"], "the graph source was attributed nothing"
    assert rows["Answer generation"]["findings"] > rows["Knowledge graph query"]["findings"], (
        "the chain that writes the answer should carry more than one source does"
    )


# --- the tariff change scenario ----------------------------------------------
#
# The other half of the use case, and the one that shows why a system boundary
# is not bookkeeping. A customer service agent approves the change before it
# takes effect - but they read the checked form, not the text the agent wrote
# to the customer. Those belong to different systems, so the approval clears
# the one and not the other. Merge the two and the escape fires on both, which
# would report an explanation as reviewed that nobody ever read.

TARIFF_REVIEW = """
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix ec:   <http://w3id.org/airiskkg/example/energy-cs#> .

ec:DraftExplanationRef a bpmn:dataObjectReference ;
    bp:name "Drafted explanation" .

ec:DraftExplanationOut a bpmn:dataOutputAssociation ;
    bp:sourceRef ec:ExplainConditions ; bp:targetRef ec:DraftExplanationRef .

ec:ExplanationToApprove a bpmn:dataInputAssociation ;
    bp:sourceRef ec:DraftExplanationRef ; bp:targetRef ec:ChangePlan .

ec:ExplainConditions bp:dataOutputAssociation ec:DraftExplanationOut .
ec:ChangePlan bp:dataInputAssociation ec:ExplanationToApprove .
"""


def _assess_tariff(process_turtle: str):
    from airiskkg.assessment_runner import _run_assessment_on_graph

    graph = load_base_graph()
    graph.parse(example_path(TARIFF_NS), format="turtle")
    graph.parse(data=process_turtle, format="turtle")
    return _run_assessment_on_graph(graph, write_outputs=False, output_dir=".")


def test_the_tariff_process_raises_without_clearing() -> None:
    """Personal data in the chat and on the account reaches what the assistant says back."""
    tariff = example_path(TARIFF_NS)
    alone = _findings_by_pattern(run_assessment(tariff, write_outputs=False))
    with_context = _findings_by_pattern(
        run_assessment([tariff, TARIFF_PROCESS], write_outputs=False)
    )

    assert alone[IMPROPER_OUTPUT] == 2 and alone[DISCLOSURE] == 0
    assert with_context[DISCLOSURE] == 2, "the personal data annotation raised nothing"
    assert with_context[IMPROPER_OUTPUT] == 2, (
        "the agent approves the change, not the chat text, so it clears neither reply"
    )


def test_an_approval_that_reads_the_reply_is_what_clears_it() -> None:
    """Same process, same person, one more thing on their desk: the drafted reply."""
    process = TARIFF_PROCESS.read_text(encoding="utf-8")

    assert _findings_by_pattern(_assess_tariff(process))[IMPROPER_OUTPUT] == 2
    assert _findings_by_pattern(_assess_tariff(process + TARIFF_REVIEW))[IMPROPER_OUTPUT] == 0


def test_the_tariff_process_names_a_system_for_each_capability() -> None:
    """Four systems, because the diagram separates four things: the agent that
    talks, the rules that decide, the form machinery and the record service.
    Attribution is the point - the risk sits on the agent, not on the form."""
    from airiskkg.assessment_view import summarize_result
    from airiskkg.workbench.process_view import process_view

    graph = Graph()
    graph.parse(example_path(TARIFF_NS), format="turtle")
    graph.parse(TARIFF_PROCESS, format="turtle")
    refined = {a["label"]: a["refines"] for a in process_view(graph)["activities"] if a["refines"]}
    assert len({s for targets in refined.values() for s in targets}) == 4

    result = run_assessment([example_path(TARIFF_NS), TARIFF_PROCESS], write_outputs=False)
    rows = {row["label"]: row["findings"] for row in summarize_result(result)["findingsByActivity"]}
    assert rows["Explain the conditions"] > 0, "the agent that writes to the customer carries none"
    assert rows["Check the contract conditions"] == 0, "the rules check carries the chat findings"
    assert rows["Show the change form"] == 0, "the form machinery carries the chat findings"
