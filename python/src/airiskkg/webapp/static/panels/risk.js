import { api, postJson } from "../core/api.js";
import { on } from "../core/bus.js";
import { $, $$, el } from "../core/dom.js";
import { revealInSource } from "../core/source.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { RiskCanvas } from "../lib/risk_canvas.js";
import { applyControl, reassess } from "./findings.js";
import { runMutation } from "./mutations.js";
import { noteChange } from "./run.js";
import { state } from "../state.js";

let register = null;
let storming = false;
const SCOPE_LABELS = {
  in: "answers the scope",
  out: "outside the scope",
  unclassified: "no risk domain linked",
  all: "no scope stated",
};

const BAND_LABEL = {
  impact: "Impact", consequence: "Consequence", context: "Context",
  risk: "Risk", source: "Risk Source", control: "Risk Control",
  system: "System", business: "Activity",
};

const TRIAGE = [
  ["confirmed", "Confirmed", "a real weakness in this design"],
  ["mitigated", "Mitigated", "something built now interrupts it"],
  ["accepted", "Accepted", "understood and carried, usually by a process"],
  ["refuted", "Not a risk", "examined and judged not to apply here"],
];

export async function initRisk() {
  RiskCanvas.init("#risk-canvas", {
       onSelect: () => renderRail(),
    onUnfold: unfold,
  });
  $("#btn-risk-zoom-in").addEventListener("click", () => RiskCanvas.zoom(1.2));
  $("#btn-risk-zoom-out").addEventListener("click", () => RiskCanvas.zoom(0.83));
  $("#btn-risk-fit").addEventListener("click", () => RiskCanvas.fit());

  on("assessment:rendered", () => refreshRegister().then(renderRisk));
  knownRisks();
  foldable("#btn-tools-fold", "#risk-tools", "the tools");
  foldable("#btn-side-fold", "#risk-side-tray", "the detail");
}
function foldable(handle, tray, name) {
  const head = $(handle);
  const box = $(tray);
  if (!head || !box) return;
  const mark = head.querySelector(".tray-toggle");
  head.addEventListener("click", () => {
    const folded = box.classList.toggle("collapsed");
    if (mark) mark.textContent = folded ? "▾" : "▴";
    head.title = `${folded ? "Show" : "Hide"} ${name}`;
    requestAnimationFrame(() => RiskCanvas.fit());
  });
}

async function edit(op, payload, cause, { rerun = false, onMade = null } = {}) {
  return runMutation(async () => {
    try {
      const { ttl, newId } = await postJson("/api/scope-edit", {
        ttl: Editor.getValue(), op, ...payload,
      });
      // Before the re-run: the redraw it triggers has to know what to show.
      if (onMade) onMade(newId);
      noteChange(cause);
      Editor.setValue(ttl);
      await refreshRegister();
      if (rerun) {
        setStatus("busy", cause + " - re-assessing…");
        await reassess(ttl); // emits assessment:rendered, which redraws this level
        setStatus("ok", cause);
        return;
      }
      setStatus("ok", cause, "run the assessment again to read against it");
      renderRisk();
    } catch (error) {
      setStatus("error", "Could not edit the scope: " + error.message.split("\n")[0]);
    }
  });
}


const HAND_DROP = {
  risk: {
    bands: ["system", "business"], element: true,
    where: "a system, an element or an activity",
  },
  source: {
    bands: ["risk", "system", "business"], element: true,
    where: "an element, an activity or a risk",
    aims: "an element or activity it comes from, or a risk it causes",
  },
  consequence: { bands: ["risk"], element: false, where: "a risk" },
  impact: { bands: ["consequence"], element: false, where: "a consequence" },
  control: {
    bands: ["risk", "source", "consequence", "impact"], element: false,
    where: "a risk, source or consequence",
  },
};

// A candidate the run raised takes these too, so what a partner adds in an
// experiment is recorded against the finding rather than a copy of it.
const ON_CANDIDATES = new Set(["consequence", "control"]);

function concernOf(id, view) {
  return ((view || {}).groups || []).find((group) => group.key === id) || null;
}

function markDroppable(kind, view) {
  const rule = HAND_DROP[kind];
  const bands = new Set((((view || {}).diagram || {}).nodes || [])
    .filter((node) => rule.bands.includes(node.band)
      && (node.origin === "stated" || (ON_CANDIDATES.has(kind) && concernOf(node.id, view))))
    .map((node) => node.id));
  const marked = [];
  $$("#risk-canvas [data-node]").forEach((card) => {
    const isFlow = card.classList.contains("rc-flow");
    if (bands.has(card.getAttribute("data-node")) || (rule.element && isFlow)) {
      card.classList.add("rc-droppable");
      marked.push(card);
    }
  });
  return marked;
}

function dropTargetAt(event) {
  const under = document.elementFromPoint(event.clientX, event.clientY);
  const card = under && under.closest("#risk-canvas .rc-droppable");
  return card ? { id: card.getAttribute("data-node"), card } : null;
}

function startPaletteDrag(kind, event, view) {
  event.preventDefault();
  event.stopPropagation();
  const ghost = el("div", { class: `risk-ghost band-${kind}` }, HAND_LABEL[kind]);
  document.body.appendChild(ghost);
  const droppable = markDroppable(kind, view);
  ghost.classList.toggle("nowhere", !droppable.length);
  let hot = null;

  const place = (ev) => {
    ghost.style.left = `${ev.clientX + 14}px`;
    ghost.style.top = `${ev.clientY + 14}px`;
    const found = droppable.length ? dropTargetAt(ev) : null;
    if (hot && (!found || found.card !== hot)) hot.classList.remove("rc-drop");
    hot = found ? found.card : null;
    if (hot) hot.classList.add("rc-drop");
    ghost.classList.toggle("over", !!hot);
  };

  const finish = (ev) => {
    window.removeEventListener("pointermove", place);
    window.removeEventListener("pointerup", finish);
    ghost.remove();
    const found = droppable.length ? dropTargetAt(ev) : null;
    droppable.forEach((card) => card.classList.remove("rc-droppable", "rc-drop"));
    if (!found) {
      const noun = HAND_LABEL[kind].toLowerCase();
      setStatus("error", droppable.length
        ? `Drop a ${noun} on ${HAND_DROP[kind].where}.`
        : HAND_DROP[kind].element
          ? `Nothing to drop it on yet: a ${noun} needs ${HAND_DROP[kind].where}.`
          : `Nothing to drop it on yet: a ${noun} needs ${HAND_DROP[kind].where}.`);
      return;
    }
    unfoldDetail();
    const concern = concernOf(found.id, view);
    const target = concern ? { attachToFindings: concern.findingIds } : { attachTo: [found.id] };
    edit("state-concept", { kind, label: HAND_LABEL[kind], ...target },
      `wrote a ${HAND_LABEL[kind].toLowerCase()} by hand`,
      { onMade: (id) => { RiskCanvas.select(id); } });
  };

  window.addEventListener("pointermove", place);
  window.addEventListener("pointerup", finish);
  place(event);
}

let shelf = null;

async function knownRisks() {
  if (shelf) return shelf;
  try {
    const catalogue = await api("/api/library");
    const patterns = (catalogue.riskPatterns || []).map((row) => ({
      id: row.iri || row.id, label: row.label,
    }));
    const controls = new Map();
    (catalogue.riskPatterns || []).forEach((row) => {
      (row.controls || []).forEach((control) => {
        controls.set(control.iri || control.id, control.label);
      });
    });
    shelf = {
      risk: patterns.sort((a, b) => a.label.localeCompare(b.label)),
      control: [...controls].map(([id, label]) => ({ id, label }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    };
  } catch (_) {
    shelf = { risk: [], control: [] }; 
  }
  return shelf;
}

const HAND_LABEL = {
  risk: "Risk", source: "Risk source", consequence: "Consequence", impact: "Impact",
  control: "Risk control",
};

function renderPalette(show, view) {
  const host = $("#risk-palette");
  if (!host) return;
  host.classList.toggle("hidden", !show);
  if (!show) return;
  host.innerHTML = "";
  host.appendChild(el("span", { class: "pp-group" }, "Assess by hand"));
  Object.keys(HAND_LABEL).forEach((kind) => {
    const item = el("button", {
      type: "button", class: `pp-item band-${kind}`, "data-kind": kind,
      title: `Drag onto ${HAND_DROP[kind].where}. Yours, not the library's.`,
    }, [
      el("span", { class: `pal-swatch band-${kind}` }),
      el("span", { class: "pal-text" }, [
        el("span", {}, HAND_LABEL[kind]),
        el("span", { class: "pal-where" },
          `onto ${HAND_DROP[kind].aims || HAND_DROP[kind].where}`),
      ]),
    ]);
    item.addEventListener("pointerdown", (event) => startPaletteDrag(kind, event, view));
    host.appendChild(item);
  });
}

function concernDetail(group, view) {
  const evidenceIds = group.evidence.map((e) => e.id);
  const domains = group.riskDomains.map((d) => d.label).join(", ");
  GraphView.setHighlight(evidenceIds);
  revealInSource(evidenceIds);

  const head = el("div", { class: "concern-head" }, [
    el("span", { class: `scope-tag ${group.scopeMatch}` }, SCOPE_LABELS[group.scopeMatch]),
    el("strong", {}, group.label),
    // Concerns that share a name say where, here as on the diagram.
    group.distinguisher ? el("span", { class: "chip" }, "at " + group.distinguisher) : null,
    group.corroboration > 1
      ? el("span", { class: "chip corroborated" }, `${group.corroboration} structures`)
      : null,
    group.clearable ? el("span", { class: "chip clearable" }, "control to apply") : null,
    group.settled ? el("span", { class: `chip decided ${group.status}` }, group.status) : null,
  ]);

  const body = [head];

  body.push(detailRow("may lead to", domains
    ? domains
    : el("span", { class: "dim" }, "no risk domain linked")));

  if (group.description) {
    body.push(foldRow("what this is", "", el("p", { class: "concern-desc" }, group.description)));
  }

  if (group.why.length) {
    body.push(foldRow("why", `${group.why.length} condition${group.why.length > 1 ? "s" : ""}`,
      whyList(group.why)));
  }

  body.push(foldRow("where", `${group.evidence.length} element${group.evidence.length > 1 ? "s" : ""}`,
    group.evidence.map((e) => e.label).join(" → ")));

  if (group.statedRisks.length) {
    body.push(detailRow("also stated", group.statedRisks.map((r) => el("span", {
      class: `chip stated ${(r.priority || {}).key || ""}`,
      title: r.priority ? `${r.priority.label} priority` : "no priority stated",
    }, r.label))));
  }

  if (group.applicableControls.length) {
    body.push(detailRow("fix", group.applicableControls.map((control) => {
      const button = el("button", {
        type: "button", class: "chip motif-suggest clickable",
        title: "Insert this control on the path this concern cites, then re-assess",
      }, `Apply ${control.label}`);
      button.addEventListener("click", (ev) => {
        ev.stopPropagation();
        applyControl(control, { id: group.applyTo, label: group.label });
      });
      return button;
    })));
  } else if (group.otherControls.length) {
    body.push(detailRow("suggested",
      el("span", {
        class: "dim",
        title: "No structural rewrite clears this one, so it goes to triage.",
      }, group.otherControls.map((c) => c.label).join(", "))));
  }

  // What a person added to this candidate, so it reads beside what the run said.
  const added = ((view || {}).diagram || { links: [] }).links
    .filter((link) => link.editable && (
      (link.source === group.key && link.label === "hasConsequence")
      || (link.target === group.key && link.label === "modifiesRiskConcept")))
    .map((link) => (link.source === group.key ? link.target : link.source));
  if (added.length) {
    body.push(detailRow("added by hand", added.map((id) => {
      const row = el("button", { type: "button", class: "chip clickable" }, nameOf(id, view));
      row.addEventListener("click", () => { RiskCanvas.select(id); renderRail(); });
      return row;
    })));
  }

  if (group.motifs.length) {
    body.push(foldRow("raised by", `${group.motifs.length} motif${group.motifs.length > 1 ? "s" : ""}`,
      el("span", { class: "dim" }, group.motifs.join(", "))));
  }
  body.push(triageRow(group));

  return el("div", {
    class: "rail-detail concern-card" + (group.settled ? ` settled ${group.status}` : ""),
  }, body);
}


function whyList(why) {
  return el("ul", { class: "why-list" }, why.map((text) => el("li", {}, text)));
}

/* A folded row: the key is the control, and the hint says how much is behind it
   so a reader can tell whether to open it. The panel carried a paragraph, nine
   conditions and a chain of elements all open at once, which is more than
   anyone reads at a glance - and the parts worth acting on were below it. */
function foldRow(key, hint, value, extra) {
  const values = Array.isArray(value) ? value : [value];
  return el("details", { class: "concern-row concern-fold" + (extra ? " " + extra : "") }, [
    el("summary", {}, [
      el("span", { class: "concern-key" }, key),
      hint ? el("span", { class: "dim small" }, hint) : null,
    ]),
    el("div", { class: "concern-val" }, values),
  ]);
}

function detailRow(key, value, extra) {
  const values = Array.isArray(value) ? value : [value];
  return el("div", { class: "concern-row" + (extra ? " " + extra : "") }, [
    el("span", { class: "concern-key" }, key),
    el("div", { class: "concern-val" }, values),
  ]);
}

function triageRow(group) {
  const decided = group.decisions[0];
  const row = detailRow(decided ? "decided" : "triage", [], "concern-triage");
  const cell = row.querySelector(".concern-val");

  if (decided) {
    cell.appendChild(el("span", { class: "triage-note" }, [
      el("strong", {}, group.status),
      decided.rationale ? el("span", {}, ` — ${decided.rationale}`) : null,
      el("span", { class: "dim" },
        ` (${[decided.statedBy, decided.date].filter(Boolean).join(", ") || "unattributed"})`),
    ]));
    const undo = el("button", { type: "button", class: "chip clickable" }, "reopen");
    undo.addEventListener("click", (ev) => { ev.stopPropagation(); decide(group, ""); });
    cell.appendChild(undo);
    return row;
  }

  TRIAGE.forEach(([status, text, why]) => {
    const button = el("button", { type: "button", class: "chip clickable", title: why }, text);
    button.addEventListener("click", (ev) => { ev.stopPropagation(); decide(group, status); });
    cell.appendChild(button);
  });
  return row;
}

function decide(group, status) {
  if (!status) {
    return edit("triage", { findings: group.findingIds, status: "" },
      `reopened ${group.label}`, { rerun: true });
  }
  const rationale = window.prompt(`Why is "${group.label}" ${status}?`, "");
  if (rationale === null) return Promise.resolve();
  const statedBy = window.prompt("Who decided that?", "") || "";
  return edit("triage",
    { findings: group.findingIds, status, rationale, statedBy },
    `${status}: ${group.label}`, { rerun: true });
}

function stormToggle(view) {
  const button = el("button", {
    type: "button",
    class: "storm-toggle" + (storming ? " on" : ""),
    title: "Risk storming states risks in silence first, before reading the run",
  }, storming
    ? `Show the run (${view.summary.concerns})`
    : "Hide the run");
  button.addEventListener("click", () => { storming = !storming; renderRisk(); });
  return button;
}

// ---- render ----

export async function refreshRegister() {
  try {
    register = await postJson("/api/scope", { ttl: Editor.getValue() });
  } catch (_) {
    register = null; // an unparseable graph already says so in the status bar
  }
}

export function clearRisk() {
  storming = false;
  register = null;
  expanded.clear();
  focus = null;
  RiskCanvas.forgetLayout();

  RiskCanvas.clear();
  const empty = $("#risk-canvas-empty");
  if (empty) empty.classList.add("hidden");
  const side = $("#risk-side");
  if (side) side.innerHTML = "";
}

export function renderRisk() {
  if (!$("#risk-view")) return;
  renderRail();

  const view = drawable();
  const empty = $("#risk-canvas-empty");
  
  renderLayerBar(true);
  renderPalette(true, view);

  if (!view || !view.diagram.nodes.length) {
    RiskCanvas.render({ nodes: [], links: [], bands: [] }, state.lastGraph,
      { layers, focus, expanded });
    const bare = !RiskCanvas.painted();
    empty.classList.remove("hidden");
    empty.classList.toggle("over-drawing", !bare);
    empty.innerHTML = "";
    empty.appendChild(el("span", { class: "empty-note" }, currentView()
      ? "Nothing was raised and nothing was stated on this graph."
      : "No assessment yet - drag a risk onto a box, or run the assessment."));
    return;
  }
  empty.classList.add("hidden");
  empty.classList.remove("over-drawing");
  RiskCanvas.render(storming ? statedOnly(view.diagram) : view.diagram, state.lastGraph,
    { layers, focus, expanded });
}

const layers = { business: true, architecture: true, risk: true };
let focus = null;
const expanded = new Set();

function unfold(system, open) {
  if (open) expanded.add(system); else expanded.delete(system);
  renderRisk();
}

const LAYER_LABEL = {
  business: "Business", architecture: "Architecture", risk: "Risk",
};

function renderLayerBar(show) {
  const bar = $("#risk-layers");
  if (!bar) return;
  const tools = $("#risk-tools");
  if (tools) tools.classList.toggle("hidden", !show);
  bar.classList.toggle("hidden", !show);
  if (!show) return;
  bar.innerHTML = "";

  Object.keys(layers).forEach((layer) => {
    const button = el("button", {
      type: "button",
      class: "layer-toggle" + (layers[layer] ? " on" : ""),
      title: `Show or hide the ${LAYER_LABEL[layer].toLowerCase()} layer`,
    }, LAYER_LABEL[layer]);
    button.addEventListener("click", () => {
      layers[layer] = !layers[layer];
      renderRisk();
    });
    bar.appendChild(button);
  });

  const run = currentView();
  if (run) bar.appendChild(stormToggle(run));

  const systems = (state.lastGraph && state.lastGraph.systems) || [];
  if (systems.length < 2) return;
  const picker = el("select", { class: "layer-focus", title: "Read one architecture at a time" }, [
    el("option", focus ? { value: "" } : { value: "", selected: "selected" },
      `Every architecture (${systems.length})`),
    ...systems.map((system) => el("option",
      focus === system.id ? { value: system.id, selected: "selected" } : { value: system.id },
      system.label)),
  ]);
  picker.addEventListener("change", () => {
    focus = picker.value || null;
    RiskCanvas.clearSelection();
    renderRisk();
  });
  bar.appendChild(picker);
}

function unfoldDetail() {
  const tray = $("#risk-side-tray");
  if (tray) tray.classList.remove("collapsed");
}


function renderRail() {
  const side = $("#risk-side");
  if (!side) return;
  side.innerHTML = "";
  const view = drawable();
  const picked = RiskCanvas.selected();
  const line = RiskCanvas.link();

  if (view && line) { side.appendChild(connectionDetail(line, view)); return; }
  if (view && picked) {
    const group = (view.groups || []).find((g) => g.key === picked);
    if (group) { side.appendChild(concernDetail(group, view)); return; }
    const node = view.diagram.nodes.find((n) => n.id === picked);
    if (node) { side.appendChild(nodeDetail(node, view)); return; }
    const part = elementDetail(picked, view);
    if (part) { side.appendChild(part); return; }
  }

  side.appendChild(el("p", { class: "dim small rail-empty" },
    view ? "Pick a box to see what stands behind it." : "Nothing to read yet."));
}

function drawable() {
  const view = currentView();
  const stated = (register && register.diagram) || null;
  if (view) return stated ? { ...view, diagram: mergeStated(view.diagram, stated, view.groups) } : view;
  const diagram = stated;
  if (!diagram) return null;
  return {
    diagram,
    groups: [],
    statedRisks: (register && register.statedRisks) || [],
    scope: (register && register.scope) || null,
    handWritten: true,
  };
}

function mergeStated(run, stated, groups) {
  const nodes = run.nodes.filter((node) => node.origin !== "stated");
  const links = run.links.filter((link) => !link.editable);
  const known = new Set(nodes.map((node) => node.id));
  stated.nodes.forEach((node) => { if (!known.has(node.id)) nodes.push(node); });
  // The live register names a finding; the run says which concern holds it.
  const concernOfFinding = new Map();
  (groups || []).forEach((group) =>
    (group.findingIds || []).forEach((id) => concernOfFinding.set(id, group.key)));
  const seen = new Set();
  const placed = [];
  stated.links.forEach((link) => {
    let { source, target } = link;
    if (link.findingEnd === "source") source = concernOfFinding.get(source);
    if (link.findingEnd === "target") target = concernOfFinding.get(target);
    if (!source || !target) return;
    const key = `${source}|${target}|${link.label}`;
    if (seen.has(key)) return;
    seen.add(key);
    placed.push({ ...link, source, target });
  });
  return { ...run, nodes, links: [...links, ...placed] };
}

function currentView() {
  return (state.lastAssessment || {}).riskView || null;
}


function statedOnly(diagram) {
  const kept = new Set(diagram.nodes.filter((n) => n.origin === "stated").map((n) => n.id));
  return {
    ...diagram,
    nodes: diagram.nodes.filter((n) => kept.has(n.id)),
    links: diagram.links.filter((l) => kept.has(l.source) && (l.kind === "attaches" || kept.has(l.target))),
  };
}


function elementDetail(id, view) {
  const graph = state.lastGraph || {};
  const element = (graph.nodes || []).find((node) => node.id === id);
  if (!element) return null;
  const owner = (graph.systems || []).find((system) => (system.members || []).includes(id));
  const here = (view.groups || []).filter(
    (group) => group.evidence.some((cited) => cited.id === id));

  const box = el("div", { class: "rail-detail" }, [
    el("h3", {}, element.typeLabel || "Element"),
    el("div", { class: "concern-head" }, [el("strong", {}, element.label)]),
  ]);
  if (owner) box.appendChild(detailRow("part of", owner.label));
  if (element.roles && element.roles.length) {
    box.appendChild(detailRow("plays", element.roles.join(" · ")));
  }
  if (element.categories && element.categories.length) {
    box.appendChild(detailRow("carries", element.categories.join(" · ")));
  }
  box.appendChild(detailRow(
    here.length ? `${here.length} concern${here.length > 1 ? "s" : ""}` : "concerns",
    here.length
      ? here.map((group) => {
        const row = el("button", { type: "button", class: "frame-risk" }, group.label);
        row.addEventListener("click", () => { RiskCanvas.select(group.key); renderRail(); });
        return row;
      })
      : el("span", { class: "dim" }, "none cite this")));
  return box;
}

function frameDetail(node, view) {
  const mine = node.isSystem ? [node.id] : (node.refines || []);
  const groups = new Map((view.groups || []).map((group) => [group.key, group]));
  const here = ((view.diagram || {}).nodes || []).filter(
    (entry) => entry.band === "risk" && mine.some((s) => (entry.systems || []).includes(s)));

  const box = el("div", { class: "rail-detail" }, [
    el("h3", {}, node.isSystem ? "System" : "Activity"),
    el("div", { class: "concern-head" }, [el("strong", {}, node.title)]),
    node.body ? el("p", { class: "concern-desc" }, node.body) : null,
  ]);

  if (node.isSystem) {
    const count = (node.members || []).length;
    const open = expanded.has(node.id);
    const toggle = el("button", { type: "button", class: "chip clickable" },
      `${open ? "Fold" : "Unfold"} ${count} part${count === 1 ? "" : "s"}`);
    toggle.addEventListener("click", () => unfold(node.id, !open));
    box.appendChild(detailRow("built from", count ? toggle : el("span", { class: "dim" }, "nothing")));
    const work = ((view.diagram || {}).nodes || [])
      .filter((entry) => entry.isActivity && (entry.refines || []).includes(node.id));
    if (work.length) box.appendChild(detailRow("runs", work.map((w) => w.title).join(" · ")));
  } else if (mine.length) {
    box.appendChild(detailRow("refines",
      mine.map((id) => nameOf(id, view)).join(" · ")));
  }

  if (!here.length) {
    box.appendChild(el("p", { class: "dim small" },
      "No concern in this run lands here."));
    return box;
  }
  const list = here.map((entry) => {
    const group = groups.get(entry.id);
    const row = el("button", { type: "button", class: "frame-risk" }, entry.title);
    row.addEventListener("click", () => {
      RiskCanvas.select(entry.id);
      renderRail();
    });
    return group && group.settled ? el("span", { class: "frame-risk-settled" }, [row]) : row;
  });
  box.appendChild(detailRow(`${here.length} concern${here.length > 1 ? "s" : ""}`, list));
  return box;
}

function nodeDetail(node, view) {
  if (node.isSystem || node.isActivity) return frameDetail(node, view);
  const box = el("div", { class: "rail-detail" }, [
    el("h3", {}, BAND_LABEL[node.band] || node.band),
    el("div", { class: "concern-head" }, [el("strong", {}, node.title)]),
    node.body ? el("p", { class: "concern-desc" }, node.body) : null,
    el("p", { class: "dim small" }, node.origin === "stated"
      ? "Manual entry."
      : "Derived from this run. Dashed border on the diagram."),
  ]);
  const reaching = view.groups.filter((g) =>
    view.diagram.links.some((l) =>
      (l.source === node.id && l.target === g.key) || (l.target === node.id && l.source === g.key)));
  if (reaching.length) {
    box.appendChild(el("h3", {}, `Reaches ${reaching.length} concern${reaching.length > 1 ? "s" : ""}`));
    reaching.forEach((g) => box.appendChild(el("div", { class: "ov-row" }, g.label)));
  }
  const joins = ((view.diagram || {}).links || [])
    .filter((link) => link.source === node.id && link.editable)
    .map((link) => nameOf(link.target, view));
  if (joins.length) box.appendChild(detailRow("attached to", joins.join(" · ")));

  if (node.origin === "stated" && node.band === "risk") {
    box.appendChild(verdictRow(node, view));
    box.appendChild(chainRow(node, view));
  }

  // Written by hand, so it is named, joined up and taken back the same way.
  if (node.origin === "stated" && HAND_BANDS.has(node.band)) {
    box.appendChild(nameForm(node));
    const connect = connectForm(node, view);
    if (connect) box.appendChild(connect);
    const remove = el("button", {
      type: "button", class: "chip clickable danger",
      title: "Removes it from the graph, along with what pointed at it.",
    }, "remove this");
    remove.addEventListener("click", () => {
      RiskCanvas.clearSelection();
      edit("remove-concept", { concept: node.id }, `removed ${node.title}`);
    });
    box.appendChild(remove);
  }
  return box;
}

const HAND_BANDS = new Set(["risk", "source", "consequence", "impact", "control"]);

function verdictRow(node, view) {
  const also = (view.groups || []).filter(
    (group) => (group.statedRisks || []).some((stated) => stated.id === node.id));
  if (!also.length) {
    return detailRow("the run", el("span", { class: "dim" }, "raised nothing here"));
  }
  return detailRow("the run", also.map((group) => {
    const row = el("button", { type: "button", class: "frame-risk" },
      `also raised ${group.label}`);
    row.addEventListener("click", () => { RiskCanvas.select(group.key); renderRail(); });
    return row;
  }));
}

const CHAIN_PARTS = [
  ["source", "isRiskSourceFor"],
  ["consequence", "hasConsequence"],
  ["control", "modifiesRiskConcept"],
];

function chainRow(node, view) {
  const links = (view.diagram || {}).links || [];
  const marks = CHAIN_PARTS.map(([part, relation]) => {
    const there = links.some((link) => link.label === relation
      && (link.target === node.id || link.source === node.id));
    return el("span", { class: there ? "chain-has" : "chain-missing" },
      `${there ? "✓" : "–"} ${part}`);
  });
  return detailRow("chain", marks);
}


function nameOf(id, view) {
  const drawn = ((view.diagram || {}).nodes || []).find((node) => node.id === id);
  if (drawn) return drawn.title;
  const element = ((state.lastGraph && state.lastGraph.nodes) || [])
    .find((node) => node.id === id);
  return element ? element.label : id.split(/[#/]/).pop();
}


function connectionDetail(line, view) {
  const box = el("div", { class: "rail-detail" }, [
    el("h3", {}, "Connection"),
    el("div", { class: "concern-head" }, [el("strong", {}, nameOf(line.from, view))]),
    detailRow("joins", nameOf(line.to, view)),
    detailRow("as", el("span", { class: "mono" }, line.label)),
  ]);
  const remove = el("button", {
    type: "button", class: "chip clickable danger",
    title: "Removes this one relation. Nothing else on the assessment changes.",
  }, "remove this connection");
  remove.addEventListener("click", () => {
    RiskCanvas.clearSelection();
    const concern = concernOf(line.from, view) || concernOf(line.to, view);
    edit("unlink-concept", {
      from: line.from, to: line.to, ...(concern ? { findings: concern.findingIds } : {}),
    }, "removed a connection");
  });
  box.appendChild(remove);
  return box;
}


function nameForm(node) {
  const kind = node.band;
  const offered = (shelf && shelf[kind]) || [];
  const rows = [];

  const name = el("input", { type: "text", class: "scope-input", value: node.title || "" });
  let picker = null;
  if (offered.length) {
    const named = (node.concernsRiskPattern || node.id);
    picker = el("select", { class: "scope-select" }, [
      el("option", { value: "" }, "choose from the library…"),
      ...offered.map((row) => el("option",
        row.id === named ? { value: row.id, selected: "selected" } : { value: row.id },
        row.label)),
    ]);
    picker.addEventListener("change", () => {
      const row = offered.find((entry) => entry.id === picker.value);
      if (row) name.value = row.label;
    });
    rows.push(detailRow(
      kind === "control" ? "a control the library knows" : "a risk the library knows", picker));
  }
  rows.push(detailRow("called", name));

  const apply = el("button", { type: "button", class: "btn small primary" }, "Apply");
  apply.addEventListener("click", () => {
    const label = name.value.trim();
    const chosen = picker ? picker.value : "";
    if (!label && !chosen) { name.focus(); return; }
    const payload = { concept: node.id };
    if (label) payload.label = label;
    if (chosen) payload.fromLibrary = chosen;
    edit("rename-concept", payload, `named it ${label || "from the library"}`,
      { onMade: (id) => { if (id) RiskCanvas.select(id); } });
  });
  rows.push(detailRow("", apply));
  return el("div", { class: "name-form" }, rows);
}

function connectForm(node, view) {
  const rule = HAND_DROP[node.band];
  if (!rule) return null;
  const joined = new Set(((view.diagram || {}).links || [])
    .filter((link) => link.source === node.id).map((link) => link.target));

  const options = [];
  ((view.diagram || {}).nodes || []).forEach((other) => {
    if (other.id !== node.id && rule.bands.includes(other.band) && !joined.has(other.id)) {
      options.push({ id: other.id, label: other.title });
    }
  });
  if (rule.element) {
    ((state.lastGraph && state.lastGraph.nodes) || []).forEach((element) => {
      if (!joined.has(element.id)) options.push({ id: element.id, label: element.label });
    });
  }
  if (!options.length) return null;

  const picker = el("select", { class: "scope-input" },
    options.map((row) => el("option", { value: row.id }, row.label)));
  const join = el("button", { type: "button", class: "btn small" }, "Connect");
  join.addEventListener("click", () => {
    const concern = concernOf(picker.value, view);
    if (concern && !ON_CANDIDATES.has(node.band)) {
      setStatus("error", "A candidate the run raised takes a consequence or a control.");
      return;
    }
    edit("link-concept", {
      from: node.id, to: picker.value, ...(concern ? { findings: concern.findingIds } : {}),
    }, "connected it");
  });
  return el("details", { class: "scope-add" }, [
    el("summary", {}, `+ connect to ${rule.where}`),
    el("div", { class: "scope-add-body" }, [picker, join]),
  ]);
}
