import { postJson } from "../core/api.js";
import { $, el } from "../core/dom.js";
import { setStatus } from "../core/status.js";
import { state } from "../state.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { runMutation } from "./mutations.js";
import { noteChange } from "./run.js";

// element palette

const BEAM_NS = "http://w3id.org/beam/core#";

/* A system is not an element. It is the container the elements sit in, and it
   belongs with the other system controls above the canvas, not in a tray of
   shapes to drop. See createSystem, called from the system bar. */
const PALETTE = [
  { label: "Data", cls: "Data", kind: "data", cat: "resource",
    hint: "What flows: a question, a document, a result" },
  { label: "Symbol", cls: "Symbol", kind: "symbol", cat: "resource",
    hint: "Structured knowledge: a database, a knowledge graph, a label" },
  { label: "Model", cls: "StatisticalModel", kind: "model", cat: "resource",
    hint: "A trained statistical model, such as an LLM or a classifier" },
  { label: "Transform", cls: "Transform", kind: "process", cat: "process",
    hint: "A step that turns its inputs into an output" },
  { label: "Infer", cls: "Infer", kind: "process", cat: "process",
    hint: "A step that draws a conclusion from a model, such as a prediction" },
  { label: "Train", cls: "Train", kind: "process", cat: "process",
    hint: "A step that builds a model from data" },
  { label: "Generate", cls: "Generate", kind: "process", cat: "process",
    hint: "A step that produces new content, such as an answer" },
];

export function createSystem(unclaimedCount, systemCount) {
  const label = window.prompt("Name of the new system:", "New system");
  if (!label) return null;
  /* Naming the architecture you just opened means "this is that architecture",
     so with nothing else on the canvas the elements simply join it - being
     asked at that point is a question with one sensible answer. Once a system
     already exists the same act is ambiguous: it may be a second architecture,
     or a split of the first, and only the reader knows which. */
  const adopt = unclaimedCount > 0 && (
    !systemCount || window.confirm(
      `Put the ${unclaimedCount} element(s) that belong to no system into "${label}"?`));
  return runMutation(async () => {
    try {
      const { ttl } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> ." + String.fromCharCode(10),
        op: "add-system", label, adopt,
      });
      noteChange(`added system ${label}`);
      Editor.setValue(ttl);
      setStatus("ok", adopt
        ? `Added ${label} — it holds the elements that belonged to no system`
        : `Added ${label} — new elements land in it, and a business activity can name it`);
    } catch (error) {
      setStatus("error", "Could not add the system: " + error.message.split(String.fromCharCode(10))[0]);
    }
  });
}

/* Said once, when the server made the container the element landed in. */
export function madeSystemNote(newSystem) {
  return newSystem ? ' in "My system" (made for it; click its name above to rename it)' : "";
}

function addPaletteElement(item, clientX, clientY) {
  return runMutation(async () => {
    try {
      const { ttl, newId, newSystem } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> .\n",
        op: "add-element", classUri: BEAM_NS + item.cls, category: item.cat, label: item.label,
        /* The architecture that is selected, then the one on screen. */
        system: GraphView.getSelectedSystem() || state.scopedSystem || null,
      });
      if (newId && clientX != null) GraphView.placeNodeAt(newId, clientX, clientY);
      noteChange(`added ${item.label}`);
      Editor.setValue(ttl);
      setStatus("ok", `Added ${item.label}${madeSystemNote(newSystem)} — click it to edit, `
        + "drag its ▸ port to connect");
    } catch (error) {
      setStatus("error", "Could not add element: " + error.message.split("\n")[0]);
    }
  });
}

// Build a collapsible tray
export function buildTray(container, title, body, startCollapsed) {
  const toggle = el("span", { class: "tray-toggle" }, startCollapsed ? "▸" : "▾");
  const head = el("div", { class: "tray-head", title: "Show / hide" }, [el("span", {}, title), toggle]);
  head.addEventListener("click", () => {
    const collapsed = container.classList.toggle("collapsed");
    toggle.textContent = collapsed ? "▸" : "▾";
  });
  if (startCollapsed) container.classList.add("collapsed");
  container.textContent = "";
  container.appendChild(head);
  container.appendChild(body);
}

export function initPalette() {
  const palette = $("#palette");
  if (!palette) return;
  const wrap = $("#canvas-wrap");
  const body = el("div", { class: "tray-body" });
  PALETTE.forEach((item) => {
    const chip = el("div",
      { class: `palette-item ${item.kind}`,
        title: `${item.hint} (beam:${item.cls}). Click to add, or drag onto the canvas` },
      item.label);
    chip.addEventListener("pointerdown", (ev) => startTrayDrag(ev, chip, wrap, (x, y) => addPaletteElement(item, x, y)));
    body.appendChild(chip);
  });
  buildTray(palette, "Elements", body);
}

// Click a tray item to add it (at center)
export function startTrayDrag(ev, chip, wrap, onDrop) {
  ev.preventDefault();
  ev.stopPropagation();
  const startX = ev.clientX;
  const startY = ev.clientY;
  const ghost = chip.cloneNode(true);
  ghost.classList.add("palette-ghost");
  ghost.style.left = startX + 10 + "px";
  ghost.style.top = startY + 10 + "px";
  let moved = false;
  const move = (mv) => {
    if (!moved) {
      if (Math.hypot(mv.clientX - startX, mv.clientY - startY) < 6) return;
      moved = true;
      document.body.appendChild(ghost); // only show the ghost once actually dragging
    }
    ghost.style.left = mv.clientX + 10 + "px";
    ghost.style.top = mv.clientY + 10 + "px";
  };
  const up = (uv) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    ghost.remove();
    if (!moved) { onDrop(null, null); return; } // click -> add at center
    const r = wrap.getBoundingClientRect();
    const inside = uv.clientX >= r.left && uv.clientX <= r.right && uv.clientY >= r.top && uv.clientY <= r.bottom;
    const onTray = uv.target && uv.target.closest && (uv.target.closest(".palette") || uv.target.closest(".motif-palette"));
    onDrop(inside && !onTray ? uv.clientX : null, inside && !onTray ? uv.clientY : null);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}
