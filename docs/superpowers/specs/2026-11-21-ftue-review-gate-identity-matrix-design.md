# FTUE Review-Gate Identity Matrix: Closing the Solo-Harness Simulation Blind Spot

- **Date:** 2026-11-21
- **Status:** Proposed
- **Author:** Claude (Home Conductor, Mode A)
- **Related Issues:** gh:#5355 (solo-harness-account carve-out gap), gh:#5297/#5298/#5299 (fixed via PR #5303)
- **Related Specs:**
  - `docs/superpowers/specs/2026-11-15-ftue-onboarding-vm-testbed-and-discovery-design.md` (the VM testbed this extends)
  - `docs/superpowers/specs/2026-10-01-unified-onboarding-journeys-and-lifecycle-design.md` (the 10-stage journey this scenario covers a slice of)
  - `docs/superpowers/specs/2026-10-07-policy-enforcement-maturity-design.md` (observe/enforce gate maturity model)

---

## 1. Executive Summary & Intent

Three onboarding bugs (#5297/#5298/#5299) were fixed via PR #5303, which also shipped a VM-based testbed (`synlynk/testbed/`) with synthetic multi-harness identities and an acceptance test suite. Separately, while answering an ad-hoc question about solo-harness-account onboarding, gh:#5355 surfaced: `_cross_harness_review_verdict()` (`synlynk/db.py:372-446`) hard-fails whenever the implementing and reviewing identity match — with no carve-out for a workspace that only has one harness account. This is currently non-blocking everywhere (the gate defaults off, and this repo's own `.synlynk/policy.json` runs it in `observe` mode), but would become a real functional block the moment any project flips `cross_harness_review_required_mode` to `enforce` while a contributor has only one harness account.

The bug class that produced #5355 — a gap in the review/merge path, not the install/discovery/wizard path the existing testbed already covers — was found by accident, not by systematic testing. This spec closes that specific gap in the testbed's coverage: it adds identity fixtures for account configurations the existing 3-node team doesn't model, and a new scenario that runs the review/merge gate against each of them, so a future gate change can't reintroduce this bug class silently.

This spec does **not** fix #5355 itself. It produces the regression test that proves the gap, in red state, as a deliberate prerequisite — per this project's Design → Plan → Build sequence and systematic-debugging practice (root-cause and reproduce before fixing).

## 2. Problem Statement

`synlynk/testbed/identities.py`'s `STANDARD_IDENTITIES` models exactly one account-configuration shape: a 3-person team, each on a different harness (alice/codex, bob/agy, charlie/grok). Every scenario in `synlynk/testbed/scenarios.py` (`brownfield_init`, `p2p_mesh`, `task_lease_recovery`, `state_db_wal_soak`) runs against that same shape, or against none (the local-only WAL soak). None of the existing scenarios exercise the PR review/merge gate at all — the testbed's acceptance matrix stops at Stage 9 of the unified onboarding journey ("First-Win Project Intake") and never reaches Stage 10 ("First-Win Micro-Cycle, Effect-Verified"), which is where `_cross_harness_review_verdict` actually runs.

Two structural facts make this gap easy to close without new infrastructure:

1. **The gate is pure local-state evaluation.** `_cross_harness_review_verdict(conn, pr_number)` reads only `capability_ratings`, `cost_entries`, and `daemon_jobs` from the local `state.db` connection (verified by reading `synlynk/db.py:372-446` directly — no `gh` subprocess call appears anywhere in the function). It can be driven entirely by seeding rows, with no real GitHub account, token, or API mock needed.
2. **The testbed has no GitHub mock today**, confirmed by grep across `synlynk/testbed/*.py` and `tests/testbed_mocks/gateway_mock.py` — only LLM-provider endpoints (LiteLLM/OpenRouter/Ollama-shaped) are mocked. Building a full GitHub mock to test this specific gate would be solving a problem that fact (1) already makes unnecessary.

## 3. Design

### 3.1 New identity fixtures (`synlynk/testbed/identities.py`)

Add three fixtures to `STANDARD_IDENTITIES` (or an adjacent `SOLO_AND_EDGE_IDENTITIES` dict, kept separate so existing team-shaped scenarios are unaffected):

- **`solo_claude`** — one harness account (`claude`, one `ANTHROPIC_API_KEY`), one role. The direct #5355 shape: there is no second harness/model identity available to satisfy cross-harness review.
- **`gateway_poweruser`** — `claude` routed through a DGX/LiteLLM gateway (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CONFIG_DIR` — the exact env vars #5298 fixed passthrough for). Modeled separately from `solo_claude` because a gateway can genuinely fan out multiple models behind one externally-visible harness identity; the matrix should confirm the gate's identity resolution isn't fooled either way by gateway routing.
- **`ci_headless`** — a bot/service identity (`codex`, dispatch-only, no interactive wizard session ever runs). Confirms the gate's identity resolution behaves the same for a non-human, headless-only identity as for an interactively-onboarded one.

Each fixture is a `SyntheticIdentity` using the existing dataclass shape — no changes to `identities.py`'s structure, only new data.

### 3.2 New scenario (`synlynk/testbed/scenarios.py`): `run_review_gate_matrix`

For each of the 6 identities (3 existing team + 3 new), in a local (no-VM) run against an isolated `state.db` copy:

1. Seed one synthetic `cost_entries` row and one `capability_ratings` row attributing a fake story/PR to that identity's `(harness, model)` pair, as the implementer.
2. Seed a second `cost_entries`/review-provenance row for the **same identity** as reviewer — the worst case, and the literal #5355 shape (a solo-harness or solo-gateway identity has no other identity to be reviewed by).
3. Call `_cross_harness_review_verdict(conn, pr_number)` directly (same import path `synlynk pr check` itself uses) and record the verdict.
4. Assert against the **current policy mode** read from the scenario's own test fixture `.synlynk/policy.json` (not the real repo's), parameterized over both `observe` and `enforce` so the matrix proves the gap exists in `enforce` mode specifically, independent of what this repo happens to have configured today.

This follows the existing `ScenarioRunner` pattern (`ScenarioResult(name, status, duration_seconds, details, invariants=None)`), returning one `ScenarioResult` per identity so failures are individually attributable rather than one pass/fail blob for all six.

Because step 3 calls into `synlynk.db` directly against a throwaway `state.db`, this scenario needs **no VM, no network, and no GitHub mock** — it can run as a fast local scenario the same way `run_state_db_wal_soak` already does, not through `TestbedDriver.exec_command`.

### 3.3 Expected result (red state, by design)

Run against current `main`: `solo_claude` and `gateway_poweruser` are expected to **fail** the `enforce`-mode assertion (hard block, matching #5355's finding). `ci_headless` is included to establish whether the same gap applies to bot identities or not — its result is not assumed in advance. The three existing team identities are expected to **pass** (they already have a genuinely different harness available). This is the scenario's job: prove the gap exists in a reproducible, deterministic local test, which is the prerequisite for #5355's eventual fix PR.

### 3.4 Test wiring (`tests/test_ftue_vm_acceptance.py`)

Add new test functions alongside the existing `test_orb_driver_provisioning_sequence` and `test_live_orb_ftue_e2e`, following the same `_is_orbctl_available()` guard pattern where relevant — though per 3.2, this scenario doesn't need a VM at all, so its test function should NOT be gated behind `_is_orbctl_available()`; it runs unconditionally as a fast local test.

## 4. Explicitly Out of Scope

- **Fixing #5355 itself** (adding the carve-out to `_cross_harness_review_verdict`). Follow-up PR, informed by this scenario's red-state output.
- **Re-running the full 10-stage journey per new identity.** No evidence yet that Stages 1-5/7-9 vary by harness-account count; the existing VM suite already covers those generically. Revisit only if this audit (or a future one) finds a stage-specific gap.
- **A GitHub API mock, or real disposable test-org testing** (the two alternatives considered and rejected in favor of local-state simulation — see §2). Logged here as a follow-up idea for a future spec if a bug is ever found that specifically requires real/mocked GitHub API fidelity (e.g., App-token auth routing bugs) — not scheduled now.

## 5. Verification & Test Matrix

| Identity | Harness | Expected verdict (enforce mode) |
|---|---|---|
| alice (existing) | codex | pass (distinct reviewer identity available) |
| bob (existing) | agy | pass |
| charlie (existing) | grok | pass |
| `solo_claude` (new) | claude only | **fail** — reproduces #5355 |
| `gateway_poweruser` (new) | claude via gateway | **fail** — reproduces #5355's gateway variant |
| `ci_headless` (new) | codex, headless | unassumed — reported, not pre-judged |

Acceptance: `run_review_gate_matrix` returns one `ScenarioResult` per row above; the scenario itself is considered correctly implemented when the two "fail" rows actually fail against current `main` (proving it reproduces the real gap) — a scenario that passes all six today would indicate the simulation isn't faithfully reproducing #5355's conditions and needs revision before merge.

## 6. Rollout Plan

1. This spec, reviewed and approved.
2. Implementation plan via `writing-plans`, scoped to: `identities.py` fixtures, `scenarios.py` scenario, `test_ftue_vm_acceptance.py` wiring.
3. PR, reviewed cross-harness per this repo's Hardened PR Review Policy, merged.
4. Separate follow-up: fix PR for #5355 itself, using this scenario as its regression test (should flip from fail to pass for `solo_claude`/`gateway_poweruser`).
