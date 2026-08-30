/* The business layer, drawn: pools as bands, activities in flow order,
 * sequence flow within a pool and message flow across pools. Gateways, events
 * and boundary markers are deliberately absent. A separate surface from
 * graph_view.js, not a second mode of it. */

const SVG_NS = "http://www.w3.org/2000/svg";

const POOL_LABEL_W = 34;   // the vertical name strip down a pool's left edge
const POOL_PAD = 20;
const BOX_W = 244;
const BOX_H = 58;
const BOX_GAP = 52;        // room for an arrow between two activities
const CHILD_H = 30;
const POOL_GAP = 34;
const LINE_H = 14;         // a wrapped second line of an activity name
const DATA_W = 30;         // the folded page / cylinder itself
const DATA_H = 36;
const DATA_BAND = 92;      // the strip above a pool's activities, when it has data

let svg = null;
let root = null;
let data = null;
let expanded = new Set();   // subprocesses opened in place
let onOpenArchitecture = null;
let onEdit = null;            // (op, payload) -> Promise, applied server-side
let onSelect = null;          // (id) -> void, so a click can reach the source
let systems = [];             // architectures a activity may be refined by
let dataClasses = [];         // what a data object may be classified as
let selectedPool = null;      // where a new activity lands
let connecting = null;        // drag in progress: { from, line }
let swallowNextClick = false; // a pan ends in a click the reader did not mean
let findingsByActivity = new Map();  // activity id -> { findings, items }
let openRisks = new Set();           // activities whose risk list is unfolded
let view = { x: 0, y: 0, k: 1 };

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

function truncate(value, max) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

/* Wrap on words instead of cutting. A name reading "Check the meter r..." tells
 * a reader nothing about which of several meter activities they are looking
 * at; the full text also goes on the <title> so nothing is lost. */
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

function nameRoomOf(activity) {
  return riskOf(activity) && riskOf(activity).findings ? 19 : 28;
}

/* The block above the sub-process marker: type icon, name, chip, performers.
 * Everything inside a box is placed relative to this rather than to BOX_H, so
 * a name that needs two lines pushes the rest down instead of colliding. */
function headHeight(activity) {
  const lines = wrap(activity.label, nameRoomOf(activity), 2).length;
  return BOX_H + (lines - 1) * LINE_H;
}

function dataOf(activity) {
  return [
    ...activity.reads.map((d) => ({ ...d, direction: "in" })),
    ...activity.writes.map((d) => ({ ...d, direction: "out" })),
  ];
}

/* dpv:PersonalData reads as "Personal data" to someone who does not write RDF;
 * the prefixed form stays on the tooltip. */
export function humanKind(kind) {
  const local = String(kind).split(/[#:/]/).pop();
  const spaced = local.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

/** Activities of one pool, outermost only - children are drawn nested. */
function topLevelOf(participant) {
  return data.activities.filter(
    (a) => !a.parent && a.process && a.process === participant.process
  );
}

function childrenOf(activity) {
  const byId = new Map(data.activities.map((a) => [a.id, a]));
  return activity.children.map((id) => byId.get(id)).filter(Boolean);
}

const RISK_ROW_H = 17;

function riskOf(activity) {
  return findingsByActivity.get(activity.id) || null;
}

function boxHeight(activity) {
  let height = headHeight(activity);
  if (expanded.has(activity.id) && activity.children.length) {
    height += activity.children.length * CHILD_H + 10;
  }
  const risk = riskOf(activity);
  if (risk && openRisks.has(activity.id)) {
    height += risk.items.length * RISK_ROW_H + 12;
  }
  return height;
}

function layout() {
  const placed = new Map();
  const pools = [];
  let y = POOL_PAD;

  data.participants.forEach((participant) => {
    const activities = topLevelOf(participant);
    let x = POOL_LABEL_W + POOL_PAD;
    let tallest = BOX_H;
    // Data objects sit in a strip above the activities, so a pool with none
    // does not carry an empty band.
    const band = activities.some((a) => dataOf(a).length) ? DATA_BAND : 0;
    activities.forEach((activity) => {
      const h = boxHeight(activity);
      tallest = Math.max(tallest, h);
      placed.set(activity.id, {
        x, y: y + POOL_PAD + band, w: BOX_W, h,
        head: headHeight(activity), band, activity,
      });
      x += BOX_W + BOX_GAP;
    });
    const poolH = tallest + band + POOL_PAD * 2;
    pools.push({
      participant,
      x: 0,
      y,
      w: Math.max(x + POOL_PAD, POOL_LABEL_W + BOX_W + POOL_PAD * 2),
      h: poolH,
      activities,
    });
    y += poolH + POOL_GAP;
  });

  return { pools, placed, height: y };
}

function arrow(parent, from, to, dashed, label) {
  const x1 = from.x + from.w;
  const y1 = from.y + (from.head || BOX_H) / 2;
  const x2 = to.x;
  const y2 = to.y + (to.head || BOX_H) / 2;
  const sameRow = Math.abs(y1 - y2) < 2;
  const d = sameRow
    ? `M ${x1} ${y1} L ${x2} ${y2}`
    : `M ${x1} ${y1} C ${x1 + 40} ${y1}, ${x2 - 40} ${y2}, ${x2} ${y2}`;
  node("path", {
    d,
    class: dashed ? "pc-flow message" : "pc-flow",
    "marker-end": dashed ? "url(#pc-arrow-msg)" : "url(#pc-arrow)",
  }, parent);
  if (label) {
    const t = text(parent, (x1 + x2) / 2, (y1 + y2) / 2 - 6, label, "pc-flow-label");
    t.setAttribute("text-anchor", "middle");
  }
}

/** A message crosses a boundary: leave the source downward, enter the target. */
function messageArrow(parent, from, to, label) {
  const x1 = from.x + from.w / 2;
  const x2 = to.x + to.w / 2;
  const goingDown = to.y > from.y;
  const y1 = goingDown ? from.y + from.h : from.y;
  const y2 = goingDown ? to.y : to.y + to.h;
  const mid = (y1 + y2) / 2;
  node("path", {
    d: `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`,
    class: "pc-flow message",
    "marker-end": "url(#pc-arrow-msg)",
  }, parent);
  node("circle", { cx: x1, cy: y1, r: 3.5, class: "pc-msg-start" }, parent);
  const t = text(parent, (x1 + x2) / 2, mid - 4, label, "pc-flow-label");
  t.setAttribute("text-anchor", "middle");
}


// BPMN marks the kind of work with a corner glyph, not a word.
function typeMarker(parent, kind, x, y) {
  const g = node("g", { class: "pc-icon", transform: `translate(${x} ${y})` }, parent);
  if (kind === "userTask") {
    node("circle", { cx: 6, cy: 3.5, r: 2.6 }, g);
    node("path", { d: "M 1 11 a 5 5 0 0 1 10 0" }, g);
  } else if (kind === "manualTask") {
    node("path", { d: "M 2 10 v -4 a 1.4 1.4 0 0 1 2.8 0 v -2 a 1.4 1.4 0 0 1 2.8 0 v 1 a 1.4 1.4 0 0 1 2.8 0 v 5" }, g);
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
  }
  return g;
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
  }
  if (item.collection) {
    node("path", {
      d: `M ${x + DATA_W / 2 - 3} ${y + DATA_H - 7} v 6 M ${x + DATA_W / 2} ${y + DATA_H - 7} v 6 M ${x + DATA_W / 2 + 3} ${y + DATA_H - 7} v 6`,
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
  const items = dataOf(slot.activity);
  if (!items.length || !slot.band) return;
  const spread = Math.min(slot.w / items.length, 92);
  items.forEach((item, index) => {
    const cx = slot.x + spread * (index + 0.5) + (slot.w - spread * items.length) / 2;
    const top = slot.y - slot.band + 6;
    const g = dataGlyph(parent, cx - DATA_W / 2, top, item);
    if (item.direction === "in") {
      dataAssociation(g, cx, top + DATA_H + 2, cx, slot.y - 4);
    } else {
      dataAssociation(g, cx, slot.y - 4, cx, top + DATA_H + 2);
    }
    wrap(item.label, 16, 2).forEach((line, row) => {
      const label = text(g, cx, top + DATA_H + 13 + row * 11, line, "pc-data-label");
      label.setAttribute("text-anchor", "middle");
    });
    if (item.kinds.length) {
      const chip = text(g, cx, top - 4, item.kinds.map(humanKind).join(", "), "pc-data-kind");
      chip.setAttribute("text-anchor", "middle");
    }
    const title = node("title", {}, g);
    title.textContent = `${item.label} — ${item.direction === "in" ? "read by" : "written by"} `
      + `${slot.activity.label}`
      + (item.kinds.length
        ? `\nClassified: ${item.kinds.join(", ")}`
        : "\nNot classified");
  });
}

function drawActivity(parent, slot) {
  const { activity } = slot;
  const group = node("g", {
    class: `pc-activity${activity.refines.length ? " refined" : ""}${activity.human ? " human" : ""}`,
  }, parent);

  node("rect", {
    x: slot.x, y: slot.y, width: slot.w, height: slot.h, rx: 8, class: "pc-box",
  }, group);
  const hint = node("title", {}, group);
  hint.textContent = `${activity.label}\n` + (activity.refines.length
    ? "Open the AI architecture that carries out this activity"
    : (activity.children.length ? "Click + to show the steps inside" : "Edit this activity"));

  typeMarker(group, activity.kind, slot.x + 8, slot.y + 7);
  // The risk badge owns the top right, so the name wraps under it.
  const lines = wrap(activity.label, nameRoomOf(activity), 2);
  lines.forEach((line, index) => {
    text(group, slot.x + 26, slot.y + 17 + index * LINE_H, line, "pc-label");
  });
  const afterName = slot.y + 17 + (lines.length - 1) * LINE_H;

  if (activity.performers.length) {
    const row = afterName + (activity.refines.length ? 31 : 17);
    text(group, slot.x + 26, row, truncate(activity.performers.join(", "), 26), "pc-by");
  }

  // Two ways in: the inner flow, and the architecture that carries it.
  if (activity.children.length) {
    const marker = node("g", { class: "pc-marker" }, group);
    node("rect", {
      x: slot.x + slot.w / 2 - 9, y: slot.y + slot.h - 9,
      width: 18, height: 18, rx: 3, class: "pc-marker-box",
    }, marker);
    const sign = text(marker, slot.x + slot.w / 2, slot.y + slot.h + 4,
      expanded.has(activity.id) ? "−" : "+", "pc-marker-sign");
    sign.setAttribute("text-anchor", "middle");
    marker.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (expanded.has(activity.id)) expanded.delete(activity.id);
      else expanded.add(activity.id);
      draw();
    });
    marker.setAttribute("cursor", "pointer");
    const title = node("title", {}, marker);
    title.textContent = expanded.has(activity.id)
      ? "Collapse the business steps inside this activity"
      : "Show the business steps inside this activity";
  }

  if (expanded.has(activity.id) && activity.children.length) {
    childrenOf(activity).forEach((child, index) => {
      const cy = slot.y + slot.head + index * CHILD_H;
      node("rect", {
        x: slot.x + 12, y: cy, width: slot.w - 24, height: CHILD_H - 6, rx: 4, class: "pc-child",
      }, group);
      text(group, slot.x + 22, cy + 18, truncate(child.label, 26), "pc-child-label");
    });
  }

  // Candidate risks for this activity; the badge folds the list.
  const risk = riskOf(activity);
  if (risk && risk.findings) {
    const open = openRisks.has(activity.id);
    const badge = node("g", { class: "pc-risk", cursor: "pointer" }, group);
    const width = 54;
    node("rect", {
      x: slot.x + slot.w - width - 10, y: slot.y + 8,
      width, height: 17, rx: 8, class: "pc-risk-box",
    }, badge);
    const caption = text(badge, slot.x + slot.w - width / 2 - 10, slot.y + 20,
      `${risk.findings} risk${risk.findings === 1 ? "" : "s"} ${open ? "⌃" : "⌄"}`,
      "pc-risk-label");
    caption.setAttribute("text-anchor", "middle");
    badge.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (open) openRisks.delete(activity.id); else openRisks.add(activity.id);
      draw();
    });
    const riskTitle = node("title", {}, badge);
    riskTitle.textContent = open
      ? "Hide the candidate risks found here"
      : "Show the candidate risks found here";

    if (open) {
      let rowY = slot.y + slot.h - risk.items.length * RISK_ROW_H - 6;
      risk.items.forEach((item) => {
        text(group, slot.x + 26, rowY + 11, "• " + truncate(item.label, 34), "pc-risk-item");
        rowY += RISK_ROW_H;
      });
    }
  }

  if (activity.refines.length) {
    // A badge, not a button: the box itself opens the architecture.
    const chip = node("g", { class: "pc-open" }, group);
    const chipW = 74;
    node("rect", {
      x: slot.x + 26, y: afterName + 6, width: chipW, height: 15, rx: 7, class: "pc-open-box",
    }, chip);
    const badge = text(chip, slot.x + 26 + chipW / 2, afterName + 17, "AI system ›", "pc-open-label");
    badge.setAttribute("text-anchor", "middle");
  }
  if (onEdit) {
    // Sequence flow or message flow follows from the pools; the server decides.
    const port = node("g", { class: "pc-port", cursor: "crosshair" }, group);
    node("circle", {
      cx: slot.x + slot.w, cy: slot.y + slot.head / 2, r: 7, class: "pc-port-dot",
    }, port);
    port.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
      startConnect(ev, activity, slot);
    });
    const portTitle = node("title", {}, port);
    portTitle.textContent = "Drag onto another activity to connect";

    // One primary action per box: a refined activity opens its architecture.
    group.addEventListener("click", (ev) => {
      if (ev.target.closest(".pc-marker, .pc-port, .pc-edit, .pc-risk")) return;
      ev.stopPropagation();
      if (onSelect) onSelect(activity.id);
      if (activity.refines.length && onOpenArchitecture) onOpenArchitecture(activity);
      else showDetail(activity, ev);
    });
    group.setAttribute("cursor", "pointer");

    if (activity.refines.length) {
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
        showDetail(activity, ev);
      });
      const editTitle = node("title", {}, pencil);
      editTitle.textContent = "Edit this activity";
    }
  }
  return group;
}

function svgPoint(clientX, clientY) {
  const rect = svg.getBoundingClientRect();
  return { x: (clientX - rect.left - view.x) / view.k, y: (clientY - rect.top - view.y) / view.k };
}

function startConnect(ev, activity, slot) {
  const line = node("path", { class: "pc-flow pending" }, root);
  connecting = { from: activity, slot, line, id: ev.pointerId };
  // Held for the length of the drag so it survives leaving the port, and
  // released in endConnect - a capture left standing swallows every later
  // click on the canvas.
  try { svg.setPointerCapture(ev.pointerId); } catch (error) { /* already gone */ }
}

function moveConnect(ev) {
  if (!connecting) return;
  const to = svgPoint(ev.clientX, ev.clientY);
  const x1 = connecting.slot.x + connecting.slot.w;
  const y1 = connecting.slot.y + connecting.slot.head / 2;
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
  const group = dropped && dropped.closest(".pc-activity");
  if (!group) return;
  const target = [...root.querySelectorAll(".pc-activity")].indexOf(group);
  const targetId = drawnOrder[target];
  if (!targetId || targetId === from.id) return;
  await onEdit("connect", { source: from.id, target: targetId });
}

let drawnOrder = [];

function closeDetail() {
  const panel = document.querySelector("#process-detail");
  if (panel) panel.classList.add("hidden");
}

function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
}

function classOptions(selected) {
  return ['<option value="">— not classified —</option>']
    .concat(dataClasses.map((c) =>
      `<option value="${c.id}"${c.id === selected ? " selected" : ""}>${escapeHtml(c.label)}</option>`))
    .join("");
}

/* The data rows are why this panel exists at all now: a classification on a
 * data object is what business_data_bridge.rq turns into a data category on the
 * architecture, and it was previously only reachable by hand-writing three
 * BPMN nodes in Turtle. */
function dataRows(activity) {
  const items = dataOf(activity);
  if (!items.length) return '<div class="pd-empty">No data attached yet.</div>';
  return items.map((item) => `
    <div class="pd-data" data-ref="${escapeHtml(item.id)}">
      <span class="pd-dir">${item.direction === "in" ? "reads" : "writes"}</span>
      <span class="pd-name" title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</span>
      <select class="pd-class">${classOptions(item.kinds[0] || "")}</select>
      <button type="button" class="pd-drop" title="Detach this data from the activity">×</button>
    </div>`).join("");
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
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-pool-apply">Apply</button>
      <button type="button" class="btn small" id="pd-pool-delete">Delete</button>
    </div>`;
  panel.classList.remove("hidden");
  const rect = svg.getBoundingClientRect();
  panel.style.left = `${Math.min(ev.clientX - rect.left + 12, rect.width - 300)}px`;
  panel.style.top = `${Math.max(8, Math.min(ev.clientY - rect.top + 12, rect.height - 200))}px`;

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

function showDetail(activity, ev) {
  const panel = document.querySelector("#process-detail");
  if (!panel) return;
  const options = ['<option value="">— not an AI activity —</option>']
    .concat(systems.map((s) =>
      `<option value="${s.id}"${activity.refines.includes(s.id) ? " selected" : ""}>${escapeHtml(s.label)}</option>`))
    .join("");
  panel.innerHTML = `
    <div class="nd-head">${activity.kind}</div>
    <label class="nd-row"><span>Name</span>
      <input type="text" id="pd-name" value="${escapeHtml(activity.label)}" /></label>
    <label class="nd-row"><span>Carried out by</span>
      <select id="pd-refines">${options}</select></label>
    <div class="pd-section">Data</div>
    ${dataRows(activity)}
    <div class="pd-add">
      <select id="pd-dir"><option value="in">reads</option><option value="out">writes</option></select>
      <input type="text" id="pd-data-name" placeholder="name of the data" />
      <select id="pd-data-class">${classOptions("")}</select>
      <button type="button" class="btn small" id="pd-data-add">Add</button>
    </div>
    <div class="nd-actions">
      <button type="button" class="btn small primary" id="pd-apply">Apply</button>
      <button type="button" class="btn small" id="pd-delete">Delete</button>
    </div>`;
  panel.classList.remove("hidden");
  const rect = svg.getBoundingClientRect();
  panel.style.left = `${Math.min(ev.clientX - rect.left + 12, rect.width - 300)}px`;
  panel.style.top = `${Math.max(8, Math.min(ev.clientY - rect.top + 12, rect.height - 300))}px`;

  panel.querySelectorAll(".pd-data").forEach((row) => {
    const reference = row.dataset.ref;
    row.querySelector(".pd-class").addEventListener("change", async (event) => {
      closeDetail();
      await onEdit("classify-data", { reference, classification: event.target.value });
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
    closeDetail();
    await onEdit("add-data", { activity: activity.id, direction, label, classification });
  });

  panel.querySelector("#pd-apply").addEventListener("click", async () => {
    const name = panel.querySelector("#pd-name").value.trim();
    const system = panel.querySelector("#pd-refines").value;
    closeDetail();
    if (name && name !== activity.label) await onEdit("rename", { element: activity.id, label: name });
    await onEdit("set-refines", { activity: activity.id, system });
  });
  panel.querySelector("#pd-delete").addEventListener("click", async () => {
    closeDetail();
    await onEdit("delete", { element: activity.id });
  });
}

function draw() {
  if (!svg || !data) return;
  svg.innerHTML = "";

  const defs = node("defs", {}, svg);
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

  root = node("g", { id: "pc-root" }, svg);
  drawnOrder = [];
  const { pools, placed } = layout();

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
      if (ev.target.closest(".pc-activity, .pc-pool-edit")) return;
      selectedPool = pool.participant.id;
      if (onSelect) onSelect(pool.participant.id);
      draw();
      renderPalette();
    });

    /* A pool could be added and never removed: the delete op has handled a
     * participant all along - it takes the process and its activities with it -
     * but nothing on the canvas asked for it. */
    if (onEdit) {
      const edit = node("g", { class: "pc-pool-edit", cursor: "pointer" }, group);
      node("rect", {
        x: pool.x + pool.w - 26, y: pool.y + 6, width: 18, height: 18, rx: 3,
        class: "pc-marker-box",
      }, edit);
      // The far corner: the near one carries the rotated pool name.
      const glyph = text(edit, pool.x + pool.w - 17, pool.y + 19, "\u22ef", "pc-marker-sign");
      glyph.setAttribute("text-anchor", "middle");
      node("title", {}, edit).textContent = "Rename or delete this participant";
      edit.addEventListener("click", (ev) => {
        ev.stopPropagation();
        showPoolDetail(pool.participant, ev);
      });
    }
    const label = text(group, 0, 0, truncate(pool.participant.label, 24), "pc-pool-label");
    label.setAttribute("text-anchor", "middle");
    label.setAttribute(
      "transform",
      `translate(${pool.x + POOL_LABEL_W / 2}, ${pool.y + pool.h / 2}) rotate(-90)`
    );

    // sequence flow: consecutive activities inside this pool
    pool.activities.forEach((activity, index) => {
      const next = pool.activities[index + 1];
      if (next) arrow(group, placed.get(activity.id), placed.get(next.id), false, null);
    });
    pool.activities.forEach((activity) => {
      drawnOrder.push(activity.id);
      drawData(group, placed.get(activity.id));
      drawActivity(group, placed.get(activity.id));
    });
  });

  // message flow: what crosses a boundary between actors
  data.messageFlows.forEach((flow) => {
    const from = placed.get(flow.source);
    const to = placed.get(flow.target);
    if (from && to) messageArrow(root, from, to, flow.label);
  });

  fit();
}

function applyView() {
  if (root) root.setAttribute("transform", `translate(${view.x} ${view.y}) scale(${view.k})`);
}

function fit() {
  if (!root || !svg) return;
  const box = root.getBBox();
  const rect = svg.getBoundingClientRect();
  if (!box.width || !box.height || !rect.width) return;
  const k = Math.min(rect.width / (box.width + 60), rect.height / (box.height + 60), 1.2);
  view = {
    k,
    x: (rect.width - box.width * k) / 2 - box.x * k,
    y: (rect.height - box.height * k) / 2 - box.y * k,
  };
  applyView();
}

function initPanZoom() {
  /* Capture only once a drag is really under way: capturing on pointerdown
   * retargets the following click to the <svg> and no box ever opens.
   * Covered by test_canvas_interaction.py. */
  const DRAG_THRESHOLD = 4;
  let pan = null;

  svg.addEventListener("pointerdown", (ev) => {
    // Clear here: a flag left armed eats the next real click.
    swallowNextClick = false;
    if (ev.target.closest(".pc-open, .pc-marker, .pc-port, .pc-edit, .pc-risk")) return;
    closeDetail();
    pan = {
      id: ev.pointerId,
      fromX: ev.clientX, fromY: ev.clientY,
      originX: view.x, originY: view.y,
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
      svg.classList.add("panning");
      try { svg.setPointerCapture(pan.id); } catch (error) { /* already gone */ }
    }
    view.x = pan.originX + dx;
    view.y = pan.originY + dy;
    applyView();
  });

  const release = (ev) => {
    if (connecting) endConnect(ev);
    if (pan && pan.moved) {
      svg.classList.remove("panning");
      try { svg.releasePointerCapture(pan.id); } catch (error) { /* already gone */ }
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
    svg.classList.remove("panning");
    pan = null;
  });

  svg.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const factor = ev.deltaY < 0 ? 1.1 : 0.9;
    const rect = svg.getBoundingClientRect();
    const cx = ev.clientX - rect.left;
    const cy = ev.clientY - rect.top;
    view.x = cx - (cx - view.x) * factor;
    view.y = cy - (cy - view.y) * factor;
    view.k *= factor;
    applyView();
  }, { passive: false });
}

const PALETTE = [
  { op: "add-pool", label: "Participant", hint: "A pool: an actor with a boundary" },
  { kind: "receiveTask", label: "Receive", hint: "Waits for a message" },
  { kind: "task", label: "Task", hint: "A step of work" },
  { kind: "userTask", label: "User task", hint: "A person does it - and can review what an AI produced" },
  { kind: "serviceTask", label: "Service task", hint: "Automated: where an AI capability usually sits" },
  { kind: "subProcess", label: "Sub-process", hint: "Has a flow of its own, and may name an architecture" },
  { kind: "sendTask", label: "Send", hint: "Sends a message" },
];

function renderPalette() {
  const host = document.querySelector("#process-palette");
  if (!host || !onEdit) return;
  host.innerHTML = "";
  const pool = data && data.participants.find((p) => p.id === selectedPool);
  PALETTE.forEach((item) => {
    const needsPool = !item.op;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pp-item";
    button.textContent = item.label;
    button.title = needsPool && !pool
      ? `${item.hint} — click a participant first`
      : item.hint;
    button.disabled = needsPool && !pool;
    button.addEventListener("click", async () => {
      if (item.op === "add-pool") {
        const label = window.prompt("Name of the participant (an organisation, a customer, a team):");
        if (label) await onEdit("add-pool", { label });
        return;
      }
      await onEdit("add-activity", { pool: selectedPool, kind: item.kind, label: item.label });
    });
    host.appendChild(button);
  });
  const note = document.createElement("span");
  note.className = "pp-note";
  note.textContent = pool ? `adding to: ${pool.label}` : "click a participant to add steps to it";
  host.appendChild(note);
  // Visibility belongs to the level switch, not to render.
}

function init(options) {
  svg = document.querySelector(options.svg);
  onOpenArchitecture = options.onOpenArchitecture || null;
  onEdit = options.onEdit || null;
  onSelect = options.onSelect || null;
  if (svg) initPanZoom();
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
  // Keep an activity open across a re-render, but forget one that is gone.
  const ids = new Set(next.activities.map((a) => a.id));
  expanded = new Set([...expanded].filter((id) => ids.has(id)));
  const pools = new Set(next.participants.map((p) => p.id));
  if (!pools.has(selectedPool)) selectedPool = next.participants.length ? next.participants[0].id : null;
  draw();
  renderPalette();
}

function hasProcess() {
  return Boolean(data && data.stats && data.stats.activities);
}

export const ProcessCanvas = { init, render, fit, hasProcess, setSystems, setDataClasses, setFindings, svgRoot: () => svg };