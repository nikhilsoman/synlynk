# Implementation Plan: PM Autonomous Backlog Triaging & Living Story Formation Engine

**Issue:** [#1340](https://github.com/nikhilsoman/synlynk/issues/1340)  
**Spec:** `docs/superpowers/specs/2026-08-31-governs-backlog-automation-design.md`  
**Goal:** `goal-6733bbf1` (state.db is the sole mutation point for todo/roadmap)  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: GitHub Issue Ingestion & Deduplication Classifier (`synlynk/backlog.py`)**
  - Implement `fetch_open_github_issues()` and semantic/SHA-256 deduplication against existing `state.db` stories and closed PRs.
  - Add SQLite schema migrations in `synlynk/db.py` for `backlog_items` and ingestion fingerprints.
  - Add unit tests in `tests/test_backlog.py`.

- [ ] **Task 2: Semantic Goal Alignment & Story Synthesizer**
  - Implement `synthesize_story_from_issue(issue_dict)` generating structured stories with role assignment (`dev`, `qa`, `architect`, `pm`), complexity tiers (Tier 1/2/3), and testable acceptance criteria.
  - Automatically map stories to active roadmap goals (`goal-005ea87d`, `goal-adb60ccc`, `goal-ef42902a`).
  - Add unit tests in `tests/test_backlog.py`.

- [ ] **Task 3: PM Autonomous Triage CLI & Sweep Integration**
  - Register CLI commands in `synlynk/cli.py` and `synlynk/taxonomy.py`:
    - `synlynk backlog ingest [--sync-github]`
    - `synlynk backlog triage`
    - `synlynk backlog auto-promote`
  - Wire into `synlynk tpm sweep` to automatically pick up newly ready stories.

- [ ] **Task 4: Documentation, Blog Post, and Full Suite Verification**
  - Author blog post `docs/blog/166-pr1349-pm-backlog-triage-engine.md` and index in `docs/blog/README.md`.
  - Update `project-docs/memory.md` and devlogs. Ensure all pytest tests pass.
