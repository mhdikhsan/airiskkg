
import { postJson } from "../core/api.js";
import { $, $$, el } from "../core/dom.js";
import { revealInSource } from "../core/source.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { runMutation } from "./mutations.js";
import { buildTray, startTrayDrag } from "./palette.js";
import { noteChange } from "./run.js";

// ---- matches and gaps ----
let selectedMotifRow = null;

function gapCard(gap) {
  const items = [];
  gap.missingNodes.forEach((n) => {
    const hint = n.candidates.length
      ? ` — try: ${n.candidates.map((c) => c.label).join(", ")}`
      : "";
    items.push(el("li", { class: "gap-need-role" }, [
      el("span", {}, "no element plays "),
      el("strong", {}, n.role),
      el("span", { class: "gap-hint" }, hint),
    ]));
  });
  gap.missingEdges.forEach((e) => items.push(el("li", { class: "gap-need-edge" }, e.text)));

  const card = el("div", { class: "gap-row" }, [
    el("div", { class: "gap-head" }, [
      el("span", { class: "motif-row-name" }, gap.label.replace(/\s+Motif$/, "")),
      el("span", { class: "gap-score", title: "pattern nodes and edges satisfied" },
        `${gap.satisfied}/${gap.total}`),
    ]),
    el("ul", { class: "gap-list" }, items),
  ]);
  const candidateIds = gap.missingNodes.flatMap((n) => n.candidates.map((c) => c.id));
  if (candidateIds.length) {
    card.classList.add("clickable");
    card.title = "Click to highlight the elements that could take these roles";
    card.addEventListener("click", () => GraphView.setHighlight(candidateIds));
  }
  return card;
}

function renderMotifGaps(gaps) {
  const list = $("#motifs-list");
  // Only near misses are actionable.
  const near = (gaps || []).filter((g) => g.satisfied / g.total >= 0.5).slice(0, 5);
  if (!near.length) return;
  list.appendChild(el("div", { class: "gap-section-head" },
    "Almost matched — what's missing"));
  near.forEach((g) => list.appendChild(gapCard(g)));
}

export function clearMotifs() {
  $("#motifs-list").innerHTML = "";
  $("#motifs-count").textContent = "";
  $("#motifs-empty").classList.remove("hidden");
  selectedMotifRow = null;
}

export function renderMotifs(matches, gaps) {
  const byName = new Map();
  (matches || []).forEach((m) => {
    const label = (m.label || (m.motif && m.motif.label) || "Motif").replace(/\s+Motif$/, "");
    const g = byName.get(label) || { label, ids: new Set(), count: 0 };
    (m.nodeIds || []).forEach((id) => g.ids.add(id));
    g.count += 1;
    byName.set(label, g);
  });
  const rows = [...byName.values()]
    .map((g) => ({ label: g.label, nodeIds: [...g.ids], count: g.count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));

  const list = $("#motifs-list");
  const empty = $("#motifs-empty");
  list.innerHTML = "";
  selectedMotifRow = null;
  if (!rows.length) {
    empty.textContent = "No motifs matched. Add roles so motifs can bind, then Run assessment.";
    empty.classList.remove("hidden");
    $("#motifs-count").textContent = "";
    renderMotifGaps(gaps); 
    return;
  }
  empty.classList.add("hidden");
  rows.forEach((r) => {
    const row = el("div", {
      class: "motif-row", tabindex: "0",
      title: `Matched ${r.count} time${r.count > 1 ? "s" : ""} · click to highlight ${r.nodeIds.length} elements`,
    }, [
      el("span", { class: "motif-row-name" }, r.label),
      el("span", { class: "motif-row-count" }, r.count > 1 ? `×${r.count}` : "1"),
    ]);
    row.addEventListener("click", () => {
      const wasSelected = selectedMotifRow === row;
      $$(".motif-row.selected").forEach((x) => x.classList.remove("selected"));
      if (wasSelected) { selectedMotifRow = null; GraphView.setHighlight([]); return; }
      selectedMotifRow = row;
      row.classList.add("selected");
      GraphView.setHighlight(r.nodeIds);
      revealInSource(r.nodeIds);
    });
    list.appendChild(row);
  });
  renderMotifGaps(gaps);
  $("#motifs-count").textContent = String(rows.length);
}

// ---- motif palette ----

function addMotif(item) {
  return runMutation(async () => {
    try {
      const { ttl } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> .\n",
        op: "add-motif", motif: item.id,
      });
      noteChange(`added motif: ${item.label}`);
      Editor.setValue(ttl);
      setStatus("ok", `Added "${item.label}" — already annotated; Run assessment for findings`);
    } catch (error) {
      setStatus("error", "Could not add motif: " + error.message.split("\n")[0]);
    }
  });
}

export function initMotifPalette(templates) {
  const panel = $("#motif-palette");
  if (!panel) return;
  if (!templates || !templates.length) { panel.style.display = "none"; return; }
  const wrap = $("#canvas-wrap");
  const body = el("div", { class: "tray-body" });
  templates.forEach((item) => {
    const chip = el("div", { class: "motif-item", title: `Add ${item.label} — click or drag onto the canvas` }, item.label);
    chip.addEventListener("pointerdown", (ev) => startTrayDrag(ev, chip, wrap, () => addMotif(item)));
    body.appendChild(chip);
  });
  buildTray(panel, "Motifs", body, true); 
}
