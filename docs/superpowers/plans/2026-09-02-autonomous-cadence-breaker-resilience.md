# Implementation Plan: Autonomous Cadence-Breaker Resilience & Self-Healing Engine

**Spec:** `docs/superpowers/specs/2026-09-02-autonomous-cadence-breaker-resilience-design.md`  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: Implement Markdown Table & Append-Only Auto-Rebaser (`synlynk/rebase.py`)**
  - Implement `auto_rebase_markdown_conflicts(repo_path, branch, target_branch="main")` to resolve pure markdown table/append conflicts in `docs/blog/README.md`, `project-docs/memory.md`, and `CHANGELOG.md`.
  - Wire into `synlynk pr check` and QA merge workflow.
  - Add unit tests in `tests/test_rebase.py`.

- [ ] **Task 2: Active Job Circuit Breaker & Stalled Loop Killer**
  - Extend `synlynk/sentinel.py` to monitor active child processes and terminate subagents when tokens exceed 500k with 0 files touched or cost exceeds $5.00.
  - Log stack trace telemetry to `state.db` and reset story status to `stalled_aborted`.
  - Add unit tests in `tests/test_sentinel.py`.

- [ ] **Task 3: Dynamic Harness Failover on Startup Crash**
  - In `synlynk/dispatch.py`, detect non-zero startup exit within 10s and automatically failover to secondary harness in the capability matrix (Codex -> Agy -> Claude).
  - Add unit tests in `tests/test_dispatch.py`.

- [ ] **Task 4: SRE Zombie PID & Leaked Worktree Reaper**
  - Extend `_reconcile_daemon_jobs()` in `synlynk/jobs.py` to check OS process tables, mark dead PIDs as `killed_zombie`, and run `git worktree remove --force`.
  - Add unit tests in `tests/test_jobs.py`.

- [ ] **Task 5: Documentation, Blog Post, and Verification**
  - Author blog post `docs/blog/163-pr1346-cadence-breaker-resilience.md` and index in `docs/blog/README.md`.
  - Ensure all pytest tests pass.
