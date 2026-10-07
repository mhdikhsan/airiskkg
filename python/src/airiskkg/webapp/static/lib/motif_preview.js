/* A motif drawn from its declaration, not from a graph. */

const SVG_NS = "http://www.w3.org/2000/svg";

const NODE_W = 128;
const NODE_H = 40;
const COL_GAP = 62;
const ROW_GAP = 16;
const PAD = 14;

// Several previews share one document, and a duplicated marker id would make
// every arrow resolve to whichever SVG parsed first.
let markerSeq = 0;

const KIND_OF = {
  Data: "data",
  StatisticalModel: "model",
  SemanticModel: "model",
  Model: "model",
  Symbol: "symbol",
  Agent: "agent",
  Resource: "resource",
  Process: "process",
  Infer: "process",
  Transform: "process",
  Train: "process",
  Generate: "process",
};

// Process is named, never assumed: a fallback of "process" drew the one
// beam:Resource node in the library (External Dependency) as a step, so its
// `step beam:use resource` edge read as process to process.
// The box side of the graph shares one silhouette, whatever its colour.
const RESOURCE_SIDE = new Set(["data", "symbol", "resource"]);

export function kindOf(cls) {
  return KIND_OF[cls] || "other";
}

function svgEl(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

/* Declared edges are (process, predicate, other). Drawn edges are whichever way
 * the thing moves, which for `use` is the other way round. */
function drawnEdges(edges) {
  return edges.map(([source, kind, target]) =>
    (kind === "use" ? { from: target, to: source, kind } : { from: source, to: target, kind }));
}

function assignLayers(nodes, edges) {
  const incoming = new Map(nodes.map((n) => [n.key, []]));
  edges.forEach((e) => {
    if (incoming.has(e.to) && incoming.has(e.from)) incoming.get(e.to).push(e.from);
  });
  const depth = new Map();
  // A motif may hold a loop (memory written then read), so the walk carries its
  // own trail rather than trusting the declaration to be acyclic.
  const walk = (key, trail) => {
    if (depth.has(key)) return depth.get(key);
    if (trail.has(key)) return 0;
    trail.add(key);
    const parents = incoming.get(key) || [];
    const value = parents.length
      ? Math.max(...parents.map((p) => walk(p, trail) + 1))
      : 0;
    trail.delete(key);
    depth.set(key, value);
    return value;
  };
  nodes.forEach((n) => walk(n.key, new Set()));
  return depth;
}

/* Two lines rather than an ellipsis: "Query Reformulati…" reads as a different
 * step from the one it is, and the box has the room. */
function wrap(text, max) {
  const words = text.split(/\s+/);
  const lines = [];
  words.forEach((word) => {
    const last = lines[lines.length - 1];
    if (last && (last + " " + word).length <= max) lines[lines.length - 1] = last + " " + word;
    else lines.push(word);
  });
  if (lines.length <= 2) return lines;
  return [lines[0], lines.slice(1).join(" ")];
}

function shapeFor(group, node, box) {
  const common = { class: `shape ${node.kind}` };
  if (node.kind === "model") {
    const c = 10;
    const points = [
      [box.x + c, box.y], [box.x + box.w - c, box.y], [box.x + box.w, box.y + box.h / 2],
      [box.x + box.w - c, box.y + box.h], [box.x + c, box.y + box.h], [box.x, box.y + box.h / 2],
    ].map((p) => p.join(",")).join(" ");
    svgEl("polygon", { ...common, points }, group);
  } else if (node.kind === "agent") {
    svgEl("ellipse", {
      ...common,
      cx: box.x + box.w / 2, cy: box.y + box.h / 2, rx: box.w / 2, ry: box.h / 2,
    }, group);
  } else {
    const rx = RESOURCE_SIDE.has(node.kind) ? 13 : 4;
    svgEl("rect", { ...common, x: box.x, y: box.y, width: box.w, height: box.h, rx }, group);
  }
}

function anchors(from, to) {
  // Left/right when the layers differ, top/bottom when they do not.
  if (Math.abs(from.x - to.x) > 4) {
    const forward = from.x < to.x;
    return [
      { x: forward ? from.x + from.w : from.x, y: from.y + from.h / 2 },
      { x: forward ? to.x : to.x + to.w, y: to.y + to.h / 2 },
    ];
  }
  const down = from.y < to.y;
  return [
    { x: from.x + from.w / 2, y: down ? from.y + from.h : from.y },
    { x: to.x + to.w / 2, y: down ? to.y : to.y + to.h },
  ];
}

/* `highlight` names roles; a node playing one is marked, so a page about one
 * term can show where that term sits inside each structure that reads it. */
export function motifPreview(template, options = {}) {
  const highlight = new Set(options.highlight || []);
  const nodes = (template.nodes || []).map((n) => ({ ...n, kind: kindOf(n.cls) }));
  const svg = svgEl("svg", { class: "motif-preview", xmlns: SVG_NS });
  if (!nodes.length) return svg;

  const edges = drawnEdges(template.edges || []);
  const depth = assignLayers(nodes, edges);

  const columns = new Map();
  nodes.forEach((n) => {
    const layer = depth.get(n.key) || 0;
    if (!columns.has(layer)) columns.set(layer, []);
    columns.get(layer).push(n);
  });
  const order = [...columns.keys()].sort((a, b) => a - b);
  const tallest = Math.max(...order.map((k) => columns.get(k).length));
  const height = tallest * NODE_H + (tallest - 1) * ROW_GAP + PAD * 2;
  const width = order.length * NODE_W + (order.length - 1) * COL_GAP + PAD * 2;

  const boxes = new Map();
  order.forEach((layer, column) => {
    const members = columns.get(layer);
    const span = members.length * NODE_H + (members.length - 1) * ROW_GAP;
    members.forEach((node, row) => {
      boxes.set(node.key, {
        x: PAD + column * (NODE_W + COL_GAP),
        y: (height - span) / 2 + row * (NODE_H + ROW_GAP),
        w: NODE_W,
        h: NODE_H,
      });
    });
  });

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  /* Its natural size, so a four-node motif is not blown up to fill the card
   * and a nine-node one keeps its labels readable. CSS shrinks it to fit. */
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);

  const arrowId = `mp-arrow-${++markerSeq}`;
  const defs = svgEl("defs", {}, svg);
  const marker = svgEl("marker", {
    id: arrowId, viewBox: "0 0 10 10", refX: "9", refY: "5",
    markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse",
  }, defs);
  svgEl("path", { d: "M 0 1 L 9 5 L 0 9 z", class: "mp-arrowhead" }, marker);

  const edgeLayer = svgEl("g", {}, svg);
  edges.forEach((edge) => {
    const from = boxes.get(edge.from);
    const to = boxes.get(edge.to);
    if (!from || !to) return;
    const [a, b] = anchors(from, to);
    svgEl("line", {
      class: `edge ${edge.kind}`, x1: a.x, y1: a.y, x2: b.x, y2: b.y,
      "marker-end": `url(#${arrowId})`,
    }, edgeLayer);
  });

  nodes.forEach((node) => {
    const box = boxes.get(node.key);
    const marked = (node.roles || []).some((role) => highlight.has(role));
    const group = svgEl("g", marked ? { class: "mp-hl" } : {}, svg);
    shapeFor(group, node, box);
    const lines = wrap(node.label, 17);
    const top = box.y + box.h / 2 + 4 - (lines.length - 1) * 6;
    const text = svgEl("text", {
      class: "mp-label", x: box.x + box.w / 2, y: top, "text-anchor": "middle",
    }, group);
    lines.forEach((line, index) => {
      const span = svgEl("tspan", {
        x: box.x + box.w / 2, dy: index ? 12 : 0,
      }, text);
      span.textContent = line;
    });
    svgEl("title", {}, group).textContent = `${node.label} — ${node.cls}`
      + (node.roles && node.roles.length ? ` · plays ${node.roles.join(", ")}` : "")
      // What the declaration calls this node, when the role says something else.
      + (node.note ? ` · declared as ${node.note}` : "");
  });
  return svg;
}
