# Design Spec: Deep Review 2026-10-16 Remaining P0 Tranche (P0-6 to P0-10)

**Date:** 2026-10-17  
**Status:** In Review / Ready for Implementation  
**Tracking Issue:** [gh:#2384](https://github.com/nikhilsoman/synlynk/issues/2384)  
**Parent Epic:** `[Epic] Deep Review 2026-10-16: Core Architectural & Security Hardening (P0-1 to P0-10)`  
**Scope:** P0-6 (`capability report`), P0-7 (Distribution & VS Code), P0-8 (Token/Cost Honesty), P0-9 (Onboarding Hardening), P0-10 (Goal Reconciliation)  

---

## 1. Context & Motivation

The Deep Architectural Review 2026-10-16 converged on a central imperative: Synlynk possesses a world-class verification kernel (5 invariants, single-writer WAL, three-branch effect verification), but enterprise adoption and developer preview readiness require extracting and hardening the kernel while clearing operational debt.

Tranche 1 (P0-1 through P0-5) achieved:
- P0-1: State.db shard consolidation and migration 22 registration (PR #2371).
- P0-2: Authoritative job-status reconciliation and zero-diff effect oracle fixes (PR #2375).
- P0-3: Login-shell shim isolation, dynamic token refresh, SQLite row hardening, daemon worktree safety (PR #2376, PR #2377).
- P0-4: Surface tiering into 8 core daily verbs and `--experimental` quarantine (PR #2379).
- P0-5: Safe-by-default permissions with role-scoped profiles, Claude settings injection, and strict bypass audits (PR #2383).

This specification establishes the architectural designs, file targets, and verification contracts for the remaining items: P0-6 through P0-10.

---

## 2. Technical Designs by Item

### P0-6: `synlynk capability report` (gh:#1993, gh:#2332)
* **Goal:** Convert static `.synlynk/policy.json` task allocations into an empirical, data-driven recommendation engine backed by real job outcomes.
* **Problems Identified:**
  1. `DISCIPLINE_TO_TASK_TYPE` in `synlynk/capability_report.py` maps `docs: None`, `security: None`, `ml: None`, `PROG: None`, causing 130+ completed jobs to be skipped.
  2. Synthetic ratings (`SEED_QUALITY = 0.6`) from `synlynk/local_agent_seed.py` are not filtered out.
* **Design:**
  - Update `DISCIPLINE_TO_TASK_TYPE` to map all recognized disciplines: `docs -> content`, `security -> refactor`, `devops -> infra`.
  - Filter out seed rows: `quality != 0.6` and `story_id NOT LIKE 'seed-%'`.
  - Support `synlynk capability report --apply` to directly patch `task_allocation` in `.synlynk/policy.json` when candidate harnesses meet `min_sample_size >= 5` with strictly lower review cycles and lower median costs.

### P0-7: Distribution: PyPI Package + Thin VS Code Client (gh:#2103) + Install Docs
* **Goal:** Make Synlynk discoverable, installable, and usable in developers' native environments.
* **Design:**
  - **Packaging:** `pyproject.toml` is verified clean with dynamic versioning. Add `.github/workflows/release-pypi.yml` triggered on release tags.
  - **Thin VS Code Client (`clients/vscode/`):** A zero-dependency TypeScript extension invoking the installed `synlynk` CLI:
    - Command `synlynk.dispatch`: launches `synlynk dispatch` in an integrated terminal or background execution.
    - Command `synlynk.jobs`: fetches `synlynk jobs --json` and presents status in a quick-pick or tree view.
    - Command `synlynk.logs`: tails active job log file.
  - **Install Docs:** Document `pip install synlynk` and one-liner setup in `README.md`.

### P0-8: Token & Cost Honesty — Circuit Breaker Blindspot (gh:#1937)
* **Root Cause:**
  - `split_billed_tokens()` in `synlynk/costs.py` subtracts cached prompt tokens.
  - `synlynk/circuit_breaker.py` evaluates `zero_file_threshold` (500k) against *discounted billed tokens* instead of *raw prompt tokens*.
  - When Codex replays cached context repeatedly (e.g. 1.2M tokens with 1.18M cached), the breaker sees only ~20k tokens and fails to fire, allowing 0-file runaway loops while Sentinel logs `TOKEN_BLOAT` warnings.
* **Design:**
  - Disambiguate cost calculation from loop detection.
  - `evaluate_job_circuit_breaker()` must compare `zero_file_token_threshold` against raw cumulative tokens (`raw_in + out_tokens`).
  - Sentinel `TOKEN_BLOAT` graduates from passive warning to hard circuit-breaker trip after threshold.

### P0-9: Onboarding Hardening (gh:#1228, `--yes` flags, `heal --magic`)
* **Design:**
  - `run_magic_heal()` in `synlynk/heal.py` must isolate execution inside an ephemeral worktree (`git worktree add`) instead of mutating the user's checked-out branch.
  - Dynamically resolve agent commit trailers rather than hardcoding Codex.
  - Smoke test: verify `synlynk init --yes` and `synlynk heal --magic --dry-run` on a clean repository fixture.

### P0-10: Stale-Goal Reconciliation
* **Design:**
  - Confirm `goal-5be4eb8b`, `goal-56d4beee`, and `goal-d38e3c83` remain marked `superseded` and `goal-d3333441` marked `done` in `state.db`.
  - Reflect clean state in `project-docs/roadmap.md`.

---

## 3. Ceremony & Rollup Policy Integration

Per governance decision:
1. All multi-task tracking is anchored in parent epic issues (e.g. [#2384](https://github.com/nikhilsoman/synlynk/issues/2384)).
2. Mechanical per-PR blog generation is retired.
3. Long-form conversational rollups are posted to the parent tracking issue upon PR merge.
4. Milestone blogs synthesize complete arcs (Intent, Context, Pathway, and Outcome).
