
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

/* What the annotation guidance said about each element, keyed by IRI.
 *
 * The gap report and the SHACL guidance answer the same question - "why did no
 * motif match?" - from opposite directions. The gap report reads structure:
 * which pattern nodes and edges are satisfied. The guidance reads coherence:
 * whether a role and a class agree. Neither can do the other's job, and until
 * now they were in different tabs.
 *
 * The case that made it obvious: a `pair:RetrievalStep` role put on a
 * `beam:Data` element. The gap report offered it as a candidate six times over
 * - "make Retrieval a Vector Store", "a Prediction Request" - because it is
 * Data-typed and those roles are unfilled. All six were the wrong advice. The
 * guidance said the true thing in one line: it plays a step role and carries no
 * process class.
 *
 * So a candidate the guidance flagged is marked rather than dropped. Hiding it
 * would leave the reader wondering where their element went; saying why is the
 * point. */
let annotationHints = new Map();

/* Only the role/class contradictions mark a candidate. Those are exactly the
 * two Warning-level shapes; the Info ones are about missing structure, which
 * is what the gap report itself is for. */
function blockingHint(id) {
  return (annotationHints.get(id) || []).find((h) => h.severity === "warning") || null;
}

function candidateItem(candidate) {
  const bad = blockingHint(candidate.id);
  if (!bad) return el("span", { class: "gap-candidate" }, candidate.label);
  return el("span", { class: "gap-candidate flagged", title: bad.message }, [
    el("span", {}, candidate.label),
    el("span", { class: "gap-flag" }, "annotation problem"),
  ]);
}

function gapCard(gap) {
  const items = [];
  gap.missingNodes.forEach((n) => {
    const need = [
      el("span", {}, "no element plays "),
      el("strong", {}, n.role),
    ];
    if (n.candidates.length) {
      need.push(el("span", { class: "gap-hint" }, " — try: "));
      n.candidates.forEach((c, index) => {
        if (index) need.push(el("span", { class: "gap-hint" }, ", "));
        need.push(candidateItem(c));
      });
    }
    items.push(el("li", { class: "gap-need-role" }, need));
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
  if (near.length) {
    list.appendChild(el("div", { class: "gap-section-head" },
      "Almost matched — what's missing"));
    near.forEach((g) => list.appendChild(gapCard(g)));
  }

  /* Not gated on there being a near miss. An element whose role and class
   * contradict each other is exactly the case where NOTHING comes close, so
   * hiding the explanation behind a near miss withholds it when it matters
   * most. */
  const flagged = [...annotationHints.entries()]
    .filter(([, hints]) => hints.some((h) => h.severity === "warning"));
  if (!flagged.length) return;
  list.appendChild(el("div", { class: "gap-section-head" },
    "Annotations that cannot bind"));
  flagged.forEach(([id, hints]) => {
    const worst = hints.find((h) => h.severity === "warning");
    const row = el("div", { class: "gap-row flagged-row", title: worst.message }, [
      el("div", { class: "gap-head" }, [
        el("span", { class: "motif-row-name" }, id.split(/[#/]/).pop()),
      ]),
      el("div", { class: "gap-flag-text" }, worst.message),
    ]);
    row.classList.add("clickable");
    row.addEventListener("click", () => { GraphView.setHighlight([id]); revealInSource([id]); });
    list.appendChild(row);
  });
}

/* Fetched rather than carried on the assessment: pyshacl costs about 1.7s on
 * the largest bundled example, which is half again what an assessment takes.
 * The gaps draw immediately and the hints attach when they land. */
async function loadAnnotationHints(ttl, gaps) {
  try {
    const report = await postJson("/api/validate", { ttl });
    const next = new Map();
    /* Guidance only. The input contract's warnings ride in the same report and
     * are a different question - "type this to a leaf class" fires on every
     * plain beam:Data and says nothing about how anyone annotated it. */
    const add = (items, severity) => (items || []).forEach((item) => {
      if (!item.focusNode || !item.guidance) return;
      const list = next.get(item.focusNode) || [];
      list.push({ severity, message: item.message });
      next.set(item.focusNode, list);
    });
    add(report.warnings, "warning");
    add(report.hints, "info");
    const changed = next.size !== annotationHints.size
      || [...next.keys()].some((k) => !annotationHints.has(k));
    annotationHints = next;
    if (changed && lastGaps) renderMotifsFromCache();
  } catch (_) { /* hints are an extra; the gap report stands without them */ }
}

export function clearMotifs() {
  annotationHints = new Map();
  lastMatches = null;
  lastGaps = null;
  $("#motifs-list").innerHTML = "";
  $("#motifs-count").textContent = "";
  $("#motifs-empty").classList.remove("hidden");
  selectedMotifRow = null;
}

let lastMatches = null;
let lastGaps = null;

function renderMotifsFromCache() {
  renderMotifs(lastMatches, lastGaps, { refetchHints: false });
}

export function renderMotifs(matches, gaps, options = {}) {
  lastMatches = matches;
  lastGaps = gaps;
  if (options.refetchHints !== false) {
    const ttl = Editor.getValue().trim();
    if (ttl) loadAnnotationHints(ttl, gaps);
  }
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
