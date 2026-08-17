"use strict";


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

    const OTHER = "Other";
    function groupsOf(available) {
      const byGroup = new Map();
      for (const it of available) {
        const key = it.group || OTHER;
        if (!byGroup.has(key)) byGroup.set(key, []);
        byGroup.get(key).push(it);
      }
      const names = [...byGroup.keys()].filter((n) => n !== OTHER).sort((a, b) => a.localeCompare(b));
      if (byGroup.has(OTHER)) names.push(OTHER);
      return names.map((name) => [name, byGroup.get(name).sort((a, b) => a.label.localeCompare(b.label))]);
    }

   
    const SHOW_ALL = "__show_all__";
    let showAll = false;
    function applicable(list) {
      if (showAll || !opts.filterKind) return { shown: list, hidden: 0 };
      const shown = list.filter((it) => !it.applies || it.applies === opts.filterKind);
      return { shown, hidden: list.length - shown.length };
    }

    function renderSelect() {
      addSelect.innerHTML = "";
      addSelect.appendChild(el("option", { value: "" }, opts.placeholder || "+ add"));
      const { shown, hidden } = applicable(items.filter((it) => !selected.has(it.id)));
      if (!opts.grouped) {
        for (const it of shown) addSelect.appendChild(el("option", { value: it.id }, it.label));
      } else {
        for (const [name, groupItems] of groupsOf(shown)) {
          const optgroup = el("optgroup", { label: name });
          for (const it of groupItems) optgroup.appendChild(el("option", { value: it.id }, it.label));
          addSelect.appendChild(optgroup);
        }
      }
      if (hidden > 0) {
        addSelect.appendChild(el("option", { value: SHOW_ALL, class: "mp-show-all" },
          `… show all roles (+${hidden})`));
      }
      addSelect.value = "";
    }

    function render() { renderChips(); renderSelect(); }

    addSelect.addEventListener("change", (e) => {
      e.stopPropagation();
      if (!addSelect.value) return;
      if (addSelect.value === SHOW_ALL) { showAll = true; render(); return; }
      selected.add(addSelect.value);
      render();
    });
    // keep clicks inside the picker from triggering a parent row's handler
    container.addEventListener("click", (e) => e.stopPropagation());

    render();
    return { element: container, getValues: () => [...selected] };
  };
})();
