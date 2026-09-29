/* The risk view: the third level, and the only one that opens before a graph.
 *
 * Architecture answers "what is built", process answers "who is exposed". This
 * one answers "what did we come here to find out, and did we find it" - so it
 * carries the scope a person states, the concerns the run raised, and the
 * reconciliation between the two. */

import { postJson } from "../core/api.js";
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
/* Risk storming identifies risks in silence first, on purpose: a reader who
 * has seen the library's answers will not add one it missed. Offered, never
 * enforced - the discipline is the team's to keep. */
let storming = false;
const SCOPE_LABELS = {
  in: "answers the scope",
  out: "outside the scope",
  unclassified: "no risk domain linked",
  all: "no scope stated",
};

/* An out-of-scope concern is set aside, never removed - and one that reaches no
 * catalogued domain is neither in nor out, because nothing upstream maps it. */

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
  RiskCanvas.init("#risk-canvas", { onSelect: () => renderRail(), onUnfold: unfold });
  $("#btn-risk-zoom-in").addEventListener("click", () => RiskCanvas.zoom(1.2));
  $("#btn-risk-zoom-out").addEventListener("click", () => RiskCanvas.zoom(0.83));
  $("#btn-risk-fit").addEventListener("click", () => RiskCanvas.fit());
  // Told rather than called into: the panel that draws a run is not this one.
  on("assessment:rendered", () => refreshRegister().then(renderRisk));
  foldable("#btn-tools-fold", "#risk-tools", "the tools");
  foldable("#btn-side-fold", "#risk-side-tray", "the detail");
}

/* Both trays fold the way the architecture palettes do: the head stays, so what
   folded a tray is also what brings it back, and the canvas refits because the
   room it has to draw in just changed. */
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

/* `rerun` for the edits whose whole point is what the run then says: a
 * judgement recorded against a finding is invisible until the finding carries
 * it. A scope edit needs none - the band reads the document, not the run. */
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

/* Assessing by hand.
 *
 * The library is 15 risk patterns over 31 motifs, which is a fraction of what
 * an assessor wants to record. Everything outside it would otherwise be lost,
 * so a person writes the same four concepts directly onto the graph and they
 * travel with it - drawn beside what the run found, marked as theirs, and
 * exported as Turtle like everything else. No query matches anything here. */

/* What each kind may be dropped on, which is what the vocabulary allows: a risk
   hangs off an element of the design, a consequence off a risk, an impact off a
   consequence, and a source off either an element or the risk it gives rise to. */
const HAND_DROP = {
  /* A system is a beam:Element too, so a risk hangs off a whole architecture
     with the relation the vocabulary already has. That is what makes a first
     pass possible before any part is unfolded. A business activity is neither
     an Element nor a Task, so it is not offered. */
  risk: { bands: ["system"], element: true, where: "a system or an element" },
  source: { bands: ["risk", "system"], element: true, where: "an element or a risk" },
  consequence: { bands: ["risk"], element: false, where: "a risk" },
  impact: { bands: ["consequence"], element: false, where: "a consequence" },
  /* A control is the one that points outward at what it changes, and
     beamr:modifiesRiskConcept ranges over every one of the four. Writing one
     down is not applying it - nothing is inserted into the design and no
     finding clears; it records that somebody says this is handled. */
  control: {
    bands: ["risk", "source", "consequence", "impact"], element: false,
    where: "a risk, source or consequence",
  },
};

/* Every box a drop would be accepted on, marked before the drag starts rather
   than discovered by trying: "drag this somewhere" is not an instruction.
 *
 * Only boxes that stand for a node in the graph. A concern the library raised
 * is a group of findings keyed by (risk pattern, evidence) - there is no such
 * subject to hang anything off, and hanging one off it is the conflation the
 * method forbids anyway: a control clears a finding by being built, not by
 * being asserted, and a finding is answered by triage. */
function markDroppable(kind, view) {
  const rule = HAND_DROP[kind];
  const bands = new Set((((view || {}).diagram || {}).nodes || [])
    .filter((node) => rule.bands.includes(node.band) && node.origin === "stated")
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

/* Drawn on, rather than filled in: drag the shape onto what it is about.
 *
 * Nothing is matched here - this is the assessor's own judgement, written in
 * the same vocabulary a run emits so it travels with the graph and exports with
 * it. The library is small, and what it cannot say still has to be recordable. */
function startPaletteDrag(kind, event, view) {
  event.preventDefault();
  event.stopPropagation();
  /* The box that will be written, following the cursor, the way the
     architecture palette drags a symbol. It stays for the whole gesture even
     when there is nowhere to put it: a drag that shows nothing cannot be told
     from one that never started, and the status bar is read afterwards. */
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
      // Said once, where it is needed: what the library raised is triaged.
      setStatus("error", droppable.length
        ? `Drop a ${noun} on ${HAND_DROP[kind].where}.`
        : HAND_DROP[kind].element
          ? `Nothing to drop it on yet: a ${noun} needs ${HAND_DROP[kind].where}.`
          : `A ${noun} attaches to a risk written by hand. `
            + "What the library raised is answered by triage instead.");
      return;
    }
    const label = window.prompt(`Name the ${HAND_LABEL[kind].toLowerCase()}:`, "");
    if (!label || !label.trim()) return;
    edit("state-concept", { kind, label: label.trim(), attachTo: [found.id] },
      `wrote a ${HAND_LABEL[kind].toLowerCase()} by hand`);
  };

  window.addEventListener("pointermove", place);
  window.addEventListener("pointerup", finish);
  place(event);
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
        el("span", { class: "pal-where" }, `onto ${HAND_DROP[kind].where}`),
      ]),
    ]);
    item.addEventListener("pointerdown", (event) => startPaletteDrag(kind, event, view));
    host.appendChild(item);
  });
}

function concernDetail(group) {
  const evidenceIds = group.evidence.map((e) => e.id);
  const domains = group.riskDomains.map((d) => d.label).join(", ");
  // Selecting on the canvas is also selecting in the architecture and the source.
  GraphView.setHighlight(evidenceIds);
  revealInSource(evidenceIds);

  const head = el("div", { class: "concern-head" }, [
    el("span", { class: `scope-tag ${group.scopeMatch}` }, SCOPE_LABELS[group.scopeMatch]),
    el("strong", {}, group.label),
    group.corroboration > 1
      ? el("span", { class: "chip corroborated" }, `${group.corroboration} structures`)
      : null,
    group.clearable ? el("span", { class: "chip clearable" }, "control to apply") : null,
    group.settled ? el("span", { class: `chip decided ${group.status}` }, group.status) : null,
  ]);

  const body = [head];

  if (group.description) body.push(el("p", { class: "concern-desc" }, group.description));

  if (group.why.length) body.push(detailRow("why", whyList(group.why)));

  body.push(detailRow("may lead to", domains
    ? domains
    : el("span", { class: "dim" }, "no risk domain linked")));

  body.push(detailRow("where", group.evidence.map((e) => e.label).join(" → ")));

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

  if (group.motifs.length) {
    body.push(detailRow("raised by", el("span", { class: "dim" }, group.motifs.join(", "))));
  }
  body.push(triageRow(group));

  return el("div", {
    class: "rail-detail concern-card" + (group.settled ? ` settled ${group.status}` : ""),
  }, body);
}


/* The extension point the vocabulary always declared and nothing ever wrote.
 * Three risk patterns carry no structural escape at all, so for those this is
 * the only honest disposition - and risk storming keeps what was decided NOT
 * to be a risk for the same reason. */
/* Every line in a concern is the same shape: a small label, then the value on
   its own full-width line. Mixing inline and stacked rows is what made the
   card read as unsorted. */
/* The conditions that held, one per line and the tail folded away.
   Run together with separators they were a paragraph nobody finished. */
const WHY_SHOWN = 3;

function whyList(why) {
  const line = (text) => el("li", {}, text);
  const list = el("ul", { class: "why-list" }, why.slice(0, WHY_SHOWN).map(line));
  if (why.length <= WHY_SHOWN) return list;
  return [list, el("details", { class: "why-more" }, [
    el("summary", {}, `${why.length - WHY_SHOWN} more`),
    el("ul", { class: "why-list" }, why.slice(WHY_SHOWN).map(line)),
  ])];
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
  const rationale = window.prompt(
    `Why is "${group.label}" ${status}?

A judgement nobody can read back is not reviewable.`,
    "");
  if (rationale === null) return Promise.resolve();
  const statedBy = window.prompt("Who decided that?", "") || "";
  return edit("triage",
    { findings: group.findingIds, status, rationale, statedBy },
    `${status}: ${group.label}`, { rerun: true });
}

/* Offered, never enforced: a team shown the library's answers first will
   ratify them and add nothing it missed. */
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

/* The graph read back without running anything: what people stated, and the
   notation drawn from it. An assessment written by hand shows up through this. */
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
  RiskCanvas.forgetLayout();
  const side = $("#risk-side");
  if (side) side.innerHTML = "";
}

export function renderRisk() {
  if (!$("#risk-view")) return;
  renderRail();

  const view = drawable();
  const empty = $("#risk-canvas-empty");
  // Assessing by hand needs no run: the architecture is on screen, the palette
  // is on it, and what is written lands in the graph either way.
  renderLayerBar(true);
  renderPalette(true, view);

  if (!view || !view.diagram.nodes.length) {
    empty.classList.remove("hidden");
    empty.textContent = currentView()
      ? "Nothing was raised and nothing was stated on this graph."
      : "Nothing has been assessed yet. Drag a risk from the palette onto an element "
        + "to record one of your own, or run the assessment to see what the library finds.";
    RiskCanvas.render({ nodes: [], links: [], bands: [] }, state.lastGraph,
      { layers, focus, expanded });
    return;
  }
  empty.classList.add("hidden");
  RiskCanvas.render(storming ? statedOnly(view.diagram) : view.diagram, state.lastGraph,
    { layers, focus, expanded });
}

/* Which layers are on screen, and which architecture is being read.
 *
 * The notation draws every risk in every architecture at once, which is what
 * made it hard to follow. Business starts off because it is the outermost
 * frame, not what a reader opens the risk level for. */
const layers = { business: true, architecture: true, risk: true };
let focus = null;
/* Which architectures have been unfolded. Empty on purpose: the risk view opens
   on the work and the systems, and the parts are asked for. */
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

/* Everything that used to be a list is now the detail of what the canvas has
 * selected: pick a risk box and this is what stands behind it. */
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

  /* Nothing picked, nothing to say. What the rail used to stack up here was
     read past rather than read. */
  side.appendChild(el("p", { class: "dim small rail-empty" },
    view ? "Pick a box to see what stands behind it." : "Nothing to read yet."));
}

/* What is on the canvas. After a run that is the run, with the hand-written
   layer taken from the graph as it is now; before one it is only what people
   wrote - an assessment does not have to wait for a query to match. */
function drawable() {
  const view = currentView();
  const stated = (register && register.diagram) || null;
  if (view) return stated ? { ...view, diagram: mergeStated(view.diagram, stated) } : view;
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

/* The run's own layer, with the hand-written one taken from the graph as it is
   now. Stated nodes are replaced rather than added to: the graph is the truth
   about them, and the run's copy is as old as the run. */
function mergeStated(run, stated) {
  const nodes = run.nodes.filter((node) => node.origin !== "stated");
  const links = run.links.filter((link) => !link.editable);
  const known = new Set(nodes.map((node) => node.id));
  stated.nodes.forEach((node) => { if (!known.has(node.id)) nodes.push(node); });
  return { ...run, nodes, links: [...links, ...stated.links] };
}

function currentView() {
  return (state.lastAssessment || {}).riskView || null;
}

/* Storming, on the diagram: what the run derived comes off, what people drew
 * stays. The architecture underneath is what they are storming over. */
function statedOnly(diagram) {
  const kept = new Set(diagram.nodes.filter((n) => n.origin === "stated").map((n) => n.id));
  return {
    ...diagram,
    nodes: diagram.nodes.filter((n) => kept.has(n.id)),
    links: diagram.links.filter((l) => kept.has(l.source) && (l.kind === "attaches" || kept.has(l.target))),
  };
}

/* A box that is not a concern still has something to say - which is why it is
 * on the diagram at all. */
/* One part of an architecture, picked once its system is unfolded: where it
   sits and what was raised on it. Unfolding is only worth doing if the parts
   answer something the system box could not. */
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

/* A system or an activity, picked. The coarse boxes are the anchor now, so
   picking one has to answer what stands in it - not just repeat its name. */
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
      ? "Stated by a person. Solid border on the diagram."
      : "Derived from this run. Dashed border on the diagram."),
  ]);
  const reaching = view.groups.filter((g) =>
    view.diagram.links.some((l) =>
      (l.source === node.id && l.target === g.key) || (l.target === node.id && l.source === g.key)));
  if (reaching.length) {
    box.appendChild(el("h3", {}, `Reaches ${reaching.length} concern${reaching.length > 1 ? "s" : ""}`));
    reaching.forEach((g) => box.appendChild(el("div", { class: "ov-row" }, g.label)));
  }
  /* What it hangs off, which is the question a box on its own cannot answer:
     a risk source attaches to any element of the design - a step, a data node,
     a model, an agent or a whole system. */
  const joins = ((view.diagram || {}).links || [])
    .filter((link) => link.source === node.id && link.editable)
    .map((link) => nameOf(link.target, view));
  if (joins.length) box.appendChild(detailRow("attached to", joins.join(" · ")));

  // Written by hand, so it can be taken back the same way.
  if (node.origin === "stated" && HAND_BANDS.has(node.band)) {
    const connect = connectForm(node, view);
    if (connect) box.appendChild(connect);
    const remove = el("button", {
      type: "button", class: "chip clickable",
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

/* A name for anything on the diagram, including the architecture underneath it,
   so a connection can say what it joins rather than showing two IRIs. */
function nameOf(id, view) {
  const drawn = ((view.diagram || {}).nodes || []).find((node) => node.id === id);
  if (drawn) return drawn.title;
  const element = ((state.lastGraph && state.lastGraph.nodes) || [])
    .find((node) => node.id === id);
  return element ? element.label : id.split(/[#/]/).pop();
}

/* One line, picked. A connection drawn wrong should cost that connection - not
   the assessment it is part of. */
function connectionDetail(line, view) {
  const box = el("div", { class: "rail-detail" }, [
    el("h3", {}, "Connection"),
    el("div", { class: "concern-head" }, [el("strong", {}, nameOf(line.from, view))]),
    detailRow("joins", nameOf(line.to, view)),
    detailRow("as", el("span", { class: "mono" }, line.label)),
  ]);
  const remove = el("button", {
    type: "button", class: "chip clickable",
    title: "Removes this one relation. Nothing else on the assessment changes.",
  }, "remove this connection");
  remove.addEventListener("click", () => {
    RiskCanvas.clearSelection();
    edit("unlink-concept", { from: line.from, to: line.to },
      "removed a connection");
  });
  box.appendChild(remove);
  return box;
}

/* Joining a hand-written concept to something else, after the fact. */
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
    edit("link-concept", { from: node.id, to: picker.value },
      "connected it");
  });
  return el("details", { class: "scope-add" }, [
    el("summary", {}, `+ connect to ${rule.where}`),
    el("div", { class: "scope-add-body" }, [picker, join]),
  ]);
}
