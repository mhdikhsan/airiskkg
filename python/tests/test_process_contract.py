"""The business process input contract: is the BPMN well formed?"""

from __future__ import annotations

import pytest
from rdflib import RDF, Graph, Namespace

from airiskkg.paths import SHACL_DIR
from airiskkg.workbench.validation import shacl_report
from conftest import FIXTURE_DIR

SH = Namespace("http://www.w3.org/ns/shacl#")

BROKEN = """
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp: <https://sBPMN.github.io/2.0/properties#> .
@prefix ex: <http://example.org/broken#> .
ex:A a bpmn:participant ; bp:name "Customer" ; bp:processRef ex:PA .
ex:B a bpmn:participant ; bp:name "Desk" ; bp:processRef ex:PB .
ex:PA a bpmn:process ; bp:contains ex:s, ex:ask, ex:log, ex:e, ex:lonely .
ex:PB a bpmn:process ; bp:contains ex:answer .
ex:s a bpmn:startEvent ; bp:name "Begin" .
ex:ask a bpmn:task ; bp:name "Ask" .
ex:log a bpmn:task ; bp:name "Log" .
ex:e a bpmn:endEvent ; bp:name "Done" .
ex:lonely a bpmn:task ; bp:name "Forgotten step" .
ex:answer a bpmn:task ; bp:name "Answer" .
ex:f1 a bpmn:sequenceFlow ; bp:sourceRef ex:s ; bp:targetRef ex:ask .
ex:f2 a bpmn:sequenceFlow ; bp:sourceRef ex:ask ; bp:targetRef ex:log .
ex:f3 a bpmn:sequenceFlow ; bp:sourceRef ex:log ; bp:targetRef ex:e .
ex:back a bpmn:sequenceFlow ; bp:sourceRef ex:e ; bp:targetRef ex:s .
ex:across a bpmn:sequenceFlow ; bp:sourceRef ex:log ; bp:targetRef ex:answer .
ex:inside a bpmn:messageFlow ; bp:sourceRef ex:ask ; bp:targetRef ex:log .
"""


@pytest.fixture(scope="module")
def broken() -> dict:
    report = shacl_report(BROKEN)
    return {
        "violations": [row for row in report["violations"] if row["process"]],
        "warnings": [row for row in report["warnings"] if row["process"]],
    }


def _said(rows: list[dict], *parts: str) -> bool:
    return any(all(part in row["message"] for part in parts) for row in rows)


def test_the_bpmn_rules_are_violations_and_name_both_ends(broken) -> None:
    """Elmar: "no validation for syntactic correctness yet, I presume?" """
    rows = broken["violations"]
    assert _said(rows, '"Begin" is a start event', '"Done"')
    assert _said(rows, '"Done" is an end event', '"Begin"')
    assert _said(rows, 'from "Log" to "Answer"', "crosses between participants")
    assert _said(rows, 'from "Ask" to "Log"', "stays inside one participant")
    assert len(rows) == 4, [row["message"] for row in rows]


def test_modelling_practice_is_a_warning(broken) -> None:
    rows = broken["warnings"]
    assert _said(rows, '"Desk" has no start event')
    assert _said(rows, '"Desk" has no end event')
    assert _said(rows, '"Forgotten step" has no sequence flow leading into it')
    assert _said(rows, '"Forgotten step" has no sequence flow leaving it')
    assert not _said(rows, '"Ask"'), "a joined-up step was warned about"


@pytest.mark.parametrize("files", [
    ["wien_energie_bottina.ttl", "context/energy_customer_service.ttl"],
    ["wien_energie_tariff_change.ttl", "context/energy_tariff_change.ttl"],
    ["it_support_agent.ttl", "context/it_service_desk.ttl"],
])
def test_the_tracked_scenes_are_well_formed_bpmn(files) -> None:
    ttl = "\n\n".join((FIXTURE_DIR / name).read_text(encoding="utf-8") for name in files)
    report = shacl_report(ttl)
    rows = [row["message"] for row in report["violations"] + report["warnings"] if row["process"]]
    assert not rows, rows


def test_the_process_contract_is_only_violations_and_warnings() -> None:
    shapes = Graph().parse(SHACL_DIR / "process_input_contract.ttl", format="turtle")
    severities = set(shapes.objects(None, SH.severity))
    assert severities and severities <= {SH.Violation, SH.Warning}
    assert set(shapes.subjects(RDF.type, SH.NodeShape))
