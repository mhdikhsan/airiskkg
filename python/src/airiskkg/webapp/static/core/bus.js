const listeners = new Map();

export function on(event, handler) {
  if (!listeners.has(event)) listeners.set(event, []);
  listeners.get(event).push(handler);
}

export function emit(event, detail) {
  (listeners.get(event) || []).forEach((handler) => handler(detail));
}
