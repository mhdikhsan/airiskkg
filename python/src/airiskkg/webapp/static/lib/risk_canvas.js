const BAND_ORDER = ["business", "impact", "consequence", "context",
                    "risk", "source", "control", "system"];

const LAYER_OF_BAND = {
  business: "business",
  system: "architecture",
  context: "risk",
  impact: "risk", consequence: "risk", risk: "risk", source: "risk", control: "risk",
};

const BAND_STYLE = {
  business: { fill: "#eef2ff", stroke: "#4f46e5", chip: "Activity" },
  impact: { fill: "#fdecef", stroke: "#c2185b", chip: "Impact" },
  consequence: { fill: "#fdeef7", stroke: "#d81b8c", chip: "Consequence" },
  context: { fill: "#f4f6f9", stroke: "#5f6b7d", chip: "Context" },
  risk: { fill: "#fff6e6", stroke: "#e08800", chip: "Risk" },
  source: { fill: "#fff3e0", stroke: "#c77800", chip: "Risk Source" },
  control: { fill: "#eaf6ec", stroke: "#2e7d32", chip: "Risk Control" },
  system: { fill: "#e6f4ea", stroke: "#1f7a34", chip: "System" },
  // The lens: one risk in the middle, the work on one side, the build on the other.
  "lens-risk": { fill: "#fff1dc", stroke: "#d35400", chip: "Defined risk" },
  "lens-about": { fill: "#fff6e6", stroke: "#e08800", chip: "About it" },
  "lens-through": { fill: "#f3f4f6", stroke: "#9aa1af", chip: "Passes through" },
  "lens-control": { fill: "#eaf6ec", stroke: "#2e7d32", chip: "Risk Control" },
  "lens-proc": { fill: "#eef2ff", stroke: "#4f46e5", chip: "Process" },
  "lens-arch": { fill: "#fbe4ec", stroke: "#c2185b", chip: "Architecture" },
};

/* The four a person writes themselves. Marked, so a reader can tell their own
   assessment from the library's at a glance. */
const HAND_BANDS = new Set(["risk", "source", "consequence", "impact", "control"]);

const LENS_CHIP = {
  activity: "Activity", "data object": "Data object", "human step": "Human step",
  process: "Step", data: "Data", model: "Model", symbol: "Symbol", agent: "Agent",
};

const FLOW_STYLE = {
  process: { fill: "#fbe4ec", stroke: "#c2185b" },
  data: { fill: "#e6f4ea", stroke: "#2e7d32" },
  model: { fill: "#dbeafe", stroke: "#1d4ed8" },
  symbol: { fill: "#e8eaed", stroke: "#5f6368" },
  agent: { fill: "#f3e8fd", stroke: "#7b3fbf" },
  other: { fill: "#eceff1", stroke: "#78909c" },
};

const CARD_W = 210;
const CARD_MIN_H = 46;
const CARD_GAP_X = 16;
const BAND_GAP_Y = 26;
const FLOW_W = 180;
const FLOW_H = 52;
const FLOW_GAP_X = 34;
const FLOW_GAP_Y = 30;
const PAD = 40;

const SVG_NS = "http://www.w3.org/2000/svg";

export function createRiskCanvas() {
  let root = null;
  let svg = null;
  let surface = null;
  let onSelect = null;
  let onUnfold = null;
  let currentExpanded = new Set();
  let view = { x: 0, y: 0, k: 1 };
  let manualPositions = new Map();
  let selected = null;
  let pickedLink = null;
  let lastDraw = null;

  function make(tag, attrs = {}, text) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value !== null && value !== undefined) node.setAttribute(key, value);
    }
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /* Break at word boundaries; SVG has no wrapping of its own. */
  function wrap(text, width, size) {
    const words = String(text || "").split(/\s+/).filter(Boolean);
    const perLine = Math.max(8, Math.floor(width / (size * 0.55)));
    const lines = [];
    let line = "";
    for (const word of words) {
      if (!line.length) line = word;
      else if ((line + " " + word).length <= perLine) line += " " + word;
      else { lines.push(line); line = word; }
    }
    if (line) lines.push(line);
    return lines;
  }

  // ---- layout ----
  function layoutFlow(nodes, edges) {
    const ids = new Set(nodes.map((n) => n.id));
    const flow = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    const layer = new Map(nodes.map((n) => [n.id, 0]));
    for (let pass = 0; pass < nodes.length + 1; pass += 1) {
      let changed = false;
      for (const edge of flow) {
        const want = layer.get(edge.source) + 1;
        if (want > layer.get(edge.target) && want <= nodes.length) {
          layer.set(edge.target, want);
          changed = true;
        }
      }
      if (!changed) break;
    }
    const columns = new Map();
    for (const node of nodes) {
      const key = layer.get(node.id);
      if (!columns.has(key)) columns.set(key, []);
      columns.get(key).push(node);
    }
    const positions = new Map();
    [...columns.keys()].sort((a, b) => a - b).forEach((key) => {
      columns.get(key).forEach((node, index) => {
        positions.set(node.id, {
          x: key * (FLOW_W + FLOW_GAP_X),
          y: index * (FLOW_H + FLOW_GAP_Y),
          w: FLOW_W,
          h: FLOW_H,
          node,
        });
      });
    });
    return positions;
  }


  const showsBody = (entry) =>
    String(entry.band || "").startsWith("lens-") || entry.band === "source";


  function cardHeight(entry) {
    const titleLines = wrap(entry.title, CARD_W - 20, 12).length;
    const bodyLines = entry.body && showsBody(entry)
      ? Math.min(3, wrap(entry.body, CARD_W - 20, 10.5).length) : 0;
    return Math.max(CARD_MIN_H, (bodyLines ? 20 : 14) + titleLines * 15 + bodyLines * 13);
  }

 
  function spread(entries) {
    entries.sort((a, b) => a.x - b.x || a.id.localeCompare(b.id));
    let cursor = -Infinity;
    for (const entry of entries) {
      if (entry.x < cursor) entry.x = cursor;
      cursor = entry.x + CARD_W + CARD_GAP_X;
    }
  }


  function narrow(diagram, architecture, options) {
    const layers = options.layers || {};
    const on = (layer) => layers[layer] !== false;
    const focus = options.focus || null;
    const expanded = new Set(options.expanded || []);

    let nodes = diagram.nodes;
    if (focus) {
      const kept = new Set(
        nodes.filter((n) => n.band === "risk" && (n.systems || []).includes(focus))
          .map((n) => n.id));
      const chained = new Set();
      for (const link of diagram.links) {
        if (link.kind !== "chain") continue;
        if (kept.has(link.source)) chained.add(link.target);
        if (kept.has(link.target)) chained.add(link.source);
      }
      nodes = nodes.filter((n) =>
        kept.has(n.id) || chained.has(n.id)
        || (n.isSystem && n.id === focus)
        || (n.isActivity && (n.refines || []).includes(focus)));
    }
    nodes = nodes.filter((n) => on(LAYER_OF_BAND[n.band] || "risk"));

    const drawn = new Set(nodes.map((n) => n.id));
    const ownerOf = new Map();
    for (const system of architecture.systems || []) {
      for (const member of system.members || []) ownerOf.set(member, system.id);
    }

   
    let flowNodes = on("architecture")
      ? (architecture.nodes || []).filter((n) => {
        const owner = ownerOf.get(n.id);
        if (!owner) return !focus;
        return expanded.has(owner) && drawn.has(owner);
      })
      : [];
    const flowIds = new Set(flowNodes.map((n) => n.id));

    const nameOf = new Map();
    for (const node of architecture.nodes || []) nameOf.set(node.id, node.label || node.id);

    const links = [];
    const seen = new Set();
    const keep = (link) => {
      const key = `${link.source}|${link.target}|${link.kind}`;
      if (seen.has(key)) return;
      seen.add(key);
      links.push(link);
    };

    /* Every line into a system lands on its band, folded or not, and several
       land on the same spot. Drawn one per evidence element they were three
       quarters of the ink on the diagram and all of it said "where", not
       "what": a concern cites three to eight elements, so nine concerns drew
       seventy-four lines. They merge into one line that names what it stands
       for - deduplicating instead would report one attachment where the
       assessment found eight.

       The exception is the concern the reader picked. Unfolding a system is
       how you ask which element exactly, and a merged line stops at the band,
       so the selected concern keeps its own lines to the boxes it cites. */
    const rolled = new Map();
    for (const link of diagram.links) {
      if (!drawn.has(link.source)) continue;
      if (link.contains) continue;
      const owner = ownerOf.get(link.target);
      const asked = selected && (link.source === selected || link.target === selected);
      const there = drawn.has(link.target) || (flowIds.has(link.target) && asked);
      if (there) { keep(link); continue; }
      if (!owner || !drawn.has(owner)) continue;
      const key = `${link.source}|${owner}|${link.kind}`;
      if (!rolled.has(key)) {
        rolled.set(key, { link: { ...link, target: owner, rolledUp: true }, of: [] });
      }
      rolled.get(key).of.push(nameOf.get(link.target) || link.target);
    }
    for (const { link, of } of rolled.values()) {
      const names = [...new Set(of)].sort();
      keep({
        ...link,
        rolledUpOf: names,
        label: names.length > 2 ? `${names.length} elements` : names.join(", "),
      });
    }

    return {
      diagram: { ...diagram, nodes, links },
      architecture: {
        ...architecture,
        nodes: flowNodes,
        edges: (architecture.edges || []).filter(
          (e) => flowIds.has(e.source) && flowIds.has(e.target)),
      },
    };
  }


  const GROUP_PAD = 20;
  const GROUP_GAP = 52;
  const PART_COLS = 3;
  const BAND_COLS = 4;

  function median(values) {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = sorted.length >> 1;
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }


  function groupsOf(diagram, ownerOf) {
    const of = new Map();
    for (const entry of diagram.nodes) {
      if (entry.isSystem) of.set(entry.id, entry.id);
      else if ((entry.systems || []).length === 1) of.set(entry.id, entry.systems[0]);
      else if ((entry.refines || []).length === 1) of.set(entry.id, entry.refines[0]);
    }
    for (let pass = 0; pass < 4; pass += 1) {
      for (const link of diagram.links) {
        if (!of.has(link.source) && of.has(link.target)) of.set(link.source, of.get(link.target));
        else if (!of.has(link.target) && of.has(link.source)) of.set(link.target, of.get(link.source));
      }
    }
    for (const [member, owner] of ownerOf) of.set(member, owner);
    return of;
  }

  const SHARED_GROUP = "\u0000shared";

  function layoutDiagram(diagram, architecture) {
    const flow = layoutFlow(architecture.nodes || [], architecture.edges || []);
    const byId = new Map(diagram.nodes.map((n) => [n.id, n]));

    const ownerOf = new Map();
    for (const system of architecture.systems || []) {
      for (const member of system.members || []) {
        if (flow.has(member)) ownerOf.set(member, system.id);
      }
    }

    const neighbours = new Map();
    const join = (a, b) => {
      if (!neighbours.has(a)) neighbours.set(a, []);
      neighbours.get(a).push(b);
    };
    for (const link of diagram.links) {
      join(link.source, link.target);
      join(link.target, link.source);
    }

    const group = groupsOf(diagram, ownerOf);
    const columns = [];
    const byGroup = new Map();
    const slot = (key) => {
      if (!byGroup.has(key)) {
        byGroup.set(key, { key, bands: new Map(BAND_ORDER.map((b) => [b, []])), parts: [] });
        columns.push(byGroup.get(key));
      }
      return byGroup.get(key);
    };
  
    for (const entry of diagram.nodes) if (entry.isSystem) slot(entry.id);
    for (const entry of diagram.nodes) {
      slot(group.get(entry.id) || SHARED_GROUP).bands.get(entry.band).push({ ...entry });
    }
    for (const [id, at] of flow) {
      slot(ownerOf.get(id) || SHARED_GROUP).parts.push({ ...at, id, band: "flow" });
    }

    for (const column of columns) {
      const across = Math.min(Math.max(column.parts.length, 1), PART_COLS);
      const widest = Math.min(
        BAND_COLS,
        Math.max(1, ...BAND_ORDER.map((band) => column.bands.get(band).length)),
      );
      column.width = Math.max(
        widest * CARD_W + (widest - 1) * CARD_GAP_X,
        across * FLOW_W + (across - 1) * FLOW_GAP_X,
      );
    }
    let cursor = 0;
    for (const column of columns) {
      column.x = cursor;
      cursor += column.width + GROUP_GAP;
    }

    const placed = new Map();
    const orderBand = (rows) => {
      rows.forEach((row) => {
        const xs = (neighbours.get(row.id) || [])
          .map((id) => placed.get(id)).filter((x) => typeof x === "number");
        row.rank = median(xs);
      });
      rows.sort((a, b) => {
        if (a.rank === null && b.rank === null) return a.title.localeCompare(b.title);
        if (a.rank === null) return 1;
        if (b.rank === null) return -1;
        return a.rank - b.rank || a.title.localeCompare(b.title);
      });
    };

  
    for (let sweep = 0; sweep < 2; sweep += 1) {
      const order = sweep ? [...BAND_ORDER].reverse() : BAND_ORDER;
      for (const band of order) {
        for (const column of columns) {
          const rows = column.bands.get(band);
          if (!rows.length) continue;
          orderBand(rows);
          const across = Math.min(rows.length, BAND_COLS);
          const span = across * CARD_W + (across - 1) * CARD_GAP_X;
          const left = column.x + (column.width - span) / 2;
          rows.forEach((row, index) => {
            row.x = left + (index % BAND_COLS) * (CARD_W + CARD_GAP_X);
            row.line = Math.floor(index / BAND_COLS);
            row.w = CARD_W;
            row.h = cardHeight(row);
            placed.set(row.id, row.x + CARD_W / 2);
          });
        }
      }
    }


    let y = 0;
    for (const band of BAND_ORDER) {
      const rows = columns.flatMap((column) => column.bands.get(band));
      if (!rows.length) continue;
      const height = Math.max(...rows.map((row) => row.h));
      const lines = Math.max(...rows.map((row) => row.line || 0)) + 1;
      rows.forEach((row) => { row.y = y + (row.line || 0) * (height + BAND_GAP_Y); });
      y += lines * height + lines * BAND_GAP_Y;
    }

    const positions = new Map();
    for (const column of columns) {
  
      column.parts.sort((a, b) => a.x - b.x || a.id.localeCompare(b.id));
      const across = Math.min(Math.max(column.parts.length, 1), PART_COLS);
      const span = across * FLOW_W + (across - 1) * FLOW_GAP_X;
      column.parts.forEach((part, index) => {
        part.x = column.x + (column.width - span) / 2
          + (index % PART_COLS) * (FLOW_W + FLOW_GAP_X);
        part.y = y + Math.floor(index / PART_COLS) * (FLOW_H + FLOW_GAP_Y);
        part.w = FLOW_W;
        part.h = FLOW_H;
        positions.set(part.id, part);
      });
      for (const band of BAND_ORDER) {
        for (const row of column.bands.get(band)) positions.set(row.id, row);
      }
    }

    // Moved boxes first, so the frame is measured round where they now stand.
    for (const [id, at] of manualPositions) {
      const current = positions.get(id);
      if (current) positions.set(id, { ...current, x: at.x, y: at.y });
    }

    const frames = [];
    columns.forEach((column) => {
      if (column.key === SHARED_GROUP || !byId.has(column.key)) return;
      const held = [...BAND_ORDER.flatMap((band) => column.bands.get(band)), ...column.parts]
        .map((row) => positions.get(row.id) || row);
      if (!held.length) return;
      const left = Math.min(...held.map((row) => row.x));
      const right = Math.max(...held.map((row) => row.x + row.w));
      const top = Math.min(...held.map((row) => row.y));
      const bottom = Math.max(...held.map((row) => row.y + row.h));
      frames.push({
        id: column.key,
        index: frames.length,
        label: (byId.get(column.key) || {}).title || "",
        x: left - GROUP_PAD,
        y: top - GROUP_PAD - 16,
        w: right - left + GROUP_PAD * 2,
        h: bottom - top + GROUP_PAD * 2 + 16,
      });
    });

    return { positions, byId, flowIds: new Set(flow.keys()), frames };
  }


  // ---- the lens layout ----

  const LENS_COL_W = 240;
  const LENS_GAP_Y = 18;
  const LENS_X = { proc: 0, centre: 330, arch: 680 };

 
  function flowOrder(points, flow) {
    const ids = points.map((p) => p.id);
    const depth = new Map(ids.map((id) => [id, 0]));
    for (let pass = 0; pass < ids.length + 1; pass += 1) {
      let changed = false;
      for (const edge of flow) {
        if (!depth.has(edge.source) || !depth.has(edge.target)) continue;
        // A step that reads content sits below it; content a step writes sits below the step.
        const first = edge.kind === "use" ? edge.target : edge.source;
        const then = edge.kind === "use" ? edge.source : edge.target;
        const want = depth.get(first) + 1;
        if (want > depth.get(then) && want <= ids.length) { depth.set(then, want); changed = true; }
      }
      if (!changed) break;
    }
    return [...points].sort((a, b) => depth.get(a.id) - depth.get(b.id) || a.label.localeCompare(b.label));
  }

  function lensCard(id, band, title, body, x, extra = {}) {
    const entry = { id, band, title, body, x, w: LENS_COL_W, origin: "derived", ...extra };
    entry.h = Math.max(CARD_MIN_H, cardHeight(entry) - 6);
    return entry;
  }

  function stack(entries, top) {
    let y = top;
    for (const entry of entries) { entry.y = y; y += entry.h + LENS_GAP_Y; }
    return y;
  }

  function layoutLens(lens) {
    const links = [];
    const riskId = "lens:" + lens.risk.id;
    const criteria = [
      lens.risk.dataCategory ? "about " + lens.risk.dataCategory.label : null,
      lens.risk.system ? "in " + lens.risk.system.label : null,
      lens.risk.riskPattern ? "as " + lens.risk.riskPattern.label : null,
    ].filter(Boolean).join(" · ");
    const centre = [lensCard(riskId, "lens-risk", lens.risk.label, criteria, LENS_X.centre,
      { origin: "stated" })];

    for (const concern of lens.about) {
      const id = "about:" + concern.key;
      centre.push(lensCard(id, "lens-about", concern.label, concern.why[0] || null,
        LENS_X.centre, { status: concern.status, settled: concern.settled, key: concern.key }));
      links.push({ source: riskId, target: id, kind: "chain" });
      for (const element of concern.evidence) {
        links.push({ source: id, target: element.id, kind: "evidence" });
      }
    }
    if (lens.passesThrough.length) {
      const id = "through:" + lens.risk.id;
      centre.push(lensCard(id, "lens-through",
        lens.passesThrough.length + " more pass through it",
        "Their evidence touches this content, but none of them is about it.",
        LENS_X.centre));
      links.push({ source: riskId, target: id, kind: "chain" });
    }
    for (const control of lens.controls) {
      const id = "control:" + control;
      centre.push(lensCard(id, "lens-control", control, null, LENS_X.centre,
        { buildable: lens.buildable.includes(control) }));
      for (const concern of lens.about) {
        links.push({ source: "about:" + concern.key, target: id, kind: "chain" });
      }
    }

    const process = lens.process.map((point) => lensCard(point.id, "lens-proc", point.label,
      point.why, LENS_X.proc, { chip: LENS_CHIP[point.kind] || point.kind }));
    const architecture = flowOrder(lens.architecture, lens.flow).map((point) => lensCard(point.id,
      "lens-arch", point.label, point.why, LENS_X.arch, { chip: LENS_CHIP[point.kind] || point.kind }));
    for (const point of process) links.push({ source: riskId, target: point.id, kind: "lens-side" });
    for (const point of lens.process) {
      for (const key of point.concerns || []) {
        links.push({ source: point.id, target: "about:" + key, kind: "context" });
      }
    }
    for (const point of architecture) links.push({ source: riskId, target: point.id, kind: "lens-side" });
    for (const edge of lens.flow) links.push({ source: edge.source, target: edge.target, kind: "lens-flow" });

    const top = 40;
    stack(process, top);
    stack(centre, top);
    stack(architecture, top);

    const positions = new Map([...process, ...centre, ...architecture].map((n) => [n.id, n]));
    for (const [id, at] of manualPositions) {
      const current = positions.get(id);
      if (current) positions.set(id, { ...current, x: at.x, y: at.y });
    }
    const headers = [
      { x: LENS_X.proc, text: "In the process (" + process.length + ")" },
      { x: LENS_X.centre, text: "The risk" },
      { x: LENS_X.arch, text: "In the architecture (" + architecture.length + ")" },
    ];
    return { positions, links, headers };
  }

 
  function lensPath(from, to) {
    if (Math.abs(from.x - to.x) < 20) {
      // Out past the right edge, further for a longer hop: several links leaving
      // one card at the same offset stacked into a single unreadable bar.
      const x = from.x + from.w;
      const y1 = from.y + Math.min(from.h / 2, 20);
      const y2 = to.y + Math.min(to.h / 2, 20);
      const out = x + 14 + Math.min(70, Math.abs(y2 - y1) / 6);
      return "M" + x + "," + y1 + " C" + out + "," + y1 + " " + out + "," + y2 + " " + x + "," + y2;
    }
    const leftToRight = from.x < to.x;
    const x1 = leftToRight ? from.x + from.w : from.x;
    const x2 = leftToRight ? to.x : to.x + to.w;
    const y1 = from.y + Math.min(from.h / 2, 24);
    const y2 = to.y + Math.min(to.h / 2, 24);
    const mid = (x1 + x2) / 2;
    return "M" + x1 + "," + y1 + " C" + mid + "," + y1 + " " + mid + "," + y2 + " " + x2 + "," + y2;
  }

  // ---- drawing ----

  function drawCard(entry, layer, dimmed, positions) {
    const style = BAND_STYLE[entry.band];
    const chipText = entry.chip || style.chip;
    const group = make("g", {
      class: "rc-card" + (dimmed ? " dim" : "") + (selected === entry.id ? " sel" : ""),
      "data-node": entry.id,
      transform: `translate(${entry.x},${entry.y})`,
    });
    group.addEventListener("pointerdown", (event) => startDrag(event, entry.id, positions));

    // The type label the notation puts above every box.
    group.appendChild(make("text", { x: 2, y: -5, class: "rc-chip", fill: style.stroke }, chipText));

    /* Where this one is, when another box carries the same name. Opposite the
       type chip and above the box, so the notation keeps its type label and the
       card keeps its height. */
    if (entry.where) {
      group.appendChild(make("text", {
        x: entry.w - 2, y: -5, class: "rc-where", "text-anchor": "end",
      }, "at " + (entry.where.length > 22 ? entry.where.slice(0, 21) + "…" : entry.where)));
    }

    group.appendChild(make("rect", {
      class: "rc-box",
      width: entry.w, height: entry.h, rx: 3,
      fill: style.fill, stroke: style.stroke,
      "stroke-width": entry.origin === "stated" ? 2 : 1.2,
      // A person's claim and the library's are not the same kind of statement.
      "stroke-dasharray": entry.origin === "stated" ? "none" : "4 2",
    }));

    let cursor = 16;
    wrap(entry.title, entry.w - 20, 12).forEach((line) => {
      group.appendChild(make("text", { x: 10, y: cursor, class: "rc-title" }, line));
      cursor += 15;
    });
    if (entry.body && showsBody(entry)) {
      wrap(entry.body, entry.w - 20, 10.5).slice(0, 3).forEach((line) => {
        group.appendChild(make("text", { x: 10, y: cursor, class: "rc-body" }, line));
        cursor += 13;
      });
    }

   
    const marks = [];
    if (entry.origin === "stated" && HAND_BANDS.has(entry.band)) marks.push("by hand");
    if (entry.settled) marks.push(entry.status);
    if (marks.length) {
      group.appendChild(make("text", {
        x: entry.w - 10, y: entry.h - 7, class: "rc-mark", "text-anchor": "end",
        fill: style.stroke,
      }, marks.join(" · ")));
    }

   
    if (entry.isSystem && (entry.members || []).length) {
      const open = currentExpanded.has(entry.id);
      const handle = make("g", {
        class: "rc-unfold" + (open ? " open" : ""), "data-unfold": entry.id,
        transform: `translate(8,${entry.h - 16})`,
      });
      const text = `${open ? "▾" : "▸"} ${entry.members.length} parts`;
      handle.appendChild(make("rect", {
        class: "rc-unfold-box", width: 10 + text.length * 5.6, height: 14, rx: 7,
      }));
      handle.appendChild(make("text", { x: 6, y: 10.5, class: "rc-unfold-text" }, text));
      handle.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        if (onUnfold) onUnfold(entry.id, !open);
      });
      group.appendChild(handle);
    }
    layer.appendChild(group);
  }

  function drawFlowNode(entry, layer, highlighted, positions) {
    const style = FLOW_STYLE[entry.node.kind] || FLOW_STYLE.other;
    const group = make("g", {
      class: "rc-flow" + (highlighted ? " hit" : ""),
      "data-node": entry.id,
      transform: `translate(${entry.x},${entry.y})`,
    });
    group.addEventListener("pointerdown", (event) => startDrag(event, entry.id, positions));
    // What BEAM calls it, above the box, the way every other box on the
    // notation says what it is.
    const kind = entry.node.typeLabel || LENS_CHIP[entry.node.kind] || entry.node.kind;
    if (kind) {
      group.appendChild(make("text", { x: 2, y: -5, class: "rc-chip", fill: style.stroke }, kind));
    }
    group.appendChild(make("rect", {
      class: "rc-box",
      width: entry.w, height: entry.h, rx: 3,
      fill: style.fill, stroke: style.stroke,
      "stroke-width": highlighted ? 2.4 : 1.2,
    }));
    let cursor = 20;
    wrap(entry.node.label, entry.w - 16, 11.5).slice(0, 2).forEach((line) => {
      group.appendChild(make("text", { x: 8, y: cursor, class: "rc-flow-label" }, line));
      cursor += 14;
    });
    layer.appendChild(group);
  }

  function edgePath(from, to) {
    const x1 = from.x + from.w / 2;
    const y1 = from.y + from.h;
    const x2 = to.x + to.w / 2;
    const y2 = to.y;
    const mid = (y1 + y2) / 2;
    return `M${x1},${y1} C${x1},${mid} ${x2},${mid} ${x2},${y2}`;
  }

 
  let pendingFrame = 0;

  function redraw() {
    if (pendingFrame || !lastDraw) return;
    pendingFrame = requestAnimationFrame(() => {
      pendingFrame = 0;
      if (lastDraw.mode === "lens") canvas.renderLens(lastDraw.lens, { keepView: true });
      else canvas.render(lastDraw.diagram, lastDraw.architecture,
        { ...(lastDraw.options || {}), keepView: true });
    });
  }

  /* Screen point -> diagram coordinates, so a drag tracks the pointer at any zoom. */
  function toDiagram(clientX, clientY) {
    const rect = svg.getBoundingClientRect();
    return {
      x: (clientX - rect.left - view.x) / view.k,
      y: (clientY - rect.top - view.y) / view.k,
    };
  }


  function startDrag(event, id, positions) {
    event.stopPropagation();
    const base = positions.get(id);
    if (!base) return;
    const from = toDiagram(event.clientX, event.clientY);
    const origin = { x: base.x, y: base.y };
    let moved = false;

    const move = (ev) => {
      const at = toDiagram(ev.clientX, ev.clientY);
      const dx = at.x - from.x;
      const dy = at.y - from.y;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      manualPositions.set(id, {
        x: Math.round(origin.x + dx),
        y: Math.round(origin.y + dy),
      });
      redraw();
    };

    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      if (moved) return; // a move is a move, never also a selection
      selected = selected === id ? null : id;
      pickedLink = null;
      redraw();
      if (onSelect) onSelect(selected);
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  }

  const canvas = {
    init(selector, handlers = {}) {
      svg = document.querySelector(selector);
      onSelect = handlers.onSelect || null;
      onUnfold = handlers.onUnfold || null;
      if (!svg) return;
      surface = svg.parentElement || svg;
      svg.innerHTML = "";
      root = make("g", { id: "rc-root" });
      svg.appendChild(root);

  
      let panning = null;

      const panMove = (event) => {
        if (!panning) return;
        view.x += event.clientX - panning.x;
        view.y += event.clientY - panning.y;
        panning = { x: event.clientX, y: event.clientY };
        this.apply();
      };
      const panEnd = () => {
        panning = null;
        window.removeEventListener("pointermove", panMove);
        window.removeEventListener("pointerup", panEnd);
        window.removeEventListener("pointercancel", panEnd);
        window.removeEventListener("blur", panEnd);
      };

      surface.addEventListener("pointerdown", (event) => {
        if (event.target.closest("[data-node], .canvas-controls, button, .risk-tray")) return;
        panning = { x: event.clientX, y: event.clientY };
        window.addEventListener("pointermove", panMove);
        window.addEventListener("pointerup", panEnd);
        window.addEventListener("pointercancel", panEnd);
        window.addEventListener("blur", panEnd);
        if (selected !== null || pickedLink !== null) {
          selected = null;
          pickedLink = null;
          redraw();
          if (onSelect) onSelect(null);
        }
      });

      surface.addEventListener("wheel", (event) => {
        event.preventDefault();
        const rect = svg.getBoundingClientRect();
        const cx = event.clientX - rect.left;
        const cy = event.clientY - rect.top;
        const next = Math.min(2.5, Math.max(0.2, view.k * (event.deltaY < 0 ? 1.12 : 1 / 1.12)));
        const ratio = next / view.k;
        view.x = cx - (cx - view.x) * ratio;
        view.y = cy - (cy - view.y) * ratio;
        view.k = next;
        this.apply();
      }, { passive: false });
    },

    apply() {
      if (root) root.setAttribute("transform", `translate(${view.x},${view.y}) scale(${view.k})`);
    },

    clearSelection() {
      selected = null;
      pickedLink = null;
    },

    /* The line the reader picked, or null. */
    link() {
      return pickedLink;
    },

    forgetLayout() {
      manualPositions = new Map();
      selected = null;
    },

    selected() {
      return selected;
    },

    select(id) {
      selected = id || null;
      pickedLink = null;
      redraw();
    },

    render(diagram, architecture, options = {}) {
      if (!svg || !diagram) return;
      currentExpanded = new Set(options.expanded || []);
      const view = narrow(diagram, architecture || { nodes: [], edges: [] }, options);
      lastDraw = { mode: "notation", diagram, architecture, options };
      root.innerHTML = "";

      const { positions, flowIds, frames } = layoutDiagram(view.diagram, view.architecture);
      diagram = view.diagram;

      const related = new Set();
      if (selected) {
        related.add(selected);
        for (const link of diagram.links) {
          if (link.source === selected) related.add(link.target);
          if (link.target === selected) related.add(link.source);
        }
      }

      const frameLayer = make("g", {});
      const edgeLayer = make("g", { class: "rc-edges" });
      const nodeLayer = make("g", {});
      root.appendChild(frameLayer);
      root.appendChild(edgeLayer);
      root.appendChild(nodeLayer);

      for (const frame of frames || []) {
        const box = make("g", {
          class: `rc-frame s${frame.index % 4}`
            + (selected === frame.id ? " sel" : ""),
        });
        box.appendChild(make("rect", {
          class: "rc-frame-box", x: frame.x, y: frame.y,
          width: frame.w, height: frame.h, rx: 10,
        }));
        box.appendChild(make("text", {
          class: "rc-frame-label", x: frame.x + 12, y: frame.y + 16,
        }, frame.label));
        frameLayer.appendChild(box);
      }

      for (const link of diagram.links) {
        const from = positions.get(link.source);
        const to = positions.get(link.target);
        if (!from || !to) continue;
        const active = !selected || (related.has(link.source) && related.has(link.target));
        const d = edgePath(from, to);
        const picked = pickedLink
          && pickedLink.from === link.source && pickedLink.to === link.target;
        edgeLayer.appendChild(make("path", {
          d,
          class: `rc-link ${link.kind}` + (active ? "" : " dim") + (picked ? " picked" : ""),
          fill: "none",
        }));
        if (link.label) {
          edgeLayer.appendChild(make("text", {
            x: (from.x + from.w / 2 + to.x + to.w / 2) / 2,
            y: (from.y + from.h + to.y) / 2 + 3,
            class: "rc-edge-label" + (active ? "" : " dim"),
            "text-anchor": "middle",
          }, link.label));
        }
        if (!link.editable) continue;
        const hit = make("path", {
          d, class: "rc-link-hit", fill: "none",
          "data-from": link.source, "data-to": link.target,
        });
        hit.addEventListener("pointerdown", (event) => {
          event.stopPropagation();
          selected = null;
          pickedLink = { from: link.source, to: link.target, label: link.label || link.kind };
          if (onSelect) onSelect(null);
          redraw();
        });
        edgeLayer.appendChild(hit);
      }

      for (const entry of positions.values()) {
        if (entry.band === "flow") drawFlowNode(entry, nodeLayer, related.has(entry.id), positions);
        else drawCard(entry, nodeLayer, selected && !related.has(entry.id), positions);
      }
      // Refitting mid-gesture would slide the diagram out from under the pointer.
      if (!options.keepView) this.fit();
    },

    renderLens(lens, options = {}) {
      if (!svg || !lens) return;
      lastDraw = { mode: "lens", lens };
      root.innerHTML = "";
      const { positions, links, headers } = layoutLens(lens);

      const related = new Set();
      if (selected) {
        related.add(selected);
        for (const link of links) {
          if (link.source === selected) related.add(link.target);
          if (link.target === selected) related.add(link.source);
        }
      }

      const headLayer = make("g", {});
      const edgeLayer = make("g", { class: "rc-edges" });
      const nodeLayer = make("g", {});
      root.appendChild(headLayer);
      root.appendChild(edgeLayer);
      root.appendChild(nodeLayer);

      for (const head of headers) {
        headLayer.appendChild(make("text", { x: head.x, y: 16, class: "rc-lens-head" }, head.text));
      }
      for (const link of links) {
        const from = positions.get(link.source);
        const to = positions.get(link.target);
        if (!from || !to) continue;
        const active = !selected || (related.has(link.source) && related.has(link.target));
        // Drawn for the pick only: at rest they would be a wall of lines.
        if (link.kind === "context" && !(selected && active)) continue;
        edgeLayer.appendChild(make("path", {
          d: lensPath(from, to),
          class: "rc-link " + link.kind + (active ? "" : " dim"),
          fill: "none",
        }));
      }
      for (const entry of positions.values()) {
        drawCard(entry, nodeLayer, selected && !related.has(entry.id), positions);
      }
      if (!options.keepView) this.fit();
    },

    mode() {
      return lastDraw ? lastDraw.mode : null;
    },

    painted() {
      return !!root && !!root.querySelector(".rc-card, .rc-flow");
    },

    clear() {
      if (root) root.innerHTML = "";
      lastDraw = null;
    },

    fit() {
      if (!svg || !root) return;
      const box = root.getBBox ? root.getBBox() : null;
      if (!box || !box.width) return;
      const rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      const left = Math.min(trayInset("#risk-tools"), rect.width * 0.3);
      const right = Math.min(trayInset("#risk-side-tray"), rect.width * 0.3);
      const usable = Math.max(rect.width - left - right, 220);
      const k = Math.min(1.2, (usable - PAD) / box.width, (rect.height - PAD) / box.height);
      view.k = Math.max(0.42, k > 0 ? k : 1);
      view.x = left + Math.max(0, (usable - box.width * view.k) / 2) - box.x * view.k;
      view.y = Math.max(PAD / 2, (rect.height - box.height * view.k) / 2) - box.y * view.k;
      this.apply();
    },

    zoom(factor) {
      view.k = Math.min(2.5, Math.max(0.2, view.k * factor));
      this.apply();
    },
  };
  return canvas;
}

function trayInset(selector) {
  const tray = document.querySelector(selector);
  if (!tray || tray.classList.contains("hidden")) return 0;
  const width = tray.getBoundingClientRect().width;
  return width ? width + 18 : 0;
}

export const RiskCanvas = createRiskCanvas();
