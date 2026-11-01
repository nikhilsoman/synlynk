# v0.26.10 Harness Capability and Quota Preflight Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicit harness routing and model-aware quota preflight reliable for v0.26.10.

**Architecture:** Keep the existing dispatch resolver, quota tables, reservation table, and job evidence path. Add the smallest compatibility migration needed to carry model/track identity, evaluate subscription/credits/reservations transactionally, and classify provider quota failures without introducing a registry.

**Tech Stack:** Python, SQLite, pytest, existing Synlynk CLI/dispatch/job modules.

**Spec:** `docs/superpowers/specs/2026-11-01-v02610-capability-quota-preflight-design.md`

## Global Constraints

- State.db remains the only roadmap/GOVERNS authority.
- Explicit harness names are binding; only omitted/`auto` selection may use learned routing.
- Paid provider work must not spawn when required quota/credit data is unavailable or insufficient.
- No human token, authority, account mutation, automatic paid fallback, or new registry.
- Every behavior change follows red-green-refactor TDD.

## Review Focus

- Positional `codex` with an incompatible learned story route must remain `codex`; add the resolver regression in `tests/test_resolve_dispatch_harness.py`.
- `auto` must still select the capable learned harness; retain/add the paired auto test in the same file.
- Agy with exhausted or unknown model/track quota must fail before process/worktree execution; add preflight tests in `tests/test_quota_reservation_integration.py`.
- Two concurrent reservations for the same model/track must not oversubscribe; add transactional tests in `tests/test_agent_quota_tracking.py`.
- Provider 429 after partial output must preserve evidence and use a quota-specific terminal reason; add job tests in `tests/test_jobs.py`.

---

### Task 1: Bind explicitly selected harnesses

**Files:** `synlynk/dispatch.py`, `synlynk/capability_probe.py`, `tests/test_resolve_dispatch_harness.py`, `tests/test_dispatch_capability_routing.py`

- [ ] Write failing tests for named Codex binding and auto learned routing, asserting selected harness and probe input.
- [ ] Run focused tests and confirm named binding fails for current substitution.
- [ ] Make only omitted/`auto` selection consult learned routing; keep `--force-harness` compatibility and fail-closed probing.
- [ ] Run focused tests and commit `fix: bind explicit dispatch harness selection`.

### Task 2: Add model/track-aware reservation identity

**Files:** `synlynk/db.py`, reservation helpers in `synlynk/dispatch.py`/`synlynk/jobs.py`, `tests/test_multitrack_quota.py`, `tests/test_agent_quota_tracking.py`

- [ ] Write failing migration and identity tests for columns, legacy rows, and separate tracks.
- [ ] Run focused tests and confirm the new-column assertions fail.
- [ ] Add an idempotent SQLite migration and thread normalized model/track through create, lookup, release, and reconciliation.
- [ ] Run focused reservation lifecycle tests and commit `feat: scope quota reservations by model and track`.

### Task 3: Enforce atomic model-aware quota and credit preflight

**Files:** `synlynk/dispatch.py`, `synlynk/quota.py`, `synlynk/costs.py`, `tests/test_quota_reservation_integration.py`, `tests/test_payment_models.py`, `tests/test_cost_estimate_drift.py`

- [ ] Write failing tests for exhausted Agy credit, unknown required quota, healthy selected pool with another pool exhausted, and parallel same-pool reservations.
- [ ] Run focused tests and confirm the harness-wide gate permits the bad cases.
- [ ] Implement model/track-aware lookup using existing tables; include active grants and reservations in the projection.
- [ ] Make check plus reservation one transaction and leave no open reservation on rejection.
- [ ] Run focused quota/payment tests and commit `fix: enforce model-aware quota preflight`.

### Task 4: Preserve and classify provider quota failures

**Files:** `synlynk/jobs.py`, dispatch result handling, `tests/test_jobs.py`, `tests/test_dispatch.py`, `tests/test_cost_estimate_drift.py`

- [ ] Write a failing simulated-429 test with partial output and inspectable evidence.
- [ ] Run it and confirm current ordinary-failure classification or evidence loss.
- [ ] Add narrow quota/credit error classification, preserve worktree evidence, release reservations, and prohibit automatic paid fallback.
- [ ] Run focused tests and commit `fix: preserve provider quota failure evidence`.

### Task 5: Surface federated preflight evidence

**Files:** `synlynk/quota_capture.py` or existing `quota federated` path, `tests/test_federated_quota_capture.py`, CLI tests

- [ ] Write failing CLI tests for all active harnesses and Agy unknown/exhausted states.
- [ ] Extend existing output to distinguish known, unknown, exhausted, and reserved capacity without a registry.
- [ ] Run focused tests and the command against a temporary DB; commit `feat: expose federated preflight capacity`.

### Task 6: Full verification and governed handoff

- [ ] Run focused routing, quota, payment, reservation, job, and CLI tests.
- [ ] Run the complete project test command and record unrelated baseline failures.
- [ ] Run `synlynk pr check` and `synlynk policy check-merge --role qa` from the PR worktree.
- [ ] Request non-author QA review, address important findings, and have QA merge.
- [ ] Update goal `goal-90277c9c`, phase `116`, stories, issue links, cost log, and parent status rollup with evidence.

## Self-review

The plan covers every spec acceptance criterion: Task 1 covers explicit routing, Tasks 2-3 cover identity and atomic preflight, Task 4 covers provider evidence, Task 5 covers observability, and Task 6 covers GOVERNS/review/merge.
