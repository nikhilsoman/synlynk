# Implementation Plan: Zero-Risk Onboarding & Instant First-Win Experience

**Spec:** `docs/superpowers/specs/2026-09-03-zero-risk-onboarding-and-first-win-design.md`  
**Date:** 2026-09-03  

---

## Tasks

- [ ] **Task 1: Dirty-Tree Safety Guard & Backup Manager (`synlynk/wizard.py`)**
  - Implement `guard_dirty_worktree()` in `synlynk/wizard.py` creating `.synlynk/backups/init-<timestamp>.tar.gz` and git stash prior to any workspace configuration write.
  - Add unit tests in `tests/test_onboarding_safety.py`.

- [ ] **Task 2: Zero-Config Discovery & Instant Setup**
  - Streamline `cmd_wizard_init()` in `synlynk/wizard.py` to auto-detect installed CLI harnesses (`claude`, `codex`, `agy`, `grok`, `local`), codebase stack, and provision standard agent charters in $<5\text{s}$.
  - Auto-invoke `synlynk backlog ingest --sync-github` to import existing GitHub issues into `state.db`.
  - Add unit tests in `tests/test_onboarding_safety.py`.

- [ ] **Task 3: "First Win" Instant Remediation Demo**
  - In `synlynk/wizard.py` / `synlynk/launch.py`, prompt the user to auto-remediate the top discovered scan finding and dispatch an automated fix to open a GitHub PR in $<2$ minutes.
  - Add unit tests in `tests/test_onboarding_safety.py`.

- [ ] **Task 4: Documentation, Blog Post, and Verification**
  - Author blog post `docs/blog/169-pr1352-zero-risk-onboarding-first-win.md` and index in `docs/blog/README.md`.
  - Ensure all pytest tests pass.
