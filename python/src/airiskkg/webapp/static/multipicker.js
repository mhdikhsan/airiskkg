"use strict";

/* Shared multi-value picker: current selections show as removable chips, plus an
 * "add" dropdown listing the remaining vocabulary. Lets an element carry several
 * roles / data categories. Used by the node popup (graph.js) and the Annotate
 * table (annotate.js).
 *
 * window.MultiPicker(items, selectedIds, {placeholder}) -> { element, getValues }
 *   items       : [{ id, label }]
 *   selectedIds : [id, ...] already-selected ids
 *   getValues() : current selected ids (array)
 */
(function () {
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    attrs = attrs || {};
    for (const k in attrs) {
      const v = attrs[k];
      if (k === "class") node.className = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (v != null) node.setAttribute(k, v);
    }
    for (const child of [].concat(children || [])) {
      if (child == null) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  window.MultiPicker = function (items, selectedIds, opts) {
    opts = opts || {};
    items = items || [];
    const selected = new Set(selectedIds || []);
    const labelOf = new Map(items.map((it) => [it.id, it.label]));

    const chipsEl = el("div", { class: "mp-chips" });
    const addSelect = el("select", { class: "an-select mp-add" });
    const container = el("div", { class: "mp" }, [chipsEl, addSelect]);

    function renderChips() {
      chipsEl.innerHTML = "";
      selected.forEach((id) => {
        chipsEl.appendChild(el("span", { class: "mp-chip" }, [
          el("span", { class: "mp-chip-label" }, labelOf.get(id) || id),
          el("span", {
            class: "mp-x", title: "Remove",
            onclick: (e) => { e.stopPropagation(); selected.delete(id); render(); },
          }, "×"),
        ]));
      });
      chipsEl.style.display = selected.size ? "flex" : "none";
    }

    function renderSelect() {
      addSelect.innerHTML = "";
      addSelect.appendChild(el("option", { value: "" }, opts.placeholder || "+ add"));
      for (const it of items) {
        if (selected.has(it.id)) continue;
        addSelect.appendChild(el("option", { value: it.id }, it.label));
      }
      addSelect.value = "";
    }

    function render() { renderChips(); renderSelect(); }

    addSelect.addEventListener("change", (e) => {
      e.stopPropagation();
      if (addSelect.value) { selected.add(addSelect.value); render(); }
    });
    // keep clicks inside the picker from triggering a parent row's handler
    container.addEventListener("click", (e) => e.stopPropagation());

    render();
    return { element: container, getValues: () => [...selected] };
  };
})();
