/* The SHACL report, grouped by severity.
 */

import { $, el } from "../core/dom.js";
import { GraphView } from "../graph.js";

// validation 
function validationRow(item, severity) {
  const row = el("div", { class: `validation-row ${severity}` }, [
    el("span", { class: "sev" }, severity === "violation" ? "Violation" : "Warning"),
    el("span", { class: "msg" }, item.message),
  ]);
  if (item.focusNode) {
    row.appendChild(el("code", { class: "focus", title: item.focusNode }, item.focusNode.split(/[#/]/).pop()));
    row.addEventListener("click", () => GraphView.setHighlight([item.focusNode]));
  }
  return row;
}

export function renderValidation(report) {
  $("#validation-empty").classList.add("hidden");
  const list = $("#validation-list");
  list.innerHTML = "";
  const total = report.violations.length + report.warnings.length;
  list.appendChild(el("div", { class: "summary-row" }, [
    el("span", { class: `stat ${report.conforms ? "good" : "bad"}` },
      report.conforms ? "Input contract satisfied" : "Input contract violated"),
    el("span", { class: "stat" }, `${report.violations.length} violations · ${report.warnings.length} warnings`),
    total ? el("span", { class: "hint" }, "Click a row to highlight the focus node.") : null,
  ]));
  report.violations.forEach((v) => list.appendChild(validationRow(v, "violation")));
  report.warnings.forEach((w) => list.appendChild(validationRow(w, "warning")));
  $("#validation-count").textContent = total ? String(total) : "";
}
