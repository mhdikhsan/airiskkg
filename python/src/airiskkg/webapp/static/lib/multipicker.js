"use strict";

import { kindOf } from "./motif_preview.js";

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
const OTHER_ID = "mp:other";
const FLY_WIDTH = 250;

// The BEAM class the term goes on; `group` is the old top-level role.
function shelfOf(item) {
  return item.shelf || item.group || OTHER;
}

// The canvas's own shape for the shelf's class, so a shelf reads as the box it goes on.
function shelfKind(item) {
  return item.shelfId ? kindOf(item.shelfId.split(/[#/]/).pop()) : null;
}

// 0 and 1 fit the element's class, 2 does not. A term that does not fit is
// offered behind "Show more", never dropped: some match queries constrain no
// class at all, so a term declared for Data can still bind on a Symbol.
function fitRank(item, types) {
  if (!types.length) return 1;
  if (types.includes(item.shelfId)) return 0;
  if ((item.appliesTo || []).some((cls) => types.includes(cls))) return 1;
  return 2;
}

function fitsSide(item, kind) {
  return !item.applies || !kind || item.applies === kind;
}

// The element's BEAM classes: all of them when known, else its most specific one.
function typesOf(opts) {
  return opts.typeUris || (opts.typeUri ? [opts.typeUri] : []);
}

function fits(item, opts) {
  return fitsSide(item, opts.filterKind) && fitRank(item, typesOf(opts)) < 2;
}

/* pair:containsDataCategory is declared on beam:Data, so only a Data element
   is offered a category; one it already carries can still be removed. */
export function categoryPickerOptions(node, placeholder) {
  if (node.kind === "data") return { placeholder };
  return {
    cannotAdd: "only on Data",
    cannotAddWhy: "A data category says what content holds, so it goes on a Data element."
      + " The assessment carries it along the flow from there.",
  };
}

/* The role tree a cascading menu walks: each role under the roles it refines,
   with the categories at the top. A role refining only a category's parent
   (Processing Step, Resource Role) is the root of nothing and is left out. */
function roleTree(items) {
  const childrenOf = new Map();
  for (const it of items) {
    for (const parent of it.parents || []) {
      if (!childrenOf.has(parent)) childrenOf.set(parent, []);
      childrenOf.get(parent).push(it);
    }
  }
  const roots = items.filter((it) => it.category);
  const reached = new Set();
  const categoryOf = new Map();
  const walk = (it, category) => {
    if (reached.has(it.id)) return;
    reached.add(it.id);
    categoryOf.set(it.id, category);
    (childrenOf.get(it.id) || []).forEach((child) => walk(child, category));
  };
  roots.forEach((root) => walk(root, root.label));
  const loose = items.filter((it) => !reached.has(it.id)
    && !(childrenOf.get(it.id) || []).some((child) => child.category));
  if (loose.length) {
    roots.push({ id: OTHER_ID, label: OTHER, category: true });
    childrenOf.set(OTHER_ID, loose);
    loose.forEach((it) => categoryOf.set(it.id, OTHER));
  }
  return { roots, childrenOf, categoryOf };
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
  const tree = opts.tree ? roleTree(items) : null;

  let query = "";
  let family = null;
  let showAll = false;
  let open = false;
  let cursor = 0;

  const chipsEl = el("div", { class: "mp-chips" });
  const trigger = el("button", {
    type: "button", class: "mp-add", "aria-haspopup": "listbox", "aria-expanded": "false",
  }, opts.cannotAdd ? opts.cannotAdd : (opts.placeholder || "+ add"));
  // What it already carries stays removable; nothing new can be put on it.
  if (opts.cannotAdd) {
    trigger.disabled = true;
    trigger.title = opts.cannotAddWhy || opts.cannotAdd;
  }
  const search = el("input", {
    type: "text", class: "mp-search", placeholder: "Type to narrow", "aria-label": "Search terms",
  });
  const familyBar = el("div", { class: "mp-families" });
  const listEl = el("div", { class: "mp-list", role: "listbox" });
  const hint = el("div", { class: "mp-hint" + (tree ? "" : " hidden") });
  const foot = el("div", { class: "mp-foot" });
  const pop = el("div", { class: "mp-pop hidden" }, [search, familyBar, listEl, hint, foot]);
  const container = el("div", { class: "mp" }, [chipsEl, trigger, pop]);

  // A category files roles and matches nothing, so it is a folder, never a pick.
  function available() {
    return items.filter((it) => !selected.has(it.id) && !(tree && it.category));
  }

  function shelfName(it) {
    return tree ? (tree.categoryOf.get(it.id) || OTHER) : shelfOf(it);
  }

  function familyOk(it) {
    return !family || !(it.families || []).length || it.families.includes(family);
  }

  function hits(it) {
    if (!familyOk(it)) return false;
    if (!query) return true;
    const hay = (it.label + " " + (it.definition || "") + " " + shelfName(it)).toLowerCase();
    return hay.includes(query);
  }

  function offered() {
    const pool = available();
    const fitting = showAll ? pool : pool.filter((it) => fits(it, opts));
    return { shown: fitting.filter(hits), hidden: pool.length - fitting.length };
  }

  /* Shelves in fit order, so the terms that go on this element come first and
     the rest stay reachable below them. */
  function shelves(list) {
    const bins = new Map();
    for (const it of list) {
      const key = shelfName(it);
      if (!bins.has(key)) bins.set(key, { items: [], rank: 3 });
      const bin = bins.get(key);
      bin.items.push(it);
      bin.rank = Math.min(bin.rank, fitRank(it, typesOf(opts)));
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
          onclick: (e) => { e.stopPropagation(); selected.delete(id); renderChips(); render(); },
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
        onclick: (e) => { e.stopPropagation(); family = name; cursor = 0; render(); renderFamilies(); },
      }, name || "All"));
    }
  }

  function renderFoot(hidden) {
    foot.innerHTML = "";
    if (hidden > 0 && !showAll) {
      foot.appendChild(el("button", {
        type: "button", class: "mp-all",
        title: "Terms usually put on another kind of element. Some still match here.",
        onclick: (e) => { e.stopPropagation(); showAll = true; render(); renderFamilies(); },
      }, `Show ${hidden} more for other kinds of element`));
    } else if (showAll) {
      foot.appendChild(el("span", { class: "mp-note" },
        "Showing every term; those under \"not this element\" are rarely right here"));
    }
  }

  function render() {
    if (tree && !query) renderTree();
    else renderList();
  }

  function renderList() {
    closeFrom(1);
    listEl.innerHTML = "";
    const { shown, hidden } = offered();
    if (cursor >= shown.length) cursor = Math.max(0, shown.length - 1);

    if (!shown.length) {
      listEl.appendChild(el("p", { class: "mp-none" }, "Nothing matches that."));
    }

    let index = 0;
    for (const [name, group, rank] of shelves(shown)) {
      const kind = shelfKind(group[0]);
      // one box per shelf, so its sticky heading leaves with its last term
      const section = el("div", { class: "mp-group" }, el("div", {
        class: "mp-shelf" + (kind ? " " + kind : "") + (rank > 1 ? " off" : ""),
      }, [
        kind ? el("span", { class: "lib-swatch " + kind }) : null,
        el("span", { class: "mp-shelf-name" }, name),
        rank > 1 ? el("span", { class: "mp-shelf-note" }, "not this element") : null,
        el("span", { class: "mp-shelf-count" }, String(group.length)),
      ]));
      listEl.appendChild(section);
      for (const it of group) {
        const at = index++;
        section.appendChild(el("button", {
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
    renderFoot(hidden);
  }

  function mark() {
    const options = [...listEl.querySelectorAll(".mp-opt")];
    options.forEach((node, at) => node.classList.toggle("at", at === cursor));
    if (options[cursor]) options[cursor].scrollIntoView({ block: "nearest" });
  }

  /* ---- the cascading menu --------------------------------------------------
     Categories first, each opening onto the roles filed under it, and each role
     onto the roles that refine it. Hovering a row opens what is under it; the
     arrow does the same for a touch or a click, and the label picks. */
  let levels = [];  // [{ rows, cursor, panel, anchor, parent }]
  let depth = 0;    // the level the arrow keys move in
  let timer = null;
  let shows = () => true;
  let rankOf = () => 1;

  function visibility() {
    const seen = new Map();
    const best = new Map();
    const types = typesOf(opts);
    const visit = (it) => {
      if (seen.has(it.id)) return seen.get(it.id);
      seen.set(it.id, false);  // a cycle in the hierarchy reads as nothing below
      let rank = 3;
      let ok = false;
      if (!it.category && familyOk(it) && (showAll || fits(it, opts))) {
        ok = true;
        rank = fitsSide(it, opts.filterKind) ? fitRank(it, types) : 2;
      }
      for (const child of tree.childrenOf.get(it.id) || []) {
        if (visit(child)) { ok = true; rank = Math.min(rank, best.get(child.id)); }
      }
      seen.set(it.id, ok);
      best.set(it.id, rank);
      return ok;
    };
    tree.roots.forEach(visit);
    shows = (it) => visit(it);
    rankOf = (it) => (visit(it) ? best.get(it.id) : 3);
  }

  /* A row that does not go on this element is still drawn when something under
     it does, as the way there; it opens rather than picks until "Show more". */
  function canPick(it) {
    return !it.category && !selected.has(it.id) && familyOk(it) && (showAll || fits(it, opts));
  }

  function under(it) {
    return (tree.childrenOf.get(it.id) || []).filter(shows)
      .sort((a, b) => a.label.localeCompare(b.label));
  }

  function renderTree() {
    closeFrom(0);
    visibility();
    listEl.innerHTML = "";
    const rows = tree.roots.filter(shows).sort((a, b) =>
      rankOf(a) - rankOf(b)
      || (a.id === OTHER_ID) - (b.id === OTHER_ID)
      || a.label.localeCompare(b.label));
    if (!rows.length) listEl.appendChild(el("p", { class: "mp-none" }, "Nothing matches that."));
    levels = [{ rows, cursor: -1, panel: listEl, anchor: null, parent: null }];
    depth = 0;
    fill(0);
    showHint(null);
    renderFoot(offered().hidden);
  }

  function fill(level) {
    const { rows, panel } = levels[level];
    rows.forEach((it, at) => {
      const below = under(it);
      const chosen = selected.has(it.id);
      const off = level === 0 ? rankOf(it) > 1 : !it.category && !fits(it, opts);
      const kind = level === 0 && it.id !== OTHER_ID ? shelfKind(it) : null;
      panel.appendChild(el("div", {
        class: "mp-row" + (it.category ? " folder" : "") + (off ? " off" : "")
          + (chosen ? " chosen" : "") + (canPick(it) ? " pick" : ""),
        role: "menuitem",
        "aria-haspopup": below.length ? "menu" : null,
        "data-id": it.id,
        title: it.definition || null,
        onmouseenter: () => hover(level, at),
        onclick: (e) => { e.stopPropagation(); choose(level, at); },
      }, [
        kind ? el("span", { class: "lib-swatch " + kind }) : null,
        el("span", { class: "mp-row-label" }, it.label),
        chosen ? el("span", { class: "mp-row-note" }, "added") : null,
        off && level === 0 ? el("span", { class: "mp-row-note" }, "not this element") : null,
        below.length ? el("span", {
          class: "mp-row-more", title: `What refines ${it.label}`,
          onclick: (e) => { e.stopPropagation(); expand(level, at); depth = level + 1; markTree(); },
        }) : null,
      ]));
    });
  }

  function rowsOf(level) {
    return [...levels[level].panel.querySelectorAll(":scope > .mp-row")];
  }

  function markTree() {
    levels.forEach((lv, level) => {
      const next = levels[level + 1];
      rowsOf(level).forEach((row, at) => {
        row.classList.toggle("at", at === lv.cursor);
        row.classList.toggle("open", !!next && next.parent === lv.rows[at].id);
      });
    });
  }

  function showHint(it) {
    hint.innerHTML = "";
    if (!it) {
      hint.appendChild(el("span", { class: "mp-hint-empty" },
        "Point at a term to read what it means. A row with an arrow opens what refines it."));
      return;
    }
    hint.appendChild(el("span", { class: "mp-hint-label" }, it.label));
    if (it.category) {
      hint.appendChild(el("span", { class: "mp-hint-def" },
        "A category: it files roles and matches nothing itself, so pick a role under it."));
    } else if (!showAll && !fits(it, opts)) {
      hint.appendChild(el("span", { class: "mp-hint-def" },
        "Usually on another kind of element, so it is the way to what refines it."
        + (it.definition ? " " + it.definition : "")));
    } else if (it.definition) {
      hint.appendChild(el("span", { class: "mp-hint-def" }, it.definition));
    }
  }

  // The root list stays in the popover; only the submenus are taken down.
  function closeFrom(level) {
    clearTimeout(timer);
    const from = Math.max(level, 1);
    for (const lv of levels.slice(from)) lv.panel.remove();
    if (level === 0) levels = [];
    else if (levels.length > from) levels.length = from;
    if (depth >= levels.length) depth = Math.max(0, levels.length - 1);
  }

  function expand(level, at) {
    const it = levels[level].rows[at];
    levels[level].cursor = at;
    const next = levels[level + 1];
    if (next && next.parent === it.id) return;
    closeFrom(level + 1);
    const rows = under(it);
    if (!rows.length) { markTree(); return; }
    const panel = el("div", {
      class: "mp-fly mp-list", role: "menu",
      onmouseenter: () => clearTimeout(timer),
    });
    container.appendChild(panel);
    const anchor = rowsOf(level)[at];
    levels.push({ rows, cursor: -1, panel, anchor, parent: it.id });
    fill(level + 1);
    placeFly(level + 1);
    markTree();
  }

  function hover(level, at) {
    const it = levels[level].rows[at];
    depth = level;
    levels[level].cursor = at;
    markTree();
    showHint(it);
    clearTimeout(timer);
    // a pause before switching, so crossing a row on the way to an open
    // submenu does not close it
    const wait = levels.length > level + 1 ? 160 : 40;
    timer = setTimeout(() => {
      if (!levels[level] || levels[level].rows[at] !== it) return;
      if (under(it).length) expand(level, at);
      else { closeFrom(level + 1); markTree(); }
    }, wait);
  }

  function choose(level, at) {
    const it = levels[level].rows[at];
    if (!canPick(it)) {
      expand(level, at);
      if (levels.length > level + 1) { depth = level + 1; levels[depth].cursor = 0; }
      markTree();
      return;
    }
    pick(it.id);
  }

  /* Beside the row it opens from, held inside the window. A cascade keeps the
     side it started on, so a third menu never lands back on the first. */
  function placeFly(level) {
    const lv = levels[level];
    const { panel, anchor } = lv;
    const gap = 8;
    const parent = levels[level - 1].panel.getBoundingClientRect();
    const row = anchor.getBoundingClientRect();
    const width = Math.min(FLY_WIDTH, window.innerWidth - 2 * gap);
    const right = parent.right - 2;
    const leftward = parent.left - width + 2;
    const roomRight = right + width <= window.innerWidth - gap;
    const roomLeft = leftward >= gap;
    const side = (level > 1 && levels[level - 1].side) || "right";
    lv.side = side === "right" ? (roomRight || !roomLeft ? "right" : "left")
      : (roomLeft || !roomRight ? "left" : "right");
    let left = lv.side === "right" ? right : leftward;
    left = Math.max(gap, Math.min(left, window.innerWidth - width - gap));
    panel.style.width = width + "px";
    panel.style.left = left + "px";
    panel.style.maxHeight = (window.innerHeight - 2 * gap) + "px";
    const height = panel.getBoundingClientRect().height;
    const top = Math.min(row.top - 5, window.innerHeight - height - gap);
    panel.style.top = Math.max(gap, top) + "px";
  }

  function treeKey(e) {
    const lv = levels[depth];
    if (!lv) return false;
    const n = lv.rows.length;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      lv.cursor = e.key === "ArrowDown" ? Math.min(lv.cursor + 1, n - 1) : Math.max(lv.cursor - 1, 0);
      closeFrom(depth + 1);
      markTree();
      const row = rowsOf(depth)[lv.cursor];
      if (row) row.scrollIntoView({ block: "nearest" });
      showHint(lv.rows[lv.cursor]);
    } else if (e.key === "ArrowRight" && lv.cursor >= 0) {
      expand(depth, lv.cursor);
      if (levels.length > depth + 1) { depth += 1; levels[depth].cursor = 0; showHint(levels[depth].rows[0]); }
      markTree();
    } else if ((e.key === "ArrowLeft" || e.key === "Escape") && depth > 0) {
      closeFrom(depth);
      depth -= 1;
      markTree();
    } else if (e.key === "Enter" && lv.cursor >= 0) {
      choose(depth, lv.cursor);
    } else {
      return false;
    }
    e.preventDefault();
    return true;
  }

  // Closed after a pick: left open, the list covered the Apply button below it.
  function pick(id) {
    selected.add(id);
    query = "";
    search.value = "";
    cursor = 0;
    renderChips();
    setOpen(false);
    trigger.focus();
    if (opts.onPick) opts.onPick(id);
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
    const width = Math.min(Math.max(rect.width, tree ? 270 : 300), window.innerWidth - 2 * gap);
    const below = window.innerHeight - rect.bottom - gap;
    const above = rect.top - gap;
    const up = below < 240 && above > below;
    const room = Math.max(180, Math.min(tree ? 440 : 380, up ? above : below));

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
    // the rest of the popover is the search box, the family chips, the hint and the foot
    listEl.style.maxHeight = Math.max(110, room - (tree ? 170 : 110)) + "px";
  }

  const reposition = () => {
    if (!open) return;
    place();
    for (let level = 1; level < levels.length; level++) placeFly(level);
  };

  function setOpen(next) {
    open = next;
    pop.classList.toggle("hidden", !open);
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      openPickers.add(closeOnOutside);
      renderFamilies();
      render();
      place();
      // the popup it sits in scrolls, and the trigger moves with it
      window.addEventListener("scroll", reposition, true);
      window.addEventListener("resize", reposition);
      search.focus();
    } else {
      closeFrom(1);
      openPickers.delete(closeOnOutside);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    }
  }

  trigger.addEventListener("click", (e) => { e.stopPropagation(); setOpen(!open); });

  search.addEventListener("input", () => {
    query = search.value.trim().toLowerCase();
    cursor = 0;
    render();
  });

  search.addEventListener("keydown", (e) => {
    if (tree && !query && treeKey(e)) return;
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
