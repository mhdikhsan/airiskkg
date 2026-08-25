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
