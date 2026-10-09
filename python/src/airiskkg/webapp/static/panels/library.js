/* The library */

import { api } from "../core/api.js";
import { on } from "../core/bus.js";
import { $, $$, el } from "../core/dom.js";
import { kindOf, motifPreview } from "../lib/motif_preview.js";
import { startDrawing } from "./canvas.js";
import { addMotif } from "./motifs.js";

let catalogue = null;
let tab = "risks";
let query = "";
let selected = { risks: null, motifs: null, terms: null };
let addedCount = 0;


const opened = { risks: new Set(), motifs: new Set(), terms: new Set() };

// Open as the front door, rather than opened deliberately from the toolbar.
let openingMode = false;

const byId = { risks: new Map(), motifs: new Map(), terms: new Map() };

// Motifs a control names as a candidate structural realization.
let controlMotifs = new Set();

const RISK_SUFFIX = /\s*risk pattern$/i;
const MOTIF_SUFFIX = /\s*Motif$/;

function shortName(label, suffix) {
  return label.replace(suffix, "").trim() || label;
}

/* Not every risk pattern carries a description of its own. */
function describe(entry) {
  if (entry.description) return { text: entry.description, from: null };

  const source = (entry.derivedFrom || []).find((ref) => ref.definition);

  return source
    ? { text: source.definition, from: source.label }
    : { text: "", from: null };
}

function haystack(entry) {
  return [
    entry.label,
    entry.description || "",
    entry.definition || "",
    entry.shelf || "",
    entry.family && entry.family.label ? entry.family.label : "",
    entry.group && entry.group.label ? entry.group.label : "",
    ...(entry.derivedFrom || []).map((d) => d.label),
    ...(entry.taxonomy || []).map((t) => t.label + " " + t.sourceShort),
    ...(entry.roles || []).map((r) => r.label),
    ...(entry.controls || []).map((c) => c.label),
    ...(entry.refines || []).map((r) => r.label),
    ...(entry.families || []),
    ...(entry.motifs || []),
  ].join(" ").toLowerCase();
}

function hits(entry) {
  return !query || haystack(entry).includes(query);
}

function entriesOf(kind) {
  if (kind === "risks") return catalogue.riskPatterns;
  if (kind === "motifs") return catalogue.motifs;
  return catalogue.vocabulary.roles;
}


// ---- the rail ----

/* Risk patterns and motifs both shelve by the family of AI system; a risk
   pattern files where most of the motifs it applies to belong. */
function groupsOfMotifs(entries) {
  const groups = new Map();

  entries.forEach((entry) => {
    const name = entry.family
      ? entry.family.label
      : "Unshelved";

    if (!groups.has(name)) {
      groups.set(name, []);
    }

    groups.get(name).push(entry);
  });

  return [...groups.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]));
}

/* Inside a family, the motifs that are variants or companions of each other sit
   together: the retrieval shapes, the RAG loops, the guardrails. */
function groupsWithin(entries) {
  const groups = new Map();
  entries.forEach((entry) => {
    const name = entry.group ? entry.group.label : "Other";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(entry);
  });
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

// A family filed as one group says nothing more under a second heading.
function groupHeadingsShown(groups) {
  return groups.length > 1;
}


/* Terms shelve by the BEAM class they go on. The role hierarchy's four
   top-level terms cannot shelve them: half of the 97 sit under one of them. */
function groupsOfTerms(entries) {
  const groups = new Map();

  entries.forEach((entry) => {
    const name = entry.shelf || "Unshelved";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(entry);
  });

  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

/* A term is read by a query wherever it, or a term it refines, is named on a
   pattern node - so "nothing" has to mean both, or it would read as inert. */
function termReach(entry) {
  const direct = (entry.motifs || []).length;
  const inherited = (entry.serves || []).length;

  if (direct) {
    return direct + " motif" + (direct > 1 ? "s" : "") + " ask for it by name";
  }
  if (inherited) {
    return "serves " + inherited + " motif" + (inherited > 1 ? "s" : "")
      + " through the term it refines";
  }
  return "no motif in the library reads it";
}

function termRow(entry) {
  const row = el("button", {
    type: "button",
    class: "lib-row" + (selected.terms === entry.id ? " selected" : ""),
    title: entry.label + " - goes on a " + (entry.shelf || "?") + "; " + termReach(entry),
  }, [
    el("span", { class: "lib-row-name" }, entry.label),
    el("span", {
      class: "lib-row-count" + ((entry.motifs || []).length ? "" : " zero"),
    }, String((entry.motifs || []).length)),
  ]);

  row.addEventListener("click", () => select("terms", entry.id));
  return row;
}

/* How many risk patterns apply to a motif. A control structure carries none by
   design, so it is marked as a control rather than counted as a zero. */
function motifRiskCount(entry) {
  if (entry.control && !entry.riskPatterns.length) {
    return el("span", {
      class: "lib-row-count control",
      title: "A control: it realizes a control rather than carrying a risk pattern",
    }, "control");
  }
  return el(
    "span",
    {
      class:
        "lib-row-count"
        + (entry.riskPatterns.length ? "" : " zero"),
    },
    String(entry.riskPatterns.length)
  );
}

function suggestedAgainst(entry) {
  return [...new Set((entry.controls || []).flatMap((control) => control.suggestedBy || []))];
}

function railRow(entry, kind) {
  const isRisk = kind === "risks";

  const name = shortName(
    entry.label,
    isRisk ? RISK_SUFFIX : MOTIF_SUFFIX
  );

  const row = el(
    "button",
    {
      type: "button",

      class:
        "lib-row"
        + (selected[kind] === entry.id ? " selected" : ""),

      title: isRisk
        ? entry.label
          + " - "
          + (
              entry.motifs.length
                ? entry.motifs.length + " motif(s) it applies to"
                : "applies over any matched motif"
            )

        : entry.label
          + " - "
          + entry.nodes.length
          + " elements, "
          + entry.edges.length
          + " relations, "
          + (
              entry.riskPatterns.length
                ? entry.riskPatterns.length
                  + " risk pattern(s) apply to it"
                : entry.control
                  ? "a control, suggested against "
                    + suggestedAgainst(entry).length
                    + " risk pattern(s)"
                  : "no risk pattern in the library applies to it"
            )
          + (
              controlMotifs.has(entry.id) && !entry.control
                ? "; a control can be realized by it"
                : ""
            ),
    },

    [
      el(
        "span",
        { class: "lib-row-name" },
        name
      ),

      isRisk
        ? el(
            "span",
            { class: "lib-row-count" },
            String(entry.motifs.length || "any")
          )
        : motifRiskCount(entry),
    ]
  );

  row.addEventListener(
    "click",
    () => select(kind, entry.id)
  );

  return row;
}

function renderRail() {
  const list = $("#library-list");

  list.innerHTML = "";

  const entries = entriesOf(tab).filter(hits);

  if (!entries.length) {
    list.appendChild(
      el(
        "p",
        { class: "lib-empty" },
        "Nothing in the library matches that."
      )
    );

    return;
  }

  const groups = tab === "terms" ? groupsOfTerms(entries) : groupsOfMotifs(entries);
  const open = opened[tab];

  groups.forEach(([name, items]) => {
    // A search that matched inside a folded group would otherwise find nothing.
    const isOpen = open.has(name) || Boolean(query);

    const head = el("button", {
      type: "button",
      class: "lib-group" + (isOpen ? "" : " shut"),
      "aria-expanded": isOpen ? "true" : "false",
      title: isOpen ? "Hide " + name : "Show " + name,
    }, [
      el("span", { class: "lib-group-mark" }),
      el("span", { class: "lib-group-name" }, name),
      el("span", { class: "lib-group-count" }, String(items.length)),
    ]);
    head.addEventListener("click", () => {
      if (open.has(name)) open.delete(name);
      else open.add(name);
      renderRail();
    });
    list.appendChild(head);

    if (!isOpen) return;
    if (tab === "terms") {
      items.forEach((entry) => list.appendChild(termRow(entry)));
      return;
    }
    // Risk patterns have no groups inside a family.
    if (tab === "risks") {
      items.forEach((entry) => list.appendChild(railRow(entry, tab)));
      return;
    }
    const within = groupsWithin(items);
    const showHeads = groupHeadingsShown(within);
     within.forEach(([groupName, members]) => {
      const rows = members.map((entry) => railRow(entry, tab));

      if (!showHeads) {
        rows.forEach((row) => list.appendChild(row));
        return;
      }

      const definition = members[0].group && members[0].group.definition;

      list.appendChild(el("div", { class: "lib-subgroup" }, [
        el("div", { class: "lib-subgroup-head", title: definition || groupName }, [
          el("span", { class: "lib-subgroup-name" }, groupName),
          el("span", { class: "lib-subgroup-count" }, String(members.length)),
        ]),
        el("div", { class: "lib-subgroup-items" }, rows),
      ]));
    });
  });
}


// ---- the detail ----

function refChip(ref, extraClass) {
  // "Other" is not a catalogue. A published pattern page is named by its host
  // and linked; only a real catalogue gets a source prefix.

  const body = [
    ref.sourceShort === "Other"
      ? null
      : el(
          "span",
          { class: ref.doi ? "chip-source doi" : "chip-source" },
          ref.doi ? "doi:" + ref.doi : ref.sourceShort
        ),

    el("span", {}, ref.label),
  ].filter(Boolean);

  const title =
    ref.source
    + String.fromCharCode(10)
    + (ref.definition || ref.id);

  const cls =
    "chip "
    + (extraClass || "");

  if (ref.url) {
    return el(
      "a",
      {
        class: cls,
        href: ref.url,
        target: "_blank",
        rel: "noopener noreferrer",
        title,
      },
      body
    );
  }

  return el(
    "span",
    {
      class: cls,
      title,
    },
    body
  );
}

// ---- the detail pages ----

/* One shape for every detail page: a hero that says what this is, then a main
 * column and an aside. The structure sits on the left and the aside reads down
 * the rest of the constituent equation - mechanism, what it may lead to,
 * controls. */

const BACK_LABEL = {
  risks: "All risk patterns",
  motifs: "All motifs",
  terms: "All terms",
};

function backButton() {
  return el("button", {
    type: "button",
    class: "btn lib-back",
    title: "Back to the whole catalogue",
    onclick: () => {
      selected[tab] = null;
      renderRail();
      renderDetail();
    },
  }, [el("span", { class: "lib-back-arrow" }), BACK_LABEL[tab]]);
}

function plural(count, one, many) {
  return count === 1 ? one : many;
}

function statStrip(stats) {
  return el("div", { class: "lib-stats" }, stats.map(([value, label]) =>
    el("div", { class: "lib-stat" }, [
      el("span", { class: "lib-stat-value" }, String(value)),
      el("span", { class: "lib-stat-label" }, label),
    ])));
}

function hero({ eyebrow, title, mark, meta, lede, actions, stats }) {
  return el("header", { class: "lib-hero" }, [
    el("div", { class: "lib-hero-top" }, [
      el("span", { class: "lib-eyebrow" }, eyebrow),
      el("div", { class: "lib-hero-actions" }, [...(actions || []), backButton()]),
    ]),
    el("h2", { class: "lib-hero-title" }, [mark || null, el("span", {}, title)]),
    meta && meta.length ? el("div", { class: "lib-hero-meta" }, meta) : null,
    lede || null,
    stats && stats.length ? statStrip(stats) : null,
  ]);
}

// One line at most under a heading; anything longer goes on the heading's tip.
function panel(title, { count, hint, tip, body } = {}) {
  return el("section", { class: "lib-panel" }, [
    el("div", { class: "lib-panel-head", title: tip || "" }, [
      el("h3", {}, title),
      count ? el("span", { class: "lib-panel-count" }, String(count)) : null,
    ]),
    hint ? el("p", { class: "lib-panel-hint" }, hint) : null,
    el("div", { class: "lib-panel-body" }, [].concat(body).filter(Boolean)),
  ]);
}

/* `lead` is the panel a reader needs before anything else: it heads the aside
 * on a wide screen and the whole page on a narrow one, where an aside stacked
 * under the main column would put it below every diagram. */
function layout(main, aside, lead) {
  return el("div", { class: "lib-layout" + (lead ? " has-lead" : "") }, [
    lead ? el("div", { class: "lib-lead" }, [lead]) : null,
    el("div", { class: "lib-main" }, main.filter(Boolean)),
    el("aside", { class: "lib-aside" }, aside.filter(Boolean)),
  ]);
}

function emptyLine(text) {
  return el("p", { class: "lib-empty-line" }, text);
}

function lede(entry) {
  const told = describe(entry);
  if (!told.text) return null;
  return el("p", { class: "lib-lede" + (told.from ? " borrowed" : "") }, [
    told.from ? el("span", { class: "lib-from" }, told.from + " — ") : null,
    el("span", {}, told.text),
  ]);
}

// OWASP is a source beside the name, never a category.
function sourceMeta(entry) {
  const refs = entry.derivedFrom || [];
  return refs.length
    ? [el("span", { class: "lib-meta-lead" }, "source"), ...refs.map((ref) => refChip(ref, "tax"))]
    : [];
}

function chipTo(kind, entry, suffix, extraClass) {
  return el("button", {
    type: "button",
    class: "chip clickable " + (extraClass || "tax"),
    title: entry.description || entry.label,
    onclick: () => select(kind, entry.id),
  }, shortName(entry.label, suffix));
}

/* The canvas's own shapes and colours, so a step is told apart from what flows
 * between steps without anyone saying so. */
const KIND_NAME = {
  data: "Data",
  symbol: "Symbol",
  model: "Model",
  resource: "Resource",
  process: "Process",
  agent: "Agent",
  other: "Untyped",
};

function swatch(kind) {
  return el("span", { class: "lib-swatch " + kind, title: KIND_NAME[kind] || kind });
}

function legend(template) {
  const kinds = [...new Set((template.nodes || []).map((node) => kindOf(node.cls)))];
  return el("div", { class: "lib-legend" }, kinds.map((kind) =>
    el("span", { class: "lib-legend-item" }, [swatch(kind), KIND_NAME[kind] || kind])));
}

/* On a risk page, whether the motif raises the risk by itself or only once its
   elements carry the context named here, which inserting it then adds. */
function carriesLine(motif, risk) {
  if (!risk) return null;
  const needs = (risk.motifContext || {})[motif.id] || [];
  if (!needs.length) {
    return el("p", { class: "lib-carries carried" }, "Raises this risk pattern by itself.");
  }
  return el("div", { class: "lib-carries" }, [
    el("span", { class: "lib-meta-lead" }, "raises it when"),
    el("ul", { class: "lib-when-list" }, needs.map((need) => el("li", {}, need))),
  ]);
}

function motifCard(motif, risk) {
  return el("div", { class: "lib-card" }, [
    el("div", { class: "lib-card-head" }, [
      el("strong", {}, shortName(motif.label, MOTIF_SUFFIX)),
      motif.family ? el("span", { class: "chip family" }, motif.family.label) : null,
      el("span", { class: "lib-card-size" },
        motif.nodes.length + " elements · " + motif.edges.length + " relations"),
    ]),
    el("div", { class: "lib-preview" }, motifPreview(motif)),
    carriesLine(motif, risk),
    el("div", { class: "lib-card-foot" }, [
      motif.roles.length
        ? el("div", { class: "lib-roles" }, [
            el("span", { class: "lib-meta-lead" }, "matches on"),
            ...motif.roles.map((role) => el("span", { class: "chip role" }, role.label)),
          ])
        : el("span"),
      el("div", { class: "lib-card-actions" }, [
        el("button", {
          type: "button",
          class: "btn small",
          title: "Read this motif on its own",
          onclick: () => select("motifs", motif.id),
        }, "Open motif"),
        el("button", {
          type: "button",
          class: "btn small primary",
          title: risk && ((risk.motifContext || {})[motif.id] || []).length
            ? "Add this motif's elements to the graph, with the context that raises this risk pattern"
            : "Add this motif's elements to the graph, already annotated with the roles it matches on",
          onclick: () => insertMotif(motif, risk),
        }, "Add to canvas"),
      ]),
    ]),
  ]);
}

function riskDetail(entry) {
  const motifs = entry.motifs.map((id) => byId.motifs.get(id)).filter(Boolean);
  const domains = entry.riskDomains || [];

  return [
    hero({
      eyebrow: "Risk pattern",
      title: shortName(entry.label, RISK_SUFFIX),
      meta: sourceMeta(entry),
      lede: lede(entry),
      stats: [
        [motifs.length || "any", motifs.length > 1 ? "structures" : "structure"],
        [domains.length, plural(domains.length, "domain of harm", "domains of harm")],
        [entry.controls.length, plural(entry.controls.length, "suggested control", "suggested controls")],
      ],
    }),
    layout(
      [
        panel("Structures it applies to", {
          count: motifs.length,
          hint: motifs.length ? " " : null,
          body: motifs.length
            ? motifs.map((motif) => motifCard(motif, entry))
            : emptyLine("Names no motif of its own: evaluated over any motif match whose conditions hold."),
        }),
      ],
      [harmPanel(entry), controlsPanel(entry)],
      mechanismPanel(entry),
    ),
  ];
}

/* The mechanism and the conditions that raise it, read as one thing: how this
 * weakness becomes a candidate finding. */
function mechanismPanel(entry) {
  const mechanism = entry.mechanism;
  const conditions = entry.conditions || [];

  return panel("Risk mechanism", {
    tip: "Curated and carried by reference, so the same explanation reproduces on every system.",
    body: [
      mechanism ? el("div", { class: "lib-chips" }, [refChip(mechanism, "mech")]) : null,
      mechanism && mechanism.definition
        ? el("p", { class: "lib-mech-text" }, mechanism.definition)
        : null,
      conditions.length
        ? el("div", { class: "lib-mech-when" }, [
            el("span", { class: "lib-meta-lead" }, "raised when"),
            el("ul", { class: "lib-when-list" }, conditions.map((condition) =>
              el("li", { title: condition.definition || condition.id }, condition.label))),
          ])
        : null,
    ],
  });
}

/* Grouped by the domain each entry rolls up to, so a reader sees which link
 * produced which domain. An entry rolling up to nothing is a citation, not an
 * outcome, and is listed apart. */
function harmPanel(entry) {
  const byDomain = new Map();
  const alsoCalled = [];

  entry.taxonomy.forEach((ref) => {
    if (!ref.domain) {
      alsoCalled.push(ref);
      return;
    }
    if (!byDomain.has(ref.domain)) byDomain.set(ref.domain, []);
    byDomain.get(ref.domain).push(ref);
  });

  const body = [...byDomain.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([domain, refs]) => el("div", { class: "lib-domain" }, [
      el("span", { class: "chip domain" }, domain),
      el("div", { class: "lib-chips" }, refs.map((ref) => refChip(ref, "tax"))),
    ]));

  if (!byDomain.size) {
    body.push(el("span", {
      class: "chip domain none",
      title: "Nothing upstream maps this pattern to a domain of harm, and writing that link here would be curation with no source.",
    }, "no risk domain linked"));
  }

  if (alsoCalled.length) {
    body.push(el("div", { class: "lib-domain also" }, [
      el("span", { class: "lib-meta-lead" }, "also catalogued as"),
      el("div", { class: "lib-chips" }, alsoCalled.map((ref) => refChip(ref, "tax"))),
    ]));
  }

  return panel("May lead to", {
    hint: "Possible harm, never an observed outcome.",
    body: el("div", { class: "lib-harm" }, body),
  });
}

function controlItem(control) {
  const realizing = (control.realizedByMotifs || [])
    .map((id) => byId.motifs.get(id))
    .filter(Boolean);

  return el("div", { class: "lib-control", title: control.definition || "" }, [
    el("div", { class: "lib-control-head" }, [
      el("span", { class: "lib-control-name" }, control.label),
      control.nature ? el("span", { class: "ctrl-nature " + control.nature }, control.nature) : null,
    ]),
    realizing.length
      ? el("div", { class: "lib-control-motifs" }, [
          el("span", { class: "lib-meta-lead" }, "candidate structure"),
          ...realizing.map((motif) => chipTo("motifs", motif, MOTIF_SUFFIX, "motif-suggest")),
        ])
      : null,
  ]);
}

function controlsPanel(entry) {
  return panel("Suggested controls", {
    count: entry.controls.length,
    hint: "Candidates, not proof the risk is removed.",
    body: entry.controls.length
      ? el("div", { class: "lib-controls" }, entry.controls.map(controlItem))
      : emptyLine("None suggested."),
  });
}

/* A control the motif realizes, with the risk patterns that suggest it: the
   link runs through the control, so the page says which control it is. */
function realizedControlItem(control) {
  const against = (control.suggestedBy || []).map((id) => byId.risks.get(id)).filter(Boolean);
  return el("div", { class: "lib-control", title: control.definition || "" }, [
    el("div", { class: "lib-control-head" }, [
      el("span", { class: "lib-control-name" }, control.label),
      control.nature ? el("span", { class: "ctrl-nature " + control.nature }, control.nature) : null,
    ]),
    against.length
      ? el("div", { class: "lib-control-motifs" }, [
          el("span", { class: "lib-meta-lead" }, "suggested against"),
          ...against.map((risk) => chipTo("risks", risk, RISK_SUFFIX)),
        ])
      : null,
  ]);
}

function realizedControlsPanel(entry) {
  const controls = entry.controls || [];
  return panel("Realizes a control", {
    count: controls.length,
    hint: "A candidate structure, not proof the risk is removed.",
    body: el("div", { class: "lib-controls" }, controls.map(realizedControlItem)),
  });
}

/* The motifs filed with this one, drawn as silhouettes: the variants of a shape
   read as variants only side by side. */
function relatedMotifsPanel(entry) {
  if (!entry.group) return null;
  const siblings = catalogue.motifs.filter((motif) =>
    motif.id !== entry.id && motif.group && motif.group.id === entry.group.id);
  if (!siblings.length) return null;
  return panel("Related motifs", {
    count: siblings.length,
    tip: entry.group.definition || "",
    body: el("div", { class: "lib-uses" }, siblings.map((motif) => usageCard(motif, [], false))),
  });
}

function motifDetail(entry) {
  const risks = entry.riskPatterns.map((id) => byId.risks.get(id)).filter(Boolean);
  const controls = entry.controls || [];
  // A control structure is what clears risk patterns, never what raises them.
  const asControl = entry.control && !risks.length;
  const against = suggestedAgainst(entry);

  return [
    hero({
      eyebrow: asControl ? "Control motif" : "Motif",
      title: shortName(entry.label, MOTIF_SUFFIX),
      meta: [
        entry.family
          ? el("span", { class: "chip family", title: entry.family.definition || "" }, entry.family.label)
          : null,
        entry.group
          ? el("span", { class: "chip group", title: entry.group.definition || "" }, entry.group.label)
          : null,
        ...sourceMeta(entry),
      ].filter(Boolean),
      lede: lede(entry),
      actions: [el("button", {
        type: "button",
        class: "btn primary",
        title: "Add this motif's elements to the graph, already annotated with the roles it matches on",
        onclick: () => insertMotif(entry),
      }, "Add to canvas")],
      stats: asControl
        ? [
            [entry.nodes.length, plural(entry.nodes.length, "element", "elements")],
            [controls.length, plural(controls.length, "control realized", "controls realized")],
            [against.length, "suggested against"],
          ]
        : [
            [entry.nodes.length, plural(entry.nodes.length, "element", "elements")],
            [entry.edges.length, plural(entry.edges.length, "relation", "relations")],
            [risks.length, plural(risks.length, "risk pattern", "risk patterns")],
          ],
    }),
    layout(
      [
        panel("Structure", {
          tip: "Drawn from the motif's own declaration.",
          body: [
            legend(entry),
            el("div", { class: "lib-preview large" }, motifPreview(entry)),
            entry.roles.length
              ? el("div", { class: "lib-roles" }, [
                  el("span", { class: "lib-meta-lead" }, "matches on"),
                  ...entry.roles.map((role) => el("button", {
                    type: "button",
                    class: "chip role clickable",
                    title: "Open this term",
                    onclick: () => select("terms", role.id),
                  }, role.label)),
                ])
              : null,
          ],
        }),
        relatedMotifsPanel(entry),
      ],
      asControl
        ? [realizedControlsPanel(entry)]
        : [
            panel("Risk patterns that apply", {
              count: risks.length,
              hint: risks.length ? "A match alone is not a finding." : null,
              body: risks.length
                ? el("div", { class: "lib-chips" }, risks.map((risk) => chipTo("risks", risk, RISK_SUFFIX)))
                : emptyLine("None on its own; it can still sit inside a larger match."),
            }),
            controls.length ? realizedControlsPanel(entry) : null,
          ],
    ),
  ];
}

/* What a pattern may lead to, on a card: the domains of harm the entries it may
 * indicate roll up to. Reported, not used to file the card - one pattern
 * reaches several, and none of them is its category. */
function domainRow(entry) {
  const domains = entry.riskDomains || [];

  if (!domains.length) {
    return el(
      "div",
      { class: "lib-tile-domains" },
      [
        el(
          "span",
          {
            class: "chip domain none",
            title:
              "Nothing upstream maps this pattern to a domain of harm, and "
              + "writing that link here would be curation with no source.",
          },
          "no risk domain linked"
        ),
      ]
    );
  }

  return el(
    "div",
    { class: "lib-tile-domains" },
    [
      el(
        "span",
        { class: "lib-roles-lead" },
        "may lead to"
      ),

      ...domains.map((domain) =>
        el(
          "span",
          {
            class: "chip domain",
            title: domain.definition || "",
          },
          domain.label
        )
      ),
    ]
  );
}


// Motif Shelf head
function motifShelfHead(name, count, definition) {
  return el("div", { class: "lib-shelf lib-motif-shelf" }, [
    el("h4", {}, name),
    el("span", { class: "lib-shelf-count" }, String(count)),
    definition
      ? el("p", { class: "lib-note lib-motif-shelf-note" }, definition)
      : null,
  ]);
}

/* The vocabulary drawn in the notation it annotates: each shelf carries the
 * canvas's own shape and colour for its class, and so does every term on it. */
function shelfHead(name, count) {
  return el("div", { class: "lib-shelf" }, [
    swatch(shelfKind(name)),
    el("h4", {}, name),
    el("span", { class: "lib-shelf-count" }, String(count)),
  ]);
}


function termKind(entry) {
  return entry && entry.shelfId ? kindOf(entry.shelfId.split(/[#/]/).pop()) : "other";
}

function shelfKind(name) {
  return termKind((catalogue.vocabulary.roles || []).find((role) => role.shelf === name));
}

/* How much of the library reads this term. A count, not a gauge: a four-segment
   bar that tops out at four reads as decoration and cannot say which of the two
   ways a term is reached. */
function usageBadge(entry) {
  const direct = (entry.motifs || []).length;
  const inherited = (entry.serves || []).length;
  if (!direct && !inherited) {
    return el("span", { class: "lib-term-uses none", title: termReach(entry) }, "unread");
  }
  return el("span", {
    class: "lib-term-uses" + (direct ? "" : " indirect"),
    title: termReach(entry),
  }, String(direct || inherited));
}

function termTile(entry) {
  // Quiet means no motif reaches it at all, not that no pattern node names it:
  // 14 terms are read only through the term they refine and are in full use.
  const unread = !(entry.motifs || []).length && !(entry.serves || []).length;
  return el("button", {
    type: "button",
    class: `lib-term ${termKind(entry)}` + (unread ? " quiet" : ""),
    title: termReach(entry),
    onclick: () => select("terms", entry.id),
  }, [
    el("span", { class: "lib-term-head" }, [
      el("span", { class: "lib-term-name" }, entry.label),
      usageBadge(entry),
    ]),
    entry.definition ? el("span", { class: "lib-term-def" }, entry.definition) : null,
    (entry.families || []).length
      ? el("span", { class: "lib-term-fams" }, entry.families.map((family) =>
          el("span", {
            class: "lib-fam-dot " + family.replace(/\W+/g, "-").toLowerCase(),
            title: family,
          })))
      : null,
  ]);
}

function ancestorsOf(entry) {
  const found = new Set();
  const queue = (entry.refines || []).map((parent) => parent.id);
  while (queue.length) {
    const id = queue.shift();
    if (found.has(id)) continue;
    found.add(id);
    const parent = byId.terms.get(id);
    if (parent) queue.push(...(parent.refines || []).map((p) => p.id));
  }
  return found;
}

/* One structure that reads this term, drawn with the element it would annotate
 * marked. Dashed when it is reached through a term this one refines. */
function usageCard(motif, highlight, inherited) {
  return el("button", {
    type: "button",
    class: "lib-use" + (inherited ? " inherited" : ""),
    title: (inherited ? "Reached through the term it refines: " : "Names this term: ") + motif.label,
    onclick: () => select("motifs", motif.id),
  }, [
    el("span", { class: "lib-use-name" }, shortName(motif.label, MOTIF_SUFFIX)),
    el("span", { class: "lib-use-shape" }, motifPreview(motif, { highlight })),
  ]);
}

/* R6's three routes, named rather than flattened: a term introduced to refine
 * another is grounded by the term it specializes, which is not the same claim
 * as having cited a source of its own. */
const PROVENANCE_LEAD = {
  stated: "cites",
  mapped: "mapped to",
  inherited: "grounded through",
};

// Hidden until the role mappings are reviewed: several point at a source that
// does not match the term's name. The API still serves provenance.
const SHOW_TERM_PROVENANCE = false;

function termDetail(entry) {
  const asked = (entry.motifs || []).map((id) => byId.motifs.get(id)).filter(Boolean);
  const served = (entry.serves || []).map((id) => byId.motifs.get(id)).filter(Boolean);
  const risks = (entry.riskPatterns || []).map((id) => byId.risks.get(id)).filter(Boolean);
  const controlFor = (entry.controlFor || []).map((id) => byId.risks.get(id)).filter(Boolean);
  const lineage = [...ancestorsOf(entry)];
  const provenance = entry.provenance || { route: null, refs: [] };

  const uses = [
    ...asked.map((motif) => usageCard(motif, [entry.id], false)),
    ...served.map((motif) => usageCard(motif, lineage, true)),
  ];

  return [
    hero({
      eyebrow: "Annotation term",
      title: entry.label,
      mark: swatch(termKind(entry)),
      meta: [
        entry.shelf
          ? el("span", { class: "chip family", title: "The BEAM class this term is annotated on" },
              "goes on " + entry.shelf)
          : null,
        ...(entry.families || []).map((family) => el("span", { class: "chip" }, family)),
      ].filter(Boolean),
      lede: entry.definition ? el("p", { class: "lib-lede" }, entry.definition) : null,
      stats: [
        [asked.length, plural(asked.length, "motif names it", "motifs name it")],
        [served.length, "reached by refining"],
        risks.length || !controlFor.length
          ? [risks.length, plural(risks.length, "risk pattern", "risk patterns")]
          : [controlFor.length, "suggested against"],
      ],
    }),
    layout(
      [
        panel("Related motifs", {
          count: uses.length,
          tip: "Every motif that reads this term, with the element it would annotate marked.",
          body: uses.length
            ? el("div", { class: "lib-uses" }, uses)
            : emptyLine("No motif in the library reads this term."),
        }),
      ],
      [
        (entry.refines || []).length
          ? panel("Refines", {
              tip: "A term that refines another is read wherever the term above it is.",
              body: el("div", { class: "lib-chips" }, entry.refines.map((parent) =>
                el("button", {
                  type: "button",
                  class: "chip clickable",
                  onclick: () => select("terms", parent.id),
                }, parent.label))),
            })
          : null,
        // Related, not raised: a term can be what a risk pattern needs, or a
        // step its query accepts as the escape.
        risks.length || !controlFor.length
          ? panel("Related risk patterns", {
              count: risks.length,
              tip: "Carried by a motif that names this term. The term may be what the risk pattern needs, or what clears it.",
              body: risks.length
                ? el("div", { class: "lib-chips" }, risks.map((risk) => chipTo("risks", risk, RISK_SUFFIX)))
                : emptyLine("No risk pattern is carried by a motif that names it."),
            })
          : null,
        // A control step clears risk patterns, so it is read through the
        // controls its motifs realize.
        controlFor.length
          ? panel("Suggested against", {
              count: controlFor.length,
              hint: "Through the controls its motifs realize. Candidates, not proof a risk is removed.",
              body: el("div", { class: "lib-chips" }, controlFor.map((risk) => chipTo("risks", risk, RISK_SUFFIX))),
            })
          : null,
        SHOW_TERM_PROVENANCE && panel("Where it comes from", {
          body: provenance.refs.length
            ? el("div", { class: "lib-chips" }, [
                el("span", { class: "lib-meta-lead" },
                  PROVENANCE_LEAD[provenance.route]
                    + (provenance.via ? " " + provenance.via.label : "")),
                ...provenance.refs.map((ref) => refChip(ref, "tax")),
              ])
            : emptyLine("No source, no mapping, and nothing above it carries one."),
        }),
      ],
    ),
  ];
}


/* Nothing selected is the opening moment, and it is the one the whole panel
 * exists for: the reader is here to find out what the knowledge base holds. */
function landingTile(entry, kind) {
  const isRisk = kind === "risks";

  const told = describe(entry);

  const tile = el(
    "button",
    {
      type: "button",
      class: "lib-tile",

      title:
        told.from
          ? told.from + " - " + told.text
          : told.text,
    },

    [
      el(
        "div",
        { class: "lib-tile-head" },
        [
          el(
            "strong",
            {},
            shortName(
              entry.label,
              isRisk
                ? RISK_SUFFIX
                : MOTIF_SUFFIX
            )
          ),
        ]
      ),

      // A motif is a shape, and the shape is what tells two of them apart. The
      // description repeats it in words; the drawing does not have to be read.
      isRisk
        ? el(
            "p",
            {
              class:
                "lib-tile-desc"
                + (told.from ? " borrowed" : ""),
            },
            told.text
          )
        : el("div", { class: "lib-tile-shape" }, motifPreview(entry)),

      isRisk
        ? domainRow(entry)
        : null,

      el(
        "div",
        { class: "lib-tile-foot" },

        isRisk
          ? [
              el(
                "span",
                {},
                entry.motifs.length
                  ? entry.motifs.length
                    + " structure"
                    + (
                        entry.motifs.length > 1
                          ? "s"
                          : ""
                      )
                  : "any matched motif"
              ),

              el(
                "span",
                {},
                entry.controls.length
                  + " controls"
              ),
            ]

          : [
              el(
                "span",
                {},
                entry.nodes.length
                  + " elements"
              ),

              el(
                "span",
                {},
                entry.edges.length
                  + " relations"
              ),

              entry.control && !entry.riskPatterns.length
                ? el(
                    "span",
                    { class: "lib-tile-control" },
                    "control · suggested against " + suggestedAgainst(entry).length
                  )
                : el(
                    "span",
                    {},
                    entry.riskPatterns.length
                      ? entry.riskPatterns.length
                        + " risk pattern"
                        + (
                            entry.riskPatterns.length > 1
                              ? "s"
                              : ""
                          )
                      : "no risk pattern"
                  ),

              controlMotifs.has(entry.id) && !entry.control
                ? el(
                    "span",
                    {},
                    "realizes a control"
                  )
                : null,
            ]
      ),
    ]
  );

  tile.addEventListener(
    "click",
    () =>
      select(
        kind,
        entry.id
      )
  );

  return tile;
}

const LANDING_TITLE = {
  risks: "Every risk pattern this library can apply",
  motifs: "Every structure this library can recognise",
  terms: "Every term you can annotate an element with",
};

const LANDING_NOTE = { 
  risks: "A weakness in a system design and process that may lead to harm.",
  motifs: "Structures the library recognises in an architecture.",
  terms: "Annotation vocabulary for the library's motifs and risk patterns.",
};

function landing() {
  const entries = entriesOf(tab).filter(hits);

  const parts = [
    el("h3", { class: "lib-landing-title" }, LANDING_TITLE[tab]),
    el("p", { class: "lib-note" }, LANDING_NOTE[tab]),
  ];

  if (!entries.length) {
    parts.push(
      el(
        "p",
        { class: "lib-empty" },
        "Nothing in the library matches that."
      )
    );

    return parts;
  }

  if (tab === "risks") {
    groupsOfMotifs(entries).forEach(([familyName, members]) => {
      const family = members[0] ? members[0].family : null;
      parts.push(motifShelfHead(familyName, members.length, family && family.definition));
      parts.push(el("div", { class: "lib-grid" },
        members.map((entry) => landingTile(entry, tab))));
    });

    return parts;
  }

  if (tab === "terms") {
    groupsOfTerms(entries).forEach((group) => {
      parts.push(shelfHead(group[0], group[1].length));
      parts.push(el("div", { class: "lib-terms" },
        group[1].map((entry) => termTile(entry))));
    });

    const categories = catalogue.vocabulary.dataCategories.filter(hits);
    if (categories.length) {
      parts.push(el("h4", {}, "Data categories"));
      parts.push(el("p", { class: "lib-note" },
        "Set on an element by you, or derived by the assessment from the data flow "
        + "and the business process."));
      parts.push(el("div", { class: "lib-terms" }, categories.map((entry) =>
        el("div", { class: "lib-term lib-term-flat" }, [
          el("span", { class: "lib-term-name" }, entry.label),
          entry.definition
            ? el("span", { class: "lib-term-def" }, entry.definition)
            : null,
        ]))));
    }

    return parts;
  }

   groupsOfMotifs(entries).forEach(([familyName, members]) => {
    const family = members[0] ? members[0].family : null;

    parts.push(motifShelfHead(
      familyName,
      members.length,
      family && family.definition
    ));

    const sorted = [...members].sort((a, b) =>
      String(a.label || "").localeCompare(String(b.label || "")));

    parts.push(el("div", { class: "lib-grid shapes" },
      sorted.map((entry) => landingTile(entry, tab))));
  });
  return parts;
}

function renderDetail() {
  const panel =
    $("#library-detail");

  panel.innerHTML = "";
  panel.scrollTop = 0;

  const entry =
    byId[tab].get(
      selected[tab]
    );

  if (!entry) {
    landing().forEach(
      (part) =>
        panel.appendChild(part)
    );

    return;
  }

  (
    tab === "risks"
      ? riskDetail(entry)
      : tab === "terms"
        ? termDetail(entry)
        : motifDetail(entry)
  ).forEach(
    (part) => {
      if (part) {
        panel.appendChild(part);
      }
    }
  );
}

function showTab(next) {
  tab = next;

  $$(".library-tab").forEach(
    (t) =>
      t.classList.toggle(
        "active",
        t.dataset.libraryTab === next
      )
  );

  $("#library-collection").textContent =
    next === "risks"
      ? "Risk pattern library"
      : next === "terms"
        ? "Annotation vocabulary"
        : "Motif library";
}

/* Which group in the rail holds this entry, so selecting from the landing does
   not point at a row inside a folded section. */
function groupOf(kind, entry) {
  if (kind === "terms") return entry.shelf || "Unshelved";
  return entry.family ? entry.family.label : "Unshelved";
}

function select(kind, id) {
  showTab(kind);

  selected[kind] = id;

  const entry = byId[kind].get(id);
  const group = entry && groupOf(kind, entry);
  if (group && opened[kind]) opened[kind].add(group);

  renderRail();
  renderDetail();
}


// ---- adding a motif ----

async function insertMotif(motif, risk) {
  const ok =
    await addMotif({
      id: motif.id,
      label: motif.label,
      riskPattern: risk && ((risk.motifContext || {})[motif.id] || []).length ? risk.id : null,
    });

  if (!ok) {
    note(
      "error",
      "Could not add "
        + motif.label
        + "."
    );

    return;
  }

  addedCount += 1;

  leaveOpeningMode();

  startDrawing("architecture");

  note(
    "ok",

    "Added "
      + shortName(
          motif.label,
          MOTIF_SUFFIX
        )
      + " · "
      + motif.nodes.length
      + " elements"
  );

  $("#btn-library-close").textContent =
    "Show the canvas";
}

function note(kind, text) {
  const line =
    $("#library-status");

  line.className =
    "library-status "
    + kind;

  line.textContent =
    addedCount
      ? text
        + " — "
        + addedCount
        + " motif"
        + (
            addedCount > 1
              ? "s"
              : ""
          )
        + " added so far"

      : text;
}


// ---- opening and closing ----

function renderStats() {
  const stats =
    catalogue.stats;

  $("#library-stats").textContent =
    stats.riskPatterns
      + " risk patterns · "
      + stats.motifs
      + " motifs · "
      + stats.taxonomyEntries
      + " taxonomy entries · "
      + stats.controls
      + " controls · "
      + stats.patternRoles
      + " roles";

  $("#library-risk-count").textContent =
    String(stats.riskPatterns);

  $("#library-motif-count").textContent =
    String(stats.motifs);

  $("#library-term-count").textContent =
    String(stats.patternRoles);
}

async function load() {
  if (catalogue) {
    return true;
  }

  try {
    catalogue =
      await api("/api/library");
  } catch (error) {
    note(
      "error",

      "Could not read the library: "
        + error.message.split(
            String.fromCharCode(10)
          )[0]
    );

    return false;
  }

  catalogue.riskPatterns.forEach(
    (entry) =>
      byId.risks.set(
        entry.id,
        entry
      )
  );
  // Risks open unfolded: 33 entries are the front door, and still fold by family.
  catalogue.riskPatterns.forEach((entry) => opened.risks.add(groupOf("risks", entry)));

  catalogue.motifs.forEach(
    (entry) =>
      byId.motifs.set(
        entry.id,
        entry
      )
  );

  catalogue.vocabulary.roles.forEach(
    (entry) =>
      byId.terms.set(
        entry.id,
        entry
      )
  );

  controlMotifs = new Set(
    catalogue.motifs
      .filter((motif) => (motif.controls || []).length)
      .map((motif) => motif.id)
  );

  renderStats();

  return true;
}

function leaveOpeningMode() {
  openingMode = false;

  $("#library-lead")
    .classList.add("hidden");
}

export function closeLibrary() {
  openingMode = false;

  $("#library")
    .classList.add("hidden");
}

export function isLibraryOpen() {
  return !$("#library")
    .classList.contains("hidden");
}

export async function openLibrary(
  options = {}
) {
  $("#library")
    .classList.remove("hidden");

  openingMode =
    Boolean(options.opening);

  // The lead is the opening frame, not a permanent banner over the catalogue.
  $("#library-lead")
    .classList.toggle(
      "hidden",
      !openingMode
    );

  if (!(await load())) {
    return;
  }

  renderRail();
  renderDetail();
}

export function initLibrary() {
  on(
    "choice:settled",
    () => {
      if (openingMode) {
        closeLibrary();
      }
    }
  );

  $("#btn-library")
    .addEventListener(
      "click",
      () => openLibrary()
    );

  $("#btn-library-close")
    .addEventListener(
      "click",
      closeLibrary
    );

  $$(".library-tab").forEach(
    (button) =>
      button.addEventListener(
        "click",
        () => {
          showTab(
            button.dataset.libraryTab
          );

          renderRail();
          renderDetail();
        }
      )
  );

  $("#library-search")
    .addEventListener(
      "input",
      (ev) => {
        query =
          ev.target.value
            .trim()
            .toLowerCase();

        renderRail();

        if (!selected[tab]) {
          renderDetail();
        }
      }
    );

  $("#library-start-business")
    .addEventListener(
      "click",
      () => {
        startDrawing("business");
        closeLibrary();
      }
    );

  $("#library-start-architecture")
    .addEventListener(
      "click",
      () => {
        startDrawing("architecture");
        closeLibrary();
      }
    );
}