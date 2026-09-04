# Design Spec: Zero-Risk Onboarding & Instant First-Win Experience

**Date:** 2026-09-03  
**Status:** In Review  
**Authors:** [@nikhilsoman], [@agy], [@codex], [@claude]  
**Relates to:** `goal-85656c82`, `goal-06758149`, `goal-6733bbf1`  

---

## 1. Objective & Scope

Deliver a zero-friction, fail-safe onboarding flow for early adopters that transitions any repository into a fully configured Synlynk workspace in $<60\text{s}$ and delivers a tangible "First Win" automated PR in $<2\text{m}$ without risking user data.

---

## 2. Architecture & Components

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                      synlynk init / launch                       │
 └────────────────────────────────┬─────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
 ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
 │ Dirty-Tree    │        │ Zero-Config   │        │ First-Win     │
 │ Safety Guard  │        │ Stack & Model │        │ Diagnostic PR │
 ├───────────────┤        ├───────────────┤        ├───────────────┤
 │ Creates git   │        │ Probes CLI    │        │ Auto-fixes 1st│
 │ stash backup  │        │ harnesses &   │        │ discovered gap│
 │ before writes │        │ imports issues│        │ in <2 minutes │
 └───────────────┘        └───────────────┘        └───────────────┘
```

### A. Non-Destructive Dirty-Tree Safety Guard
- **Check:** Probes `git status --porcelain`.
- If dirty files or untracked state exist:
  - Automatically snapshots the tree state into `.synlynk/backups/init-<timestamp>.tar.gz` and git stash.
  - Guarantees zero overwrite of existing developer files.

### B. 1-Click Zero-Config Setup & GitHub Backlog Ingest
- Probes installed harnesses (`claude`, `codex`, `agy`, `grok`, `local`).
- Probes repository technology stack (Python, Node, Go, Rust, Ruby).
- Mints 8 standard workspace agent charters in `.synlynk/agents/`.
- Automatically calls `synlynk backlog ingest --sync-github` to import existing GitHub issues into `state.db`.

### C. "First Win" Instant Remediation Demo
- During onboarding, `synlynk scan` flags the highest-confidence low-hanging improvement (e.g. missing docstrings, test coverage gaps, or missing `.gitignore` rules).
- Prompts 1-click confirmation to dispatch the fix $\rightarrow$ executes in isolated worktree $\rightarrow$ passes tests $\rightarrow$ opens a GitHub PR with blog summary in $<2$ minutes.

---

## 3. Test & Verification Plan
- Unit tests in `tests/test_onboarding_safety.py` testing dirty-tree guards, stash backups, and zero-config wizard defaults.
