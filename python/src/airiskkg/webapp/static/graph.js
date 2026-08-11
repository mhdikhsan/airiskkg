"use strict";

/* Live architecture graph preview: layered left-to-right layout of the BEAM
 * flow graph, boxology-style node shapes, pan/zoom, node details, and
 * evidence highlighting, and standalone SVG export.
 * The public surface is the window.GraphView assignment at the end of the file.
 */
(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";

  const NODE_H = 44;
  const LAYER_GAP = 110;
  const ROW_GAP = 34;

  // Human-readable meaning of each BEAM flow edge, shown on hover so viewers
  // can tell the three arrow kinds apart.
  const EDGE_MEANINGS = {
    use:            { title: "uses",           dir: "process → resource", body: "The process reads this resource as input." },
    produce:        { title: "produces",       dir: "process → resource", body: "The process writes this resource as output." },
    inform:         { title: "informs",        dir: "process → process",  body: "One step hands off to the next; data or control flows between processes." },
    participatedIn: { title: "participates in", dir: "resource ↔ process", body: "Imported participation link between a resource and a process." },
  };

  let svg, viewport, wrap, detailBox, emptyBox, tipBox;
  let current = { nodes: [], edges: [] };
  let positions = new Map();
  let view = { x: 0, y: 0, w: 1000, h: 700 };
  let contentBox = null;
  let highlighted = new Set();
  let manualPositions = new Map(); // node id -> {x,y} drag overrides (view-only)
  let lastNodeIds = "";            // to refit only when the element set changes
  let suppressFitOnce = false;     // set by placeNodeAt so a dropped node stays put
  let selectedId = null;           // the element clicked for editing (Del key target)

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

  /* Disconnected parts of the graph are laid out separately and stacked.
   *
   * A single global layered layout assigns every source node to layer 0, so two
   * unconnected flows - which is exactly what you get after dropping a motif
   * from the catalogue onto an existing diagram - are interleaved into the same
   * columns and rows. The barycentre sweep cannot pull them apart either,
   * because there are no edges between them to pull on. The result reads as one
   * tangled diagram rather than two tidy ones.
   *
   * Laying out each connected component on its own and stacking them
   * vertically keeps each flow intact and puts a newly dropped motif in its own
   * band below what is already there.
   */
  const COMPONENT_GAP = 70;

  /** Sort key that reads trailing digits numerically, so e2 precedes e10.
   *  Generated element ids are minted sequentially (local:e1, e2, ...), so this
   *  orders components by when they were added: older above, newer below. */
  function naturalKey(id) {
    const match = /^(.*?)(\d+)$/.exec(String(id));
    return match ? [match[1], Number(match[2])] : [String(id), -1];
  }

  function compareIds(a, b) {
    const [pa, na] = naturalKey(a);
    const [pb, nb] = naturalKey(b);
    return pa === pb ? na - nb : pa < pb ? -1 : 1;
  }

  /** Weakly-connected components: flow direction is ignored, since a chain is
   *  one visual unit regardless of which way its arrows point. */
  function connectedComponents(nodes, flowEdges) {
    const parent = new Map(nodes.map((n) => [n.id, n.id]));
    const find = (id) => {
      while (parent.get(id) !== id) {
        parent.set(id, parent.get(parent.get(id)));
        id = parent.get(id);
      }
      return id;
    };
    const union = (a, b) => {
      const ra = find(a);
      const rb = find(b);
      if (ra !== rb) parent.set(ra, rb);
    };
    for (const e of flowEdges) union(e.source, e.target);

    const groups = new Map();
    for (const n of nodes) {
      const root = find(n.id);
      if (!groups.has(root)) groups.set(root, []);
      groups.get(root).push(n);
    }
    const components = Array.from(groups.values()).map((groupNodes) => {
      const memberIds = new Set(groupNodes.map((n) => n.id));
      return {
        nodes: groupNodes,
        edges: flowEdges.filter((e) => memberIds.has(e.source)),
        // Oldest element in the component decides where the band sits.
        key: groupNodes.map((n) => n.id).sort(compareIds)[0],
      };
    });
    components.sort((a, b) => compareIds(a.key, b.key));
    return components;
  }

  function layout(nodes, edges) {
    const ids = new Set(nodes.map((n) => n.id));
    const flowEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));

    positions = new Map();
    let offsetY = 0;
    for (const component of connectedComponents(nodes, flowEdges)) {
      const local = layoutComponent(component.nodes, component.edges);
      let minY = Infinity;
      let maxY = -Infinity;
      for (const p of local.values()) {
        minY = Math.min(minY, p.y);
        maxY = Math.max(maxY, p.y + p.h);
      }
      if (!isFinite(minY)) continue;
      for (const [id, p] of local) positions.set(id, { ...p, y: p.y - minY + offsetY });
      offsetY += maxY - minY + COMPONENT_GAP;
    }

    // Re-apply manual drag positions on top of the computed layout, so a dragged
    // node keeps its place across re-renders (positions are view-only state).
    for (const [id, p] of manualPositions) {
      const cur = positions.get(id);
      if (cur) positions.set(id, { ...cur, x: p.x, y: p.y });
    }
  }

  /** Layered left-to-right layout of one connected component, from its own
   *  origin. Returns positions rather than writing the module-level map. */
  function layoutComponent(nodes, flowEdges) {
    const layer = new Map(nodes.map((n) => [n.id, 0]));

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
    const placed = new Map();
    let x = 0;
    const totalHeight = Math.max(...layerKeys.map((l) => layers.get(l).length)) * (NODE_H + ROW_GAP);
    for (const l of layerKeys) {
      const row = layers.get(l);
      const w = Math.max(...row.map(nodeWidth));
      const rowHeight = row.length * (NODE_H + ROW_GAP) - ROW_GAP;
      let y = (totalHeight - rowHeight) / 2;
      for (const n of row) {
        placed.set(n.id, { x: x + (w - nodeWidth(n)) / 2, y, w: nodeWidth(n), h: NODE_H });
        y += NODE_H + ROW_GAP;
      }
      x += w + LAYER_GAP;
    }
    return placed;
  }

  // ---- rendering ------------------------------------------------------------

  /* Edges attach to whichever side of a box faces the other box, rather than
   * always leaving the right edge and arriving at the left.
   *
   * The layered layout puts most edges between adjacent layers, where the boxes
   * are separated horizontally and right -> left is correct. But nodes in the
   * same layer are stacked vertically, and nodes moved by hand can end up in any
   * arrangement at all; forcing right -> left there drags the line back across
   * both boxes and arrives from behind. Picking the facing sides keeps the line
   * outside the boxes and lets the arrowhead point the way the flow reads.
   *
   * Each anchor carries an outward normal, and the Bezier control points are
   * pushed along it, so a line leaves and arrives perpendicular to the side it
   * touches instead of clipping the corner.
   */
  function sideAnchor(box, side) {
    switch (side) {
      case "right":  return { x: box.x + box.w,     y: box.y + box.h / 2, nx: 1,  ny: 0 };
      case "left":   return { x: box.x,             y: box.y + box.h / 2, nx: -1, ny: 0 };
      case "bottom": return { x: box.x + box.w / 2, y: box.y + box.h,     nx: 0,  ny: 1 };
      default:       return { x: box.x + box.w / 2, y: box.y,             nx: 0,  ny: -1 };
    }
  }

  /** Which sides face each other, from the gaps between the two boxes. */
  function facingSides(s, t) {
    // Positive when the boxes are actually apart on that axis; negative when
    // their spans overlap. Comparing gaps rather than centre distance is what
    // makes two stacked, horizontally-overlapping boxes connect top-to-bottom.
    const gapX = Math.max(s.x - (t.x + t.w), t.x - (s.x + s.w));
    const gapY = Math.max(s.y - (t.y + t.h), t.y - (s.y + s.h));
    if (gapX >= gapY) {
      return t.x + t.w / 2 >= s.x + s.w / 2 ? ["right", "left"] : ["left", "right"];
    }
    return t.y + t.h / 2 >= s.y + s.h / 2 ? ["bottom", "top"] : ["top", "bottom"];
  }

  /** A self-edge, drawn as a loop off the top-right so it stays visible. */
  function selfLoopPath(box) {
    const x = box.x + box.w;
    const y = box.y + box.h / 2;
    const r = Math.max(26, box.h * 0.7);
    const topX = box.x + box.w * 0.72;
    return `M ${x} ${y} C ${x + r} ${y}, ${x + r} ${box.y - r}, ${topX} ${box.y}`;
  }

  function edgePath(e) {
    const s = positions.get(e.source);
    const t = positions.get(e.target);
    if (!s || !t) return null;
    if (e.source === e.target) return selfLoopPath(s);

    const [sourceSide, targetSide] = facingSides(s, t);
    const a1 = sideAnchor(s, sourceSide);
    const a2 = sideAnchor(t, targetSide);

    // Control-point reach scales with the span, clamped so short hops keep a
    // visible curve and long ones do not balloon across the canvas.
    const span = Math.hypot(a2.x - a1.x, a2.y - a1.y);
    const reach = Math.max(30, Math.min(120, span * 0.4));

    const c1x = a1.x + a1.nx * reach;
    const c1y = a1.y + a1.ny * reach;
    const c2x = a2.x + a2.nx * reach;
    const c2y = a2.y + a2.ny * reach;
    return `M ${a1.x} ${a1.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${a2.x} ${a2.y}`;
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
    selectedId = null;
    detailBox.classList.add("hidden");
    if (!data.nodes.length) {
      svg.innerHTML = "";
      emptyBox.classList.remove("hidden");
      contentBox = null;
      lastNodeIds = "";
      return;
    }
    emptyBox.classList.add("hidden");
    layout(data.nodes, data.edges);
    draw();
    // Refit only when the set of elements changes (new graph, add/remove
    // element) - not on annotate/connect/drag, so a hand-arranged view is kept.
    const ids = data.nodes.map((n) => n.id).sort().join("|");
    if (ids !== lastNodeIds && !suppressFitOnce) fit();
    suppressFitOnce = false;
    lastNodeIds = ids;
  }

  // Place a just-added element at a screen point (converted to graph coords) and
  // skip the next auto-fit so it stays where it was dropped.
  function placeNodeAt(id, clientX, clientY) {
    const pt = toSvgPoint(clientX, clientY);
    manualPositions.set(id, { x: Math.round(pt.x - 65), y: Math.round(pt.y - 22) });
    suppressFitOnce = true;
  }

  // Rebuild the SVG from `current` + `positions` (no layout, no fit). Also used
  // by drag, so a move repaints in place without re-running layout or refitting.
  function draw() {
    svg.innerHTML = "";
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
      // Wide transparent hit-area so the thin edge is easy to hover for its
      // meaning tooltip. Carries a native <title> as a fallback.
      const hit = svgEl("path", {
        d, class: "edge-hit", fill: "none",
        "data-source": e.source, "data-target": e.target, "data-kind": e.kind,
      }, edgeLayer);
      const meaning = EDGE_MEANINGS[e.kind];
      if (meaning) {
        svgEl("title", {}, hit).textContent = `${meaning.title} (${meaning.dir}) — ${meaning.body}`;
      }
    }

    for (const node of current.nodes) {
      const pos = positions.get(node.id);
      if (!pos) continue;
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
      // right-edge port: drag from here onto another node to connect them
      const port = svgEl("circle", {
        cx: pos.x + pos.w, cy: pos.y + pos.h / 2, r: 6, class: "port", "data-port": node.id,
      }, group);
      port.addEventListener("pointerdown", (ev) => startConnect(ev, node));
      // node body: drag to move, or click (no drag) to open the role popup
      group.addEventListener("pointerdown", (ev) => {
        if (ev.target.classList.contains("port")) return;
        ev.stopPropagation();
        startDrag(ev, node);
      });
    }

    const pad = 40;
    const xs = Array.from(positions.values());
    contentBox = {
      x: Math.min(...xs.map((p) => p.x)) - pad,
      y: Math.min(...xs.map((p) => p.y)) - pad,
      w: Math.max(...xs.map((p) => p.x + p.w)) - Math.min(...xs.map((p) => p.x)) + pad * 2,
      h: Math.max(...xs.map((p) => p.y + p.h)) - Math.min(...xs.map((p) => p.y)) + pad * 2,
    };
    paintHighlight();
  }

  function toSvgPoint(clientX, clientY) {
    const pt = new DOMPoint(clientX, clientY);
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  // Drag a node to reposition it (view-only; never edits the graph). A
  // pointerdown released without moving is treated as a click -> role popup.
  function startDrag(ev, node) {
    const startPt = toSvgPoint(ev.clientX, ev.clientY);
    const base = positions.get(node.id);
    const orig = { x: base.x, y: base.y };
    let moved = false;
    const move = (mv) => {
      const pt = toSvgPoint(mv.clientX, mv.clientY);
      const dx = pt.x - startPt.x;
      const dy = pt.y - startPt.y;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      detailBox.classList.add("hidden");
      const cur = positions.get(node.id);
      const next = { ...cur, x: Math.round(orig.x + dx), y: Math.round(orig.y + dy) };
      positions.set(node.id, next);
      manualPositions.set(node.id, { x: next.x, y: next.y });
      draw();
    };
    const up = (uv) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (!moved) { setHighlight([node.id]); selectedId = node.id; showDetail(node, uv); }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // BEAM flow triple for a connection dragged source -> target, or null if
  // invalid (resource -> resource has no direct BEAM flow).
  function edgeTriple(source, target) {
    const sp = source.kind === "process";
    const tp = target.kind === "process";
    if (!sp && tp) return { subject: target.id, predicate: "use", object: source.id };
    if (sp && !tp) return { subject: source.id, predicate: "produce", object: target.id };
    if (sp && tp) return { subject: source.id, predicate: "inform", object: target.id };
    return null;
  }

  function startConnect(ev, sourceNode) {
    ev.stopPropagation();
    const pos = positions.get(sourceNode.id);
    const temp = svgEl("path", { class: "edge temp", fill: "none" }, viewport);
    const sx = pos.x + pos.w;
    const sy = pos.y + pos.h / 2;
    const move = (mv) => {
      const pt = toSvgPoint(mv.clientX, mv.clientY);
      temp.setAttribute("d", `M ${sx} ${sy} L ${pt.x} ${pt.y}`);
    };
    const up = (uv) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      temp.remove();
      const hit = document.elementFromPoint(uv.clientX, uv.clientY);
      const group = hit && hit.closest ? hit.closest(".node") : null;
      if (!group || group.dataset.id === sourceNode.id) return;
      const target = current.nodes.find((n) => n.id === group.dataset.id);
      if (!target) return;
      // read the source's current kind (it may be stale after re-renders)
      const src = current.nodes.find((n) => n.id === sourceNode.id) || sourceNode;
      const triple = edgeTriple(src, target);
      if (!triple) {
        if (annotationCfg.onStatus) annotationCfg.onStatus("error", "Two resources can't connect directly — flow passes through a process.");
        return;
      }
      if (annotationCfg.onConnect) annotationCfg.onConnect(triple);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function paintHighlight() {
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

  function truncate(text, max) {
    return text.length > max ? text.slice(0, Math.max(1, max - 1)) + "…" : text;
  }

  // ---- element popover ------------------------------------------------------
  // Click a node -> highlight it -> edit its label / name / type / role / data
  // category here and Apply. onEdit delegates the write to the host (which calls
  // /api/graph-edit and updates the editor); onConnect handles port-drag edges.
  let annotationCfg = { vocabulary: { roles: [], dataCategories: [] }, classes: [], onEdit: null, onConnect: null, onDelete: null, onStatus: null };
  function setAnnotation(cfg) { annotationCfg = { ...annotationCfg, ...cfg }; }
  function escapeAttr(text) { return escape(text).replace(/"/g, "&quot;"); }

  function optionsHtml(items, placeholder, selectedId) {
    let html = `<option value="">${escape(placeholder)}</option>`;
    for (const item of items || []) {
      const selected = item.id === selectedId ? " selected" : "";
      html += `<option value="${escape(item.id)}"${selected}>${escape(item.label)}</option>`;
    }
    return html;
  }

  function positionDetail(ev) {
    if (!ev) return;
    const rect = wrap.getBoundingClientRect();
    const box = detailBox.getBoundingClientRect(); // popup is visible here, so real size
    const w = box.width || 300;
    const h = box.height || 240;
    let x = ev.clientX - rect.left + 12;
    let y = ev.clientY - rect.top + 12;
    x = Math.max(8, Math.min(x, wrap.clientWidth - w - 8));
    y = Math.max(8, Math.min(y, wrap.clientHeight - h - 8));
    detailBox.style.left = x + "px";
    detailBox.style.top = y + "px";
    detailBox.style.right = "auto";
    detailBox.style.bottom = "auto";
  }

  function showDetail(node, ev) {
    const currentClass = node.typeUri || "";
    detailBox.innerHTML = [
      `<h4>Element</h4>`,
      `<label class="detail-field"><span>Label</span>`,
      `<input id="nd-label" class="an-input" type="text" value="${escapeAttr(node.label || "")}"></label>`,
      `<label class="detail-field"><span>Name (id)</span>`,
      `<input id="nd-name" class="an-input" type="text" value="${escapeAttr(node.id.split(/[#/]/).pop())}"></label>`,
      `<label class="detail-field"><span>Type</span>`,
      `<select id="nd-type" class="an-select">${optionsHtml(annotationCfg.classes, "— type —", currentClass)}</select></label>`,
      `<div class="detail-field"><span>Roles</span><div id="nd-role-mp"></div></div>`,
      `<div class="detail-field"><span>Data categories</span><div id="nd-cat-mp"></div></div>`,
      `<div class="detail-actions">`,
      `<button type="button" class="btn small primary" id="nd-apply">Apply</button>`,
      `<button type="button" class="btn small danger" id="nd-delete" title="Delete (or press the Delete / Backspace key)">Delete</button>`,
      `</div>`,
    ].join("");
    // multi-value pickers: an element may carry several roles / data categories
    const rolePicker = MultiPicker(annotationCfg.vocabulary.roles, node.roleIds || [], {
      placeholder: "+ add role", grouped: true,
      filterKind: node.kind === "process" ? "process" : "resource",
    });
    const catPicker = MultiPicker(annotationCfg.vocabulary.dataCategories, node.categoryIds || [], { placeholder: "+ add data category" });
    detailBox.querySelector("#nd-role-mp").appendChild(rolePicker.element);
    detailBox.querySelector("#nd-cat-mp").appendChild(catPicker.element);
    detailBox.classList.remove("hidden");
    positionDetail(ev);
    detailBox.querySelector("#nd-apply").addEventListener("click", () => {
      if (!annotationCfg.onEdit) return;
      annotationCfg.onEdit(node.id, {
        label: detailBox.querySelector("#nd-label").value,
        name: detailBox.querySelector("#nd-name").value,
        classUri: detailBox.querySelector("#nd-type").value,
        roles: rolePicker.getValues(),
        categories: catPicker.getValues(),
      });
    });
    detailBox.querySelector("#nd-delete").addEventListener("click", () => {
      detailBox.classList.add("hidden");
      setHighlight([]);
      if (annotationCfg.onDelete) annotationCfg.onDelete(node.id);
    });
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
      if (ev.target.closest(".node") || ev.target.closest(".canvas-controls") || ev.target.closest(".node-detail") || ev.target.closest(".palette") || ev.target.closest(".motif-palette")) return;
      dragging = { x: ev.clientX, y: ev.clientY };
      wrap.setPointerCapture(ev.pointerId);
      detailBox.classList.add("hidden");
      setHighlight([]);
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
    selectedId = null;
    highlighted = new Set(ids || []);
    paintHighlight();
  }

  // Delete / Backspace removes the clicked element, unless focus is in a text
  // field (the code editor or a popup input) so typing is never hijacked.
  function onKeyDown(ev) {
    if (ev.key !== "Delete" && ev.key !== "Backspace") return;
    if (!selectedId || !annotationCfg.onDelete) return;
    const target = ev.target;
    if (target && target.matches && target.matches("input, textarea, select")) return;
    ev.preventDefault();
    const id = selectedId;
    detailBox.classList.add("hidden");
    setHighlight([]);
    annotationCfg.onDelete(id);
  }

  function clear() {
    current = { nodes: [], edges: [] };
    manualPositions = new Map();
    svg.innerHTML = "";
    contentBox = null;
    emptyBox.classList.remove("hidden");
    detailBox.classList.add("hidden");
  }

  // ---- edge hover tooltip ---------------------------------------------------
  function positionTip(ev) {
    const pad = 14;
    let x = ev.clientX + pad;
    let y = ev.clientY + pad;
    if (x + tipBox.offsetWidth > window.innerWidth - 8) x = ev.clientX - tipBox.offsetWidth - pad;
    if (y + tipBox.offsetHeight > window.innerHeight - 8) y = ev.clientY - tipBox.offsetHeight - pad;
    tipBox.style.left = `${Math.max(8, x)}px`;
    tipBox.style.top = `${Math.max(8, y)}px`;
  }

  function onEdgeOver(ev) {
    const hit = ev.target;
    if (!hit.classList || !hit.classList.contains("edge-hit")) return;
    const meaning = EDGE_MEANINGS[hit.getAttribute("data-kind")];
    if (!meaning) return;
    tipBox.innerHTML =
      `<span class="edge-tip-head"><strong>${meaning.title}</strong>` +
      `<span class="edge-tip-dir">${meaning.dir}</span></span>${meaning.body}`;
    tipBox.classList.remove("hidden");
    positionTip(ev);
  }

  function onEdgeMove(ev) {
    if (!tipBox.classList.contains("hidden")) positionTip(ev);
  }

  function onEdgeOut(ev) {
    if (ev.target.classList && ev.target.classList.contains("edge-hit")) {
      tipBox.classList.add("hidden");
    }
  }

  function init() {
    svg = document.getElementById("canvas");
    wrap = document.getElementById("canvas-wrap");
    detailBox = document.getElementById("node-detail");
    emptyBox = document.getElementById("canvas-empty");
    tipBox = document.createElement("div");
    tipBox.className = "edge-tip hidden";
    wrap.appendChild(tipBox);
    svg.addEventListener("pointerover", onEdgeOver);
    svg.addEventListener("pointermove", onEdgeMove);
    svg.addEventListener("pointerout", onEdgeOut);
    initPanZoom();
    applyView();
    window.addEventListener("resize", () => { if (contentBox) fit(); });
    document.addEventListener("keydown", onKeyDown);
  }

  /** Run the layered layout standalone (used by Draw mode's "From code"). */
  function layoutPositions(nodes, edges) {
    layout(nodes, edges);
    return new Map(positions);
  }

  // ---- SVG export -----------------------------------------------------------

  /* The canvas is already SVG, so exporting is not a re-render - it is making
   * the live element stand on its own. Three things stop a naive clone from
   * opening correctly in Inkscape, Illustrator, or a browser tab:
   *
   *   1. Every colour lives in style.css, referenced through CSS custom
   *      properties. Detached from the page there is no stylesheet and no
   *      :root, so an unmodified clone renders as black shapes on transparent.
   *   2. The viewport carries the current pan/zoom transform, so the file would
   *      capture whatever happened to be on screen rather than the whole graph.
   *   3. Interaction-only elements (transparent edge hit-targets, drag ports)
   *      are invisible but land in the file as stray shapes an editor shows.
   *
   * Rules are copied out of the live stylesheet rather than hardcoded here, so
   * a colour change in style.css reaches the export without anyone remembering
   * to update two places.
   */

  const EXPORT_STYLE_PREFIXES = [".edge", ".arrow", ".node", ".shape", "#viewport"];

  // Classes whose elements are removed from the export, plus transient UI
  // state. Their rules would be dead weight an SVG editor still lists.
  const EXPORT_STRIPPED_CLASSES = [
    "edge-hit", "port", "temp", "selected", "highlight", "node-detail", "edge-tip",
  ];

  function exportedStyleText() {
    const rulesText = [];
    for (const sheet of Array.from(document.styleSheets)) {
      let rules;
      try {
        rules = sheet.cssRules; // same-origin only; a cross-origin sheet throws
      } catch {
        continue;
      }
      for (const rule of Array.from(rules || [])) {
        if (!rule.selectorText || !rule.cssText) continue;
        // Interaction states cannot fire in a static file, and :hover would
        // otherwise override the base fill in some editors.
        if (/:(hover|active|focus)/.test(rule.selectorText)) continue;
        if (EXPORT_STRIPPED_CLASSES.some((cls) =>
          new RegExp(`\\.${cls}\\b`).test(rule.selectorText))) continue;
        const relevant = EXPORT_STYLE_PREFIXES.some((prefix) =>
          rule.selectorText.split(",").some((sel) => sel.trim().startsWith(prefix)));
        if (relevant) rulesText.push(rule.cssText);
      }
    }

    /* Resolve exactly the custom properties the kept rules reference, read off
     * the live :root. Deriving the list instead of hardcoding it is the point:
     * a hardcoded list silently goes stale the moment a rule starts using a new
     * variable, and the symptom is a shape that exports with no colour at all
     * rather than an error anyone would notice. */
    const root = getComputedStyle(document.documentElement);
    const referenced = new Set();
    for (const text of rulesText) {
      for (const match of text.matchAll(/var\((--[\w-]+)\)/g)) referenced.add(match[1]);
    }
    referenced.add("--canvas-bg"); // used by the background rect, not by a rule

    const resolved = Array.from(referenced)
      .sort()
      .map((name) => [name, root.getPropertyValue(name).trim()])
      .filter(([, value]) => value)
      .map(([name, value]) => `  ${name}: ${value};`);

    return [`:root {\n${resolved.join("\n")}\n}`, ...rulesText].join("\n");
  }

  /** Serialize the current graph as a standalone SVG document string. */
  function toSvgDocument() {
    if (!contentBox || !current.nodes.length) return null;

    const clone = svg.cloneNode(true);
    clone.removeAttribute("style");
    // Strip interaction-only elements and transient state.
    clone.querySelectorAll(".edge-hit, .port, .edge.temp").forEach((el) => el.remove());
    clone.querySelectorAll("[data-port]").forEach((el) => el.removeAttribute("data-port"));
    const clonedViewport = clone.querySelector("#viewport");
    if (clonedViewport) {
      // Export the whole graph, not the current pan/zoom.
      clonedViewport.removeAttribute("transform");
      clonedViewport.classList.remove("has-highlight");
    }

    const box = contentBox;
    clone.setAttribute("xmlns", SVG_NS);
    clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
    clone.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
    clone.setAttribute("width", Math.round(box.w));
    clone.setAttribute("height", Math.round(box.h));

    const style = document.createElementNS(SVG_NS, "style");
    style.textContent = exportedStyleText();
    clone.insertBefore(style, clone.firstChild);

    // Opaque background: the canvas is light in the app, and a transparent
    // export looks broken on any dark surface it is pasted onto.
    const bg = document.createElementNS(SVG_NS, "rect");
    const canvasBg = getComputedStyle(document.documentElement)
      .getPropertyValue("--canvas-bg").trim() || "#ffffff";
    bg.setAttribute("x", box.x);
    bg.setAttribute("y", box.y);
    bg.setAttribute("width", box.w);
    bg.setAttribute("height", box.h);
    bg.setAttribute("fill", canvasBg);
    clone.insertBefore(bg, style.nextSibling);

    const serialized = new XMLSerializer().serializeToString(clone);
    return `<?xml version="1.0" encoding="UTF-8"?>\n${serialized}`;
  }

  /** Download the current graph as an .svg file. Returns false if empty. */
  function exportSvg(filename = "architecture.svg") {
    const doc = toSvgDocument();
    if (!doc) return false;
    const blob = new Blob([doc], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Revoke on the next frame: revoking synchronously can cancel the download
    // in some browsers before it has read the blob.
    requestAnimationFrame(() => URL.revokeObjectURL(url));
    return true;
  }

  window.GraphView = {
    init, render, clear, setHighlight, fit, layoutPositions, setAnnotation, placeNodeAt,
    exportSvg, toSvgDocument,
  };
})();
