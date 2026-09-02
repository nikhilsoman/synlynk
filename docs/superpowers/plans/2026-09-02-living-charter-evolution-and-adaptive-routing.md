# Implementation Plan: Living Charter Evolution & Capability-Gated Adaptive Routing Engine

**Issue:** [#1342](https://github.com/nikhilsoman/synlynk/issues/1342)  
**Spec:** `docs/superpowers/specs/2026-09-02-living-charter-evolution-and-adaptive-routing-design.md`  
**Goal:** `goal-adb60ccc` (Fleet analytics & capability truth)  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: Bayesian Capability Calibrator & Ledger (`synlynk/capability.py`)**
  - Implement `update_capability_score(model_id, harness, task_domain, outcome)` with Beta distribution priors (`alpha`, `beta`) and recency half-life decay.
  - Add SQLite schema migrations in `synlynk/db.py` for `capability_ledger` and empirical metrics.
  - Add unit tests in `tests/test_capability.py`.

- [ ] **Task 2: Adaptive Expected-Value Dispatch Router**
  - In `synlynk/dispatch.py`, replace hardcoded dispatch hints with dynamically calculated Expected Value:
    $$\text{Expected Value} = \frac{E[\text{Success} \mid \text{model, domain}] \times \text{Criticality}}{\text{Amortized Cost}(\text{model}) + \lambda \cdot \text{P95 Latency}}$$
  - Add unit tests in `tests/test_dispatch.py`.

- [ ] **Task 3: Living Charter PR Proposal Generator (`synlynk charters adapt`)**
  - Implement `cmd_charters_adapt()` in `synlynk/charters.py`: detects when empirical capabilities diverge $>25\%$ from static charters and drafts automated PR updates to `.synlynk/roles.yaml` and `docs/charters/corpus-references.md`.
  - Register `synlynk charters adapt` in `synlynk/cli.py` and `synlynk/taxonomy.py`.

- [ ] **Task 4: Documentation, Blog Post, and Full Suite Verification**
  - Author blog post `docs/blog/167-pr1350-living-charter-adaptive-routing.md` and index in `docs/blog/README.md`.
  - Update `project-docs/memory.md` and devlogs. Ensure all pytest tests pass.
