/* How the library names, describes and shelves an entry: shared by the
   library and the risk list page, so the two cannot label a risk differently. */

import { el } from "../core/dom.js";

export const RISK_SUFFIX = /\s*risk pattern$/i;
export const MOTIF_SUFFIX = /\s*Motif$/;

export function shortName(label, suffix) {
  return label.replace(suffix, "").trim() || label;
}

/* Not every risk pattern carries a description of its own. */
export function describe(entry) {
  if (entry.description) return { text: entry.description, from: null };

  const source = (entry.derivedFrom || []).find((ref) => ref.definition);

  return source
    ? { text: source.definition, from: source.label }
    : { text: "", from: null };
}

export function groupsOfMotifs(entries) {
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

export function refChip(ref, extraClass) {
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
