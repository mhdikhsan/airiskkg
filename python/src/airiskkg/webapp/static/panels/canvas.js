import { postJson } from "../core/api.js";
import { emit } from "../core/bus.js";
import { $, el } from "../core/dom.js";
import { openDrawer, setTabVisible } from "../core/drawer.js";
import { mapSource, revealInSource } from "../core/source.js";
import { parseErrorLine, setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { createSystem } from "./palette.js";
import { refreshRegister, renderRisk } from "./risk.js";
import { scheduleStaleCheck } from "./run.js";
import { ProcessCanvas, humanKind } from "../lib/process_canvas.js";
import { state } from "../state.js";

let awaitingChoice = true;

let hadProcess = false; 

export function resetScope() {
  state.scopedSystem = null;
  state.openedFrom = null;
  renderBreadcrumb();
}

export function askAgain() {
  awaitingChoice = true;
  hadProcess = false;
  state.levelChosenByHand = false;
  $("#canvas-wrap").classList.remove("started");
  $("#canvas-wrap").classList.add("unstarted");
  $("#level-switch").classList.add("hidden");
}

export function settleChoice() {
  awaitingChoice = false;
  $("#canvas-wrap").classList.remove("unstarted");
  $("#canvas-wrap").classList.add("started");
  $("#level-switch").classList.remove("hidden");
  emit("choice:settled");
}

export function startDrawing(level) {
  settleChoice();
  state.levelChosenByHand = true;
  setLevel(level);
  if (level === "business") {
    openDrawer("process");
    setStatus("ok", "Business process", "add a participant, then steps inside it");
    return;
  }
  if (level === "risk") {
    document.body.classList.add("editor-hidden");
    $("#drawer").classList.add("collapsed");
    $("#drawer-toggle").innerHTML = "&#9650;";
    refreshRegister().then(renderRisk);
    setStatus("ok", "Risk", "state what must not happen, then see what to look for");
    return;
  }
  setStatus("ok", "AI architecture", "drag a symbol onto the canvas, or load an example");
}

function architectureHasContent() {
  return Boolean(state.lastGraph && state.lastGraph.nodes && state.lastGraph.nodes.length);
}

export function setLevel(next, activity) {
  state.level = next;
  state.openedFrom = next === "architecture" ? activity || state.openedFrom : null;
  $("#canvas").classList.toggle("hidden", next !== "architecture");
  $("#process-canvas").classList.toggle("hidden", next !== "business");
  $("#risk-view").classList.toggle("hidden", next !== "risk");
  $("#level-business").classList.toggle("active", next === "business");
  $("#level-architecture").classList.toggle("active", next === "architecture");
  $("#level-risk").classList.toggle("active", next === "risk");
  $("#process-palette").classList.toggle("hidden", next !== "business");
  $("#palette").classList.toggle("hidden", next !== "architecture");
  $("#motif-palette").classList.toggle("hidden", next !== "architecture");
  $("#process-detail").classList.add("hidden");
  $("#canvas-wrap").classList.toggle("business", next === "business");
  /* The risk level is a document, not a drawing: the zoom controls and the
   * system bar act on a canvas that is not on screen. */
  $("#canvas-wrap").classList.toggle("risk", next === "risk");
  renderBreadcrumb();
  if (next === "risk") return;
  requestAnimationFrame(() => {
    if (next === "business") ProcessCanvas.fit();
    else GraphView.fit();
  });
}

function renderBreadcrumb() {
  const crumb = $("#breadcrumb");
  crumb.innerHTML = "";
  if (!state.openedFrom || state.level !== "architecture") {
    crumb.classList.add("hidden");
    return;
  }
  const parts = [
    { label: state.openedFrom.lane || "business process", to: "business" },
    { label: state.openedFrom.label, to: "business" },
    { label: "architecture", to: null },
  ];
  parts.forEach((part, index) => {
    if (index) crumb.appendChild(el("span", { class: "crumb-sep" }, "›"));
    if (part.to) {
      const link = el("button", { type: "button", class: "crumb-link" }, part.label);
      link.addEventListener("click", () => {
        state.scopedSystem = null;
        setLevel(part.to);
        emit("scope:changed");
      });
      crumb.appendChild(link);
    } else {
      crumb.appendChild(el("span", { class: "crumb-here" }, part.label));
    }
  });
  crumb.classList.remove("hidden");
}

const TASK_KINDS = {
  task: "Task",
  userTask: "User",
  manualTask: "Manual",
  serviceTask: "Service",
  scriptTask: "Script",
  sendTask: "Send",
  receiveTask: "Receive",
  businessRuleTask: "Business rule",
  subProcess: "Sub-process",
  callActivity: "Call activity",
  transaction: "Transaction",
  adHocSubProcess: "Ad-hoc",
};

function taskKind(kind) {
  return TASK_KINDS[kind] || humanKind(kind);
}

async function refreshProcess(ttl) {
  const list = $("#process-list");
  const summary = $("#process-summary");
  const empty = $("#process-empty");
  let data;
  try {
    data = await postJson("/api/process", { ttl });
  } catch (error) {
    return; // an unparseable graph already says so in the status bar
  }

  ProcessCanvas.setSystems(
    (state.lastGraph && state.lastGraph.systems ? state.lastGraph.systems : []).map((s) => ({ id: s.id, label: s.label }))
  );
  ProcessCanvas.setSystemContext(data.refinedSystems, data.contextOptions);
  state.lastProcess = data;
  if (awaitingChoice && (data.stats.activities || architectureHasContent())) settleChoice();
  ProcessCanvas.render(data);
  mapSource([...data.participants, ...data.activities, ...(data.events || []),
    ...(data.gateways || []), ...(data.lanes || [])], "business");
  const hasProcess = data.stats.activities > 0 || (data.participants || []).length > 0;
  $("#level-switch").classList.toggle("hidden", awaitingChoice && !hasProcess);
  setTabVisible("process", hasProcess);

  if (!hasProcess && state.level === "business") setLevel("architecture");
  else if (hasProcess && !hadProcess && !state.levelChosenByHand) setLevel("business");
  hadProcess = hasProcess;

  list.innerHTML = "";
  summary.innerHTML = "";
  const count = data.stats.activities;
  $("#process-count").textContent = count ? String(count) : "";
  empty.classList.toggle("hidden", count > 0);
  if (!count) return;

  const actors = data.participants.map((a) => a.label).join(" · ");
  const descriptive = data.processes.filter((x) => x.isExecutable === false).length;
  summary.appendChild(el("div", { class: "summary-row" }, [
    actors ? el("span", { class: "stat" }, actors) : null,
    el("span", { class: "stat" }, `${count} activities`),
    data.stats.refined ? el("span", { class: "stat" }, `${data.stats.refined} AI`) : null,
    data.stats.humanSteps ? el("span", { class: "stat" }, `${data.stats.humanSteps} human`) : null,
    data.stats.gateways ? el("span", { class: "stat" }, `${data.stats.gateways} gateways`) : null,
    data.stats.events ? el("span", { class: "stat" }, `${data.stats.events} events`) : null,
    descriptive
      ? el("span", { class: "hint" }, `${descriptive} not marked executable`)
      : null,
  ]));

  renderProcessList(list, data);
}

/* One activity, as a row of the list. */
function processRow(activity, depth) {
  const badges = [];
  if (activity.refines.length) badges.push(el("span", { class: "proc-badge ai" }, "AI system"));
  if (activity.human) badges.push(el("span", { class: "proc-badge human" }, "human"));
  activity.reads.forEach((item) => {
    item.kinds.forEach((kind) =>
      badges.push(el("span", { class: "proc-badge data" }, `reads ${humanKind(kind)}`)));
  });

  const row = el("div", { class: `proc-row depth-${depth}` }, [
    el("span", { class: "proc-kind", title: activity.kind }, taskKind(activity.kind)),
    el("span", { class: "proc-name" }, activity.label),
    el("span", { class: "proc-badges" }, badges),
    activity.performers.length
      ? el("span", { class: "proc-by" }, activity.performers.join(", "))
      : null,
  ]);

  if (activity.refines.length) {
    row.classList.add("refined");
    row.addEventListener("click", () => {
      setLevel("architecture", activity);
      GraphView.setHighlight(activity.refines);
      revealInSource(activity.refines);
    });
    row.title = "Open the AI architecture this activity is carried out by";
  }
  return row;
}

function flowRank(data) {
  const nodes = [...data.activities, ...(data.events || []), ...(data.gateways || [])];
  const label = new Map(nodes.map((n) => [n.id, n.label || ""]));
  const next = new Map(nodes.map((n) => [n.id, []]));
  const incoming = new Map(nodes.map((n) => [n.id, 0]));
  for (const flow of data.sequenceFlows || []) {
    if (!next.has(flow.source) || !incoming.has(flow.target)) continue;
    next.get(flow.source).push(flow.target);
    incoming.set(flow.target, incoming.get(flow.target) + 1);
  }
  const byLabel = (a, b) => label.get(a).localeCompare(label.get(b));
  const ready = [...incoming.keys()].filter((id) => incoming.get(id) === 0).sort(byLabel);
  const rank = new Map();
  while (ready.length) {
    const id = ready.shift();
    rank.set(id, rank.size);
    for (const target of next.get(id)) {
      incoming.set(target, incoming.get(target) - 1);
      if (incoming.get(target) === 0) { ready.push(target); ready.sort(byLabel); }
    }
  }
  // A loop leaves its nodes unranked; they follow, in the model's own order.
  nodes.forEach((n) => { if (!rank.has(n.id)) rank.set(n.id, rank.size); });
  return rank;
}

function renderProcessList(list, data) {
  const byId = new Map(data.activities.map((a) => [a.id, a]));
  const rank = flowRank(data);
  const inFlowOrder = (items) => [...items].sort((a, b) => rank.get(a.id) - rank.get(b.id));
  // A step inside a sub-process is listed by its parent, under the parent's pool.
  const topOf = (activity) => {
    let at = activity;
    while (at.parent && byId.has(at.parent)) at = byId.get(at.parent);
    return at;
  };
  const childrenOf = (activity) => inFlowOrder(data.activities.filter((a) => a.parent === activity.id));

  const addActivity = (activity, depth) => {
    list.appendChild(processRow(activity, depth));
    childrenOf(activity).forEach((child) => addActivity(child, depth + 1));
  };
  const heading = (cls, label, count) => el("div", { class: cls }, [
    el("span", {}, label),
    el("span", { class: "proc-count" }, String(count)),
  ]);

  const tops = inFlowOrder(data.activities.filter((a) => !a.parent || !byId.has(a.parent)));
  const pools = data.participants || [];
  const placed = new Set();

  pools.forEach((pool) => {
    const mine = tops.filter((a) => topOf(a).process === pool.process);
    if (!mine.length) return;
    mine.forEach((a) => placed.add(a.id));
    list.appendChild(heading("proc-pool", pool.label, mine.length));

    // Declaration order, the order the canvas bands them in.
    const lanes = (data.lanes || [])
      .filter((lane) => lane.process === pool.process)
      .sort((a, b) => (a.line ?? Infinity) - (b.line ?? Infinity)
        || a.id.localeCompare(b.id, undefined, { numeric: true }));

    if (!lanes.length) {
      // No lanes declared: the activities are the pool's, directly.
      mine.forEach((activity) => addActivity(activity, 1));
      return;
    }
    const laneIds = new Set(lanes.map((lane) => lane.id));
    lanes.forEach((lane) => {
      const inLane = mine.filter((a) => a.laneId === lane.id);
      if (!inLane.length) return;
      list.appendChild(heading("proc-lane", lane.label, inLane.length));
      inLane.forEach((activity) => addActivity(activity, 2));
    });
    const loose = mine.filter((a) => !laneIds.has(a.laneId));
    if (loose.length) {
      list.appendChild(heading("proc-lane unassigned",
        "Not in any of this pool's lanes", loose.length));
      loose.forEach((activity) => addActivity(activity, 2));
    }
  });

  // An activity whose process no participant points at still has to be listed.
  const outside = tops.filter((a) => !placed.has(a.id));
  if (outside.length) {
    list.appendChild(heading("proc-pool unassigned", "In no participant", outside.length));
    outside.forEach((activity) => addActivity(activity, 1));
  }
}

export function refreshSystemBar() {
  if (state.lastGraph) renderSystemBar(state.lastGraph);
}

function renderSystemBar(data) {
  const badge = $("#system-badge");
  const unclaimed = (data.unclaimed || []).length;
  if (data.systems.length || data.nodes.length) {

    const shown = data.scopedTo
      ? data.systems.filter((s) => s.id === data.scopedTo)
      : data.systems;

    badge.innerHTML = "";
    shown.forEach((system, index) => {
      if (index) badge.appendChild(document.createTextNode(" · "));
      const link = el("button", {
        type: "button", class: "system-badge-name",
        title: "Name, describe or delete this AI system",
      }, system.label);
      link.addEventListener("click", (ev) => GraphView.editSystem(system.id, ev));
      badge.appendChild(link);
    });
    if (unclaimed) {
      /* Not just a complaint. */
      if (shown.length) badge.appendChild(document.createTextNode(" · "));
      const orphans = el("button", {
        type: "button", class: "system-badge-orphans",
        title: "These elements are in no system, so no business activity can point at them."
          + " Click to put them in one.",
      }, `${unclaimed} in no system`);
      orphans.addEventListener("click", () => createSystem(unclaimed, data.systems.length));
      badge.appendChild(orphans);
    }
    const chosen = GraphView.getSelectedSystem();
    if (chosen) {
      const picked = data.systems.find((row) => row.id === chosen);
      if (picked) {
        badge.appendChild(document.createTextNode(" · "));
        badge.appendChild(el("span", { class: "system-badge-chosen" },
          `adding to: ${picked.label}`));
      }
    }
    const add = el("button", {
      type: "button", class: "system-badge-add", title: "Create an AI system",
    }, "+ system");
    add.addEventListener("click", () => createSystem(unclaimed, data.systems.length));
    badge.appendChild(add);
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

//  live preview 
/* An empty document has no business layer either. */
function resetProcess() {
  const empty = {
    participants: [], processes: [], activities: [], lanes: [], messageFlows: [],
    events: [], gateways: [], sequenceFlows: [], artifacts: [], associations: [],
    stats: {
      activities: 0, participants: 0, processes: 0, refined: 0, humanSteps: 0,
      events: 0, gateways: 0, lanes: 0,
    },
  };
  state.lastProcess = empty;
  ProcessCanvas.render(empty);
  setTabVisible("process", false);
  hadProcess = false;
  if (state.level === "business" && !state.levelChosenByHand) setLevel("architecture");
  $("#process-list").innerHTML = "";
  $("#process-summary").innerHTML = "";
  $("#process-count").textContent = "";
  $("#process-empty").classList.remove("hidden");
}

let previewSeq = 0;

export async function refreshPreview(ttl) {
  const seq = ++previewSeq;
  if (!ttl.trim()) {
    GraphView.clear();
    resetProcess();
    $("#system-badge").classList.add("hidden");
    setStatus("ok", "Ready");
    return;
  }
  scheduleStaleCheck(ttl);
  try {
    const data = await postJson("/api/graph", { ttl, scope: state.scopedSystem });
    if (seq !== previewSeq) return;
    state.lastGraph = data;
    GraphView.render(data);
    /* After the architecture is known, so the level decision has something to
     * go on rather than always believing the canvas is empty. */
    refreshProcess(ttl);
    mapSource([...data.nodes, ...data.systems]);
    Editor.markErrorLine(null);
    renderSystemBar(data);
    setStatus("ok", "Graph parsed", `${data.stats.nodes} nodes · ${data.stats.edges} edges`);
  } catch (error) {
    if (seq !== previewSeq) return;
    const line = parseErrorLine(error.message);
    Editor.markErrorLine(line);
    const firstLine = error.message.split("\n").find((l) => l.trim()) || "Parse error";
    setStatus("error", line ? `Line ${line}: ${firstLine}` : firstLine);
  }
}
