/* The element palette, and the starter graphs it drops onto the canvas. */

import { postJson } from "../core/api.js";
import { $, el } from "../core/dom.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { runMutation } from "./mutations.js";
import { noteChange } from "./run.js";

// ---- starter graphs ----
// One Turtle document holds both layers, so BPMN needs a starter, not a pane.
export const STARTER_BPMN = `@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix dpv:  <https://w3id.org/dpv#> .
@prefix ex:   <http://example.org/my-process#> .

ex:Customer a bpmn:participant ;
  bp:name "Customer" ;
  bp:processRef ex:CustomerSide .

ex:CustomerSide a bpmn:process ;
  bp:name "Ask for something" ;
  bp:contains ex:Ask .

ex:Ask a bpmn:task ;
  bp:name "Ask a question" .

ex:Company a bpmn:participant ;
  bp:name "My organisation" ;
  bp:processRef ex:Service .

ex:Service a bpmn:process ;
  bp:name "Answer the request" ;
  bp:isExecutable true ;
  bp:contains ex:Receive , ex:Answer , ex:Review .

ex:Receive a bpmn:receiveTask ;
  bp:name "Receive the request" ;
  bp:outgoing ex:F1 .

# The AI capability. Point pair:refinedBy at a beam:System in this document and
# the box opens into that architecture.
ex:Answer a bpmn:subProcess ;
  bp:name "Draft an answer" ;
  bp:incoming ex:F1 ;
  bp:outgoing ex:F2 .

# A human step is a control the architecture cannot see.
ex:Review a bpmn:userTask ;
  bp:name "Check it before it goes out" ;
  bp:incoming ex:F2 ;
  bp:resourceRole ex:Agent .

ex:Agent a bpmn:humanPerformer ;
  bp:name "Support agent" .

ex:F1 a bpmn:sequenceFlow ; bp:sourceRef ex:Receive ; bp:targetRef ex:Answer .
ex:F2 a bpmn:sequenceFlow ; bp:sourceRef ex:Answer ;  bp:targetRef ex:Review .

ex:Msg a bpmn:messageFlow ;
  bp:name "asks" ;
  bp:sourceRef ex:Ask ; bp:targetRef ex:Receive .
`;

export const STARTER_TTL = `@prefix ex:   <http://example.org/my-system#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:System a beam:System ;
  rdfs:label "My RAG system" ;
  beam:hasResource ex:Question, ex:VectorDB, ex:Context, ex:LLM, ex:Answer ;
  beam:hasProcess ex:Retrieve, ex:Generate .

ex:Question a beam:Data ;
  rdfs:label "User question" ;
  pair:playsRole pair:PublicUserInput ;
  pair:containsDataCategory pair:ExternalUserContent .

ex:VectorDB a beam:Data ;
  rdfs:label "Knowledge vector store" ;
  pair:playsRole pair:VectorStore ;
  pair:containsDataCategory pair:SensitiveInformation .

ex:Context a beam:Data ;
  rdfs:label "Retrieved context" ;
  pair:playsRole pair:RetrievedResult ;
  pair:containsDataCategory pair:UntrustedContent .

ex:LLM a beam:StatisticalModel ;
  rdfs:label "Generative model" ;
  pair:playsRole pair:GenerativeModel .

ex:Answer a beam:Data ;
  rdfs:label "User-facing answer" ;
  pair:playsRole pair:PublicUserFacingOutput .

ex:Retrieve a beam:Infer ;
  rdfs:label "Vector retrieval" ;
  pair:playsRole pair:RetrievalStep ;
  beam:use ex:Question, ex:VectorDB ;
  beam:produce ex:Context ;
  beam:inform ex:Generate .

ex:Generate a beam:Transform ;
  rdfs:label "LLM generation" ;
  pair:playsRole pair:GenerationStep ;
  beam:use ex:Question, ex:Context, ex:LLM ;
  beam:produce ex:Answer .
`;

// Palette of BEAM symbols; click one to add it, or drag it onto the canvas.
// ---- element palette ----

const BEAM_NS = "http://w3id.org/beam/core#";

const PALETTE = [
  { label: "Data", cls: "Data", kind: "data", cat: "resource" },
  { label: "Symbol", cls: "Symbol", kind: "symbol", cat: "resource" },
  { label: "Model", cls: "StatisticalModel", kind: "model", cat: "resource" },
  { label: "Transform", cls: "Transform", kind: "process", cat: "process" },
  { label: "Infer", cls: "Infer", kind: "process", cat: "process" },
  { label: "Train", cls: "Train", kind: "process", cat: "process" },
  { label: "Generate", cls: "Generate", kind: "process", cat: "process" },
];

function addPaletteElement(item, clientX, clientY) {
  return runMutation(async () => {
    try {
      const { ttl, newId } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> .\n",
        op: "add-element", classUri: BEAM_NS + item.cls, category: item.cat, label: item.label,
      });
      if (newId && clientX != null) GraphView.placeNodeAt(newId, clientX, clientY);
      noteChange(`added ${item.label}`);
      Editor.setValue(ttl);
      setStatus("ok", `Added ${item.label} — click it to edit, drag its ▸ port to connect`);
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
      { class: `palette-item ${item.kind}`, title: `Click to add, or drag onto the canvas — ${item.cls}` },
      item.label);
    chip.addEventListener("pointerdown", (ev) => startTrayDrag(ev, chip, wrap, (x, y) => addPaletteElement(item, x, y)));
    body.appendChild(chip);
  });
  buildTray(palette, "Symbols", body);
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
