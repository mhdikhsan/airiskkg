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
  const BOX_W = 220;
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
    let height = BOX_H;
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
    node("circle", { cx: x1, cy: y1, r: 3.5, class: "pc-msg-start" }, parent);
    const t = text(parent, (x1 + x2) / 2, mid - 4, label, "pc-flow-label");
    t.setAttribute("text-anchor", "middle");
  }


  /* BPMN draws what kind of work an activity is as a small marker in the
   * top-left corner, not as a word. Anyone who has seen a process diagram reads
   * the envelope and the little person without being told; the uppercase
   * "RECEIVETASK" we printed instead was ours, not BPMN's. */
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

  function drawActivity(parent, slot) {
    const { activity } = slot;
    const group = node("g", {
      class: `pc-activity${activity.refines.length ? " refined" : ""}${activity.human ? " human" : ""}`,
    }, parent);

    node("rect", {
      x: slot.x, y: slot.y, width: slot.w, height: slot.h, rx: 8, class: "pc-box",
    }, group);
    const hint = node("title", {}, group);
    hint.textContent = activity.refines.length
      ? "Open the AI architecture that carries out this activity"
      : (activity.children.length ? "Click + to show the steps inside" : "Edit this activity");

    typeMarker(group, activity.kind, slot.x + 8, slot.y + 7);
    /* The risk badge sits at the top right, so the name has to give way to it
     * rather than run underneath. Measured in characters because the label is
     * the thing that gets cut, and cutting it visibly beats overlapping. */
    const nameRoom = riskOf(activity) && riskOf(activity).findings ? 18 : 26;
    text(group, slot.x + 26, slot.y + 17, truncate(activity.label, nameRoom), "pc-label");

    if (activity.performers.length) {
      const row = activity.refines.length ? 48 : 34;
      text(group, slot.x + 26, slot.y + row, truncate(activity.performers.join(", "), 24), "pc-by");
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

    /* How many candidate risks this activity carries, and which. A count alone
     * is a number nobody can act on; the whole list at once is a wall. So the
     * badge folds - the same idiom the sub-process marker already uses - and a
     * reader opens the one activity they are asking about. */
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
      /* A badge, not a button. The box itself opens the architecture - a pill
       * with 9.5px type was the only way in, and nobody aims for it when the
       * whole box looks like the thing they mean. On its own line, because
       * sharing one with the label clipped both. */
      const chip = node("g", { class: "pc-open" }, group);
      const chipW = 74;
      node("rect", {
        x: slot.x + 26, y: slot.y + 23, width: chipW, height: 15, rx: 7, class: "pc-open-box",
      }, chip);
      const badge = text(chip, slot.x + 26 + chipW / 2, slot.y + 34, "AI system ›", "pc-open-label");
      badge.setAttribute("text-anchor", "middle");
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

      /* One primary action per box, and it is the one the shape promises.
       * An activity carried out by an AI system opens that system - which is
       * what "expand this sub-process" means here. Everything else opens its
       * editor. The pencil is there when you want to edit a refined one. */
      group.addEventListener("click", (ev) => {
        if (swallowNextClick) { swallowNextClick = false; return; }
        if (ev.target.closest(".pc-marker, .pc-port, .pc-edit, .pc-risk")) return;
        ev.stopPropagation();
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
    const y1 = connecting.slot.y + BOX_H / 2;
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
        if (swallowNextClick) { swallowNextClick = false; return; }
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
    /* Capture is taken only once a drag is really under way.
     *
     * Capturing on pointerdown - the obvious way to write this - retargets
     * every later pointer event, and the click that follows, to the <svg>
     * itself. So the click never reached the activity group and the canvas felt
     * dead: press a box, nothing happens. It looked like a listener problem and
     * was not.
     *
     * A movement threshold keeps a click a click. Past it, the gesture is a pan,
     * capture is taken so the drag survives leaving the element, and the click
     * that the browser fires afterwards is dropped - otherwise letting go over a
     * box would open it. */
    const DRAG_THRESHOLD = 4;
    let pan = null;

    svg.addEventListener("pointerdown", (ev) => {
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
    /* Visibility belongs to the level switch, not here. Un-hiding on every
     * render put the BPMN palette on top of the architecture canvas, over the
     * BEAM one, whichever level the reader had chosen. */
  }

  function init(options) {
    svg = document.querySelector(options.svg);
    onOpenArchitecture = options.onOpenArchitecture || null;
    onEdit = options.onEdit || null;
    if (svg) initPanZoom();
  }

  function setSystems(list) { systems = list || []; }

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

  window.ProcessCanvas = { init, render, fit, hasProcess, setSystems, setFindings, svgRoot: () => svg };
})();
