import { postJson } from "../core/api.js";
import { $, $$, el } from "../core/dom.js";
import { Editor } from "../lib/editor.js";
import { ProcessCanvas } from "../lib/process_canvas.js";
import { createRiskCanvas } from "../lib/risk_canvas.js";
import { state } from "../state.js";

function overviewDiagram() {
  const source = ProcessCanvas.svgRoot();
  if (!source) return null;
  const copy = source.cloneNode(true);
  copy.removeAttribute("id");
  copy.classList.remove("hidden");
  /* Interaction affordances are noise on a page nobody can interact with. */
  copy.querySelectorAll(".pc-port, .pc-marker, .pc-risk").forEach((n) => n.remove());
  const root = copy.querySelector("#pc-root");
  if (root) {
    root.removeAttribute("transform");
    root.removeAttribute("id");
  }
  copy.setAttribute("width", "100%");
  return copy;
}

/* Unscoped on purpose: the reader may have scoped the canvas to one system,
   and the overview answers for the whole process. Refetched per opening, so a
   changed graph is never answered from the last one. */
let architecture = null;

async function architectureGraph() {
  if (!architecture) {
    architecture = await postJson("/api/graph", { ttl: Editor.getValue(), scope: null });
  }
  return architecture;
}

function closeSystem() {
  openLenses = [];
  const box = $("#overview-system");
  box.classList.add("hidden");
  box.innerHTML = "";
  $$("#overview-diagram .ov-open").forEach((n) => n.classList.remove("ov-open"));
}

function memberList(system, nodes) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const groups = new Map();
  for (const id of system.members || []) {
    const node = byId.get(id);
    if (!node) continue;
    const key = node.kind === "process" ? "Steps" : node.kind === "agent" ? "Agents" : "Resources";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(node);
  }
  const order = ["Steps", "Agents", "Resources"];
  return [...groups.entries()]
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([name, items]) =>
      el("div", {}, [
        el("div", { class: "ov-sys-group-name" }, `${name} · ${items.length}`),
        ...items.map((node) =>
          el("div", { class: "ov-sys-item" }, [
            el("span", {}, node.label),
            el("span", { class: `ov-sys-roles${node.roles.length ? "" : " none"}` },
              node.roles.length ? ` — ${node.roles.join(", ")}` : " — no role yet"),
          ])),
      ]));
}

/* Mounted per opening: the renderer is a factory, so this panel and the risk
   level each keep their own selection, pan and hand-placed boxes. */
let openLenses = [];

function lensPanel(box, row, activity, many) {
  const frame = el("div", { class: `ov-sys-canvas${many ? " multi" : ""}` });
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("id", `ov-lens-${openLenses.length}`);
  frame.appendChild(svg);
  box.appendChild(frame);

  const detail = el("div", { class: "ov-sys-detail" });
  box.appendChild(detail);

  const canvas = createRiskCanvas();
  openLenses.push(canvas);
  canvas.init(`#${svg.id}`, {
    onSelect: (picked) => {
      detail.innerHTML = "";
      if (!picked) return;
      const point = [...row.lens.process, ...row.lens.architecture]
        .find((entry) => entry.id === picked);
      if (point) {
        detail.appendChild(el("div", { class: "ov-sys-note" },
          `${point.label} — ${point.why}`));
        return;
      }
      const concern = row.lens.about.find((entry) => "about:" + entry.key === picked);
      if (concern) {
        detail.appendChild(el("div", { class: "ov-sys-note" },
          `${concern.label}${concern.why.length ? " — " + concern.why[0] : ""}`));
      }
    },
  });
  /* Drawn now, not on the next frame: the frame is already in the document
     with a height of its own, so there is nothing to wait for - and a canvas
     that waits draws nothing at all where animation frames do not run. */
  canvas.renderLens(row.lens);
  requestAnimationFrame(() => canvas.fit());

  /* Dragging the frame's own resize handle is only useful if the drawing
     follows it. The first callback is the mount, which fit() already handled. */
  if (typeof ResizeObserver === "function") {
    let mounted = false;
    new ResizeObserver(() => {
      if (mounted) canvas.fit();
      mounted = true;
    }).observe(frame);
  }
  return frame;
}

/* Panning away is cheap; getting back should be too. */
function fitLenses() {
  openLenses.forEach((canvas) => canvas.fit());
}

async function showSystem(activity) {
  const box = $("#overview-system");
  openLenses = [];
  box.innerHTML = "";
  box.classList.remove("hidden");

  const byProcess = ((state.lastAssessment || {}).riskView || {}).byProcess;
  const wanted = new Set(activity.refines);
  const rows = (byProcess && byProcess.present ? byProcess.systems : [])
    .filter((row) => wanted.has(row.id));

  box.appendChild(el("div", { class: "ov-sys-head" }, [
    el("h3", {}, rows.length
      ? rows.map((row) => row.label).join(" · ")
      : "Architecture"),
    el("span", { class: "ov-sys-for" }, `carries out ${activity.label}`),
    el("button", { class: "ov-sys-act", type: "button", onclick: fitLenses,
                   title: "Bring the whole risk view back into the frame" }, "Fit"),
    el("button", { class: "ov-sys-close", type: "button", onclick: closeSystem }, "Close"),
  ]));

  /* The run placed on this one system: what it holds, what bears on it in the
     work either side, and what the library raised about it. */
  if (rows.length) {
    rows.forEach((row) => {
      const many = rows.length > 1;
      const s = row.lens.summary;
      box.appendChild(el("p", { class: "ov-sys-note" },
        `${s.about} concern${s.about === 1 ? "" : "s"} · `
        + `${s.architecture} points in ${row.label} · ${s.process} in the process around it`));
      lensPanel(box, row, activity, many);
    });
    return;
  }

  // No run yet: the parts list is still the honest answer to "what is in here".
  box.appendChild(el("p", { class: "ov-sys-note" }, "Reading the architecture…"));
  let graph;
  try {
    graph = await architectureGraph();
  } catch (err) {
    box.appendChild(el("p", { class: "ov-sys-note" },
      `Could not read the architecture: ${err.message}`));
    return;
  }
  const systems = (graph.systems || []).filter((system) => wanted.has(system.id));
  box.querySelectorAll(".ov-sys-note").forEach((n) => n.remove());
  box.querySelector(".ov-sys-head h3").textContent =
    systems.length ? systems.map((system) => system.label).join(" · ") : "Architecture";

  if (!systems.length) {
    box.appendChild(el("p", { class: "ov-sys-note" },
      "This activity names an architecture that is not in the graph on screen."));
    return;
  }
  for (const system of systems) {
    const note = [system.description, system.context].filter(Boolean).join(" — ");
    if (note) box.appendChild(el("p", { class: "ov-sys-note" }, note));
    const groups = memberList(system, graph.nodes || []);
    box.appendChild(groups.length
      ? el("div", { class: "ov-sys-grid" }, groups)
      : el("p", { class: "ov-sys-note" }, "This architecture holds no elements yet."));
  }
  box.appendChild(el("p", { class: "ov-sys-note dim" },
    "Run the assessment to see the risk on this system instead of its parts."));
}



const SVG_NS = "http://www.w3.org/2000/svg";

/* Concerns, drawn on the work they arise under.
 *
 * Attribution is not partition: one AI system carries several activities, so
 * the mark on each says what that system carries, and the count beside it is
 * the system's - never a per-activity total that would add up to more concerns
 * than the run produced. */
function markRisk(svg, byProcess) {
  const marked = [];
  (byProcess.systems || []).forEach((system) => {
    if (!system.concerns.length) return;
    system.activities.forEach((activity) => {
      const group = svg.querySelector(`[data-node="${CSS.escape(activity.id)}"]`);
      if (!group || !group.getBBox) return;
      const box = group.getBBox();
      if (!box.width) return;
      group.classList.add("ov-at-risk");

      const mark = document.createElementNS(SVG_NS, "g");
      mark.setAttribute("class", "ov-risk-mark");
      mark.setAttribute("data-system", system.id);
      const r = 11;
      const cx = box.x + box.width - r - 2;
      const cy = box.y - r + 2;
      const dot = document.createElementNS(SVG_NS, "circle");
      dot.setAttribute("cx", cx);
      dot.setAttribute("cy", cy);
      dot.setAttribute("r", r);
      mark.appendChild(dot);
      const count = document.createElementNS(SVG_NS, "text");
      count.setAttribute("x", cx);
      count.setAttribute("y", cy + 4);
      count.setAttribute("text-anchor", "middle");
      count.setAttribute("class", "ov-risk-count");
      count.textContent = String(system.concerns.length);
      mark.appendChild(count);
      const hint = document.createElementNS(SVG_NS, "title");
      hint.textContent = `${system.concerns.length} candidate concerns in ${system.label}, `
        + `which carries out ${system.activities.map((a) => a.label).join(", ")}`;
      mark.appendChild(hint);
      group.appendChild(mark);
      marked.push({ system: system.id, top: cy - r });
    });
  });
  return marked;
}

function domainChips(domains) {
  return el("div", { class: "ov-domains" },
    domains.length
      ? domains.map((d) => el("span", { class: "chip tax" }, d))
      : [el("span", { class: "chip dim" }, "no risk domain linked")]);
}

/* One card per AI system the process calls, named once however many activities
 * it carries out. A system with nothing found is still listed: on a page shown
 * to stakeholders, "we looked and found nothing represented here" is half the
 * message. */
function capabilityCard(system, onFocus) {
  const card = el("div", {
    class: "ov-cap" + (system.concerns.length ? "" : " clean"),
    tabindex: "0",
  }, [
    el("div", { class: "ov-cap-head" }, [
      el("strong", {}, system.label),
      el("span", { class: system.concerns.length ? "ov-count" : "ov-count clean" },
        String(system.concerns.length)),
    ]),
    el("div", { class: "ov-cap-work" },
      "carries out " + system.activities.map((a) => a.label).join(", ")),
    system.concerns.length ? domainChips(system.domains) : null,
    /* Folded: every AI system the process calls has to be visible at once,
       including the ones with nothing found. */
    system.concerns.length
      ? el("details", { class: "ov-cap-detail" }, [
        el("summary", {}, `${system.concerns.length} concerns`),
        ...system.concerns.map((concern) => el("div", { class: "ov-concern" }, [
          el("div", {}, [
            el("div", {}, concern.label),
            /* Two concerns can carry the same name at different places, and on
               this page that reads as a duplicate unless each says where. */
            el("div", { class: "ov-where" }, concern.evidence.join(" → ")),
            (concern.spans || []).length
              ? el("div", { class: "ov-where" }, `also in ${concern.spans.join(", ")}`)
              : null,
          ]),
          concern.settled
            ? el("span", { class: "chip decided " + concern.status }, concern.status)
            : (concern.clearable
              ? el("span", {
                class: "chip clearable",
                title: "A suggested control can be inserted on this path from the risk view, "
                  + "and a re-run would not raise this concern.",
              }, "control to apply")
              : null),
        ])),
      ])
      : el("div", { class: "ov-cap-work dim" },
        "Nothing was raised here. Under the open world assumption that is about "
        + "what the graph represents, not about the system."),
  ]);
  card.addEventListener("click", (ev) => {
    if (ev.target.closest("summary")) return;  // the fold is its own control
    onFocus(system.id);
  });
  return card;
}

/* What the run found, as this process sees it. */
function riskSection(side, view, diagram) {
  const byProcess = view.byProcess;
  if (!byProcess || !byProcess.present) {
    side.appendChild(el("p", { class: "ov-note dim" },
      "No activity in this process names an architecture, so nothing the run "
      + "found can be placed on the work."));
    return;
  }
  const s = byProcess.summary;

  side.appendChild(el("h3", {}, "What this process carries"));
  side.appendChild(el("div", { class: "summary-row" }, [
    el("span", { class: "stat" }, `${s.inProcess} of ${s.concerns} concerns`),
    el("span", { class: "stat" }, `${s.withConcerns} of ${s.aiSystems} AI systems`),
    s.offProcess
      ? el("span", { class: "stat warn" }, `${s.offProcess} outside this process`)
      : null,
    // Without this the cards add up to more than the run found, and nothing says why.
    s.spanning
      ? el("span", { class: "stat dim" }, `${s.spanning} span two systems`)
      : null,
  ]));
  side.appendChild(domainChips(s.domains || []));

  const focus = (systemId) => {
    diagram.querySelectorAll(".ov-risk-mark").forEach((mark) => {
      mark.classList.toggle("dim",
        Boolean(systemId) && mark.getAttribute("data-system") !== systemId);
    });
  };
  (byProcess.systems || []).forEach((system) =>
    side.appendChild(capabilityCard(system, focus)));

  // Named, never dropped: an architecture no activity carries out.
  if (byProcess.offProcess.length) {
    side.appendChild(el("h3", {}, "Not carried out by this process"));
    side.appendChild(el("p", { class: "ov-note dim" },
      "Raised by the run, in an architecture no activity here calls. Filtered "
      + "off the diagram rather than out of the assessment."));
    byProcess.offProcess.forEach((concern) =>
      side.appendChild(el("div", { class: "ov-row dim" }, [
        el("span", {}, concern.label),
        el("span", { class: "dim" },
          concern.systems.length ? ` — ${concern.systems.join(", ")}` : ""),
      ])));
  }

  side.appendChild(el("p", { class: "ov-note" },
    "Candidates for triage, not confirmed failures. An AI system is named once, "
    + "however many activities it carries out."));
}


export function openOverview() {
  const panel = $("#overview");
  const diagram = $("#overview-diagram");
  const side = $("#overview-side");
  diagram.innerHTML = "";
  side.innerHTML = "";
  architecture = null;
  closeSystem();
  /* Before the fit, not after: getBBox measures nothing inside display:none,
     so a diagram fitted while hidden collapses to a 40px line. */
  panel.classList.remove("hidden");

  const process = state.lastProcess;
  if (!process || !process.stats.activities) {
    diagram.appendChild(el("p", { class: "drawer-empty" },
      "No business process in this graph yet. Draw one on the Business canvas, or load one from Load example."));
  } else {
    const svg = overviewDiagram();
    if (svg) {
      diagram.appendChild(svg);
      // A viewBox, so the page scales the drawing rather than cropping it.
      const drawn = svg.querySelector("g");
      if (drawn && drawn.getBBox) {
        const box = drawn.getBBox();
        svg.setAttribute("viewBox",
          `${box.x - 20} ${box.y - 20} ${box.width + 40} ${box.height + 40}`);
        svg.setAttribute("height", Math.min(box.height + 40, 520));
      }
      const byId = new Map(process.activities.map((a) => [a.id, a]));
      svg.querySelectorAll("[data-node]").forEach((node) => {
        const activity = byId.get(node.getAttribute("data-node"));
        if (activity && activity.refines.length) node.classList.add("ov-openable");
      });
      /* After the viewBox, so the marks are measured in the same units, and
         the box is grown to take a mark that sits above the top row. */
      if (state.lastAssessment && state.lastAssessment.riskView
          && state.lastAssessment.riskView.byProcess) {
        const marked = markRisk(svg, state.lastAssessment.riskView.byProcess);
        const highest = Math.min(...marked.map((m) => m.top), Infinity);
        const current = (svg.getAttribute("viewBox") || "").split(" ").map(Number);
        if (isFinite(highest) && current.length === 4 && highest < current[1]) {
          const grown = current[1] - highest + 8;
          svg.setAttribute("viewBox",
            `${current[0]} ${highest - 8} ${current[2]} ${current[3] + grown}`);
        }
      }

      svg.addEventListener("click", (ev) => {
        const hit = ev.target.closest("[data-node]");
        const activity = hit && byId.get(hit.getAttribute("data-node"));
        if (!activity || !activity.refines.length) return;
        $$("#overview-diagram .ov-open").forEach((n) => n.classList.remove("ov-open"));
        hit.classList.add("ov-open");
        showSystem(activity);
      });
    }
    $("#overview-title").textContent =
      process.processes.map((p) => p.participant || p.label).join(" · ") || "Business context";

    side.appendChild(el("h3", {}, "Who is involved"));
    process.participants.forEach((actor) =>
      side.appendChild(el("div", { class: "ov-row" }, actor.label)));

    side.appendChild(el("h3", {}, "AI capability"));
    const ai = process.activities.filter((a) => a.refines.length);
    if (!ai.length) {
      side.appendChild(el("div", { class: "ov-row dim" }, "No activity is carried out by an AI system."));
    }
    ai.forEach((activity) => {
      side.appendChild(el("div", {
        class: "ov-row clickable",
        title: "Show the architecture that carries this out",
        onclick: () => showSystem(activity),
      }, [
        el("strong", {}, activity.label),
        el("span", { class: "dim" }, ` · ${activity.lane || "no lane"}`),
      ]));
    });
  }

  if (state.lastAssessment) {
    riskSection(side, state.lastAssessment.riskView || {}, diagram);
    if (state.lastAssessment.run && state.lastAssessment.run.knowledgeBase) {
      const kb = state.lastAssessment.run.knowledgeBase;
      side.appendChild(el("p", { class: "ov-note dim" },
        `Assessed with library ${kb.fingerprint} — ${kb.motifs} motifs, ${kb.riskPatterns} risk patterns.`));
    }
  } else {
    side.appendChild(el("p", { class: "ov-note dim" },
      "Run an assessment to see what was found in this context."));
  }
}
