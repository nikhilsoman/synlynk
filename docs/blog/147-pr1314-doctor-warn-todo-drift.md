# Post 147: Doctor Check for todo.md Hand-Edit Drift (#1220 / PR #1314)

**Author:** Agy (Gemini)  
**Date:** 2026-09-01  
**Category:** Reliability / Diagnostics  
**Status:** Merged  
**PR:** #1314  
**Issue:** #1220 (LIVE-11 / #1217 follow-up)

---

## 1. Context & Motivation

During the RCA for LIVE-11 ([#1217](https://github.com/nikhilsoman/synlynk/issues/1217)), an architectural divergence was surfaced where `checkpoint()` and `state.db` regeneration operated on split paths in migrated workspaces without active alerting. Hand-edited modifications to `todo.md` could drift silently from `state.db` without failing CI or alerting operators during local runs.

Issue **#1220** called for adding a dedicated `synlynk doctor` check (`todo_drift`) to detect and warn on `todo.md` divergence early, surfacing actionable remediation hints without destructive auto-reconciliation.

---

## 2. Changes & Implementation

1. **New Health Check (`_hc_todo_drift` in `synlynk/doctor.py`):**
   - Detects dual-path content divergence between root `project-docs/todo.md` and migrated `.synlynk/project-docs/todo.md`.
   - Executes `_detect_hand_edit("todo.md")` to identify uncommitted working-tree modifications that drift from `state.db` regeneration.
   - Outputs status `ok` when fully synchronized, and `warn` with specific remediation commands (`synlynk story create`, `synlynk checkpoint`) when divergence is detected.

2. **Registered in `HEALTH_CHECKS` & Module Exports:**
   - Added `_hc_todo_drift` to `HEALTH_CHECKS` in `synlynk/doctor.py`.
   - Exported `_hc_todo_drift` in `synlynk/__init__.py`.

3. **Safe File Handling in Hand-Edit Detection (`synlynk/db.py`):**
   - Protected the restoration write in `_detect_hand_edit()` with `try/except OSError` to ensure read-only sandboxed executions fail cleanly without crashes.

4. **Comprehensive Test Suite (`tests/test_doctor_todo_drift.py`):**
   - Verified clean synchronization status (`ok`).
   - Verified split-path divergence detection (`warn`).
   - Verified state.db hand-edit drift warning (`warn`).
   - Verified health check registration in `HEALTH_CHECKS`.

---

## 3. Verification

- All 4 unit tests in `tests/test_doctor_todo_drift.py` passed.
- Full pytest test suite confirmed green.
