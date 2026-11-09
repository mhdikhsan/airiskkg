/* Entry for the user guide page: hash routing and rendering. The prose is in guide_content.js. */

import { api } from "./core/api.js";
import { $, $$, el } from "./core/dom.js";
import { MOTIF_SUFFIX, RISK_SUFFIX, describe, shortName } from "./lib/library_text.js";
import { motifPreview } from "./lib/motif_preview.js";
import {
  CONCEPTS, CONTACT, FOOTER, GLOSSARY, GUIDE_VERSION, HOME, KNOWLEDGE_GRAPHS, LIBRARY_PAGE, LIMITS, READING,
  RISK_REASONS, SECTIONS, STARTER_FINDINGS, STEPPER, TOUR, WALKTHROUGH, WORKBENCH,
} from "./guide_content.js";

let data = null;
const libraryState = { query: "", facets: {} };

const ICONS = {
  shape: "M3 4h5v5H3zM12 11h5v5h-5zM8 6.5h4V11",
  alert: "M10 3l7.5 13h-15zM10 8v4M10 14.4v.1",
  tag: "M3 3h6.5L17 10.500 10.500 17 3 9.500zM6.500 6.500v.1",
  shield: "M10 2.500l6 2.300v4.700c0 3.500-2.500 6.300-6 7.800-3.500-1.500-6-4.300-6-7.800V4.800z",
  link: "M8.500 11.500a3.500 3.500 0 0 0 5 0l2-2a3.500 3.500 0 0 0-5-5l-1 1M11.500 8.500a3.500 3.500 0 0 0-5 0l-2 2a3.500 3.500 0 0 0 5 5l1-1",
  book: "M3 4h5a2 2 0 0 1 2 2v10a1.600 1.600 0 0 0-1.600-1.600H3zM17 4h-5a2 2 0 0 0-2 2v10a1.600 1.600 0 0 1 1.600-1.600H17z",
};

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 20 20");
  svg.setAttribute("class", "g-icon");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[name]);
  svg.appendChild(path);
  return svg;
}

/* Inline markup from the content file, built as nodes so no prose reaches innerHTML. */
function rich(text) {
  const out = [];
  const markup = /\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[(.+?)\]\((.+?)\)/g;
  let last = 0;
  for (const m of text.matchAll(markup)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1]) out.push(el("strong", {}, m[1]));
    else if (m[2]) out.push(el("em", {}, m[2]));
    else if (m[3]) out.push(el("code", {}, m[3]));
    else out.push(el("a", { href: m[5] }, m[4]));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const para = (text, cls) => el("p", cls ? { class: cls } : {}, rich(text));
const localName = (iri) => String(iri).split(/[#/]/).pop();

function page(title, children) {
  return el("article", { class: "g-page" }, [el("h2", { class: "g-title" }, title), ...children]);
}

function section(heading, children) {
  return el("section", { class: "g-section" }, [el("h3", {}, heading), ...children]);
}

const card = (head, text) => el("div", { class: "g-card" }, [el("h4", {}, head), para(text)]);
const grid = (cards) => el("div", { class: "g-grid" }, cards);
const scroller = (table) => el("div", { class: "g-tablewrap" }, table);

function table(head, rows) {
  return scroller(el("table", { class: "g-table" }, [
    head ? el("thead", {}, el("tr", {}, head.map((h) => el("th", {}, h)))) : null,
    el("tbody", {}, rows.map((row) => el("tr", {}, row.map((cell) => el("td", {}, cell))))),
  ]));
}

// ---- counts, always read off the API ----

function uniqueControls() {
  const controls = new Map();
  data.library.riskPatterns.forEach((risk) => risk.controls.forEach((control) => {
    const id = localName(control.id);
    if (!controls.has(id)) controls.set(id, { ...control, id, suggestedBy: [] });
    controls.get(id).suggestedBy.push(risk.id);
  }));
  return [...controls.values()].sort((a, b) => a.label.localeCompare(b.label));
}

function countOf(key) {
  const { library, vocabulary } = data;
  const conditions = () => new Set(library.riskPatterns.flatMap((r) => r.conditions.map((c) => c.id))).size;
  const citations = () => new Set(library.motifs.flatMap((m) => m.derivedFrom
    .filter((ref) => localName(ref.id).startsWith("Cite_")).map((ref) => ref.id))).size;
  return {
    motifs: () => library.stats.motifs,
    riskPatterns: () => library.stats.riskPatterns,
    roles: () => vocabulary.roles.length,
    controls: () => library.stats.controls,
    dataCategories: () => vocabulary.dataCategories.length,
    taxonomyEntries: () => library.stats.taxonomyEntries,
    glossary: () => GLOSSARY.entries.length,
    conditions,
    citations,
  }[key]();
}

// ---- landing ----

function searchIndex() {
  const items = SECTIONS.map((s) => ({ label: s.title, kind: "Section", href: "#/" + s.id }));
  GLOSSARY.entries.forEach((e) => items.push({ label: e.term, kind: "Glossary", href: "#/glossary", text: e.text }));
  LIBRARY_PAGE.tabs.forEach((tab) => entriesOf(tab.kind).forEach((entry) => items.push({
    label: entry.name, kind: tab.label, href: `#/library/${tab.kind}/${entry.id}`, text: entry.text,
  })));
  return items;
}

function searchBox() {
  const results = el("ul", { class: "g-search-results hidden" });
  const index = searchIndex();
  const input = el("input", {
    type: "search", id: "guide-search", class: "g-input", placeholder: HOME.search, "aria-label": HOME.search,
    oninput: () => {
      const query = input.value.trim().toLowerCase();
      results.replaceChildren();
      results.classList.toggle("hidden", !query);
      if (!query) return;
      index.filter((i) => (i.label + " " + (i.text || "")).toLowerCase().includes(query)).slice(0, 12)
        .forEach((i) => results.appendChild(el("li", {}, el("a", { href: i.href }, [
          el("span", {}, i.label), el("span", { class: "g-muted" }, i.kind),
        ]))));
    },
  });
  return el("div", { class: "g-search" }, [input, el("kbd", {}, "/"), results]);
}

function readerMinutes(ids) {
  return SECTIONS.filter((s) => ids.includes(s.id)).reduce((sum, s) => sum + s.minutes, 0);
}

function home() {
  const flow = HOME.flow.map((step, i) => el("li", {}, el("a", { href: `#/walkthrough/${step.step}`, class: "g-chevron" }, [
    el("span", { class: "g-chevron-no" }, String(i + 1).padStart(2, "0")),
    el("strong", {}, step.name),
    el("span", {}, step.question),
    el("span", { class: "g-muted" }, step.output),
  ])));
  return el("article", { class: "g-home" }, [
    el("section", { class: "g-hero" }, [
      el("div", { class: "g-kicker" }, HOME.kicker),
      el("h2", {}, HOME.title),
      para(HOME.lead, "g-lead"),
      el("div", { class: "g-actions" }, [
        el("a", { class: "btn primary", href: HOME.primary.href }, HOME.primary.label),
        ...HOME.secondary.map((a) => el("a", { class: "btn", href: a.href }, a.label)),
      ]),
      searchBox(),
    ]),
    el("ul", { class: "g-strip" }, HOME.strip.map((s) => el("li", {}, [el("strong", {}, s.head), el("span", {}, s.text)]))),
    section(HOME.readersHead, [el("div", { class: "g-grid" }, HOME.readers.map((reader) => el("div", { class: "g-card" }, [
      el("h4", {}, reader.name),
      para(reader.text),
      el("ol", { class: "g-route" }, reader.sections.map((id) => {
        const s = SECTIONS.find((x) => x.id === id);
        return el("li", {}, el("a", { href: "#/" + id }, s.nav));
      })),
      el("p", { class: "g-muted" }, `${readerMinutes(reader.sections)} minutes of reading`),
    ])))]),
    section(HOME.flowHead, [el("ol", { class: "g-flow" }, flow)]),
    section(HOME.browseHead, [el("div", { class: "g-browse" }, HOME.tiles.map((tile) => el("a", { class: "g-tile", href: tile.href }, [
      icon(tile.icon),
      el("span", {}, [
        el("strong", {}, tile.question),
        el("span", { class: "g-muted" }, [el("span", { class: "g-count", "data-count": tile.count }, String(countOf(tile.count))), " " + tile.unit]),
      ]),
    ])))]),
    el("section", { class: "g-band" }, [
      el("div", {}, [el("h3", {}, HOME.band.head), para(HOME.band.text), el("a", { class: "btn primary", href: "/" }, HOME.band.action)]),
      el("ol", { class: "g-band-path" }, HOME.band.steps.map((s) => el("li", {}, rich(s)))),
    ]),
  ]);
}

// ---- tour ----

function stepper() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 720 300");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", STEPPER.aria);
  svg.setAttribute("class", "g-diagram");
  svg.innerHTML = STEPPER.svg;

  const caption = el("div", { class: "g-caption", "aria-live": "polite" });
  const prev = el("button", { type: "button", class: "btn small", onclick: () => show(current - 1) }, "Previous");
  const next = el("button", { type: "button", class: "btn small", onclick: () => show(current + 1) }, "Next");
  const tabs = STEPPER.steps.map((step, i) => el("button", {
    type: "button", role: "tab", class: "g-tab", onclick: () => show(i),
  }, `${i + 1} ${step.tab}`));
  let current = 0;

  function show(i) {
    current = i;
    const step = STEPPER.steps[i];
    svg.classList.toggle("show-roles", step.roles);
    svg.querySelectorAll(".n").forEach((n) => {
      n.classList.toggle("hi", step.hi.includes(n.dataset.k));
      n.classList.toggle("flag", step.flag.includes(n.dataset.k));
    });
    svg.querySelectorAll(".e").forEach((e) => {
      e.classList.toggle("hi", step.e.includes(e.dataset.k));
      e.classList.toggle("flag", step.e2.includes(e.dataset.k));
    });
    caption.replaceChildren(...rich(step.text));
    tabs.forEach((tab, j) => tab.setAttribute("aria-selected", j === i ? "true" : "false"));
    prev.disabled = i === 0;
    next.disabled = i === STEPPER.steps.length - 1;
  }
  show(0);

  return el("div", { class: "g-stepper" }, [
    el("div", { class: "g-tabs", role: "tablist" }, tabs),
    el("div", { class: "g-canvas" }, svg),
    caption,
    el("div", { class: "g-stepper-nav" }, [prev, next]),
  ]);
}

function reasonFor(row) {
  return (RISK_REASONS.find((r) => r.label === row.label && (!r.has || row.evidence.includes(r.has))) || {}).text || "";
}

function starterTable() {
  const body = el("div", {});
  const buttons = TOUR.scopes.map((scope) => el("button", {
    type: "button", class: "g-tab", "data-scope": scope.id, onclick: () => show(scope.id),
  }, scope.label));

  function show(id) {
    buttons.forEach((b) => b.setAttribute("aria-pressed", b.dataset.scope === id ? "true" : "false"));
    body.replaceChildren(table(TOUR.columns, STARTER_FINDINGS
      .filter((row) => row.scopes.includes(id))
      .map((row) => [row.label, reasonFor(row), row.evidence.join(", ")])));
    body.firstChild.dataset.scope = id;
  }
  show("full");
  return el("div", {}, [el("div", { class: "g-tabs" }, buttons), body]);
}

function tour() {
  return page(SECTIONS[0].title, [
    ...TOUR.intro.map((p) => para(p)),
    section(TOUR.conceptsHead, [grid(TOUR.concepts.map((c) => card(c.head, c.text)))]),
    para(TOUR.quick, "g-note"),
    section(TOUR.exampleHead, [para(TOUR.example), stepper()]),
    section(TOUR.resultHead, [para(TOUR.result), starterTable()]),
    section(TOUR.triageHead, [para(TOUR.triage)]),
  ]);
}

function concepts() {
  return page(SECTIONS[1].title, [
    para(CONCEPTS.intro),
    el("div", { class: "g-layers" }, CONCEPTS.levels.map((level) => el("div", { class: "g-layer " + level.kind }, [
      el("strong", {}, level.head), el("span", {}, rich(level.text)),
    ]))),
    section(CONCEPTS.howHead, [para(CONCEPTS.how)]),
    para(CONCEPTS.absence, "g-note"),
  ]);
}

function viewPanel(view) {
  if (view.rows) return table(null, view.rows.map(([name, text]) => [el("strong", {}, name), el("span", {}, rich(text))]));
  return el("div", {}, view.paragraphs.map((p) => para(p)));
}

function workbench() {
  const panel = el("div", { class: "g-panel" });
  const tabs = WORKBENCH.views.map((view) => el("button", {
    type: "button", role: "tab", class: "g-tab", onclick: () => show(view),
  }, view.tab));
  function show(view) {
    tabs.forEach((tab, i) => tab.setAttribute("aria-selected", WORKBENCH.views[i] === view ? "true" : "false"));
    panel.replaceChildren(viewPanel(view));
  }
  show(WORKBENCH.views[0]);
  return page(SECTIONS[2].title, [para(WORKBENCH.intro), el("div", { class: "g-tabs", role: "tablist" }, tabs), panel]);
}

function walkthrough(rest) {
  const wanted = Number(rest[0]) || 1;
  return page(SECTIONS[3].title, [
    para(WALKTHROUGH.intro),
    ...WALKTHROUGH.steps.map((step, i) => el("details", { class: "g-step", id: `step-${i + 1}`, ...(i + 1 === wanted ? { open: "" } : {}) }, [
      el("summary", {}, [
        el("span", { class: "g-step-no" }, String(i + 1).padStart(2, "0")),
        el("strong", {}, step.title),
        el("span", { class: "g-muted g-step-view" }, step.view),
      ]),
      el("div", { class: "g-step-body" }, [
        el("ol", {}, step.actions.map((a) => el("li", {}, rich(a)))),
        el("p", {}, [el("strong", {}, WALKTHROUGH.starterLabel + ". "), ...rich(step.starter)]),
        el("details", { class: "g-reflect" }, [
          el("summary", {}, [WALKTHROUGH.checkLabel + ": ", ...rich(step.question)]),
          para(step.answer),
        ]),
      ]),
    ])),
  ]);
}

function reading() {
  const risk = data.library.riskPatterns.find((r) => r.id === READING.riskPattern);
  const finding = STARTER_FINDINGS.find((row) => row.label === READING.evidenceLabel);
  const line = (label, value) => el("p", {}, [el("strong", {}, label + ": "), value]);
  return page(SECTIONS[4].title, [section(READING.exampleHead, [el("div", { class: "g-finding" }, [
    el("div", { class: "g-finding-title" }, "Candidate " + shortName(risk.label, RISK_SUFFIX).toLowerCase()),
    el("span", { class: "chip" }, "candidate"),
    line(READING.labels.condition, risk.conditions.map((c) => c.label).join("; ")),
    line(READING.labels.mechanism, `${risk.mechanism.label}. ${risk.mechanism.definition || ""}`),
    line(READING.labels.evidence, finding.evidence.join(", ")),
    line(READING.labels.controls, risk.controls.map((c) => c.label).join(", ")),
    line(READING.labels.taxonomy, risk.taxonomy.slice(0, 6).map((t) => t.label).join(", ")),
  ])])]);
}

function linkedEntries(key) {
  return key ? data.library.riskPatterns.flatMap((r) => r.taxonomy).filter((t) => t.sourceShort === key) : [];
}

function underTheHood() {
  const kg = KNOWLEDGE_GRAPHS;
  return page(SECTIONS[5].title, [
    para(kg.intro),
    el("div", { class: "g-pipe" }, kg.pipeline.map((step, i) => el("div", { class: "g-card" }, [
      el("h4", {}, `${i + 1} ${step.head}`), para(step.text),
    ]))),
    ...kg.blocks.map((block) => section(block.head, [para(block.text), el("pre", { class: "g-code" }, block.code)])),
    grid(kg.properties.map((c) => card(c.head, c.text))),
    section(kg.componentsHead, [para(kg.components), table(["Component", "Count", "Notes"], kg.componentRows.map((row) => [
      row.label, el("span", { class: "g-count", "data-count": row.count }, String(countOf(row.count))), row.note,
    ]))]),
    section(kg.taxonomiesHead, kg.taxonomies.map((t) => {
      const entries = new Map(linkedEntries(t.key).map((e) => [e.id, e]));
      return el("details", { class: "g-accordion" }, [
        el("summary", {}, t.name),
        el("div", {}, [
          para(t.text),
          el("p", {}, el("a", { href: t.url, target: "_blank", rel: "noopener noreferrer" }, t.url)),
          entries.size ? el("ul", { class: "g-entry-list" }, [...entries.values()].sort((a, b) => a.label.localeCompare(b.label)).map((e) => el("li", {}, e.url
            ? el("a", { href: e.url, target: "_blank", rel: "noopener noreferrer" }, e.label)
            : e.label))) : null,
        ]),
      ]);
    })),
    section(kg.sourcesHead, [table(null, kg.sources.map((s) => [
      el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, s.name), s.text,
    ]))]),
  ]);
}

// ---- library browser ----

function roleCategories() {
  const byId = new Map(data.vocabulary.roles.map((r) => [r.id, r]));
  const categoryOf = (role, seen = new Set()) => {
    for (const parent of [...(role.parents || [])].sort()) {
      if (seen.has(parent)) continue;
      seen.add(parent);
      const found = byId.get(parent);
      if (!found) continue;
      if (found.category) return found.label;
      const above = categoryOf(found, seen);
      if (above) return above;
    }
    return null;
  };
  return new Map(data.vocabulary.roles.map((r) => [localName(r.id), categoryOf(r)]));
}

function entriesOf(kind) {
  const { library } = data;
  if (kind === "risk") {
    return library.riskPatterns.map((r) => ({
      id: r.id, name: shortName(r.label, RISK_SUFFIX), text: describe(r).text,
      facets: { Family: r.family ? [r.family.label] : [], Taxonomy: [...new Set(r.taxonomy.map((t) => t.sourceShort))] },
    }));
  }
  if (kind === "motif") {
    return library.motifs.map((m) => ({
      id: m.id, name: shortName(m.label, MOTIF_SUFFIX), text: m.description || "",
      facets: { Family: m.family ? [m.family.label] : [], Group: m.group ? [m.group.label] : [] },
    }));
  }
  if (kind === "role") {
    const categories = data.roleCategories;
    return library.vocabulary.roles.map((r) => ({
      id: r.id, name: r.label, text: r.definition || "",
      facets: { Category: categories.get(r.id) ? [categories.get(r.id)] : [] },
    }));
  }
  if (kind === "category") {
    return library.vocabulary.dataCategories.map((c) => ({
      id: c.id, name: c.label, text: c.definition || "",
      facets: { Origin: [c.derived ? LIBRARY_PAGE.derived.yes : LIBRARY_PAGE.derived.no] },
    }));
  }
  return uniqueControls().map((c) => ({
    id: c.id, name: c.label, text: c.definition || "", facets: { Nature: c.nature ? [c.nature] : [] },
  }));
}

function versionLine() {
  const v = data.version;
  return el("p", { class: "g-muted g-version", id: "guide-library-version" },
    `${LIBRARY_PAGE.versionLabel} ${v.version}, fingerprint ${v.fingerprint}${v.dirty ? "+" : ""}, loaded ${v.loadedOn}`);
}

function libraryBrowser(kind) {
  const list = el("div", { class: "g-list" });
  const facetBox = el("div", { class: "g-facets" });
  const entries = entriesOf(kind);
  const chosen = libraryState.facets[kind] || (libraryState.facets[kind] = {});

  function draw() {
    const query = libraryState.query.toLowerCase();
    const shown = entries.filter((e) => (!query || (e.name + " " + e.text).toLowerCase().includes(query))
      && Object.entries(chosen).every(([facet, value]) => !value || e.facets[facet].includes(value)));
    list.replaceChildren(...(shown.length
      ? shown.map((e) => el("a", { class: "g-row", href: `#/library/${kind}/${e.id}` }, [
        el("strong", {}, e.name), el("span", { class: "g-muted" }, e.text),
      ]))
      : [el("p", { class: "g-muted" }, LIBRARY_PAGE.empty)]));
  }

  const names = [...new Set(entries.flatMap((e) => Object.keys(e.facets)))];
  names.forEach((facet) => {
    const values = [...new Set(entries.flatMap((e) => e.facets[facet]))].sort();
    if (values.length < 2) return;
    facetBox.appendChild(el("div", { class: "g-facet" }, [
      el("span", { class: "g-muted" }, facet),
      ...values.map((value) => {
        const chip = el("button", {
          type: "button", class: "g-chip", "aria-pressed": chosen[facet] === value ? "true" : "false",
          onclick: () => {
            chosen[facet] = chosen[facet] === value ? null : value;
            facetBox.querySelectorAll(`[data-facet="${facet}"]`).forEach((b) => b.setAttribute("aria-pressed", chosen[facet] === b.textContent ? "true" : "false"));
            draw();
          },
        }, value);
        chip.dataset.facet = facet;
        return chip;
      }),
    ]));
  });
  draw();

  return page(SECTIONS[6].title, [
    para(LIBRARY_PAGE.intro),
    el("div", { class: "g-tabs", role: "tablist" }, LIBRARY_PAGE.tabs.map((tab) => el("a", {
      class: "g-tab", role: "tab", href: `#/library/${tab.kind}`, "aria-selected": tab.kind === kind ? "true" : "false",
    }, [tab.label + " ", el("span", { class: "g-count", "data-tab": tab.kind }, String(entriesOf(tab.kind).length))]))),
    versionLine(),
    el("input", {
      type: "search", class: "g-input", placeholder: LIBRARY_PAGE.filter, "aria-label": LIBRARY_PAGE.filter, id: "guide-filter",
      value: libraryState.query,
      oninput: (ev) => { libraryState.query = ev.target.value; draw(); },
    }),
    facetBox,
    list,
  ]);
}

const entryLink = (kind, id, label) => el("a", { class: "g-link-chip", href: `#/library/${kind}/${id}` }, label);
const links = (items) => (items.length ? el("div", { class: "g-link-chips" }, items) : el("p", { class: "g-muted" }, LIBRARY_PAGE.none));
const outLink = (ref) => (ref.url
  ? el("a", { class: "g-link-chip", href: ref.url, target: "_blank", rel: "noopener noreferrer" }, ref.doi ? `${ref.label} (doi:${ref.doi})` : ref.label)
  : el("span", { class: "g-link-chip" }, ref.label));

function detailShell(name, kindLabel, target, panels) {
  const parts = LIBRARY_PAGE.headings;
  return el("article", { class: "g-page" }, [
    el("p", { class: "g-kicker" }, kindLabel),
    el("div", { class: "g-detail-head" }, [
      el("h2", { class: "g-title" }, name),
      el("a", { class: "btn primary", id: "guide-open-entry", href: "/?library=" + encodeURIComponent(target) }, LIBRARY_PAGE.openInWorkbench),
    ]),
    versionLine(),
    ...panels.filter(Boolean).map(([heading, body]) => section(parts[heading], [].concat(body))),
  ]);
}

const riskById = (id) => data.library.riskPatterns.find((r) => r.id === id);
const motifById = (id) => data.library.motifs.find((m) => m.id === id);
const motifLink = (id) => { const m = motifById(id); return m ? entryLink("motif", id, shortName(m.label, MOTIF_SUFFIX)) : null; };
const riskLink = (id) => { const r = riskById(id); return r ? entryLink("risk", id, shortName(r.label, RISK_SUFFIX)) : null; };

function riskPage(r) {
  const text = describe(r);
  return detailShell(shortName(r.label, RISK_SUFFIX), "AI risk pattern", `risk:${r.id}`, [
    text.text ? ["description", para(text.text)] : null,
    r.mechanism ? ["mechanism", [el("p", {}, el("strong", {}, r.mechanism.label)), para(r.mechanism.definition || "")]] : null,
    ["conditions", el("ul", {}, r.conditions.map((c) => el("li", {}, c.label)))],
    ["motifs", r.motifs.length ? links(r.motifs.map(motifLink).filter(Boolean)) : el("p", { class: "g-muted" }, LIBRARY_PAGE.noMotif)],
    ["controls", links(r.controls.map((c) => entryLink("control", localName(c.id), c.label)))],
    ["taxonomy", links(r.taxonomy.map(outLink))],
    ["source", links(r.derivedFrom.map(outLink))],
  ]);
}

function motifPage(m) {
  return detailShell(shortName(m.label, MOTIF_SUFFIX), "Motif", `motif:${m.id}`, [
    m.description ? ["description", para(m.description)] : null,
    ["structure", el("div", { class: "lib-preview large" }, motifPreview(m))],
    ["roles", links(m.roles.map((r) => entryLink("role", r.id, r.label)))],
    ["citations", links(m.derivedFrom.map(outLink))],
    ["riskPatterns", links(m.riskPatterns.map(riskLink).filter(Boolean))],
  ]);
}

function rolePage(r) {
  const children = data.library.vocabulary.roles.filter((c) => (c.refines || []).some((p) => p.id === r.id));
  return detailShell(r.label, "Role", `role:${r.id}`, [
    ["definition", para(r.definition || "")],
    ["parents", links((r.refines || []).map((p) => entryLink("role", p.id, p.label)))],
    ["children", links(children.map((c) => entryLink("role", c.id, c.label)))],
    ["usedBy", links((r.motifs || []).map(motifLink).filter(Boolean))],
  ]);
}

function categoryPage(c) {
  return detailShell(c.label, "Data category", "role", [
    ["definition", para(c.definition || "")],
    ["origin", para(c.derived ? LIBRARY_PAGE.derived.yes : LIBRARY_PAGE.derived.no)],
  ]);
}

function controlPage(c) {
  return detailShell(c.label, "Control", `risk:${c.suggestedBy[0]}`, [
    ["definition", para(c.definition || "")],
    c.nature ? ["nature", para(c.nature)] : null,
    ["suggestedBy", links(c.suggestedBy.map(riskLink).filter(Boolean))],
    ["realizedBy", links((c.realizedByMotifs || []).map(motifLink).filter(Boolean))],
  ]);
}

function libraryDetail(kind, id) {
  const { library } = data;
  if (kind === "risk") { const r = riskById(id); return r ? riskPage(r) : null; }
  if (kind === "motif") { const m = motifById(id); return m ? motifPage(m) : null; }
  if (kind === "role") { const r = library.vocabulary.roles.find((x) => x.id === id); return r ? rolePage(r) : null; }
  if (kind === "category") { const c = library.vocabulary.dataCategories.find((x) => x.id === id); return c ? categoryPage(c) : null; }
  if (kind === "control") { const c = uniqueControls().find((x) => x.id === id); return c ? controlPage(c) : null; }
  return null;
}

function library(rest) {
  const kind = LIBRARY_PAGE.tabs.some((t) => t.kind === rest[0]) ? rest[0] : "risk";
  return (rest[1] && libraryDetail(kind, rest[1])) || libraryBrowser(kind);
}

function limits() {
  return page(SECTIONS[7].title, [grid(LIMITS.cards.map((c) => card(c.head, c.text)))]);
}

function glossary() {
  const none = el("p", { class: "g-muted hidden" }, GLOSSARY.empty);
  const rows = GLOSSARY.entries.map((e) => el("div", { class: "g-gloss-row" }, [el("dt", {}, e.term), el("dd", {}, e.text)]));
  const input = el("input", {
    type: "search", id: "guide-glossary-filter", class: "g-input", placeholder: GLOSSARY.filter, "aria-label": GLOSSARY.filter,
    oninput: () => {
      const query = input.value.trim().toLowerCase();
      let shown = 0;
      rows.forEach((row) => {
        const hit = !query || row.textContent.toLowerCase().includes(query);
        row.classList.toggle("hidden", !hit);
        if (hit) shown += 1;
      });
      none.classList.toggle("hidden", shown > 0);
    },
  });
  return page(SECTIONS[8].title, [input, el("dl", { class: "g-gloss" }, rows), none]);
}

// ---- routing ----

const PAGES = {
  home, tour, concepts, workbench, walkthrough, reading, "under-the-hood": underTheHood, library, limits, glossary,
};

function route() {
  const [head, ...rest] = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (!PAGES[head]) {
    location.replace("#/home");
    return;
  }
  $("#guide-main").replaceChildren(PAGES[head](rest));
  $$("#guide-nav a").forEach((a) => a.classList.toggle("on", a.dataset.section === head));
  const section_ = SECTIONS.find((s) => s.id === head);
  document.title = section_ ? `${section_.nav}, PAIR-AI user guide` : "PAIR-AI user guide";
  window.scrollTo(0, 0);
}

function chrome() {
  $("#guide-nav").replaceChildren(...SECTIONS.map((s) => {
    const link = el("a", { href: "#/" + s.id }, s.nav);
    link.dataset.section = s.id;
    return link;
  }));
  $("#guide-contact").replaceChildren("Contact: ", el("a", { href: CONTACT.url, target: "_blank", rel: "noopener noreferrer" }, CONTACT.label));
  $("#guide-footer").textContent = `${FOOTER} Guide version ${GUIDE_VERSION}.`;
}

document.addEventListener("keydown", (ev) => {
  if (ev.key !== "/" || /^(INPUT|TEXTAREA)$/.test(ev.target.tagName)) return;
  const box = $("#guide-search");
  if (box) { ev.preventDefault(); box.focus(); }
});

async function boot() {
  chrome();
  const [lib, vocabulary, version] = await Promise.all([api("/api/library"), api("/api/vocabulary"), api("/api/kb-version")]);
  data = { library: lib, vocabulary, version };
  data.roleCategories = roleCategories();
  window.addEventListener("hashchange", route);
  route();
}

boot().catch((error) => {
  $("#guide-main").textContent = "The guide could not read the library: " + error.message;
});
