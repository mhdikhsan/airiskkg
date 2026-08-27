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
import { askAgain, refreshPreview, resetScope, setLevel, settleChoice } from "./panels/canvas.js";
import { clearDerivedCategories, renderDerivedCategories } from "./panels/dataflow.js";
import { clearFindings, reReadFindings, renderFindings } from "./panels/findings.js";
import { renderHistory } from "./panels/history.js";
import { clearMotifs, initMotifPalette, renderMotifs } from "./panels/motifs.js";
import { applyConnect, applyDelete, applyEdit, runMutation } from "./panels/mutations.js";
import { openOverview } from "./panels/overview.js";
import { STARTER_BPMN, STARTER_TTL, initPalette } from "./panels/palette.js";
import { noteChange } from "./panels/run.js";
import { clearValidation, renderValidation } from "./panels/validation.js";
import { ProcessCanvas } from "./lib/process_canvas.js";
import { state } from "./state.js";

// split divider 
function initDivider() {
  const divider = $("#divider");
  const editorPane = $("#editor-pane");
  let dragging = false;
  divider.addEventListener("pointerdown", (ev) => {
    /* The collapse button lives on the divider, and the drag takes pointer
     * capture - which retargets the click that follows and would leave the
     * button dead. Same trap as the canvas pan and the opening choice. */
    if (ev.target.closest("button")) return;
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

  /* Fold the source away to read the diagram, and back to edit it. Both
   * canvases refit afterwards: they size to their container, and the container
   * just changed. */
  const toggle = $("#btn-editor-toggle");
  const setEditorFolded = (folded) => {
    document.body.classList.toggle("editor-hidden", folded);
    toggle.innerHTML = folded ? "&#8250;" : "&#8249;";
    toggle.title = folded ? "Show the editor" : "Hide the editor";
    // Both canvases size to their container, and the container just changed.
    requestAnimationFrame(() => { GraphView.fit(); ProcessCanvas.fit(); });
  };
  toggle.addEventListener("click", () => {
    setEditorFolded(!document.body.classList.contains("editor-hidden"));
  });
  // The rail is the whole pane when it is folded, so it is also the way back.
  $("#editor-rail").addEventListener("click", () => setEditorFolded(false));
}

// init 
async function init() {
  GraphView.init();
  Editor.init({ onChange: refreshPreview });
  initDivider();

  // A scope change redraws both the canvas and the findings list.
  /* A different document means the results on screen describe something that
   * is no longer there. Decided in one place so every route in - an example, a
   * file, an import, the starter, Clear, a restored version - forgets the same
   * things. */
  const forgetTheLastDocument = () => {
    resetScope();
    clearFindings();
    clearMotifs();
    clearDerivedCategories();
    clearValidation();
  };

  on("document:replaced", forgetTheLastDocument);

  on("scope:changed", () => {
    refreshPreview(Editor.getValue());
    reReadFindings();
    // The annotate table is a view of the same graph, so it narrows with it.
    Annotate.refresh();
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
  ProcessCanvas.setDataClasses(vocabulary.dataClasses || []);
  Annotate.init({ vocabulary, onStatus: setStatus });

  initPalette();
  initMotifPalette(vocabulary.motifTemplates || []);
  renderHistory();

  ProcessCanvas.init({
    svg: "#process-canvas",
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
    onOpenArchitecture: (activity) => {
      /* Only descend into an architecture that is actually here. The activity
       * names the system that carries it out; if that system is not in this
       * graph, descending used to draw whatever else was loaded - delete the
       * graph-RAG half of the energy scene and the chatbot activity opened the
       * meter scorer. Saying it is absent is the whole point of the layer. */
      const wanted = activity.refines[0] || null;
      const here = (state.lastGraph && state.lastGraph.systems ? state.lastGraph.systems : [])
        .some((s) => s.id === wanted);
      if (wanted && !here) {
        setStatus("error",
          `${activity.label} is carried out by an architecture this graph does not contain`,
          "load it, or point the activity at a system that is here");
        return;
      }
      state.scopedSystem = wanted;
      setLevel("architecture", activity);
      emit("scope:changed");
      GraphView.setHighlight([]);
      revealInSource(activity.refines);
      setStatus("ok", `Opened ${activity.label}`, "click the breadcrumb to go back");
    },
  });
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
    /* Announced rather than done here. Widening by hand used to call the two
     * redraws it knew about, so the annotate table - which learned to follow
     * the scope later - stayed narrowed to the architecture just left. */
    if (widening) emit("scope:changed");
  });
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
        /* Replaces, exactly like an architecture example does. It used to
         * prepend whatever was already in the editor - so picking the process
         * after onyx assessed the two together and reported 30 findings where
         * the scene has 8. Picking from this dropdown is choosing what to look
         * at, and a scene is self-contained: the process plus every
         * architecture it refines. */
        const wanted = (example.requires || []).filter((r) => r.example);
        const parts = [];
        for (const requirement of wanted) {
          const architecture = await api(`/api/examples/${encodeURIComponent(requirement.example)}`);
          parts.push(architecture.ttl);
        }
        parts.push(example.ttl);

        forgetTheLastDocument();
        noteChange(`loaded scene: ${name}`);
        Editor.setValue(parts.join(String.fromCharCode(10, 10)));
        openDrawer("process");

        const orphans = example.missing || [];
        if (orphans.length) {
          setStatus("error",
            `${orphans.length} activity target(s) have no bundled architecture`,
            "the process will draw, but there is nothing to assess for them");
        } else {
          setStatus("ok", `Loaded ${name}`,
            wanted.length ? `with ${wanted.length} architecture(s) it refines` : "no architecture to bring");
        }
      } else {
        forgetTheLastDocument();
        noteChange(`loaded example: ${name}`);
        Editor.setValue(example.ttl);
        setStatus("ok", `Loaded example: ${name}`);
      }
    } catch (error) {
      setStatus("error", error.message);
    }
  });

  $("#file-input").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const text = String(reader.result);
      if (!text.includes("tool4boxology.org")) {
        forgetTheLastDocument();
        noteChange(`opened file: ${file.name}`);
        Editor.setValue(text);
        setStatus("ok", `Loaded file: ${file.name}`);
        return;
      }
      setStatus("busy", `Normalizing Tool4Boxology export: ${file.name}…`);
      try {
        const fmt = /\.nt$/i.test(file.name) ? "nt" : "turtle";
        const { ttl, warnings } = await postJson("/api/import/t4b", { data: text, format: fmt });
        forgetTheLastDocument();
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
    const business = state.level === "business";
    settleChoice();
    forgetTheLastDocument();
    noteChange(business ? "starter business process" : "starter architecture");
    Editor.setValue(business ? STARTER_BPMN : STARTER_TTL);
    setStatus("ok", "Starter graph loaded");
  });

  /* The brand is the way back to the opening question. It has to clear first:
   * refreshProcess settles the choice again the moment there is anything to
   * draw, so the question cannot stand over a canvas with content on it. */
  $("#btn-home").addEventListener("click", () => {
    const hasContent = Boolean(Editor.getValue().trim());
    if (hasContent && !window.confirm(
      "Start over? This clears the code and the diagram.")) return;
    forgetTheLastDocument();
    if (hasContent) Editor.setValue("");
    askAgain();
    setLevel("architecture");
    setStatus("ok", "Start over", "choose what you are describing");
  });

  $("#btn-clear").addEventListener("click", () => {
    if (!Editor.getValue().trim()) return;
    if (!window.confirm("Clear the code and the diagram? This cannot be undone.")) return;
    forgetTheLastDocument();
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
