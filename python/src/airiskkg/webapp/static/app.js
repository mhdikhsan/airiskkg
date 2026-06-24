"use strict";

// ---- small DOM helpers -----------------------------------------------------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
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

// ---- global vocabulary -----------------------------------------------------
let VOCAB = { roles: [], dataCategories: [], resourceClasses: [], processClasses: [], edgeKinds: [] };

function optionsFrom(items, selected = []) {
  return items.map((it) =>
    el("option", { value: it.id, selected: selected.includes(it.id) ? "selected" : null }, it.label)
  );
}

// ---- builder ---------------------------------------------------------------
function multiSelect(items, selected) {
  return el("select", { multiple: "multiple", size: Math.min(5, Math.max(3, items.length)) }, optionsFrom(items, selected));
}

function elementNames() {
  return $$("#resources .element-card, #processes .element-card")
    .map((card) => $(".el-name", card).value.trim())
    .filter(Boolean);
}

function refreshEdgeOptions() {
  const resourceNames = $$("#resources .element-card").map((c) => $(".el-name", c).value.trim()).filter(Boolean);
  const processNames = $$("#processes .element-card").map((c) => $(".el-name", c).value.trim()).filter(Boolean);
  $$("#processes .element-card").forEach((card) => {
    $$("select.edge", card).forEach((sel) => {
      const target = sel.dataset.target;
      const pool = target === "process" ? processNames : resourceNames;
      const chosen = Array.from(sel.selectedOptions).map((o) => o.value);
      sel.innerHTML = "";
      pool.forEach((name) =>
        sel.appendChild(el("option", { value: name, selected: chosen.includes(name) ? "selected" : null }, name))
      );
    });
  });
}

function resourceCard(data = {}) {
  const card = el("div", { class: "element-card" });
  card.appendChild(
    el("div", { class: "element-card-head" }, [
      el("strong", {}, "Resource"),
      el("button", { class: "btn small icon", title: "Remove", onclick: () => { card.remove(); refreshEdgeOptions(); } }, "✕"),
    ])
  );
  const name = el("input", { type: "text", class: "el-name", placeholder: "UserQuestion", value: data.name || "" });
  name.addEventListener("input", refreshEdgeOptions);
  const grid = el("div", { class: "grid" }, [
    el("label", { class: "field" }, [el("span", {}, "Name"), name]),
    el("label", { class: "field" }, [el("span", {}, "Label"), el("input", { type: "text", class: "el-label", placeholder: "Question about product", value: data.label || "" })]),
    el("label", { class: "field full" }, [el("span", {}, "Class"), el("select", { class: "el-class" }, optionsFrom(VOCAB.resourceClasses, [data.class || VOCAB.resourceClasses[0]?.id]))]),
    el("label", { class: "field" }, [el("span", {}, "Roles"), multiSelect(VOCAB.roles, data.roles || [])]),
    el("label", { class: "field" }, [el("span", {}, "Data categories"), multiSelect(VOCAB.dataCategories, data.dataCategories || [])]),
  ]);
  // mark the two multi-selects for collection
  const selects = $$("select", grid).filter((s) => s.multiple);
  selects[0].classList.add("el-roles");
  selects[1].classList.add("el-categories");
  card.appendChild(grid);
  return card;
}

function processCard(data = {}) {
  const card = el("div", { class: "element-card" });
  card.appendChild(
    el("div", { class: "element-card-head" }, [
      el("strong", {}, "Process"),
      el("button", { class: "btn small icon", title: "Remove", onclick: () => { card.remove(); refreshEdgeOptions(); } }, "✕"),
    ])
  );
  const name = el("input", { type: "text", class: "el-name", placeholder: "Retrieval", value: data.name || "" });
  name.addEventListener("input", refreshEdgeOptions);

  const edgeFields = VOCAB.edgeKinds.map((kind) => {
    const sel = el("select", { multiple: "multiple", size: "3", class: "edge", "data-kind": kind.id, "data-target": kind.target });
    return el("label", { class: "field" }, [el("span", {}, kind.label), sel]);
  });

  const grid = el("div", { class: "grid" }, [
    el("label", { class: "field" }, [el("span", {}, "Name"), name]),
    el("label", { class: "field" }, [el("span", {}, "Label"), el("input", { type: "text", class: "el-label", placeholder: "Product retrieval", value: data.label || "" })]),
    el("label", { class: "field full" }, [el("span", {}, "Class"), el("select", { class: "el-class" }, optionsFrom(VOCAB.processClasses, [data.class || VOCAB.processClasses[0]?.id]))]),
    el("label", { class: "field full" }, [el("span", {}, "Roles"), (() => { const s = multiSelect(VOCAB.roles, data.roles || []); s.classList.add("el-roles"); return s; })()]),
    ...edgeFields,
  ]);
  card.appendChild(grid);
  return card;
}

function collectModel() {
  const resources = $$("#resources .element-card").map((card) => ({
    name: $(".el-name", card).value.trim(),
    label: $(".el-label", card).value.trim(),
    class: $(".el-class", card).value,
    roles: Array.from($(".el-roles", card).selectedOptions).map((o) => o.value),
    dataCategories: Array.from($(".el-categories", card).selectedOptions).map((o) => o.value),
  }));
  const processes = $$("#processes .element-card").map((card) => {
    const proc = {
      name: $(".el-name", card).value.trim(),
      label: $(".el-label", card).value.trim(),
      class: $(".el-class", card).value,
      roles: Array.from($(".el-roles", card).selectedOptions).map((o) => o.value),
    };
    $$("select.edge", card).forEach((sel) => {
      proc[sel.dataset.kind] = Array.from(sel.selectedOptions).map((o) => o.value);
    });
    return proc;
  });
  return {
    systemName: $("#system-name").value.trim() || "System",
    systemLabel: $("#system-label").value.trim(),
    resources,
    processes,
  };
}

// A small starter pipeline so users see the shape of a model.
const STARTER = {
  resources: [
    { name: "UserQuestion", label: "User question", class: "http://w3id.org/beam/core#Data",
      roles: ["http://w3id.org/airiskkg/pair-ai#PublicUserInput"],
      dataCategories: ["http://w3id.org/airiskkg/pair-ai#ExternalUserContent"] },
    { name: "VectorDB", label: "Knowledge vector store", class: "http://w3id.org/beam/core#Data",
      roles: ["http://w3id.org/airiskkg/pair-ai#VectorStore"],
      dataCategories: ["http://w3id.org/airiskkg/pair-ai#SensitiveInformation"] },
    { name: "RetrievedContext", label: "Retrieved context", class: "http://w3id.org/beam/core#Data",
      roles: ["http://w3id.org/airiskkg/pair-ai#RetrievedResult"],
      dataCategories: ["http://w3id.org/airiskkg/pair-ai#UntrustedContent"] },
    { name: "LLM", label: "Generative model", class: "http://w3id.org/beam/core#StatisticalModel",
      roles: ["http://w3id.org/airiskkg/pair-ai#GenerativeModel"], dataCategories: [] },
    { name: "Answer", label: "User-facing answer", class: "http://w3id.org/beam/core#Data",
      roles: ["http://w3id.org/airiskkg/pair-ai#PublicUserFacingOutput"], dataCategories: [] },
  ],
  processes: [
    { name: "Retrieval", label: "Vector retrieval", class: "http://w3id.org/beam/core#Infer",
      roles: ["http://w3id.org/airiskkg/pair-ai#RetrievalStep"],
      use: ["UserQuestion", "VectorDB"], produce: ["RetrievedContext"], inform: ["Generation"] },
    { name: "Generation", label: "LLM generation", class: "http://w3id.org/beam/core#Transform",
      roles: ["http://w3id.org/airiskkg/pair-ai#GenerationStep", "http://w3id.org/airiskkg/pair-ai#PromptConstructionStep"],
      use: ["RetrievedContext", "LLM"], produce: ["Answer"], inform: [] },
  ],
};

function loadModelIntoBuilder(model) {
  $("#resources").innerHTML = "";
  $("#processes").innerHTML = "";
  (model.resources || []).forEach((r) => $("#resources").appendChild(resourceCard(r)));
  (model.processes || []).forEach((p) => $("#processes").appendChild(processCard(p)));
  refreshEdgeOptions();
  // edges depend on names existing first; set selections after refresh
  $$("#processes .element-card").forEach((card, i) => {
    const p = (model.processes || [])[i] || {};
    $$("select.edge", card).forEach((sel) => {
      const want = p[sel.dataset.kind] || [];
      Array.from(sel.options).forEach((o) => { o.selected = want.includes(o.value); });
    });
  });
}

// ---- results rendering -----------------------------------------------------
function renderRefList(refs, extraClass = "") {
  return el("ul", { class: `ref-list ${extraClass}` },
    refs.map((r) => el("li", { title: r.definition || "" }, r.label)));
}

function groupBySource(refs) {
  const groups = {};
  refs.forEach((r) => { (groups[r.source] = groups[r.source] || []).push(r); });
  return groups;
}

function renderTaxonomy(entries) {
  const groups = groupBySource(entries);
  const blocks = Object.keys(groups).map((source) =>
    el("div", {}, [el("div", { class: "tax-source" }, source), renderRefList(groups[source])]));
  return el("div", {}, blocks);
}

function findingCard(f) {
  const meta = el("div", { class: "meta" }, [
    f.motif ? el("span", { class: "chip motif", title: f.motif.id }, `motif: ${f.motif.label}`) : null,
    f.mechanism ? el("span", { class: "chip mech", title: f.mechanism.id }, `mechanism: ${f.mechanism.label}`) : null,
    f.status ? el("span", { class: "chip status" }, f.status) : null,
  ]);

  const grid = el("div", { class: "finding-grid" }, [
    el("div", { class: "finding-block full", style: "grid-column:1/-1" }, [
      el("h5", {}, "Candidate risk taxonomy entries"),
      renderTaxonomy(f.taxonomyEntries),
    ]),
    el("div", { class: "finding-block" }, [
      el("h5", {}, "Suggested controls"),
      renderRefList(f.suggestedControls, "controls"),
    ]),
    el("div", { class: "finding-block" }, [
      el("h5", {}, "Evidence elements"),
      renderRefList(f.evidence, "evidence"),
    ]),
  ]);

  return el("div", { class: "finding" }, [
    el("h3", {}, f.label),
    f.description ? el("p", { class: "desc" }, f.description) : null,
    meta,
    grid,
  ]);
}

function renderResults(data) {
  const root = $("#results");
  root.innerHTML = "";
  $("#results-empty").classList.add("hidden");
  root.classList.remove("hidden");

  root.appendChild(el("div", { class: "summary" }, [
    el("div", { class: "stat" }, [el("div", { class: "num" }, String(data.summary.riskFindingCount)), el("div", { class: "lbl" }, "Risk findings")]),
    el("div", { class: "stat" }, [el("div", { class: "num" }, String(data.summary.motifMatchCount)), el("div", { class: "lbl" }, "Motif matches")]),
  ]));

  const owasp = data.summary.findingsByOwaspCategory || [];
  if (owasp.length) {
    const max = Math.max(...owasp.map((o) => o.count));
    root.appendChild(el("div", { class: "owasp-breakdown" }, [
      el("h4", {}, "Findings by OWASP LLM category"),
      ...owasp.map((o) =>
        el("div", { class: "bar-row" }, [
          el("div", { class: "bar-track" }, [el("div", { class: "bar", style: `width:${(o.count / max) * 100}%` })]),
          el("span", {}, `${o.label} · ${o.count}`),
        ])
      ),
    ]));
  }

  if (!data.findings.length) {
    root.appendChild(el("p", { class: "desc" }, "No candidate risk findings were produced for this architecture."));
  }
  data.findings.forEach((f) => root.appendChild(findingCard(f)));

  if (data.motifMatches.length) {
    const details = el("details", { class: "collapsible" }, [
      el("summary", {}, `Matched architecture motifs (${data.motifMatches.length})`),
    ]);
    data.motifMatches.forEach((m) => {
      const bindings = m.boundElements.map((b) => `${b.patternNode} = ${b.element}`).join(" · ");
      details.appendChild(el("div", { class: "match" }, [
        el("strong", {}, m.motif ? m.motif.label : "Motif"),
        el("div", { class: "bindings" }, bindings),
      ]));
    });
    root.appendChild(details);
  }
  root.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---- wiring ----------------------------------------------------------------
function showError(msg) {
  const box = $("#input-error");
  box.textContent = msg;
  box.classList.toggle("hidden", !msg);
}

function switchTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tab-body").forEach((b) => b.classList.toggle("hidden", b.dataset.tabBody !== name));
}

async function init() {
  try {
    VOCAB = await api("/api/vocabulary");
  } catch (e) {
    showError("Failed to load vocabulary: " + e.message);
    return;
  }

  loadModelIntoBuilder(STARTER);

  // examples dropdown
  try {
    const examples = await api("/api/examples");
    const select = $("#example-select");
    examples.forEach((ex) => select.appendChild(el("option", { value: ex.name }, ex.name)));
  } catch (_) { /* non-fatal */ }

  $$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
  $("#add-resource").addEventListener("click", () => { $("#resources").appendChild(resourceCard()); });
  $("#add-process").addEventListener("click", () => { $("#processes").appendChild(processCard()); refreshEdgeOptions(); });
  $("#load-example-into-builder").addEventListener("click", () => loadModelIntoBuilder(STARTER));

  $("#generate-ttl").addEventListener("click", async () => {
    showError("");
    try {
      const { ttl } = await api("/api/build", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectModel()) });
      $("#ttl-source").value = ttl;
      switchTab("source");
    } catch (e) {
      showError(e.message);
    }
  });

  $("#example-select").addEventListener("change", async (ev) => {
    const name = ev.target.value;
    if (!name) return;
    showError("");
    try {
      const { ttl } = await api(`/api/examples/${encodeURIComponent(name)}`);
      $("#ttl-source").value = ttl;
    } catch (e) {
      showError(e.message);
    }
  });

  $("#file-input").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { $("#ttl-source").value = reader.result; };
    reader.readAsText(file);
  });

  $("#run-assessment").addEventListener("click", async () => {
    showError("");
    const ttl = $("#ttl-source").value.trim();
    if (!ttl) { showError("Provide an architecture graph (Turtle) to assess."); return; }
    $("#results-empty").classList.add("hidden");
    $("#results").classList.remove("hidden");
    $("#results").innerHTML = '<div class="spinner">Running assessment…</div>';
    try {
      const data = await api("/api/assess", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ttl }) });
      renderResults(data);
    } catch (e) {
      $("#results").innerHTML = "";
      $("#results").classList.add("hidden");
      $("#results-empty").classList.remove("hidden");
      showError(e.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
