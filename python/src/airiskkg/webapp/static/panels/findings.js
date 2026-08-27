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
    el("div", { class: "ctrl-group-head" }, `MIT mitigations (${families.length})`),
    el("ul", { class: "ref-list grounded-list" },
      families.map((f) => el("li", { title: f.definition || "" }, el("span", { class: "chip tax-ground" }, f.label)))),
  ]);
}

// All suggested controls under one "Mitigations" list.
function controlSections(controls, finding) {
  if (!controls.length) return [];
  return [
    el("div", { class: "ctrl-group" }, [
      el("div", { class: "ctrl-group-head" }, `Mitigations (${controls.length})`),
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
  /* Each entry says which catalogue it came from. Without it the list read as
   * one undifferentiated set: "LLM01:2025 Prompt Injection" names its source
   * because OWASP numbers its own entries, while "Prompt injection attack" and
   * "AI system security vulnerabilities" gave no clue they are IBM and MIT. */
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

function findingCard(finding) {
  const evidenceIds = finding.evidence.map((e) => e.id);
  const card = el("div", { class: "finding-card", tabindex: "0" }, [
    el("div", { class: "finding-head" }, [
      el("strong", {}, finding.label),
      finding.motif ? el("span", { class: "chip" }, finding.motif.label) : null,
    ]),
    finding.description ? el("p", { class: "finding-desc" }, finding.description) : null,
    taxonomyChips(finding),
    el("details", {}, [
      el("summary", {}, `Suggested controls (${finding.suggestedControls.length}) · evidence (${finding.evidence.length})`),
      ...controlSections(finding.suggestedControls, finding),
      groundedFamiliesSection(finding.groundedControlFamilies),
      el("div", { class: "evidence-note" }, "Evidence: " + finding.evidence.map((e) => e.label).join(", ")),
    ]),
  ]);
  card.addEventListener("click", () => {
    if (selectedFinding === card) {
      selectedFinding = null;
      card.classList.remove("selected");
      GraphView.setHighlight([]);
      return;
    }
    $$(".finding-card.selected").forEach((c) => c.classList.remove("selected"));
    selectedFinding = card;
    card.classList.add("selected");
    GraphView.setHighlight(evidenceIds);
    revealInSource(evidenceIds);
  });
  return card;
}

/* Which findings belong to the architecture currently open. The assessment
 * stays whole; only the reading narrows. */
/* The last run described a document that is gone. Leaving its findings under
 * a freshly loaded example reads as the new one having been assessed - the
 * canvas redraws, the risk list does not, and nothing says which graph the
 * numbers belong to. */
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
  shown.forEach((f) => list.appendChild(findingCard(f)));
  $("#findings-count").textContent = shown.length ? String(shown.length) : "";
}

// ---- applying a control ----

function applyControl(control, finding) {
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
      const data = await postJson("/api/assess", { ttl });
      renderFindings(data);
      renderMotifs(data.motifMatches, data.motifGaps);
      renderDerivedCategories(data.derivedCategories);
      setStatus("ok", `Applied "${control.label}"`,
        `${data.summary.riskFindingCount} findings · ${data.summary.motifMatchCount} matches`);
    } catch (error) {
      setStatus("error", "Could not apply the control: " + error.message.split("\n")[0]);
    }
  });
}
