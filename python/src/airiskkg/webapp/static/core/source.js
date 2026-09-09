/* Where each element was written, so a click on a canvas can reach its line. */
import { Editor } from "../lib/editor.js";

const byLayer = new Map();

export function mapSource(elements, layer = "architecture") {
  const lines = new Map();
  (elements || []).filter((e) => e && e.line).forEach((e) => lines.set(e.id, e.line));
  byLayer.set(layer, lines);
}

export function revealInSource(ids) {
  const lines = (ids || [])
    .map((id) => {
      for (const map of byLayer.values()) {
        if (map.has(id)) return map.get(id);
      }
      return null;
    })
    .filter(Boolean);
  if (lines.length) Editor.revealLines(lines);
}
