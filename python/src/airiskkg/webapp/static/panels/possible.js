import { postJson } from "../core/api.js";
import { on } from "../core/bus.js";
import { $, el } from "../core/dom.js";
import { revealInSource } from "../core/source.js";
import { setStatus } from "../core/status.js";
import { onScreen } from "../core/systems.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { runMutation } from "./mutations.js";
import { noteChange } from "./run.js";
"use strict";

/* Risks the library would raise if the diagram said a little more: a category
   tag made precise, a role the risk depends on, a part left out. Asked for after
   each run, because finding them means checking each reading of the drawing,
   and kept apart from the findings: none of them has been raised. */

const SHOWN = 4;
let asked = 0;
let showAll = false;
let last = null;

function why(need) {
  return need.why ? el("span", { class: "possible-was" }, ` - if ${need.why}`) : null;
}

function words(need) {
  if (need.kind === "category") {
    return [
      "Mark ", el("strong", {}, need.elementLabel), " as carrying ", el("strong", {}, need.categoryLabel),
      why(need),
      el("span", { class: "chip possible-cond", title: "What the risk depends on, not what the motif needs" }, "condition"),
    ];
  }
  if (need.kind === "role") {
    const was = need.was && need.was.length ? `now ${need.was.join(", ")}` : "now untagged";
    return [
      "Tag ", el("strong", {}, need.elementLabel), " as ", el("strong", {}, need.roleLabel),
      el("span", { class: "possible-was" }, ` (${was})`),
      why(need),
      need.condition ? el("span", { class: "chip possible-cond", title: "What the risk depends on, not what the motif needs" }, "condition") : null,
    ];
  }
  const link = (need.links || [])[0];
  let where = "";
  if (link) {
    const verb = link.predicate === "use" ? "uses" : "produces";
    where = link.outgoing ? ` that ${verb} ${link.elementLabel}` : ` that ${link.elementLabel} ${verb}`;
  }
  return ["Add ", el("strong", {}, need.roleLabel || need.label), where];
}

function apply(risk) {
  return runMutation(async () => {
    try {
      const { ttl, newIds } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue(), op: "apply-suggestions", needs: risk.needs,
      });
      noteChange(`completed ${risk.motifLabel.replace(/\s+Motif$/, "")} for ${risk.label.replace(/^Candidate /, "")}`);
      Editor.setValue(ttl);
      GraphView.setHighlight(newIds || []);
      setStatus("busy", "Applied the suggestions - re-assessing...");
      $("#btn-assess").click();
    } catch (error) {
      setStatus("error", "Could not apply them: " + error.message.split("\n")[0]);
    }
  });
}

function placeRow(risk) {
  const ids = risk.evidence;
  const row = el("div", { class: "possible-place", tabindex: "0", title: "Show this place on the canvas" }, [
    el("div", { class: "finding-place-evidence" }, risk.evidenceLabels.join(" · ")),
    el("div", { class: "finding-place-motifs" }, [
      el("span", { class: "ctrl-motifs-lead" }, "reading it as "),
      el("span", { class: "chip" }, risk.motifLabel.replace(/\s+Motif$/, "")),
    ]),
    el("ul", { class: "possible-needs" }, risk.needs.map((need) => el("li", {}, words(need)))),
    el("button", {
      type: "button", class: "btn small",
      title: "Write these into the diagram and run the assessment again. Only if they describe your system.",
      onclick: (ev) => { ev.stopPropagation(); apply(risk); },
    }, risk.needs.length > 1 ? "Apply these" : "Apply this"),
  ]);
  row.addEventListener("click", () => {
    GraphView.setHighlight(ids);
    GraphView.focus(ids);
    revealInSource(ids);
  });
  return row;
}

function render() {
  const host = $("#possible-list");
  if (!host) return;
  host.innerHTML = "";
  if (!last || !last.risks) return;
  const shown = onScreen(last.risks, (r) => r.evidence);
  if (!shown.length) return;
  const groups = new Map();
  shown.forEach((risk) => {
    if (!groups.has(risk.pattern)) groups.set(risk.pattern, []);
    groups.get(risk.pattern).push(risk);
  });
  const ordered = [...groups.values()];   // the server already put the smallest asks first
  host.appendChild(el("div", { class: "possible-head" }, [
    el("strong", {}, "Possible risks"),
    el("span", { class: "chip" }, String(ordered.length)),
  ]));
  host.appendChild(el("p", { class: "possible-lede" },
    "Not raised yet. Each would be, if the diagram said what is listed under it. Apply it only if it is true of your system."));
  (showAll ? ordered : ordered.slice(0, SHOWN)).forEach((risks) => {
    host.appendChild(el("div", { class: "finding-card possible-card" }, [
      el("div", { class: "finding-head" }, [
        el("strong", {}, risks[0].label.replace(/^Candidate /, "Possible ")),
        el("span", { class: "chip finding-places" }, risks.length === 1 ? "1 place" : `${risks.length} places`),
      ]),
      el("div", { class: "finding-place-list" }, risks.map(placeRow)),
    ]));
  });
  if (last.unchecked) {
    host.appendChild(el("p", { class: "possible-lede" },
      `${last.unchecked} less likely reading${last.unchecked > 1 ? "s were" : " was"} not checked in time.`));
  }
  if (ordered.length > SHOWN) {
    host.appendChild(el("button", {
      type: "button", class: "btn small possible-more",
      onclick: () => { showAll = !showAll; render(); },
    }, showAll ? "Show fewer" : `Show all ${ordered.length}`));
  }
}

async function load() {
  const ttl = Editor.getValue().trim();
  const host = $("#possible-list");
  if (!host) return;
  last = null;
  showAll = false;
  if (!ttl) { host.innerHTML = ""; return; }
  const mine = ++asked;
  host.innerHTML = "";
  host.appendChild(el("p", { class: "possible-lede possible-looking" },
    "Looking for risks a fuller diagram would raise..."));
  try {
    const report = await postJson("/api/possible", { ttl });
    if (mine !== asked || Editor.getValue().trim() !== ttl) return;  // a later run owns the panel
    last = report;
    render();
  } catch (_) {
    if (mine === asked) host.innerHTML = "";
  }
}

export function initPossible() {
  on("assessment:rendered", load);
  on("scope:changed", render);
}

export function clearPossible() {
  asked += 1;
  last = null;
  const host = $("#possible-list");
  if (host) host.innerHTML = "";
}
