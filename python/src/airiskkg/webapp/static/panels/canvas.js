import { postJson } from "../core/api.js";
import { emit } from "../core/bus.js";
import { $, el } from "../core/dom.js";
import { setTabVisible } from "../core/drawer.js";
import { mapSource, revealInSource } from "../core/source.js";
import { parseErrorLine, setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { scheduleStaleCheck } from "./run.js";
import { ProcessCanvas, humanKind } from "../lib/process_canvas.js";
import { state } from "../state.js";

/* Nothing chosen and nothing loaded: the tools for both layers would be on
 * screen before the reader has said which one they came for. */
let awaitingChoice = true;

let hadProcess = false; // so landing happens when a process arrives, not on every refresh

/* A different document is on screen, so the narrowing from the last one means
 * nothing. Leaving it set filtered every finding out of a graph that no longer
 * holds that system: "0 of 18 candidate findings", with the breadcrumb still
 * naming an activity from the example before. */
export function resetScope() {
  state.scopedSystem = null;
  state.openedFrom = null;
  // Redraw, or the trail keeps naming an activity of the example before.
  renderBreadcrumb();
}

export function settleChoice() {
  awaitingChoice = false;
  $("#canvas-wrap").classList.remove("unstarted");
  // The question has been answered; leaving it on screen behind an empty
  // canvas reads as the answer having gone nowhere.
  $("#canvas-wrap").classList.add("started");
  $("#level-switch").classList.remove("hidden");
}

function architectureHasContent() {
  return Boolean(state.lastGraph && state.lastGraph.nodes && state.lastGraph.nodes.length);
}

export function setLevel(next, activity) {
  state.level = next;
  state.openedFrom = next === "architecture" ? activity || state.openedFrom : null;
  $("#canvas").classList.toggle("hidden", next !== "architecture");
  $("#process-canvas").classList.toggle("hidden", next !== "business");
  $("#level-business").classList.toggle("active", next === "business");
  $("#level-architecture").classList.toggle("active", next === "architecture");
  $("#process-palette").classList.toggle("hidden", next !== "business");
  $("#palette").classList.toggle("hidden", next !== "architecture");
  $("#motif-palette").classList.toggle("hidden", next !== "architecture");
  $("#process-detail").classList.add("hidden");
  /* Architecture furniture - the empty-state overlay, the legend, the system
   * badge - is absolutely positioned across the whole wrap, so it painted
   * over a perfectly good business diagram. One class, hidden in CSS. */
  $("#canvas-wrap").classList.toggle("business", next === "business");
  renderBreadcrumb();
  /* After the browser has actually laid the newly shown surface out. Fitting
   * synchronously measured an element that was display:none a statement ago
   * and produced a drawing the size of a full stop. */
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

/* BPMN task types read as identifiers in the model and as words on a diagram.
 * The list beside the canvas showed "receiveTask" and "subProcess" while the
 * canvas had been drawing the glyph for them all along. */
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
  state.lastProcess = data;
  if (awaitingChoice && (data.stats.activities || architectureHasContent())) settleChoice();
  ProcessCanvas.render(data);
  const hasProcess = data.stats.activities > 0;
  /* Visible once either layer has been chosen or loaded. Hiding it until a
   * process existed meant choosing "a business process" on an empty workbench
   * left no way back to the architecture. */
  $("#level-switch").classList.toggle("hidden", awaitingChoice && !hasProcess);
  setTabVisible("process", hasProcess);

  /* Land where there is something to see. A process loaded on its own leaves
   * the architecture canvas legitimately empty - there are no BEAM elements -
   * and with nothing saying to press Business, both surfaces read as broken.
   * Only ever chosen for the reader, never taken away from them: once they
   * have picked a level by hand, it stays picked. */
  /* Land on the layer the graph is about. A process was opened to be looked
   * at, so it is shown - previously the presence of an architecture won,
   * which meant loading a business example dropped you into the architecture
   * and the BPMN diagram had to be hunted for. A reader who has picked a
   * level by hand keeps it. */
  /* Only when a process first appears. This ran on every refresh, and
   * descending into an activity triggers one - so the canvas switched to the
   * architecture and was immediately dragged back to the business layer. It
   * looked like a glitch and was a rule fighting the click that caused it. */
  if (!hasProcess && state.level === "business") setLevel("architecture");
  else if (hasProcess && !hadProcess && !state.levelChosenByHand) setLevel("business");
  hadProcess = hasProcess;

  list.innerHTML = "";
  summary.innerHTML = "";
  const count = data.stats.activities;
  $("#process-count").textContent = count ? String(count) : "";
  empty.classList.toggle("hidden", count > 0);
  if (!count) return;

  /* One line. It used to print a row per process, each repeating the same
   * global counts, so a two-pool collaboration claimed twice that "1 of 10
   * activities are AI" - both noisier and wrong. */
  const actors = data.participants.map((a) => a.label).join(" · ");
  const descriptive = data.processes.filter((x) => x.isExecutable === false).length;
  summary.appendChild(el("div", { class: "summary-row" }, [
    actors ? el("span", { class: "stat" }, actors) : null,
    el("span", { class: "stat" }, `${count} activities`),
    data.stats.refined ? el("span", { class: "stat" }, `${data.stats.refined} AI`) : null,
    data.stats.humanSteps ? el("span", { class: "stat" }, `${data.stats.humanSteps} human`) : null,
    descriptive
      ? el("span", { class: "hint" }, `${descriptive} not marked executable`)
      : null,
  ]));

  let lane = null;
  data.activities.forEach((activity) => {
    if (activity.lane !== lane) {
      lane = activity.lane;
      list.appendChild(el("div", { class: "proc-lane" }, lane || "no lane"));
    }
    const badges = [];
    if (activity.refines.length) badges.push(el("span", { class: "proc-badge ai" }, "AI system"));
    if (activity.human) badges.push(el("span", { class: "proc-badge human" }, "human"));
    activity.reads.forEach((item) => {
      item.kinds.forEach((kind) =>
        badges.push(el("span", { class: "proc-badge data" }, `reads ${humanKind(kind)}`)));
    });

    const row = el("div", { class: "proc-row" }, [
      el("span", { class: "proc-kind", title: activity.kind }, taskKind(activity.kind)),
      el("span", { class: "proc-name" }, activity.label),
      el("span", { class: "proc-badges" }, badges),
      activity.performers.length
        ? el("span", { class: "proc-by" }, activity.performers.join(", "))
        : null,
    ]);

    /* Expand: the AI activity is one box here and a whole architecture when
     * opened. Clicking it highlights the system that carries it and puts the
     * cursor on its source, which is as far as one editor pane can take the
     * idea. */
    if (activity.refines.length) {
      row.classList.add("refined");
      row.addEventListener("click", () => {
        setLevel("architecture", activity);
        GraphView.setHighlight(activity.refines);
        revealInSource(activity.refines);
      });
      row.title = "Open the AI architecture this activity is carried out by";
    }
    list.appendChild(row);
  });
}

//  live preview 
let previewSeq = 0;

export async function refreshPreview(ttl) {
  const seq = ++previewSeq;
  if (!ttl.trim()) {
    GraphView.clear();
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
    const badge = $("#system-badge");
    if (data.systems.length) {
      /* When the canvas is narrowed, name the one system on screen. Listing
       * every system the document holds would caption a drawing that shows
       * only one of them. */
      const shown = data.scopedTo
        ? data.systems.filter((s) => s.id === data.scopedTo)
        : data.systems;
      badge.textContent = shown.map((s) => s.label).join(" · ")
        + (data.unclaimed && data.unclaimed.length
            ? ` · ${data.unclaimed.length} element(s) belong to no system`
            : "");
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
    setStatus("ok", "Graph parsed", `${data.stats.nodes} nodes · ${data.stats.edges} edges`);
  } catch (error) {
    if (seq !== previewSeq) return;
    const line = parseErrorLine(error.message);
    Editor.markErrorLine(line);
    const firstLine = error.message.split("\n").find((l) => l.trim()) || "Parse error";
    setStatus("error", line ? `Line ${line}: ${firstLine}` : firstLine);
  }
}
