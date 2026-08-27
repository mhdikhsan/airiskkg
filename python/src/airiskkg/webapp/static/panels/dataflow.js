import { $, $$, el } from "../core/dom.js";
import { GraphView } from "../lib/graph_view.js";

export function clearDerivedCategories() {
  $("#derived-list").innerHTML = "";
  $("#derived-count").textContent = "";
  $("#derived-empty").classList.remove("hidden");
}

export function renderDerivedCategories(rows) {
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
    el("span", {}, "Inferred categories"),
    el("span", { class: "derived-section-hint" },
      "Click a row to trace it on the diagram."),
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
