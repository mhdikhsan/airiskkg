"use strict";

/* Draw mode: drag components from the palette, connect them, edit their
 * properties, and generate Turtle into the editor (via /api/build).
 * The reverse direction ("From code") converts the current editor graph
 * into an editable scene.
 * Exposes window.DrawMode = { init, show, hide, loadFromGraph, isEmpty }.
 */
(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const BEAM = "http://w3id.org/beam/core#";

  const PALETTE = [
    { kind: "data", label: "Data", classUri: BEAM + "Data" },
    { kind: "symbol", label: "Symbol", classUri: BEAM + "Symbol" },
    { kind: "model", label: "Statistical Model", classUri: BEAM + "StatisticalModel" },
    { kind: "model", label: "Semantic Model", classUri: BEAM + "SemanticModel" },
    { kind: "process", label: "Transform", classUri: BEAM + "Transform" },
    { kind: "process", label: "Infer", classUri: BEAM + "Infer" },
    { kind: "process", label: "Train", classUri: BEAM + "Train" },
    { kind: "process", label: "Generate", classUri: BEAM + "Generate" },
  ];

  const RESOURCE_CLASSES = [
    { uri: BEAM + "Data", label: "Data", kind: "data" },
    { uri: BEAM + "Symbol", label: "Symbol", kind: "symbol" },
    { uri: BEAM + "StatisticalModel", label: "Statistical Model", kind: "model" },
    { uri: BEAM + "SemanticModel", label: "Semantic Model", kind: "model" },
  ];
  const PROCESS_CLASSES = [
    { uri: BEAM + "Transform", label: "Transform", kind: "process" },
    { uri: BEAM + "Infer", label: "Infer", kind: "process" },
    { uri: BEAM + "Train", label: "Train", kind: "process" },
    { uri: BEAM + "Generate", label: "Generate", kind: "process" },
    { uri: BEAM + "Process", label: "Process (generic)", kind: "process" },
  ];

  const NODE_W = 150;
  const NODE_H = 46;

  let svg, viewport, wrap, panel;
  let vocab = { roles: [], dataCategories: [] };
  let callbacks = {};
  let scene = { nodes: [], edges: [], nextId: 1 };
  let selection = null; // {type:'node'|'edge', id}
  let visible = false;

  // ---- helpers ---------------------------------------------------------------
  function svgEl(tag, attrs = {}, parent = null) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function htmlEl(tag, attrs = {}, children = []) {
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

  function toSvgPoint(clientX, clientY) {
    const pt = new DOMPoint(clientX, clientY);
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  function isProcess(node) { return node.kind === "process"; }

  function nodeById(id) { return scene.nodes.find((n) => n.id === id); }

  function uniqueName(base) {
    let cleaned = (base || "Element").replace(/[^A-Za-z0-9_]/g, "");
    if (!cleaned) cleaned = "Element";
    if (/^\d/.test(cleaned)) cleaned = "El" + cleaned;
    const taken = new Set(scene.nodes.map((n) => n.name));
    if (!taken.has(cleaned)) return cleaned;
    let i = 2;
    while (taken.has(cleaned + i)) i += 1;
    return cleaned + i;
  }

  function edgeKindFor(source, target) {
    if (!isProcess(source) && isProcess(target)) return "use";
    if (isProcess(source) && !isProcess(target)) return "produce";
    if (isProcess(source) && isProcess(target)) return "inform";
    return null; // resource -> resource is not a BEAM flow
  }

  function status(state, message) {
    if (callbacks.onStatus) callbacks.onStatus(state, message);
  }

  // ---- scene mutations -------------------------------------------------------
  function addNode(paletteItem, x, y) {
    const node = {
      id: `n${scene.nextId++}`,
      name: uniqueName(paletteItem.label.replace(/\s/g, "")),
      label: paletteItem.label,
      kind: paletteItem.kind,
      classUri: paletteItem.classUri,
      roles: [],
      categories: [],
      x: Math.round(x - NODE_W / 2),
      y: Math.round(y - NODE_H / 2),
    };
    scene.nodes.push(node);
    select({ type: "node", id: node.id });
    render();
    return node;
  }

  function addEdge(sourceId, targetId) {
    if (sourceId === targetId) return;
    const source = nodeById(sourceId);
    const target = nodeById(targetId);
    const kind = edgeKindFor(source, target);
    if (!kind) {
      status("error", "Resources cannot connect directly - flow always passes through a process.");
      return;
    }
    if (scene.edges.some((e) => e.source === sourceId && e.target === targetId)) return;
    scene.edges.push({ id: `e${scene.nextId++}`, source: sourceId, target: targetId, kind });
    render();
  }

  function deleteSelection() {
    if (!selection) return;
    if (selection.type === "node") {
      scene.nodes = scene.nodes.filter((n) => n.id !== selection.id);
      scene.edges = scene.edges.filter((e) => e.source !== selection.id && e.target !== selection.id);
    } else {
      scene.edges = scene.edges.filter((e) => e.id !== selection.id);
    }
    select(null);
    render();
  }

  function select(sel) {
    selection = sel;
    renderPanel();
  }

  // ---- rendering ---------------------------------------------------------------
  function edgePath(e) {
    const s = nodeById(e.source);
    const t = nodeById(e.target);
    if (!s || !t) return null;
    const sc = { x: s.x + NODE_W / 2, y: s.y + NODE_H / 2 };
    const tc = { x: t.x + NODE_W / 2, y: t.y + NODE_H / 2 };
    // attach to left/right side depending on relative position
    const sx = tc.x >= sc.x ? s.x + NODE_W : s.x;
    const tx = tc.x >= sc.x ? t.x : t.x + NODE_W;
    const dx = Math.max(30, Math.abs(tx - sx) / 2) * (tc.x >= sc.x ? 1 : -1);
    return `M ${sx} ${sc.y} C ${sx + dx} ${sc.y}, ${tx - dx} ${tc.y}, ${tx} ${tc.y}`;
  }

  function nodeShape(group, node) {
    const common = { class: `shape ${node.kind}` };
    if (node.kind === "model") {
      const c = 12;
      const p = [[node.x + c, node.y], [node.x + NODE_W - c, node.y], [node.x + NODE_W, node.y + NODE_H / 2],
        [node.x + NODE_W - c, node.y + NODE_H], [node.x + c, node.y + NODE_H], [node.x, node.y + NODE_H / 2]];
      svgEl("polygon", { ...common, points: p.map((q) => q.join(",")).join(" ") }, group);
    } else {
      const rx = node.kind === "process" ? 4 : 16;
      svgEl("rect", { ...common, x: node.x, y: node.y, width: NODE_W, height: NODE_H, rx }, group);
    }
  }

  function render() {
    viewport.innerHTML = "";
    const edgeLayer = svgEl("g", {}, viewport);
    const nodeLayer = svgEl("g", {}, viewport);

    for (const e of scene.edges) {
      const d = edgePath(e);
      if (!d) continue;
      const selected = selection && selection.type === "edge" && selection.id === e.id;
      svgEl("path", {
        d, class: `edge ${e.kind}${selected ? " selected" : ""}`, fill: "none",
        "marker-end": `url(#draw-arrow-${e.kind})`, "data-edge": e.id,
      }, edgeLayer);
      // fat invisible hit path for easier clicking
      const hit = svgEl("path", { d, class: "edge-hit", fill: "none", "data-edge": e.id }, edgeLayer);
      hit.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); select({ type: "edge", id: e.id }); render(); });
    }

    for (const node of scene.nodes) {
      const selected = selection && selection.type === "node" && selection.id === node.id;
      const group = svgEl("g", { class: `dnode node ${node.kind}${selected ? " selected" : ""}`, "data-id": node.id }, nodeLayer);
      nodeShape(group, node);
      const label = svgEl("text", {
        x: node.x + NODE_W / 2, y: node.y + NODE_H / 2 - 2, class: "node-label", "text-anchor": "middle",
      }, group);
      label.textContent = node.label.length > 20 ? node.label.slice(0, 19) + "…" : node.label;
      const sub = svgEl("text", {
        x: node.x + NODE_W / 2, y: node.y + NODE_H / 2 + 13, class: "node-type", "text-anchor": "middle",
      }, group);
      const typeName = node.classUri.split("#").pop();
      const badges = [];
      if (node.roles.length) badges.push(`${node.roles.length} role${node.roles.length > 1 ? "s" : ""}`);
      if (node.categories.length) badges.push(`${node.categories.length} categor${node.categories.length > 1 ? "ies" : "y"}`);
      sub.textContent = typeName + (badges.length ? ` · ${badges.join(" · ")}` : "");
      // connect port
      const port = svgEl("circle", {
        cx: node.x + NODE_W, cy: node.y + NODE_H / 2, r: 7, class: "port", "data-port": node.id,
      }, group);
      port.addEventListener("pointerdown", (ev) => startConnect(ev, node));
      group.addEventListener("pointerdown", (ev) => {
        if (ev.target.classList.contains("port")) return;
        ev.stopPropagation();
        startDrag(ev, node);
      });
    }
  }

  // ---- interactions ------------------------------------------------------------
  function startDrag(ev, node) {
    select({ type: "node", id: node.id });
    render();
    const start = toSvgPoint(ev.clientX, ev.clientY);
    const orig = { x: node.x, y: node.y };
    const move = (mv) => {
      const pt = toSvgPoint(mv.clientX, mv.clientY);
      node.x = Math.round(orig.x + pt.x - start.x);
      node.y = Math.round(orig.y + pt.y - start.y);
      render();
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function startConnect(ev, sourceNode) {
    ev.stopPropagation();
    const temp = svgEl("path", { class: "edge temp", fill: "none" }, viewport);
    const sx = sourceNode.x + NODE_W;
    const sy = sourceNode.y + NODE_H / 2;
    const move = (mv) => {
      const pt = toSvgPoint(mv.clientX, mv.clientY);
      temp.setAttribute("d", `M ${sx} ${sy} L ${pt.x} ${pt.y}`);
    };
    const up = (uv) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      temp.remove();
      const hit = document.elementFromPoint(uv.clientX, uv.clientY);
      const group = hit && hit.closest ? hit.closest(".dnode") : null;
      if (group) addEdge(sourceNode.id, group.dataset.id);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // ---- property panel ----------------------------------------------------------
  // Checkbox list with a filter box and removable chips for the current
  // selection. Deliberately not a native <select multiple>: that requires
  // ctrl/cmd-click to add to a selection (a single plain click replaces it),
  // which reads as "broken" for a list of 80 pattern roles. Also deliberately
  // NOT wrapped in a <label>: labels forward clicks on any non-control area
  // to their first control, which would silently toggle/remove the wrong
  // checkbox or chip when clicking elsewhere in the widget.
  function checkList(items, chosenIds, onchange, emptyHint) {
    const wrap = htmlEl("div", { class: "checklist" });
    const chosen = new Set(chosenIds);
    const chips = htmlEl("div", { class: "chips" });
    const box = htmlEl("div", { class: "checklist-box" });
    const search = htmlEl("input", {
      type: "text", class: "checklist-search",
      placeholder: items.length > 8 ? `Filter ${items.length} options…` : "Filter…",
    });
    const labelFor = (id) => (items.find((it) => it.id === id) || {}).label || id;

    function renderChips() {
      chips.innerHTML = "";
      if (!chosen.size) {
        chips.appendChild(htmlEl("span", { class: "chips-empty" }, emptyHint || "None selected"));
        return;
      }
      for (const id of chosen) {
        const removeBtn = htmlEl("button", { type: "button", class: "chip-x", title: "Remove" }, "×");
        removeBtn.addEventListener("click", () => {
          chosen.delete(id);
          onchange(Array.from(chosen));
          renderChips();
          renderRows(search.value);
        });
        chips.appendChild(htmlEl("span", { class: "chip" }, [labelFor(id), removeBtn]));
      }
    }

    function renderRows(filter) {
      box.innerHTML = "";
      const q = (filter || "").toLowerCase().trim();
      const filtered = q ? items.filter((it) => it.label.toLowerCase().includes(q)) : items;
      if (!filtered.length) {
        box.appendChild(htmlEl("p", { class: "checklist-empty" }, "No matches."));
        return;
      }
      for (const item of filtered) {
        const cb = htmlEl("input", { type: "checkbox" });
        cb.checked = chosen.has(item.id);
        cb.addEventListener("change", () => {
          if (cb.checked) chosen.add(item.id); else chosen.delete(item.id);
          onchange(Array.from(chosen));
          renderChips();
        });
        box.appendChild(htmlEl("label", { class: "checklist-row" }, [cb, htmlEl("span", {}, item.label)]));
      }
    }

    search.addEventListener("input", () => renderRows(search.value));
    renderChips();
    renderRows("");
    wrap.appendChild(chips);
    if (items.length > 8) wrap.appendChild(search);
    wrap.appendChild(box);
    return wrap;
  }

  function renderPanel() {
    panel.innerHTML = "";
    if (!selection) {
      panel.appendChild(htmlEl("h4", {}, "System"));
      panel.appendChild(htmlEl("label", { class: "pfield" }, ["Name",
        htmlEl("input", { type: "text", value: scene.systemName || "System",
          oninput: (ev) => { scene.systemName = ev.target.value; } })]));
      panel.appendChild(htmlEl("label", { class: "pfield" }, ["Label",
        htmlEl("input", { type: "text", value: scene.systemLabel || "", placeholder: "My RAG system",
          oninput: (ev) => { scene.systemLabel = ev.target.value; } })]));
      panel.appendChild(htmlEl("p", { class: "phint" },
        "Drag components from the palette. Drag the ○ port of a node onto another node to connect them. Select a node to edit it."));
      return;
    }

    if (selection.type === "edge") {
      const edge = scene.edges.find((e) => e.id === selection.id);
      if (!edge) { select(null); return; }
      const s = nodeById(edge.source), t = nodeById(edge.target);
      panel.appendChild(htmlEl("h4", {}, `Edge: ${edge.kind}`));
      panel.appendChild(htmlEl("p", { class: "phint" }, `${s ? s.label : "?"} → ${t ? t.label : "?"}`));
      panel.appendChild(htmlEl("button", { type: "button", class: "btn danger", onclick: deleteSelection }, "Delete edge"));
      return;
    }

    const node = nodeById(selection.id);
    if (!node) { select(null); return; }
    panel.appendChild(htmlEl("h4", {}, node.kind === "process" ? "Process" : "Resource"));
    panel.appendChild(htmlEl("label", { class: "pfield" }, ["Name (identifier)",
      htmlEl("input", { type: "text", value: node.name,
        oninput: (ev) => { node.name = ev.target.value; } })]));
    panel.appendChild(htmlEl("label", { class: "pfield" }, ["Label",
      htmlEl("input", { type: "text", value: node.label,
        oninput: (ev) => { node.label = ev.target.value; render(); } })]));

    const classes = isProcess(node) ? PROCESS_CLASSES : RESOURCE_CLASSES;
    const classSelect = htmlEl("select", {});
    for (const cls of classes) {
      classSelect.appendChild(htmlEl("option", { value: cls.uri, selected: cls.uri === node.classUri ? "selected" : null }, cls.label));
    }
    classSelect.addEventListener("change", () => {
      node.classUri = classSelect.value;
      const cls = classes.find((c) => c.uri === classSelect.value);
      if (cls) node.kind = cls.kind;
      render();
    });
    panel.appendChild(htmlEl("label", { class: "pfield" }, ["BEAM class", classSelect]));

    // Not <label>-wrapped on purpose (see checkList's comment) - these
    // widgets contain many controls, and a wrapping <label> would forward
    // clicks on empty space to the first checkbox/chip inside it.
    panel.appendChild(htmlEl("div", { class: "pfield" }, [
      htmlEl("span", { class: "pfield-title" }, "Pattern roles"),
      checkList(vocab.roles, node.roles, (v) => { node.roles = v; render(); }, "No roles assigned"),
    ]));
    if (!isProcess(node)) {
      panel.appendChild(htmlEl("div", { class: "pfield" }, [
        htmlEl("span", { class: "pfield-title" }, "Data categories"),
        checkList(vocab.dataCategories, node.categories, (v) => { node.categories = v; render(); }, "No categories assigned"),
      ]));
    }
    panel.appendChild(htmlEl("button", { type: "button", class: "btn danger", onclick: deleteSelection }, node.kind === "process" ? "Delete process" : "Delete resource"));
  }

  // ---- scene <-> builder model ---------------------------------------------------
  function toBuilderModel() {
    const resources = scene.nodes.filter((n) => !isProcess(n)).map((n) => ({
      name: n.name, label: n.label, class: n.classUri, roles: n.roles, dataCategories: n.categories,
    }));
    const processes = scene.nodes.filter(isProcess).map((n) => {
      const use = [], produce = [], inform = [];
      for (const e of scene.edges) {
        if (e.kind === "use" && e.target === n.id) use.push(nodeById(e.source).name);
        if (e.kind === "produce" && e.source === n.id) produce.push(nodeById(e.target).name);
        if (e.kind === "inform" && e.source === n.id) inform.push(nodeById(e.target).name);
      }
      return { name: n.name, label: n.label, class: n.classUri, roles: n.roles, use, produce, inform };
    });
    return {
      systemName: scene.systemName || "System",
      systemLabel: scene.systemLabel || "",
      resources,
      processes,
    };
  }

  /** Populate the scene from an /api/graph payload (code -> diagram). */
  function loadFromGraph(data) {
    const drawable = data.nodes.filter((n) => n.kind !== "agent" && n.kind !== "task");
    const skipped = data.nodes.length - drawable.length;
    const positions = window.GraphView.layoutPositions(drawable, data.edges);
    scene = { nodes: [], edges: [], nextId: 1 };
    scene.systemName = data.systems.length ? data.systems[0].id.split(/[#/]/).pop() : "System";
    scene.systemLabel = data.systems.length ? data.systems[0].label : "";
    const idMap = new Map();
    const taken = new Set();
    for (const n of drawable) {
      const pos = positions.get(n.id) || { x: 40, y: 40 };
      let name = n.id.split(/[#/]/).pop().replace(/[^A-Za-z0-9_]/g, "") || `El${scene.nextId}`;
      if (/^\d/.test(name)) name = "El" + name;
      let unique = name; let i = 2;
      while (taken.has(unique)) unique = name + i++;
      taken.add(unique);
      const id = `n${scene.nextId++}`;
      idMap.set(n.id, id);
      scene.nodes.push({
        id, name: unique, label: n.label,
        kind: n.kind === "resource" || n.kind === "other" ? "data" : n.kind,
        classUri: n.typeUri || (BEAM + (n.kind === "process" ? "Process" : "Data")),
        roles: n.roleIds || [], categories: n.categoryIds || [],
        x: Math.round(pos.x), y: Math.round(pos.y),
      });
    }
    for (const e of data.edges) {
      if (e.kind === "participatedIn") continue;
      const source = idMap.get(e.source), target = idMap.get(e.target);
      if (source && target) scene.edges.push({ id: `e${scene.nextId++}`, source, target, kind: e.kind });
    }
    select(null);
    render();
    fitView();
    status("ok", `Diagram loaded from code (${scene.nodes.length} nodes${skipped ? `, ${skipped} agent/task nodes skipped` : ""})`);
  }

  // ---- view ----------------------------------------------------------------------
  let view = { x: -40, y: -40, w: 1200, h: 800 };

  function applyView() {
    svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
  }

  function fitView() {
    if (!scene.nodes.length) { view = { x: -40, y: -40, w: 1200, h: 800 }; applyView(); return; }
    const pad = 60;
    const minX = Math.min(...scene.nodes.map((n) => n.x)) - pad;
    const minY = Math.min(...scene.nodes.map((n) => n.y)) - pad;
    const maxX = Math.max(...scene.nodes.map((n) => n.x + NODE_W)) + pad;
    const maxY = Math.max(...scene.nodes.map((n) => n.y + NODE_H)) + pad;
    const aspect = wrap.clientWidth / Math.max(1, wrap.clientHeight);
    let w = maxX - minX, h = maxY - minY;
    if (w / h > aspect) h = w / aspect; else w = h * aspect;
    view = { x: minX, y: minY, w, h };
    applyView();
  }

  function initViewInteractions() {
    let panning = null;
    svg.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".dnode") || ev.target.classList.contains("port")) return;
      select(null);
      render();
      panning = { x: ev.clientX, y: ev.clientY };
    });
    window.addEventListener("pointermove", (ev) => {
      if (!panning) return;
      view.x -= ((ev.clientX - panning.x) / wrap.clientWidth) * view.w;
      view.y -= ((ev.clientY - panning.y) / wrap.clientHeight) * view.h;
      panning = { x: ev.clientX, y: ev.clientY };
      applyView();
    });
    window.addEventListener("pointerup", () => { panning = null; });
    svg.addEventListener("wheel", (ev) => {
      if (!visible) return;
      ev.preventDefault();
      const factor = ev.deltaY > 0 ? 1.12 : 1 / 1.12;
      const rect = wrap.getBoundingClientRect();
      const px = view.x + ((ev.clientX - rect.left) / wrap.clientWidth) * view.w;
      const py = view.y + ((ev.clientY - rect.top) / wrap.clientHeight) * view.h;
      view.w *= factor; view.h *= factor;
      view.x = px - ((ev.clientX - rect.left) / wrap.clientWidth) * view.w;
      view.y = py - ((ev.clientY - rect.top) / wrap.clientHeight) * view.h;
      applyView();
    }, { passive: false });

    document.addEventListener("keydown", (ev) => {
      if (!visible || ev.target.matches("input, textarea, select")) return;
      if (ev.key === "Delete" || ev.key === "Backspace") deleteSelection();
    });
  }

  function initPalette() {
    const palette = document.getElementById("palette");
    for (const item of PALETTE) {
      const chip = htmlEl("div", { class: `palette-item ${item.kind}`, draggable: "true", title: `Drag onto the canvas (${item.classUri.split("#").pop()})` }, item.label);
      chip.addEventListener("dragstart", (ev) => {
        ev.dataTransfer.setData("text/palette", JSON.stringify(item));
        ev.dataTransfer.effectAllowed = "copy";
      });
      chip.addEventListener("dblclick", () => {
        addNode(item, view.x + view.w / 2, view.y + view.h / 2);
      });
      palette.appendChild(chip);
    }
    wrap.addEventListener("dragover", (ev) => {
      if (visible) { ev.preventDefault(); ev.dataTransfer.dropEffect = "copy"; }
    });
    wrap.addEventListener("drop", (ev) => {
      if (!visible) return;
      const raw = ev.dataTransfer.getData("text/palette");
      if (!raw) return;
      ev.preventDefault();
      const pt = toSvgPoint(ev.clientX, ev.clientY);
      addNode(JSON.parse(raw), pt.x, pt.y);
    });
  }

  // ---- public API ------------------------------------------------------------------
  function show() {
    visible = true;
    document.getElementById("draw-layer").classList.remove("hidden");
    renderPanel();
    render();
  }

  function hide() {
    visible = false;
    document.getElementById("draw-layer").classList.add("hidden");
  }

  function isEmpty() {
    return scene.nodes.length === 0;
  }

  function init(options) {
    vocab = options.vocabulary || vocab;
    callbacks = options;
    svg = document.getElementById("draw-canvas");
    wrap = document.getElementById("canvas-wrap");
    panel = document.getElementById("draw-panel");

    const defs = svgEl("defs", {}, svg);
    for (const kind of ["use", "produce", "inform"]) {
      const marker = svgEl("marker", {
        id: `draw-arrow-${kind}`, viewBox: "0 0 10 10", refX: 9, refY: 5,
        markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse",
      }, defs);
      svgEl("path", { d: "M 0 0 L 10 5 L 0 10 z", class: `arrow ${kind}` }, marker);
    }
    viewport = svgEl("g", {}, svg);
    applyView();
    initViewInteractions();
    initPalette();

    document.getElementById("btn-draw-from-code").addEventListener("click", () => {
      if (callbacks.onFromCode) callbacks.onFromCode();
    });
    document.getElementById("btn-draw-generate").addEventListener("click", async () => {
      if (!scene.nodes.length) { status("error", "The canvas is empty - drag components from the palette first."); return; }
      if (callbacks.onGenerate) callbacks.onGenerate(toBuilderModel());
    });
    document.getElementById("btn-draw-clear").addEventListener("click", () => {
      scene = { nodes: [], edges: [], nextId: 1, systemName: scene.systemName, systemLabel: scene.systemLabel };
      select(null);
      render();
    });
    document.getElementById("btn-draw-fit").addEventListener("click", fitView);
    renderPanel();
  }

  window.DrawMode = { init, show, hide, loadFromGraph, isEmpty };
})();
