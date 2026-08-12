"use strict";

/* Workbench wiring: editor <-> live preview <-> assessment.
 * Requires editor.js (window.Editor) and graph.js (window.GraphView).
 */
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

  /* Download endpoints answer with a file on success and JSON on failure, so
   * they cannot go through api() - it parses every response as JSON and would
   * turn a perfectly good Turtle download into a parse error. */
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

  /** Name exports after the loaded example, so several downloads stay apart. */
  function exportBaseName() {
    const selected = $("#example-select");
    const name = selected && selected.value ? selected.value : "";
    return (name || "architecture").replace(/\.(ttl|turtle|nt)$/i, "");
  }

  // ---- status bar ------------------------------------------------------------
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

  // ---- live preview ----------------------------------------------------------
  let previewSeq = 0;

  async function refreshPreview(ttl) {
    const seq = ++previewSeq;
    if (!ttl.trim()) {
      GraphView.clear();
      $("#system-badge").classList.add("hidden");
      setStatus("ok", "Ready");
      return;
    }
    try {
      const data = await postJson("/api/graph", { ttl });
      if (seq !== previewSeq) return; // a newer edit is already in flight
      GraphView.render(data);
      Editor.markErrorLine(null);
      const badge = $("#system-badge");
      if (data.systems.length) {
        badge.textContent = data.systems.map((s) => s.label).join(" · ");
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
      // keep the last good graph on screen while the user is mid-edit
    }
  }

  // ---- drawer ----------------------------------------------------------------
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

  // ---- findings --------------------------------------------------------------
  let selectedFinding = null;

  // One mitigation as a list item, with any suggested motif beneath it.
  function controlItem(control) {
    const motifs = control.realizedByMotifs || [];
    const children = [el("span", { class: "ctrl-label" }, control.label)];
    if (motifs.length) {
      children.push(
        el("div", { class: "ctrl-motifs" }, [
          el("span", { class: "ctrl-motifs-lead" }, "suggested mitigation: "),
          ...motifs.map((m) =>
            el("span", {
              class: "chip motif-suggest clickable",
              title: "Click to add this motif to the canvas",
              onclick: (ev) => { ev.stopPropagation(); addSuggestedMotif(m); },
            }, m.label)
          ),
        ])
      );
    }
    return el("li", { title: control.definition || "" }, children);
  }

  // MIT taxonomy-grounded mitigations for this finding's risks.
  function groundedFamiliesSection(families) {
    if (!families || !families.length) return null;
    return el("div", { class: "ctrl-group evidence" }, [
      el("div", { class: "ctrl-group-head" }, `MIT mitigations (${families.length})`),
      el("ul", { class: "ref-list grounded-list" },
        families.map((f) => el("li", { title: f.definition || "" }, el("span", { class: "chip tax-ground" }, f.label)))),
    ]);
  }

  // All suggested controls under one "Mitigations" list.
  function controlSections(controls) {
    if (!controls.length) return [];
    return [
      el("div", { class: "ctrl-group" }, [
        el("div", { class: "ctrl-group-head" }, `Mitigations (${controls.length})`),
        el("ul", { class: "ref-list" }, controls.map(controlItem)),
      ]),
    ];
  }

  /* Taxonomy chips, with the overflow actually reachable.
   *
   * The row used to cut off at four and render a dead "+3" that named nothing
   * and could not be opened, so the anchors a finding carries - which are the
   * whole point of anchoring to external taxonomies - were unreadable. The
   * counter is now a button that reveals the rest in place. */
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
        ...controlSections(finding.suggestedControls),
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
    });
    return card;
  }

  function renderFindings(data) {
    $("#findings-empty").classList.add("hidden");
    const summary = $("#findings-summary");
    summary.innerHTML = "";
    summary.appendChild(el("div", { class: "summary-row" }, [
      el("span", { class: "stat" }, `${data.summary.riskFindingCount} candidate findings`),
      el("span", { class: "stat" }, `${data.summary.motifMatchCount} motif matches`),
      el("span", { class: "hint" }, "Click a finding to highlight its evidence in the graph."),
    ]));

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

  // ---- matched motifs tab ----------------------------------------------------
  let selectedMotifRow = null;

  // "Almost matched" motifs: what the graph is missing for each one. Turns a
  // thin or empty result into a checklist instead of a silent non-match.
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
    // clicking highlights the elements that are the likeliest fix
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

  /* Why does this element carry that category?
   *
   * A propagated category is the engine's claim, not the modeler's, and one they
   * cannot check from the graph alone - the annotation that caused it may be
   * several hops upstream. Each hop is grouped under the element it landed on
   * and the chain is walked back to the element nobody derived, which is the one
   * a human actually annotated. Clicking a row highlights the whole path in the
   * diagram, so the claim can be read off the picture.
   */
  function renderDerivedCategories(rows) {
    const list = $("#derived-list");
    const empty = $("#derived-empty");
    const count = $("#derived-count");
    list.innerHTML = "";
    if (!rows || !rows.length) {
      empty.textContent = "Nothing was inferred: every data category in this graph was annotated by hand.";
      empty.classList.remove("hidden");
      count.textContent = "";
      return;
    }
    empty.classList.add("hidden");
    count.textContent = String(rows.length);

    /* Hop lookup: "element|category" -> EVERY hop that put the category there.
     * An element can acquire the same category from several upstream elements,
     * so keeping one per key silently hid alternative provenance. */
    const hopsBy = new Map();
    rows.forEach((r) => {
      const key = `${r.element.id}|${r.category.id}`;
      if (!hopsBy.has(key)) hopsBy.set(key, []);
      hopsBy.get(key).push(r);
    });

    /* Trace back to the annotation the category actually came from.
     *
     * Following hops backwards and reporting wherever you stop is wrong when the
     * flow contains a loop - a conversation store written at the end of a turn
     * and read at the start of the next is a loop - because the category
     * circulates and there is no last hop. Whatever the walk reported as the
     * "origin" was then an artefact of traversal order, which is how a structured
     * response ended up blamed on the context-update step it feeds rather than
     * on the store it came from.
     *
     * Breadth-first back to the nearest ANNOTATED source instead: the element a
     * human tagged is a real endpoint, and searching for it terminates a cycle on
     * a meaningful criterion. If no annotated source is reachable the trail is
     * genuinely circular, and the row says so rather than inventing a start.
     */
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

    // One entry per (element, category) the modeler sees on an element.
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
    // Collapse repeated matches of the same motif into one row (a motif can match
    // several times with different elements — e.g. External Dependency per source).
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
      renderMotifGaps(gaps); // say what is missing, not just that nothing matched
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
      });
      list.appendChild(row);
    });
    renderMotifGaps(gaps);
    $("#motifs-count").textContent = String(rows.length);
  }

  // ---- validation ------------------------------------------------------------
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

  // ---- split divider ---------------------------------------------------------
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

  // ---- starter graph ---------------------------------------------------------
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

  // ---- in-canvas annotation --------------------------------------------------
  // ---- diagram -> code edits (serialized) ------------------------------------
  // Every structural edit runs through one queue, so rapid actions (add several
  // components, connect, delete in a row) never race on the editor value: each
  // reads the latest code only after the previous edit has written it back.
  let mutating = Promise.resolve();
  function runMutation(task) {
    const next = mutating.then(task, task);
    mutating = next.catch(() => {});
    return next;
  }

  // Edit an element (label / name / type / role / category) from the popup.
  function applyEdit(elementId, edit) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "edit-element", element: elementId, ...edit,
        });
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
        Editor.setValue(ttl);
        setStatus("ok", "Element deleted");
      } catch (error) {
        setStatus("error", "Could not delete: " + error.message.split("\n")[0]);
      }
    });
  }

  // Add a BEAM flow edge from a canvas port-drag. use = resource→process,
  // produce = process→resource, inform = process→process.
  function applyConnect(triple) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue(), op: "add-edge", ...triple,
        });
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
        Editor.setValue(ttl);
        setStatus("ok", `Added ${item.label} — click it to edit, drag its ▸ port to connect`);
      } catch (error) {
        setStatus("error", "Could not add element: " + error.message.split("\n")[0]);
      }
    });
  }

  // Build a collapsible tray: a clickable header (title + chevron) that toggles a
  // `collapsed` class on the tray, hiding its body. Used by both symbol palette
  // and motif catalogue.
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

  // Click a tray item to add it (at center); or drag it onto the canvas to drop
  // at a point, then invoke onDrop(x, y) (both null on a plain click). Pointer-
  // based because native HTML5 DnD fought the canvas pan / pointer capture.
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

  // ---- motif catalogue -------------------------------------------------------
  // Add a motif that a finding's control suggests as a structural mitigation
  // (the chips under "suggested mitigation"). motifRef.id is the motif URI.
  function addSuggestedMotif(motifRef) {
    const shortId = String(motifRef.id || "").split(/[#/]/).pop();
    if (!shortId) return;
    addMotif({ id: shortId, label: motifRef.label || shortId });
  }

  function addMotif(item) {
    return runMutation(async () => {
      try {
        const { ttl } = await postJson("/api/graph-edit", {
          ttl: Editor.getValue() || "@prefix beam: <http://w3id.org/beam/core#> .\n",
          op: "add-motif", motif: item.id,
        });
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
    buildTray(panel, "Motifs", body, true); // 24 items - start collapsed, expand on demand
  }

  // ---- init ------------------------------------------------------------------
  async function init() {
    GraphView.init();
    Editor.init({ onChange: refreshPreview });
    initDivider();

    let vocabulary = { roles: [], dataCategories: [] };
    try {
      vocabulary = await api("/api/vocabulary");
    } catch (_) { /* annotation popups will just have empty pick lists */ }
    const classes = [...(vocabulary.resourceClasses || []), ...(vocabulary.processClasses || [])];
    GraphView.setAnnotation({ vocabulary, classes, onEdit: applyEdit, onDelete: applyDelete, onConnect: applyConnect, onStatus: setStatus });
    Annotate.init({ vocabulary, onStatus: setStatus });

    initPalette();
    initMotifPalette(vocabulary.motifTemplates || []);

    try {
      const examples = await api("/api/examples");
      const select = $("#example-select");
      examples.forEach((ex) => select.appendChild(el("option", { value: ex.name }, ex.name)));
    } catch (_) { /* non-fatal */ }

    $("#example-select").addEventListener("change", async (ev) => {
      const name = ev.target.value;
      if (!name) return;
      try {
        const { ttl } = await api(`/api/examples/${encodeURIComponent(name)}`);
        Editor.setValue(ttl);
        setStatus("ok", `Loaded example: ${name}`);
      } catch (error) {
        setStatus("error", error.message);
      }
    });

    // Open a graph file. A Tool4Boxology / t4b-beam export carries its own
    // vocabulary, so loading it verbatim would leave BEAM queries with nothing
    // to match; route those through the normalizer instead of the editor. Any
    // other Turtle is already BEAM and loads as-is.
    $("#file-input").addEventListener("change", (ev) => {
      const file = ev.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async () => {
        const text = String(reader.result);
        if (!text.includes("tool4boxology.org")) {
          Editor.setValue(text);
          setStatus("ok", `Loaded file: ${file.name}`);
          return;
        }
        setStatus("busy", `Normalizing Tool4Boxology export: ${file.name}…`);
        try {
          const fmt = /\.nt$/i.test(file.name) ? "nt" : "turtle";
          const { ttl, warnings } = await postJson("/api/import/t4b", { data: text, format: fmt });
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
