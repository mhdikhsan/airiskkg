# Local scripts

Gitignored except for this file. Put one-off and personal scripts here — a
scratch SPARQL runner, an export for a slide, an analysis you ran once to
answer a question — so that `git add -A` cannot carry them onto main.

`python/scripts/` one level up is the opposite: tracked tooling, and a script
earns its place there by being depended on.

- a test imports it — `validate_graphs.py`, `normalize_t4b.py`,
  `run_competency_questions.py`
- a doc says "regenerate with" — `generate_mapping_provenance.py`
- it rewrites a tracked file — `generate_mit_action_layer.py` writes
  `ontology/taxonomy/mit_mitigation_action.ttl`, `generate_risk_control_linkage.py`
  writes `docs/reference/risk_control_linkage.md`

Living here now: `export_ontology.py`, `pattern_provenance_worklist.py` and
`role_provenance_export.py` — nothing imports them, no doc regenerates from them,
and they write to `outputs/` or a scratch CSV. The last two were tracked until
2026-09-08; moving them here stages their deletion, which is the intent.

`export_ontology.py` is the case worth remembering: it meets none of the three. Nothing imports it, its output goes to
gitignored `outputs/`, and the only documents naming it were written in the same
change that added the script - a doc pointing at a script is not a dependency
when you wrote both. Reproducibility argues for tracking the ontology, not the
convenience script that reformats it for a viewer.

Two rules worth knowing before moving anything:

- **`.gitignore` does not untrack what is already committed.** Adding a pattern
  for a file that is already on main changes nothing; that needs
  `git rm --cached <path>`, which removes it from the repository for everyone.
- **Moving a tracked script breaks its callers.** `test_mapping_integrity.py`
  invokes `generate_mapping_provenance.py` by path, and `test_input_contract.py`
  imports `validate_graphs`. Rename with the callers in the same commit.
  Tried on 2026-09-08 and reverted the same day: moving the four depended-on
  scripts here cost a collection error in `test_competency_questions.py`, a failing
  `test_the_provenance_layer_is_in_sync_with_its_generator`, and six doc paths
  pointing into a gitignored directory. **A tracked file that says "regenerate with
  X" while X is gitignored cannot be regenerated from a clone** — the artifact stops
  being reproducible, which is the whole reason it is checked in.
