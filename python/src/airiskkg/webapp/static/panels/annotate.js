import { Editor } from "../lib/editor.js";
import { revealInSource } from "../core/source.js";
import { GraphView } from "../lib/graph_view.js";
import { MultiPicker } from "../lib/multipicker.js";
import { state } from "../state.js";
"use strict";
const $ = (sel, root = document) => root.querySelector(sel);

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

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}
const roleKindFor = (node) => (node.kind === "process" ? "process" : "resource");

let vocab = { roles: [], dataCategories: [] };
let onStatus = () => {};
let rows = []; // { id, rolePicker, catPicker }
let collapsed = new Set();  // architecture groups the reader folded away

function setCount(n) {
  const badge = $("#annotate-count");
  if (badge) badge.textContent = n ? String(n) : "";
}

function annotateRow(node) {
  const rolePicker = MultiPicker(vocab.roles, node.roleIds || [], {
    placeholder: "+ add role", grouped: true, filterKind: roleKindFor(node),
  });
  const catPicker = MultiPicker(vocab.dataCategories, node.categoryIds || [],
    { placeholder: "+ add category" });
  rows.push({ id: node.id, rolePicker, catPicker });

  return el("div", {
    class: "annotate-row",
    title: `${node.typeLabel || node.kind} — click to highlight it on the diagram`,
    onclick: () => {
      GraphView.setHighlight([node.id]);
      revealInSource([node.id]);
    },
  }, [
    el("span", { class: "an-el" }, [
      el("span", { class: `kind-badge ${node.kind}` }, node.kind),
      el("span", { class: "an-el-label" }, node.label),
    ]),
    el("span", { class: "an-role" }, rolePicker.element),
    el("span", { class: "an-cat" }, catPicker.element),
  ]);
}

function renderTable(data) {
  rows = [];
  const nodes = data.nodes || [];
  const list = $("#annotate-list");
  list.innerHTML = "";
  if (!nodes.length) {
    list.appendChild(el("p", { class: "drawer-empty" },
      "No architecture elements found. Load or import a graph, then reopen this tab."));
    setCount(0);
    return;
  }

  const body = [el("div", { class: "annotate-row annotate-row-head" }, [
    el("span", { class: "an-el" }, "Element"),
    el("span", { class: "an-role" }, "Roles"),
    el("span", { class: "an-cat" }, "Data categories (optional)"),
  ])];

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const systems = (data.systems || []).filter((s) => (s.members || []).length);
  const claimed = new Set(systems.flatMap((s) => s.members));
  const groups = systems
    .map((s) => ({ label: s.label, nodes: s.members.map((id) => byId.get(id)).filter(Boolean) }))
    .concat([{ label: null, nodes: nodes.filter((n) => !claimed.has(n.id)) }])
    .filter((g) => g.nodes.length);

  let untagged = 0;
  for (const group of groups) {
    const label = group.label || "Belongs to no system";
    const rowsOfGroup = group.nodes.map((node) => {
      if (!(node.roleIds || []).length) untagged += 1;
      return annotateRow(node);
    });

    // One architecture needs no heading; it is the only thing on screen.
    if (groups.length < 2) {
      body.push(...rowsOfGroup);
      continue;
    }

    const open = !collapsed.has(label);
    const head = el("div", {
      class: `annotate-group${open ? "" : " collapsed"}`,
      title: open ? "Hide these elements" : "Show these elements",
      onclick: () => {
        if (collapsed.has(label)) collapsed.delete(label);
        else collapsed.add(label);
        renderTable(data);
      },
    }, [
      el("span", { class: "annotate-group-mark" }, open ? "–" : "+"),
      el("span", {}, label),
      el("span", { class: "annotate-group-count" }, `${group.nodes.length}`),
    ]);
    body.push(head);
    if (open) body.push(...rowsOfGroup);
  }
  list.append(...body);
  setCount(untagged);
}

async function refresh() {
  const list = $("#annotate-list");
  const ttl = Editor.getValue().trim();  // imported, so it is always there
  if (!ttl) {
    list.innerHTML = "";
    list.appendChild(el("p", { class: "drawer-empty" },
      "Load or import an architecture graph, then reopen this tab to tag its elements."));
    setCount(0);
    return;
  }
  try {
    const data = await postJson("/api/graph", { ttl, scope: state.scopedSystem });
    renderTable(data);
  } catch (error) {
    list.innerHTML = "";
    list.appendChild(el("p", { class: "drawer-empty" },
      "Fix the graph before annotating — " + error.message.split("\n")[0]));
    setCount(0);
  }
}

async function apply() {
  if (!rows.length) return;
  const annotations = {};
  for (const row of rows) {
    annotations[row.id] = { roles: row.rolePicker.getValues(), categories: row.catPicker.getValues() };
  }
  const button = $("#btn-annotate-apply");
  button.disabled = true;
  onStatus("busy", "Applying role annotations…");
  try {
    const { ttl } = await postJson("/api/annotate", { ttl: Editor.getValue(), annotations });
    Editor.setValue(ttl); // fires the change handler -> refreshes the preview
    const tagged = Object.values(annotations).filter((a) => a.roles.length).length;
    onStatus("ok", `Applied roles to ${tagged} element(s) — now Run assessment`);
    await refresh();
  } catch (error) {
    onStatus("error", "Could not apply annotations: " + error.message.split("\n")[0]);
  } finally {
    button.disabled = false;
  }
}

function init(options) {
  vocab = options.vocabulary || vocab;
  onStatus = options.onStatus || onStatus;
  const applyBtn = $("#btn-annotate-apply");
  if (applyBtn) applyBtn.addEventListener("click", apply);
}

export const Annotate = { init, refresh };