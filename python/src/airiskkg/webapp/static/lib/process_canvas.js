/* The business layer, drawn as BPMN 2.0 draws it: pools banded into lanes,
 * events, gateways, activities with their type and loop markers, sequence flow
 * routed from the model rather than from where a box happened to land, message
 * flow across pools, data objects with their classification, and text
 * annotations. Restricted to what external/sbpmn/sbpmn_2.0.ttl can express.
 * A separate surface from graph_view.js, not a second mode of it. */

const SVG_NS = "http://www.w3.org/2000/svg";

const POOL_LABEL_W = 30;
const LANE_LABEL_W = 24;
const POOL_PAD = 16;
const BOX_W = 212;
const BOX_H = 64;
const EVENT_R = 18;
const GATE_R = 22;
const COL_GAP = 48;
const BRANCH_GAP = 62;   // extra room after a gateway, for the branch labels
const ROW_GAP = 22;
const POOL_GAP = 30;
const COLLAPSED_H = 46;  // a black-box pool: the band and its name, nothing inside
const LINE_H = 14;
const DATA_W = 30;
const DATA_H = 36;
const DATA_BAND = 92;
const NOTE_W = 150;
const RISK_ROW_H = 17;
const CHILD_H = 30;

let svg = null;
let root = null;
let data = null;
let index = null;             // id -> normalised flow node, built per render
let expanded = new Set();
let onOpenArchitecture = null;
let onEdit = null;
let onSelect = null;
/* Which connector the reader has picked, by its flow IRI. View state: picking
   a line changes nothing in the model until they say so. */
let pickedFlow = null;
/* Where the picked connector's remove badge goes, filled while the connectors
   are drawn and painted once everything else is down. */
let pendingBadge = null;
let systems = [];
let dataClasses = [];
let selectedPool = null;
let selectedLane = null;      // where a new node lands inside a banded pool
let connecting = null;
let swallowNextClick = false;
let findingsByActivity = new Map();
let openRisks = new Set();
let view = { x: 0, y: 0, k: 1 };
let paletteFolded = false;
let paletteTouched = false;       // once the reader chooses, the choice sticks
let collapsedPools = new Set();   // BPMN black-box pools: banded, not opened
/* Where a reader has put a box by hand. View-only, like the architecture
   canvas: the process model is the source, and a moved box is a reading aid,
   never an edit. Keyed by node id, so a layout survives a re-render. */
let manualPositions = new Map();
/* The structure the view was last fitted to. A redraw of the same model keeps
   the reader's pan and zoom; only a changed structure refits. Refitting on
   every redraw is what snapped the view back each time a lane, a pool or a
   risk badge was clicked. */
let lastFitIds = null;
let pendingFrame = 0;

function node(tag, attrs = {}, parent = null) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined) element.setAttribute(key, value);
  }
  if (parent) parent.appendChild(element);
  return element;
}

function text(parent, x, y, value, cls) {
  const element = node("text", { x, y, class: cls }, parent);
  element.textContent = value;
  return element;
}

function centred(parent, x, y, value, cls) {
  const element = text(parent, x, y, value, cls);
  element.setAttribute("text-anchor", "middle");
  return element;
}

function truncate(value, max) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

/* Wrap on words instead of cutting; the full text goes on the <title> anyway. */
function wrap(value, max, maxLines) {
  const words = String(value || "").split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  words.forEach((word) => {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length <= max || !line) { line = candidate; return; }
    lines.push(line);
    line = word;
  });
  if (line) lines.push(line);
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  kept[maxLines - 1] = truncate(`${kept[maxLines - 1]} ${lines.slice(maxLines).join(" ")}`, max);
  return kept;
}

/* dpv:PersonalData reads as "Personal data" to someone who does not write RDF;
 * the prefixed form stays on the tooltip. */
export function humanKind(kind) {
  const local = String(kind).split(/[#:/]/).pop();
  const spaced = local.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

function dataOf(activity) {
  if (!activity.reads) return [];
  return [
    ...activity.reads.map((d) => ({ ...d, direction: "in" })),
    ...activity.writes.map((d) => ({ ...d, direction: "out" })),
  ];
}

function riskOf(item) {
  return findingsByActivity.get(item.id) || null;
}

/** Every flow node of the model in one table, tagged with how it is drawn. */
function buildIndex(model) {
  const table = new Map();
  (model.activities || []).forEach((a) => table.set(a.id, { ...a, shape: "activity" }));
  (model.events || []).forEach((e) => table.set(e.id, { ...e, shape: "event" }));
  (model.gateways || []).forEach((g) => table.set(g.id, { ...g, shape: "gateway" }));
  return table;
}

function nameRoomOf(activity) {
  return riskOf(activity) && riskOf(activity).findings ? 19 : 28;
}

function headHeight(activity) {
  const lines = wrap(activity.label, nameRoomOf(activity), 2).length;
  return BOX_H + (lines - 1) * LINE_H;
}

/* An event is 36px wide and its name is not. Sizing a column by the shape
 * alone put "The customer has an answer" outside the pool it belongs to. */
function footprintOf(item) {
  const { w } = sizeOf(item);
  if (item.shape === "activity" || !item.label) return w;
  const longest = Math.max(...wrap(item.label, 18, 2).map((line) => line.length));
  return Math.max(w, longest * 5.6);
}

function sizeOf(item) {
  if (item.shape === "event") return { w: EVENT_R * 2, h: EVENT_R * 2 };
  if (item.shape === "gateway") return { w: GATE_R * 2, h: GATE_R * 2 };
  let h = headHeight(item);
  if (expanded.has(item.id) && item.children.length) {
    h += item.children.length * CHILD_H + 10;
  }
  const risk = riskOf(item);
  if (risk && openRisks.has(item.id)) h += risk.items.length * RISK_ROW_H + 12;
  return { w: BOX_W, h };
}

/* Longest-path layering over sequence flow. A cycle - a rework loop - leaves
 * nodes that Kahn never reaches; they are placed after the latest predecessor
 * that was reached, so the loop draws as a backward edge instead of hanging. */
function rankNodes(ids, edges) {
  const succ = new Map(ids.map((id) => [id, []]));
  const pred = new Map(ids.map((id) => [id, []]));
  const indegree = new Map(ids.map((id) => [id, 0]));
  edges.forEach(([source, target]) => {
    if (!succ.has(source) || !indegree.has(target)) return;
    succ.get(source).push(target);
    pred.get(target).push(source);
    indegree.set(target, indegree.get(target) + 1);
  });

  const rank = new Map(ids.map((id) => [id, 0]));
  const depth = new Map(ids.map((id) => [id, 0]));
  const queue = ids.filter((id) => indegree.get(id) === 0);
  const settled = new Set(queue);
  while (queue.length) {
    const current = queue.shift();
    succ.get(current).forEach((next) => {
      rank.set(next, Math.max(rank.get(next), rank.get(current) + 1));
      indegree.set(next, indegree.get(next) - 1);
      if (indegree.get(next) === 0 && !settled.has(next)) {
        settled.add(next);
        queue.push(next);
      }
    });
  }
  ids.filter((id) => !settled.has(id)).forEach((id) => {
    const reached = pred.get(id).filter((p) => settled.has(p)).map((p) => rank.get(p));
    rank.set(id, reached.length ? Math.max(...reached) + 1 : 0);
    settled.add(id);
  });

  // How much process is left after each node. Walked back from the deepest
  // rank, so a successor is always settled before the node that reaches it.
  [...ids].sort((a, b) => rank.get(b) - rank.get(a)).forEach((id) => {
    const onward = succ.get(id).filter((n) => rank.get(n) > rank.get(id)).map((n) => depth.get(n));
    depth.set(id, onward.length ? Math.max(...onward) + 1 : 0);
  });

  return { rank, pred, depth };
}

/** Lanes of one process, in the order the modeller declared them. */
function lanesOf(model, processId) {
  const bands = (model.lanes || []).filter((lane) => lane.process === processId);
  /* Declaration order, and nothing else. */
  bands.sort((a, b) => (a.line ?? Infinity) - (b.line ?? Infinity)
    || a.id.localeCompare(b.id, undefined, { numeric: true }));
  return bands;
}

/* One row per branch: a node sits on its predecessor's row when that row is
 * free at this column, so a straight chain stays straight and only a split
 * steps down. Which branch keeps the row is not arbitrary - a default flow is
 * the exception by definition, and an end event terminates one path rather
 * than continuing the process, so both step off and the main line runs
 * straight, and of the rest the branch with the most process still ahead of it
 * keeps the row. Ordered by id alone, the tariff diagram put "another request"
 * on the main row and pushed the tariff change itself down a row. */
function assignRows(members, rank, pred, laneOf, aside, depth) {
  const taken = new Set();
  const row = new Map();
  [...members].sort((a, b) =>
    (rank.get(a) - rank.get(b))
    || (aside.has(a) - aside.has(b))
    || (depth.get(b) - depth.get(a))
    || a.localeCompare(b))
    .forEach((id) => {
      const sameLane = pred.get(id).filter((p) => laneOf.get(p) === laneOf.get(id));
      const preferred = sameLane.length ? Math.min(...sameLane.map((p) => row.get(p) ?? 0)) : 0;
      let slot = Math.max(0, preferred);
      while (taken.has(`${rank.get(id)}:${slot}`)) slot += 1;
      taken.add(`${rank.get(id)}:${slot}`);
      row.set(id, slot);
    });
  return row;
}

function layout() {
  const pools = [];
  const placed = new Map();
  const notes = [];
  const flows = data.sequenceFlows || [];
  let poolY = POOL_PAD;

  data.participants.forEach((participant) => {
    const members = [...index.values()].filter(
      (item) => !item.parent && !item.attachedTo && item.process
        && item.process === participant.process
    );

    /* A collapsed pool is BPMN's black box: the band and its name, nothing inside. */
    if (collapsedPools.has(participant.id)) {
      const band = {
        x: 0, y: poolY, w: POOL_LABEL_W + LANE_LABEL_W + BOX_W + POOL_PAD * 2, h: COLLAPSED_H,
      };
      /* Each member gets a slice of the band rather than all of it. */
      const usable = band.w - POOL_LABEL_W - POOL_PAD;
      const slice = members.length ? usable / members.length : usable;
      members.forEach((item, seat) => {
        placed.set(item.id, {
          x: POOL_LABEL_W + slice * seat, y: band.y, w: slice, h: band.h,
          item, band: 0, head: band.h,
        });
      });
      pools.push({
        participant, ...band, lanes: [], members, showLanes: false, collapsed: true,
      });
      poolY += COLLAPSED_H + POOL_GAP;
      return;
    }
    const ids = members.map((m) => m.id);
    const inPool = new Set(ids);
    const edges = flows
      .filter((f) => inPool.has(f.source) && inPool.has(f.target))
      .map((f) => [f.source, f.target]);
    const { rank, pred, depth } = rankNodes(ids, edges);

    // Column widths: an event or a gateway must not force an activity's width.
    const columns = new Map();
    members.forEach((item) => {
      const at = rank.get(item.id);
      columns.set(at, Math.max(columns.get(at) || 0, footprintOf(item)));
    });
    /* A column that a gateway branches out of needs a wider gap after it: every
     * branch turns in that gap, and the labels saying which branch is which go
     * beside those turns. Sized like every other column rather than by nudging
     * the whole diagram apart. */
    const branching = new Set(
      members.filter((item) => item.shape === "gateway"
        && flows.filter((f) => f.source === item.id).length > 1)
        .map((item) => rank.get(item.id))
    );
    const columnX = new Map();
    let cursor = POOL_LABEL_W + LANE_LABEL_W + POOL_PAD;
    let lastGap = 0;
    [...columns.keys()].sort((a, b) => a - b).forEach((at) => {
      columnX.set(at, cursor);
      lastGap = COL_GAP + (branching.has(at) ? BRANCH_GAP : 0);
      cursor += columns.get(at) + lastGap;
    });
    let poolW = Math.max(cursor - lastGap + POOL_PAD,
      POOL_LABEL_W + LANE_LABEL_W + BOX_W + POOL_PAD * 2);
    let rightmost = 0;

    // The branches that give up the main row: the default flow's target, and a
    // path that only ends.
    const aside = new Set([
      ...flows.filter((f) => f.default && inPool.has(f.target)).map((f) => f.target),
      ...ids.filter((id) => {
        const item = index.get(id);
        return item.shape === "event" && item.kind === "endEvent";
      }),
    ]);

    // Every node lands in a band. A process with no lanes gets one unnamed
    // band, so the rest of the layout does not need a second code path.
    const declared = lanesOf(data, participant.process);
    const laneOf = new Map();
    members.forEach((item) => {
      const band = declared.find((lane) => lane.id === item.laneId);
      laneOf.set(item.id, band ? band.id : "");
    });
    /* Every declared lane is drawn, empty or not. */
    const bands = [...declared];
    const loose = ids.filter((id) => laneOf.get(id) === "");
    if (loose.length || !bands.length) {
      bands.push({ id: "", label: bands.length ? "Other" : "", members: loose, implicit: true });
    }

    const noteOf = new Map();
    (data.associations || []).forEach((link) => {
      const note = (data.artifacts || []).find(
        (a) => a.kind === "textAnnotation" && (a.id === link.target || a.id === link.source));
      const anchor = note && (note.id === link.target ? link.source : link.target);
      if (note && inPool.has(anchor)) noteOf.set(note.id, anchor);
    });

    let laneY = poolY + POOL_PAD;
    const drawnBands = [];
    bands.forEach((band) => {
      const mine = ids.filter((id) => laneOf.get(id) === band.id);
      const row = assignRows(mine, rank, pred, laneOf, aside, depth);
      const noteRow = Math.max(-1, ...mine.map((id) => row.get(id))) + 1;
      const attached = [...noteOf.entries()].filter(([, anchor]) => mine.includes(anchor));

      const rowHeight = new Map();
      const rowBand = new Map();
      mine.forEach((id) => {
        const item = index.get(id);
        const at = row.get(id);
        rowHeight.set(at, Math.max(rowHeight.get(at) || 0, sizeOf(item).h));
        if (dataOf(item).length) rowBand.set(at, DATA_BAND);
      });
      if (attached.length) rowHeight.set(noteRow, 54);

      const rowY = new Map();
      let stack = laneY + POOL_PAD / 2;
      [...rowHeight.keys()].sort((a, b) => a - b).forEach((at) => {
        stack += rowBand.get(at) || 0;
        rowY.set(at, stack);
        stack += rowHeight.get(at) + ROW_GAP;
      });
      let laneH = Math.max(stack - ROW_GAP + POOL_PAD / 2 - laneY, BOX_H + POOL_PAD);
      let laneBottom = laneY + laneH;

      mine.forEach((id) => {
        const item = index.get(id);
        const { w, h } = sizeOf(item);
        const at = rank.get(id);
        const band = rowBand.get(row.get(id)) || 0;
        let x = columnX.get(at) + (columns.get(at) - w) / 2;
        let y = rowY.get(row.get(id));
        const hand = manualPositions.get(id);
        if (hand) {
          /* Held inside its own lane. A box drawn in another lane would say
             someone else does the work, and lane membership is the model's to
             state (bp:flowNodeRef), not the layout's. Pulled past the right or
             the bottom edge, the lane grows to take it instead. */
          x = Math.max(POOL_LABEL_W + LANE_LABEL_W + 6, hand.x);
          y = Math.max(laneY + band + 6, hand.y);
        }
        laneBottom = Math.max(laneBottom, y + h + POOL_PAD / 2);
        rightmost = Math.max(rightmost, x + w + POOL_PAD);
        placed.set(id, {
          x, y, w, h, item, band,
          head: item.shape === "activity" ? headHeight(item) : h,
        });
      });
      laneH = Math.max(laneH, laneBottom - laneY);
      attached.forEach(([noteId, anchor], seat) => {
        const host = placed.get(anchor);
        notes.push({
          note: (data.artifacts || []).find((a) => a.id === noteId),
          x: (host ? host.x : columnX.get(0)) + seat * (NOTE_W + 12),
          y: rowY.get(noteRow), anchor,
        });
      });

      drawnBands.push({ ...band, x: POOL_LABEL_W, y: laneY, w: poolW - POOL_LABEL_W, h: laneH });
      laneY += laneH;
    });

    // A boundary event sits on the lower border of the activity it watches,
    // so it is placed from its host rather than given a column of its own.
    members.forEach((item) => {
      const host = placed.get(item.id);
      if (!host || !(item.boundary || []).length) return;
      const r = EVENT_R - 3;
      const step = Math.min(host.w / (item.boundary.length + 1), 46);
      item.boundary.forEach((id, seat) => {
        const attached = index.get(id);
        if (!attached) return;
        placed.set(id, {
          x: host.x + step * (seat + 1) - r, y: host.y + host.h - r,
          w: r * 2, h: r * 2, item: attached, band: 0, head: r * 2,
        });
      });
    });

    poolW = Math.max(poolW, rightmost);
    const poolH = Math.max(laneY + POOL_PAD - poolY, BOX_H + POOL_PAD * 2);
    pools.push({
      participant, x: 0, y: poolY, w: poolW, h: poolH,
      lanes: drawnBands, members, showLanes: bands.some((b) => !b.implicit),
    });
    poolY += poolH + POOL_GAP;
  });

  const widest = Math.max(0, ...pools.map((pool) => pool.w));
  pools.forEach((pool) => {
    pool.w = widest;
    pool.lanes.forEach((lane) => { lane.w = widest - POOL_LABEL_W; });
  });

  return { pools, placed, notes, height: poolY };
}

/* Event trigger glyphs, drawn about the centre of the ring. A throwing event
 * fills its glyph and a catching one outlines it - in BPMN that is the whole
 * difference between waiting for a message and sending one. */
function definitionGlyph(parent, kind, throwing) {
  const g = node("g", { class: `pc-ev-glyph${throwing ? " throwing" : ""}` }, parent);
  if (kind === "message") {
    node("rect", { x: -7, y: -5, width: 14, height: 10, class: "pc-ev-mark" }, g);
    node("path", { d: "M -7 -5 L 0 1 L 7 -5", class: "pc-ev-line" }, g);
  } else if (kind === "timer") {
    node("circle", { cx: 0, cy: 0, r: 7.5, class: "pc-ev-line" }, g);
    node("path", {
      d: "M 0 -5 V 0 L 3.5 2.5 M 0 -7.5 v 1.6 M 0 6 v 1.5 M -7.5 0 h 1.6 M 6 0 h 1.5",
      class: "pc-ev-line",
    }, g);
  } else if (kind === "error") {
    node("path", { d: "M -7 6 L -2.5 -3 L 2 1.5 L 7 -6 L 2.5 3 L -2 -1.5 Z", class: "pc-ev-mark" }, g);
  } else if (kind === "escalation") {
    node("path", { d: "M 0 -7 L 6 7 L 0 1 L -6 7 Z", class: "pc-ev-mark" }, g);
  } else if (kind === "signal") {
    node("path", { d: "M 0 -7 L 7 6 H -7 Z", class: "pc-ev-mark" }, g);
  } else if (kind === "conditional") {
    node("rect", { x: -6, y: -7, width: 12, height: 14, class: "pc-ev-mark" }, g);
    node("path", { d: "M -4 -4 h 8 M -4 -1 h 8 M -4 2 h 8 M -4 5 h 8", class: "pc-ev-line" }, g);
  } else if (kind === "compensate") {
    node("path", { d: "M 0 -6 V 6 L -7 0 Z M 7 -6 V 6 L 0 0 Z", class: "pc-ev-mark" }, g);
  } else if (kind === "cancel") {
    node("path", { d: "M -6 -6 L 6 6 M 6 -6 L -6 6", class: "pc-ev-line strong" }, g);
  } else if (kind === "terminate") {
    node("circle", { cx: 0, cy: 0, r: 7, class: "pc-ev-mark filled" }, g);
  } else if (kind === "link") {
    node("path", { d: "M -7 -2.5 h 7 v -3 l 7 5.5 l -7 5.5 v -3 h -7 z", class: "pc-ev-mark" }, g);
  }
  return g;
}

/* A start event is a thin ring, an intermediate one a double ring, an end
 * event a thick one, and a non-interrupting boundary event dashes both. */
function eventShape(parent, cx, cy, item, radius = EVENT_R) {
  const dashed = item.kind === "boundaryEvent" && !item.interrupting;
  const cls = (extra) => `pc-ev-ring ${extra}${dashed ? " open" : ""}`;
  if (item.kind === "endEvent") {
    node("circle", { cx, cy, r: radius, class: cls("end") }, parent);
  } else if (item.kind === "startEvent") {
    node("circle", { cx, cy, r: radius, class: cls("start") }, parent);
  } else {
    node("circle", { cx, cy, r: radius, class: cls("mid") }, parent);
    node("circle", { cx, cy, r: radius - 3.5, class: cls("mid") }, parent);
  }
  if (item.definition) {
    const glyph = definitionGlyph(parent, item.definition, item.throwing);
    glyph.setAttribute("transform", `translate(${cx} ${cy}) scale(${radius / EVENT_R})`);
  }
}

function drawEvent(parent, slot) {
  const { item } = slot;
  const group = node("g", { class: `pc-event ${item.kind}` }, parent);
  const cx = slot.x + slot.w / 2;
  const cy = slot.y + slot.h / 2;
  eventShape(group, cx, cy, item);
  if (item.label) {
    wrap(item.label, 18, 2).forEach((line, row) => {
      centred(group, cx, slot.y + slot.h + 13 + row * 12, line, "pc-ev-label");
    });
  }
  const hint = node("title", {}, group);
  hint.textContent = `${item.label || humanKind(item.kind)}\n${humanKind(item.kind)}`
    + (item.definition ? ` — ${humanKind(item.definition)}` : "")
    + (item.definitionLabel ? `: ${item.definitionLabel}` : "");
  return group;
}

/** The glyph inside the diamond - drawn on the canvas and in the palette. */
function gatewayMark(parent, kind, cx, cy) {
  const mark = node("g", { transform: `translate(${cx} ${cy})`, class: "pc-gate-mark" }, parent);
  if (kind === "exclusiveGateway") {
    node("path", { d: "M -6 -6 L 6 6 M 6 -6 L -6 6" }, mark);
  } else if (kind === "parallelGateway") {
    node("path", { d: "M 0 -8 V 8 M -8 0 H 8" }, mark);
  } else if (kind === "inclusiveGateway") {
    node("circle", { cx: 0, cy: 0, r: 7.5, class: "pc-gate-ring" }, mark);
  } else if (kind === "complexGateway") {
    node("path", { d: "M 0 -8 V 8 M -8 0 H 8 M -5.6 -5.6 L 5.6 5.6 M 5.6 -5.6 L -5.6 5.6" }, mark);
  } else {
    node("circle", { cx: 0, cy: 0, r: 9, class: "pc-gate-ring" }, mark);
    node("circle", { cx: 0, cy: 0, r: 6.5, class: "pc-gate-ring" }, mark);
    if (kind === "parallelEventBasedGateway") {
      node("path", { d: "M 0 -4 V 4 M -4 0 H 4" }, mark);
    } else {
      node("path", {
        d: "M 0 -4.4 L 4.2 -1.4 L 2.6 3.6 H -2.6 L -4.2 -1.4 Z", class: "pc-gate-ring",
      }, mark);
    }
  }
  return mark;
}

/* A gateway is a diamond and the glyph inside says which one. A bare diamond
 * is legal BPMN and means exclusive, but a reader who has to know that rule is
 * a reader the diagram has already failed, so the X is always drawn. */
function drawGateway(parent, slot) {
  const { item } = slot;
  const group = node("g", { class: `pc-gateway ${item.kind}` }, parent);
  const cx = slot.x + slot.w / 2;
  const cy = slot.y + slot.h / 2;
  const r = GATE_R;
  node("path", {
    d: `M ${cx} ${cy - r} L ${cx + r} ${cy} L ${cx} ${cy + r} L ${cx - r} ${cy} Z`,
    class: "pc-gate-box",
  }, group);
  gatewayMark(group, item.kind, cx, cy);
  if (item.label) {
    wrap(item.label, 18, 2).forEach((line, row) => {
      centred(group, cx, slot.y - 18 + row * 12, line, "pc-ev-label");
    });
  }
  const hint = node("title", {}, group);
  hint.textContent = `${item.label || humanKind(item.kind)}\n${humanKind(item.kind)}`
    + (item.direction ? ` (${item.direction})` : "");
  return group;
}

/** The marker row along the bottom edge: what BPMN says about how it runs. */
function activityMarkers(parent, slot) {
  const { item } = slot;
  const marks = [];
  if (item.children.length) marks.push("sub");
  if (item.markers.loop === "standard") marks.push("loop");
  if (item.markers.loop === "multiParallel") marks.push("multiParallel");
  if (item.markers.loop === "multiSequential") marks.push("multiSequential");
  if (item.markers.adHoc) marks.push("adHoc");
  if (item.markers.compensation) marks.push("compensation");
  if (!marks.length) return;

  const size = 14;
  const step = size + 6;
  const startX = slot.x + slot.w / 2 - (marks.length * step - 6) / 2;
  marks.forEach((mark, seat) => {
    const x = startX + seat * step;
    const y = slot.y + slot.h - size - 3;
    const g = node("g", { class: `pc-mk pc-mk-${mark}`, transform: `translate(${x} ${y})` }, parent);
    if (mark === "sub") {
      node("rect", { x: 0, y: 0, width: size, height: size, class: "pc-mk-box" }, g);
      node("path", { d: `M ${size / 2} 3 V ${size - 3} M 3 ${size / 2} H ${size - 3}` }, g);
      g.classList.add("pc-marker");
      g.setAttribute("cursor", "pointer");
      g.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (expanded.has(item.id)) expanded.delete(item.id); else expanded.add(item.id);
        draw();
      });
      node("title", {}, g).textContent = expanded.has(item.id)
        ? "Collapse the business steps inside this activity"
        : "Show the business steps inside this activity";
    } else if (mark === "loop") {
      node("path", { d: "M 12 4 a 5 5 0 1 0 1 5 M 12 1 v 3.5 h -3.5" }, g);
      node("title", {}, g).textContent = "Loop: repeats while its condition holds";
    } else if (mark === "multiParallel") {
      node("path", { d: "M 3 2 v 11 M 7 2 v 11 M 11 2 v 11" }, g);
      node("title", {}, g).textContent = "Multi-instance, parallel";
    } else if (mark === "multiSequential") {
      node("path", { d: "M 2 4 h 11 M 2 7.5 h 11 M 2 11 h 11" }, g);
      node("title", {}, g).textContent = "Multi-instance, sequential";
    } else if (mark === "adHoc") {
      node("path", { d: "M 2 9 q 3 -5 5.5 0 t 5.5 0" }, g);
      node("title", {}, g).textContent = "Ad-hoc: the steps have no fixed order";
    } else if (mark === "compensation") {
      node("path", { d: "M 7 3 v 9 L 1 7.5 Z M 14 3 v 9 L 8 7.5 Z", class: "pc-mk-fill" }, g);
      node("title", {}, g).textContent = "Compensation handler";
    }
  });
}

// BPMN marks the kind of work with a corner glyph, not a word.
function typeMarker(parent, kind, x, y) {
  const g = node("g", { class: "pc-icon", transform: `translate(${x} ${y})` }, parent);
  if (kind === "userTask") {
    node("circle", { cx: 6, cy: 3.5, r: 2.6 }, g);
    node("path", { d: "M 1 11 a 5 5 0 0 1 10 0" }, g);
  } else if (kind === "manualTask") {
    node("path", {
      d: "M 2 10 v -4 a 1.4 1.4 0 0 1 2.8 0 v -2 a 1.4 1.4 0 0 1 2.8 0 v 1 a 1.4 1.4 0 0 1 2.8 0 v 5",
    }, g);
  } else if (kind === "serviceTask") {
    node("circle", { cx: 6, cy: 6, r: 4.4 }, g);
    node("circle", { cx: 6, cy: 6, r: 1.6, class: "pc-icon-hole" }, g);
  } else if (kind === "scriptTask") {
    node("path", { d: "M 3 1 h 6 v 10 h -6 z M 4.6 4 h 2.8 M 4.6 6 h 2.8 M 4.6 8 h 2.8" }, g);
  } else if (kind === "sendTask") {
    node("path", { d: "M 1 2.5 h 10 v 7 h -10 z", class: "pc-icon-filled" }, g);
    node("path", { d: "M 1 2.5 l 5 4 l 5 -4" }, g);
  } else if (kind === "receiveTask") {
    node("path", { d: "M 1 2.5 h 10 v 7 h -10 z" }, g);
    node("path", { d: "M 1 2.5 l 5 4 l 5 -4" }, g);
  } else if (kind === "businessRuleTask") {
    node("path", { d: "M 1 2 h 10 v 8 h -10 z M 1 4.4 h 10 M 4.4 4.4 v 5.6" }, g);
  } else if (kind === "callActivity") {
    node("path", { d: "M 1 2 h 10 v 8 h -10 z M 3.4 4.4 h 5.2 v 3.2 h -5.2 z" }, g);
  }
  return g;
}

/* A text annotation is an open bracket, not a box: BPMN draws only the left
 * edge so a comment never reads as another step of work. */
function drawNote(parent, note, x, y) {
  const lines = wrap(note.text, 30, 3);
  const height = Math.max(34, lines.length * 13 + 12);
  const group = node("g", { class: "pc-note" }, parent);
  node("path", {
    d: `M ${x + 9} ${y} H ${x} V ${y + height} H ${x + 9}`, class: "pc-note-bracket",
  }, group);
  lines.forEach((line, row) => {
    text(group, x + 15, y + 15 + row * 13, line, "pc-note-label");
  });
  node("title", {}, group).textContent = note.text;
  return { group, width: NOTE_W, height };
}

/* BPMN routes connectors at right angles, not as splines. The corners are
 * rounded so a three-segment route still reads as one line. */
function orthPath(points, radius = 9) {
  const kept = points.filter((p, i) => i === 0
    || Math.abs(p.x - points[i - 1].x) > 0.5 || Math.abs(p.y - points[i - 1].y) > 0.5);
  if (kept.length < 2) return "";
  let d = `M ${kept[0].x} ${kept[0].y}`;
  for (let i = 1; i < kept.length - 1; i += 1) {
    const previous = kept[i - 1];
    const corner = kept[i];
    const next = kept[i + 1];
    const back = Math.hypot(corner.x - previous.x, corner.y - previous.y);
    const on = Math.hypot(next.x - corner.x, next.y - corner.y);
    const r = Math.min(radius, back / 2, on / 2);
    const ax = corner.x - ((corner.x - previous.x) / back) * r;
    const ay = corner.y - ((corner.y - previous.y) / back) * r;
    const bx = corner.x + ((next.x - corner.x) / on) * r;
    const by = corner.y + ((next.y - corner.y) / on) * r;
    d += ` L ${ax} ${ay} Q ${corner.x} ${corner.y} ${bx} ${by}`;
  }
  const last = kept[kept.length - 1];
  return `${d} L ${last.x} ${last.y}`;
}

/** Where a connector leaves or meets a shape - a diamond by its four points. */
function port(slot, side) {
  const cx = slot.x + slot.w / 2;
  const midY = slot.y + (slot.head || slot.h) / 2;
  const cy = slot.item && slot.item.shape === "activity" ? midY : slot.y + slot.h / 2;
  if (side === "right") return { x: slot.x + slot.w, y: cy };
  if (side === "left") return { x: slot.x, y: cy };
  if (side === "top") return { x: cx, y: slot.y };
  return { x: cx, y: slot.y + slot.h };
}

/* Three cases, and the third is the one the old canvas could not draw at all:
 * a flow that goes backwards is a rework loop and has to leave and re-enter
 * from below, or it crosses every box between its ends. */
function routeSequence(from, to) {
  const gap = 22;
  if (to.x >= from.x + from.w - 1) {
    const a = port(from, "right");
    const b = port(to, "left");
    if (Math.abs(a.y - b.y) < 2) return [a, b];
    const midX = (a.x + b.x) / 2;
    return [a, { x: midX, y: a.y }, { x: midX, y: b.y }, b];
  }
  if (to.x + to.w <= from.x + 1) {
    const a = port(from, "bottom");
    const b = port(to, "bottom");
    const below = Math.max(a.y, b.y) + gap;
    return [a, { x: a.x, y: below }, { x: b.x, y: below }, b];
  }
  const downward = to.y > from.y;
  const a = port(from, downward ? "bottom" : "top");
  const b = port(to, downward ? "top" : "bottom");
  const midY = (a.y + b.y) / 2;
  return [a, { x: a.x, y: midY }, { x: b.x, y: midY }, b];
}

function sequenceArrow(parent, from, to, flow) {
  const points = routeSequence(from, to);
  const picked = flow.id && flow.id === pickedFlow;
  const group = node("g", { class: "pc-seq" }, parent);
  if (flow.id) group.setAttribute("data-flow", flow.id);
  node("path", {
    d: orthPath(points),
    class: "pc-flow" + (picked ? " picked" : ""),
    "marker-end": "url(#pc-arrow)",
  }, group);
  wireConnector(group, orthPath(points), flow.id, picked, points);
  // A default flow carries a tick through its tail; a conditional one a diamond.
  const start = points[0];
  const after = points[1];
  if (flow.default) {
    const dx = Math.sign(after.x - start.x) || 0;
    const dy = Math.sign(after.y - start.y) || 0;
    node("path", {
      d: `M ${start.x + dx * 5 - 4 - dy * 4} ${start.y + dy * 5 - 4 + dx * 4} `
        + `L ${start.x + dx * 12 + 4 - dy * 4} ${start.y + dy * 12 + 4 + dx * 4}`,
      class: "pc-flow-tick",
    }, group);
  } else if (flow.condition) {
    const dx = Math.sign(after.x - start.x) || 0;
    const dy = Math.sign(after.y - start.y) || 0;
    const cx = start.x + dx * 7;
    const cy = start.y + dy * 7;
    node("path", {
      d: `M ${cx - dx * 6 - dy * 5} ${cy - dy * 6 - dx * 5} L ${cx + dy * 5 - dx * 0} ${cy + dx * 5}`
        + ` L ${cx + dx * 6 + dy * 5} ${cy + dy * 6 + dx * 5} L ${cx - dy * 5} ${cy - dx * 5} Z`,
      class: "pc-flow-diamond",
    }, group);
  }
  /* On the longest segment of the route. */
  const caption = flow.label;
  if (caption) {
    let best = null;
    for (let i = 1; i < points.length; i += 1) {
      const run = Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
      if (!best || run > best.run) best = { run, from: points[i - 1], to: points[i] };
    }
    if (best && best.run >= 34) {
      const vertical = Math.abs(best.to.x - best.from.x) < Math.abs(best.to.y - best.from.y);
      const room = vertical ? 30 : Math.max(10, Math.floor(best.run / 5.4));
      const midX = (best.from.x + best.to.x) / 2;
      const midY = (best.from.y + best.to.y) / 2;
      if (vertical) text(group, midX + 5, midY, truncate(caption, room), "pc-flow-label");
      else centred(group, midX, midY - 5, truncate(caption, room), "pc-flow-label");
    }
  }
  if (flow.label || flow.condition) {
    node("title", {}, group).textContent = flow.condition
      ? `${flow.label || "when"}: ${flow.condition}` : flow.label;
  }
  return group;
}

/** A message crosses a boundary: leave the source downward, enter the target. */
function messageArrow(parent, from, to, label, id) {
  const downward = to.y > from.y;
  const a = port(from, downward ? "bottom" : "top");
  const b = port(to, downward ? "top" : "bottom");
  const midY = (a.y + b.y) / 2;
  const points = [a, { x: a.x, y: midY }, { x: b.x, y: midY }, b];
  const picked = id && id === pickedFlow;
  const group = node("g", { class: "pc-msg" }, parent);
  if (id) group.setAttribute("data-flow", id);
  node("path", {
    d: orthPath(points), class: "pc-flow message" + (picked ? " picked" : ""),
    "marker-end": "url(#pc-arrow-msg)",
  }, group);
  node("circle", { cx: a.x, cy: a.y, r: 3.5, class: "pc-msg-start" }, group);
  if (label) centred(group, (a.x + b.x) / 2, midY - 5, truncate(label, 26), "pc-flow-label");
  wireConnector(group, orthPath(points), id, picked, points);
}

/* One gesture for every connector: a wide invisible path takes the press, and
 * a picked one carries the badge that removes it.
 *
 * A line drawn wrong used to cost the boxes at either end - deleting a node was
 * the only thing that took its connectors with it. A 1.5px stroke cannot be hit
 * reliably, so the press lands on a fat copy of the same route. */
function wireConnector(group, d, id, picked, points) {
  if (!id) return;
  const hit = node("path", { d, class: "pc-flow-hit", fill: "none" }, group);
  hit.addEventListener("pointerdown", (ev) => {
    ev.stopPropagation();
    pickedFlow = picked ? null : id;
    redraw();
  });
  if (!picked) return;
  // On the longest run, so the badge does not land on a corner.
  let best = null;
  for (let i = 1; i < points.length; i += 1) {
    const run = Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
    if (!best || run > best.run) best = { run, from: points[i - 1], to: points[i] };
  }
  /* Recorded rather than drawn here. Connectors are painted under the boxes so
     a line never sits on one it only passes - which put the badge under a port
     dot, where no press could reach it. A control goes on top. */
  pendingBadge = {
    id,
    at: best
      ? { x: (best.from.x + best.to.x) / 2, y: (best.from.y + best.to.y) / 2 }
      : points[0],
  };
}

/* Drawn last, over everything, because it is the only thing on the canvas that
   is purely a control. */
function drawPickedBadge(parent) {
  if (!pendingBadge) return;
  const { id, at } = pendingBadge;
  const badge = node("g", { class: "pc-flow-drop" }, parent);
  node("circle", { cx: at.x, cy: at.y, r: 8, class: "pc-flow-drop-disc" }, badge);
  const sign = node("text", {
    x: at.x, y: at.y + 3.5, class: "pc-flow-drop-sign", "text-anchor": "middle",
  }, badge);
  sign.textContent = "\u00d7";
  node("title", {}, badge).textContent = "Remove this connector";
  badge.addEventListener("pointerdown", async (ev) => {
    ev.stopPropagation();
    pickedFlow = null;
    if (onEdit) await onEdit("disconnect", { flow: id });
  });
}

/* A data object is a folded page and a data store a cylinder, which is what
 * BPMN 2.0 draws and what a reader of a process model already recognises. The
 * classification underneath is the point of showing them at all: dpv:PersonalData
 * on the item definition is what business_data_bridge.rq turns into a data
 * category on the architecture, so an invisible annotation is an invisible
 * cause of findings. */
function dataGlyph(parent, x, y, item) {
  const g = node("g", { class: "pc-data" }, parent);
  if (item.store) {
    node("path", {
      d: `M ${x} ${y + 6} a ${DATA_W / 2} 6 0 0 1 ${DATA_W} 0 v 24 a ${DATA_W / 2} 6 0 0 1 ${-DATA_W} 0 z`,
      class: "pc-data-shape",
    }, g);
    node("path", {
      d: `M ${x} ${y + 6} a ${DATA_W / 2} 6 0 0 0 ${DATA_W} 0`, class: "pc-data-fold",
    }, g);
  } else {
    const fold = 9;
    node("path", {
      d: `M ${x} ${y} h ${DATA_W - fold} l ${fold} ${fold} v ${DATA_H - fold} h ${-DATA_W} z`,
      class: "pc-data-shape",
    }, g);
    node("path", { d: `M ${x + DATA_W - fold} ${y} v ${fold} h ${fold}`, class: "pc-data-fold" }, g);
    // A data input is an open arrow in the corner and a data output a filled one.
    if (item.input || item.output) {
      node("path", {
        d: `M ${x + 4} ${y + 9} l 4 -4 l 4 4 m -4 -4 v 8`,
        class: item.output ? "pc-data-io filled" : "pc-data-io",
      }, g);
    }
  }
  if (item.collection) {
    node("path", {
      d: `M ${x + DATA_W / 2 - 3} ${y + DATA_H - 7} v 6 M ${x + DATA_W / 2} ${y + DATA_H - 7} v 6 `
        + `M ${x + DATA_W / 2 + 3} ${y + DATA_H - 7} v 6`,
      class: "pc-data-fold",
    }, g);
  }
  return g;
}

/* A data association: dashed, with an open head, and pointing the way the data
 * moves - into the activity for a read, out of it for a write. */
function dataAssociation(parent, x1, y1, x2, y2) {
  node("path", {
    d: `M ${x1} ${y1} L ${x2} ${y2}`,
    class: "pc-data-link",
    "marker-end": "url(#pc-arrow-data)",
  }, parent);
}

function drawData(parent, slot) {
  const items = dataOf(slot.item);
  if (!items.length || !slot.band) return;
  const spread = Math.min(slot.w / items.length, 92);
  items.forEach((item, seat) => {
    const cx = slot.x + spread * (seat + 0.5) + (slot.w - spread * items.length) / 2;
    const top = slot.y - slot.band + 6;
    const g = dataGlyph(parent, cx - DATA_W / 2, top, item);
    if (item.direction === "in") {
      dataAssociation(g, cx, top + DATA_H + 2, cx, slot.y - 4);
    } else {
      dataAssociation(g, cx, slot.y - 4, cx, top + DATA_H + 2);
    }
    wrap(item.label, 16, 2).forEach((line, row) => {
      centred(g, cx, top + DATA_H + 13 + row * 11, line, "pc-data-label");
    });
    if (item.state) centred(g, cx, top - 14, `[${truncate(item.state, 14)}]`, "pc-data-state");
    if (item.kinds.length) {
      centred(g, cx, top - 4, item.kinds.map(humanKind).join(", "), "pc-data-kind");
    }
    const title = node("title", {}, g);
    title.textContent = `${item.label} — ${item.direction === "in" ? "read by" : "written by"} `
      + `${slot.item.label}`
      + (item.kinds.length
        ? `\nClassified: ${item.kinds.join(", ")}`
        : "\nNot classified");
  });
}

function childrenOf(activity) {
  return activity.children.map((id) => index.get(id)).filter(Boolean);
}

/* A call activity is drawn with a thick border and a transaction with a second
 * one inside it - both are BPMN's way of saying "this box is not the whole
 * story", which for a risk assessment is exactly the box to look inside. */
function activityBorder(parent, slot) {
  const { item } = slot;
  const dashed = item.markers.eventSubProcess;
  node("rect", {
    x: slot.x, y: slot.y, width: slot.w, height: slot.h, rx: 8,
    class: `pc-box${item.markers.call ? " call" : ""}${dashed ? " event-sub" : ""}`,
  }, parent);
  if (item.markers.transaction) {
    node("rect", {
      x: slot.x + 3.5, y: slot.y + 3.5, width: slot.w - 7, height: slot.h - 7, rx: 5,
      class: "pc-box inner",
    }, parent);
  }
}

function drawActivity(parent, slot) {
  const item = slot.item;
  const group = node("g", {
    class: `pc-activity${item.refines.length ? " refined" : ""}${item.human ? " human" : ""}`,
  }, parent);

  activityBorder(group, slot);
  const hint = node("title", {}, group);
  hint.textContent = `${item.label}\n` + (item.refines.length
    ? "Click the AI system chip to open the architecture, the pencil to edit"
    : (item.children.length ? "Click + to show the steps inside" : "Edit this activity"));

  typeMarker(group, item.kind, slot.x + 8, slot.y + 7);
  // The risk badge owns the top right, so the name wraps under it.
  const lines = wrap(item.label, nameRoomOf(item), 2);
  lines.forEach((line, seat) => {
    text(group, slot.x + 26, slot.y + 17 + seat * LINE_H, line, "pc-label");
  });
  const afterName = slot.y + 17 + (lines.length - 1) * LINE_H;

  if (item.performers.length) {
    const row = afterName + (item.refines.length ? 31 : 17);
    text(group, slot.x + 26, row, truncate(item.performers.join(", "), 26), "pc-by");
  }

  activityMarkers(group, slot);

  if (expanded.has(item.id) && item.children.length) {
    childrenOf(item).forEach((child, seat) => {
      const cy = slot.y + slot.head + seat * CHILD_H;
      node("rect", {
        x: slot.x + 12, y: cy, width: slot.w - 24, height: CHILD_H - 6, rx: 4, class: "pc-child",
      }, group);
      const glyph = child.shape === "gateway" ? "◇ " : (child.shape === "event" ? "○ " : "");
      text(group, slot.x + 22, cy + 18, glyph + truncate(child.label, 26), "pc-child-label");
    });
  }

  // Candidate risks for this activity; the badge folds the list.
  const risk = riskOf(item);
  if (risk && risk.findings) {
    const open = openRisks.has(item.id);
    const badge = node("g", { class: "pc-risk", cursor: "pointer" }, group);
    const width = 54;
    node("rect", {
      x: slot.x + slot.w - width - 10, y: slot.y + 8,
      width, height: 17, rx: 8, class: "pc-risk-box",
    }, badge);
    centred(badge, slot.x + slot.w - width / 2 - 10, slot.y + 20,
      `${risk.findings} risk${risk.findings === 1 ? "" : "s"} ${open ? "⌃" : "⌄"}`,
      "pc-risk-label");
    badge.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (open) openRisks.delete(item.id); else openRisks.add(item.id);
      draw();
    });
    node("title", {}, badge).textContent = open
      ? "Hide the candidate risks found here"
      : "Show the candidate risks found here";

    if (open) {
      let rowY = slot.y + slot.h - risk.items.length * RISK_ROW_H - 6;
      risk.items.forEach((entry) => {
        text(group, slot.x + 26, rowY + 11, `• ${truncate(entry.label, 34)}`, "pc-risk-item");
        rowY += RISK_ROW_H;
      });
    }
  }

  if (item.refines.length) {
    /* The chip is the only way down, and that is the point. */
    const chip = node("g", { class: "pc-open", cursor: "pointer" }, group);
    const chipW = 74;
    node("rect", {
      x: slot.x + 26, y: afterName + 6, width: chipW, height: 15, rx: 7, class: "pc-open-box",
    }, chip);
    centred(chip, slot.x + 26 + chipW / 2, afterName + 17, "AI system ›", "pc-open-label");
    node("title", {}, chip).textContent = "Open the AI architecture that carries out this activity";
    chip.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (onSelect) onSelect(item.id);
      if (onOpenArchitecture) onOpenArchitecture(item);
    });
  }
  if (onEdit) {
    // Sequence flow or message flow follows from the pools; the server decides.
    const dot = node("g", { class: "pc-port", cursor: "crosshair" }, group);
    node("circle", {
      cx: slot.x + slot.w, cy: slot.y + slot.head / 2, r: PORT_SCREEN_R, class: "pc-port-dot",
    }, dot);
    dot.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
      startConnect(ev, item, slot);
    });
    node("title", {}, dot).textContent = "Drag onto another activity to connect";

    /* Clicking the box selects it and reveals the line that declares it. */
    group.addEventListener("click", (ev) => {
      if (ev.target.closest(".pc-marker, .pc-port, .pc-edit, .pc-risk, .pc-open")) return;
      ev.stopPropagation();
      if (onSelect) onSelect(item.id);
      if (!item.refines.length) showDetail(item, ev);
    });
    group.setAttribute("cursor", "pointer");

    if (item.refines.length) {
      const pencil = node("g", { class: "pc-edit", cursor: "pointer" }, group);
      node("rect", {
        x: slot.x + slot.w - 26, y: slot.y + slot.h - 24, width: 18, height: 18, rx: 3,
        class: "pc-edit-box",
      }, pencil);
      node("path", {
        d: `M ${slot.x + slot.w - 21} ${slot.y + slot.h - 10} l 0 -3 l 7 -7 l 3 3 l -7 7 z`,
        class: "pc-edit-nib",
      }, pencil);
      pencil.addEventListener("click", (ev) => {
        ev.stopPropagation();
        showDetail(item, ev);
      });
      node("title", {}, pencil).textContent = "Edit this activity";
    }
  }
  return group;
}

/** An event pinned to the border of the activity it watches. */
function drawBoundary(parent, slot) {
  const { item } = slot;
  const group = node("g", { class: `pc-event boundaryEvent${item.interrupting ? "" : " open"}` },
    parent);
  eventShape(group, slot.x + slot.w / 2, slot.y + slot.h / 2, item, EVENT_R - 3);
  if (item.label) {
    wrap(item.label, 16, 2).forEach((line, row) => {
      centred(group, slot.x + slot.w / 2, slot.y + slot.h + 12 + row * 11, line, "pc-ev-label");
    });
  }
  node("title", {}, group).textContent = `${item.label || "Boundary event"}\n`
    + `${item.interrupting ? "Interrupting" : "Non-interrupting"} boundary event`
    + (item.definition ? ` — ${humanKind(item.definition)}` : "");
  group.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (onSelect) onSelect(item.id);
    if (onEdit) showNodeDetail(item, ev);
  });
  return group;
}

function drawFlowNode(parent, slot) {
  if (slot.item.shape === "event") return drawEvent(parent, slot);
  if (slot.item.shape === "gateway") return drawGateway(parent, slot);
  return drawActivity(parent, slot);
}

/* An event or a gateway is clicked like an activity, but there is no
 * architecture behind it, so it always opens its editor. */
function wireSimpleNode(group, slot) {
  if (!onEdit) return;
  const { item } = slot;
  const dot = node("g", { class: "pc-port", cursor: "crosshair" }, group);
  node("circle", {
    cx: slot.x + slot.w, cy: slot.y + slot.h / 2, r: PORT_SCREEN_R, class: "pc-port-dot",
  }, dot);
  dot.addEventListener("pointerdown", (ev) => {
    ev.stopPropagation();
    startConnect(ev, item, { ...slot, head: slot.h });
  });
  node("title", {}, dot).textContent = "Drag onto another node to connect";
  group.setAttribute("cursor", "pointer");
  group.addEventListener("click", (ev) => {
    if (ev.target.closest(".pc-port")) return;
    ev.stopPropagation();
    if (onSelect) onSelect(item.id);
    showNodeDetail(item, ev);
  });
}

/* The last layout's placement for a node, so a drag starts from where the box
   actually is rather than from where the automatic layout would put it. */
let lastPlaced = new Map();
let lastPools = [];

/* What the view is fitted to: the model's structure, not just its flow nodes.
   Keyed on node ids alone - the architecture canvas's rule - a new lane or a
   new pool changed nothing the key could see, so the view stayed put while
   the diagram grew off the bottom of it. A selection, a fold or a moved box
   leaves this unchanged, which is what keeps the reader's view. */
function structureKey() {
  return [
    ...lastPools.map((pool) => "pool:" + pool.participant.id),
    ...lastPools.flatMap((pool) => pool.lanes.map((lane) => "lane:" + pool.participant.id + "/" + lane.id)),
    ...lastPlaced.keys(),
  ].sort().join("|");
}

function currentPlacement(id) {
  const slot = lastPlaced.get(id);
  return slot && slot.item && ["activity", "event", "gateway"].includes(slot.item.shape)
    ? slot : null;
}

function svgPoint(clientX, clientY) {
  const rect = svg.getBoundingClientRect();
  return { x: (clientX - rect.left - view.x) / view.k, y: (clientY - rect.top - view.y) / view.k };
}

function startConnect(ev, item, slot) {
  const line = node("path", { class: "pc-flow pending" }, root);
  connecting = { from: item, slot, line, id: ev.pointerId };
  // Held for the length of the drag so it survives leaving the port, and
  // released in endConnect - a capture left standing swallows every later
  // click on the canvas.
  try { svg.setPointerCapture(ev.pointerId); } catch (error) { /* already gone */ }
}

function moveConnect(ev) {
  if (!connecting) return;
  const to = svgPoint(ev.clientX, ev.clientY);
  const x1 = connecting.slot.x + connecting.slot.w;
  const y1 = connecting.slot.y + (connecting.slot.head || connecting.slot.h) / 2;
  connecting.line.setAttribute("d", `M ${x1} ${y1} L ${to.x} ${to.y}`);
}

async function endConnect(ev) {
  if (!connecting) return;
  const { from, line, id } = connecting;
  connecting = null;
  line.remove();
  try { svg.releasePointerCapture(id); } catch (error) { /* already gone */ }
  swallowNextClick = true;
  const dropped = document.elementFromPoint(ev.clientX, ev.clientY);
  // The id travels on the element, so a drop lands on the node under the
  // pointer rather than on whatever was drawn in that position.
  const group = dropped && dropped.closest("[data-node]");
  const targetId = group && group.getAttribute("data-node");
  if (!targetId || targetId === from.id) return;
  await onEdit("connect", { source: from.id, target: targetId });
}

function closeDetail() {
  const panel = document.querySelector("#process-detail");
  if (panel) panel.classList.add("hidden");
}

function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
}

function options(list, selected) {
  return list.map(([value, label]) =>
    `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>`
    + `${escapeHtml(label)}</option>`).join("");
}

function classOptions(selected) {
  return ['<option value="">— not classified —</option>']
    .concat(dataClasses.map((c) =>
      `<option value="${c.id}"${c.id === selected ? " selected" : ""}>${escapeHtml(c.label)}</option>`))
    .join("");
}

function placePanel(panel, ev, height) {
  panel.classList.remove("hidden");
  const rect = svg.getBoundingClientRect();
  // Clamped at both ends: on a canvas narrower than the panel, rect.width - 300
  // is negative and the panel went off the left edge entirely.
  panel.style.left = `${Math.max(8, Math.min(ev.clientX - rect.left + 12, rect.width - 300))}px`;
  panel.style.top = `${Math.max(8, Math.min(ev.clientY - rect.top + 12, rect.height - height))}px`;
}

const EVENT_KINDS = [
  ["startEvent", "Start"],
  ["intermediateCatchEvent", "Intermediate (catching)"],
  ["intermediateThrowEvent", "Intermediate (throwing)"],
  ["endEvent", "End"],
  ["boundaryEvent", "Boundary"],
];

const EVENT_DEFINITIONS = [
  ["", "— none (plain) —"],
  ["message", "Message"],
  ["timer", "Timer"],
  ["error", "Error"],
  ["escalation", "Escalation"],
  ["signal", "Signal"],
  ["conditional", "Conditional"],
  ["compensate", "Compensation"],
  ["cancel", "Cancel"],
  ["terminate", "Terminate"],
  ["link", "Link"],
];

const GATEWAY_KINDS = [
  ["exclusiveGateway", "Exclusive (XOR)"],
  ["parallelGateway", "Parallel (AND)"],
  ["inclusiveGateway", "Inclusive (OR)"],
  ["eventBasedGateway", "Event-based"],
  ["parallelEventBasedGateway", "Event-based, parallel"],
  ["complexGateway", "Complex"],
];

/* Events and gateways get their own editor: they carry a type and, for an
 * event, a trigger - and changing either is what turns a placeholder circle
 * into the thing the process actually waits for. */
function showNodeDetail(item, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  const isEvent = item.shape === "event";
  const kinds = isEvent ? EVENT_KINDS : GATEWAY_KINDS;
  panel.innerHTML = `
    <div class="nd-head">${escapeHtml(isEvent ? "event" : "gateway")}</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-name" value="${escapeHtml(item.label)}" /></label>
    <label class="nd-row"><span>Type</span>
      <select id="pd-kind">${options(kinds, item.kind)}</select></label>
    ${isEvent ? `<label class="nd-row"><span>Trigger</span>
      <select id="pd-def">${options(EVENT_DEFINITIONS, item.definition || "")}</select></label>` : ""}
    ${isEvent && item.kind === "boundaryEvent" ? `<label class="nd-row nd-check">
      <span>Interrupts the activity</span>
      <input type="checkbox" id="pd-interrupt"${item.interrupting ? " checked" : ""} /></label>` : ""}
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-apply">Apply</button>
      <button type="button" class="btn small" id="pd-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 220);

  panel.querySelector("#pd-apply").addEventListener("click", async () => {
    const label = panel.querySelector("#pd-name").value.trim();
    const kind = panel.querySelector("#pd-kind").value;
    const definition = isEvent ? panel.querySelector("#pd-def").value : "";
    const interrupting = panel.querySelector("#pd-interrupt");
    closeDetail();
    await onEdit("set-node-type", {
      element: item.id, kind, definition, label,
      interrupting: interrupting ? interrupting.checked : true,
    });
  });
  panel.querySelector("#pd-delete").addEventListener("click", async () => {
    closeDetail();
    await onEdit("delete", { element: item.id });
  });
}

/* The same panel an activity gets, with the two things a pool has: its name,
 * and whether it should exist. */
function showPoolDetail(participant, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  panel.innerHTML = `
    <div class="nd-head">participant</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-pool-name" value="${escapeHtml(participant.label)}" /></label>
    <div class="pd-add">
      <input type="text" id="pd-lane-name" placeholder="name of a new lane" />
      <button type="button" class="btn small" id="pd-lane-add">Add lane</button>
    </div>
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-pool-apply">Apply</button>
      <button type="button" class="btn small" id="pd-pool-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 200);

  panel.querySelector("#pd-lane-add").addEventListener("click", async () => {
    const label = panel.querySelector("#pd-lane-name").value.trim();
    if (!label) return;
    closeDetail();
    await onEdit("add-lane", { pool: participant.id, label });
  });
  panel.querySelector("#pd-pool-apply").addEventListener("click", async () => {
    const name = panel.querySelector("#pd-pool-name").value.trim();
    closeDetail();
    if (name && name !== participant.label) {
      await onEdit("rename", { element: participant.id, label: name });
    }
  });
  panel.querySelector("#pd-pool-delete").addEventListener("click", async () => {
    closeDetail();
    if (selectedPool === participant.id) selectedPool = null;
    await onEdit("delete", { element: participant.id });
  });
}

function showLaneDetail(lane, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  panel.innerHTML = `
    <div class="nd-head">lane</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-lane-label" value="${escapeHtml(lane.label)}" /></label>
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-lane-apply">Apply</button>
      <button type="button" class="btn small" id="pd-lane-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 160);
  panel.querySelector("#pd-lane-apply").addEventListener("click", async () => {
    const label = panel.querySelector("#pd-lane-label").value.trim();
    closeDetail();
    if (label && label !== lane.label) await onEdit("rename", { element: lane.id, label });
  });
  panel.querySelector("#pd-lane-delete").addEventListener("click", async () => {
    closeDetail();
    if (selectedLane === lane.id) selectedLane = null;
    await onEdit("delete", { element: lane.id });
  });
}

/* The data rows are why this panel exists at all now: a classification on a
 * data object is what business_data_bridge.rq turns into a data category on the
 * architecture, and it was previously only reachable by hand-writing three
 * BPMN nodes in Turtle. */
const DATA_SHAPES = [["object", "Document"], ["store", "Data store"]];

function dataRows(activity) {
  const items = dataOf(activity);
  if (!items.length) return '<div class="pd-empty">No data attached yet.</div>';
  return items.map((item) => `
    <div class="pd-data" data-ref="${escapeHtml(item.id)}">
      <span class="pd-dir">${item.direction === "in" ? "reads" : "writes"}</span>
      <span class="pd-name" title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</span>
      <select class="pd-shape" title="A document is a folded page, a data store a cylinder"
        >${options(DATA_SHAPES, item.store ? "store" : "object")}</select>
      <select class="pd-class">${classOptions(item.kinds[0] || "")}</select>
      <button type="button" class="pd-drop" title="Detach this data from the activity">×</button>
    </div>`).join("");
}

const LOOP_KINDS = [
  ["", "— runs once —"],
  ["standard", "Loop"],
  ["multiParallel", "Multi-instance, parallel"],
  ["multiSequential", "Multi-instance, sequential"],
];

function showDetail(activity, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  /* The last option is how an architecture gets started at all. */
  const systemOptions = ['<option value="">— not an AI activity —</option>']
    .concat(systems.map((s) =>
      `<option value="${s.id}"${activity.refines.includes(s.id) ? " selected" : ""}>`
      + `${escapeHtml(s.label)}</option>`))
    .concat(['<option value="__new__">+ new AI system…</option>'])
    .join("");
  panel.innerHTML = `
    <div class="nd-head">${escapeHtml(activity.kind)}</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-name" value="${escapeHtml(activity.label)}" /></label>
    <label class="nd-row"><span>Carried out by</span>
      <select id="pd-refines">${systemOptions}</select></label>
    <label class="nd-row"><span>Repetition</span>
      <select id="pd-loop">${options(LOOP_KINDS, activity.markers.loop || "")}</select></label>
    <div class="pd-section">Data</div>
    ${dataRows(activity)}
    <div class="pd-add">
      <select id="pd-dir"><option value="in">reads</option><option value="out">writes</option></select>
      <input type="text" id="pd-data-name" placeholder="name of the data" />
      <select id="pd-data-shape">${options(DATA_SHAPES, "object")}</select>
      <select id="pd-data-class">${classOptions("")}</select>
      <button type="button" class="btn small" id="pd-data-add">Add</button>
    </div>
    <div class="pd-add">
      <select id="pd-boundary">${options(EVENT_DEFINITIONS, "error")}</select>
      <button type="button" class="btn small" id="pd-boundary-add">Attach boundary event</button>
    </div>
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-apply">Apply</button>
      <button type="button" class="btn small" id="pd-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 340);

  panel.querySelectorAll(".pd-data").forEach((row) => {
    const reference = row.dataset.ref;
    row.querySelector(".pd-class").addEventListener("change", async (event) => {
      closeDetail();
      await onEdit("classify-data", { reference, classification: event.target.value });
    });
    row.querySelector(".pd-shape").addEventListener("change", async (event) => {
      closeDetail();
      await onEdit("set-data-shape", { reference, shape: event.target.value });
    });
    row.querySelector(".pd-drop").addEventListener("click", async () => {
      closeDetail();
      await onEdit("detach-data", { reference, activity: activity.id });
    });
  });

  panel.querySelector("#pd-data-add").addEventListener("click", async () => {
    const label = panel.querySelector("#pd-data-name").value.trim();
    if (!label) return;
    const direction = panel.querySelector("#pd-dir").value;
    const classification = panel.querySelector("#pd-data-class").value;
    const shape = panel.querySelector("#pd-data-shape").value;
    closeDetail();
    await onEdit("add-data", { activity: activity.id, direction, label, classification, shape });
  });

  panel.querySelector("#pd-boundary-add").addEventListener("click", async () => {
    const definition = panel.querySelector("#pd-boundary").value;
    closeDetail();
    await onEdit("add-event", {
      kind: "boundaryEvent", definition, attachedTo: activity.id, label: "",
    });
  });

  panel.querySelector("#pd-apply").addEventListener("click", async () => {
    const name = panel.querySelector("#pd-name").value.trim();
    const system = panel.querySelector("#pd-refines").value;
    const loop = panel.querySelector("#pd-loop").value;
    const label = name || activity.label;
    closeDetail();
    if (name && name !== activity.label) await onEdit("rename", { element: activity.id, label: name });
    if (loop !== (activity.markers.loop || "")) {
      await onEdit("set-loop", { activity: activity.id, loop });
    }
    if (system === "__new__") {
      // Named after the activity it carries out, which is the only thing known
      // about it yet; the chip then opens it so the shape can be drawn.
      const suggested = window.prompt("Name of the AI system that carries out this activity:",
        `${label} system`);
      if (suggested) await onEdit("add-system", { activity: activity.id, label: suggested });
      return;
    }
    await onEdit("set-refines", { activity: activity.id, system });
  });
  panel.querySelector("#pd-delete").addEventListener("click", async () => {
    closeDetail();
    await onEdit("delete", { element: activity.id });
  });
}

function defineMarkers(defs) {
  const dataHead = node("marker", {
    id: "pc-arrow-data", viewBox: "0 0 10 10", refX: 9, refY: 5,
    markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse",
  }, defs);
  node("path", { d: "M 0 0 L 10 5 L 0 10", class: "pc-arrow-head open" }, dataHead);
  [["pc-arrow", "pc-arrow-head"], ["pc-arrow-msg", "pc-arrow-head message"]].forEach(([id, cls]) => {
    // the message head is hollow; only sequence flow is filled
    const marker = node("marker", {
      id, viewBox: "0 0 10 10", refX: 9, refY: 5,
      markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse",
    }, defs);
    node("path", { d: "M 0 0 L 10 5 L 0 10 z", class: cls }, marker);
  });
}

/* A group is an artifact: it draws a dashed frame round whatever it names and
 * crosses lanes freely, which is the one thing pools and lanes may not do. */
function drawGroups(parent, placed) {
  (data.artifacts || []).filter((a) => a.kind === "group").forEach((cluster) => {
    const boxes = (cluster.members || []).map((id) => placed.get(id)).filter(Boolean);
    if (!boxes.length) return;
    const x = Math.min(...boxes.map((b) => b.x)) - 14;
    const y = Math.min(...boxes.map((b) => b.y - b.band)) - 18;
    const right = Math.max(...boxes.map((b) => b.x + b.w)) + 14;
    const bottom = Math.max(...boxes.map((b) => b.y + b.h)) + 14;
    const group = node("g", { class: "pc-group" }, parent);
    node("rect", {
      x, y, width: right - x, height: bottom - y, rx: 8, class: "pc-group-box",
    }, group);
    text(group, x + 10, y + 14, truncate(cluster.text, 34), "pc-group-label");
  });
}

function draw() {
  if (!svg || !data) return;
  svg.innerHTML = "";
  defineMarkers(node("defs", {}, svg));

  pendingBadge = null;
  root = node("g", { id: "pc-root" }, svg);
  portsSizedAt = null;   // a fresh DOM: the handles have to be measured again
  const { pools, placed, notes } = layout();
  lastPlaced = placed;
  lastPools = pools;

  drawGroups(root, placed);

  pools.forEach((pool) => {
    const group = node("g", { class: "pc-pool" }, root);
    node("rect", {
      x: pool.x, y: pool.y, width: pool.w, height: pool.h, rx: 6, class: "pc-pool-box",
    }, group);
    node("rect", {
      x: pool.x, y: pool.y, width: POOL_LABEL_W, height: pool.h, rx: 6, class: "pc-pool-strip",
    }, group);
    if (pool.participant.id === selectedPool) group.classList.add("selected");
    group.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-node], .pc-pool-edit, .pc-pool-fold, .pc-lane-strip")) return;
      selectedPool = pool.participant.id;
      selectedLane = null;
      if (onSelect) onSelect(pool.participant.id);
      draw();
      renderPalette();
    });

    /* A pool could be added and never removed: the delete op has handled a
     * participant all along - it takes the process and its activities with it -
     * but nothing on the canvas asked for it. */
    /* Collapse to the band. BPMN calls this a black-box pool and draws exactly
     * this: a participant whose internals are not the subject at hand. With
     * two pools on screen and only one being read, the other is scenery. */
    const fold = node("g", { class: "pc-pool-fold pc-marker", cursor: "pointer" }, group);
    node("rect", {
      x: pool.x + pool.w - 48, y: pool.y + 6, width: 18, height: 18, rx: 3,
      class: "pc-marker-box",
    }, fold);
    centred(fold, pool.x + pool.w - 39, pool.y + 19, pool.collapsed ? "+" : "−", "pc-marker-sign");
    node("title", {}, fold).textContent = pool.collapsed
      ? "Open this participant"
      : "Collapse this participant to a band";
    fold.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (collapsedPools.has(pool.participant.id)) collapsedPools.delete(pool.participant.id);
      else collapsedPools.add(pool.participant.id);
      draw();
    });

    if (onEdit) {
      const edit = node("g", { class: "pc-pool-edit", cursor: "pointer" }, group);
      node("rect", {
        x: pool.x + pool.w - 26, y: pool.y + 6, width: 18, height: 18, rx: 3,
        class: "pc-marker-box",
      }, edit);
      // The far corner: the near one carries the rotated pool name.
      centred(edit, pool.x + pool.w - 17, pool.y + 19, "⋯", "pc-marker-sign");
      node("title", {}, edit).textContent = "Rename this participant, add a lane, or delete it";
      edit.addEventListener("click", (ev) => {
        ev.stopPropagation();
        showPoolDetail(pool.participant, ev);
      });
    }
    // Three bars at the foot of the pool: BPMN's way of saying there are many
    // of this participant, not one.
    if (pool.participant.multiple) {
      const cx = pool.x + pool.w / 2;
      node("path", {
        d: `M ${cx - 5} ${pool.y + pool.h - 13} v 10 M ${cx} ${pool.y + pool.h - 13} v 10 `
          + `M ${cx + 5} ${pool.y + pool.h - 13} v 10`,
        class: "pc-multi",
      }, group);
      node("title", {}, group).textContent = `${pool.participant.label} (many)`;
    }
    /* The name runs down the strip while there is room for it. A collapsed
     * pool is 46px tall and the rotated name is longer than that, so it read
     * as a caption hanging off the band rather than the band's own name. */
    if (pool.collapsed) {
      text(group, pool.x + POOL_LABEL_W + 12, pool.y + pool.h / 2 + 4,
        truncate(pool.participant.label, 44), "pc-pool-label");
    } else {
      const label = centred(group, 0, 0, truncate(pool.participant.label, 24), "pc-pool-label");
      label.setAttribute(
        "transform",
        `translate(${pool.x + POOL_LABEL_W / 2}, ${pool.y + pool.h / 2}) rotate(-90)`
      );
    }

    if (pool.collapsed) return;

    // Lane bands: drawn only when the model declares them, so a plain process
    // is not given a boundary it never claimed.
    if (pool.showLanes) {
      pool.lanes.forEach((lane) => {
        const band = node("g", { class: "pc-lane" }, group);
        node("rect", {
          x: lane.x, y: lane.y, width: lane.w, height: lane.h, class: "pc-lane-box",
        }, band);
        node("rect", {
          x: lane.x, y: lane.y, width: LANE_LABEL_W, height: lane.h, class: "pc-lane-strip",
        }, band);
        if (lane.id === selectedLane) band.classList.add("selected");
        const caption = centred(band, 0, 0, truncate(lane.label || "", 22), "pc-lane-label");
        caption.setAttribute(
          "transform",
          `translate(${lane.x + LANE_LABEL_W / 2}, ${lane.y + 12 + (lane.h - 12) / 2}) rotate(-90)`
        );
        /* The whole band selects it, not the name strip alone. */
        band.addEventListener("click", (ev) => {
          if (ev.target.closest("[data-node], .pc-pool-edit, .pc-pool-fold, .pc-lane-edit")) {
            return;
          }
          ev.stopPropagation();
          selectedPool = pool.participant.id;
          selectedLane = lane.id || null;
          if (lane.id && onSelect) onSelect(lane.id);
          draw();
          renderPalette();
        });
        if (onEdit && lane.id) {
          /* The same handle a pool has. Renaming a lane was double-click only,
           * which is a gesture nothing on the canvas advertises - a reader who
           * had not been told simply could not rename or remove one. */
          const edit = node("g", { class: "pc-lane-edit", cursor: "pointer" }, band);
          node("rect", {
            x: lane.x + 3, y: lane.y + 4, width: LANE_LABEL_W - 6, height: 16, rx: 3,
            class: "pc-marker-box",
          }, edit);
          centred(edit, lane.x + LANE_LABEL_W / 2, lane.y + 16, "⋯", "pc-marker-sign");
          node("title", {}, edit).textContent = `Rename or delete the lane "${lane.label}"`;
          edit.addEventListener("click", (ev) => {
            ev.stopPropagation();
            showLaneDetail(lane, ev);
          });

          [band.querySelector(".pc-lane-strip"), caption].forEach((target) => {
            target.addEventListener("dblclick", (ev) => {
              ev.stopPropagation();
              showLaneDetail(lane, ev);
            });
          });
          node("title", {}, band).textContent = `Lane: ${lane.label}`
            + "\nClick to add steps here, double-click to rename";
        }
      });
    }

    // Sequence flow, from the model. Drawn under the nodes so a connector
    // never sits on top of a box it only passes.
    const edges = node("g", { class: "pc-edges" }, group);
    // Boundary events belong to the pool through their host, so a flow out of
    // one is drawn here rather than dropped for being outside the member set.
    const mine = new Set(pool.members.flatMap((m) => [m.id, ...(m.boundary || [])]));
    (data.sequenceFlows || []).forEach((flow) => {
      if (!mine.has(flow.source) && !mine.has(flow.target)) return;
      const from = placed.get(flow.source);
      const to = placed.get(flow.target);
      if (from && to) sequenceArrow(edges, from, to, flow);
    });

    pool.members.forEach((item) => {
      const slot = placed.get(item.id);
      if (!slot) return;
      if (item.shape === "activity") drawData(group, slot);
      const drawn = drawFlowNode(group, slot);
      drawn.setAttribute("data-node", item.id);
      if (item.shape !== "activity") wireSimpleNode(drawn, slot);
      (item.boundary || []).forEach((id) => {
        const attached = placed.get(id);
        if (attached) drawBoundary(group, attached).setAttribute("data-node", id);
      });
    });

    notes.filter((entry) => mine.has(entry.anchor)).forEach((entry) => {
      const drawn = drawNote(group, entry.note, entry.x, entry.y);
      const host = placed.get(entry.anchor);
      if (host) {
        node("path", {
          d: `M ${entry.x + 4} ${entry.y + 6} L ${host.x + host.w / 2} ${host.y + host.h}`,
          class: "pc-assoc",
        }, drawn.group);
      }
    });
  });

  // message flow: what crosses a boundary between actors
  (data.messageFlows || []).forEach((flow) => {
    const from = placed.get(flow.source);
    const to = placed.get(flow.target);
    if (from && to) messageArrow(root, from, to, flow.message || flow.label, flow.id);
  });

  drawPickedBadge(root);
  if (structureKey() !== lastFitIds && fit()) return;
  applyView();
}

/* Coalesced onto animation frames: a drag fires pointermove far faster than a
   whole process can be rebuilt, and a canvas that trails the cursor reads as
   stiffness. */
function redraw() {
  if (pendingFrame) return;
  pendingFrame = requestAnimationFrame(() => {
    pendingFrame = 0;
    draw();
  });
}

/* The connector handle is measured on screen, not in the diagram. */
const PORT_SCREEN_R = 7;
let portsSizedAt = null;

function sizePorts() {
  if (!root || portsSizedAt === view.k) return;
  portsSizedAt = view.k;
  const scale = view.k || 1;
  root.querySelectorAll(".pc-port-dot").forEach((dot) => {
    dot.setAttribute("r", PORT_SCREEN_R / scale);
    dot.setAttribute("stroke-width", 1.5 / scale);
  });
}

function applyView() {
  if (root) root.setAttribute("transform", `translate(${view.x} ${view.y}) scale(${view.k})`);
  sizePorts();
}

/* Fit under the palette, not behind it. */
function paletteInset() {
  const palette = document.querySelector("#process-palette");
  if (!palette || palette.classList.contains("hidden")) return 0;
  const height = palette.getBoundingClientRect().height;
  return height ? height + 18 : 0;
}

function fit() {
  if (!root || !svg) return;
  // The canvas is hidden while the reader is on the architecture level, so the
  // palette could not measure itself against it until now.
  renderPalette();
  const box = root.getBBox();
  const rect = svg.getBoundingClientRect();
  if (!box.width || !box.height || !rect.width) return false;
  /* Capped at half the canvas. */
  const inset = Math.min(paletteInset(), rect.height * 0.5);
  const usable = Math.max(rect.height - inset, 140);
  const k = Math.min(rect.width / (box.width + 60), usable / (box.height + 60), 1.2);
  view = {
    k,
    x: (rect.width - box.width * k) / 2 - box.x * k,
    y: inset + (usable - box.height * k) / 2 - box.y * k,
  };
  applyView();
  // Whoever asked for the fit, this is now the model the view was fitted to -
  // or the first click after showing the canvas would snap it back again.
  lastFitIds = structureKey();
  return true;
}

function initPanZoom() {
  /* Capture only once a drag is really under way: capturing on pointerdown
   * retargets the following click to the <svg> and no box ever opens.
   * Covered by test_canvas_interaction.py. */
  const DRAG_THRESHOLD = 4;
  let pan = null;

  window.addEventListener("keydown", async (ev) => {
    if (ev.key !== "Delete" && ev.key !== "Backspace") return;
    if (!pickedFlow) return;
    const on = document.activeElement;
    if (on && on.closest && on.closest("input, textarea, select, [contenteditable]")) return;
    ev.preventDefault();
    const id = pickedFlow;
    pickedFlow = null;
    if (onEdit) await onEdit("disconnect", { flow: id });
  });
  svg.addEventListener("pointerdown", (ev) => {
    // Clear here: a flag left armed eats the next real click.
    swallowNextClick = false;
    if (ev.target.closest(".pc-open, .pc-marker, .pc-port, .pc-edit, .pc-risk")) return;
    // A press anywhere else puts a picked connector down, like any selection.
    if (pickedFlow && !ev.target.closest(".pc-flow-hit, .pc-flow-drop")) {
      pickedFlow = null;
      redraw();
    }
    closeDetail();
    /* Pressed on a box: the same gesture moves it, the way the architecture
       canvas does. Only a flow node of an open pool moves - a collapsed pool
       draws nothing inside to move. */
    const hit = ev.target.closest("[data-node]");
    const box = hit && hit.getAttribute("data-node");
    const drawnAt = box ? currentPlacement(box) : null;
    pan = {
      id: ev.pointerId,
      fromX: ev.clientX, fromY: ev.clientY,
      originX: view.x, originY: view.y,
      node: drawnAt ? box : null,
      nodeFrom: drawnAt ? svgPoint(ev.clientX, ev.clientY) : null,
      nodeOrigin: drawnAt ? { x: drawnAt.x, y: drawnAt.y } : null,
      moved: false,
    };
  });

  svg.addEventListener("pointermove", (ev) => {
    if (connecting) { moveConnect(ev); return; }
    if (!pan) return;
    const dx = ev.clientX - pan.fromX;
    const dy = ev.clientY - pan.fromY;
    if (!pan.moved) {
      if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
      pan.moved = true;
      svg.classList.add(pan.node ? "dragging-node" : "panning");
      try { svg.setPointerCapture(pan.id); } catch (error) { /* already gone */ }
    }
    if (pan.node) {
      // In diagram units, so the box tracks the pointer at any zoom.
      const at = svgPoint(ev.clientX, ev.clientY);
      manualPositions.set(pan.node, {
        x: Math.round(pan.nodeOrigin.x + at.x - pan.nodeFrom.x),
        y: Math.round(pan.nodeOrigin.y + at.y - pan.nodeFrom.y),
      });
      redraw();
      return;
    }
    view.x = pan.originX + dx;
    view.y = pan.originY + dy;
    applyView();
  });

  const release = (ev) => {
    if (connecting) endConnect(ev);
    if (pan && pan.moved) {
      svg.classList.remove("panning", "dragging-node");
      try { svg.releasePointerCapture(pan.id); } catch (error) { /* already gone */ }
      // A move is a move, never also a click that opens the box's editor.
      swallowNextClick = true;
    }
    pan = null;
  };
  // Consumed in the capture phase, so the flag cannot outlive one gesture.
  svg.addEventListener("click", (ev) => {
    if (!swallowNextClick) return;
    swallowNextClick = false;
    ev.stopPropagation();
    ev.preventDefault();
  }, true);

  svg.addEventListener("pointerup", release);
  svg.addEventListener("pointercancel", release);
  svg.addEventListener("lostpointercapture", () => {
    svg.classList.remove("panning", "dragging-node");
    pan = null;
  });
  // A press released off the window still has to end - never leave a drag armed.
  window.addEventListener("blur", () => {
    svg.classList.remove("panning", "dragging-node");
    pan = null;
  });

  svg.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const factor = ev.deltaY < 0 ? 1.1 : 0.9;
    const rect = svg.getBoundingClientRect();
    const cx = ev.clientX - rect.left;
    const cy = ev.clientY - rect.top;
    // Clamped, like the other canvases: past these a diagram is a dot or a pixel.
    const next = Math.min(3, Math.max(0.15, view.k * factor));
    const ratio = next / view.k;
    view.x = cx - (cx - view.x) * ratio;
    view.y = cy - (cy - view.y) * ratio;
    view.k = next;
    applyView();
  }, { passive: false });
}

/* Grouped the way a BPMN palette is: what starts and ends a process, what
 * splits it, what does the work, and what says something about it. */
const PALETTE = [
  { group: "Pool", op: "add-pool", label: "Participant", hint: "A pool: an actor with a boundary" },
  { group: "Pool", op: "add-lane", label: "Lane", hint: "A band inside a pool: who does the work" },

  { group: "Events", op: "add-event", kind: "startEvent", label: "Start",
    hint: "Where the process begins" },
  { group: "Events", op: "add-event", kind: "startEvent", definition: "message",
    label: "Message start", hint: "Begins when a message arrives" },
  { group: "Events", op: "add-event", kind: "startEvent", definition: "timer",
    label: "Timer start", hint: "Begins on a schedule" },
  { group: "Events", op: "add-event", kind: "intermediateCatchEvent", definition: "message",
    label: "Message catch", hint: "Waits for a message part-way through" },
  { group: "Events", op: "add-event", kind: "intermediateThrowEvent", definition: "message",
    label: "Message throw", hint: "Sends a message part-way through" },
  { group: "Events", op: "add-event", kind: "endEvent", label: "End",
    hint: "Where this path of the process finishes" },
  { group: "Events", op: "add-event", kind: "endEvent", definition: "error",
    label: "Error end", hint: "Finishes by raising an error" },

  { group: "Gateways", op: "add-gateway", kind: "exclusiveGateway", label: "XOR",
    hint: "Exclusive: exactly one path is taken" },
  { group: "Gateways", op: "add-gateway", kind: "parallelGateway", label: "AND",
    hint: "Parallel: every path is taken" },
  { group: "Gateways", op: "add-gateway", kind: "inclusiveGateway", label: "OR",
    hint: "Inclusive: one or more paths are taken" },
  { group: "Gateways", op: "add-gateway", kind: "eventBasedGateway", label: "Event",
    hint: "Event-based: whichever event happens first decides" },

  { group: "Activities", kind: "task", label: "Task", hint: "A step of work" },
  { group: "Activities", kind: "userTask", label: "User task",
    hint: "A person does it - and can review what an AI produced" },
  { group: "Activities", kind: "serviceTask", label: "Service task",
    hint: "Automated: where an AI capability usually sits" },
  { group: "Activities", kind: "businessRuleTask", label: "Rule task",
    hint: "Decides by a rule, not by a model" },
  { group: "Activities", kind: "sendTask", label: "Send", hint: "Sends a message" },
  { group: "Activities", kind: "receiveTask", label: "Receive", hint: "Waits for a message" },
  { group: "Activities", kind: "subProcess", label: "Sub-process",
    hint: "Has a flow of its own, and may name an architecture" },
  { group: "Activities", kind: "callActivity", label: "Call",
    hint: "Calls a process defined elsewhere" },
  { group: "Activities", kind: "transaction", label: "Transaction",
    hint: "Completes as a whole or compensates" },

  { group: "Artifacts", op: "add-annotation", label: "Note",
    hint: "A text annotation: says something about a step without being one" },
];

/* The palette draws the shape it inserts, at the size it can be recognised at. */
function paletteIcon(item) {
  const icon = document.createElementNS(SVG_NS, "svg");
  icon.setAttribute("class", "pp-icon");
  icon.setAttribute("viewBox", "0 0 30 24");
  icon.setAttribute("aria-hidden", "true");

  if (item.op === "add-pool") {
    node("rect", { x: 2, y: 4, width: 26, height: 16, class: "pc-pool-box" }, icon);
    node("rect", { x: 2, y: 4, width: 6, height: 16, class: "pc-pool-strip" }, icon);
  } else if (item.op === "add-lane") {
    node("rect", { x: 2, y: 4, width: 26, height: 16, class: "pc-pool-box" }, icon);
    node("path", { d: "M 2 12 H 28", class: "pc-lane-box" }, icon);
    node("rect", { x: 2, y: 4, width: 5, height: 16, class: "pc-lane-strip" }, icon);
  } else if (item.op === "add-event") {
    eventShape(icon, 15, 12, {
      kind: item.kind, definition: item.definition || null,
      throwing: item.kind.startsWith("intermediateThrow") || item.kind === "endEvent",
      interrupting: true,
    }, 10);
  } else if (item.op === "add-gateway") {
    node("path", { d: "M 15 2 L 26 12 L 15 22 L 4 12 Z", class: "pc-gate-box" }, icon);
    const mark = gatewayMark(icon, item.kind, 15, 12);
    mark.setAttribute("transform", "translate(15 12) scale(0.62)");
  } else if (item.op === "add-annotation") {
    node("path", { d: "M 10 4 H 4 V 20 H 10", class: "pc-note-bracket" }, icon);
    node("path", { d: "M 13 9 H 26 M 13 13 H 26 M 13 17 H 22", class: "pc-note-rule" }, icon);
  } else {
    node("rect", {
      x: 2, y: 4, width: 26, height: 16, rx: 3,
      class: `pc-box${item.kind === "callActivity" ? " call" : ""}`,
    }, icon);
    if (item.kind === "transaction") {
      node("rect", { x: 4, y: 6, width: 22, height: 12, rx: 2, class: "pc-box inner" }, icon);
    }
    const glyph = typeMarker(icon, item.kind, 4, 6);
    glyph.setAttribute("transform", "translate(4 6) scale(0.95)");
    if (item.kind === "subProcess") {
      node("rect", { x: 12, y: 14, width: 7, height: 7, class: "pc-mk-box" }, icon);
      node("path", { d: "M 15.5 15.5 V 19.5 M 13.5 17.5 H 17.5", class: "pp-icon-plus" }, icon);
    }
  }
  return icon;
}

/* Twenty-four buttons in five sections is a reasonable toolbar on a wide screen
 * and the whole canvas on a small one: at 800px it left the diagram a strip at
 * the bottom. Rather than guess at breakpoints, measure - a toolbar that takes
 * a third of the canvas is in the way, whatever the screen is. It only ever
 * folds itself; unfolding is the reader's to do, and once they have chosen the
 * choice sticks. */
const PALETTE_SHARE = 0.34;

/* Decided by measuring the palette against the canvas, both ways, every time. */
function autoFoldPalette(host) {
  if (paletteTouched || !svg) return;
  const rect = svg.getBoundingClientRect();
  const height = host.getBoundingClientRect().height;
  if (!rect.height || !height) return;
  paletteFolded = height > rect.height * PALETTE_SHARE;
}

function renderPalette() {
  const host = document.querySelector("#process-palette");
  if (!host || !onEdit) return;
  buildPalette(host);
  const wasFolded = paletteFolded;
  autoFoldPalette(host);
  if (paletteFolded !== wasFolded) buildPalette(host);
}

function buildPalette(host) {
  host.innerHTML = "";
  host.classList.toggle("folded", paletteFolded);
  const pool = data && data.participants.find((p) => p.id === selectedPool);

  /* The palette grew from seven buttons to twenty-four when it started
   * offering the whole notation, and three rows of them sat over the diagram
   * they were for. It folds to its handle. */
  const fold = document.createElement("button");
  fold.type = "button";
  fold.className = "pp-fold";
  fold.textContent = paletteFolded ? "▸ Add" : "▾ Add";
  fold.title = paletteFolded ? "Show the BPMN palette" : "Fold the palette away";
  fold.addEventListener("click", () => {
    paletteTouched = true;
    paletteFolded = !paletteFolded;
    buildPalette(host);
    fit();
  });
  host.appendChild(fold);
  if (paletteFolded) return;

  /* Each category is its own block, not a label floating in a run of buttons.
   * Inline, the headings wrapped into the middle of a row and the reader could
   * not see where the gateways stopped and the activities began. */
  const sections = new Map();
  PALETTE.forEach((item) => {
    if (!sections.has(item.group)) {
      const section = document.createElement("div");
      section.className = "pp-section";
      const heading = document.createElement("span");
      heading.className = "pp-group";
      heading.textContent = item.group;
      section.appendChild(heading);
      host.appendChild(section);
      sections.set(item.group, section);
    }
    const section = sections.get(item.group);
    const needsPool = item.op !== "add-pool";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pp-item";
    button.appendChild(paletteIcon(item));
    button.appendChild(document.createTextNode(item.label));
    button.title = needsPool && !pool ? `${item.hint} — click a participant first` : item.hint;
    button.disabled = needsPool && !pool;
    button.addEventListener("click", async () => {
      if (item.op === "add-pool") {
        const label = window.prompt("Name of the participant (an organisation, a customer, a team):");
        if (label) await onEdit("add-pool", { label });
        return;
      }
      if (item.op === "add-lane") {
        const label = window.prompt("Name of the lane (a role, a team, a system):");
        if (label) await onEdit("add-lane", { pool: selectedPool, label });
        return;
      }
      const where = { pool: selectedPool, lane: selectedLane };
      if (item.op === "add-event") {
        await onEdit("add-event", {
          ...where, kind: item.kind, definition: item.definition || "", label: "",
        });
      } else if (item.op === "add-gateway") {
        await onEdit("add-gateway", { ...where, kind: item.kind, label: "" });
      } else if (item.op === "add-annotation") {
        const body = window.prompt("What should the note say?");
        if (body) await onEdit("add-annotation", { ...where, text: body });
      } else {
        await onEdit("add-activity", { ...where, kind: item.kind, label: item.label });
      }
    });
    section.appendChild(button);
  });
  const note = document.createElement("span");
  note.className = "pp-note";
  const lane = data && (data.lanes || []).find((l) => l.id === selectedLane);
  note.textContent = pool
    ? `adding to: ${pool.label}${lane ? ` › ${lane.label}` : ""}`
    : "click a participant to add steps to it";
  host.appendChild(note);
  // Visibility belongs to the level switch, not to render.
}

function init(options) {
  svg = document.querySelector(options.svg);
  onOpenArchitecture = options.onOpenArchitecture || null;
  onEdit = options.onEdit || null;
  onSelect = options.onSelect || null;
  if (svg) initPanZoom();
  /* A window that changes size changes how much room the diagram has, and the
   * fit is computed from that room. Without this the canvas kept the scale it
   * was given when the page loaded. */
  let resizing = null;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizing);
    resizing = window.setTimeout(() => {
      renderPalette();
      fit();
    }, 120);
  });
  // Built now: the palette is how an empty process gets its first participant.
  renderPalette();
}

function setSystems(list) { systems = list || []; }
function setDataClasses(list) { dataClasses = list || []; }

/** Candidate risks per business activity, from the last assessment. */
function setFindings(rows) {
  findingsByActivity = new Map((rows || []).map((row) => [row.id, row]));
  const known = new Set(findingsByActivity.keys());
  openRisks = new Set([...openRisks].filter((id) => known.has(id)));
  if (data) draw();
}

function render(next) {
  data = next;
  index = buildIndex(next);
  // Keep an activity open across a re-render, but forget one that is gone.
  expanded = new Set([...expanded].filter((id) => index.has(id)));
  const pools = new Set(next.participants.map((p) => p.id));
  if (!pools.has(selectedPool)) selectedPool = next.participants.length ? next.participants[0].id : null;
  const lanes = new Set((next.lanes || []).map((l) => l.id));
  if (!lanes.has(selectedLane)) selectedLane = null;
  collapsedPools = new Set([...collapsedPools].filter((id) => pools.has(id)));
  draw();
  renderPalette();
}

function hasProcess() {
  return Boolean(data && data.stats && data.stats.activities);
}

/* A different document: positions from the last one would land on boxes that
   are not the same boxes, and the next render should fit what it draws. */
function forgetLayout() {
  manualPositions = new Map();
  lastFitIds = null;
}

export const ProcessCanvas = {
  init, render, fit, hasProcess, setSystems, setDataClasses, setFindings, forgetLayout,
  svgRoot: () => svg,
};
