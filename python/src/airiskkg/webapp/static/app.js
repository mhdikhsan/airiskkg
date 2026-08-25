"use strict";

(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function el(tag, attrs = {}, children = []) {
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

  async function api(url, options) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  function postJson(url, body) {
    return api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  }

  async function postForFile(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = /filename="([^"]+)"/.exec(disposition);
    return {
      blob: await res.blob(),
      findings: res.headers.get("X-PAIR-AI-Findings") || "0",
      matches: res.headers.get("X-PAIR-AI-Matches") || "0",
      filename: match ? match[1] : null,
    };
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    requestAnimationFrame(() => URL.revokeObjectURL(url));
  }

  function exportBaseName() {
    const selected = $("#example-select");
    const name = selected && selected.value ? selected.value : "";
    return (name || "architecture").replace(/\.(ttl|turtle|nt)$/i, "");
  }

  //status bar
  function setStatus(state, message, stats) {
    const dot = $("#status-dot");
    dot.className = `status-dot ${state}`;
    $("#status-text").textContent = message;
    $("#status-stats").textContent = stats || "";
  }

  function parseErrorLine(message) {
    const match = /line (\d+)/i.exec(message);
    return match ? Number(match[1]) : null;
  }

  let lastRun = null; // { fingerprint, findingIds: Set }
  let staleTimer = null;
  let pendingCause = null;

  function noteChange(cause) {
    pendingCause = cause;
  }

  function setTabVisible(name, visible) {
    const tab = document.querySelector(`[data-drawer-tab="${name}"]`);
    if (!tab) return;
    tab.classList.toggle("hidden", !visible);
    /* Hiding the tab someone is reading would leave the drawer showing a panel
     * with no tab above it, which looks like the app lost its place. */
    if (!visible && tab.classList.contains("active")) openDrawer("findings");
  }

  function setStale(isStale) {
    $("#findings-stale").classList.toggle("hidden", !isStale);
  }

  function scheduleStaleCheck(ttl) {
    if (!lastRun) return;
    clearTimeout(staleTimer);
    staleTimer = setTimeout(async () => {
      try {
        const { fingerprint } = await postJson("/api/fingerprint", { ttl });
        setStale(fingerprint !== lastRun.fingerprint);
      } catch (error) {
      }
    }, 400);
  }

  function runDelta(findings) {
    if (!lastRun) return null;
    const now = new Set(findings.map((f) => f.id));
    const cleared = [...lastRun.findingIds].filter((id) => !now.has(id)).length;
    const raised = [...now].filter((id) => !lastRun.findingIds.has(id)).length;
    return { cleared, raised };
  }

  function renderKnowledgeBaseBadge(run) {
    const badge = $("#kb-badge");
    const kb = run && run.knowledgeBase;
    if (!kb) { badge.classList.add("hidden"); return; }
    const parts = [`library ${kb.fingerprint}`];
    if (kb.revision) parts.push(kb.dirty ? `${kb.revision}+` : kb.revision);
    parts.push(`${kb.motifs} motifs · ${kb.riskPatterns} risk patterns`);
    badge.textContent = parts.join(" · ");
    badge.classList.toggle("dirty", Boolean(kb.dirty));
    badge.classList.remove("hidden");
  }

  /* ---- business process -----------------------------------------------------
   *
   * The layer above the architecture: what the organisation does, and which of
   * its activities this system carries out. Rendered as a list rather than a
   * diagram on purpose - what a risk assessment needs from a process is which
   * activity, in whose lane, reading what, performed by whom, and a row answers
   * each of those at least as well as a shape would.
   *
   * Activities arrive in flow order from the server, so this renders them as
   * given and never re-sorts. */
  /* Which layer the canvas is showing. "business" only becomes reachable once a
   * process is actually submitted - offering a level with nothing on it reads
   * as a broken feature rather than an empty one. */
  let level = "architecture";
  let levelChosenByHand = false;
  /* Which architecture the canvas is narrowed to, when a reader descended from
   * a business activity. Null means the whole document, which is right when it
   * holds one architecture and misleading when it holds two. */
  let scopedSystem = null;
  let openedFrom = null; // the activity a reader descended through

  function architectureHasContent() {
    return Boolean(lastGraph && lastGraph.nodes && lastGraph.nodes.length);
  }

  function setLevel(next, activity) {
    level = next;
    openedFrom = next === "architecture" ? activity || openedFrom : null;
    $("#canvas").classList.toggle("hidden", next !== "architecture");
    $("#process-canvas").classList.toggle("hidden", next !== "business");
    $("#level-business").classList.toggle("active", next === "business");
    $("#level-architecture").classList.toggle("active", next === "architecture");
    $("#canvas-hint").classList.toggle("hidden", next === "business");
    $("#process-palette").classList.toggle("hidden", next !== "business");
    $("#palette").classList.toggle("hidden", next !== "architecture");
    $("#motif-palette").classList.toggle("hidden", next !== "architecture");
    $("#process-detail").classList.add("hidden");
    /* Architecture furniture - the empty-state overlay, the legend, the system
     * badge - is absolutely positioned across the whole wrap, so it painted
     * over a perfectly good business diagram. One class, hidden in CSS. */
    $("#canvas-wrap").classList.toggle("business", next === "business");
    renderBreadcrumb();
    /* After the browser has actually laid the newly shown surface out. Fitting
     * synchronously measured an element that was display:none a statement ago
     * and produced a drawing the size of a full stop. */
    requestAnimationFrame(() => {
      if (next === "business") ProcessCanvas.fit();
      else GraphView.fit();
    });
  }

  function renderBreadcrumb() {
    const crumb = $("#breadcrumb");
    crumb.innerHTML = "";
    if (!openedFrom || level !== "architecture") {
      crumb.classList.add("hidden");
      return;
    }
    const parts = [
      { label: openedFrom.lane || "business process", to: "business" },
      { label: openedFrom.label, to: "business" },
      { label: "architecture", to: null },
    ];
    parts.forEach((part, index) => {
      if (index) crumb.appendChild(el("span", { class: "crumb-sep" }, "›"));
      if (part.to) {
        const link = el("button", { type: "button", class: "crumb-link" }, part.label);
        link.addEventListener("click", () => {
          scopedSystem = null;
          setLevel(part.to);
          refreshPreview(Editor.getValue());
        });
        crumb.appendChild(link);
      } else {
        crumb.appendChild(el("span", { class: "crumb-here" }, part.label));
      }
    });
    crumb.classList.remove("hidden");
  }

  async function refreshProcess(ttl) {
    const list = $("#process-list");
    const summary = $("#process-summary");
    const empty = $("#process-empty");
    let data;
    try {
      data = await postJson("/api/process", { ttl });
    } catch (error) {
      return; // an unparseable graph already says so in the status bar
    }

    ProcessCanvas.setSystems(
      (lastGraph && lastGraph.systems ? lastGraph.systems : []).map((s) => ({ id: s.id, label: s.label }))
    );
    lastProcess = data;
    ProcessCanvas.render(data);
    const hasProcess = data.stats.activities > 0;
    $("#level-switch").classList.toggle("hidden", !hasProcess);
    setTabVisible("process", hasProcess);

    /* Land where there is something to see. A process loaded on its own leaves
     * the architecture canvas legitimately empty - there are no BEAM elements -
     * and with nothing saying to press Business, both surfaces read as broken.
     * Only ever chosen for the reader, never taken away from them: once they
     * have picked a level by hand, it stays picked. */
    if (!hasProcess && level === "business") setLevel("architecture");
    else if (hasProcess && !levelChosenByHand && !architectureHasContent()) setLevel("business");

    list.innerHTML = "";
    summary.innerHTML = "";
    const count = data.stats.activities;
    $("#process-count").textContent = count ? String(count) : "";
    empty.classList.toggle("hidden", count > 0);
    if (!count) return;

    /* One line. It used to print a row per process, each repeating the same
     * global counts, so a two-pool collaboration claimed twice that "1 of 10
     * activities are AI" - both noisier and wrong. */
    const actors = data.participants.map((a) => a.label).join(" · ");
    const descriptive = data.processes.filter((x) => x.isExecutable === false).length;
    summary.appendChild(el("div", { class: "summary-row" }, [
      actors ? el("span", { class: "stat" }, actors) : null,
      el("span", { class: "stat" }, `${count} activities`),
      data.stats.refined ? el("span", { class: "stat" }, `${data.stats.refined} AI`) : null,
      data.stats.humanSteps ? el("span", { class: "stat" }, `${data.stats.humanSteps} human`) : null,
      descriptive
        ? el("span", { class: "hint" }, `${descriptive} not marked executable`)
        : null,
    ]));

    let lane = null;
    data.activities.forEach((activity) => {
      if (activity.lane !== lane) {
        lane = activity.lane;
        list.appendChild(el("div", { class: "proc-lane" }, lane || "no lane"));
      }
      const badges = [];
      if (activity.refines.length) badges.push(el("span", { class: "proc-badge ai" }, "AI system"));
      if (activity.human) badges.push(el("span", { class: "proc-badge human" }, "human"));
      activity.reads.forEach((item) => {
        item.kinds.forEach((kind) =>
          badges.push(el("span", { class: "proc-badge data" }, `reads ${kind}`)));
      });

      const row = el("div", { class: "proc-row" }, [
        el("span", { class: "proc-kind" }, activity.kind),
        el("span", { class: "proc-name" }, activity.label),
        el("span", { class: "proc-badges" }, badges),
        activity.performers.length
          ? el("span", { class: "proc-by" }, activity.performers.join(", "))
          : null,
      ]);

      /* Expand: the AI activity is one box here and a whole architecture when
       * opened. Clicking it highlights the system that carries it and puts the
       * cursor on its source, which is as far as one editor pane can take the
       * idea. */
      if (activity.refines.length) {
        row.classList.add("refined");
        row.addEventListener("click", () => {
          setLevel("architecture", activity);
          GraphView.setHighlight(activity.refines);
          revealInSource(activity.refines);
        });
        row.title = "Open the AI architecture this activity is carried out by";
      }
      list.appendChild(row);
    });
  }


  /* ---- stakeholder overview -------------------------------------------------
   *
   * One page, read-only, meant to be shown rather than edited: the business
   * process as a picture, and what the assessment found in it, attributed to
   * the activity it arises under.
   *
   * The diagram is a clone of the business canvas rather than a second
   * rendering of it. Two renderers of the same thing drift, and the one people
   * put in a slide deck must be the one they were just looking at. */
  let lastProcess = null;
  let lastAssessment = null;

  function overviewDiagram() {
    const source = ProcessCanvas.svgRoot();
    if (!source) return null;
    const copy = source.cloneNode(true);
    copy.removeAttribute("id");
    copy.classList.remove("hidden");
    /* Interaction affordances are noise on a page nobody can interact with. */
    copy.querySelectorAll(".pc-port, .pc-marker").forEach((n) => n.remove());
    const root = copy.querySelector("#pc-root");
    if (root) {
      root.removeAttribute("transform");
      root.removeAttribute("id");
    }
    copy.setAttribute("width", "100%");
    return copy;
  }

  function openOverview() {
    const panel = $("#overview");
    const diagram = $("#overview-diagram");
    const side = $("#overview-side");
    diagram.innerHTML = "";
    side.innerHTML = "";

    const process = lastProcess;
    if (!process || !process.stats.activities) {
      diagram.appendChild(el("p", { class: "drawer-empty" },
        "No business process in this graph yet. Draw one on the Business canvas, or load one from Load example."));
    } else {
      const svg = overviewDiagram();
      if (svg) {
        diagram.appendChild(svg);
        /* The clone carries the live canvas's pan/zoom-less sizing, so give
         * it a viewBox: the page should scale the drawing, not crop it. */
        const drawn = svg.querySelector("g");
        if (drawn && drawn.getBBox) {
          const box = drawn.getBBox();
          svg.setAttribute("viewBox",
            `${box.x - 20} ${box.y - 20} ${box.width + 40} ${box.height + 40}`);
          svg.setAttribute("height", Math.min(box.height + 40, 520));
        }
      }
      $("#overview-title").textContent =
        process.processes.map((p) => p.participant || p.label).join(" · ") || "Business context";

      side.appendChild(el("h3", {}, "Who is involved"));
      process.participants.forEach((actor) =>
        side.appendChild(el("div", { class: "ov-row" }, actor.label)));

      side.appendChild(el("h3", {}, "AI capability"));
      const ai = process.activities.filter((a) => a.refines.length);
      if (!ai.length) {
        side.appendChild(el("div", { class: "ov-row dim" }, "No activity is carried out by an AI system."));
      }
      ai.forEach((activity) => {
        side.appendChild(el("div", { class: "ov-row" }, [
          el("strong", {}, activity.label),
          el("span", { class: "dim" }, ` · ${activity.lane || "no lane"}`),
        ]));
      });
    }

    if (lastAssessment) {
      side.appendChild(el("h3", {}, "What was found, by activity"));
      const rows = lastAssessment.findingsByActivity || [];
      if (!rows.length) {
        side.appendChild(el("div", { class: "ov-row dim" },
          "Run an assessment to attribute findings to the activities they arise under."));
      }
      rows.forEach((row) => {
        side.appendChild(el("div", { class: "ov-row" }, [
          el("span", { class: "ov-count" }, String(row.findings)),
          el("span", {}, row.label),
        ]));
      });
      /* Findings are attributed, not partitioned - a finding whose evidence
       * spans two systems is counted under each - so a total here would be
       * wrong in exactly the case that matters. Say what they are instead. */
      side.appendChild(el("p", { class: "ov-note" },
        `${lastAssessment.summary.riskFindingCount} candidate findings in total. These are candidates for triage, not confirmed failures.`));
      if (lastAssessment.run && lastAssessment.run.knowledgeBase) {
        const kb = lastAssessment.run.knowledgeBase;
        side.appendChild(el("p", { class: "ov-note dim" },
          `Assessed with library ${kb.fingerprint} — ${kb.motifs} motifs, ${kb.riskPatterns} risk patterns.`));
      }
    } else {
      side.appendChild(el("p", { class: "ov-note dim" },
        "Run an assessment to see what was found in this context."));
    }

    panel.classList.remove("hidden");
  }

  //version history

  function shortTime(iso) {
    const at = new Date(iso);
    return Number.isNaN(at.getTime()) ? "" : at.toLocaleString();
  }

  function deltaChip(delta) {
    if (!delta) return el("span", { class: "hist-delta" }, "first run");
    if (!delta.cleared && !delta.raised) return el("span", { class: "hist-delta" }, "no change");
    const parts = [];
    if (delta.cleared) parts.push(`−${delta.cleared}`);
    if (delta.raised) parts.push(`+${delta.raised}`);
    return el(
      "span",
      { class: delta.raised ? "hist-delta raised" : "hist-delta cleared" },
      parts.join(" ")
    );
  }

  function renderHistory() {
    const versions = VersionHistory.list();
    const list = $("#history-list");
    const empty = $("#history-empty");
    list.innerHTML = "";
    $("#history-count").textContent = versions.length ? String(versions.length) : "";
    setTabVisible("history", versions.length > 0);
    empty.classList.toggle("hidden", versions.length > 0);

    versions.forEach((version) => {
      const current = lastRun && lastRun.fingerprint === version.fingerprint;
      const row = el("div", { class: current ? "hist-row current" : "hist-row" }, [
        el("span", { class: "hist-v" }, `v${version.v}`),
        el("span", { class: "hist-at" }, shortTime(version.at)),
        el("span", { class: "hist-counts" },
          `${version.counts.findings ?? "?"} findings · ${version.counts.matches ?? "?"} matches`),
        deltaChip(version.delta),
        el("span", { class: "hist-cause" }, version.cause || ""),
      ]);

      if (version.ttl && !current) {
        const restore = el("button", { class: "btn small", type: "button" }, "Restore");
        restore.addEventListener("click", () => {
          noteChange(`restored v${version.v}`);
          Editor.setValue(version.ttl);
          setStatus("ok", `Restored v${version.v}`,
            `${version.counts.findings ?? "?"} findings when it was assessed`);
        });
        row.appendChild(restore);
      } else if (!version.ttl) {
        row.appendChild(el("span", { class: "hint" }, "graph dropped to save space"));
      }
      list.appendChild(row);
    });
  }

  //  live preview 
  let previewSeq = 0;
  let lastGraph = null; // the parsed architecture, for the level decision and the picker

  async function refreshPreview(ttl) {
    const seq = ++previewSeq;
    if (!ttl.trim()) {
      GraphView.clear();
      $("#system-badge").classList.add("hidden");
      setStatus("ok", "Ready");
      return;
    }
    scheduleStaleCheck(ttl);
    try {
      const data = await postJson("/api/graph", { ttl, scope: scopedSystem });
      if (seq !== previewSeq) return;
      lastGraph = data;
      GraphView.render(data);
      /* After the architecture is known, so the level decision has something to
       * go on rather than always believing the canvas is empty. */
      refreshProcess(ttl);
      sourceLines = new Map(
        [...data.nodes, ...data.systems]
          .filter((n) => n.line)
          .map((n) => [n.id, n.line])
      );
      Editor.markErrorLine(null);
      const badge = $("#system-badge");
      if (data.systems.length) {
        /* When the canvas is narrowed, name the one system on screen. Listing
         * every system the document holds would caption a drawing that shows
         * only one of them. */
        const shown = data.scopedTo
          ? data.systems.filter((s) => s.id === data.scopedTo)
          : data.systems;
        badge.textContent = shown.map((s) => s.label).join(" · ")
          + (data.unclaimed && data.unclaimed.length
              ? ` · ${data.unclaimed.length} element(s) belong to no system`
              : "");
        badge.classList.remove("hidden");
      } else {
        badge.classList.add("hidden");
      }
      setStatus("ok", "Graph parsed", `${data.stats.nodes} nodes · ${data.stats.edges} edges`);
    } catch (error) {
      if (seq !== previewSeq) return;
      const line = parseErrorLine(error.message);
      Editor.markErrorLine(line);
      const firstLine = error.message.split("\n").find((l) => l.trim()) || "Parse error";
      setStatus("error", line ? `Line ${line}: ${firstLine}` : firstLine);
    }
  }

 
  let sourceLines = new Map();

  function revealInSource(ids) {
    const lines = (ids || []).map((id) => sourceLines.get(id)).filter(Boolean);
    if (lines.length) Editor.revealLines(lines);
  }

  //  drawer 
  function openDrawer(tab) {
    $("#drawer").classList.remove("collapsed");
    $("#drawer-toggle").innerHTML = "&#9660;";
    if (tab) switchDrawerTab(tab);
  }

  function toggleDrawer() {
    const drawer = $("#drawer");
    drawer.classList.toggle("collapsed");
    $("#drawer-toggle").innerHTML = drawer.classList.contains("collapsed") ? "&#9650;" : "&#9660;";
  }

  function switchDrawerTab(name) {
    $$(".drawer-tab").forEach((t) => t.classList.toggle("active", t.dataset.drawerTab === name));
    $$(".drawer-panel").forEach((p) => p.classList.toggle("hidden", p.dataset.drawerPanel !== name));
  }

  // findings 
  let selectedFinding = null;

  function controlItem(control, finding) {
    const motifs = control.realizedByMotifs || [];
    const children = [el("span", { class: "ctrl-label" }, control.label)];
    if (control.applicable) {
      children.push(
        el("div", { class: "ctrl-motifs" }, [
          el("button", {
            type: "button",
            class: "chip motif-suggest clickable",
            title: "Insert this control on the path this finding cites, then re-assess",
            onclick: (ev) => { ev.stopPropagation(); applyControl(control, finding); },
          }, "Apply to this finding"),
          motifs.length ? el("span", { class: "ctrl-motifs-lead" }, ` inserts ${motifs[0].label}`) : null,
        ])
      );
    } else if (motifs.length) {
      children.push(
        el("div", { class: "ctrl-motifs" }, [
          el("span", { class: "ctrl-motifs-lead" }, "realized by: "),
          ...motifs.map((m) => el("span", { class: "chip motif-suggest" }, m.label)),
        ])
      );
    }
    return el("li", { title: control.definition || "" }, children);
  }

  // 
  function groundedFamiliesSection(families) {
    if (!families || !families.length) return null;
    return el("div", { class: "ctrl-group evidence" }, [
      el("div", { class: "ctrl-group-head" }, `MIT mitigations (${families.length})`),
      el("ul", { class: "ref-list grounded-list" },
        families.map((f) => el("li", { title: f.definition || "" }, el("span", { class: "chip tax-ground" }, f.label)))),
    ]);
  }

  // All suggested controls under one "Mitigations" list.
  function controlSections(controls, finding) {
    if (!controls.length) return [];
    return [
      el("div", { class: "ctrl-group" }, [
        el("div", { class: "ctrl-group-head" }, `Mitigations (${controls.length})`),
        el("ul", { class: "ref-list" }, controls.map((c) => controlItem(c, finding))),
      ]),
    ];
  }

  const TAXONOMY_CHIP_LIMIT = 4;

  function taxonomyChips(finding) {
    const entries = finding.taxonomyEntries || [];
    const row = el("div", { class: "finding-meta" });
    if (finding.mechanism) {
      row.appendChild(el("span", { class: "chip mech", title: finding.mechanism.id }, finding.mechanism.label));
    }
    const chipFor = (t) => el("span", { class: "chip tax", title: t.definition || t.id }, t.label);
    entries.slice(0, TAXONOMY_CHIP_LIMIT).forEach((t) => row.appendChild(chipFor(t)));

    const hidden = entries.slice(TAXONOMY_CHIP_LIMIT);
    if (!hidden.length) return row;

    const more = el("button",
      { type: "button", class: "chip tax chip-more", title: "Show the remaining taxonomy entries" },
      `+${hidden.length}`);
    more.addEventListener("click", (ev) => {
      ev.stopPropagation(); // the card itself selects the finding
      hidden.forEach((t) => row.insertBefore(chipFor(t), more));
      more.remove();
    });
    row.appendChild(more);
    return row;
  }

  function findingCard(finding) {
    const evidenceIds = finding.evidence.map((e) => e.id);
    const card = el("div", { class: "finding-card", tabindex: "0" }, [
      el("div", { class: "finding-head" }, [
        el("strong", {}, finding.label),
        finding.motif ? el("span", { class: "chip" }, finding.motif.label) : null,
      ]),
      finding.description ? el("p", { class: "finding-desc" }, finding.description) : null,
      taxonomyChips(finding),
      el("details", {}, [
        el("summary", {}, `Suggested controls (${finding.suggestedControls.length}) · evidence (${finding.evidence.length})`),
        ...controlSections(finding.suggestedControls, finding),
        groundedFamiliesSection(finding.groundedControlFamilies),
        el("div", { class: "evidence-note" }, "Evidence: " + finding.evidence.map((e) => e.label).join(", ")),
      ]),
    ]);
    card.addEventListener("click", () => {
      if (selectedFinding === card) {
        selectedFinding = null;
        card.classList.remove("selected");
        GraphView.setHighlight([]);
        return;
      }
      $$(".finding-card.selected").forEach((c) => c.classList.remove("selected"));
      selectedFinding = card;
      card.classList.add("selected");
      GraphView.setHighlight(evidenceIds);
      revealInSource(evidenceIds);
    });
    return card;
  }

  function renderFindings(data) {
    $("#findings-empty").classList.add("hidden");
    const summary = $("#findings-summary");
    summary.innerHTML = "";

    const delta = runDelta(data.findings);
    const row = [
      el("span", { class: "stat" }, `${data.summary.riskFindingCount} candidate findings`),
      el("span", { class: "stat" }, `${data.summary.motifMatchCount} motif matches`),
    ];
    if (delta && (delta.cleared || delta.raised)) {
      if (delta.cleared) {
        row.push(el("span", { class: "stat delta" },
          `${delta.cleared} cleared since the last run`));
      }
      if (delta.raised) {
        row.push(el("span", { class: "stat delta raised" },
          `${delta.raised} newly raised`));
      }
    } else if (delta) {
      row.push(el("span", { class: "stat" }, "unchanged since the last run"));
    }
    row.push(el("span", { class: "hint" }, "Click a finding to highlight its evidence in the graph."));
    summary.appendChild(el("div", { class: "summary-row" }, row));

    if (data.run && data.run.inputFingerprint) {
      lastRun = {
        fingerprint: data.run.inputFingerprint,
        findingIds: new Set(data.findings.map((f) => f.id)),
      };
      setStale(false);
      VersionHistory.record({
        fingerprint: data.run.inputFingerprint,
        knowledgeBase: data.run.knowledgeBase,
        counts: {
          findings: data.summary.riskFindingCount,
          matches: data.summary.motifMatchCount,
          derived: data.summary.derivedCategoryCount,
        },
        findingIds: data.findings.map((f) => f.id),
        ttl: Editor.getValue(),
        cause: pendingCause,
      });
      pendingCause = null;
      renderHistory();

    }
    lastAssessment = data;
    /* The business canvas learns what was found where, so an activity box can
     * say how many candidate risks it carries and unfold them on request. */
    ProcessCanvas.setFindings(data.findingsByActivity);
    renderKnowledgeBaseBadge(data.run);

    const list = $("#findings-list");
    list.innerHTML = "";
    selectedFinding = null;
    GraphView.setHighlight([]);
    if (!data.findings.length) {
      list.appendChild(el("p", { class: "drawer-empty" }, "No candidate risk findings were produced for this architecture."));
    }
    data.findings.forEach((f) => list.appendChild(findingCard(f)));
    $("#findings-count").textContent = data.findings.length ? String(data.findings.length) : "";
  }

  // matched motifs tab 
  let selectedMotifRow = null;


  function gapCard(gap) {
    const items = [];
    gap.missingNodes.forEach((n) => {
      const hint = n.candidates.length
        ? ` — try: ${n.candidates.map((c) => c.label).join(", ")}`
        : "";
      items.push(el("li", { class: "gap-need-role" }, [
        el("span", {}, "no element plays "),
        el("strong", {}, n.role),
        el("span", { class: "gap-hint" }, hint),
      ]));
    });
    gap.missingEdges.forEach((e) => items.push(el("li", { class: "gap-need-edge" }, e.text)));

    const card = el("div", { class: "gap-row" }, [
      el("div", { class: "gap-head" }, [
        el("span", { class: "motif-row-name" }, gap.label.replace(/\s+Motif$/, "")),
        el("span", { class: "gap-score", title: "pattern nodes and edges satisfied" },
          `${gap.satisfied}/${gap.total}`),
      ]),
      el("ul", { class: "gap-list" }, items),
    ]);
    const candidateIds = gap.missingNodes.flatMap((n) => n.candidates.map((c) => c.id));
    if (candidateIds.length) {
      card.classList.add("clickable");
      card.title = "Click to highlight the elements that could take these roles";
      card.addEventListener("click", () => GraphView.setHighlight(candidateIds));
    }
    return card;
  }

  function renderMotifGaps(gaps) {
    const list = $("#motifs-list");
    // only the near misses are actionable; a motif sharing nothing with the
    // graph would just be noise
    const near = (gaps || []).filter((g) => g.satisfied / g.total >= 0.5).slice(0, 5);
    if (!near.length) return;
    list.appendChild(el("div", { class: "gap-section-head" },
      "Almost matched — what's missing"));
    near.forEach((g) => list.appendChild(gapCard(g)));
  }

  function renderDerivedCategories(rows) {
    const list = $("#derived-list");
    const empty = $("#derived-empty");
    const count = $("#derived-count");
    list.innerHTML = "";
    if (!rows || !rows.length) {
      empty.textContent = "No category travelled: every data category in this graph sits where you annotated it.";
      empty.classList.remove("hidden");
      count.textContent = "";
      return;
    }
    empty.classList.add("hidden");
    
    count.textContent = String(
      new Set(rows.map((r) => `${r.element.id}|${r.category.id}`)).size
    );
    list.appendChild(el("div", { class: "derived-section-head" }, [
      el("span", {}, "Categories the engine inferred — traced back to the annotation each came from"),
      el("span", { class: "derived-section-hint" },
        "Categories you annotated yourself are not listed. Click a row to highlight its route on the diagram."),
    ]));

    const hopsBy = new Map();
    rows.forEach((r) => {
      const key = `${r.element.id}|${r.category.id}`;
      if (!hopsBy.has(key)) hopsBy.set(key, []);
      hopsBy.get(key).push(r);
    });

    const traceFor = (row) => {
      const queue = [[row]];
      const visited = new Set([row.element.id]);
      let deepest = [row];
      while (queue.length) {
        const path = queue.shift();
        const last = path[path.length - 1];
        if (path.length > deepest.length) deepest = path;
        if (!last.from) return { path, origin: null, circular: false };
        if (last.fromAnnotated) return { path, origin: last.from, circular: false };
        if (visited.has(last.from.id)) continue;
        visited.add(last.from.id);
        for (const next of hopsBy.get(`${last.from.id}|${row.category.id}`) || []) {
          queue.push([...path, next]);
        }
      }
      return { path: deepest, origin: null, circular: true };
    };

  
    const byElement = new Map();
    rows.forEach((r) => {
      const key = r.element.id;
      if (!byElement.has(key)) byElement.set(key, { element: r.element, categories: new Map() });
      byElement.get(key).categories.set(r.category.id, r);
    });

    [...byElement.values()]
      .sort((a, b) => a.element.label.localeCompare(b.element.label))
      .forEach((group) => {
        const block = el("div", { class: "derived-group" });
        block.appendChild(el("div", { class: "derived-element" }, group.element.label));
        [...group.categories.values()]
          .sort((a, b) => a.category.label.localeCompare(b.category.label))
          .forEach((row) => {
            const { path: chain, origin, circular } = traceFor(row);
            // Read the trail forwards, the direction the data actually moved.
            const steps = chain.map((hop) => hop.via && hop.via.label).filter(Boolean).reverse();
            const alternatives =
              (hopsBy.get(`${row.element.id}|${row.category.id}`) || []).length - 1;

            let why;
            if (circular) {
              why = `circulates through ${chain[chain.length - 1].from.label}` +
                (steps.length ? ` · via ${steps.join(" → ")}` : "");
            } else {
              why = `annotated on ${origin ? origin.label : "an upstream element"}` +
                (steps.length ? ` · via ${steps.join(" → ")}` : "");
            }
            if (alternatives > 0) why += ` · +${alternatives} other source${alternatives > 1 ? "s" : ""}`;

            const line = el("div", { class: "derived-row", title: "Click to highlight this path in the diagram" }, [
              el("span", { class: "derived-cat" }, row.category.label),
              el("span", { class: "derived-why" }, why),
            ]);
            const path = [row.element.id, ...chain.map((h) => h.from && h.from.id), ...chain.map((h) => h.via && h.via.id)]
              .filter(Boolean);
            line.addEventListener("click", () => {
              $$("#derived-list .derived-row").forEach((n) => n.classList.remove("active"));
              line.classList.add("active");
              GraphView.setHighlight(path);
            });
            block.appendChild(line);
          });
        list.appendChild(block);
      });
  }

  function renderMotifs(matches, gaps) {
    const byName = new Map();
    (matches || []).forEach((m) => {
      const label = (m.label || (m.motif && m.motif.label) || "Motif").replace(/\s+Motif$/, "");
      const g = byName.get(label) || { label, ids: new Set(), count: 0 };
      (m.nodeIds || []).forEach((id) => g.ids.add(id));
      g.count += 1;
      byName.set(label, g);
    });
    const rows = [...byName.values()]
      .map((g) => ({ label: g.label, nodeIds: [...g.ids], count: g.count }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));

    const list = $("#motifs-list");
    const empty = $("#motifs-empty");
    list.innerHTML = "";
    selectedMotifRow = null;
    if (!rows.length) {
      empty.textContent = "No motifs matched. Add roles so motifs can bind, then Run assessment.";
      empty.classList.remove("hidden");
      $("#motifs-count").textContent = "";
      renderMotifGaps(gaps); 
      return;
    }
    empty.classList.add("hidden");
    rows.forEach((r) => {
      const row = el("div", {
        class: "motif-row", tabindex: "0",
        title: `Matched ${r.count} time${r.count > 1 ? "s" : ""} · click to highlight ${r.nodeIds.length} elements`,
      }, [
        el("span", { class: "motif-row-name" }, r.label),
        el("span", { class: "motif-row-count" }, r.count > 1 ? `×${r.count}` : "1"),
      ]);
      row.addEventListener("click", () => {
        const wasSelected = selectedMotifRow === row;
        $$(".motif-row.selected").forEach((x) => x.classList.remove("selected"));
        if (wasSelected) { selectedMotifRow = null; GraphView.setHighlight([]); return; }
        selectedMotifRow = row;
        row.classList.add("selected");
        GraphView.setHighlight(r.nodeIds);
        revealInSource(r.nodeIds);
      });
      list.appendChild(row);
    });
    renderMotifGaps(gaps);
    $("#motifs-count").textContent = String(rows.length);
  }

  // validation 
  function validationRow(item, severity) {
    const row = el("div", { class: `validation-row ${severity}` }, [
      el("span", { class: "sev" }, severity === "violation" ? "Violation" : "Warning"),
      el("span", { class: "msg" }, item.message),
    ]);
    if (item.focusNode) {
      row.appendChild(el("code", { class: "focus", title: item.focusNode }, item.focusNode.split(/[#/]/).pop()));
      row.addEventListener("click", () => GraphView.setHighlight([item.focusNode]));
    }
    return row;
  }

  function renderValidation(report) {
    $("#validation-empty").classList.add("hidden");
    const list = $("#validation-list");
    list.innerHTML = "";
    const total = report.violations.length + report.warnings.length;
    list.appendChild(el("div", { class: "summary-row" }, [
      el("span", { class: `stat ${report.conforms ? "good" : "bad"}` },
        report.conforms ? "Input contract satisfied" : "Input contract violated"),
      el("span", { class: "stat" }, `${report.violations.length} violations · ${report.warnings.length} warnings`),
      total ? el("span", { class: "hint" }, "Click a row to highlight the focus node.") : null,
    ]));
    report.violations.forEach((v) => list.appendChild(validationRow(v, "violation")));
    report.warnings.forEach((w) => list.appendChild(validationRow(w, "warning")));
    $("#validation-count").textContent = total ? String(total) : "";
  }

  //split divider
  function initDivider() {
    const divider = $("#divider");
    const editorPane = $("#editor-pane");
    let dragging = false;
    divider.addEventListener("pointerdown", (ev) => {
      dragging = true;
      divider.setPointerCapture(ev.pointerId);
      document.body.classList.add("resizing");
    });
    divider.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      const main = $(".workbench");
      const rect = main.getBoundingClientRect();
      const ratio = Math.min(0.75, Math.max(0.2, (ev.clientX - rect.left) / rect.width));
      editorPane.style.flex = `0 0 ${ratio * 100}%`;
      GraphView.fit();
    });
    divider.addEventListener("pointerup", () => {
      dragging = false;
      document.body.classList.remove("resizing");
    });
  }

  // starter graph 
  const STARTER_TTL = `@prefix ex:   <http://example.org/my-system#> .
@prefix beam: <http://w3id.org/beam/core#> .
@prefix pair: <http://w3id.org/airiskkg/pair-ai#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:System a beam:System ;
    rdfs:label "My RAG system" ;
    beam:hasResource ex:Question, ex:VectorDB, ex:Context, ex:LLM, ex:Answer ;
    beam:hasProcess ex:Retrieve, ex:Generate .

ex:Question a beam:Data ;
    rdfs:label "User question" ;
    pair:playsRole pair:PublicUserInput ;
    pair:containsDataCategory pair:ExternalUserContent .

ex:VectorDB a beam:Data ;
    rdfs:label "Knowledge vector store" ;
    pair:playsRole pair:VectorStore ;
    pair:containsDataCategory pair:SensitiveInformation .

ex:Context a beam:Data ;
    rdfs:label "Retrieved context" ;
    pair:playsRole pair:RetrievedResult ;
    pair:containsDataCategory pair:UntrustedContent .

ex:LLM a beam:StatisticalModel ;
    rdfs:label "Generative model" ;
    pair:playsRole pair:GenerativeModel .

ex:Answer a beam:Data ;
    rdfs:label "User-facing answer" ;
    pair:playsRole pair:PublicUserFacingOutput .

ex:Retrieve a beam:Infer ;
    rdfs:label "Vector retrieval" ;
    pair:playsRole pair:RetrievalStep ;
    beam:use ex:Question, ex:VectorDB ;
    beam:produce ex:Context ;
    beam:inform ex:Generate .

ex:Generate a beam:Transform ;
    rdfs:label "LLM generation" ;
    pair:playsRole pair:GenerationStep ;
    beam:use ex:Question, ex:Context, ex:LLM ;
    beam:produce ex:Answer .
`;

  let mutating = Promise.resolve();
  function runMutation(task) {
    const next = mutating.then(task, task);
    mutating = next.catch(() => {});
    return next;
  }

  // Edit an element from the popup.
  function applyEdit(elementId, edit) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "edit-element", element: elementId, ...edit,
        });
        noteChange("edited an element");
        Editor.setValue(ttl);
        setStatus("ok", "Element updated — Run assessment to see findings");
      } catch (error) {
        setStatus("error", "Could not update element: " + error.message.split("\n")[0]);
      }
    });
  }

  // Delete an element and every edge touching it.
  function applyDelete(elementId) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "delete-element", element: elementId,
        });
        noteChange("deleted an element");
        Editor.setValue(ttl);
        setStatus("ok", "Element deleted");
      } catch (error) {
        setStatus("error", "Could not delete: " + error.message.split("\n")[0]);
      }
    });
  }

  // Add a BEAM flow edge from a canvas port-drag.
  function applyConnect(triple) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "add-edge", ...triple,
        });
        noteChange(`connected: ${triple.predicate}`);
        Editor.setValue(ttl);
        setStatus("ok", `Connected: ${triple.predicate}`);
      } catch (error) {
        setStatus("error", "Could not connect: " + error.message.split("\n")[0]);
      }
    });
  }

  // Palette of BEAM symbols; click one to add it, or drag it onto the canvas.
  const BEAM_NS = "http://w3id.org/beam/core#";
  const PALETTE = [
    { label: "Data", cls: "Data", kind: "data", cat: "resource" },
    { label: "Symbol", cls: "Symbol", kind: "symbol", cat: "resource" },
    { label: "Model", cls: "StatisticalModel", kind: "model", cat: "resource" },
    { label: "Transform", cls: "Transform", kind: "process", cat: "process" },
    { label: "Infer", cls: "Infer", kind: "process", cat: "process" },
    { label: "Train", cls: "Train", kind: "process", cat: "process" },
    { label: "Generate", cls: "Generate", kind: "process", cat: "process" },
  ];

  function addPaletteElement(item, clientX, clientY) {
    return runMutation(async () => {
      try {
        const { ttl, newId } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> .\n",
          op: "add-element", classUri: BEAM_NS + item.cls, category: item.cat, label: item.label,
        });
        if (newId && clientX != null) GraphView.placeNodeAt(newId, clientX, clientY);
        noteChange(`added ${item.label}`);
        Editor.setValue(ttl);
        setStatus("ok", `Added ${item.label} — click it to edit, drag its ▸ port to connect`);
      } catch (error) {
        setStatus("error", "Could not add element: " + error.message.split("\n")[0]);
      }
    });
  }

  // Build a collapsible tray
  function buildTray(container, title, body, startCollapsed) {
    const toggle = el("span", { class: "tray-toggle" }, startCollapsed ? "▸" : "▾");
    const head = el("div", { class: "tray-head", title: "Show / hide" }, [el("span", {}, title), toggle]);
    head.addEventListener("click", () => {
      const collapsed = container.classList.toggle("collapsed");
      toggle.textContent = collapsed ? "▸" : "▾";
    });
    if (startCollapsed) container.classList.add("collapsed");
    container.textContent = "";
    container.appendChild(head);
    container.appendChild(body);
  }

  function initPalette() {
    const palette = $("#palette");
    if (!palette) return;
    const wrap = $("#canvas-wrap");
    const body = el("div", { class: "tray-body" });
    PALETTE.forEach((item) => {
      const chip = el("div",
        { class: `palette-item ${item.kind}`, title: `Click to add, or drag onto the canvas — ${item.cls}` },
        item.label);
      chip.addEventListener("pointerdown", (ev) => startTrayDrag(ev, chip, wrap, (x, y) => addPaletteElement(item, x, y)));
      body.appendChild(chip);
    });
    buildTray(palette, "Symbols", body);
  }

  // Click a tray item to add it (at center)
  function startTrayDrag(ev, chip, wrap, onDrop) {
    ev.preventDefault();
    ev.stopPropagation();
    const startX = ev.clientX;
    const startY = ev.clientY;
    const ghost = chip.cloneNode(true);
    ghost.classList.add("palette-ghost");
    ghost.style.left = startX + 10 + "px";
    ghost.style.top = startY + 10 + "px";
    let moved = false;
    const move = (mv) => {
      if (!moved) {
        if (Math.hypot(mv.clientX - startX, mv.clientY - startY) < 6) return;
        moved = true;
        document.body.appendChild(ghost); // only show the ghost once actually dragging
      }
      ghost.style.left = mv.clientX + 10 + "px";
      ghost.style.top = mv.clientY + 10 + "px";
    };
    const up = (uv) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      ghost.remove();
      if (!moved) { onDrop(null, null); return; } // click -> add at center
      const r = wrap.getBoundingClientRect();
      const inside = uv.clientX >= r.left && uv.clientX <= r.right && uv.clientY >= r.top && uv.clientY <= r.bottom;
      const onTray = uv.target && uv.target.closest && (uv.target.closest(".palette") || uv.target.closest(".motif-palette"));
      onDrop(inside && !onTray ? uv.clientX : null, inside && !onTray ? uv.clientY : null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // motif catalogue 

  function applyControl(control, finding) {
    return runMutation(async () => {
      try {
        const { ttl, addedTriples, newIds } = await postJson("/api/apply-control", {
          ttl: Editor.getValue(), control: control.id, finding: finding.id,
        });
        if (!addedTriples) {
          setStatus("ok", `"${control.label}" is already in place on this path.`);
          return;
        }
        noteChange(`applied ${control.label}`);
        Editor.setValue(ttl);
        GraphView.setHighlight(newIds || []);
        setStatus("busy", `Applied "${control.label}" - re-assessing...`);
        const data = await postJson("/api/assess", { ttl });
        renderFindings(data);
        renderMotifs(data.motifMatches, data.motifGaps);
        renderDerivedCategories(data.derivedCategories);
        setStatus("ok", `Applied "${control.label}"`,
          `${data.summary.riskFindingCount} findings · ${data.summary.motifMatchCount} matches`);
      } catch (error) {
        setStatus("error", "Could not apply the control: " + error.message.split("\n")[0]);
      }
    });
  }

  function addMotif(item) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> .\n",
          op: "add-motif", motif: item.id,
        });
        noteChange(`added motif: ${item.label}`);
        Editor.setValue(ttl);
        setStatus("ok", `Added "${item.label}" — already annotated; Run assessment for findings`);
      } catch (error) {
        setStatus("error", "Could not add motif: " + error.message.split("\n")[0]);
      }
    });
  }

  function initMotifPalette(templates) {
    const panel = $("#motif-palette");
    if (!panel) return;
    if (!templates || !templates.length) { panel.style.display = "none"; return; }
    const wrap = $("#canvas-wrap");
    const body = el("div", { class: "tray-body" });
    templates.forEach((item) => {
      const chip = el("div", { class: "motif-item", title: `Add ${item.label} — click or drag onto the canvas` }, item.label);
      chip.addEventListener("pointerdown", (ev) => startTrayDrag(ev, chip, wrap, () => addMotif(item)));
      body.appendChild(chip);
    });
    buildTray(panel, "Motifs", body, true); 
  }

  //  init 
  async function init() {
    GraphView.init();
    Editor.init({ onChange: refreshPreview });
    initDivider();

    let vocabulary = { roles: [], dataCategories: [] };
    try {
      vocabulary = await api("/api/vocabulary");
    } catch (_) { /* annotation popups will just have empty pick lists */ }
    const classes = [...(vocabulary.resourceClasses || []), ...(vocabulary.processClasses || [])];
    GraphView.setAnnotation({
      vocabulary, classes,
      onEdit: applyEdit, onDelete: applyDelete, onConnect: applyConnect, onStatus: setStatus,
      onSelect: (id) => revealInSource([id]),
    });
    Annotate.init({ vocabulary, onStatus: setStatus });

    initPalette();
    initMotifPalette(vocabulary.motifTemplates || []);
    renderHistory();

    ProcessCanvas.init({
      svg: "#process-canvas",
      /* Every edit is a server-side rewrite of the graph, exactly like the
       * architecture canvas: the Turtle in the editor stays the single source
       * of truth, and nothing about the process lives only in the browser. */
      onEdit: (op, payload) => runMutation(async () => {
        try {
          const { ttl } = await postJson("/api/process-edit", {
            ttl: Editor.getValue(), op, ...payload,
          });
          noteChange(`business process: ${op.replace(/-/g, " ")}`);
          Editor.setValue(ttl);
          setStatus("ok", `Business process updated (${op})`);
        } catch (error) {
          setStatus("error", "Could not edit the process: " + error.message.split(String.fromCharCode(10))[0]);
        }
      }),
      /* Descending is the whole point of the two levels: one box up here, a
       * whole architecture down there. Highlight what was opened so the reader
       * lands on it rather than on the graph in general. */
      onOpenArchitecture: (activity) => {
        /* Descending means "show me the architecture behind THIS activity", not
         * "switch to the other tab". The relation is already in the graph -
         * pair:refinedBy names the system, beam:hasProcess/hasResource say what
         * it holds - so narrowing is a query, and nothing has to be stored. */
        scopedSystem = activity.refines[0] || null;
        setLevel("architecture", activity);
        refreshPreview(Editor.getValue());
        /* Not setHighlight(activity.refines): those are system IRIs, and a
         * system is not a node on the canvas - the call highlighted nothing and
         * only looked like it did something. Descending shows the whole
         * architecture, which is the point; clear any evidence highlight left
         * over from a finding so what is on screen is the system, not the last
         * thing someone clicked. */
        GraphView.setHighlight([]);
        revealInSource(activity.refines);
        setStatus("ok", `Opened ${activity.label}`, "click the breadcrumb to go back");
      },
    });
    $("#btn-overview").addEventListener("click", openOverview);
    $("#btn-overview-close").addEventListener("click", () => $("#overview").classList.add("hidden"));
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") $("#overview").classList.add("hidden");
    });
    $("#btn-overview-svg").addEventListener("click", () => {
      const svg = $("#overview-diagram").querySelector("svg");
      if (!svg) { setStatus("error", "No diagram to export."); return; }
      const markup = new XMLSerializer().serializeToString(svg);
      downloadBlob(new Blob([markup], { type: "image/svg+xml" }), `${exportBaseName()}-context.svg`);
      setStatus("ok", "Diagram exported");
    });
    $("#level-business").addEventListener("click", () => {
      levelChosenByHand = true;
      setLevel("business");
    });
    $("#level-architecture").addEventListener("click", () => {
      levelChosenByHand = true;
      /* Picking the level by hand asks for the architecture layer, not the one
       * activity someone descended through earlier. */
      const widening = scopedSystem !== null;
      scopedSystem = null;
      openedFrom = null;
      setLevel("architecture");
      if (widening) refreshPreview(Editor.getValue());
    });

    /* Put the canvases and palettes into a known state once, rather than
     * leaving them on whatever the markup happened to say until the first
     * click. That gap is what made a freshly loaded process show nothing. */
    setLevel(level);

    $("#btn-history-clear").addEventListener("click", () => {
      if (!VersionHistory.list().length) return;
      if (!window.confirm("Delete every recorded version from this browser? This cannot be undone.")) return;
      VersionHistory.clear();
      renderHistory();
      setStatus("ok", "History cleared");
    });

    $("#btn-history-export").addEventListener("click", () => {
      const versions = VersionHistory.list();
      if (!versions.length) { setStatus("error", "No history to export."); return; }
      downloadBlob(
        new Blob([JSON.stringify(versions, null, 2)], { type: "application/json" }),
        `${exportBaseName()}-history.json`
      );
      setStatus("ok", `Exported ${versions.length} versions`);
    });

    try {
      const examples = await api("/api/examples");
      const select = $("#example-select");
      const groups = [
        ["Bundled", examples.filter((ex) => !ex.local)],
        ["Local (not in the repository)", examples.filter((ex) => ex.local)],
      ];
      for (const [label, items] of groups) {
        if (!items.length) continue;
        const group = el("optgroup", { label });
        items.forEach((ex) => group.appendChild(el("option", { value: ex.name }, ex.name)));
        select.appendChild(group);
      }
    } catch (_) { /* non-fatal */ }

    $("#example-select").addEventListener("change", async (ev) => {
      const name = ev.target.value;
      if (!name) return;
      try {
        const example = await api(`/api/examples/${encodeURIComponent(name)}`);
        if (example.kind === "process") {
          /* A process names the systems its activities are carried out by and
           * does not contain them. Loaded on its own it draws a diagram
           * pointing at architectures that are not there: no nodes, no motifs,
           * no findings, and nothing on screen saying why.
           *
           * So bring what it needs - but only what is not already loaded, so
           * adding context to a graph someone is working on stays an addition
           * rather than a reset. */
          const present = new Set((lastGraph && lastGraph.systems ? lastGraph.systems : []).map((s) => s.id));
          const wanted = (example.requires || []).filter((r) => r.example && !present.has(r.system));
          const parts = [];
          for (const requirement of wanted) {
            const architecture = await api(`/api/examples/${encodeURIComponent(requirement.example)}`);
            parts.push(architecture.ttl);
          }

          const current = Editor.getValue().trimEnd();
          if (current) parts.unshift(current);
          parts.push(example.ttl);

          noteChange(wanted.length
            ? `loaded scene: ${name}`
            : `added business process: ${name}`);
          Editor.setValue(parts.join(String.fromCharCode(10, 10)));
          openDrawer("process");

          const orphans = example.missing || [];
          if (orphans.length) {
            setStatus("error",
              `${orphans.length} activity target(s) have no bundled architecture`,
              "the process will draw, but there is nothing to assess for them");
          } else {
            setStatus("ok", `Loaded ${name}`,
              wanted.length ? `with ${wanted.length} architecture(s) it refines` : "added to the current graph");
          }
        } else {
          noteChange(`loaded example: ${name}`);
          Editor.setValue(example.ttl);
          setStatus("ok", `Loaded example: ${name}`);
        }
      } catch (error) {
        setStatus("error", error.message);
      }
    });

    // Open a graph file.
    $("#file-input").addEventListener("change", (ev) => {
      const file = ev.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async () => {
        const text = String(reader.result);
        if (!text.includes("tool4boxology.org")) {
          noteChange(`opened file: ${file.name}`);
          Editor.setValue(text);
          setStatus("ok", `Loaded file: ${file.name}`);
          return;
        }
        setStatus("busy", `Normalizing Tool4Boxology export: ${file.name}…`);
        try {
          const fmt = /\.nt$/i.test(file.name) ? "nt" : "turtle";
          const { ttl, warnings } = await postJson("/api/import/t4b", { data: text, format: fmt });
          noteChange(`imported Tool4Boxology export: ${file.name}`);
          Editor.setValue(ttl);
          setStatus("ok", `Imported ${file.name} — ${(warnings || []).length} normalization note(s). ` +
            "The export carries no roles: use the Annotate tab so motifs can match.");
        } catch (error) {
          setStatus("error", "Could not import Tool4Boxology export: " + error.message.split("\n")[0]);
        }
      };
      reader.readAsText(file);
      ev.target.value = "";
    });

    $("#btn-starter").addEventListener("click", () => {
      noteChange("starter graph");
      Editor.setValue(STARTER_TTL);
      setStatus("ok", "Starter graph loaded");
    });

    $("#btn-clear").addEventListener("click", () => {
      if (!Editor.getValue().trim()) return;
      if (!window.confirm("Clear the code and the diagram? This cannot be undone.")) return;
      Editor.setValue(""); // empty -> refreshPreview clears the canvas
      setStatus("ok", "Cleared");
    });

    $("#btn-validate").addEventListener("click", async () => {
      const ttl = Editor.getValue().trim();
      if (!ttl) { setStatus("error", "Nothing to validate - the editor is empty."); return; }
      const button = $("#btn-validate");
      button.disabled = true;
      setStatus("busy", "Validating against the input contract…");
      try {
        const report = await postJson("/api/validate", { ttl });
        renderValidation(report);
        openDrawer("validation");
        setStatus(report.conforms ? "ok" : "error",
          report.conforms ? "Input contract satisfied" : `${report.violations.length} contract violation(s)`);
      } catch (error) {
        setStatus("error", error.message);
      } finally {
        button.disabled = false;
      }
    });

    $("#btn-assess").addEventListener("click", async () => {
      const ttl = Editor.getValue().trim();
      if (!ttl) { setStatus("error", "Nothing to assess - the editor is empty."); return; }
      const button = $("#btn-assess");
      button.disabled = true;
      setStatus("busy", "Running candidate risk assessment…");
      try {
        const data = await postJson("/api/assess", { ttl });
        renderFindings(data);
        renderMotifs(data.motifMatches, data.motifGaps); // Motifs tab (each match carries nodeIds)
        renderDerivedCategories(data.derivedCategories);
        openDrawer("findings");
        setStatus("ok", `Assessment finished`, `${data.summary.riskFindingCount} findings · ${data.summary.motifMatchCount} matches`);
      } catch (error) {
        setStatus("error", error.message);
      } finally {
        button.disabled = false;
      }
    });

    $("#btn-export-svg").addEventListener("click", () => {
      const ok = GraphView.exportSvg(`${exportBaseName()}.svg`);
      if (ok) setStatus("ok", "Diagram exported as SVG.");
      else setStatus("error", "Nothing to export - the diagram is empty.");
    });

    $("#btn-export-kg").addEventListener("click", async () => {
      const ttl = Editor.getValue().trim();
      if (!ttl) { setStatus("error", "Nothing to export - the editor is empty."); return; }
      const button = $("#btn-export-kg");
      const format = $("#export-format").value;
      button.disabled = true;
      setStatus("busy", "Building the assessment knowledge graph…");
      try {
        const { blob, findings, matches, filename } = await postForFile(
          "/api/export/assessment",
          { ttl, format, sourceLabel: exportBaseName() },
        );
        downloadBlob(blob, filename || `${exportBaseName()}-assessment`);
        setStatus("ok", "Assessment exported", `${findings} findings · ${matches} matches`);
      } catch (error) {
        setStatus("error", error.message);
      } finally {
        button.disabled = false;
      }
    });

    $("#drawer-toggle").addEventListener("click", toggleDrawer);
    $("#drawer-head").addEventListener("dblclick", toggleDrawer);
    $$(".drawer-tab").forEach((tab) =>
      tab.addEventListener("click", () => {
        switchDrawerTab(tab.dataset.drawerTab);
        openDrawer();
        if (tab.dataset.drawerTab === "annotate") Annotate.refresh();
      }));
  }

  document.addEventListener("DOMContentLoaded", init);
})();
