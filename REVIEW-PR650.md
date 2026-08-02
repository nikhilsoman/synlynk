# Review: PR #650

## Verdict: APPROVE

Non-authoring technical review of Grok's fix for #648.

### Blocking findings

None.

### Code review

- `_get_db()` now catches `OSError`, covering `EROFS` as well as the existing `PermissionError` case.
- `sqlite3.OperationalError` remains handled for an existing-but-unwritable primary directory.
- The fallback is the requested repository-local `.synlynk/state.db` path.
- The fallback warning includes the primary path, fallback path, and explicit "no project state" / "falling back" wording.
- If the fallback also fails, the second exception is re-raised.
- Regression coverage includes EROFS, PermissionError, SQLite OperationalError, and dual failure.
- The diff is scoped to `_get_db()`, focused tests, and `docs/blog/92-pr650-sandbox-db-fallback.md`; it does not expand into dispatch shared-state design.

### Verification evidence

- `git log -3 --oneline` confirms the PR commits are present; `git diff origin/main...HEAD --stat` shows only the three scoped files.
- `python3 -m pytest tests/test_get_db_sandbox_fallback.py -v`: **4 passed**.
- `python3 -m pytest tests/test_capability_scoring.py -v`: **61 passed**.
- `python3 -m pytest tests/test_capability_scoring.py -k 'test_get_db_creates_state_db' -v`: **1 passed**.
- `python3 -m pytest tests/test_agent_quota_tracking.py -k 'cmd_status_crashes_with_unable_to_open_d' -v`: **0 selected, 54 deselected**; no matching test exists in this checkout.
- `synlynk pr check` could not complete because the installed executable resolves to an older package copy and raises the known sandbox error: `sqlite3.OperationalError: unable to open database file`. This is the limitation described in #648 and was recorded rather than treated as a PR regression.

### Review checklist

- [x] Non-authoring review completed.
- [x] Scope checked against #648.
- [x] Focused regression tests pass.
- [x] Broader capability-scoring tests pass.
- [x] No blocking findings.
- [x] APPROVE COMMENT is appropriate; do not use `--approve` under the shared GitHub identity constraint.
