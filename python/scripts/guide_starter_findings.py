"""Print the candidate risks of the starter scene and write them into the guide."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from airiskkg.assessment_runner import run_assessment
from airiskkg.assessment_view import summarize_result
from airiskkg.paths import REPO_ROOT
from airiskkg.workbench.risk_view import group_findings

EXAMPLES = REPO_ROOT / "ontology" / "example"
SYSTEM = EXAMPLES / "support_chatbot.ttl"
PROCESS = EXAMPLES / "context" / "customer_support.ttl"
TARGET = REPO_ROOT / "python" / "src" / "airiskkg" / "webapp" / "static" / "guide_content.js"
BLOCK = re.compile(r"(// BEGIN STARTER FINDINGS\n).*?(// END STARTER FINDINGS)", re.S)


def candidate_risks(paths: list[Path]) -> dict[tuple, str]:
    findings = summarize_result(run_assessment([str(p) for p in paths], write_outputs=False))["findings"]
    risks = {}
    for group in group_findings(findings):
        label = re.sub(r"^Candidate\s+", "", group["label"])
        risks[(label[:1].upper() + label[1:], tuple(sorted(e["label"] for e in group["evidence"])))] = group["label"]
    return risks


def main() -> int:
    full = candidate_risks([SYSTEM, PROCESS])
    system_only = candidate_risks([SYSTEM])
    rows = [
        {
            "label": label,
            "evidence": list(evidence),
            "scopes": [
                scope
                for scope, risks in (("full", full), ("system", system_only))
                if (label, evidence) in risks
            ],
        }
        for label, evidence in sorted({*full, *system_only})
    ]
    body = "export const STARTER_FINDINGS = " + json.dumps(rows, indent=2, ensure_ascii=False) + ";\n"
    text = TARGET.read_text(encoding="utf-8")
    TARGET.write_text(BLOCK.sub(lambda m: m.group(1) + body + m.group(2), text, count=1), encoding="utf-8")
    for row in rows:
        print(f"{row['label']} [{', '.join(row['scopes'])}]: {', '.join(row['evidence'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
