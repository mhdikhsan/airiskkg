import { postJson } from "../core/api.js";
import { setStatus } from "../core/status.js";
import { Editor } from "../lib/editor.js";
import { noteChange } from "./run.js";

let mutating = Promise.resolve();

export function runMutation(task) {
  const next = mutating.then(task, task);
  mutating = next.catch(() => {});
  return next;
}

// Edit an element from the popup.
export function applyEdit(elementId, edit) {
  return runMutation(async () => {
    try {
      const { ttl } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue(), op: "edit-element", element: elementId, ...edit,
      });
      noteChange("edited an element");
      Editor.setValue(ttl);
      setStatus("ok", "Element updated — Run assessment to see findings");
    } catch (error) {
      setStatus("error", "Could not update element: " + error.message.split("\n")[0]);
    }
  });
}

// Delete an element and every edge touching it.
export function applyDelete(elementId) {
  return runMutation(async () => {
    try {
      const { ttl } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue(), op: "delete-element", element: elementId,
      });
      noteChange("deleted an element");
      Editor.setValue(ttl);
      setStatus("ok", "Element deleted");
    } catch (error) {
      setStatus("error", "Could not delete: " + error.message.split("\n")[0]);
    }
  });
}

// Add a BEAM flow edge from a canvas port-drag.
export function applyConnect(triple) {
  return runMutation(async () => {
    try {
      const { ttl } = await postJson("/api/graph-edit", {
        ttl: Editor.getValue(), op: "add-edge", ...triple,
      });
      noteChange(`connected: ${triple.predicate}`);
      Editor.setValue(ttl);
      setStatus("ok", `Connected: ${triple.predicate}`);
    } catch (error) {
      setStatus("error", "Could not connect: " + error.message.split("\n")[0]);
    }
  });
}
