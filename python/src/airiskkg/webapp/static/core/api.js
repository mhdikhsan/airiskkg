/* Talking to the server: JSON in, JSON or a file out.
 */

import { $ } from "../core/dom.js";

export async function api(url, options) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export function postJson(url, body) {
  return api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export async function postForFile(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = /filename="([^"]+)"/.exec(disposition);
  return {
    blob: await res.blob(),
    findings: res.headers.get("X-PAIR-AI-Findings") || "0",
    matches: res.headers.get("X-PAIR-AI-Matches") || "0",
    filename: match ? match[1] : null,
  };
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  requestAnimationFrame(() => URL.revokeObjectURL(url));
}

export function exportBaseName() {
  const selected = $("#example-select");
  const name = selected && selected.value ? selected.value : "";
  return (name || "architecture").replace(/\.(ttl|turtle|nt)$/i, "");
}
