"""The version history's logic, exercised outside a browser.

`test_webapp_static_wiring.py` says it plainly: there is no JavaScript test
runner here, so the browser code is only ever exercised by hand. That was
tolerable while the front end was rendering - a wrong pixel is visible. History
is not rendering. It decides whether a version is recorded at all, computes the
delta a reader will trust, and sheds data when the browser's storage fills up,
and every one of those fails silently and looks like nothing happened.

So this runs the real module under node, with localStorage stubbed, and skips
when node is unavailable rather than pretending the checks ran.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from airiskkg.paths import REPO_ROOT

HISTORY_JS = REPO_ROOT / "python" / "src" / "airiskkg" / "webapp" / "static" / "history.js"

HARNESS = """
import { pathToFileURL } from "node:url";

const store = {};
let budget = Number(process.env.BUDGET || 1e9);
global.window = {
  localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => {
      if (v.length > budget) { const e = new Error("quota"); e.name = "QuotaExceededError"; throw e; }
      store[k] = v;
    },
    removeItem: (k) => { delete store[k]; },
  },
};
// Imported dynamically, not with a static import: the stub above has to be in
// place before the module runs, and static imports are hoisted above it.
const { VersionHistory: H } = await import(pathToFileURL(process.env.HISTORY_JS).href);

const failures = [];
const check = (label, cond) => { if (!cond) failures.push(label); };

const v1 = H.record({ fingerprint: "aaa", counts: { findings: 17 },
                      findingIds: ["f1", "f2", "f3"], ttl: "x", cause: "loaded example" });
check("first record is v1", v1.v === 1);
check("first record has no delta", v1.delta === null);

const again = H.record({ fingerprint: "aaa", counts: { findings: 17 },
                         findingIds: ["f1", "f2", "f3"], ttl: "x" });
check("an unchanged graph is the same version", again.v === 1 && H.list().length === 1);

const v2 = H.record({ fingerprint: "bbb", counts: { findings: 15 },
                      findingIds: ["f1"], ttl: "y", cause: "applied Output validation" });
check("a changed graph is a new version", v2.v === 2);
check("delta counts what cleared", v2.delta.cleared === 2 && v2.delta.raised === 0);

const v3 = H.record({ fingerprint: "ccc", counts: { findings: 16 },
                      findingIds: ["f1", "f9"], ttl: "z" });
check("delta counts what was newly raised", v3.delta.raised === 1 && v3.delta.cleared === 0);
check("an unlabelled change still gets a cause", typeof v3.cause === "string" && v3.cause.length > 0);
check("list is newest first", H.list()[0].v === 3);
check("get finds a version by fingerprint", H.get("bbb").v === 2);
check("a record without a fingerprint is refused", H.record({ fingerprint: "" }) === null);

// Fill past the cap and past the storage budget at once.
budget = 40000;
for (let i = 0; i < 40; i += 1) {
  H.record({ fingerprint: "big" + i, counts: { findings: i }, findingIds: [], ttl: "z".repeat(3000) });
}
const after = H.list();
check("history stays within its cap", after.length <= H.LIMIT);
check("versions survive even when their graph is shed",
      after.length > 0 && after.every((v) => typeof v.v === "number" && v.counts));
check("the newest version is still restorable", after[0].ttl !== null);

H.clear();
check("clear empties it", H.list().length === 0);

if (failures.length) { console.log(failures.join("\\n")); process.exit(1); }
console.log("ok");
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")
def test_history_records_versions_computes_deltas_and_sheds_under_quota(tmp_path) -> None:
    harness = tmp_path / "harness.mjs"
    harness.write_text(HARNESS, encoding="utf-8")

    completed = subprocess.run(
        ["node", str(harness)],
        capture_output=True,
        text=True,
        env={"HISTORY_JS": str(HISTORY_JS), "PATH": __import__("os").environ.get("PATH", "")},
        timeout=60,
    )

    assert completed.returncode == 0, (
        "version history behaved wrongly:\n" + completed.stdout + completed.stderr
    )
