/* Assessment history: what the graph looked like, and what the assessment said,
 * each time it changed.
 *
 * Client-side on purpose, and not for convenience:
 *
 *   - The workbench has no authentication or sessions. A server-side store
 *     would mix one person's architectures with another's on any shared
 *     deployment, which is the hazard the app already guards against by
 *     defaulting local examples off for WSGI.
 *   - A version's label - "applied Output validation" - is only knowable here.
 *     The server sees a different Turtle document; it cannot tell an applied
 *     control from a hand edit. Without the label the history is a column of
 *     numbers, and the label is the part that makes it readable.
 *   - Recording costs nothing. The version identity is the input fingerprint
 *     the assessment already returns.
 *
 * What is stored is a summary, never the full answer. A full assessment payload
 * is ~300 KB, so twenty-five of them is ~7.5 MB against a ~5 MB budget; the
 * summary plus the graph itself is ~24 KB, so twenty-five fit in ~0.6 MB. That
 * is also why opening an old version never re-runs anything: an assessment is
 * ~2.6 s, a history click has to be instant.
 *
 * Exposes window.VersionHistory.
 */
(function () {
  "use strict";

  const KEY = "pair-ai.history.v1";
  const LIMIT = 25;

  function read() {
    try {
      const raw = window.localStorage.getItem(KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return []; // unreadable history is not worth breaking the app over
    }
  }

  function write(versions) {
    /* Trim oldest-first, and shed the stored graph before shedding a whole
     * version: losing the ability to restore v3 is a smaller loss than losing
     * the record that v3 happened at all. */
    let trimmed = versions.slice(-LIMIT);
    for (let attempt = 0; attempt < 40; attempt += 1) {
      try {
        window.localStorage.setItem(KEY, JSON.stringify(trimmed));
        return trimmed;
      } catch (error) {
        const withGraph = trimmed.findIndex((v) => v.ttl);
        if (withGraph !== -1 && trimmed.length > 1) {
          trimmed = trimmed.map((v, i) => (i === withGraph ? { ...v, ttl: null } : v));
        } else if (trimmed.length > 1) {
          trimmed = trimmed.slice(1);
        } else {
          return read(); // one version and it still will not fit: leave what is there
        }
      }
    }
    return trimmed;
  }

  /* A version is a graph state plus what the assessment said about it. The
   * fingerprint decides: re-assessing an unchanged graph is the same version,
   * not a new one. */
  function record({ fingerprint, knowledgeBase, counts, findingIds, ttl, cause }) {
    if (!fingerprint) return null;
    const versions = read();
    const latest = versions[versions.length - 1];
    if (latest && latest.fingerprint === fingerprint) return latest;

    const previous = latest ? new Set(latest.findingIds || []) : null;
    const now = new Set(findingIds || []);
    const entry = {
      v: (latest ? latest.v : 0) + 1,
      at: new Date().toISOString(),
      cause: cause || "edited by hand",
      fingerprint,
      knowledgeBase: knowledgeBase || null,
      counts: counts || {},
      findingIds: [...now],
      delta: previous
        ? {
            cleared: [...previous].filter((id) => !now.has(id)).length,
            raised: [...now].filter((id) => !previous.has(id)).length,
          }
        : null,
      ttl: ttl || null,
    };
    return write([...versions, entry]).slice(-1)[0];
  }

  function list() {
    return read().slice().reverse(); // newest first, the way it is read
  }

  function get(fingerprint) {
    return read().find((v) => v.fingerprint === fingerprint) || null;
  }

  function clear() {
    try {
      window.localStorage.removeItem(KEY);
    } catch (error) {
      /* nothing to do: an unwritable store is already empty as far as we care */
    }
  }

  function size() {
    try {
      return (window.localStorage.getItem(KEY) || "").length;
    } catch (error) {
      return 0;
    }
  }

  window.VersionHistory = { record, list, get, clear, size, LIMIT };
})();
