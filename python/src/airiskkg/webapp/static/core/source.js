/* Where each element was written, so clicking one puts the cursor on
 * the line that declares it.
 */

import { Editor } from "../editor.js";

/* Where each element was written, so clicking it on a canvas can put the
 * cursor on the line that declares it. Rebuilt rather than reassigned: the map
 * is what other code holds on to. */
const sourceLines = new Map();

export function mapSource(elements) {
  sourceLines.clear();
  elements.filter((e) => e.line).forEach((e) => sourceLines.set(e.id, e.line));
}

export function revealInSource(ids) {
  const lines = (ids || []).map((id) => sourceLines.get(id)).filter(Boolean);
  if (lines.length) Editor.revealLines(lines);
}
