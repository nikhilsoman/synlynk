# GOVERNS Goal and Phase Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every recognized initiative enter through a GOVERNS goal and roadmap phase, with atomic placement by default and an explicit audited `unplaced` escape hatch for strategic work.

**Architecture:** Extend existing `goals` and `roadmap_phases`; do not add a registry. Add direct goal placement state, expose atomic `governs start`, make dispatch/PR/release checks phase-aware after observe-before-enforce, and reuse GOVERNS events for auditability.

**Tech Stack:** Python 3 stdlib, sqlite3, argparse, pytest.

**Spec:** Panel decision `dec-f1dacff3` recorded 2026-11-01; source decision is in the Claude dispatch worktree at `project-docs/decisions/2026-11-01-should-governs-goal-and-roadmap-phase-cr.md`.

## Global Constraints

- No second initiative registry.
- No guessed placement for existing orphaned records.
- Exploration and design require a goal and phase before durable work is recognized.
- `unplaced` is explicit, reasoned, queryable, and audited.
- Implementation dispatch requires a placed goal/phase; only explicitly classified exploration/design may use `unplaced`.
- Preserve existing goal-contribution and GOVERNS event data.
- Do not remove the repo-local shadow DB in this implementation; add the verified cleanup guard first.

## Review Focus

- Atomic rollback leaves neither a half-created goal nor an orphan placement audit.
- Legacy goals remain readable without guessed phases.
- Re-phasing leaves one current placement and an audit trail.
- Explicit identifiers beat text-similarity attribution.
- Shadow DB detection remains read-only until a separately approved cleanup.

### Task 1: Placement schema and migration helpers

**Files:** `synlynk/db_schema.py`, `synlynk/db.py`, `tests/test_goals.py`

- [ ] Add failing tests for `phase_id`, `placement_status`, `placement_reason`, and legacy-row preservation.
- [ ] Run `pytest tests/test_goals.py -q` and confirm failure.
- [ ] Implement guarded schema upgrades and transaction-safe placement helpers.
- [ ] Run focused tests and confirm pass.
- [ ] Commit `feat: add governed goal phase placement state`.

### Task 2: Atomic `synlynk governs start`

**Files:** `synlynk/cli.py`, `synlynk/db.py`, `tests/test_governs_start.py`

- [ ] Add failing tests for atomic success, rollback, and explicit unplaced reason validation.
- [ ] Implement `synlynk governs start --outcome ... --criterion ... --phase ...` plus `--unplaced --reason`.
- [ ] Verify focused tests and commit `feat: add atomic governs start ceremony`.

### Task 3: Phase-aware linkage enforcement

**Files:** `synlynk/governs_gate.py`, `synlynk/dispatch.py`, `synlynk/db.py`, `tests/test_governs_phase_gate.py`

- [ ] Add failing tests for missing phase, unplaced exploration, and blocked implementation dispatch.
- [ ] Implement phase-aware linkage and observe-before-enforce compatibility reporting.
- [ ] Verify focused tests and commit `feat: enforce governed goal phase linkage`.

### Task 4: Audited transactional re-phasing

**Files:** `synlynk/db.py`, `synlynk/events.py`, `tests/test_governs_phase_gate.py`

- [ ] Add failing re-phase and rollback audit tests.
- [ ] Implement transactional re-phasing with old phase, new phase, actor, reason, and timestamp evidence.
- [ ] Verify focused tests and commit `feat: audit governed goal rephasing`.

### Task 5: Drift audit and shadow-DB guard

**Files:** `synlynk/doctor.py`, `synlynk/fleet.py`, `tests/test_governs_phase_audit.py`

- [ ] Add failing tests for orphaned goals/phases and repo-local shadow DB detection.
- [ ] Implement read-only audit output and cleanup violation classification.
- [ ] Verify no destructive cleanup occurs and commit `feat: audit governed roadmap drift`.

### Task 6: Canonical reconciliation

**Files:** canonical product `state.db` through supported CLI/API commands; audit tests

- [ ] Classify existing records without guessing placements.
- [ ] Register `v0.26.8`, `v0.26.9`, and `v0.26.10` only through GOVERNS commands.
- [ ] Verify new initiatives are clean under the audit.
- [ ] Defer shadow DB removal until the cleanup guard passes and a separate approved cleanup action is ready.
