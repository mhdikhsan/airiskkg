/* Every risk pattern on one page, under the labels the library gives it. */

import { api } from "../core/api.js";
import { el } from "../core/dom.js";
import {
  MOTIF_SUFFIX, RISK_SUFFIX, describe, groupsOfMotifs, refChip, shortName,
} from "../lib/library_text.js";

function row(label, value) {
  return el("div", { class: "rl-row" }, [el("dt", {}, label), el("dd", {}, value)]);
}

function listed(labels, none) {
  return labels.length ? labels.join(", ") : none;
}

function entryOf(risk, motifName) {
  const told = describe(risk);
  return el("section", { class: "rl-entry", id: risk.id }, [
    el("h3", {}, el("a", { href: "#" + risk.id }, shortName(risk.label, RISK_SUFFIX))),
    (risk.derivedFrom || []).length
      ? el("div", { class: "rl-source" }, [
        el("span", { class: "lib-meta-lead" }, "source"),
        ...risk.derivedFrom.map((ref) => refChip(ref, "tax")),
      ])
      : null,
    told.text
      ? el("p", { class: "rl-lede" }, [
        told.from ? el("span", { class: "lib-from" }, told.from + " — ") : null,
        told.text,
      ])
      : null,
    el("dl", {}, [
      row("Risk mechanism", risk.mechanism ? risk.mechanism.label : "none recorded"),
      row("Raised when", listed((risk.conditions || []).map((c) => c.label), "its motif matches")),
      row("May lead to", listed((risk.riskDomains || []).map((d) => d.label), "no risk domain linked")),
      row("Suggested controls", listed((risk.controls || []).map((c) => c.label), "none")),
      row("Related motifs", listed(risk.motifs.map(motifName),
        "any motif match whose conditions hold")),
    ]),
  ]);
}

export async function renderRiskList(host) {
  const catalogue = await api("/api/library");
  const motifs = new Map(catalogue.motifs.map((m) => [m.id, shortName(m.label, MOTIF_SUFFIX)]));
  const risks = catalogue.riskPatterns;
  host.textContent = "";
  host.appendChild(el("p", { class: "rl-count" },
    `${risks.length} risk patterns. Each one raises a candidate risk for triage, never a confirmed defect.`));
  groupsOfMotifs(risks).forEach(([family, entries]) => {
    host.appendChild(el("h2", {}, [family, " ", el("span", { class: "rl-n" }, String(entries.length))]));
    entries.forEach((risk) => host.appendChild(entryOf(risk, (id) => motifs.get(id) || id)));
  });
  const asked = location.hash && document.getElementById(location.hash.slice(1));
  if (asked) asked.scrollIntoView();
}
