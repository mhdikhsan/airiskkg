import { postJson } from "../core/api.js";
import { emit } from "../core/bus.js";
import { $, $$, el } from "../core/dom.js";
import { revealInSource } from "../core/source.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { GraphView } from "../lib/graph_view.js";
import { VersionHistory } from "../lib/version_history.js";
import { renderDerivedCategories } from "./dataflow.js";
import { renderHistory } from "./history.js";
import { renderMotifs } from "./motifs.js";
import { runMutation } from "./mutations.js";
import { noteChange, renderKnowledgeBaseBadge, runDelta, setStale } from "./run.js";
import { ProcessCanvas } from "../lib/process_canvas.js";
import { state } from "../state.js";

let selectedFinding = null;

function controlItem(control, finding) {
  const motifs = control.realizedByMotifs || [];
  const children = [el("span", { class: "ctrl-label" }, control.label)];
   if (control.nature) {
    children.push(el("span", { class: `ctrl-nature ${control.nature}` }, control.nature));
  }
  if (control.applicable) {
    children.push(
      el("div", { class: "ctrl-motifs" }, [
        el("button", {
          type: "button",
          class: "chip motif-suggest clickable",
          title: "Insert this control on the path this finding cites, then re-assess",
          onclick: (ev) => { ev.stopPropagation(); applyControl(control, finding); },
        }, "Apply to this finding"),
        motifs.length ? el("span", { class: "ctrl-motifs-lead" }, ` inserts ${motifs[0].label}`) : null,
      ])
    );
  } else if (motifs.length) {
    children.push(
      el("div", { class: "ctrl-motifs" }, [
        el("span", { class: "ctrl-motifs-lead" }, "realized by: "),
        ...motifs.map((m) => el("span", { class: "chip motif-suggest" }, m.label)),
      ])
    );
  }
  return el("li", { title: control.definition || "" }, children);
}

function groundedFamiliesSection(families) {
  if (!families || !families.length) return null;
  return el("div", { class: "ctrl-group evidence" }, [
    el("div", { class: "ctrl-group-head" }, [
      el("span", {}, `Related control families (${families.length})`),
      el("span", { class: "ctrl-group-source" }, "MIT AI Risk Repository"),
    ]),
    el("ul", { class: "ref-list grounded-list" },
      families.map((f) => el("li", { title: f.definition || "" }, el("span", { class: "chip tax-ground" }, f.label)))),
  ]);
}

// All suggested controls under one "Mitigations" list.
function controlSections(controls, finding) {
  if (!controls.length) return [];
  return [
    el("div", { class: "ctrl-group" }, [
      el("div", { class: "ctrl-group-head" }, [
        el("span", {}, `Suggested controls (${controls.length})`),
        el("span", { class: "ctrl-group-source" }, "PAIR-AI"),
      ]),
      el("ul", { class: "ref-list" }, controls.map((c) => controlItem(c, finding))),
    ]),
  ];
}

const TAXONOMY_CHIP_LIMIT = 4;

function taxonomyChips(finding) {
  const entries = finding.taxonomyEntries || [];
  const row = el("div", { class: "finding-meta" });
  if (finding.mechanism) {
    row.appendChild(el("span", { class: "chip mech", title: finding.mechanism.id }, finding.mechanism.label));
  }
  /* Each entry says which catalogue it came from. */
  const chipFor = (t) => el("span", {
    class: "chip tax",
    title: `${t.source}
${t.definition || t.id}`,
  }, [
    el("span", { class: "chip-source" }, t.sourceShort || t.source),
    el("span", {}, t.label),
  ]);
  entries.slice(0, TAXONOMY_CHIP_LIMIT).forEach((t) => row.appendChild(chipFor(t)));

  const hidden = entries.slice(TAXONOMY_CHIP_LIMIT);
  if (!hidden.length) return row;

  const more = el("button",
    { type: "button", class: "chip tax chip-more", title: "Show the remaining taxonomy entries" },
    `+${hidden.length}`);
  more.addEventListener("click", (ev) => {
    ev.stopPropagation(); // the card itself selects the finding
    hidden.forEach((t) => row.insertBefore(chipFor(t), more));
    more.remove();
  });
  row.appendChild(more);
  return row;
}

/* One risk pattern raised at several places is one card, not one per place.
   Findings with the same evidence are one place reached by several motifs. */
function placesOf(findings) {
  const places = new Map();
  findings.forEach((finding) => {
    const key = finding.evidence.map((e) => e.id).sort().join("|");
    if (!places.has(key)) places.set(key, { findings: [], evidence: finding.evidence });
    places.get(key).findings.push(finding);
  });
  return [...places.values()];
}

function byRiskPattern(findings) {
  const groups = new Map();
  findings.forEach((finding) => {
    const key = (finding.riskPattern && finding.riskPattern.id) || finding.label;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(finding);
  });
  return [...groups.values()];
}

function unique(items, key) {
  const seen = new Map();
  items.forEach((item) => { if (item && !seen.has(key(item))) seen.set(key(item), item); });
  return [...seen.values()];
}

function select(card, ids) {
  $$(".finding-card.selected, .finding-place.selected").forEach((c) => c.classList.remove("selected"));
  selectedFinding = card;
  card.classList.add("selected");
  GraphView.setHighlight(ids);
  revealInSource(ids);
}

function placeRow(place, index, count) {
  const finding = place.findings[0];
  const ids = place.evidence.map((e) => e.id);
  const motifs = unique(place.findings.map((f) => f.motif), (m) => m.id);
  const row = el("div", { class: "finding-place", tabindex: "0", title: "Show this place on the canvas" }, [
    el("div", { class: "finding-place-head" }, [
      count > 1 ? el("span", { class: "finding-place-n" }, String(index + 1)) : null,
      el("span", { class: "finding-place-evidence" }, place.evidence.map((e) => e.label).join(" · ")),
    ]),
    motifs.length
      ? el("div", { class: "finding-place-motifs" },
        [el("span", { class: "ctrl-motifs-lead" }, "matched by "),
          ...motifs.map((m) => el("span", { class: "chip" }, m.label))])
      : null,
    el("details", {}, [
      el("summary", {}, `Suggested controls (${finding.suggestedControls.length}) for this place`),
      ...controlSections(finding.suggestedControls, finding),
    ]),
  ]);
  row.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (selectedFinding === row) {
      selectedFinding = null;
      row.classList.remove("selected");
      GraphView.setHighlight([]);
      return;
    }
    select(row, ids);
  });
  return row;
}

function findingCard(findings) {
  const first = findings[0];
  const places = placesOf(findings);
  const allIds = unique(findings.flatMap((f) => f.evidence), (e) => e.id).map((e) => e.id);
  const merged = {
    ...first,
    taxonomyEntries: unique(findings.flatMap((f) => f.taxonomyEntries || []), (t) => t.id),
  };
  const families = unique(findings.flatMap((f) => f.groundedControlFamilies || []), (f) => f.id || f.label);
  const card = el("div", { class: "finding-card", tabindex: "0" }, [
    el("div", { class: "finding-head" }, [
      el("strong", {}, first.label),
      el("span", { class: "chip finding-places", title: "Places in this architecture where the risk pattern holds" },
        places.length === 1 ? "1 place" : `${places.length} places`),
    ]),
    first.description ? el("p", { class: "finding-desc" }, first.description) : null,
    taxonomyChips(merged),
    el("div", { class: "finding-place-list" }, places.map((place, i) => placeRow(place, i, places.length))),
    groundedFamiliesSection(families),
  ]);
  card.addEventListener("click", () => {
    if (selectedFinding === card) {
      selectedFinding = null;
      card.classList.remove("selected");
      GraphView.setHighlight([]);
      return;
    }
    select(card, allIds);
  });
  return card;
}

export function clearFindings() {
  state.lastAssessment = null;
  state.lastRun = null;
  $("#findings-list").innerHTML = "";
  $("#findings-summary").innerHTML = "";
  $("#findings-count").textContent = "";
  $("#findings-empty").classList.remove("hidden");
  setStale(false);
  selectedFinding = null;
  ProcessCanvas.setFindings([]);
}

export function reReadFindings() {
  // Nothing is re-run: the findings are the same, the question is narrower.
  if (state.lastAssessment) renderFindings(state.lastAssessment);
}

function findingsInScope(data) {
  if (!state.scopedSystem) return data.findings;
  const rows = (data.findingsByActivity || []).filter((row) => row.systems.includes(state.scopedSystem));
  const wanted = new Set(rows.flatMap((row) => row.items.map((item) => item.id)));
  return data.findings.filter((finding) => wanted.has(finding.id));
}

export function renderFindings(data) {
  $("#findings-empty").classList.add("hidden");
  const summary = $("#findings-summary");
  summary.innerHTML = "";

  const shown = findingsInScope(data);
  const narrowed = shown.length !== data.findings.length;
  const delta = runDelta(data.findings);
  const row = [
    el("span", { class: "stat" },
      narrowed
        ? `${shown.length} of ${data.summary.riskFindingCount} candidate findings`
        : `${data.summary.riskFindingCount} candidate findings`),
    el("span", { class: "stat" }, `${byRiskPattern(shown).length} risk patterns`),
    el("span", { class: "stat" }, `${data.summary.motifMatchCount} motif matches`),
  ];
  if (delta && (delta.cleared || delta.raised)) {
    if (delta.cleared) {
      row.push(el("span", { class: "stat delta" },
        `${delta.cleared} cleared since the last run`));
    }
    if (delta.raised) {
      row.push(el("span", { class: "stat delta raised" },
        `${delta.raised} newly raised`));
    }
  } else if (delta) {
    row.push(el("span", { class: "stat" }, "unchanged since the last run"));
  }
  if (narrowed) {
    const scopeLabel = (state.lastGraph && state.lastGraph.systems || [])
      .filter((s) => s.id === state.scopedSystem).map((s) => s.label)[0] || "this architecture";
    const clear = el("button", { type: "button", class: "crumb-link" }, `showing ${scopeLabel} — show all`);
    clear.addEventListener("click", () => {
      state.scopedSystem = null;
      state.openedFrom = null;
      emit("scope:changed");
    });
    row.push(clear);
  }
  summary.appendChild(el("div", { class: "summary-row" }, row));

  if (data.run && data.run.inputFingerprint) {
    state.lastRun = {
      fingerprint: data.run.inputFingerprint,
      findingIds: new Set(data.findings.map((f) => f.id)),
    };
    setStale(false);
    VersionHistory.record({
      fingerprint: data.run.inputFingerprint,
      knowledgeBase: data.run.knowledgeBase,
      counts: {
        findings: data.summary.riskFindingCount,
        matches: data.summary.motifMatchCount,
        derived: data.summary.derivedCategoryCount,
      },
      findingIds: data.findings.map((f) => f.id),
      findings: data.findings.map((f) => ({ id: f.id, label: f.label })),
      ttl: Editor.getValue(),
      cause: state.pendingCause,
    });
    state.pendingCause = null;
    renderHistory();

  }
  state.lastAssessment = data;
  // Tell the business canvas what was found where.
  ProcessCanvas.setFindings(data.findingsByActivity);
  renderKnowledgeBaseBadge(data.run);

  const list = $("#findings-list");
  list.innerHTML = "";
  selectedFinding = null;
  GraphView.setHighlight([]);
  if (!shown.length) {
    list.appendChild(el("p", { class: "drawer-empty" },
      narrowed
        ? "Nothing was found in this architecture. Other systems in this graph may still carry risks."
        : "No candidate risk findings were produced for this architecture."));
  }
  const groups = byRiskPattern(shown);
  groups.forEach((group) => list.appendChild(findingCard(group)));
  $("#findings-count").textContent = shown.length ? String(shown.length) : "";
  emit("assessment:rendered");
}

export async function reassess(ttl) {
  const data = await postJson("/api/assess", { ttl });
  renderFindings(data);
  renderMotifs(data.motifMatches, data.motifGaps);
  renderDerivedCategories(data.derivedCategories);
  return data;
}

// ---- applying a control ----

export function applyControl(control, finding) {
  return runMutation(async () => {
    try {
      const { ttl, addedTriples, newIds } = await postJson("/api/apply-control", {
        ttl: Editor.getValue(), control: control.id, finding: finding.id,
      });
      if (!addedTriples) {
        setStatus("ok", `"${control.label}" is already in place on this path.`);
        return;
      }
      noteChange(`applied ${control.label}`);
      Editor.setValue(ttl);
      GraphView.setHighlight(newIds || []);
      setStatus("busy", `Applied "${control.label}" - re-assessing...`);
      const data = await reassess(ttl);
      setStatus("ok", `Applied "${control.label}"`,
        `${data.summary.riskFindingCount} findings · ${data.summary.motifMatchCount} matches`);
    } catch (error) {
      setStatus("error", "Could not apply the control: " + error.message.split("\n")[0]);
    }
  });
}
