/* The library */

import { api } from "../core/api.js";
import { on } from "../core/bus.js";
import { $, $$, el } from "../core/dom.js";
import { motifPreview } from "../lib/motif_preview.js";
import { startDrawing } from "./canvas.js";
import { addMotif } from "./motifs.js";

let catalogue = null;
let tab = "risks";
let query = "";
let selected = { risks: null, motifs: null };
let addedCount = 0;

// Open as the front door, rather than opened deliberately from the toolbar.
let openingMode = false;

const byId = { risks: new Map(), motifs: new Map() };

// Motifs a control names as a candidate structural realization: the same list
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
    ...(entry.derivedFrom || []).map((d) => d.label),
    ...(entry.taxonomy || []).map((t) => t.label + " " + t.sourceShort),
    ...(entry.roles || []).map((r) => r.label),
    ...(entry.controls || []).map((c) => c.label),
  ].join(" ").toLowerCase();
}

function hits(entry) {
  return !query || haystack(entry).includes(query);
}


// ---- the rail ----

/* Risk patterns are listed, not filed. */

/* Motifs group by the family of AI system */
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


/* How many risk patterns apply to a motif */
function motifRiskCount(entry) {
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
                : "no risk pattern in the library applies to it"
            )
          + (
              controlMotifs.has(entry.id)
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

  const entries = (
    tab === "risks"
      ? catalogue.riskPatterns
      : catalogue.motifs
  ).filter(hits);

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

  if (tab === "risks") {
    entries.forEach((entry) => {
      list.appendChild(railRow(entry, tab));
    });

    return;
  }

  groupsOfMotifs(entries).forEach((group) => {
    list.appendChild(
      el(
        "div",
        { class: "lib-group" },
        [
          el("span", {}, group[0]),

          el(
            "span",
            { class: "lib-group-count" },
            String(group[1].length)
          ),
        ]
      )
    );

    group[1].forEach((entry) => {
      list.appendChild(
        railRow(entry, tab)
      );
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
          { class: "chip-source" },
          ref.sourceShort
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

function section(title, note, children) {
  return el(
    "section",
    { class: "lib-section" },
    [
      el("h4", {}, title),

      note
        ? el(
            "p",
            { class: "lib-note" },
            note
          )
        : null,

      ...[]
        .concat(children)
        .filter(Boolean),
    ]
  );
}

function motifCard(motif, compact) {
  return el(
    "div",
    { class: "lib-card" },
    [
      el(
        "div",
        { class: "lib-card-head" },
        [
          el(
            "strong",
            {},
            shortName(
              motif.label,
              MOTIF_SUFFIX
            )
          ),

          el(
            "span",
            { class: "lib-card-size" },
            motif.nodes.length
              + " elements · "
              + motif.edges.length
              + " relations"
          ),
        ]
      ),

      // On the motif's own page the description is already above the card.
      compact && motif.description
        ? el(
            "p",
            { class: "lib-card-desc" },
            motif.description
          )
        : null,

      el(
        "div",
        { class: "lib-preview" },
        motifPreview(motif)
      ),

      motif.roles.length
        ? el(
            "div",
            { class: "lib-roles" },
            [
              el(
                "span",
                { class: "lib-roles-lead" },
                "roles it matches on: "
              ),

              ...motif.roles.map(
                (role) =>
                  el(
                    "span",
                    { class: "chip role" },
                    role.label
                  )
              ),
            ]
          )
        : null,

      el(
        "div",
        { class: "lib-card-actions" },
        [
          el(
            "button",
            {
              type: "button",
              class: "btn small primary",

              title:
                "Add this motif's elements to the graph, "
                + "already annotated with the roles it matches on",

              onclick: () => insertMotif(motif),
            },
            "Add to canvas"
          ),

          compact
            ? el(
                "button",
                {
                  type: "button",
                  class: "btn small",

                  title:
                    "Read this motif on its own",

                  onclick: () =>
                    select(
                      "motifs",
                      motif.id
                    ),
                },
                "Open motif"
              )
            : null,
        ]
      ),
    ]
  );
}

function detailHead(entry, extra) {
  return el(
    "div",
    { class: "lib-detail-head" },
    [
      el(
        "button",
        {
          type: "button",
          class: "lib-back",

          title:
            "Back to the whole catalogue",

          onclick: () => {
            selected[tab] = null;
            renderRail();
            renderDetail();
          },
        },
        "‹ all"
      ),

      el(
        "h3",
        {},
        entry.label
      ),

      el(
        "div",
        { class: "lib-detail-source" },
        [
          extra || null,

          (entry.derivedFrom || []).length
            ? el(
                "span",
                { class: "lib-roles-lead" },
                "source:"
              )
            : null,

          ...(entry.derivedFrom || [])
            .map((ref) =>
              refChip(ref, "tax")
            ),
        ].filter(Boolean)
      ),
    ]
  );
}

function describedParagraph(entry) {
  const told = describe(entry);

  if (!told.text) {
    return null;
  }

  return el(
    "p",
    { class: "lib-detail-desc" },
    [
      told.from
        ? el(
            "span",
            { class: "lib-from" },
            told.from + " — "
          )
        : null,

      el(
        "span",
        {},
        told.text
      ),
    ].filter(Boolean)
  );
}

function riskDetail(entry) {
  const motifs = entry.motifs
    .map((id) =>
      byId.motifs.get(id)
    )
    .filter(Boolean);

  const parts = [
    detailHead(entry),

    describedParagraph(entry),
  ];

  parts.push(
    section(
      motifs.length
        ? "Structures it applies to (" + motifs.length + ")"
        : "Structures it applies to",

      motifs.length
        ? "A motif states what is present, never that it is dangerous. Add one to start a graph the assessment can already read."
        : "This pattern names no motif of its own: it is evaluated over any motif match whose conditions hold.",

      motifs.map(
        (motif) =>
          motifCard(motif, true)
      )
    )
  );

  parts.push(
    section(
      "Applicability conditions (" + entry.conditions.length + ")",

      "Evaluated over a motif match, not over the graph at large. Only when these hold does the pattern raise a candidate finding.",

      el(
        "ul",
        { class: "lib-list" },

        entry.conditions.map(
          (condition) =>
            el(
              "li",
              {
                title:
                  condition.definition
                  || condition.id,
              },
              condition.label
            )
        )
      )
    )
  );

  if (entry.mechanism) {
    parts.push(
      section(
        "Mechanism",

        "Curated, and carried by reference: the same explanation reproduces unchanged across systems and runs.",

        el(
          "div",
          { class: "lib-mechanism" },
          [
            refChip(
              entry.mechanism,
              "mech"
            ),

            entry.mechanism.definition
              ? el(
                  "p",
                  { class: "lib-card-desc" },
                  entry.mechanism.definition
                )
              : null,
          ]
        )
      )
    );
  }

  parts.push(consequenceSection(entry));

  parts.push(
    section(
      "Suggested controls (" + entry.controls.length + ")",

      "Suggested, not verified. A control realized by a motif names a candidate structure, not proof that inserting it removes the risk.",

      el(
        "ul",
        { class: "lib-list" },

        entry.controls.map(controlItem)
      )
    )
  );

  return parts;
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

/* The consequence side, which is what makes a risk a risk. */
function consequenceSection(entry) {
  const byDomain = new Map();
  const alsoCalled = [];

  entry.taxonomy.forEach((ref) => {
    if (!ref.domain) {
      alsoCalled.push(ref);
      return;
    }

    if (!byDomain.has(ref.domain)) {
      byDomain.set(ref.domain, []);
    }

    byDomain.get(ref.domain).push(ref);
  });

  const body = [];

  if (byDomain.size) {
    [...byDomain.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .forEach((pair) => {
        body.push(
          el(
            "div",
            { class: "lib-domain" },
            [
              el("span", { class: "chip domain" }, pair[0]),

              el(
                "div",
                { class: "lib-chips" },
                pair[1].map((ref) => refChip(ref, "tax"))
              ),
            ]
          )
        );
      });
  } else {
    body.push(
      el(
        "p",
        { class: "lib-note" },
        "Nothing upstream maps this pattern to a domain of harm. The link is "
        + "not written here: curating one without a source is how a mapping "
        + "layer stops being evidence."
      )
    );
  }

  if (alsoCalled.length) {
    body.push(
      el(
        "div",
        { class: "lib-domain" },
        [
          el(
            "span",
            { class: "lib-roles-lead" },
            "also catalogued as"
          ),

          el(
            "div",
            { class: "lib-chips" },
            alsoCalled.map((ref) => refChip(ref, "tax"))
          ),
        ]
      )
    );
  }

  return section(
    "What it may lead to",

    "A pattern names a weakness in the design. The risk is the harm it may end "
    + "in, and these are the domains the entries it may indicate roll up to.",

    body
  );
}

function controlItem(control) {
  const realizing = control.realizedByMotifs
    .map((id) =>
      byId.motifs.get(id)
    )
    .filter(Boolean);

  return el(
    "li",
    {
      title:
        control.definition || "",
    },
    [
      el(
        "span",
        { class: "lib-control-name" },
        control.label
      ),

      control.nature
        ? el(
            "span",
            {
              class:
                "ctrl-nature "
                + control.nature,
            },
            control.nature
          )
        : null,

      realizing.length
        ? el(
            "div",
            { class: "lib-control-motifs" },
            [
              el(
                "span",
                { class: "lib-roles-lead" },
                "candidate structure: "
              ),

              ...realizing.map(
                (motif) =>
                  el(
                    "button",
                    {
                      type: "button",
                      class:
                        "chip motif-suggest clickable",

                      title:
                        "Open " + motif.label,

                      onclick: () =>
                        select(
                          "motifs",
                          motif.id
                        ),
                    },

                    shortName(
                      motif.label,
                      MOTIF_SUFFIX
                    )
                  )
              ),
            ]
          )
        : null,
    ]
  );
}

function motifDetail(entry) {
  const risks = entry.riskPatterns
    .map((id) =>
      byId.risks.get(id)
    )
    .filter(Boolean);

  return [
    detailHead(
      entry,

      entry.family
        ? el(
            "span",
            {
              class: "chip family",

              title:
                entry.family.definition || "",
            },
            entry.family.label
          )
        : null
    ),

    describedParagraph(entry),

    motifCard(entry, false),

    section(
      risks.length
        ? "Risk patterns that apply to it (" + risks.length + ")"
        : "Risk patterns that apply to it",

      risks.length
        ? "Matching this structure is not a finding. Each of these adds conditions that decide whether one is raised."
        : "No risk pattern in the library applies to this structure on its own. It can still appear inside a larger match.",

      el(
        "div",
        { class: "lib-chips" },

        risks.map(
          (risk) =>
            el(
              "button",
              {
                type: "button",
                class:
                  "chip tax clickable",

                title:
                  risk.description
                  || risk.label,

                onclick: () =>
                  select(
                    "risks",
                    risk.id
                  ),
              },

              shortName(
                risk.label,
                RISK_SUFFIX
              )
            )
        )
      )
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

      el(
        "p",
        {
          class:
            "lib-tile-desc"
            + (told.from ? " borrowed" : ""),
        },

        told.text
          || "A structure the library can recognise."
      ),

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
                entry.conditions.length
                  + " condition"
                  + (
                      entry.conditions.length > 1
                        ? "s"
                        : ""
                    )
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

              el(
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

              controlMotifs.has(entry.id)
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

function landing() {
  const entries = (
    tab === "risks"
      ? catalogue.riskPatterns
      : catalogue.motifs
  ).filter(hits);

  const parts = [
    el(
      "h3",
      { class: "lib-landing-title" },

      tab === "risks"
        ? "Every risk pattern this library can apply"
        : "Every structure this library can recognise"
    ),

    el(
      "p",
      { class: "lib-note" },

      tab === "risks"
        ? "A risk pattern is a weakness in a design: a structure, plus the conditions that make it worth raising. It is not the risk. The risk is what it may lead to, and each card says which domains of harm the entries it may indicate roll up to - candidates for triage, never an outcome anyone has observed."
        : "A motif is risk-neutral: it says what is present, never that it is dangerous. Open one to see its shape and what applies to it."
    ),
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
    parts.push(
      el(
        "div",
        { class: "lib-grid" },

        entries.map(
          (entry) => landingTile(entry, tab)
        )
      )
    );

    return parts;
  }

  groupsOfMotifs(entries).forEach((group) => {
    parts.push(
      el(
        "h4",
        {},
        group[0]
      )
    );

    const family = group[1][0] ? group[1][0].family : null;

    if (family && family.definition) {
      parts.push(
        el(
          "p",
          { class: "lib-note" },
          family.definition
        )
      );
    }

    parts.push(
      el(
        "div",
        { class: "lib-grid" },

        group[1].map(
          (entry) =>
            landingTile(
              entry,
              tab
            )
        )
      )
    );
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
      : "Motif library";
}

function select(kind, id) {
  showTab(kind);

  selected[kind] = id;

  renderRail();
  renderDetail();
}


// ---- adding a motif ----

async function insertMotif(motif) {
  const ok =
    await addMotif({
      id: motif.id,
      label: motif.label,
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

  catalogue.motifs.forEach(
    (entry) =>
      byId.motifs.set(
        entry.id,
        entry
      )
  );

  controlMotifs =
    new Set(
      catalogue.riskPatterns.flatMap(
        (pattern) =>
          pattern.controls.flatMap(
            (control) =>
              control.realizedByMotifs
          )
      )
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

  $("#library-start-risk")
    .addEventListener(
      "click",
      () => {
        startDrawing("risk");
        closeLibrary();
      }
    );
}