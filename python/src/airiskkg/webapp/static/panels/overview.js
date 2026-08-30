import { $, el } from "../core/dom.js";
import { ProcessCanvas } from "../lib/process_canvas.js";
import { state } from "../state.js";

function overviewDiagram() {
  const source = ProcessCanvas.svgRoot();
  if (!source) return null;
  const copy = source.cloneNode(true);
  copy.removeAttribute("id");
  copy.classList.remove("hidden");
  /* Interaction affordances are noise on a page nobody can interact with. */
  copy.querySelectorAll(".pc-port, .pc-marker").forEach((n) => n.remove());
  const root = copy.querySelector("#pc-root");
  if (root) {
    root.removeAttribute("transform");
    root.removeAttribute("id");
  }
  copy.setAttribute("width", "100%");
  return copy;
}

export function openOverview() {
  const panel = $("#overview");
  const diagram = $("#overview-diagram");
  const side = $("#overview-side");
  diagram.innerHTML = "";
  side.innerHTML = "";

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
      side.appendChild(el("div", { class: "ov-row" }, [
        el("strong", {}, activity.label),
        el("span", { class: "dim" }, ` · ${activity.lane || "no lane"}`),
      ]));
    });
  }

  if (state.lastAssessment) {
    side.appendChild(el("h3", {}, "What was found, by activity"));
    const rows = state.lastAssessment.findingsByActivity || [];
    if (!rows.length) {
      side.appendChild(el("div", { class: "ov-row dim" },
        "Run an assessment to attribute findings to the activities they arise under."));
    }
    rows.forEach((row) => {
      side.appendChild(el("div", { class: "ov-row" }, [
        el("span", { class: "ov-count" }, String(row.findings)),
        el("span", {}, row.label),
      ]));
    });
    // Findings are attributed, not partitioned, so a total here would mislead.
    side.appendChild(el("p", { class: "ov-note" },
      `${state.lastAssessment.summary.riskFindingCount} candidate findings in total. These are candidates for triage, not confirmed failures.`));
    if (state.lastAssessment.run && state.lastAssessment.run.knowledgeBase) {
      const kb = state.lastAssessment.run.knowledgeBase;
      side.appendChild(el("p", { class: "ov-note dim" },
        `Assessed with library ${kb.fingerprint} — ${kb.motifs} motifs, ${kb.riskPatterns} risk patterns.`));
    }
  } else {
    side.appendChild(el("p", { class: "ov-note dim" },
      "Run an assessment to see what was found in this context."));
  }

  panel.classList.remove("hidden");
}
