/* The status line under the editor, and reading a line number out of a
 * parser error so the editor can point at it.
 */

import { $ } from "../core/dom.js";
import { state } from "../state.js";

//status bar
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
