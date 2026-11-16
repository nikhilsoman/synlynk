# Implementation Plan — TPM Proposal Pipeline Dynamic Reconciliation & Perf Refresh

**Date:** 2026-11-16  
**Status:** Approved  
**Author:** Agy (AntiGravity / Gemini)  
**Spec Reference:** `docs/superpowers/specs/2026-11-16-tpm-proposal-pipeline-reconciliation-and-perf-refresh-design.md`  

---

## Proposed Changes

### 1. `synlynk/tpm_sweep.py`
- Add `_resolve_roadmap_metadata(rel_ver: str, conn, repo_root: str = ".") -> dict` to query `roadmap_arcs` / `goals` for dynamic theme, bookends, and active priority.
- Update `package_next_release_proposal()`:
  - Join `stories` to `goals` on `s.goal_id = g.goal_id`.
  - Filter out stories where `g.status IN ('done', 'archived')`.
  - Order by `CASE s.readiness WHEN 'advisory' THEN 1 WHEN 'ready' THEN 2 ELSE 3 END, COALESCE(g.roadmap_priority, 9999) ASC, COALESCE(s.priority, 0) DESC, s.rowid DESC LIMIT 5`.
  - Use `_resolve_roadmap_metadata()` to populate proposal theme and bookends.
- Update `dispatch_tpm_advisory_proposal()`:
  - Supersede stale open proposals where `story_id < rel_ver`.

### 2. State & Backlog Housekeeping
- Close `#4361` (`story-issue-1654`) and `#4362` (`story-issue-1655`) in `state.db` and GitHub.
- Retarget `#2901` (`story-3aeb1c7a`) to `goal-d5323df6` (Theme 6 / Swarms) and update title.
- Reconcile `approval_tickets` Ticket #13 and GitHub Issue #5285 to `v0.37.1`.

### 3. Perf Specs & Benchmarks
- Refresh `docs/testing/pytest-xdist-evaluation-1496.md` with 5,764 test suite findings.
- Add CLI startup profiling benchmark in `tests/test_cli_startup_perf.py`.

### 4. Tests
- Add unit tests in `tests/test_tpm_l1_advisory.py` verifying:
  - Dynamic theme resolution from `roadmap_arcs` and `goals`.
  - Exclusion of stories under completed goals.
  - Sorting candidates by roadmap priority.
  - Auto-superseding stale proposals.

---

## Verification Plan

### Automated Suites
- `pytest tests/test_tpm_l1_advisory.py`
- `pytest tests/test_docs_sync.py`
- `pytest tests/test_cli_startup_perf.py`
- Full CI matrix on PR check.
