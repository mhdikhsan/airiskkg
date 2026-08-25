/* The version list, and previewing a version without restoring it.
 */

import { $, el } from "../core/dom.js";
import { setTabVisible } from "../core/drawer.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../editor.js";
import { VersionHistory } from "../history.js";
import { noteChange } from "../panels/run.js";
import { state } from "../state.js";

//version history

function shortTime(iso) {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? "" : at.toLocaleString();
}

function deltaChip(delta) {
  if (!delta) return el("span", { class: "hist-delta" }, "first run");
  if (!delta.cleared && !delta.raised) return el("span", { class: "hist-delta" }, "no change");
  const parts = [];
  if (delta.cleared) parts.push(`−${delta.cleared}`);
  if (delta.raised) parts.push(`+${delta.raised}`);
  return el(
    "span",
    { class: delta.raised ? "hist-delta raised" : "hist-delta cleared" },
    parts.join(" ")
  );
}

export function renderHistory() {
  const versions = VersionHistory.list();
  const list = $("#history-list");
  const empty = $("#history-empty");
  list.innerHTML = "";
  $("#history-count").textContent = versions.length ? String(versions.length) : "";
  setTabVisible("history", versions.length > 0);
  empty.classList.toggle("hidden", versions.length > 0);

  versions.forEach((version) => {
    const current = state.lastRun && state.lastRun.fingerprint === version.fingerprint;
    const row = el("div", { class: current ? "hist-row current" : "hist-row" }, [
      el("span", { class: "hist-v" }, `v${version.v}`),
      el("span", { class: "hist-at" }, shortTime(version.at)),
      el("span", { class: "hist-counts" },
        `${version.counts.findings ?? "?"} findings · ${version.counts.matches ?? "?"} matches`),
      deltaChip(version.delta),
      el("span", { class: "hist-cause" }, version.cause || ""),
    ]);

    /* Reading a version is not the same act as adopting one. Restore replaces
     * the graph on screen, which is a commitment; opening a row only says what
     * that assessment found, and what moved since the one before it. */
    row.addEventListener("click", (ev) => {
      if (ev.target.closest("button")) return;
      previewVersion(version);
    });
    row.style.cursor = "pointer";

    if (version.ttl && !current) {
      const restore = el("button", { class: "btn small", type: "button" }, "Restore");
      restore.addEventListener("click", () => {
        noteChange(`restored v${version.v}`);
        Editor.setValue(version.ttl);
        setStatus("ok", `Restored v${version.v}`,
          `${version.counts.findings ?? "?"} findings when it was assessed`);
      });
      row.appendChild(restore);
    } else if (!version.ttl) {
      row.appendChild(el("span", { class: "hint" }, "graph dropped to save space"));
    }
    list.appendChild(row);
  });
}

/* What a past assessment said, without adopting it.
 *
 * Read-only by construction: it renders into the history panel and touches
 * neither the editor nor the canvas, so looking costs nothing and there is
 * nothing to undo afterwards. Restore stays a separate, deliberate act. */
function previewVersion(version) {
  const panel = $("#history-preview");
  panel.innerHTML = "";

  const versions = VersionHistory.list();
  const index = versions.findIndex((v) => v.fingerprint === version.fingerprint);
  const earlier = versions[index + 1] || null;

  panel.appendChild(el("div", { class: "hv-head" }, [
    el("strong", {}, `v${version.v}`),
    el("span", { class: "dim" }, shortTime(version.at)),
    el("span", { class: "dim" }, version.cause || ""),
    el("span", { class: "stat" },
      `${version.counts.findings != null ? version.counts.findings : "?"} findings`),
  ]));

  const stored = version.findings || [];

  /* What moved, by finding id - the same set difference the summary row uses,
   * because a version is mostly interesting next to the one before it. */
  if (earlier) {
    const before = new Set(earlier.findingIds || []);
    const now = new Set(version.findingIds || []);
    const labelOf = new Map(
      [...stored, ...(earlier.findings || [])].map((f) => [f.id, f.label])
    );
    const cleared = [...before].filter((id) => !now.has(id));
    const raised = [...now].filter((id) => !before.has(id));

    [[`cleared since v${earlier.v}`, cleared, "cleared"],
     ["newly raised", raised, "raised"]].forEach((group) => {
      const [title, ids, cls] = group;
      if (!ids.length) return;
      panel.appendChild(el("div", { class: `hv-group ${cls}` }, [
        el("div", { class: "hv-group-title" }, `${ids.length} ${title}`),
        ...ids.map((id) => el("div", { class: "hv-item" }, labelOf.get(id) || id)),
      ]));
    });
    if (!cleared.length && !raised.length) {
      panel.appendChild(el("p", { class: "hint" },
        `Nothing moved between v${earlier.v} and v${version.v}.`));
    }
  }

  if (stored.length) {
    panel.appendChild(el("div", { class: "hv-group" }, [
      el("div", { class: "hv-group-title" }, `all ${stored.length} findings in this version`),
      ...stored.map((f) => el("div", { class: "hv-item dim" }, f.label)),
    ]));
  } else {
    panel.appendChild(el("p", { class: "hint" },
      "This version's findings were shed to save space; its counts are kept."));
  }
  panel.classList.remove("hidden");
}
