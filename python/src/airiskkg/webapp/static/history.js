
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
      const withLabels = trimmed.findIndex((v) => v.findings && v.findings.length);
      const withGraph = trimmed.findIndex((v) => v.ttl);
      if (withLabels !== -1 && trimmed.length > 1) {
        // Labels first: losing the ability to read v3 costs less than losing
        // the ability to restore it, and both cost less than losing v3.
        trimmed = trimmed.map((v, i) => (i === withLabels ? { ...v, findings: [] } : v));
      } else if (withGraph !== -1 && trimmed.length > 1) {
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

function record({ fingerprint, knowledgeBase, counts, findingIds, findings, ttl, cause }) {
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
    /* The labels too, so a version can be read without being restored.
     * Recording only ids meant the one way to see what a past assessment said
     * was to replace the graph on screen with it - which is a commitment, and
     * a poor way to answer "what changed". */
    findings: (findings || []).slice(0, 60),
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

export const VersionHistory = { record, list, get, clear, size, LIMIT };