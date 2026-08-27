import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { MultiPicker } from "../lib/multipicker.js";
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

function setCount(n) {
  const badge = $("#annotate-count");
  if (badge) badge.textContent = n ? String(n) : "";
}

/* One row per element, grouped by the architecture that holds it.
 *
 * A document can carry several architectures - a business process running two
 * systems is the ordinary case - and a flat list of every element from all of
 * them gives no way to tell which is which. Membership comes from the server,
 * off beam:hasProcess / hasResource / hasAgent / contain. */
function annotateRow(node, untagged) {
  const rolePicker = MultiPicker(vocab.roles, node.roleIds || [], {
    placeholder: "+ add role", grouped: true, filterKind: roleKindFor(node),
  });
  const catPicker = MultiPicker(vocab.dataCategories, node.categoryIds || [],
    { placeholder: "+ add category" });
  rows.push({ id: node.id, rolePicker, catPicker });

  return el("div", {
    class: "annotate-row",
    title: `${node.typeLabel || node.kind} — click to highlight it on the diagram`,
    /* Was guarded on window.GraphView, which stopped existing when the front
     * end became modules: the row looked clickable and did nothing. */
    onclick: () => GraphView.setHighlight([node.id]),
  }, [
    el("span", { class: "an-el" }, [
      // The kind, not the type label: five values that align, where
      // "StatisticalModel" and "Data" left the column ragged.
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
    // One architecture needs no heading; it is the only thing on screen.
    if (group.label && groups.length > 1) {
      body.push(el("div", { class: "annotate-group" }, group.label));
    } else if (!group.label && groups.length > 1) {
      body.push(el("div", { class: "annotate-group" }, "Belongs to no system"));
    }
    for (const node of group.nodes) {
      if (!(node.roleIds || []).length) untagged += 1;
      body.push(annotateRow(node, untagged));
    }
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
    const data = await postJson("/api/graph", { ttl });
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