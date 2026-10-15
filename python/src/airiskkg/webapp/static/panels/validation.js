import { postJson } from "../core/api.js";
import { $, el } from "../core/dom.js";
import { openDrawer } from "../core/drawer.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { applyEdit } from "./mutations.js";

/* One click per choice: the kind it is, applied to that element. */
function fixRow(item) {
  const { mode, choices } = item.fix;
  return el("div", { class: "validation-fix" }, [
    el("span", { class: "hint" }, mode === "add" ? "Add the kind:" : "Make it:"),
    ...choices.map((choice) => {
      const button = el("button", {
        type: "button", class: "chip clickable",
        title: mode === "add"
          ? `Mark "${item.focusLabel}" as ${choice.label} as well`
          : `Mark "${item.focusLabel}" as ${choice.label}`,
      }, choice.label);
      button.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        await applyEdit(item.focusNode,
          mode === "add" ? { addClassUri: choice.classUri } : { classUri: choice.classUri });
        validateNow().catch((error) => setStatus("error", "Could not validate: " + error.message));
      });
      return button;
    }),
  ]);
}

function validationRow(item, severity) {
  const row = el("div", { class: `validation-row ${severity}` }, [
    el("span", { class: "sev" }, severity === "violation" ? "Violation" : "Warning"),
    el("span", { class: "msg" }, item.message),
  ]);
  if (item.focusNode) {
    row.appendChild(el("code", { class: "focus", title: item.focusNode },
      item.focusLabel || item.focusNode.split(/[#/]/).pop()));
    row.addEventListener("click", () => GraphView.setHighlight([item.focusNode]));
  }
  if (item.fix && item.focusNode) row.appendChild(fixRow(item));
  return row;
}

export function clearValidation() {
  $("#validation-list").innerHTML = "";
  $("#validation-count").textContent = "";
  $("#validation-empty").classList.remove("hidden");
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

/* Run after the editor settles, so the panel is never empty for a graph that
   has something to say. One request at a time: a check started while another
   runs waits for it, then checks whatever the editor holds by then. */
const SETTLE_MS = 1500;
let settleTimer = null;
let running = null;

export function scheduleValidation() {
  clearTimeout(settleTimer);
  if (!Editor.getValue().trim()) { clearValidation(); return; }
  settleTimer = setTimeout(async () => {
    if (running) await running.catch(() => {});
    // The status bar already reports a graph that does not parse.
    running = validateNow().catch(() => null);
    await running;
    running = null;
  }, SETTLE_MS);
}

/* Checks the editor against the input contract. `open` shows the panel. */
export async function validateNow({ open = false } = {}) {
  const ttl = Editor.getValue().trim();
  if (!ttl) {
    if (open) setStatus("error", "Nothing to validate - the editor is empty.");
    return null;
  }
  const report = await postJson("/api/validate", { ttl });
  // The document moved on while this ran, so the report is about something gone.
  if (Editor.getValue().trim() !== ttl) return null;
  renderValidation(report);
  if (open) openDrawer("validation");
  return report;
}
