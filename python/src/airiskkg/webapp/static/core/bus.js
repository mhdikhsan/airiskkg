/* Announcing that something happened, for the cases where calling the
 * other panel directly would make each of them need the other.
 */

/* A very small publish/subscribe, so two panels can say what happened rather
 * than call each other.
 *
 * It earns its place on one case: narrowing to an architecture has to redraw
 * the canvas AND the findings list, and the two places a reader can do it from
 * are those same two panels. Calling across made each of them depend on the
 * other, which is a cycle in any file layout and was only invisible while
 * everything lived in one file. They announce it now, and whoever wired the
 * page up listens. */
const listeners = new Map();

export function on(event, handler) {
  if (!listeners.has(event)) listeners.set(event, []);
  listeners.get(event).push(handler);
}

export function emit(event, detail) {
  (listeners.get(event) || []).forEach((handler) => handler(detail));
}
