
import { postJson } from "../core/api.js";
import { $, $$, el } from "../core/dom.js";
import { revealInSource } from "../core/source.js";
import { groupBySystem, onScreen } from "../core/systems.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { runMutation } from "./mutations.js";
import { buildTray, madeSystemNote, startTrayDrag } from "./palette.js";
import { noteChange } from "./run.js";
import { state } from "../state.js";

// ---- matches and gaps ----
let selectedMotifRow = null;
let selectedMotifLabel = null;   // survives the redraw the hint check causes
let annotationHints = new Map();

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
  /* Candidates that are not on screen belong to another architecture; offering
   * them under a scoped view suggests annotating something the reader cannot
   * see. The gap itself is graph-wide and stays. */
  const scopedGaps = (gaps || []).map((g) => {
    const had = g.missingNodes.some((n) => (n.candidates || []).length);
    const missingNodes = g.missingNodes.map((n) => ({
      ...n,
      candidates: onScreen(n.candidates || [], (c) => [c.id]),
    }));
    const has = missingNodes.some((n) => n.candidates.length);
    /* A gap whose every candidate was elsewhere is a statement about the other architecture. */
    return { ...g, missingNodes, elsewhere: had && !has };
  }).filter((g) => !g.elsewhere);
  const near = scopedGaps.filter((g) => g.satisfied / g.total >= 0.5).slice(0, 5);
  if (near.length) {
    list.appendChild(el("div", { class: "gap-section-head" },
      "Almost matched — what's missing"));
    near.forEach((g) => list.appendChild(gapCard(g)));
  }
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

async function loadAnnotationHints(ttl, gaps) {
  try {
    const report = await postJson("/api/validate", { ttl });
    const next = new Map();
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
  selectedMotifLabel = null;
}

let lastMatches = null;
let lastGaps = null;

function renderMotifsFromCache() {
  renderMotifs(lastMatches, lastGaps, { refetchHints: false });
}

/* Aggregated per architecture, not across them. A motif matched in both
 * systems used to collapse into one row reading "x2", which is the confusion
 * the grouping exists to remove. */
function motifRows(matches) {
  const byName = new Map();
  (matches || []).forEach((m) => {
    const label = (m.label || (m.motif && m.motif.label) || "Motif").replace(/\s+Motif$/, "");
    const g = byName.get(label) || { label, ids: new Set(), count: 0, bindings: new Map() };
    (m.nodeIds || []).forEach((id) => g.ids.add(id));
    (m.boundElements || []).forEach((b) => {
      const key = `${b.elementId}|${b.role}`;
      if (!g.bindings.has(key)) g.bindings.set(key, b);
    });
    g.count += 1;
    byName.set(label, g);
  });
  return [...byName.values()]
    .map((g) => ({ label: g.label, nodeIds: [...g.ids], count: g.count, bindings: [...g.bindings.values()] }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

/* Which of the reader's annotations made the motif match: each element, the
   role its pattern node asks for, and the element's own role when that is a
   refinement of it. */
function bindingList(bindings) {
  const rows = [...bindings]
    .sort((a, b) => (a.element || "").localeCompare(b.element || ""))
    .map((b) => el("li", {}, [
      el("strong", {}, b.element),
      el("span", { class: "motif-binding-role" }, b.role ? ` as ${b.role}` : ""),
      b.via && b.via !== b.role
        ? el("span", { class: "motif-binding-via" }, ` (its role ${b.via} refines it)`)
        : null,
    ]));
  return el("div", { class: "motif-bindings" }, [
    el("div", { class: "motif-bindings-lead" }, "Matched on these annotations:"),
    el("ul", {}, rows),
  ]);
}

export function renderMotifs(matches, gaps, options = {}) {
  lastMatches = matches;
  lastGaps = gaps;
  if (options.refetchHints !== false) {
    const ttl = Editor.getValue().trim();
    if (ttl) loadAnnotationHints(ttl, gaps);
  }
  const shown = onScreen(matches || [], (m) => m.nodeIds || []);
  const groups = groupBySystem(shown, (m) => m.nodeIds || []);
  const rows = motifRows(shown);

  const list = $("#motifs-list");
  const empty = $("#motifs-empty");
  list.innerHTML = "";
  selectedMotifRow = null;
  // Redrawn for the hints alone, the reader's pick is still the same match.
  const keep = options.refetchHints === false ? selectedMotifLabel : null;
  if (!keep) selectedMotifLabel = null;
  if (!rows.length) {
    empty.textContent = "No motifs matched. Add roles so motifs can bind, then Run assessment.";
    empty.classList.remove("hidden");
    $("#motifs-count").textContent = "";
    renderMotifGaps(gaps); 
    return;
  }
  empty.classList.add("hidden");
  const draw = (r) => {
    const row = el("div", {
      class: "motif-row", tabindex: "0",
      title: `Matched ${r.count} time${r.count > 1 ? "s" : ""} · click to highlight ${r.nodeIds.length} elements`,
    }, [
      el("span", { class: "motif-row-name" }, r.label),
      el("span", { class: "motif-row-count" }, r.count > 1 ? `×${r.count}` : "1"),
      r.bindings.length ? bindingList(r.bindings) : null,
    ]);
    if (keep === r.label && !selectedMotifRow) {
      selectedMotifRow = row;
      row.classList.add("selected");
    }
    row.addEventListener("click", () => {
      const wasSelected = selectedMotifRow === row;
      $$(".motif-row.selected").forEach((x) => x.classList.remove("selected"));
      if (wasSelected) {
        selectedMotifRow = null;
        selectedMotifLabel = null;
        GraphView.setHighlight([]);
        return;
      }
      selectedMotifRow = row;
      selectedMotifLabel = r.label;
      row.classList.add("selected");
      GraphView.setHighlight(r.nodeIds);
      revealInSource(r.nodeIds);
    });
    list.appendChild(row);
  };

  groups.forEach((group) => {
    if (group.label) list.appendChild(el("div", { class: "annotate-group static" }, [
      el("span", {}, group.label),
      el("span", { class: "annotate-group-count" }, `${group.items.length}`),
    ]));
    motifRows(group.items).forEach(draw);
  });
  renderMotifGaps(gaps);
  $("#motifs-count").textContent = String(rows.length);
}

// ---- motif palette ----

/* Resolves to true when the motif landed in the editor. The palette ignores
 * that - the status bar has already said so - but the library sits over the
 * status bar and has to report the outcome itself. */
export function addMotif(item) {
  return runMutation(async () => {
    try {
      const { ttl, newSystem } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> .\n",
        op: "add-motif", motif: item.id,
        ...(item.riskPattern ? { riskPattern: item.riskPattern } : {}),
        /* Where the system bar says "adding to", exactly as a palette symbol does. */
        system: GraphView.getSelectedSystem() || state.scopedSystem || null,
      });
      noteChange(`added motif: ${item.label}`);
      Editor.setValue(ttl);
      setStatus("ok", `Added "${item.label}"${madeSystemNote(newSystem)}`
        + " — already annotated; Run assessment for findings");
      return true;
    } catch (error) {
      setStatus("error", "Could not add motif: " + error.message.split("\n")[0]);
      return false;
    }
  });
}

/* The library shelves motifs by the kind of AI system each is a shape of, then
 * by the variants and companions within it; one alphabetical column said
 * nothing about either. */
function binBy(items, key, fallback) {
  const bins = new Map();
  items.forEach((item) => {
    const name = item[key] || fallback;
    if (!bins.has(name)) bins.set(name, []);
    bins.get(name).push(item);
  });
  return [...bins.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

export function initMotifPalette(templates) {
  const panel = $("#motif-palette");
  if (!panel) return;
  if (!templates || !templates.length) { panel.style.display = "none"; return; }
  const wrap = $("#canvas-wrap");
  const search = el("input", {
    type: "search", class: "motif-search", placeholder: "Search motifs",
    "aria-label": "Search motifs by name or description",
  });
  const none = el("p", { class: "motif-none hidden" }, "No motif matches that.");
  const body = el("div", { class: "tray-body" }, [search]);
  /* Families start folded and open on a click; a search opens every family it
     finds something in, or a match inside a folded one would read as no match. */
  const opened = new Set();
  const shelves = [];

  binBy(templates, "family", "Unshelved").forEach(([family, items]) => {
    const count = el("span", { class: "motif-family-count" }, String(items.length));
    const head = el("button", { type: "button", class: "motif-family", "aria-expanded": "false" },
      [el("span", {}, family), count]);
    const shelf = el("div", { class: "motif-shelf" });
    const chips = [];
    const groups = binBy(items, "group", "Other");
    groups.forEach(([group, members]) => {
      // A family filed as one group says nothing more under a second heading.
      const heading = groups.length > 1 ? el("div", { class: "motif-group" }, group) : null;
      if (heading) shelf.appendChild(heading);
      members.forEach((item) => {
        const chip = el("div", {
          class: "motif-item",
          title: (item.description ? `${item.description}\n\n` : "")
            + "Click or drag onto the canvas to add it.",
        }, item.label.replace(/\s*Motif$/, ""));
        chip.addEventListener("pointerdown", (ev) => startTrayDrag(ev, chip, wrap, () => addMotif(item)));
        shelf.appendChild(chip);
        chips.push({ chip, heading, text: [item.label, item.description, group, family]
          .filter(Boolean).join(" ").toLowerCase() });
      });
    });
    head.addEventListener("click", () => {
      if (opened.has(family)) opened.delete(family); else opened.add(family);
      show();
    });
    body.appendChild(head);
    body.appendChild(shelf);
    shelves.push({ family, head, shelf, chips, count, total: items.length });
  });
  body.appendChild(none);

  const show = () => {
    const query = search.value.trim().toLowerCase();
    let found = 0;
    shelves.forEach(({ family, head, shelf, chips, count, total }) => {
      const hits = chips.filter(({ text }) => !query || text.includes(query));
      chips.forEach(({ chip }) => chip.classList.toggle("hidden", !hits.some((h) => h.chip === chip)));
      new Set(chips.map(({ heading }) => heading).filter(Boolean)).forEach((heading) =>
        heading.classList.toggle("hidden", !hits.some((h) => h.heading === heading)));
      const open = query ? hits.length > 0 : opened.has(family);
      head.classList.toggle("hidden", Boolean(query) && !hits.length);
      head.classList.toggle("open", open);
      head.setAttribute("aria-expanded", String(open));
      shelf.classList.toggle("hidden", !open);
      count.textContent = String(query ? hits.length : total);
      found += hits.length;
    });
    none.classList.toggle("hidden", found > 0);
  };
  search.addEventListener("input", show);
  show();

  buildTray(panel, "Motifs", body, true);
}
