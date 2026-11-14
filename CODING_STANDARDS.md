# Coding standards

These rules apply to every file a pull request changes. Each one exists because
its absence caused a real problem. Files a pull request does not touch are not
held to them (see "Known violations").

## Lint and format

Run both from the repository root, on the files you changed, before opening the
pull request. Both must exit 0.

```
ruff check <changed files>
ruff format --check <changed files>
```

- No function or class defined twice in a module (`F811`), and no name used
  without an import (`F821`). A merge once left two `build_narrative`
  definitions in `src/engine/discovery.py`; the later one silently replaced the
  real one, and a missing `Region` import went unnoticed because annotations are
  not evaluated at import time.
- Imports sorted (`I001`). `ruff check --fix` does it.
- The line length is pinned in `pyproject.toml`; do not override it in your
  editor.

## After a merge

A merge that touches a file you own is not done until you have re-run the full
suite (`pytest`) and `ruff check` on that file. Two branches can each be green
and still break each other.

## Tests

- Drive new behaviour test-first at the seam the spec assigns it (Seam 1 is the
  engine's public interface, Seam 2 the HTTP API), and watch the test fail for
  the right reason before writing the code.
- Cover each integration between two tickets with a test that goes through both
  (for example, a Candidate Discovery from `find_candidate_discoveries` carries
  the narrative from `build_narrative`).
- Check the tests you wrote by mutation: break the code on purpose (change a
  rounding mode, swap first and last, drop a sentence) and confirm a test fails,
  then revert. Report any mutation that survives.
- Numbers shown to students come from computed values only (ADR 0001), so a test
  uses values that differ from any hard-coded stub value.

## Evidence

Every pull request that closes a ticket links an evidence pack: the claims, the
commands run with their exit codes, what was not run, and the revision it was
produced on. Regenerate the pack when the revision changes.

## Known violations

These files predate this document and are cleaned up in their own change, not in
unrelated pull requests:

- `tests/test_contracts.py:120` (`RUF015`)
- `tests/test_engine_isolation.py:43` (`PLW1510`)
- `tests/test_catalog.py` (`ruff format --check`)
