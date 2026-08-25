/* Entry point: wiring only. Panels render, core/ is plumbing, state.js is
 * what more than one panel reads. */

import { Annotate } from "./panels/annotate.js";
import { api, downloadBlob, exportBaseName, postForFile, postJson } from "./core/api.js";
import { emit, on } from "./core/bus.js";
import { $, $$, el } from "./core/dom.js";
import { openDrawer, switchDrawerTab, toggleDrawer } from "./core/drawer.js";
import { revealInSource } from "./core/source.js";
import { setStatus } from "./core/status.js";
import { Editor } from "./lib/editor.js";
import { GraphView } from "./lib/graph_view.js";
import { VersionHistory } from "./lib/version_history.js";
import { refreshPreview, setLevel, settleChoice } from "./panels/canvas.js";
import { renderDerivedCategories } from "./panels/dataflow.js";
import { reReadFindings, renderFindings } from "./panels/findings.js";
import { renderHistory } from "./panels/history.js";
import { initMotifPalette, renderMotifs } from "./panels/motifs.js";
import { applyConnect, applyDelete, applyEdit, runMutation } from "./panels/mutations.js";
import { openOverview } from "./panels/overview.js";
import { STARTER_BPMN, STARTER_TTL, initPalette } from "./panels/palette.js";
import { noteChange } from "./panels/run.js";
import { renderValidation } from "./panels/validation.js";
import { ProcessCanvas } from "./lib/process_canvas.js";
import { state } from "./state.js";

// ---- split divider ----
function initDivider() {
  const divider = $("#divider");
  const editorPane = $("#editor-pane");
  let dragging = false;
  divider.addEventListener("pointerdown", (ev) => {
    dragging = true;
    divider.setPointerCapture(ev.pointerId);
    document.body.classList.add("resizing");
  });
  divider.addEventListener("pointermove", (ev) => {
    if (!dragging) return;
    const main = $(".workbench");
    const rect = main.getBoundingClientRect();
    const ratio = Math.min(0.75, Math.max(0.2, (ev.clientX - rect.left) / rect.width));
    editorPane.style.flex = `0 0 ${ratio * 100}%`;
    GraphView.fit();
  });
  divider.addEventListener("pointerup", () => {
    dragging = false;
    document.body.classList.remove("resizing");
  });
}

// ---- init ----
async function init() {
  GraphView.init();
  Editor.init({ onChange: refreshPreview });
  initDivider();

  // A scope change redraws both the canvas and the findings list.
  on("scope:changed", () => {
    refreshPreview(Editor.getValue());
    reReadFindings();
  });

  let vocabulary = { roles: [], dataCategories: [] };
  try {
    vocabulary = await api("/api/vocabulary");
  } catch (_) { /* annotation popups will just have empty pick lists */ }
  const classes = [...(vocabulary.resourceClasses || []), ...(vocabulary.processClasses || [])];
  GraphView.setAnnotation({
    vocabulary, classes,
    onEdit: applyEdit, onDelete: applyDelete, onConnect: applyConnect, onStatus: setStatus,
    onSelect: (id) => revealInSource([id]),
  });
  Annotate.init({ vocabulary, onStatus: setStatus });

  initPalette();
  initMotifPalette(vocabulary.motifTemplates || []);
  renderHistory();

  ProcessCanvas.init({
    svg: "#process-canvas",
    // Server-side rewrite: the Turtle in the editor stays the source of truth.
    onEdit: (op, payload) => runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/process-edit", {
          ttl: Editor.getValue(), op, ...payload,
        });
        noteChange(`business process: ${op.replace(/-/g, " ")}`);
        Editor.setValue(ttl);
        setStatus("ok", `Business process updated (${op})`);
      } catch (error) {
        setStatus("error", "Could not edit the process: " + error.message.split(String.fromCharCode(10))[0]);
      }
    }),
    // Highlight what was opened, not the graph in general.
    onOpenArchitecture: (activity) => {
      // Narrowing is a query over pair:refinedBy; nothing is stored.
      state.scopedSystem = activity.refines[0] || null;
      setLevel("architecture", activity);
      emit("scope:changed");
      // Not setHighlight(refines): those are system IRIs, not canvas nodes.
      GraphView.setHighlight([]);
      revealInSource(activity.refines);
      setStatus("ok", `Opened ${activity.label}`, "click the breadcrumb to go back");
    },
  });
  // An empty workbench asks which layer, rather than guessing.
  $("#canvas-wrap").classList.add("unstarted");

  $("#start-business").addEventListener("click", () => {
    settleChoice();
    state.levelChosenByHand = true;
    setLevel("business");
    openDrawer("process");
    setStatus("ok", "Business process", "add a participant, then steps inside it");
  });
  $("#start-architecture").addEventListener("click", () => {
    settleChoice();
    state.levelChosenByHand = true;
    setLevel("architecture");
    setStatus("ok", "AI architecture", "drag a symbol onto the canvas, or load an example");
  });

  $("#btn-overview").addEventListener("click", openOverview);
  $("#btn-overview-close").addEventListener("click", () => $("#overview").classList.add("hidden"));
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") $("#overview").classList.add("hidden");
  });
  $("#btn-overview-svg").addEventListener("click", () => {
    const svg = $("#overview-diagram").querySelector("svg");
    if (!svg) { setStatus("error", "No diagram to export."); return; }
    const markup = new XMLSerializer().serializeToString(svg);
    downloadBlob(new Blob([markup], { type: "image/svg+xml" }), `${exportBaseName()}-context.svg`);
    setStatus("ok", "Diagram exported");
  });
  $("#level-business").addEventListener("click", () => {
    state.levelChosenByHand = true;
    setLevel("business");
  });
  $("#level-architecture").addEventListener("click", () => {
    state.levelChosenByHand = true;
    // By hand means the whole layer, not the activity descended through.
    const widening = state.scopedSystem !== null;
    state.scopedSystem = null;
    state.openedFrom = null;
    setLevel("architecture");
    if (widening) {
      refreshPreview(Editor.getValue());
      reReadFindings();
    }
  });

  // Known state once, rather than whatever the markup said until first click.
  setLevel(state.level);

  $("#btn-history-clear").addEventListener("click", () => {
    if (!VersionHistory.list().length) return;
    if (!window.confirm("Delete every recorded version from this browser? This cannot be undone.")) return;
    VersionHistory.clear();
    renderHistory();
    setStatus("ok", "History cleared");
  });

  $("#btn-history-export").addEventListener("click", () => {
    const versions = VersionHistory.list();
    if (!versions.length) { setStatus("error", "No history to export."); return; }
    downloadBlob(
      new Blob([JSON.stringify(versions, null, 2)], { type: "application/json" }),
      `${exportBaseName()}-history.json`
    );
    setStatus("ok", `Exported ${versions.length} versions`);
  });

  try {
    const examples = await api("/api/examples");
    const select = $("#example-select");
    const groups = [
      ["Bundled", examples.filter((ex) => !ex.local)],
      ["Local (not in the repository)", examples.filter((ex) => ex.local)],
    ];
    for (const [label, items] of groups) {
      if (!items.length) continue;
      const group = el("optgroup", { label });
      items.forEach((ex) => group.appendChild(el("option", { value: ex.name }, ex.name)));
      select.appendChild(group);
    }
  } catch (_) { /* non-fatal */ }

  $("#example-select").addEventListener("change", async (ev) => {
    const name = ev.target.value;
    if (!name) return;
    try {
      const example = await api(`/api/examples/${encodeURIComponent(name)}`);
      if (example.kind === "process") {
        // Bring the architectures it refines, minus what is already loaded.
        const present = new Set((state.lastGraph && state.lastGraph.systems ? state.lastGraph.systems : []).map((s) => s.id));
        const wanted = (example.requires || []).filter((r) => r.example && !present.has(r.system));
        const parts = [];
        for (const requirement of wanted) {
          const architecture = await api(`/api/examples/${encodeURIComponent(requirement.example)}`);
          parts.push(architecture.ttl);
        }

        const current = Editor.getValue().trimEnd();
        if (current) parts.unshift(current);
        parts.push(example.ttl);

        noteChange(wanted.length
          ? `loaded scene: ${name}`
          : `added business process: ${name}`);
        Editor.setValue(parts.join(String.fromCharCode(10, 10)));
        openDrawer("process");

        const orphans = example.missing || [];
        if (orphans.length) {
          setStatus("error",
            `${orphans.length} activity target(s) have no bundled architecture`,
            "the process will draw, but there is nothing to assess for them");
        } else {
          setStatus("ok", `Loaded ${name}`,
            wanted.length ? `with ${wanted.length} architecture(s) it refines` : "added to the current graph");
        }
      } else {
        noteChange(`loaded example: ${name}`);
        Editor.setValue(example.ttl);
        setStatus("ok", `Loaded example: ${name}`);
      }
    } catch (error) {
      setStatus("error", error.message);
    }
  });

  // Open a graph file.
  $("#file-input").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const text = String(reader.result);
      if (!text.includes("tool4boxology.org")) {
        noteChange(`opened file: ${file.name}`);
        Editor.setValue(text);
        setStatus("ok", `Loaded file: ${file.name}`);
        return;
      }
      setStatus("busy", `Normalizing Tool4Boxology export: ${file.name}…`);
      try {
        const fmt = /\.nt$/i.test(file.name) ? "nt" : "turtle";
        const { ttl, warnings } = await postJson("/api/import/t4b", { data: text, format: fmt });
        noteChange(`imported Tool4Boxology export: ${file.name}`);
        Editor.setValue(ttl);
        setStatus("ok", `Imported ${file.name} — ${(warnings || []).length} normalization note(s). ` +
          "The export carries no roles: use the Annotate tab so motifs can match.");
      } catch (error) {
        setStatus("error", "Could not import Tool4Boxology export: " + error.message.split("\n")[0]);
      }
    };
    reader.readAsText(file);
    ev.target.value = "";
  });

  $("#btn-starter").addEventListener("click", () => {
    // Starter for whichever layer is open.
    const business = state.level === "business";
    settleChoice();
    noteChange(business ? "starter business process" : "starter architecture");
    Editor.setValue(business ? STARTER_BPMN : STARTER_TTL);
    setStatus("ok", "Starter graph loaded");
  });

  $("#btn-clear").addEventListener("click", () => {
    if (!Editor.getValue().trim()) return;
    if (!window.confirm("Clear the code and the diagram? This cannot be undone.")) return;
    Editor.setValue(""); // empty -> refreshPreview clears the canvas
    setStatus("ok", "Cleared");
  });

  $("#btn-validate").addEventListener("click", async () => {
    const ttl = Editor.getValue().trim();
    if (!ttl) { setStatus("error", "Nothing to validate - the editor is empty."); return; }
    const button = $("#btn-validate");
    button.disabled = true;
    setStatus("busy", "Validating against the input contract…");
    try {
      const report = await postJson("/api/validate", { ttl });
      renderValidation(report);
      openDrawer("validation");
      setStatus(report.conforms ? "ok" : "error",
        report.conforms ? "Input contract satisfied" : `${report.violations.length} contract violation(s)`);
    } catch (error) {
      setStatus("error", error.message);
    } finally {
      button.disabled = false;
    }
  });

  $("#btn-assess").addEventListener("click", async () => {
    const ttl = Editor.getValue().trim();
    if (!ttl) { setStatus("error", "Nothing to assess - the editor is empty."); return; }
    const button = $("#btn-assess");
    button.disabled = true;
    setStatus("busy", "Running candidate risk assessment…");
    try {
      const data = await postJson("/api/assess", { ttl });
      renderFindings(data);
      renderMotifs(data.motifMatches, data.motifGaps); // Motifs tab (each match carries nodeIds)
      renderDerivedCategories(data.derivedCategories);
      openDrawer("findings");
      setStatus("ok", `Assessment finished`, `${data.summary.riskFindingCount} findings · ${data.summary.motifMatchCount} matches`);
    } catch (error) {
      setStatus("error", error.message);
    } finally {
      button.disabled = false;
    }
  });

  $("#btn-export-svg").addEventListener("click", () => {
    const ok = GraphView.exportSvg(`${exportBaseName()}.svg`);
    if (ok) setStatus("ok", "Diagram exported as SVG.");
    else setStatus("error", "Nothing to export - the diagram is empty.");
  });

  $("#btn-export-kg").addEventListener("click", async () => {
    const ttl = Editor.getValue().trim();
    if (!ttl) { setStatus("error", "Nothing to export - the editor is empty."); return; }
    const button = $("#btn-export-kg");
    const format = $("#export-format").value;
    button.disabled = true;
    setStatus("busy", "Building the assessment knowledge graph…");
    try {
      const { blob, findings, matches, filename } = await postForFile(
        "/api/export/assessment",
        { ttl, format, sourceLabel: exportBaseName() },
      );
      downloadBlob(blob, filename || `${exportBaseName()}-assessment`);
      setStatus("ok", "Assessment exported", `${findings} findings · ${matches} matches`);
    } catch (error) {
      setStatus("error", error.message);
    } finally {
      button.disabled = false;
    }
  });

  $("#drawer-toggle").addEventListener("click", toggleDrawer);
  $("#drawer-head").addEventListener("dblclick", toggleDrawer);
  $$(".drawer-tab").forEach((tab) =>
    tab.addEventListener("click", () => {
      switchDrawerTab(tab.dataset.drawerTab);
      openDrawer();
      if (tab.dataset.drawerTab === "annotate") Annotate.refresh();
    }));
}

document.addEventListener("DOMContentLoaded", init);
window.PairAI = { Editor, GraphView, ProcessCanvas, VersionHistory, state };
