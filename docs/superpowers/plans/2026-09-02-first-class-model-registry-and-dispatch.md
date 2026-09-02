# Implementation Plan: First-Class Model Registry, Environment Discovery, Entitlements, and Complexity-Aware Dispatch

**Spec:** `docs/superpowers/specs/2026-09-02-first-class-model-registry-and-dispatch-design.md`  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: Canonical Model Registry & Schema (`synlynk/models.py`)**
  - Implement `ModelFamily` and `ModelSpec` dataclasses with entitlement tiers and differential rate cards.
  - Create SQLite database schema migration for `models` and `model_families` in `synlynk/db.py`.
  - Add CLI inspection commands (`synlynk models list`, `synlynk models show <id>`).

- [ ] **Task 2: Local Environment Discovery Probing**
  - Implement dynamic CLI probes for `claude`, `codex`, `agy`, `grok`, and local inference endpoints (`ollama`, `oMLX`).
  - Wire discovery into `synlynk doctor`, `synlynk init`, and `synlynk onboard`.

- [ ] **Task 3: Complexity-Aware Dispatch & Entitlement Arbitration**
  - Update `synlynk/dispatch.py` to evaluate task complexity tiers and requisition model families.
  - Implement pre-dispatch entitlement checks (verifying `metered_extra_usage_only` fits within `extra_usage_cap_usd`).

- [ ] **Task 4: Dual-State Telemetry Attribution & Unit Tests**
  - Record `requested_model` vs `resolved_model` on all `daemon_jobs` and `cost_entries`.
  - Add comprehensive unit tests in `tests/test_models.py` and `tests/test_dispatch.py`.
  - Author blog post `docs/blog/162-pr1339-first-class-model-registry.md` and index in `docs/blog/README.md`.
