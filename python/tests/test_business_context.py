"""The business process layer, over a process that really exists."""

from __future__ import annotations

from collections import Counter

import pytest
from rdflib import RDF, Graph, Namespace, URIRef

from airiskkg.assessment_runner import (
    PAIR,
    load_base_graph,
    run_assessment,
    run_assessment_from_text,
)
from airiskkg.assessment_view import summarize_result
from airiskkg.paths import EXAMPLE_DIR
from conftest import TARIFF_NS, WIEN_ENERGIE_NS, example_path, process_path  # noqa: E402

# Resolved rather than located: these two retired from the shipped example set
# and are kept as test fixtures, so the coverage they back did not retire with
# them. process_path finds either home.
PROCESS = process_path("energy_customer_service")
TARIFF_PROCESS = process_path("energy_tariff_change")
PROV = Namespace("http://www.w3.org/ns/prov#")
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
    # Two: the store reaches the user along both generation paths, the answer
    # and the explanation. One per path is how every other risk is counted.
    assert after[DISCLOSURE] == 2

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


# ---- naming the element a business data object is ----

# One architecture, two inputs, two activities - which is the shape the
# system-wide bridge cannot tell apart. Every shipped example happens to give a
# shared system exactly one input-playing element, so the coarseness never shows
# there; it shows the moment an architecture has two.
TWO_INPUTS = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix dpv:  <https://w3id.org/dpv#> .
@prefix ex:   <http://example.org/two#> .

ex:Assistant a beam:System ;
    beam:hasResource ex:ChatText , ex:UploadedFile , ex:Answer ;
    beam:hasProcess ex:Generate .
ex:ChatText a beam:Data ; pair:playsRole pair:UserInput .
ex:UploadedFile a beam:Data ; pair:playsRole pair:UserInput .
ex:Answer a beam:Data ; pair:playsRole pair:UserFacingOutput .
ex:Generate a beam:Generate ; beam:use ex:ChatText ; beam:produce ex:Answer .

ex:Chat a bpmn:serviceTask ;
    bp:name "Take the question" ;
    pair:refinedBy ex:Assistant ;
    bp:dataInputAssociation ex:ChatIn .
ex:ChatIn a bpmn:dataInputAssociation ;
    bp:sourceRef ex:ChatRef ; bp:targetRef ex:Chat .
ex:ChatRef a bpmn:dataObjectReference ; bp:dataObjectRef ex:TypedMessage .
ex:TypedMessage a bpmn:dataObject ;
    bp:name "Typed message" ;
    bp:itemSubjectRef ex:MessageItem .
ex:MessageItem a bpmn:itemDefinition ; bp:structureRef dpv:PersonalData .

ex:Upload a bpmn:serviceTask ;
    bp:name "Take the file" ;
    pair:refinedBy ex:Assistant .
"""

NAMED = """
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix ex:   <http://example.org/two#> .

ex:TypedMessage pair:realisedBy ex:ChatText .
"""


def _sensitive(ttl: str) -> set[str]:
    graph = run_assessment_from_text(ttl).combined_graph
    return {
        str(subject).split("#")[-1]
        for subject in graph.subjects(PAIR.containsDataCategory, PAIR.SensitiveInformation)
    }


def test_without_the_finer_join_every_input_of_the_system_is_marked() -> None:
    """The bridge maps an activity to a whole architecture, so a personal-data
    annotation on one activity reaches every input-playing element of the system
    it refines - including the ones that activity never reads."""
    marked = _sensitive(TWO_INPUTS)
    assert {"ChatText", "UploadedFile"} <= marked, (
        f"the coarse bridge marks both inputs: {sorted(marked)}"
    )


def test_naming_the_element_narrows_it_to_that_element() -> None:
    """pair:realisedBy says which element of the architecture a business data
    object is. Said, the annotation goes there and nowhere else."""
    marked = _sensitive(TWO_INPUTS + NAMED)
    assert "ChatText" in marked, "the element the data object names has to be marked"
    assert "UploadedFile" not in marked, (
        f"a file nothing declared personal is still marked: {sorted(marked)}"
    )


def test_naming_one_data_object_does_not_silence_the_others() -> None:
    """The fallback is per data object, not per graph: one annotation naming its
    element must not turn the coarse route off for an annotation that does not.
    Otherwise adding precision in one place loses coverage everywhere else."""
    both = TWO_INPUTS + NAMED + """
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix dpv:  <https://w3id.org/dpv#> .
@prefix ex:   <http://example.org/two#> .

ex:Upload bp:dataInputAssociation ex:FileIn .
ex:FileIn a bpmn:dataInputAssociation ;
    bp:sourceRef ex:FileRef ; bp:targetRef ex:Upload .
ex:FileRef a bpmn:dataObjectReference ; bp:dataObjectRef ex:CustomerFile .
ex:CustomerFile a bpmn:dataObject ;
    bp:name "Customer file" ;
    bp:itemSubjectRef ex:FileItem .
ex:FileItem a bpmn:itemDefinition ; bp:structureRef dpv:PersonalData .
"""
    marked = _sensitive(both)
    assert {"ChatText", "UploadedFile"} <= marked, (
        "the second annotation names no element, so it still reaches every input"
    )


def test_the_finer_join_changes_nothing_on_the_shipped_graphs() -> None:
    """Nothing shipped names its element, so the fallback decides both scenes.

    The energy scene moved to 11 on 2026-10-04 and the move is the point: the
    fallback used to reach only elements playing pair:UserInput or
    pair:PredictionRequest, four of the fifty resource-side roles, so a document
    store declared to hold personal data on the business process reached nothing
    at all. DocumentStore is now marked, its category travels the flow it
    already had, and the second sensitive-information-disclosure finding is the
    one that was previously invisible.
    """
    for architecture, process, matches, findings in (
        (TARIFF_NS, "energy_tariff_change", 3, 11),
        (WIEN_ENERGIE_NS, "energy_customer_service", 5, 11),
    ):
        result = run_assessment(
            [str(example_path(architecture)), str(process_path(process))],
            write_outputs=False,
        )
        summary = summarize_result(result)["summary"]
        assert (summary["motifMatchCount"], summary["riskFindingCount"]) == (matches, findings), (
            f"{architecture} moved to "
            f"{summary['motifMatchCount']}/{summary['riskFindingCount']}"
        )


# ---- what a business annotation can reach ----

# A store nobody calls an input, which is the shape the role test could not see:
# patient records, a case file, a document store. It is read by the system and
# produced by nothing in it, so it is where content crosses the edge.
STORE_NOT_AN_INPUT = """
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix dpv:  <https://w3id.org/dpv#> .
@prefix ex:   <http://example.org/records#> .

ex:Service a beam:System ;
    beam:hasResource ex:CaseFiles , ex:Retrieved , ex:Summary , ex:LLM ;
    beam:hasProcess ex:Retrieve , ex:Write .
ex:CaseFiles a beam:Data ; pair:playsRole pair:KnowledgeSource .
ex:Retrieved a beam:Data ; pair:playsRole pair:RetrievedContext .
ex:Summary a beam:Data ; pair:playsRole pair:UserFacingOutput , pair:LLMResponse .
ex:LLM a beam:StatisticalModel ; pair:playsRole pair:GenerativeModel , pair:FoundationLLM .
ex:Retrieve a beam:Transform ; pair:playsRole pair:RetrievalStep ;
    beam:use ex:CaseFiles ; beam:produce ex:Retrieved .
ex:Write a beam:Generate ; pair:playsRole pair:GenerationStep ;
    beam:use ex:Retrieved , ex:LLM ; beam:produce ex:Summary .

ex:Consult a bpmn:serviceTask ;
    bp:name "Consult the case file" ;
    pair:refinedBy ex:Service ;
    bp:dataInputAssociation ex:ConsultIn .
ex:ConsultIn a bpmn:dataInputAssociation ;
    bp:sourceRef ex:FileRef ; bp:targetRef ex:Consult .
ex:FileRef a bpmn:dataObjectReference ; bp:dataStoreRef ex:PatientRecords .
ex:PatientRecords a bpmn:dataStore ;
    bp:name "Patient records" ;
    bp:itemSubjectRef ex:RecordItem .
ex:RecordItem a bpmn:itemDefinition ; bp:structureRef dpv:MedicalHealth .
"""


def _marked(result) -> set[str]:
    """Elements the bridge put a category on, by local name."""
    graph = result.combined_graph
    out = set()
    for derivation in graph.subjects(RDF.type, PROV.Derivation):
        if graph.value(derivation, PAIR.derivedCategory) != PAIR.SensitiveInformation:
            continue
        if graph.value(derivation, PAIR.targetInferred) is None:
            continue  # a propagation derivation, not this bridge's
        for element in graph.subjects(PROV.qualifiedDerivation, derivation):
            out.add(str(element).rsplit("#", 1)[-1])
    return out


def test_a_store_carries_personal_data_without_anyone_calling_it_an_input() -> None:
    """Personal data does not only arrive as something a person typed.

    Patient records, a case file, a document store: necessary to the system,
    disclosure-relevant, and nobody's idea of user input. The fallback used to
    test for pair:UserInput or pair:PredictionRequest, four of the fifty
    resource-side roles, so a store reached nothing however it was annotated.
    """
    result = run_assessment_from_text(STORE_NOT_AN_INPUT)

    assert "CaseFiles" in _marked(result), (
        "the store the process declared as holding health records was not "
        "reached, so the annotation changed nothing"
    )
    assert "LLM" not in _marked(result), (
        "the model is read by the step that handles the records and sits on the "
        "same edge, but it contains nobody's health record"
    )
    # And it travels: facet:hasPersonalDataCategory is declared on beam:Data for
    # the same reason the bridge targets it, and content_categories.rq does the rest.
    categories = set(result.combined_graph.objects(
        URIRef("http://example.org/records#Summary"), PAIR.containsDataCategory))
    assert PAIR.SensitiveInformation in categories, (
        "the category reached the store but never travelled to the output"
    )


def test_the_derivation_says_whether_the_element_was_named_or_found() -> None:
    """Only one of those is somebody's claim. A reader who cannot tell them
    apart cannot tell a statement from a match."""
    found = run_assessment_from_text(STORE_NOT_AN_INPUT)
    graph = found.combined_graph
    inferred = [
        graph.value(d, PAIR.targetInferred)
        for d in graph.subjects(RDF.type, PROV.Derivation)
        if graph.value(d, PAIR.derivedCategory) == PAIR.SensitiveInformation
        and graph.value(d, PAIR.targetInferred) is not None
    ]
    assert inferred and all(bool(flag) for flag in inferred), (
        "nothing named an element here, so every derivation should say so"
    )

    named = run_assessment_from_text(
        STORE_NOT_AN_INPUT + "\nex:PatientRecords pair:realisedBy ex:CaseFiles .\n")
    graph = named.combined_graph
    flags = {
        str(graph.value(d, PAIR.targetInferred))
        for d in graph.subjects(RDF.type, PROV.Derivation)
        if graph.value(d, PAIR.derivedCategory) == PAIR.SensitiveInformation
        and graph.value(d, PAIR.targetInferred) is not None
    }
    assert flags == {"false"}, f"naming the element should stop it being a guess: {flags}"
    assert _marked(named) == {"CaseFiles"}, "the named element and no other"


def test_what_an_activity_writes_is_annotated_too() -> None:
    """A record a step writes carries the same kind of content as one it reads,
    and sBPMN runs the two associations in opposite directions. Reading only the
    input side left a step that produces a patient summary saying nothing."""
    writes = STORE_NOT_AN_INPUT.replace(
        "    bp:dataInputAssociation ex:ConsultIn .",
        "    bp:dataOutputAssociation ex:ConsultOut .",
    ).replace(
        """ex:ConsultIn a bpmn:dataInputAssociation ;
    bp:sourceRef ex:FileRef ; bp:targetRef ex:Consult .""",
        """ex:ConsultOut a bpmn:dataOutputAssociation ;
    bp:sourceRef ex:Consult ; bp:targetRef ex:FileRef .""",
    )
    marked = _marked(run_assessment_from_text(writes))
    assert "Summary" in marked, (
        "an activity that writes personal data reached nothing: only "
        "bp:dataInputAssociation was read"
    )
    assert "CaseFiles" not in marked, (
        "a write landed on the system's entry rather than on what it produces"
    )


def test_a_dpv_term_the_editor_does_not_list_still_counts_as_personal() -> None:
    """The option list says which terms mean *not* personal. Everything else
    stays personal, because saying nothing about a term is not saying it is safe.

    The guard was written `!BOUND(?x) || ?x`, and rdflib does not short-circuit
    `||`: the second operand was evaluated unbound, the filter errored, and the
    row was dropped. Every DPV term outside the five the editor offers was
    silently discarded, which is the reverse of what the list means.
    """
    options = {
        str(term) for term in load_base_graph().objects(None, PAIR.classifiesAs)
    }
    assert "https://w3id.org/dpv#MedicalHealth" not in options, (
        "this test needs a DPV term the editor does not list"
    )
    assert "CaseFiles" in _marked(run_assessment_from_text(STORE_NOT_AN_INPUT)), (
        "an unlisted DPV term was treated as though it meant 'not personal'"
    )

    # And the two that do mean not personal are still excluded.
    anonymised = STORE_NOT_AN_INPUT.replace("dpv:MedicalHealth", "dpv:AnonymisedData")
    assert not _marked(run_assessment_from_text(anonymised)), (
        "'checked, and not personal' must not raise anything"
    )
