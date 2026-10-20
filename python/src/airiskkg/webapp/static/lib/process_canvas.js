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
const TAP_SLOP = 5;   // a press that moves less than this is a click, not a drag
const DATA_BAND = 92;
const NOTE_W = 150;
const RISK_LINE_H = 14;
const CHILD_H = 30;
const BAND_H = 20;       // a participant band on a choreography activity
const ENV_PAD = 28;      // room above and below a choreography task for its messages
const CONV_R = 20;       // a conversation hexagon
const CONV_ROW = 110;    // the strip conversations sit in, between the pools

let svg = null;
let root = null;
let data = null;
let index = null;             // id -> normalised flow node, built per render
let expanded = new Set();
let onOpenArchitecture = null;
let onEdit = null;
let onSelect = null;
let pickedFlow = null;
let pendingBadge = null;

let topLayer = null;
let systems = [];
let refinedSystems = [];
let contextOptions = [];
let dataClasses = [];
let selectedPool = null;
let selectedLane = null;      // where a new node lands inside a banded pool
let selectedModel = null;     // which bpmn:collaboration is drawn
let wantedModel = null;       // one just made, opened once it arrives
let connecting = null;
let swallowNextClick = false;
let picked = new Set();       // shift-clicked nodes, deleted together
let onPick = null;
let findingsByActivity = new Map();
let openRisks = new Set();
let view = { x: 0, y: 0, k: 1 };
let paletteFolded = false;
let paletteTouched = false;       // once the reader chooses, the choice sticks
let collapsedPools = new Set();   // BPMN black-box pools: banded, not opened

let manualPositions = new Map();
let bandHeights = new Map();      // dragged band heights, view-only like a dragged box
let poolWidth = 0;
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


export function humanKind(kind) {
  const local = String(kind).split(/[#:/]/).pop();
  const spaced = local.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

function dataOf(activity) {
  if (!activity.reads) return [];
  const seen = new Map();
  [...activity.reads.map((d) => ({ ...d, direction: "in" })),
    ...activity.writes.map((d) => ({ ...d, direction: "out" }))].forEach((d) => {
    const had = seen.get(d.id);
    // a step that reads and writes one box draws it once, with an arrow each way
    seen.set(d.id, had ? { ...had, direction: "both" } : d);
  });
  return [...seen.values()];
}

const DIRECTION_WORDS = { in: "reads", out: "writes", both: "reads and writes" };

function riskOf(item) {
  return findingsByActivity.get(item.id) || null;
}

/* The candidate risks an activity carries, each named once and wrapped rather than cut. */
function riskLines(risk) {
  const counts = new Map();
  risk.items.forEach((entry) => {
    const name = String(entry.label).replace(/^Candidate\s+/i, "");
    counts.set(name, (counts.get(name) || 0) + 1);
  });
  return [...counts.entries()].map(([name, n]) => {
    const text = name.charAt(0).toUpperCase() + name.slice(1) + (n > 1 ? ` (×${n})` : "");
    return wrap(text, 30, 2);
  });
}

/** Every flow node of the model in one table, tagged with how it is drawn. */
function buildIndex(model) {
  const table = new Map();
  (model.activities || []).forEach((a) => table.set(a.id, { ...a, shape: "activity" }));
  (model.events || []).forEach((e) => table.set(e.id, { ...e, shape: "event" }));
  (model.gateways || []).forEach((g) => table.set(g.id, { ...g, shape: "gateway" }));
  (model.choreographyActivities || []).forEach((c) => table.set(c.id, { ...c, shape: "choreography" }));
  return table;
}

function nameRoomOf(activity) {
  return riskOf(activity) && riskOf(activity).findings ? 19 : 28;
}

function headHeight(activity) {
  const lines = wrap(activity.label, nameRoomOf(activity), 2).length;
  return BOX_H + (lines - 1) * LINE_H;
}


function footprintOf(item) {
  const { w } = sizeOf(item);
  if (item.shape === "activity" || item.shape === "choreography" || !item.label) return w;
  const longest = Math.max(...wrap(item.label, 18, 2).map((line) => line.length));
  return Math.max(w, longest * 5.6);
}

function sizeOf(item) {
  if (item.shape === "event") return { w: EVENT_R * 2, h: EVENT_R * 2 };
  if (item.shape === "gateway") return { w: GATE_R * 2, h: GATE_R * 2 };
  if (item.shape === "choreography") {
    const messages = item.bands.some((band) => band.message) ? ENV_PAD * 2 : 0;
    return { w: BOX_W, h: BOX_H + Math.max(2, item.bands.length) * BAND_H + messages };
  }
  let h = headHeight(item);
  if (expanded.has(item.id) && item.children.length) {
    h += item.children.length * CHILD_H + 10;
  }
  const risk = riskOf(item);
  if (risk && openRisks.has(item.id)) h += riskLines(risk).flat().length * RISK_LINE_H + 16;
  return { w: BOX_W, h };
}


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

  
  [...ids].sort((a, b) => rank.get(b) - rank.get(a)).forEach((id) => {
    const onward = succ.get(id).filter((n) => rank.get(n) > rank.get(id)).map((n) => depth.get(n));
    depth.set(id, onward.length ? Math.max(...onward) + 1 : 0);
  });

  return { rank, pred, depth };
}


function lanesOf(model, processId) {
  const bands = (model.lanes || []).filter((lane) => lane.process === processId);
  /* Declaration order, and nothing else. */
  bands.sort((a, b) => (a.line ?? Infinity) - (b.line ?? Infinity)
    || a.id.localeCompare(b.id, undefined, { numeric: true }));
  return bands;
}


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

  /* A choreography is laid out like a process, inside a frame instead of a
   * pool; a participant it names only on its bands gets no pool of its own. */
  const frames = [
    ...(data.participants || []).filter((participant) => !participant.bandOnly
      && inModel(participant.id)),
    ...(data.choreographies || []).map((chor) => ({
      id: chor.id, label: chor.label, process: chor.id, multiple: false, choreography: true,
    })),
  ];
  const conversations = data.conversations || [];
  let conversationY = null;
  const reserveConversations = () => {
    if (!conversations.length || conversationY !== null) return;
    conversationY = poolY;
    poolY += CONV_ROW;
  };

  frames.forEach((participant, seat) => {
    // Between the first pool and the rest, so its links reach both ways.
    if (seat === 1) reserveConversations();
    const members = [...index.values()].filter(
      (item) => !item.parent && !item.attachedTo && item.process
        && item.process === participant.process
    );

   
    const blackBox = !participant.process;
    if (blackBox || collapsedPools.has(participant.id)) {
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
        participant, ...band, lanes: [], members, showLanes: false, collapsed: true, blackBox,
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
      const key = band.id || participant.id;
      laneH = Math.max(laneH, laneBottom - laneY, bandHeights.get(key) || 0);
      attached.forEach(([noteId, anchor], seat) => {
        const host = placed.get(anchor);
        notes.push({
          note: (data.artifacts || []).find((a) => a.id === noteId),
          x: (host ? host.x : columnX.get(0)) + seat * (NOTE_W + 12),
          y: rowY.get(noteRow), anchor,
        });
      });

      drawnBands.push({ ...band, key, x: POOL_LABEL_W, y: laneY, w: poolW - POOL_LABEL_W, h: laneH });
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

  reserveConversations();
  const widest = Math.max(POOL_LABEL_W + BOX_W, poolWidth, ...pools.map((pool) => pool.w));
  pools.forEach((pool) => {
    pool.w = widest;
    pool.lanes.forEach((lane) => { lane.w = widest - POOL_LABEL_W; });
  });

  // Spread along the strip, centred, each at its own place on the row.
  const step = CONV_R * 2 + 90;
  const startX = Math.max(POOL_LABEL_W + 20,
    POOL_LABEL_W + (widest - POOL_LABEL_W - step * (conversations.length - 1)) / 2 - CONV_R);
  conversations.forEach((item, seat) => {
    const hand = manualPositions.get(item.id);
    const x = hand ? hand.x : startX + seat * step;
    const y = hand ? hand.y : conversationY + CONV_ROW / 2 - CONV_R - 8;
    placed.set(item.id, {
      x, y, w: CONV_R * 2, h: CONV_R * 2, item: { ...item, shape: "conversation" },
      band: 0, head: CONV_R * 2,
    });
  });

  return { pools, placed, notes, height: poolY };
}

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
  } else if (kind === "multiple") {
    node("path", { d: "M 0 -7.5 L 7.1 -2.3 L 4.4 6.1 H -4.4 L -7.1 -2.3 Z", class: "pc-ev-mark" }, g);
  } else if (kind === "parallelMultiple") {
    node("path", {
      d: "M -2 -7 H 2 V -2 H 7 V 2 H 2 V 7 H -2 V 2 H -7 V -2 H -2 Z", class: "pc-ev-mark",
    }, g);
  }
  return g;
}

/* A start event is a thin ring, an intermediate one a double ring, an end
 * event a thick one. A non-interrupting boundary event dashes both rings, and
 * a non-interrupting start event (of an event sub-process) dashes its one. */
function eventShape(parent, cx, cy, item, radius = EVENT_R) {
  const dashed = (item.kind === "boundaryEvent" || item.kind === "startEvent")
    && item.interrupting === false;
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
  const triggers = (item.definitions || []).length > 1
    ? ` (${item.definitions.map(humanKind).join(item.definition === "parallelMultiple"
      ? " and " : " or ")})` : "";
  hint.textContent = `${item.label || humanKind(item.kind)}\n${humanKind(item.kind)}`
    + (item.definition ? ` — ${humanKind(item.definition)}${triggers}` : "")
    + (item.definitionLabel ? `: ${item.definitionLabel}` : "")
    + (item.kind === "startEvent" && item.interrupting === false ? "\nNon-interrupting" : "");
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


function centreOf(slot) {
  return { x: slot.x + (slot.w || 0) / 2, y: slot.y + (slot.h || 0) / 2 };
}

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
  // A default flow carries a tick through its tail; a conditional one a diamond,
  // but only out of an activity: a gateway's branches carry their condition plain.
  const start = points[0];
  const after = points[1];
  const fromGateway = (index.get(flow.source) || {}).shape === "gateway";
  if (flow.default) {
    const dx = Math.sign(after.x - start.x) || 0;
    const dy = Math.sign(after.y - start.y) || 0;
    node("path", {
      d: `M ${start.x + dx * 5 - 4 - dy * 4} ${start.y + dy * 5 - 4 + dx * 4} `
        + `L ${start.x + dx * 12 + 4 - dy * 4} ${start.y + dy * 12 + 4 + dx * 4}`,
      class: "pc-flow-tick",
    }, group);
  } else if (flow.condition && !fromGateway) {
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
  /* On the longest segment of the route; a branch with no name shows its condition. */
  const caption = flow.label || flow.condition;
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


function onPoolEdge(pool, other) {
  if (!pool) return null;
  const want = other ? other.x + other.w / 2 : pool.x + pool.w / 2;
  const x = Math.min(Math.max(want, pool.x + POOL_LABEL_W + 12), pool.x + pool.w - 12);
  return { x: x - 1, y: pool.y, w: 2, h: pool.h };
}

/** A message crosses a boundary: leave the source downward, enter the target. */
function envelope(parent, cx, cy, shaded) {
  const g = node("g", { class: `pc-env${shaded ? " shaded" : ""}` }, parent);
  node("rect", { x: cx - 9, y: cy - 6, width: 18, height: 12, rx: 1, class: "pc-env-box" }, g);
  node("path", { d: `M ${cx - 9} ${cy - 6} L ${cx} ${cy + 1} L ${cx + 9} ${cy - 6}`, class: "pc-env-fold" }, g);
  return g;
}

function messageArrow(parent, from, to, label, id, message) {
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
  // A message the flow names is drawn as BPMN draws it: an envelope on the line.
  const midX = (a.x + b.x) / 2;
  wireConnector(group, orthPath(points), id, picked, points);
  if (message) {
    envelope(group, midX, midY, false);
    text(group, midX + 13, midY + 4, truncate(label, 24), "pc-flow-label");
  } else if (label) {
    centred(group, midX, midY - 5, truncate(label, 26), "pc-flow-label");
  }
}


function wireConnector(group, d, id, picked, points) {
  if (!id) return;
  const hit = node("path", { d, class: "pc-flow-hit", fill: "none" }, group);
  hit.addEventListener("pointerdown", (ev) => {
    ev.stopPropagation();
    const opening = !picked;
    pickedFlow = opening ? id : null;
    if (opening) showFlowDetail(id, ev); else closeDetail();
    redraw();
  });
  if (!picked) return;
  // On the longest run, so the badge does not land on a corner.
  let best = null;
  for (let i = 1; i < points.length; i += 1) {
    const run = Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
    if (!best || run > best.run) best = { run, from: points[i - 1], to: points[i] };
  }
 
  pendingBadge = {
    id,
    at: best
      ? { x: (best.from.x + best.to.x) / 2, y: (best.from.y + best.to.y) / 2 }
      : points[0],
  };
}


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


function dataAssociation(parent, x1, y1, x2, y2, both = false) {
  node("path", {
    d: `M ${x1} ${y1} L ${x2} ${y2}`,
    class: "pc-data-link",
    "marker-end": "url(#pc-arrow-data)",
    ...(both ? { "marker-start": "url(#pc-arrow-data)" } : {}),
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
    // The same box, the same editor, whether it was placed or born in a step.
    g.setAttribute("data-node", item.id);
    wireDataNode(g, { ...item, links: item.links || [{ direction: item.direction }] },
      { x: cx - DATA_W / 2, y: top });
    if (item.direction === "both") {
      dataAssociation(g, cx, top + DATA_H + 2, cx, slot.y - 4, true);
    } else if (item.direction === "in") {
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
    title.textContent = `${item.label} — ${{ in: "read by", out: "written by", both: "read and written by" }[item.direction]} `
      + `${slot.item.label}`
      + (item.kinds.length
        ? `\nClassified: ${item.kinds.join(", ")}`
        : "\nNot classified");
  });
}

function childrenOf(activity) {
  return activity.children.map((id) => index.get(id)).filter(Boolean);
}


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
      // An event inside is drawn as itself, so its trigger and ring still read.
      if (child.shape === "event") {
        eventShape(group, slot.x + 29, cy + 12, child, 9);
        text(group, slot.x + 44, cy + 16, truncate(child.label, 24), "pc-child-label");
      } else {
        const glyph = child.shape === "gateway" ? "◇ " : "";
        text(group, slot.x + 22, cy + 18, glyph + truncate(child.label, 26), "pc-child-label");
      }
    });
  }

  // Candidate risks for this activity; the badge folds the list.
  const risk = riskOf(item);
  if (risk && risk.findings) {
    const open = openRisks.has(item.id);
    const badge = node("g", { class: "pc-risk", cursor: "pointer" }, topLayer || group);
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
      const rows = riskLines(risk);
      let rowY = slot.y + slot.h - rows.flat().length * RISK_LINE_H - 8;
      rows.forEach((lines) => {
        lines.forEach((line, at) => {
          text(group, slot.x + 18, rowY + 11, `${at ? "  " : "• "}${line}`, "pc-risk-item");
          rowY += RISK_LINE_H;
        });
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

    // A message leaves from the bottom, the way BPMN draws it between pools.
    // Off the centre, where message flows already drawn attach and would cover it.
    const mail = node("g", { class: "pc-port pc-port-message", cursor: "crosshair" }, group);
    node("circle", {
      cx: slot.x + slot.w / 4, cy: slot.y + slot.head, r: PORT_SCREEN_R, class: "pc-port-dot",
    }, mail);
    mail.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
      startConnect(ev, item, slot, "message");
    });
    node("title", {}, mail).textContent =
      "Drag onto a step in another participant to send it a message";
    // a dot sized in screen pixels grows over the chip when zoomed out: the chip stays on top
    const chipNode = group.querySelector(":scope > .pc-open");
    if (chipNode) group.appendChild(chipNode);

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

/* The marker row BPMN shares between activities and choreography activities. */
function loopMarker(parent, loop, x, y) {
  const g = node("g", { class: "pc-mk", transform: `translate(${x} ${y})` }, parent);
  if (loop === "standard") node("path", { d: "M 12 4 a 5 5 0 1 0 1 5 M 12 1 v 3.5 h -3.5" }, g);
  if (loop === "multiParallel") node("path", { d: "M 3 2 v 11 M 7 2 v 11 M 11 2 v 11" }, g);
  if (loop === "multiSequential") node("path", { d: "M 2 4 h 11 M 2 7.5 h 11 M 2 11 h 11" }, g);
  return g;
}

/* A band is the strip of the box a participant takes, rounded with the box
 * where it is the top or the bottom edge. */
function bandPath(x, y, w, upper, rounded) {
  const r = rounded ? 10 : 0;
  if (upper) {
    return `M ${x} ${y + BAND_H} V ${y + r} Q ${x} ${y} ${x + r} ${y} H ${x + w - r} `
      + `Q ${x + w} ${y} ${x + w} ${y + r} V ${y + BAND_H} Z`;
  }
  return `M ${x} ${y} H ${x + w} V ${y + BAND_H - r} Q ${x + w} ${y + BAND_H} ${x + w - r} `
    + `${y + BAND_H} H ${x + r} Q ${x} ${y + BAND_H} ${x} ${y + BAND_H - r} Z`;
}

/* A choreography activity: the exchange in the middle, the initiating
 * participant's band on top and the others below, each band's message in an
 * envelope beyond it - open when the initiator sends it, shaded when it is the
 * reply. Which band goes on top is BPMNDI, which sBPMN does not carry. */
function drawChoreography(parent, slot) {
  const { item } = slot;
  const group = node("g", { class: `pc-chor ${item.kind}` }, parent);
  const pad = item.bands.some((band) => band.message) ? ENV_PAD : 0;
  const x = slot.x;
  const w = slot.w;
  const y = slot.y + pad;
  const h = slot.h - pad * 2;
  node("rect", {
    x, y, width: w, height: h, rx: 10,
    class: `pc-chor-box${item.kind === "callChoreography" ? " call" : ""}`,
  }, group);

  const lower = item.bands.slice(1);
  const rows = [
    { band: item.bands[0] || null, y, upper: true, rounded: true },
    ...(lower.length ? lower : [null]).map((band, seat, all) => ({
      band,
      y: y + h - (all.length - seat) * BAND_H,
      upper: false,
      rounded: seat === all.length - 1,
    })),
  ];
  rows.forEach((row) => {
    const shaded = !row.band || !row.band.initiating;
    node("path", {
      d: bandPath(x, row.y, w, row.upper, row.rounded),
      class: `pc-chor-band${shaded ? " shaded" : ""}`,
    }, group);
    if (!row.band) return;
    centred(group, x + w / 2, row.y + 14, truncate(row.band.label, 30), "pc-chor-band-label");
    if (row.band.multiple) {
      const cx = x + w - 16;
      node("path", {
        d: `M ${cx - 4} ${row.y + 5} v 10 M ${cx} ${row.y + 5} v 10 M ${cx + 4} ${row.y + 5} v 10`,
        class: "pc-multi",
      }, group);
    }
  });

  const middleTop = y + BAND_H;
  const middleBottom = y + h - Math.max(1, lower.length) * BAND_H;
  const lines = wrap(item.label, 30, 2);
  const firstLine = (middleTop + middleBottom) / 2 - ((lines.length - 1) * LINE_H) / 2 + 2;
  lines.forEach((line, seat) => {
    centred(group, x + w / 2, firstLine + seat * LINE_H, line, "pc-label");
  });

  const marks = [];
  if (item.kind === "subChoreography") marks.push("sub");
  if (item.loop) marks.push(item.loop);
  marks.forEach((mark, seat) => {
    const mx = x + w / 2 - (marks.length * 20 - 6) / 2 + seat * 20;
    const my = middleBottom - 17;
    if (mark === "sub") {
      const g = node("g", { class: "pc-mk", transform: `translate(${mx} ${my})` }, group);
      node("rect", { x: 0, y: 0, width: 14, height: 14, class: "pc-mk-box" }, g);
      node("path", { d: "M 7 3 V 11 M 3 7 H 11" }, g);
    } else {
      loopMarker(group, mark, mx, my);
    }
  });

  // Only the outer two bands have room beyond them for an envelope.
  const outer = [
    { band: rows[0].band, edge: y, envY: slot.y + 9, label: slot.y + 13 },
    { band: rows[rows.length - 1].band, edge: y + h, envY: slot.y + slot.h - 9, label: slot.y + slot.h - 5 },
  ];
  outer.forEach(({ band, edge, envY, label }) => {
    if (!band || !band.message) return;
    const cx = x + w / 2;
    node("path", { d: `M ${cx} ${edge} L ${cx} ${envY + (envY < edge ? 6 : -6)}`, class: "pc-env-link" }, group);
    envelope(group, cx, envY, !band.initiating);
    text(group, cx + 14, label, truncate(band.message, 24), "pc-flow-label");
  });

  node("title", {}, group).textContent = `${item.label}\n${humanKind(item.kind)}\n`
    + item.bands.map((band) => `${band.label}${band.initiating ? " (initiates)" : ""}`
      + (band.message ? ` sends ${band.message}` : "")).join("\n");
  return group;
}

/* A conversation is a hexagon - thick for a call, with + for a sub-conversation. */
function drawConversation(parent, slot) {
  const { item } = slot;
  const cx = slot.x + slot.w / 2;
  const cy = slot.y + slot.h / 2;
  const group = node("g", { class: `pc-conv ${item.kind}` }, parent);
  const corners = [0, 1, 2, 3, 4, 5].map((seat) => {
    const angle = (Math.PI / 3) * seat;
    return `${cx + CONV_R * Math.cos(angle)} ${cy + CONV_R * Math.sin(angle)}`;
  });
  node("path", {
    d: `M ${corners.join(" L ")} Z`,
    class: `pc-conv-box${item.kind === "callConversation" ? " call" : ""}`,
  }, group);
  if (item.kind === "subConversation") {
    const g = node("g", { class: "pc-mk", transform: `translate(${cx - 5} ${cy + 4})` }, group);
    node("rect", { x: 0, y: 0, width: 10, height: 10, class: "pc-mk-box" }, g);
    node("path", { d: "M 5 2 V 8 M 2 5 H 8" }, g);
  }
  // Beside the hexagon: its links leave from the top and the bottom.
  const lines = wrap(item.label, 14, 2);
  lines.forEach((line, row) => {
    text(group, cx + CONV_R + 5, cy + 4 + (row - (lines.length - 1) / 2) * 11, line, "pc-ev-label");
  });
  node("title", {}, group).textContent = `${item.label}\n${humanKind(item.kind)}`;
  return group;
}

/* A conversation link is a double line from the hexagon to the pool's edge. */
function conversationLink(parent, slot, pool, id) {
  const cx = slot.x + slot.w / 2;
  const cy = slot.y + slot.h / 2;
  const above = pool.y + pool.h <= cy;
  const ey = above ? pool.y + pool.h : pool.y;
  const ex = Math.min(Math.max(cx, pool.x + POOL_LABEL_W + 12), pool.x + pool.w - 12);
  const sy = cy + (above ? -1 : 1) * CONV_R * 0.87;
  const midY = (sy + ey) / 2;
  const d = orthPath([{ x: cx, y: sy }, { x: cx, y: midY }, { x: ex, y: midY }, { x: ex, y: ey }]);
  const group = node("g", { class: "pc-conv-link" }, parent);
  if (id) group.setAttribute("data-flow", id);
  node("path", { d, class: "pc-conv-line" }, group);
  node("path", { d, class: "pc-conv-gap" }, group);
  return group;
}

function drawFlowNode(parent, slot) {
  if (slot.item.shape === "event") return drawEvent(parent, slot);
  if (slot.item.shape === "gateway") return drawGateway(parent, slot);
  if (slot.item.shape === "choreography") return drawChoreography(parent, slot);
  return drawActivity(parent, slot);
}

/* What the editor cannot yet change is still selectable, which reveals the
 * line that declares it. */
function wireSelectOnly(group, item) {
  group.setAttribute("cursor", "pointer");
  group.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (onSelect) onSelect(item.id);
  });
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


let lastPlaced = new Map();
let lastPools = [];


function structureKey() {
  return [
    ...lastPools.map((pool) => "pool:" + pool.participant.id),
    ...lastPools.flatMap((pool) => pool.lanes.map((lane) => "lane:" + pool.participant.id + "/" + lane.id)),
    ...lastPlaced.keys(),
  ].sort().join("|");
}


function bandsLike(id) {
  for (const pool of lastPools) {
    if (pool.participant.id === id) {
      return lastPools.map((other) => ({
        id: other.participant.id, x: other.x, w: other.w, y: other.y, h: other.h,
      }));
    }
    for (const lane of pool.lanes || []) {
      if (lane.id === id) {
        return (pool.lanes || []).map((other) => ({
          id: other.id, x: other.x, w: other.w, y: other.y, h: other.h,
        }));
      }
    }
  }
  return null;
}

function dropIndexAt(bands, id, y) {
  const others = bands.filter((band) => band.id !== id);
  let index = 0;
  for (const band of others) {
    if (y > band.y + band.h / 2) index += 1;
  }
  return Math.max(0, Math.min(index, others.length));
}

function showBandDrop(bands, id, index) {
  svg.querySelectorAll(".pc-band-drop").forEach((mark) => mark.remove());
  const others = bands.filter((band) => band.id !== id);
  if (!others.length) return;
  const last = others[others.length - 1];
  const edge = index >= others.length ? last.y + last.h : others[index].y;
  const x1 = Math.min(...others.map((band) => band.x));
  const x2 = Math.max(...others.map((band) => band.x + band.w));
  node("line", { class: "pc-band-drop", x1, y1: edge, x2, y2: edge }, root);
}


function currentPlacement(id) {
  const slot = lastPlaced.get(id);
  return slot && slot.item
    && ["activity", "event", "gateway", "data", "choreography", "conversation"]
      .includes(slot.item.shape)
    ? slot : null;
}

function svgPoint(clientX, clientY) {
  const rect = svg.getBoundingClientRect();
  return { x: (clientX - rect.left - view.x) / view.k, y: (clientY - rect.top - view.y) / view.k };
}

/* `kind` is "message" from the bottom port; otherwise the pools decide. */
function startConnect(ev, item, slot, kind = null, onTap = null) {
  const line = node("path", { class: "pc-flow pending" + (kind ? ` ${kind}` : "") }, root);
  const from = kind === "message"
    ? { x: slot.x + slot.w / 4, y: slot.y + (slot.head || slot.h) }
    : { x: slot.x + slot.w, y: slot.y + (slot.head || slot.h) / 2 };
  connecting = { from: item, slot, line, id: ev.pointerId, kind, anchor: from, onTap, at: [ev.clientX, ev.clientY] };
  // Held for the length of the drag so it survives leaving the port, and
  // released in endConnect - a capture left standing swallows every later
  // click on the canvas.
  try { svg.setPointerCapture(ev.pointerId); } catch (error) { /* already gone */ }
}

function moveConnect(ev) {
  if (!connecting) return;
  const to = svgPoint(ev.clientX, ev.clientY);
  const { x, y } = connecting.anchor;
  connecting.line.setAttribute("d", `M ${x} ${y} L ${to.x} ${to.y}`);
}

async function endConnect(ev) {
  if (!connecting) return;
  const { from, line, id, kind, onTap, at } = connecting;
  connecting = null;
  line.remove();
  try { svg.releasePointerCapture(id); } catch (error) { /* already gone */ }
  swallowNextClick = true;
  if (onTap && Math.hypot(ev.clientX - at[0], ev.clientY - at[1]) < TAP_SLOP) {
    onTap(ev);
    return;
  }
  const dropped = document.elementFromPoint(ev.clientX, ev.clientY);
  // The id travels on the element, so a drop lands on the node under the
  // pointer rather than on whatever was drawn in that position.
  const group = dropped && dropped.closest("[data-node]");
  const targetId = group && group.getAttribute("data-node");
  if (!targetId || targetId === from.id) return;
  await onEdit("connect", { source: from.id, target: targetId, ...(kind ? { kind } : {}) });
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
  const group = (personal, name) => {
    const rows = dataClasses.filter((row) => Boolean(row.personal) === personal);
    if (!rows.length) return "";
    return `<optgroup label="${name}">` + rows.map((row) =>
      `<option value="${escapeHtml(row.id)}"${row.id === selected ? " selected" : ""}` +
      ` title="${escapeHtml(row.iri || "")}">${escapeHtml(row.label)}</option>`).join("")
      + "</optgroup>";
  };
  return '<option value="">— not classified —</option>'
    + group(true, "Personal data (DPV)")
    + group(false, "Not personal (DPV)");
}

function placePanel(panel, ev, height) {
  panel.classList.remove("hidden");
  panel.style.bottom = "auto";
  panel.style.right = "auto";
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

// Multiple is not a trigger of its own: it is two or more on one event.
const MULTIPLE_DEFINITIONS = [
  ["multiple", "Multiple (any one of them)"],
  ["parallelMultiple", "Multiple (all of them)"],
];

const GATEWAY_KINDS = [
  ["exclusiveGateway", "Exclusive (XOR)"],
  ["parallelGateway", "Parallel (AND)"],
  ["inclusiveGateway", "Inclusive (OR)"],
  ["eventBasedGateway", "Event-based"],
  ["parallelEventBasedGateway", "Event-based, parallel"],
  ["complexGateway", "Complex"],
];

// The gateways whose branches are chosen by a condition.
const CONDITIONAL_GATEWAYS = new Set(["exclusiveGateway", "inclusiveGateway", "complexGateway"]);

/* Mirrors NO_INCOMING / NO_OUTGOING in routes/graph.py, which refuses the same. */
const SEQUENCE_FLOW_RULES = [
  { kind: "startEvent", end: "target",
    why: "A start event begins the process, so no sequence flow may lead into it."
      + " Remove the incoming flow first." },
  { kind: "boundaryEvent", end: "target",
    why: "A boundary event sits on an activity's edge, so no sequence flow may lead into it."
      + " Remove the incoming flow first." },
  { kind: "endEvent", end: "source",
    why: "An end event finishes the process, so no sequence flow may leave it."
      + " Remove the outgoing flow first." },
];

/* The event types this event cannot take while its sequence flows are drawn. */
function blockedKinds(id) {
  const flows = (data && data.sequenceFlows) || [];
  const blocked = new Map();
  for (const rule of SEQUENCE_FLOW_RULES) {
    if (flows.some((flow) => flow[rule.end] === id)) blocked.set(rule.kind, rule.why);
  }
  return blocked;
}

/* Events and gateways get their own editor: they carry a type and, for an
 * event, a trigger - and changing either is what turns a placeholder circle
 * into the thing the process actually waits for. */
function showNodeDetail(item, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  const isEvent = item.shape === "event";
  const kinds = isEvent ? EVENT_KINDS : GATEWAY_KINDS;
  const multiple = MULTIPLE_DEFINITIONS.some(([value]) => value === item.definition);
  const chosen = new Set(item.definitions || []);
  const host = item.parent ? index.get(item.parent) : null;
  // Interrupting is read on a boundary event, and on the start of an event sub-process.
  const interruptLabel = !isEvent ? null
    : item.kind === "boundaryEvent" ? "Interrupts the activity"
      : (item.kind === "startEvent" && host && host.markers && host.markers.eventSubProcess)
        ? "Interrupts the process it starts in" : null;
  const blocked = isEvent ? blockedKinds(item.id) : new Map();
  const kindOptions = kinds.map(([value, label]) => {
    const why = value === item.kind ? null : blocked.get(value);
    return `<option value="${escapeHtml(value)}"${value === item.kind ? " selected" : ""}`
      + `${why ? ` disabled title="${escapeHtml(why)}"` : ""}>`
      + `${escapeHtml(label)}${why ? " (not while connected)" : ""}</option>`;
  }).join("");
  const blockedNote = [...new Set([...blocked].filter(([value]) => value !== item.kind)
    .map(([, why]) => why))].join(" ");
  // A gateway's branches are named where the decision is, not only on each line.
  const branches = isEvent ? [] : (data.sequenceFlows || []).filter((f) => f.source === item.id);
  const decides = CONDITIONAL_GATEWAYS.has(item.kind);
  const branchRows = branches.map((f) => {
    const to = index.get(f.target);
    return `<div class="nd-row nd-branch">
      <span title="${escapeHtml(to ? to.label : "")}">→ ${escapeHtml(truncate(to ? to.label || humanKind(to.kind) : "?", 14))}</span>
      <input type="text" class="pd-branch-name" data-flow="${escapeHtml(f.id)}"
             placeholder="yes, no" value="${escapeHtml(f.label || "")}" />
      ${decides ? `<input type="text" class="pd-branch-when" data-flow="${escapeHtml(f.id)}"
             placeholder="when, in words" value="${escapeHtml(f.condition || "")}" />` : ""}
    </div>`;
  }).join("");
  panel.innerHTML = `
    <div class="nd-head">${escapeHtml(isEvent ? "event" : "gateway")}</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-name" value="${escapeHtml(item.label)}" /></label>
    <label class="nd-row"><span>Type</span>
      <select id="pd-kind"${blockedNote ? ` title="${escapeHtml(blockedNote)}"` : ""}>${kindOptions}</select></label>
    ${blockedNote ? `<p class="nd-note" id="pd-kind-why">${escapeHtml(blockedNote)}</p>` : ""}
    ${isEvent ? `<label class="nd-row"><span>Trigger</span>
      <select id="pd-def">${options([...EVENT_DEFINITIONS, ...MULTIPLE_DEFINITIONS],
        item.definition || "")}</select></label>
      <div class="nd-row nd-triggers${multiple ? "" : " hidden"}" id="pd-defs">
        ${EVENT_DEFINITIONS.filter(([value]) => value).map(([value, name]) => `<label class="nd-check">
          <input type="checkbox" value="${value}"${chosen.has(value) ? " checked" : ""} />
          <span>${escapeHtml(name)}</span></label>`).join("")}
      </div>` : ""}
    ${interruptLabel ? `<label class="nd-row nd-check">
      <span>${interruptLabel}</span>
      <input type="checkbox" id="pd-interrupt"${item.interrupting !== false ? " checked" : ""} /></label>` : ""}
    ${branches.length ? `<p class="nd-note">Branches: name each one${decides
      ? ", and say when it is taken" : ""}</p>${branchRows}` : ""}
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-apply">Apply</button>
      <button type="button" class="btn small" id="pd-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 220 + branches.length * 34);

  const select = panel.querySelector("#pd-def");
  if (select) {
    select.addEventListener("change", () => {
      const several = MULTIPLE_DEFINITIONS.some(([value]) => value === select.value);
      panel.querySelector("#pd-defs").classList.toggle("hidden", !several);
    });
  }

  panel.querySelector("#pd-apply").addEventListener("click", async () => {
    const label = panel.querySelector("#pd-name").value.trim();
    const kind = panel.querySelector("#pd-kind").value;
    const definition = isEvent ? select.value : "";
    const definitions = isEvent
      ? [...panel.querySelectorAll("#pd-defs input:checked")].map((box) => box.value) : [];
    const interrupting = panel.querySelector("#pd-interrupt");
    const named = [...panel.querySelectorAll(".pd-branch-name")]
      .map((input) => [input.dataset.flow, input.value.trim()]);
    const when = [...panel.querySelectorAll(".pd-branch-when")]
      .map((input) => [input.dataset.flow, input.value.trim()]);
    closeDetail();
    await onEdit("set-node-type", {
      element: item.id, kind, definition, definitions, label,
      // Left out when the panel did not ask, so the server keeps what is there.
      interrupting: interrupting ? interrupting.checked : undefined,
    });
    for (const [flow, text] of named) {
      const was = branches.find((f) => f.id === flow);
      if (text !== ((was && was.label) || "")) await onEdit("rename", { element: flow, label: text });
    }
    for (const [flow, text] of when) {
      const was = branches.find((f) => f.id === flow);
      if (text !== ((was && was.condition) || "")) await onEdit("set-condition", { flow, text });
    }
  });
  panel.querySelector("#pd-delete").addEventListener("click", async () => {
    closeDetail();
    await onEdit("delete", { element: item.id });
  });
}


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


function dpvIriFor(name) {
  const row = dataClasses.find((entry) => entry.id === name);
  return (row && row.iri) || name;
}

function showDataDetail(shown, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  // a box drawn in a step carries that one link; the model's entry has them all
  const entry = (data.dataNodes || []).find((n) => n.id === shown.id) || shown;
  const ways = new Map();
  (entry.links || []).forEach((link) => {
    if (!link.activity) return;
    const had = ways.get(link.activity);
    ways.set(link.activity, had && had !== link.direction ? "both" : link.direction);
  });
  const usedBy = [...ways.entries()].map(([id, way]) => ({ id, way, activity: index.get(id) }))
    .filter((row) => row.activity);
  const carryTo = usedBy.find((row) => (row.activity.refines || []).length === 1);
  const systemName = carryTo ? ((systems || []).find((s) => s.id === carryTo.activity.refines[0]) || {}).label : null;
  const holds = classOptions(entry.kinds[0] || "");
  panel.innerHTML = `
    <div class="nd-head">${entry.store ? "data store" : "data object"}</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-data-name" value="${escapeHtml(entry.label)}" /></label>
    <label class="nd-row"><span>Shape</span>
      <select id="pd-data-shape">
        <option value="object"${entry.store ? "" : " selected"}>Document</option>
        <option value="store"${entry.store ? " selected" : ""}>Data store</option>
      </select></label>
    <label class="nd-row"><span>Holds</span>
      <select id="pd-data-class">${holds}</select></label>
    <div class="nd-source">${entry.kinds.length
      ? escapeHtml(dpvIriFor(entry.kinds[0]))
      : "classified with DPV terms"}</div>
    ${(entry.candidates || []).length ? `
    <label class="nd-row"><span>Is</span>
      <select id="pd-data-realises" multiple size="${Math.min(4, entry.candidates.length)}">
        ${entry.candidates.map((c) => `<option value="${escapeHtml(c.id)}"${
          (entry.realisedBy || []).includes(c.id) ? " selected" : ""
        }>${escapeHtml(c.label)}</option>`).join("")}
      </select></label>
    <div class="nd-note">${(entry.realisedBy || []).length
      ? "named, so the classification lands here and nowhere else"
      : "not named, so the classification lands wherever content enters the system"}</div>`
    : ""}
    ${usedBy.length ? usedBy.map((row) => `
    <label class="nd-row"><span>${escapeHtml(truncate(row.activity.label, 18))}</span>
      <select class="pd-data-way" data-activity="${escapeHtml(row.id)}" data-was="${row.way}"
        >${options(Object.entries(DIRECTION_WORDS), row.way)}</select></label>`).join("")
      : `<div class="nd-note">nothing reads it yet - drag from its handle to a step</div>`}
    ${carryTo && !(entry.realisedBy || []).length ? `
    <div class="pd-add">
      <button type="button" class="btn small" id="pd-data-carry"
        title="A Data element of that system, named after this one and linked to it">
        Add to the ${escapeHtml(systemName || "system")} architecture</button>
    </div>` : ""}
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-data-apply">Apply</button>
      <button type="button" class="btn small" id="pd-data-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 210);

  const carry = panel.querySelector("#pd-data-carry");
  if (carry) {
    carry.addEventListener("click", async () => {
      closeDetail();
      await onEdit("carry-data", { activity: carryTo.id, reference: entry.id });
    });
  }

  panel.querySelector("#pd-data-apply").addEventListener("click", async () => {
    const name = panel.querySelector("#pd-data-name").value.trim();
    const turns = [...panel.querySelectorAll(".pd-data-way")]
      .filter((select) => select.value !== select.dataset.was);
    const shape = panel.querySelector("#pd-data-shape").value;
    const classification = panel.querySelector("#pd-data-class").value;
    const realises = panel.querySelector("#pd-data-realises");
    const picked = realises ? [...realises.selectedOptions].map((o) => o.value) : null;
    closeDetail();
    if (name && name !== entry.label) await onEdit("rename", { element: entry.id, label: name });
    if ((shape === "store") !== Boolean(entry.store)) {
      await onEdit("set-data-shape", { reference: entry.id, shape });
    }
    if (picked) {
      const had = entry.realisedBy || [];
      if (picked.length !== had.length || picked.some((id) => !had.includes(id))) {
        await onEdit("realise-data", { reference: entry.id, elements: picked });
      }
    }
    if (classification !== (entry.kinds[0] || "")) {
      await onEdit("classify-data", { reference: entry.id, classification });
    }
    for (const select of turns) {
      await onEdit("set-data-direction", {
        reference: entry.id, activity: select.dataset.activity, direction: select.value,
      });
    }
  });
  panel.querySelector("#pd-data-delete").addEventListener("click", async () => {
    closeDetail();
    await onEdit("remove-data", { reference: entry.id });
  });
}


function showFlowDetail(id, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel || !onEdit) return;
  const flow = [...(data.sequenceFlows || []), ...(data.messageFlows || [])]
    .find((row) => row.id === id);
  if (!flow) return;
  const message = (data.messageFlows || []).some((row) => row.id === id);
  const fromGateway = (data.gateways || []).some((row) => row.id === flow.source);
  panel.innerHTML = `
    <div class="nd-head">${message ? "message flow" : "sequence flow"}</div>
    <label class="nd-row"><span>Label</span>
      <input type="text" id="pd-flow-name" placeholder="yes, no, over the limit"
             value="${escapeHtml(flow.label || "")}" /></label>
    ${fromGateway ? `<label class="nd-row"><span>When</span>
      <input type="text" id="pd-flow-when" placeholder="the condition, in words"
             value="${escapeHtml(flow.condition || "")}" /></label>` : ""}
    <div class="nd-note">${fromGateway
      ? "the branch this arrow is taken on"
      : "what this arrow carries"}</div>
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-flow-apply">Apply</button>
      <button type="button" class="btn small" id="pd-flow-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 170);

  panel.querySelector("#pd-flow-apply").addEventListener("click", async () => {
    const label = panel.querySelector("#pd-flow-name").value.trim();
    const when = fromGateway ? panel.querySelector("#pd-flow-when").value.trim() : null;
    closeDetail();
    pickedFlow = null;
    if (label !== (flow.label || "")) await onEdit("rename", { element: id, label });
    if (when !== null && when !== (flow.condition || "")) {
      await onEdit("set-condition", { flow: id, text: when });
    }
  });
  panel.querySelector("#pd-flow-delete").addEventListener("click", async () => {
    closeDetail();
    pickedFlow = null;
    await onEdit("disconnect", { flow: id });
  });
}


function wireDataNode(group, entry, at) {
  if (!onEdit) return;
  const dot = node("g", { class: "pc-port", cursor: "crosshair" }, group);
  node("circle", {
    cx: at.x + DATA_W + 4, cy: at.y + DATA_H / 2, r: PORT_SCREEN_R, class: "pc-port-dot",
  }, dot);
  node("title", {}, dot).textContent = "Drag onto a step: out of here is a read, into here a write";
  dot.addEventListener("pointerdown", (ev) => {
    ev.stopPropagation();
    // the dot covers much of a small box: a press that goes nowhere is a click on the box
    startConnect(ev, { id: entry.id, label: entry.label },
      { x: at.x, y: at.y, w: DATA_W, h: DATA_H, head: DATA_H }, null,
      (up) => { if (onSelect) onSelect(entry.id); showDataDetail(entry, up); });
  });
  group.setAttribute("cursor", "pointer");
  group.addEventListener("click", (ev) => {
    if (ev.target.closest(".pc-port")) return;
    ev.stopPropagation();
    if (onSelect) onSelect(entry.id);
    showDataDetail(entry, ev);
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

const LOOP_KINDS = [
  ["", "— runs once —"],
  ["standard", "Loop"],
  ["multiParallel", "Multi-instance, parallel"],
  ["multiSequential", "Multi-instance, sequential"],
];


function contextRows(activity) {
  const system = (refinedSystems || []).find((s) => activity.refines.includes(s.id));
  if (!system) return "";
  const facets = [...new Set((contextOptions || []).map((o) => o.facet))];
  return facets.map((facet) => {
    const key = facet.split(/[#/]/).pop();
    const held = (system[key] || [])[0] || "";
    const choices = ['<option value="">— not stated —</option>'].concat(
      (contextOptions || []).filter((o) => o.facet === facet).map((o) =>
        `<option value="${escapeHtml(o.value)}"${o.value === held ? " selected" : ""}>`
        + `${escapeHtml(o.label)}</option>`)).join("");
    const name = key.replace(/^has/, "");
    return `<label class="nd-row"><span>${escapeHtml(name)}</span>`
      + `<select class="pd-context" data-facet="${escapeHtml(facet)}"`
      + ` data-system="${escapeHtml(system.id)}" data-held="${escapeHtml(held)}">`
      + `${choices}</select></label>`;
  }).join("");
}


/* The steps of the refined system that do this activity's work, and the way
   to bring the data it reads and writes into that system. */
function stepRows(activity) {
  const options = activity.stepOptions || [];
  if (!activity.refines.length) return "";
  const picker = options.length ? `
    <label class="nd-row"><span>Steps</span>
      <select id="pd-steps" multiple size="${Math.min(4, options.length)}">
        ${options.map((o) => `<option value="${escapeHtml(o.id)}"${
          (activity.steps || []).includes(o.id) ? " selected" : ""}>${escapeHtml(o.label)}</option>`).join("")}
      </select></label>
    <div class="nd-note">${(activity.steps || []).length
      ? "its risks are the ones these steps and its data meet"
      : "no step named, so every risk of the system is listed under it"}</div>`
    : `<div class="nd-note">the system has no steps yet</div>`;
  const loose = [...activity.reads, ...activity.writes].filter((d) => !(d.realisedBy || []).length);
  const carry = loose.length ? `
    <div class="pd-add">
      <button type="button" class="btn small" id="pd-carry"
        title="Each becomes a Data element of the system, named after it and linked to it">
        Carry ${loose.length} data item${loose.length === 1 ? "" : "s"} into the architecture</button>
    </div>` : "";
  return picker + carry;
}


function showDetail(activity, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  /* The last option is how an architecture gets started at all. */
  const systemOptions = ['<option value="">— not an AI activity —</option>']
    .concat(systems.map((s) =>
      `<option value="${s.id}"${activity.refines.includes(s.id) ? " selected" : ""}>`
      + `${escapeHtml(s.label)}</option>`))
    .concat(['<option value="__new__">+ system…</option>'])
    .join("");
  panel.innerHTML = `
    <div class="nd-head">${escapeHtml(activity.kind)}</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-name" value="${escapeHtml(activity.label)}" /></label>
    <label class="nd-row"><span>Carried out by</span>
      <select id="pd-refines">${systemOptions}</select></label>
    ${stepRows(activity)}
    ${contextRows(activity)}
    <label class="nd-row"><span>Repetition</span>
      <select id="pd-loop">${options(LOOP_KINDS, activity.markers.loop || "")}</select></label>
    <div class="nd-note">Data is drawn with the palette and joined by an arrow; click a data box for what it holds and which way it goes.</div>
    <div class="pd-add">
      <select id="pd-boundary">${options(EVENT_DEFINITIONS, "error")}</select>
      <button type="button" class="btn small" id="pd-boundary-add">Attach boundary event</button>
    </div>
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-apply">Apply</button>
      <button type="button" class="btn small" id="pd-delete">Delete</button>
    </div>`;
  placePanel(panel, ev, 340);

  const carry = panel.querySelector("#pd-carry");
  if (carry) {
    carry.addEventListener("click", async () => {
      closeDetail();
      await onEdit("carry-data", { activity: activity.id });
    });
  }

  panel.querySelector("#pd-refines").addEventListener("change", async (event) => {
    const system = event.target.value;
    closeDetail();
    if (system === "__new__") {
      const label = panel.querySelector("#pd-name").value.trim() || activity.label;
      const suggested = window.prompt("Name of the system that carries out this activity:", `${label} system`);
      if (suggested) await onEdit("add-system", { activity: activity.id, label: suggested });
      return;
    }
    await onEdit("set-refines", { activity: activity.id, system });
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
    const loop = panel.querySelector("#pd-loop").value;
    const stepPicker = panel.querySelector("#pd-steps");
    const steps = stepPicker ? [...stepPicker.selectedOptions].map((o) => o.value) : null;
    const context = [...panel.querySelectorAll(".pd-context")]
      .filter((select) => select.value !== select.dataset.held)
      .map((select) => ({
        system: select.dataset.system, facet: select.dataset.facet, value: select.value,
      }));
    closeDetail();
    for (const change of context) await onEdit("set-system-context", change);
    if (name && name !== activity.label) await onEdit("rename", { element: activity.id, label: name });
    if (loop !== (activity.markers.loop || "")) {
      await onEdit("set-loop", { activity: activity.id, loop });
    }
    const had = activity.steps || [];
    if (steps && (steps.length !== had.length || steps.some((id) => !had.includes(id)))) {
      await onEdit("set-steps", { activity: activity.id, steps });
    }
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
  // The same open head for an association. auto-start-reverse turns it round
  // at the start end, so "Both" needs no second marker.
  const assocHead = node("marker", {
    id: "pc-arrow-assoc", viewBox: "0 0 10 10", refX: 9, refY: 5,
    markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse",
  }, defs);
  node("path", { d: "M 0 0 L 10 5 L 0 10", class: "pc-arrow-head open" }, assocHead);
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
  if (pickedFlow && ![...(data.sequenceFlows || []), ...(data.messageFlows || [])]
      .some((flow) => flow.id === pickedFlow)) {
    pickedFlow = null;
  }
  svg.innerHTML = "";
  defineMarkers(node("defs", {}, svg));

  pendingBadge = null;
  root = node("g", { id: "pc-root" }, svg);
  // Created now so a pool can put a badge in it, moved to last when the pools
  // are done so nothing a later pool draws can end up over one.
  topLayer = node("g", { class: "pc-top" }, root);
  portsSizedAt = null;   // a fresh DOM: the handles have to be measured again
  const { pools, placed, notes } = layout();
  lastPlaced = placed;
  lastPools = pools;

  drawGroups(root, placed);
  // Under the pools, so a link to a pool further away passes behind the pools
  // between rather than reading as theirs.
  const conversationLinks = node("g", { class: "pc-conv-links" }, root);

  pools.forEach((pool) => {
    const group = node("g", { class: "pc-pool", "data-band": pool.participant.id }, root);
    // A choreography has no pool: it is framed and named, and holds no lanes.
    const framed = Boolean(pool.participant.choreography);
    if (framed) {
      group.setAttribute("class", "pc-chor-frame");
      node("rect", {
        x: pool.x, y: pool.y, width: pool.w, height: pool.h, rx: 6, class: "pc-chor-frame-box",
      }, group);
      const name = centred(group, 0, 0, truncate(pool.participant.label, 24), "pc-chor-frame-label");
      name.setAttribute(
        "transform", `translate(${pool.x + POOL_LABEL_W / 2}, ${pool.y + pool.h / 2}) rotate(-90)`);
    } else {
      node("rect", {
        x: pool.x, y: pool.y, width: pool.w, height: pool.h, rx: 6, class: "pc-pool-box",
      }, group);
      node("rect", {
        x: pool.x, y: pool.y, width: POOL_LABEL_W, height: pool.h, rx: 6, class: "pc-pool-strip",
      }, group);
      if (pool.participant.id === selectedPool) group.classList.add("selected");
      group.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-node], .pc-pool-edit, .pc-pool-fold, .pc-lane-strip, .pc-lane-label")) return;
        selectedPool = pool.participant.id;
        selectedLane = null;
        if (onSelect) onSelect(pool.participant.id);
        draw();
        renderPalette();
      });

      if (!pool.blackBox) {
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
      }

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
    }

    if (pool.collapsed) return;

    // Lane bands: drawn only when the model declares them, so a plain process
    // is not given a boundary it never claimed.
    if (pool.showLanes) {
      pool.lanes.forEach((lane) => {
        const band = node("g", { class: "pc-lane", "data-band": lane.id }, group);
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

    if (!framed) drawResizeGrips(group, pool);

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

    
    const inFront = [...pool.members].sort(
      (a, b) => (manualPositions.has(a.id) ? 1 : 0) - (manualPositions.has(b.id) ? 1 : 0));
    inFront.forEach((item) => {
      const slot = placed.get(item.id);
      if (!slot) return;
      if (item.shape === "activity") drawData(group, slot);
      const drawn = drawFlowNode(group, slot);
      drawn.setAttribute("data-node", item.id);
      if (item.shape === "event" || item.shape === "gateway") wireSimpleNode(drawn, slot);
      if (item.shape === "choreography") wireSelectOnly(drawn, item);
      (item.boundary || []).forEach((id) => {
        const attached = placed.get(id);
        if (attached) drawBoundary(group, attached).setAttribute("data-node", id);
      });
    });

    notes.filter((entry) => mine.has(entry.anchor)).forEach((entry) => {
      const drawn = drawNote(group, entry.note, entry.x, entry.y);
      // Placed like anything else, so the association pass can reach it - the
      // line used to be drawn here by hand and could say nothing about which
      // way, if either, the association points.
      placed.set(entry.note.id, {
        x: entry.x, y: entry.y, w: drawn.width, h: drawn.height,
        item: { id: entry.note.id, label: entry.note.text, shape: "note" },
      });
    });
  });


  const loose = (data.dataNodes || []).filter((entry) => !(entry.links || []).length);
  if (loose.length) {
    // Below the pools as well as their boxes: an empty pool places no box.
    const bottom = Math.max(
      0, ...[...placed.values()].map((slot) => slot.y + (slot.h || 0)),
      ...pools.map((pool) => pool.y + pool.h)) + 56;
    loose.forEach((entry, seat) => {
      const at = manualPositions.get(entry.id)
        || { x: 40 + seat * (DATA_W + 46), y: bottom };
      const drawn = dataGlyph(root, at.x, at.y, entry);
      drawn.setAttribute("data-node", entry.id);
      wireDataNode(drawn, entry, at);
      placed.set(entry.id, {
        x: at.x, y: at.y, w: DATA_W, h: DATA_H,
        item: { id: entry.id, label: entry.label, shape: "data" },
      });
      wrap(entry.label, 16, 2).forEach((line, row) => {
        centred(drawn, at.x + DATA_W / 2, at.y + DATA_H + 13 + row * 11, line, "pc-data-label");
      });
      if (entry.kinds.length) {
        centred(drawn, at.x + DATA_W / 2, at.y - 4,
          entry.kinds.map(humanKind).join(", "), "pc-data-kind");
      }
      node("title", {}, drawn).textContent =
        `${entry.label} - nothing reads or writes it yet`;
    });
  }


  (data.associations || []).forEach((link) => {
    const from = placed.get(link.source);
    const to = placed.get(link.target);
    if (!from || !to) return;
    const direction = link.direction || "None";
    const path = node("path", {
      d: orthPath([centreOf(from), centreOf(to)]),
      class: "pc-assoc", fill: "none",
      "data-flow": link.id,
    }, root);
    if (direction === "One" || direction === "Both") {
      path.setAttribute("marker-end", "url(#pc-arrow-assoc)");
    }
    if (direction === "Both") path.setAttribute("marker-start", "url(#pc-arrow-assoc)");
    node("title", {}, path).textContent = direction === "None"
      ? "Association" : `Association (${direction === "Both" ? "both ways" : "one way"})`;
  });

  // message flow: what crosses a boundary between actors
  const poolOf = new Map(pools.map((pool) => [pool.participant.id, pool]));

  (data.conversations || []).forEach((item) => {
    const slot = placed.get(item.id);
    if (!slot) return;
    (data.conversationLinks || []).forEach((link) => {
      const other = link.source === item.id ? link.target : (link.target === item.id ? link.source : null);
      const pool = other && poolOf.get(other);
      if (pool) conversationLink(conversationLinks, slot, pool, link.id);
    });
    const drawn = drawConversation(root, slot);
    drawn.setAttribute("data-node", item.id);
    wireSelectOnly(drawn, item);
  });
  (data.messageFlows || []).forEach((flow) => {
    const from = placed.get(flow.source);
    const to = placed.get(flow.target);
    const a = from || onPoolEdge(poolOf.get(flow.source), to);
    const b = to || onPoolEdge(poolOf.get(flow.target), from);
    if (a && b) {
      messageArrow(root, a, b, flow.message || flow.label, flow.id, Boolean(flow.message));
    }
  });

  drawPickedBadge(topLayer || root);
  paintPicked();
  if (topLayer) root.appendChild(topLayer);
  if (structureKey() !== lastFitIds && fit()) return;
  applyView();
}


function paintPicked() {
  svg.querySelectorAll("[data-node]").forEach((group) => {
    group.classList.toggle("pc-picked", picked.has(group.getAttribute("data-node")));
  });
}

/* Shift-click adds a node to the selection, or takes it out; a plain click
 * empties it. Read in the capture phase, before the node opens its editor. */
function pickOnShift(ev) {
  if (!ev.shiftKey) {
    if (picked.size) { picked = new Set(); paintPicked(); }
    return;
  }
  const hit = ev.target.closest("[data-node]");
  if (!hit || ev.target.closest(".pc-open, .pc-marker, .pc-port, .pc-edit, .pc-risk")) return;
  ev.stopPropagation();
  ev.preventDefault();
  closeDetail();
  const id = hit.getAttribute("data-node");
  if (picked.has(id)) picked.delete(id); else picked.add(id);
  paintPicked();
  if (onPick) onPick([...picked]);
}

/* Grips on a pool's right edge and on each band's lower edge; the last band's
 * is the pool's own. Drawn before the nodes, so a box on an edge stays on top. */
function drawResizeGrips(group, pool) {
  const right = node("rect", {
    x: pool.x + pool.w - 4, y: pool.y + 30, width: 8, height: Math.max(pool.h - 40, 8),
    class: "pc-resize pc-resize-w",
  }, group);
  node("title", {}, right).textContent = "Drag to make the participants wider or narrower";
  right.addEventListener("pointerdown", (ev) => startResize(ev, "w", null, pool.w));
  pool.lanes.forEach((lane, at) => {
    const last = at === pool.lanes.length - 1;
    const grip = node("rect", {
      x: pool.x + POOL_LABEL_W, y: (last ? pool.y + pool.h : lane.y + lane.h) - 4,
      width: pool.w - POOL_LABEL_W - 10, height: 8, class: "pc-resize pc-resize-h",
      "data-grip": lane.key,
    }, group);
    node("title", {}, grip).textContent = last || !lane.label
      ? "Drag to make this participant taller or shorter"
      : `Drag to make the lane "${lane.label}" taller or shorter`;
    grip.addEventListener("pointerdown", (ev) => startResize(ev, "h", lane.key, lane.h));
  });
}

/* Never smaller than what the band holds: the layout keeps the larger of the two. */
function startResize(ev, axis, key, base) {
  if (ev.button !== 0) return;
  ev.stopPropagation();
  ev.preventDefault();
  const from = axis === "w" ? ev.clientX : ev.clientY;
  let moved = false;
  svg.setPointerCapture(ev.pointerId);
  const move = (mv) => {
    const shift = (axis === "w" ? mv.clientX : mv.clientY) - from;
    if (!moved && Math.abs(shift) < 3) return;
    moved = true;
    const size = Math.max(0, Math.round(base + shift / view.k));
    if (axis === "w") poolWidth = size; else bandHeights.set(key, size);
    redraw();
  };
  const up = () => {
    svg.removeEventListener("pointermove", move);
    svg.removeEventListener("pointerup", up);
    svg.removeEventListener("pointercancel", up);
    try { svg.releasePointerCapture(ev.pointerId); } catch (error) { /* already gone */ }
    if (moved) swallowNextClick = true;
  };
  svg.addEventListener("pointermove", move);
  svg.addEventListener("pointerup", up);
  svg.addEventListener("pointercancel", up);
}

/* The model on the canvas: the one picked, else the first with pools in it. */
function currentModel() {
  const models = (data && data.models) || [];
  return models.find((m) => m.id === selectedModel)
    || models.find((m) => m.participants.length) || models[0] || null;
}

function inModel(id) {
  const model = currentModel();
  return !model || model.participants.includes(id);
}

function showModel(id) {
  selectedModel = id;
  const shown = data.participants.filter((p) => inModel(p.id));
  selectedPool = shown.length ? shown[0].id : null;
  selectedLane = null;
  closeDetail();
  draw();
  renderPalette();
  fit();
}

/* Which process model is drawn, and the way to start another. */
function modelControl() {
  const box = document.createElement("span");
  box.className = "pp-models";
  const models = (data && data.models) || [];
  const current = currentModel();
  if (models.length) {
    const pick = document.createElement("select");
    pick.className = "pp-model";
    pick.title = "The process model on the canvas";
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = `${model.label} (${model.participants.length})`;
      option.selected = Boolean(current) && model.id === current.id;
      pick.appendChild(option);
    });
    pick.addEventListener("change", () => showModel(pick.value));
    box.appendChild(pick);
    if (current && current.id) {
      const rename = document.createElement("button");
      rename.type = "button";
      rename.className = "pp-model-rename";
      rename.textContent = "Rename";
      rename.title = "Rename this process model";
      rename.addEventListener("click", async () => {
        const label = window.prompt("Name of the process model:", current.label);
        if (label && label.trim() !== current.label) {
          await onEdit("rename", { element: current.id, label: label.trim() });
        }
      });
      box.appendChild(rename);
    }
  }
  const add = document.createElement("button");
  add.type = "button";
  add.className = "pp-model-add";
  add.textContent = "+ process model";
  add.title = "Start another process model, such as the development process beside the business process";
  add.addEventListener("click", async () => {
    const label = window.prompt("Name of the process model:", "Development process");
    if (!label || !label.trim()) return;
    const made = await onEdit("add-model", { label: label.trim() });
    if (!made || !made.newId) return;
    wantedModel = made.newId;
    if ((data.models || []).some((m) => m.id === wantedModel)) {
      wantedModel = null;
      showModel(made.newId);
    }
  });
  box.appendChild(add);
  return box;
}

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

function poolOf(id) {
  const pool = lastPools.find((p) => (p.members || [])
    .some((m) => m.id === id || (m.boundary || []).includes(id)));
  return pool ? pool.participant.id : null;
}

/* What a move to `target` would leave that BPMN does not allow, in words, or "". */
function brokenByMove(id, target) {
  const moving = new Set([id, ...((index.get(id) || {}).boundary || [])]);
  const other = (f) => (moving.has(f.source) ? f.target : f.source);
  const touches = (f) => moving.has(f.source) || moving.has(f.target);
  const crossing = (data.sequenceFlows || []).filter((f) => touches(f) && !moving.has(other(f))).length;
  const joining = (data.messageFlows || []).filter((f) => touches(f) && poolOf(other(f)) === target).length;
  const parts = [];
  if (crossing) parts.push(`${crossing} sequence flow${crossing > 1 ? "s" : ""} would cross between participants`);
  if (joining) parts.push(`${joining} message flow${joining > 1 ? "s" : ""} would stay inside one participant`);
  return parts.join(" and ");
}

/* A step dropped in another lane or participant is moved there, keeping its id
   and its flows; dropped in its own lane, the drag stays a nudge of the drawing. */
function bandGeometry() {
  return lastPools.map((p) => ({
    participant: p.participant, collapsed: p.collapsed, x: p.x, y: p.y, w: p.w, h: p.h,
    lanes: (p.lanes || []).map((l) => ({ id: l.id, implicit: l.implicit, y: l.y, h: l.h })),
  }));
}

async function moveToBandAt(id, ev, pools = bandGeometry()) {
  const item = index.get(id);
  if (!item || !onEdit || item.parent || item.kind === "boundaryEvent") return;
  if (!["activity", "event", "gateway"].includes(item.shape)) return;
  const at = svgPoint(ev.clientX, ev.clientY);
  const pool = pools.find((p) => !p.collapsed
    && at.x >= p.x && at.x <= p.x + p.w && at.y >= p.y && at.y <= p.y + p.h);
  const from = poolOf(id);
  if (!pool || !from) return;
  const band = (pool.lanes || []).find((b) => !b.implicit && at.y >= b.y && at.y <= b.y + b.h);
  const laneNow = (data.lanes || []).find((lane) => (lane.members || []).includes(id));
  const lane = band ? band.id : null;
  if (pool.participant.id === from && (!band || lane === (laneNow ? laneNow.id : null))) return;

  let convert = false;
  if (pool.participant.id !== from) {
    const broken = brokenByMove(id, pool.participant.id);
    if (broken && !window.confirm(`Moving "${item.label || "this step"}" to "${pool.participant.label}":`
      + ` ${broken}, which BPMN does not allow.\n\nTurn them into the other kind`
      + " (sequence flow ⇄ message flow) and move it?")) {
      manualPositions.delete(id);
      redraw();
      return;
    }
    convert = Boolean(broken);
  }
  // Laid out afresh in its new band, not left where the pointer let go of it.
  manualPositions.delete(id);
  await onEdit("move-node", {
    element: id, pool: pool.participant.id, lane, ...(convert ? { convert: true } : {}),
  });
}

/* Zoom about the centre; above 1 zooms in. Clamped like the wheel. */
function zoomBy(factor) {
  if (!svg) return;
  const rect = svg.getBoundingClientRect();
  const next = Math.min(3, Math.max(0.15, view.k * factor));
  const ratio = next / view.k;
  view.x = rect.width / 2 - (rect.width / 2 - view.x) * ratio;
  view.y = rect.height / 2 - (rect.height / 2 - view.y) * ratio;
  view.k = next;
  applyView();
}

function initPanZoom() {

  const DRAG_THRESHOLD = 4;
  let pan = null;

  window.addEventListener("keydown", async (ev) => {
    if (ev.key !== "Delete" && ev.key !== "Backspace") return;
    if (svg.classList.contains("hidden")) return;
    const on = document.activeElement;
    if (on && on.closest && on.closest("input, textarea, select, [contenteditable]")) return;
    if (pickedFlow) {
      ev.preventDefault();
      const id = pickedFlow;
      pickedFlow = null;
      if (onEdit) await onEdit("disconnect", { flow: id });
      return;
    }
    if (picked.size && onEdit) {
      ev.preventDefault();
      const ids = [...picked];
      picked = new Set();
      await onEdit("delete", { elements: ids });
      return;
    }
    // The element whose editor is open is the one that was clicked, and its
    // own Delete button already knows how to remove that kind of thing.
    const remove = document.querySelector(
      "#process-detail:not(.hidden) .nd-actions button[id^='pd-'][id$='delete']");
    if (remove) {
      ev.preventDefault();
      remove.click();
    }
  });
  svg.addEventListener("pointerdown", (ev) => {
    // Clear here: a flag left armed eats the next real click.
    swallowNextClick = false;
    if (ev.target.closest(".pc-open, .pc-marker, .pc-port, .pc-edit, .pc-risk")) return;
    if (pickedFlow && !ev.target.closest(".pc-flow-hit, .pc-flow-drop")) {
      pickedFlow = null;
      svg.querySelectorAll(".pc-flow-drop").forEach((mark) => mark.remove());
      svg.querySelectorAll(".pc-flow.picked").forEach((line) => line.classList.remove("picked"));
    }
    closeDetail();

    const hit = ev.target.closest("[data-node]");
    const box = hit && hit.getAttribute("data-node");
    const drawnAt = box ? currentPlacement(box) : null;
    const strip = ev.target.closest(
      ".pc-pool-strip, .pc-lane-strip, .pc-pool-label, .pc-lane-label");
    const bandId = strip ? strip.closest("[data-band]")?.getAttribute("data-band") : null;
    const bands = bandId ? bandsLike(bandId) : null;
    pan = {
      id: ev.pointerId,
      fromX: ev.clientX, fromY: ev.clientY,
      originX: view.x, originY: view.y,
      node: drawnAt ? box : null,
      nodeFrom: drawnAt ? svgPoint(ev.clientX, ev.clientY) : null,
      nodeOrigin: drawnAt ? { x: drawnAt.x, y: drawnAt.y } : null,
      // Where the lanes stood before the drag: a lane grows to hold a box dragged in it.
      layoutAtStart: drawnAt ? bandGeometry() : null,
      band: bands && bands.length > 1 ? { id: bandId, bands, index: null } : null,
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
      svg.classList.add(pan.band ? "dragging-band" : pan.node ? "dragging-node" : "panning");
      try { svg.setPointerCapture(pan.id); } catch (error) { /* already gone */ }
    }
    if (pan.band) {
      const at = svgPoint(ev.clientX, ev.clientY);
      pan.band.index = dropIndexAt(pan.band.bands, pan.band.id, at.y);
      showBandDrop(pan.band.bands, pan.band.id, pan.band.index);
      return;
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
    const dropped = pan && pan.moved && pan.band ? pan.band : null;
    const movedNode = pan && pan.moved && pan.node ? pan.node : null;
    if (movedNode && ev.type === "pointerup") moveToBandAt(movedNode, ev, pan.layoutAtStart);
    if (pan && pan.moved) {
      svg.querySelectorAll(".pc-band-drop").forEach((mark) => mark.remove());
      svg.classList.remove("panning", "dragging-node", "dragging-band");
      try { svg.releasePointerCapture(pan.id); } catch (error) { /* already gone */ }
      // A move is a move, never also a click that opens the box's editor.
      swallowNextClick = true;
    }
    pan = null;
    if (dropped && dropped.index !== null && onEdit) {
      const was = dropped.bands.findIndex((band) => band.id === dropped.id);
      if (dropped.index !== was) {
        onEdit("reorder-band", { band: dropped.id, toIndex: dropped.index });
      }
    }
  };
  // Consumed in the capture phase, so the flag cannot outlive one gesture.
  svg.addEventListener("click", (ev) => {
    if (!swallowNextClick) { pickOnShift(ev); return; }
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
  { group: "Events", op: "add-event", kind: "intermediateCatchEvent", definition: "timer",
    label: "Timer catch", hint: "Waits for a time or a delay part-way through" },
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
  { group: "Activities", kind: "eventSubProcess", label: "Event sub-process",
    hint: "Started by an event rather than by the flow" },
  { group: "Activities", kind: "callActivity", label: "Call",
    hint: "Calls a process defined elsewhere" },
  { group: "Activities", kind: "transaction", label: "Transaction",
    hint: "Completes as a whole or compensates" },

  { group: "Artifacts", op: "add-annotation", label: "Note",
    hint: "A text annotation: says something about a step without being one" },
  
  { group: "Artifacts", op: "add-data", shape: "object", label: "Document",
    hint: "A data object: what a step reads or writes" },
  { group: "Artifacts", op: "add-data", shape: "store", label: "Data store",
    hint: "A data store: outlives any one run of the process" },
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
  } else if (item.op === "add-data") {
    // The two shapes BPMN draws: a folded page, and a cylinder.
    if (item.shape === "store") {
      node("path", {
        d: "M 9 6 a 6 3 0 0 1 12 0 v 12 a 6 3 0 0 1 -12 0 z",
        class: "pc-data-shape",
      }, icon);
      node("path", { d: "M 9 6 a 6 3 0 0 0 12 0", class: "pc-data-fold" }, icon);
    } else {
      node("path", {
        d: "M 10 3 H 18 L 22 7 V 21 H 10 Z", class: "pc-data-shape",
      }, icon);
      node("path", { d: "M 18 3 V 7 H 22", class: "pc-data-fold" }, icon);
    }
  } else {
    node("rect", {
      x: 2, y: 4, width: 26, height: 16, rx: 3,
      class: `pc-box${item.kind === "callActivity" ? " call" : ""}`
        + `${item.kind === "eventSubProcess" ? " event-sub" : ""}`,
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
  host.appendChild(modelControl());
  if (paletteFolded) return;

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
    // A pool, and a data node, stand on their own.
    const needsPool = !["add-pool", "add-data"].includes(item.op);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pp-item";
    button.appendChild(paletteIcon(item));
    button.appendChild(document.createTextNode(item.label));
    // Not disabled while no participant is picked: it can still be dragged onto one.
    const waiting = needsPool && !pool;
    button.title = waiting
      ? `${item.hint} — drag it onto a participant, or click one first` : `${item.hint} — click or drag`;
    button.classList.toggle("waiting", waiting);
    button.setAttribute("aria-disabled", waiting ? "true" : "false");
    button.addEventListener("pointerdown", (ev) => startPaletteDrag(ev, button, item));
    button.addEventListener("click", () => {
      if (swallowPaletteClick) { swallowPaletteClick = false; return; }
      if (!waiting) { insertFromPalette(item, { pool: selectedPool, lane: selectedLane }); return; }
      note.textContent = "drag it onto a participant, or click a participant first";
      note.classList.add("pp-note-nudge");
    });
    section.appendChild(button);
  });
  const note = document.createElement("span");
  note.className = "pp-note";
  const lane = data && (data.lanes || []).find((l) => l.id === selectedLane);
  note.textContent = pool
    ? `adding to: ${pool.label}${lane ? ` › ${lane.label}` : ""}`
    : "click a participant to add steps to it, or drag a shape onto one";
  host.appendChild(note);
  // Visibility belongs to the level switch, not to render.
}

let swallowPaletteClick = false;

/* What a palette shape adds, into `where` (a participant and maybe a lane). */
async function insertFromPalette(item, where) {
  if (item.op === "add-pool") {
    const label = window.prompt("Name of the participant (an organisation, a customer, a team):");
    const model = currentModel();
    if (label) await onEdit("add-pool", { label, ...(model && model.id ? { model: model.id } : {}) });
    return;
  }
  if (item.op === "add-lane") {
    const label = window.prompt("Name of the lane (a role, a team, a system):");
    if (label) await onEdit("add-lane", { pool: where.pool, label });
    return;
  }
  if (item.op === "add-event") {
    await onEdit("add-event", {
      ...where, kind: item.kind, definition: item.definition || "", label: "",
    });
  } else if (item.op === "add-gateway") {
    await onEdit("add-gateway", { ...where, kind: item.kind, label: "" });
  } else if (item.op === "add-annotation") {
    const body = window.prompt("What should the note say?");
    if (body) await onEdit("add-annotation", { ...where, text: body });
  } else if (item.op === "add-data") {
    const label = window.prompt(
      item.shape === "store" ? "Name of the data store:" : "Name of the document:");
    // No activity: it stands on its own until something is joined to it.
    if (label) await onEdit("add-data", { shape: item.shape, label });
  } else {
    await onEdit("add-activity", { ...where, kind: item.kind, label: item.label });
  }
}

/* Drag a shape out of the palette and drop it on a participant or a lane, as an
   element is dropped on the architecture canvas. Below the threshold it stays a click. */
function startPaletteDrag(ev, button, item) {
  if (ev.button !== 0) return;
  // A drag released off its button fires no click, so a flag left armed would eat this one.
  swallowPaletteClick = false;
  const from = { x: ev.clientX, y: ev.clientY };
  let ghost = null;
  const move = (mv) => {
    if (!ghost) {
      if (Math.hypot(mv.clientX - from.x, mv.clientY - from.y) < 6) return;
      ghost = button.cloneNode(true);
      ghost.classList.add("palette-ghost");
      document.body.appendChild(ghost);
    }
    ghost.style.left = mv.clientX + 10 + "px";
    ghost.style.top = mv.clientY + 10 + "px";
  };
  const up = (uv) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    if (!ghost) return;
    ghost.remove();
    swallowPaletteClick = true;
    const box = svg.getBoundingClientRect();
    const onCanvas = uv.clientX >= box.left && uv.clientX <= box.right
      && uv.clientY >= box.top && uv.clientY <= box.bottom
      && !(uv.target && uv.target.closest && uv.target.closest("#process-palette"));
    if (!onCanvas) return;
    const at = svgPoint(uv.clientX, uv.clientY);
    const pool = bandGeometry().find((p) => !p.collapsed
      && at.x >= p.x && at.x <= p.x + p.w && at.y >= p.y && at.y <= p.y + p.h);
    const needsPool = !["add-pool", "add-data"].includes(item.op);
    if (needsPool && !pool) return;
    const band = pool && (pool.lanes || []).find((b) => !b.implicit && at.y >= b.y && at.y <= b.y + b.h);
    if (pool) {
      // The participant it landed in is now the one the palette adds to.
      selectedPool = pool.participant.id;
      selectedLane = band ? band.id : null;
    }
    insertFromPalette(item, { pool: pool ? pool.participant.id : null, lane: band ? band.id : null });
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function init(options) {
  svg = document.querySelector(options.svg);
  onOpenArchitecture = options.onOpenArchitecture || null;
  onEdit = options.onEdit || null;
  onSelect = options.onSelect || null;
  onPick = options.onPick || null;
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
function setSystemContext(refined, options) {
  refinedSystems = refined || [];
  contextOptions = options || [];
}
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
  picked = new Set();
  if (wantedModel !== null && (next.models || []).some((m) => m.id === wantedModel)) {
    selectedModel = wantedModel;
    wantedModel = null;
  }
  // Keep an activity open across a re-render, but forget one that is gone.
  expanded = new Set([...expanded].filter((id) => index.has(id)));
  const pools = new Set(next.participants.map((p) => p.id));
  const shown = next.participants.filter((p) => inModel(p.id));
  if (!pools.has(selectedPool) || !inModel(selectedPool)) selectedPool = shown.length ? shown[0].id : null;
  const lanes = new Set((next.lanes || []).map((l) => l.id));
  if (!lanes.has(selectedLane)) selectedLane = null;
  collapsedPools = new Set([...collapsedPools].filter((id) => pools.has(id)));
  draw();
  renderPalette();
}

function hasProcess() {
  return Boolean(data && data.stats && data.stats.activities);
}

function forgetLayout() {
  manualPositions = new Map();
  bandHeights = new Map();
  poolWidth = 0;
  lastFitIds = null;
}

export const ProcessCanvas = {
  init, render, fit, zoomBy, hasProcess, setSystems, setSystemContext, setDataClasses,
  setFindings, forgetLayout,
  svgRoot: () => svg,
};
