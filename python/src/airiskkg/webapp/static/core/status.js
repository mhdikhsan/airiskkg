/* The status line, and the line number read out of a parser error. */

import { $ } from "./dom.js";

export function setStatus(state, message, stats) {
  const dot = $("#status-dot");
  dot.className = `status-dot ${state}`;
  $("#status-text").textContent = message;
  $("#status-stats").textContent = stats || "";
}

export function parseErrorLine(message) {
  const match = /line (\d+)/i.exec(message);
  return match ? Number(match[1]) : null;
}
