"use strict";

/* Live architecture graph preview: layered left-to-right layout of the BEAM
 * flow graph, boxology-style node shapes, pan/zoom, node details, and
 * evidence highlighting.
 * Exposes window.GraphView = { init, render, clear, setHighlight, fit }.
 */
(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";

  const NODE_H = 44;
  const LAYER_GAP = 110;
  const ROW_GAP = 34;

  let svg, viewport, wrap, detailBox, emptyBox;
  let current = { nodes: [], edges: [] };
  let positions = new Map();
  let view = { x: 0, y: 0, w: 1000, h: 700 };
  let contentBox = null;
  let highlighted = new Set();

  function svgEl(tag, attrs = {}, parent = null) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function nodeWidth(node) {
    const chars = Math.max(node.label.length, (node.typeLabel || "").length + 4);
    return Math.max(130, Math.min(240, chars * 7.4 + 30));
  }

  // ---- layout ---------------------------------------------------------------
  function layout(nodes, edges) {
    const layer = new Map(nodes.map((n) => [n.id, 0]));
    const ids = new Set(nodes.map((n) => n.id));
    const flowEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));

    // longest-path layering with a relaxation cap so cycles terminate
    for (let pass = 0; pass < nodes.length + 1; pass += 1) {
      let changed = false;
      for (const e of flowEdges) {
        const want = layer.get(e.source) + 1;
        if (want > layer.get(e.target) && want <= nodes.length) {
          layer.set(e.target, want);
          changed = true;
        }
      }
      if (!changed) break;
    }

    // group by layer, then reduce crossings with a few barycenter sweeps
    const layers = new Map();
    for (const n of nodes) {
      const l = layer.get(n.id);
      if (!layers.has(l)) layers.set(l, []);
      layers.get(l).push(n);
    }
    const layerKeys = Array.from(layers.keys()).sort((a, b) => a - b);
    const order = new Map();
    layerKeys.forEach((l) => layers.get(l).forEach((n, i) => order.set(n.id, i)));

    const preds = new Map();
    const succs = new Map();
    for (const e of flowEdges) {
      if (!preds.has(e.target)) preds.set(e.target, []);
      preds.get(e.target).push(e.source);
      if (!succs.has(e.source)) succs.set(e.source, []);
      succs.get(e.source).push(e.target);
    }
    const sweep = (neighbours) => {
      for (const l of layerKeys) {
        const row = layers.get(l);
        row.sort((a, b) => {
          const bary = (n) => {
            const ns = neighbours.get(n.id) || [];
            if (!ns.length) return order.get(n.id);
            return ns.reduce((acc, m) => acc + (order.get(m) ?? 0), 0) / ns.length;
          };
          return bary(a) - bary(b);
        });
        row.forEach((n, i) => order.set(n.id, i));
      }
    };
    sweep(preds); sweep(succs); sweep(preds);

    // coordinates: x by layer (widest node wins), y centered per layer
    positions = new Map();
    let x = 0;
    const totalHeight = Math.max(...layerKeys.map((l) => layers.get(l).length)) * (NODE_H + ROW_GAP);
    for (const l of layerKeys) {
      const row = layers.get(l);
      const w = Math.max(...row.map(nodeWidth));
      const rowHeight = row.length * (NODE_H + ROW_GAP) - ROW_GAP;
      let y = (totalHeight - rowHeight) / 2;
      for (const n of row) {
        positions.set(n.id, { x: x + (w - nodeWidth(n)) / 2, y, w: nodeWidth(n), h: NODE_H });
        y += NODE_H + ROW_GAP;
      }
      x += w + LAYER_GAP;
    }
  }

  // ---- rendering ------------------------------------------------------------
  function edgePath(e) {
    const s = positions.get(e.source);
    const t = positions.get(e.target);
    if (!s || !t) return null;
    const x1 = s.x + s.w;
    const y1 = s.y + s.h / 2;
    const x2 = t.x;
    const y2 = t.y + t.h / 2;
    if (x2 >= x1) {
      const dx = Math.max(30, (x2 - x1) / 2);
      return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
    }
    // back edge: route below both nodes
    const yb = Math.max(y1, y2) + NODE_H * 1.4;
    return `M ${s.x + s.w / 2} ${s.y + s.h} C ${s.x + s.w / 2} ${yb}, ${t.x + t.w / 2} ${yb}, ${t.x + t.w / 2} ${t.y + t.h}`;
  }

  function nodeShape(group, node, pos) {
    const common = { class: `shape ${node.kind}` };
    if (node.kind === "model") {
      const c = 12;
      const pts = [
        [pos.x + c, pos.y], [pos.x + pos.w - c, pos.y], [pos.x + pos.w, pos.y + pos.h / 2],
        [pos.x + pos.w - c, pos.y + pos.h], [pos.x + c, pos.y + pos.h], [pos.x, pos.y + pos.h / 2],
      ].map((p) => p.join(",")).join(" ");
      svgEl("polygon", { ...common, points: pts }, group);
    } else if (node.kind === "agent") {
      svgEl("ellipse", {
        ...common, cx: pos.x + pos.w / 2, cy: pos.y + pos.h / 2, rx: pos.w / 2, ry: pos.h / 2,
      }, group);
    } else {
      const rx = node.kind === "data" || node.kind === "symbol" ? 16 : 4;
      svgEl("rect", { ...common, x: pos.x, y: pos.y, width: pos.w, height: pos.h, rx }, group);
    }
  }

  function render(data) {
    current = data;
    highlighted = new Set();
    svg.innerHTML = "";
    detailBox.classList.add("hidden");

    if (!data.nodes.length) {
      emptyBox.classList.remove("hidden");
      contentBox = null;
      return;
    }
    emptyBox.classList.add("hidden");

    layout(data.nodes, data.edges);

    const defs = svgEl("defs", {}, svg);
    for (const kind of ["use", "produce", "inform", "participatedIn"]) {
      const marker = svgEl("marker", {
        id: `arrow-${kind}`, viewBox: "0 0 10 10", refX: 9, refY: 5,
        markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse",
      }, defs);
      svgEl("path", { d: "M 0 0 L 10 5 L 0 10 z", class: `arrow ${kind}` }, marker);
    }

    viewport = svgEl("g", { id: "viewport" }, svg);
    const edgeLayer = svgEl("g", { class: "edges" }, viewport);
    const nodeLayer = svgEl("g", { class: "nodes" }, viewport);

    for (const e of current.edges) {
      const d = edgePath(e);
      if (!d) continue;
      svgEl("path", {
        d, class: `edge ${e.kind}`, fill: "none",
        "marker-end": `url(#arrow-${e.kind})`,
        "data-source": e.source, "data-target": e.target,
      }, edgeLayer);
    }

    for (const node of current.nodes) {
      const pos = positions.get(node.id);
      const group = svgEl("g", { class: `node ${node.kind}`, "data-id": node.id }, nodeLayer);
      nodeShape(group, node, pos);
      const label = svgEl("text", {
        x: pos.x + pos.w / 2, y: pos.y + pos.h / 2 + (node.typeLabel ? -2 : 4),
        class: "node-label", "text-anchor": "middle",
      }, group);
      label.textContent = truncate(node.label, Math.floor(pos.w / 7));
      if (node.typeLabel) {
        const type = svgEl("text", {
          x: pos.x + pos.w / 2, y: pos.y + pos.h / 2 + 13,
          class: "node-type", "text-anchor": "middle",
        }, group);
        type.textContent = node.typeLabel + (node.roles.length ? ` · ${node.roles.length} role${node.roles.length > 1 ? "s" : ""}` : "");
      }
      group.addEventListener("click", (ev) => { ev.stopPropagation(); showDetail(node, pos); });
    }

    const pad = 40;
    const xs = Array.from(positions.values());
    contentBox = {
      x: -pad,
      y: Math.min(...xs.map((p) => p.y)) - pad,
      w: Math.max(...xs.map((p) => p.x + p.w)) + pad * 2,
      h: Math.max(...xs.map((p) => p.y + p.h)) - Math.min(...xs.map((p) => p.y)) + pad * 2,
    };
    fit();
  }

  function truncate(text, max) {
    return text.length > max ? text.slice(0, Math.max(1, max - 1)) + "…" : text;
  }

  // ---- detail popover -------------------------------------------------------
  function showDetail(node) {
    const rows = [];
    rows.push(`<h4>${escape(node.label)}</h4>`);
    if (node.typeLabel) rows.push(`<div class="detail-row"><span>BEAM type</span>${escape(node.typeLabel)}</div>`);
    if (node.roles.length) rows.push(`<div class="detail-row"><span>Roles</span>${node.roles.map(escape).join(", ")}</div>`);
    if (node.categories.length) rows.push(`<div class="detail-row"><span>Data categories</span>${node.categories.map(escape).join(", ")}</div>`);
    rows.push(`<div class="detail-row uri"><span>URI</span>${escape(node.id)}</div>`);
    detailBox.innerHTML = rows.join("");
    detailBox.classList.remove("hidden");
  }

  function escape(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // ---- pan / zoom -----------------------------------------------------------
  function applyView() {
    svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
  }

  function fit() {
    if (!contentBox) return;
    const aspect = wrap.clientWidth / Math.max(1, wrap.clientHeight);
    let w = contentBox.w;
    let h = contentBox.h;
    if (w / h > aspect) h = w / aspect; else w = h * aspect;
    view = { x: contentBox.x - (w - contentBox.w) / 2, y: contentBox.y - (h - contentBox.h) / 2, w, h };
    applyView();
  }

  function zoom(factor, cx, cy) {
    const px = view.x + (cx / wrap.clientWidth) * view.w;
    const py = view.y + (cy / wrap.clientHeight) * view.h;
    view.w *= factor;
    view.h *= factor;
    view.x = px - (cx / wrap.clientWidth) * view.w;
    view.y = py - (cy / wrap.clientHeight) * view.h;
    applyView();
  }

  function initPanZoom() {
    let dragging = null;
    wrap.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".node") || ev.target.closest(".canvas-controls") || ev.target.closest(".node-detail")) return;
      dragging = { x: ev.clientX, y: ev.clientY };
      wrap.setPointerCapture(ev.pointerId);
      detailBox.classList.add("hidden");
    });
    wrap.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      view.x -= ((ev.clientX - dragging.x) / wrap.clientWidth) * view.w;
      view.y -= ((ev.clientY - dragging.y) / wrap.clientHeight) * view.h;
      dragging = { x: ev.clientX, y: ev.clientY };
      applyView();
    });
    wrap.addEventListener("pointerup", () => { dragging = null; });
    wrap.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const rect = wrap.getBoundingClientRect();
      zoom(ev.deltaY > 0 ? 1.12 : 1 / 1.12, ev.clientX - rect.left, ev.clientY - rect.top);
    }, { passive: false });

    document.getElementById("btn-zoom-in").addEventListener("click", () => zoom(1 / 1.25, wrap.clientWidth / 2, wrap.clientHeight / 2));
    document.getElementById("btn-zoom-out").addEventListener("click", () => zoom(1.25, wrap.clientWidth / 2, wrap.clientHeight / 2));
    document.getElementById("btn-fit").addEventListener("click", fit);
  }

  // ---- evidence highlighting ------------------------------------------------
  function setHighlight(ids) {
    highlighted = new Set(ids || []);
    if (!viewport) return;
    const active = highlighted.size > 0;
    viewport.classList.toggle("has-highlight", active);
    for (const group of viewport.querySelectorAll(".node")) {
      group.classList.toggle("highlight", highlighted.has(group.dataset.id));
    }
    for (const path of viewport.querySelectorAll(".edge")) {
      path.classList.toggle(
        "highlight",
        active && highlighted.has(path.dataset.source) && highlighted.has(path.dataset.target)
      );
    }
  }

  function clear() {
    current = { nodes: [], edges: [] };
    svg.innerHTML = "";
    contentBox = null;
    emptyBox.classList.remove("hidden");
    detailBox.classList.add("hidden");
  }

  function init() {
    svg = document.getElementById("canvas");
    wrap = document.getElementById("canvas-wrap");
    detailBox = document.getElementById("node-detail");
    emptyBox = document.getElementById("canvas-empty");
    initPanZoom();
    applyView();
    window.addEventListener("resize", () => { if (contentBox) fit(); });
  }

  window.GraphView = { init, render, clear, setHighlight, fit };
})();
