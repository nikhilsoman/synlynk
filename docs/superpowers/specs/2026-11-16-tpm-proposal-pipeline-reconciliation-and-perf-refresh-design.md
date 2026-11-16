# Design Spec — TPM Proposal Pipeline Dynamic Reconciliation & Perf Refresh

**Date:** 2026-11-16  
**Status:** Approved  
**Author:** Agy (AntiGravity / Gemini)  
**Parent Goal:** `goal-2458-master-roadmap` / `goal-8f64eff5` (Platform Health & Performance)  
**Target Milestone:** `v0.37.1`  

---

## 1. Context & Problem Statement

Following the release of **v0.37.0** ("Autonomous Operations & Universal Governance"), a systematic audit of the release proposal mechanism (`synlynk/tpm_sweep.py`) and active approval tickets surfaced three critical governance and data-quality gaps:

1. **Version Drift in Open Proposals:**
   GitHub Issue [#5285](https://github.com/nikhilsoman/synlynk/issues/5285) was opened on 2026-11-15 as `[Proposal] v0.36.1: Milestone v0.36.1` (tracked in `approval_tickets` ticket #13). Because `v0.37.0` has already been cut and merged to `main`, release `v0.36.1` is semantically invalid. The open proposal was stranded across a version boundary without an automated synchronization or reconciliation mechanism.

2. **Hardcoded Metadata Freeze at `v0.33.0`:**
   In `synlynk/tpm_sweep.py:683-704`, `roadmap_metadata` was statically mapped up to `v0.33.0`. For any release beyond `v0.33.0`, the system defaulted to `theme: "Milestone {rel_ver}"`, bypassing the dynamic Approach C `roadmap_arcs` view and `goals` table.

3. **Backlog Dredging via `rowid ASC` Ordering:**
   `package_next_release_proposal()` retrieved constituent stories using `ORDER BY ..., rowid ASC LIMIT 5`. Because it ordered by ancient insertion order (`rowid ASC`), it continually dredged up 2-month-old backlog items from September 2026 (such as `#4290`, `#4291`, `#2901`, `#4361`, `#4362`) rather than prioritizing active roadmap goals.

4. **Zombie Stories Under Completed Goals:**
   Stories `#4361` (`story-issue-1654`) and `#4362` (`story-issue-1655`) belong to `goal-d3333441` ("v0.24.0: Autonomous Platform..."), which was marked `status: 'done'` weeks ago. Because `package_next_release_proposal()` did not verify the parent goal's status, stories under completed goals were still packaged into modern proposals.

5. **Stale Specs for Performance & Swarm Stories:**
   - `#4290` (`story-issue-1496`): Evaluated in `docs/testing/pytest-xdist-evaluation-1496.md` at 2,689 tests. Today's suite has 5,764 tests; the evaluation spec requires a currency refresh.
   - `#4291` (`story-issue-1497`): CLI startup profiling needs an explicit benchmark spec and latency threshold.
   - `#2901` (`story-3aeb1c7a`): Cites `Milestone v0.21.0` in its title; needs re-anchoring to Theme 6 (Cloud Swarms / `goal-d5323df6`).

---

## 2. Architectural Design & Solutions

### Part A: Dynamic Approach C Integration in `synlynk/tpm_sweep.py`

1. **Dynamic Theme Resolution:**
   Replace the hardcoded `roadmap_metadata` dictionary with a dynamic query against `roadmap_arcs` / `goals`:
   ```python
   def _resolve_roadmap_metadata(rel_ver: str, conn, repo_root: str = ".") -> dict:
   ```
   - Query `SELECT phase_title FROM goals WHERE arc_version=? AND phase_title IS NOT NULL LIMIT 1`, `(rel_ver,)`.
   - If not found, look up the highest-priority open arc from the Approach C `roadmap_arcs` view (`SELECT arc_version, phase_title FROM roadmap_arcs WHERE status != 'shipped' ORDER BY roadmap_priority ASC LIMIT 1`).
   - Use the resolved `phase_title` as the proposal theme.

2. **Goal-Aware & Priority-Ordered Story Selection:**
   Update the candidate story selection query in `package_next_release_proposal()`:
   ```sql
   SELECT s.story_id, s.title, s.role, s.estimated_tokens, s.gh_issue 
   FROM stories s
   LEFT JOIN goals g ON s.goal_id = g.goal_id
   WHERE (s.readiness='advisory' OR (s.readiness IN ('ready', 'draft') AND s.status NOT IN ('done', 'archived')))
     AND (g.status IS NULL OR g.status NOT IN ('done', 'archived'))
   ORDER BY 
     CASE s.readiness WHEN 'advisory' THEN 1 WHEN 'ready' THEN 2 ELSE 3 END,
     COALESCE(g.roadmap_priority, 9999) ASC,
     COALESCE(s.priority, 0) DESC,
     s.rowid DESC
   LIMIT 5
   ```
   - Excludes any story whose parent goal is `done` or `archived`.
   - Orders by `roadmap_priority ASC`, prioritizing active roadmap arcs over unplaced legacy stories.
   - Orders secondary by `s.priority DESC` and recent activity (`s.rowid DESC`) instead of `rowid ASC`.

3. **Stale Proposal Auto-Reconciliation:**
   In `dispatch_tpm_advisory_proposal()`:
   - Check if an open proposal ticket exists in `approval_tickets` whose `story_id` is less than `rel_ver` (e.g. `v0.36.1` < `v0.37.1`).
   - Mark stale older proposals as `superseded` (`UPDATE approval_tickets SET status='superseded' WHERE action='release_proposal' AND status='open' AND story_id < ?`).

---

### Part B: Backlog Triage & Reconciliations

1. **Close Zombie Stories `#4361` & `#4362`:**
   - Both tasks resolved LIVE-1 preflight and DR recovery, belonging to completed `goal-d3333441`.
   - Update `status='done'`, `readiness='done'` in `state.db` and close GitHub issues via `synlynk gh`.

2. **Re-anchor `#2901` (`story-3aeb1c7a`):**
   - Retitle from `Milestone v0.21.0: Sprint 1 Plan...` to `Theme 6: Ephemeral Swarm Execution Infrastructure Foundation`.
   - Re-link parent goal to `goal-d5323df6` (Theme 6 / Swarms).

3. **Reconcile Proposal Issue #5285 / Ticket #13:**
   - Update `approval_tickets` Ticket #13: `story_id='v0.37.1'`, `theme='Performance & Reliability'`.
   - Update GitHub Issue #5285 title to `[Proposal] v0.37.1: Performance & Reliability`.

---

### Part C: Spec Refresh for Perf Stories

1. **#4290 (`story-issue-1496`): Pytest-xdist Suite Evaluation at 5.7k Tests:**
   - Refresh `docs/testing/pytest-xdist-evaluation-1496.md` with 2026-11 measurements (5,764 tests).
   - Verify bounded `-n 4` vs `-n 8` on multi-core test runs and document state isolation requirements.

2. **#4291 (`story-issue-1497`): CLI Startup Latency Profiling:**
   - Establish `tests/perf/test_cli_startup.py` benchmark.
   - Validate `python3 bin/synlynk.py --version` startup within latency threshold (<150ms).

---

## 3. Verification & Acceptance Criteria

1. `package_next_release_proposal()` dynamically discovers version `v0.37.1`.
2. Stories under completed goals (`status='done'`) are excluded from proposal packaging.
3. Candidate stories order by `roadmap_priority` and recent activity, preventing legacy dredging.
4. Issue #5285 updated to `v0.37.1`.
5. Unit tests in `tests/test_tpm_l1_advisory.py` verify dynamic theme resolution and priority ordering.
