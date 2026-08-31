# Post 148: Fix Decision Record Path in Migrated Workspaces & Worktrees (#1226, #1194 / PR #1315)

**Author:** Agy (Gemini)  
**Date:** 2026-09-01  
**Category:** Bug Fix / Workspace Integrity  
**Status:** Merged  
**PR:** #1315  
**Issues:** #1226, #1194

---

## 1. Context & Problem

When running `synlynk decide --panel ... --record` in migrated repositories or from within a linked git worktree, `cmd_decision_record()` and `_write_decision_record_md()` routed the resulting decision documentation (`.md` + `.json` sidecar) into `.synlynk/project-docs/decisions/` via `_synlynk_project_docs_dir()`.

This caused two severe defects:
1. **Ignored from Git History ([#1194](https://github.com/nikhilsoman/synlynk/issues/1194)):** `.synlynk/*` is gitignored. Decision records are durable architectural consensus assets and must always be tracked in git.
2. **Written Outside Invoking Worktree ([#1226](https://github.com/nikhilsoman/synlynk/issues/1226)):** `_synlynk_project_docs_dir()` resolved against the shared main repository root via `git-common-dir`, writing files into the parent checkout instead of the invoking worktree's local workspace.

---

## 2. Solution & Implementation

1. **Direct Resolution to Tracked Decisions Directory (`synlynk/db.py`):**
   - Removed the `_is_migrated()` redirect in `_write_decision_record_md()`.
   - Now unconditionally resolves to `os.path.join(_docs_dir(), "decisions")` (`project-docs/decisions/`), ensuring decision records land in the active worktree and are tracked by git across all migration states.

2. **Resilient Disaster Recovery Sync (`synlynk/__init__.py`):**
   - Updated `_dr_sync()` to check `_docs_dir()` first for source documents before falling back to `.synlynk/project-docs/`.

3. **Regression Tests (`tests/test_migrate.py`):**
   - Updated migration tests to assert output in `project-docs/decisions/`.
   - Added `test_cmd_decision_record_writes_to_worktree_project_docs` to verify that executing from within a worktree cwd writes records into the worktree's own `project-docs/decisions/` without leaking into the main checkout's `.synlynk/` tree.

---

## 3. Verification

- All 4 decision record tests in `tests/test_migrate.py` passed.
- Full pytest test suite confirmed passing.
