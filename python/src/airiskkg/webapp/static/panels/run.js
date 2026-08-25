/* Run identity: whether what is on screen still matches what was
 * assessed, and what changed between one run and the next.
 */

import { postJson } from "../core/api.js";
import { $ } from "../core/dom.js";
import { state } from "../state.js";

let staleTimer = null;

export function noteChange(cause) {
  state.pendingCause = cause;
}

export function setStale(isStale) {
  $("#findings-stale").classList.toggle("hidden", !isStale);
}

export function scheduleStaleCheck(ttl) {
  if (!state.lastRun) return;
  clearTimeout(staleTimer);
  staleTimer = setTimeout(async () => {
    try {
      const { fingerprint } = await postJson("/api/fingerprint", { ttl });
      setStale(fingerprint !== state.lastRun.fingerprint);
    } catch (error) {
    }
  }, 400);
}

export function runDelta(findings) {
  if (!state.lastRun) return null;
  const now = new Set(findings.map((f) => f.id));
  const cleared = [...state.lastRun.findingIds].filter((id) => !now.has(id)).length;
  const raised = [...now].filter((id) => !state.lastRun.findingIds.has(id)).length;
  return { cleared, raised };
}

export function renderKnowledgeBaseBadge(run) {
  const badge = $("#kb-badge");
  const kb = run && run.knowledgeBase;
  if (!kb) { badge.classList.add("hidden"); return; }
  const parts = [`library ${kb.fingerprint}`];
  if (kb.revision) parts.push(kb.dirty ? `${kb.revision}+` : kb.revision);
  parts.push(`${kb.motifs} motifs · ${kb.riskPatterns} risk patterns`);
  badge.textContent = parts.join(" · ");
  badge.classList.toggle("dirty", Boolean(kb.dirty));
  badge.classList.remove("hidden");
}
