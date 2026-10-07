"use strict";


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

const OTHER = "Other";

// The BEAM class the term goes on; `group` is the old top-level role.
function shelfOf(item) {
  return item.shelf || item.group || OTHER;
}

// Orders the shelves, never filters them: some match queries constrain no class
// at all, so hiding on the declared one hides a term that binds.
function fitRank(item, typeUri) {
  if (!typeUri) return 1;
  if (item.shelfId === typeUri) return 0;
  if ((item.appliesTo || []).includes(typeUri)) return 1;
  return 2;
}

function fitsSide(item, kind) {
  return !item.applies || !kind || item.applies === kind;
}

// One listener for every picker on the page: the annotate table rebuilds its
// rows on each refresh, so one per instance accumulates on document.
const openPickers = new Set();
document.addEventListener("pointerdown", (event) => {
  openPickers.forEach((picker) => picker(event));
});

export const MultiPicker = function (items, selectedIds, opts) {
  opts = opts || {};
  items = items || [];
  const selected = new Set(selectedIds || []);
  const byId = new Map(items.map((it) => [it.id, it]));

  let query = "";
  let family = null;
  let showAll = false;
  let open = false;
  let cursor = 0;

  const chipsEl = el("div", { class: "mp-chips" });
  const trigger = el("button", {
    type: "button", class: "mp-add", "aria-haspopup": "listbox", "aria-expanded": "false",
  }, opts.placeholder || "+ add");
  const search = el("input", {
    type: "text", class: "mp-search", placeholder: "Type to narrow", "aria-label": "Search terms",
  });
  const familyBar = el("div", { class: "mp-families" });
  const listEl = el("div", { class: "mp-list", role: "listbox" });
  const foot = el("div", { class: "mp-foot" });
  const pop = el("div", { class: "mp-pop hidden" }, [search, familyBar, listEl, foot]);
  const container = el("div", { class: "mp" }, [chipsEl, trigger, pop]);

  function available() {
    return items.filter((it) => !selected.has(it.id));
  }

  function hits(it) {
    if (family && (it.families || []).length && !it.families.includes(family)) return false;
    if (!query) return true;
    const hay = (it.label + " " + (it.definition || "") + " " + shelfOf(it)).toLowerCase();
    return hay.includes(query);
  }

  function offered() {
    const pool = available();
    const side = showAll ? pool : pool.filter((it) => fitsSide(it, opts.filterKind));
    return { shown: side.filter(hits), hidden: pool.length - side.length };
  }

  /* Shelves in fit order, so the terms that go on this element come first and
     the rest stay reachable below them. */
  function shelves(list) {
    const bins = new Map();
    for (const it of list) {
      const key = shelfOf(it);
      if (!bins.has(key)) bins.set(key, { items: [], rank: 3 });
      const bin = bins.get(key);
      bin.items.push(it);
      bin.rank = Math.min(bin.rank, fitRank(it, opts.typeUri));
    }
    return [...bins.entries()]
      .sort((a, b) =>
        a[1].rank - b[1].rank
        || (a[0] === OTHER) - (b[0] === OTHER)
        || a[0].localeCompare(b[0]))
      .map(([name, bin]) => [
        name,
        bin.items.sort((x, y) => x.label.localeCompare(y.label)),
        bin.rank,
      ]);
  }

  function renderChips() {
    chipsEl.innerHTML = "";
    selected.forEach((id) => {
      const it = byId.get(id);
      chipsEl.appendChild(el("span", { class: "mp-chip", title: (it && it.definition) || id }, [
        el("span", { class: "mp-chip-label" }, (it && it.label) || id),
        el("span", {
          class: "mp-x", title: "Remove",
          onclick: (e) => { e.stopPropagation(); selected.delete(id); renderChips(); renderList(); },
        }, "×"),
      ]));
    });
    chipsEl.style.display = selected.size ? "flex" : "none";
  }

  function renderFamilies() {
    familyBar.innerHTML = "";
    const names = [...new Set(available().flatMap((it) => it.families || []))].sort();
    if (names.length < 2) return;
    // A term with no family of its own is a refinement that inherits one, so a
    // filter narrows what it offers rather than hiding that term.
    for (const name of [null].concat(names)) {
      familyBar.appendChild(el("button", {
        type: "button",
        class: "mp-fam" + (family === name ? " on" : ""),
        onclick: (e) => { e.stopPropagation(); family = name; cursor = 0; renderList(); renderFamilies(); },
      }, name || "All"));
    }
  }

  function renderList() {
    listEl.innerHTML = "";
    const { shown, hidden } = offered();
    if (cursor >= shown.length) cursor = Math.max(0, shown.length - 1);

    if (!shown.length) {
      listEl.appendChild(el("p", { class: "mp-none" }, "Nothing matches that."));
    }

    let index = 0;
    for (const [name, group, rank] of shelves(shown)) {
      listEl.appendChild(el("div", { class: "mp-shelf" + (rank > 1 ? " off" : ""), }, [
        el("span", {}, rank > 1 ? name + " (not this element)" : name),
        el("span", { class: "mp-shelf-count" }, String(group.length)),
      ]));
      for (const it of group) {
        const at = index++;
        listEl.appendChild(el("button", {
          type: "button",
          class: "mp-opt" + (at === cursor ? " at" : ""),
          role: "option",
          onmouseenter: () => { cursor = at; mark(); },
          onclick: (e) => { e.stopPropagation(); pick(it.id); },
        }, [
          el("span", { class: "mp-opt-label" }, it.label),
          it.definition ? el("span", { class: "mp-opt-def" }, it.definition) : null,
        ]));
      }
    }

    foot.innerHTML = "";
    if (hidden > 0 && !showAll) {
      foot.appendChild(el("button", {
        type: "button", class: "mp-all",
        onclick: (e) => { e.stopPropagation(); showAll = true; renderList(); renderFamilies(); },
      }, `Show ${hidden} for the other side of the graph`));
    } else if (showAll) {
      foot.appendChild(el("span", { class: "mp-note" },
        "Showing terms for processes and resources together"));
    }
  }

  function mark() {
    const options = [...listEl.querySelectorAll(".mp-opt")];
    options.forEach((node, at) => node.classList.toggle("at", at === cursor));
    if (options[cursor]) options[cursor].scrollIntoView({ block: "nearest" });
  }

  function pick(id) {
    selected.add(id);
    query = "";
    search.value = "";
    cursor = 0;
    renderChips();
    renderList();
    renderFamilies();
    search.focus();
  }

  const closeOnOutside = (event) => {
    if (open && !container.contains(event.target)) setOpen(false);
  };

  /* Fixed, not absolute: the node popup this sits in is `overflow: auto` with a
     max height, so an absolutely-positioned popover is clipped to a couple of
     rows nobody can scroll. Placed from the trigger, flipped up when the space
     below is too small. */
  function place() {
    const rect = trigger.getBoundingClientRect();
    const gap = 8;
    const width = Math.min(Math.max(rect.width, 300), window.innerWidth - 2 * gap);
    const below = window.innerHeight - rect.bottom - gap;
    const above = rect.top - gap;
    const up = below < 240 && above > below;
    const room = Math.max(180, Math.min(380, up ? above : below));

    pop.style.width = width + "px";
    pop.style.left = Math.max(gap, Math.min(rect.left, window.innerWidth - width - gap)) + "px";
    if (up) {
      pop.style.top = "auto";
      pop.style.bottom = (window.innerHeight - rect.top + 4) + "px";
    } else {
      pop.style.bottom = "auto";
      pop.style.top = (rect.bottom + 4) + "px";
    }
    pop.style.maxHeight = room + "px";
    // the rest of the popover is the search box, the family chips and the foot
    listEl.style.maxHeight = Math.max(110, room - 110) + "px";
  }

  const reposition = () => { if (open) place(); };

  function setOpen(next) {
    open = next;
    pop.classList.toggle("hidden", !open);
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      openPickers.add(closeOnOutside);
      renderFamilies();
      renderList();
      place();
      // the popup it sits in scrolls, and the trigger moves with it
      window.addEventListener("scroll", reposition, true);
      window.addEventListener("resize", reposition);
      search.focus();
    } else {
      openPickers.delete(closeOnOutside);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    }
  }

  trigger.addEventListener("click", (e) => { e.stopPropagation(); setOpen(!open); });

  search.addEventListener("input", () => {
    query = search.value.trim().toLowerCase();
    cursor = 0;
    renderList();
  });

  search.addEventListener("keydown", (e) => {
    const options = [...listEl.querySelectorAll(".mp-opt")];
    if (e.key === "Escape") { setOpen(false); trigger.focus(); e.preventDefault(); }
    else if (e.key === "ArrowDown") { cursor = Math.min(cursor + 1, options.length - 1); mark(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { cursor = Math.max(cursor - 1, 0); mark(); e.preventDefault(); }
    else if (e.key === "Enter" && options[cursor]) { options[cursor].click(); e.preventDefault(); }
  });

  // keep clicks inside the picker from triggering a parent row's handler
  container.addEventListener("click", (e) => e.stopPropagation());

  renderChips();
  return { element: container, getValues: () => [...selected] };
};
