/* Publish/subscribe. Exists so canvas and findings need not import each
 * other - see test_webapp_module_layout.py::test_the_module_graph_has_no_cycles. */
const listeners = new Map();

export function on(event, handler) {
  if (!listeners.has(event)) listeners.set(event, []);
  listeners.get(event).push(handler);
}

export function emit(event, detail) {
  (listeners.get(event) || []).forEach((handler) => handler(detail));
}
