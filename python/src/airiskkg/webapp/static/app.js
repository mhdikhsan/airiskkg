"use strict";

/* Workbench wiring: editor <-> live preview <-> assessment.
 * Requires editor.js (window.Editor) and graph.js (window.GraphView).
 */
(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (v !== null && v !== undefined) node.setAttribute(k, v);
    }
    for (const child of [].concat(children)) {
      if (child == null) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  async function api(url, options) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  function postJson(url, body) {
    return api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  }

  // ---- status bar ------------------------------------------------------------
  function setStatus(state, message, stats) {
    const dot = $("#status-dot");
    dot.className = `status-dot ${state}`;
    $("#status-text").textContent = message;
    $("#status-stats").textContent = stats || "";
  }

  function parseErrorLine(message) {
    const match = /line (\d+)/i.exec(message);
    return match ? Number(match[1]) : null;
  }

  // ---- live preview ----------------------------------------------------------
  let previewSeq = 0;

  async function refreshPreview(ttl) {
    const seq = ++previewSeq;
    if (!ttl.trim()) {
      GraphView.clear();
      $("#system-badge").classList.add("hidden");
      setStatus("ok", "Ready");
      return;
    }
    try {
      const data = await postJson("/api/graph", { ttl });
      if (seq !== previewSeq) return; // a newer edit is already in flight
      GraphView.render(data);
      Editor.markErrorLine(null);
      const badge = $("#system-badge");
      if (data.systems.length) {
        badge.textContent = data.systems.map((s) => s.label).join(" · ");
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
      // keep the last good graph on screen while the user is mid-edit
    }
  }

  // ---- drawer ----------------------------------------------------------------
  function openDrawer(tab) {
    $("#drawer").classList.remove("collapsed");
    $("#drawer-toggle").innerHTML = "&#9660;";
    if (tab) switchDrawerTab(tab);
  }

  function toggleDrawer() {
    const drawer = $("#drawer");
    drawer.classList.toggle("collapsed");
    $("#drawer-toggle").innerHTML = drawer.classList.contains("collapsed") ? "&#9650;" : "&#9660;";
  }

  function switchDrawerTab(name) {
    $$(".drawer-tab").forEach((t) => t.classList.toggle("active", t.dataset.drawerTab === name));
    $$(".drawer-panel").forEach((p) => p.classList.toggle("hidden", p.dataset.drawerPanel !== name));
  }

  // ---- findings --------------------------------------------------------------
  let selectedFinding = null;

  // One mitigation as a list item, with any suggested motif beneath it.
  function controlItem(control) {
    const motifs = control.realizedByMotifs || [];
    const children = [el("span", { class: "ctrl-label" }, control.label)];
    if (motifs.length) {
      children.push(
        el("div", { class: "ctrl-motifs" }, [
          el("span", { class: "ctrl-motifs-lead" }, "suggested mitigation: "),
          ...motifs.map((m) =>
            el("span", { class: "chip motif-suggest", title: "Candidate structural mitigation: insert this motif" }, m.label)
          ),
        ])
      );
    }
    return el("li", { title: control.definition || "" }, children);
  }

  // MIT taxonomy-grounded mitigations for this finding's risks.
  function groundedFamiliesSection(families) {
    if (!families || !families.length) return null;
    return el("div", { class: "ctrl-group evidence" }, [
      el("div", { class: "ctrl-group-head" }, `MIT mitigations (${families.length})`),
      el("ul", { class: "ref-list grounded-list" },
        families.map((f) => el("li", { title: f.definition || "" }, el("span", { class: "chip tax-ground" }, f.label)))),
    ]);
  }

  // All suggested controls under one "Mitigations" list.
  function controlSections(controls) {
    if (!controls.length) return [];
    return [
      el("div", { class: "ctrl-group" }, [
        el("div", { class: "ctrl-group-head" }, `Mitigations (${controls.length})`),
        el("ul", { class: "ref-list" }, controls.map(controlItem)),
      ]),
    ];
  }

  function findingCard(finding) {
    const evidenceIds = finding.evidence.map((e) => e.id);
    const card = el("div", { class: "finding-card", tabindex: "0" }, [
      el("div", { class: "finding-head" }, [
        el("strong", {}, finding.label),
        finding.motif ? el("span", { class: "chip" }, finding.motif.label) : null,
      ]),
      finding.description ? el("p", { class: "finding-desc" }, finding.description) : null,
      el("div", { class: "finding-meta" }, [
        finding.mechanism ? el("span", { class: "chip mech", title: finding.mechanism.id }, finding.mechanism.label) : null,
        ...finding.taxonomyEntries.slice(0, 4).map((t) => el("span", { class: "chip tax", title: t.definition || t.id }, t.label)),
        finding.taxonomyEntries.length > 4 ? el("span", { class: "chip tax" }, `+${finding.taxonomyEntries.length - 4}`) : null,
      ]),
      el("details", {}, [
        el("summary", {}, `Suggested controls (${finding.suggestedControls.length}) · evidence (${finding.evidence.length})`),
        ...controlSections(finding.suggestedControls),
        groundedFamiliesSection(finding.groundedControlFamilies),
        el("div", { class: "evidence-note" }, "Evidence: " + finding.evidence.map((e) => e.label).join(", ")),
      ]),
    ]);
    card.addEventListener("click", () => {
      if (selectedFinding === card) {
        selectedFinding = null;
        card.classList.remove("selected");
        GraphView.setHighlight([]);
        return;
      }
      $$(".finding-card.selected").forEach((c) => c.classList.remove("selected"));
      selectedFinding = card;
      card.classList.add("selected");
      GraphView.setHighlight(evidenceIds);
    });
    return card;
  }

  function renderFindings(data) {
    $("#findings-empty").classList.add("hidden");
    const summary = $("#findings-summary");
    summary.innerHTML = "";
    summary.appendChild(el("div", { class: "summary-row" }, [
      el("span", { class: "stat" }, `${data.summary.riskFindingCount} candidate findings`),
      el("span", { class: "stat" }, `${data.summary.motifMatchCount} motif matches`),
      el("span", { class: "hint" }, "Click a finding to highlight its evidence in the graph."),
    ]));

    const list = $("#findings-list");
    list.innerHTML = "";
    selectedFinding = null;
    GraphView.setHighlight([]);
    if (!data.findings.length) {
      list.appendChild(el("p", { class: "drawer-empty" }, "No candidate risk findings were produced for this architecture."));
    }
    data.findings.forEach((f) => list.appendChild(findingCard(f)));
    $("#findings-count").textContent = data.findings.length ? String(data.findings.length) : "";
  }

  // ---- validation ------------------------------------------------------------
  function validationRow(item, severity) {
    const row = el("div", { class: `validation-row ${severity}` }, [
      el("span", { class: "sev" }, severity === "violation" ? "Violation" : "Warning"),
      el("span", { class: "msg" }, item.message),
    ]);
    if (item.focusNode) {
      row.appendChild(el("code", { class: "focus", title: item.focusNode }, item.focusNode.split(/[#/]/).pop()));
      row.addEventListener("click", () => GraphView.setHighlight([item.focusNode]));
    }
    return row;
  }

  function renderValidation(report) {
    $("#validation-empty").classList.add("hidden");
    const list = $("#validation-list");
    list.innerHTML = "";
    const total = report.violations.length + report.warnings.length;
    list.appendChild(el("div", { class: "summary-row" }, [
      el("span", { class: `stat ${report.conforms ? "good" : "bad"}` },
        report.conforms ? "Input contract satisfied" : "Input contract violated"),
      el("span", { class: "stat" }, `${report.violations.length} violations · ${report.warnings.length} warnings`),
      total ? el("span", { class: "hint" }, "Click a row to highlight the focus node.") : null,
    ]));
    report.violations.forEach((v) => list.appendChild(validationRow(v, "violation")));
    report.warnings.forEach((w) => list.appendChild(validationRow(w, "warning")));
    $("#validation-count").textContent = total ? String(total) : "";
  }

  // ---- split divider ---------------------------------------------------------
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

  // ---- starter graph ---------------------------------------------------------
  const STARTER_TTL = `@prefix ex:   <http://example.org/my-system#> .
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

  // ---- in-canvas annotation --------------------------------------------------
  // ---- diagram -> code edits (serialized) ------------------------------------
  // Every structural edit runs through one queue, so rapid actions (add several
  // components, connect, delete in a row) never race on the editor value: each
  // reads the latest code only after the previous edit has written it back.
  let mutating = Promise.resolve();
  function runMutation(task) {
    const next = mutating.then(task, task);
    mutating = next.catch(() => {});
    return next;
  }

  // Edit an element (label / name / type / role / category) from the popup.
  function applyEdit(elementId, edit) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "edit-element", element: elementId, ...edit,
        });
        Editor.setValue(ttl);
        setStatus("ok", "Element updated — Run assessment to see findings");
      } catch (error) {
        setStatus("error", "Could not update element: " + error.message.split("\n")[0]);
      }
    });
  }

  // Delete an element and every edge touching it.
  function applyDelete(elementId) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "delete-element", element: elementId,
        });
        Editor.setValue(ttl);
        setStatus("ok", "Element deleted");
      } catch (error) {
        setStatus("error", "Could not delete: " + error.message.split("\n")[0]);
      }
    });
  }

  // Add a BEAM flow edge from a canvas port-drag. use = resource→process,
  // produce = process→resource, inform = process→process.
  function applyConnect(triple) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "add-edge", ...triple,
        });
        Editor.setValue(ttl);
        setStatus("ok", `Connected: ${triple.predicate}`);
      } catch (error) {
        setStatus("error", "Could not connect: " + error.message.split("\n")[0]);
      }
    });
  }

  // Palette of BEAM symbols; click one to add it, or drag it onto the canvas.
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
        Editor.setValue(ttl);
        setStatus("ok", `Added ${item.label} — click it to edit, drag its ▸ port to connect`);
      } catch (error) {
        setStatus("error", "Could not add element: " + error.message.split("\n")[0]);
      }
    });
  }

  function initPalette() {
    const palette = $("#palette");
    if (!palette) return;
    const wrap = $("#canvas-wrap");
    PALETTE.forEach((item) => {
      const chip = el("div",
        { class: `palette-item ${item.kind}`, title: `Click to add, or drag onto the canvas — ${item.cls}` },
        item.label);
      chip.addEventListener("pointerdown", (ev) => startPaletteDrag(ev, item, chip, wrap));
      palette.appendChild(chip);
    });
  }

  // Click a symbol to add it (at center); or drag it onto the canvas to drop it
  // at a point. Pointer-based (native HTML5 DnD fought the canvas pan / pointer
  // capture). Either way the element is written to the code and redrawn live.
  function startPaletteDrag(ev, item, chip, wrap) {
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
      if (!moved) { addPaletteElement(item, null, null); return; } // click -> add at center
      const r = wrap.getBoundingClientRect();
      const inside = uv.clientX >= r.left && uv.clientX <= r.right && uv.clientY >= r.top && uv.clientY <= r.bottom;
      const onPalette = uv.target && uv.target.closest && uv.target.closest(".palette");
      addPaletteElement(item, inside && !onPalette ? uv.clientX : null, inside && !onPalette ? uv.clientY : null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // ---- init ------------------------------------------------------------------
  async function init() {
    GraphView.init();
    Editor.init({ onChange: refreshPreview });
    initDivider();

    let vocabulary = { roles: [], dataCategories: [] };
    try {
      vocabulary = await api("/api/vocabulary");
    } catch (_) { /* annotation popups will just have empty pick lists */ }
    const classes = [...(vocabulary.resourceClasses || []), ...(vocabulary.processClasses || [])];
    GraphView.setAnnotation({ vocabulary, classes, onEdit: applyEdit, onDelete: applyDelete, onConnect: applyConnect, onStatus: setStatus });
    Annotate.init({ vocabulary, onStatus: setStatus });

    initPalette();

    try {
      const examples = await api("/api/examples");
      const select = $("#example-select");
      examples.forEach((ex) => select.appendChild(el("option", { value: ex.name }, ex.name)));
    } catch (_) { /* non-fatal */ }

    $("#example-select").addEventListener("change", async (ev) => {
      const name = ev.target.value;
      if (!name) return;
      try {
        const { ttl } = await api(`/api/examples/${encodeURIComponent(name)}`);
        Editor.setValue(ttl);
        setStatus("ok", `Loaded example: ${name}`);
      } catch (error) {
        setStatus("error", error.message);
      }
    });

    $("#file-input").addEventListener("change", (ev) => {
      const file = ev.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        Editor.setValue(String(reader.result));
        setStatus("ok", `Loaded file: ${file.name}`);
      };
      reader.readAsText(file);
      ev.target.value = "";
    });

    $("#btn-starter").addEventListener("click", () => {
      Editor.setValue(STARTER_TTL);
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
        openDrawer("findings");
        setStatus("ok", `Assessment finished`, `${data.summary.riskFindingCount} findings · ${data.summary.motifMatchCount} matches`);
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
})();
