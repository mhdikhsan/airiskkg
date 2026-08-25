/* The business layer, drawn.
 *
 * A second surface rather than a second mode of graph.js. The two draw
 * different things with different rules - BEAM has no notion of a pool and BPMN
 * has no notion of a flow port - and graph.js is 800 lines with no test around
 * it, so bending it into both shapes would put every existing behaviour at risk
 * to save a viewport.
 *
 * What it draws, and why only this much: pools as bands, activities left to
 * right in flow order, sequence flow inside a pool, message flow across the
 * boundary between pools. That is the vocabulary a stakeholder reads. Gateways,
 * events and boundary markers are deliberately absent - a faithful BPMN
 * renderer is a project of its own, and the one good off-the-shelf option puts
 * a permanent watermark in the page.
 *
 * Exposes window.ProcessCanvas.
 */
(function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";

  const POOL_LABEL_W = 34;   // the vertical name strip down a pool's left edge
  const POOL_PAD = 20;
  const BOX_W = 190;
  const BOX_H = 58;
  const BOX_GAP = 52;        // room for an arrow between two activities
  const CHILD_H = 30;
  const POOL_GAP = 34;

  let svg = null;
  let root = null;
  let data = null;
  let expanded = new Set();   // subprocesses opened in place
  let onOpenArchitecture = null;
  let onEdit = null;            // (op, payload) -> Promise, applied server-side
  let systems = [];             // architectures a activity may be refined by
  let selectedPool = null;      // where a new activity lands
  let connecting = null;        // drag in progress: { from, line }
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

  function boxHeight(activity) {
    if (!expanded.has(activity.id) || !activity.children.length) return BOX_H;
    return BOX_H + activity.children.length * CHILD_H + 10;
  }

  function layout() {
    const placed = new Map();
    const pools = [];
    let y = POOL_PAD;

    data.participants.forEach((participant) => {
      const activities = topLevelOf(participant);
      let x = POOL_LABEL_W + POOL_PAD;
      let tallest = BOX_H;
      activities.forEach((activity) => {
        const h = boxHeight(activity);
        tallest = Math.max(tallest, h);
        placed.set(activity.id, { x, y: y + POOL_PAD, w: BOX_W, h, activity });
        x += BOX_W + BOX_GAP;
      });
      const poolH = tallest + POOL_PAD * 2;
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
    const y1 = from.y + BOX_H / 2;
    const x2 = to.x;
    const y2 = to.y + BOX_H / 2;
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
    const t = text(parent, (x1 + x2) / 2, mid - 4, label, "pc-flow-label");
    t.setAttribute("text-anchor", "middle");
  }

  function drawActivity(parent, slot) {
    const { activity } = slot;
    const group = node("g", {
      class: `pc-activity${activity.refines.length ? " refined" : ""}${activity.human ? " human" : ""}`,
    }, parent);

    node("rect", {
      x: slot.x, y: slot.y, width: slot.w, height: slot.h, rx: 8, class: "pc-box",
    }, group);

    text(group, slot.x + 12, slot.y + 20, activity.kind, "pc-kind");
    text(group, slot.x + 12, slot.y + 39, truncate(activity.label, 24), "pc-label");

    if (activity.performers.length) {
      text(group, slot.x + 12, slot.y + 53, truncate(activity.performers.join(", "), 26), "pc-by");
    }

    /* Two ways in, and they answer different questions: the inner flow says
     * what the service does as business steps, the architecture says which AI
     * system carries them out. Offer both rather than guessing. */
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
        const cy = slot.y + BOX_H + index * CHILD_H;
        node("rect", {
          x: slot.x + 12, y: cy, width: slot.w - 24, height: CHILD_H - 6, rx: 4, class: "pc-child",
        }, group);
        text(group, slot.x + 22, cy + 18, truncate(child.label, 26), "pc-child-label");
      });
    }

    if (activity.refines.length) {
      const chip = node("g", { class: "pc-open", cursor: "pointer" }, group);
      const chipW = 92;
      node("rect", {
        x: slot.x + slot.w - chipW - 10, y: slot.y + 8,
        width: chipW, height: 18, rx: 9, class: "pc-open-box",
      }, chip);
      const t = text(chip, slot.x + slot.w - chipW / 2 - 10, slot.y + 21, "⤢ architecture", "pc-open-label");
      t.setAttribute("text-anchor", "middle");
      chip.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (onOpenArchitecture) onOpenArchitecture(activity);
      });
      const title = node("title", {}, chip);
      title.textContent = "Open the AI architecture that carries out this activity";
    }
    if (onEdit) {
      /* Drag from the port to another activity. Whether that becomes a sequence
       * flow or a message is not asked: it follows from whether the two sit in
       * the same process, which is what BPMN says and what the server decides. */
      const port = node("g", { class: "pc-port", cursor: "crosshair" }, group);
      node("circle", {
        cx: slot.x + slot.w, cy: slot.y + BOX_H / 2, r: 7, class: "pc-port-dot",
      }, port);
      port.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        startConnect(ev, activity, slot);
      });
      const portTitle = node("title", {}, port);
      portTitle.textContent = "Drag onto another activity to connect";

      group.addEventListener("click", (ev) => {
        if (ev.target.closest(".pc-open, .pc-marker, .pc-port")) return;
        ev.stopPropagation();
        showDetail(activity, ev);
      });
      group.setAttribute("cursor", "pointer");
    }
    return group;
  }

  function svgPoint(clientX, clientY) {
    const rect = svg.getBoundingClientRect();
    return { x: (clientX - rect.left - view.x) / view.k, y: (clientY - rect.top - view.y) / view.k };
  }

  function startConnect(ev, activity, slot) {
    const line = node("path", { class: "pc-flow pending" }, root);
    connecting = { from: activity, slot, line };
    svg.setPointerCapture(ev.pointerId);
  }

  function moveConnect(ev) {
    if (!connecting) return;
    const to = svgPoint(ev.clientX, ev.clientY);
    const x1 = connecting.slot.x + connecting.slot.w;
    const y1 = connecting.slot.y + BOX_H / 2;
    connecting.line.setAttribute("d", `M ${x1} ${y1} L ${to.x} ${to.y}`);
  }

  async function endConnect(ev) {
    if (!connecting) return;
    const { from, line } = connecting;
    connecting = null;
    line.remove();
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

  function showDetail(activity, ev) {
    const panel = document.querySelector("#process-detail");
    if (!panel) return;
    const options = ['<option value="">— not an AI activity —</option>']
      .concat(systems.map((s) =>
        `<option value="${s.id}"${activity.refines.includes(s.id) ? " selected" : ""}>${s.label}</option>`))
      .join("");
    panel.innerHTML = `
      <div class="nd-head">${activity.kind}</div>
      <label class="nd-row"><span>Name</span>
        <input type="text" id="pd-name" value="${activity.label.replace(/"/g, "&quot;")}" /></label>
      <label class="nd-row"><span>Carried out by</span>
        <select id="pd-refines">${options}</select></label>
      <div class="nd-actions">
        <button type="button" class="btn small primary" id="pd-apply">Apply</button>
        <button type="button" class="btn small" id="pd-delete">Delete</button>
      </div>`;
    panel.classList.remove("hidden");
    const rect = svg.getBoundingClientRect();
    panel.style.left = `${Math.min(ev.clientX - rect.left + 12, rect.width - 260)}px`;
    panel.style.top = `${Math.min(ev.clientY - rect.top + 12, rect.height - 200)}px`;

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
    [["pc-arrow", "pc-arrow-head"], ["pc-arrow-msg", "pc-arrow-head message"]].forEach(([id, cls]) => {
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
        if (ev.target.closest(".pc-activity")) return;
        selectedPool = pool.participant.id;
        draw();
        renderPalette();
      });
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
    let panning = null;
    svg.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".pc-open, .pc-marker, .pc-port")) return;
      closeDetail();
      panning = { x: ev.clientX - view.x, y: ev.clientY - view.y };
      svg.setPointerCapture(ev.pointerId);
    });
    svg.addEventListener("pointermove", (ev) => {
      if (connecting) { moveConnect(ev); return; }
      if (!panning) return;
      view.x = ev.clientX - panning.x;
      view.y = ev.clientY - panning.y;
      applyView();
    });
    svg.addEventListener("pointerup", (ev) => {
      panning = null;
      if (connecting) endConnect(ev);
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
    host.classList.remove("hidden");
  }

  function init(options) {
    svg = document.querySelector(options.svg);
    onOpenArchitecture = options.onOpenArchitecture || null;
    onEdit = options.onEdit || null;
    if (svg) initPanZoom();
  }

  function setSystems(list) { systems = list || []; }

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

  window.ProcessCanvas = { init, render, fit, hasProcess, setSystems, svgRoot: () => svg };
})();
