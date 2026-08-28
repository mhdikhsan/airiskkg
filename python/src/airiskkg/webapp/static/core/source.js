import { Editor } from "../lib/editor.js";

const sourceLines = new Map();

export function mapSource(elements) {
  sourceLines.clear();
  elements.filter((e) => e.line).forEach((e) => sourceLines.set(e.id, e.line));
}

export function revealInSource(ids) {
  const lines = (ids || []).map((id) => sourceLines.get(id)).filter(Boolean);
  if (lines.length) Editor.revealLines(lines);
}
