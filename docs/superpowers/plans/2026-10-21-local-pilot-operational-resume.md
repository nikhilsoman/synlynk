# Local Pilot Operational Resume Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a previously paused Local pilot safely resumable only through an explicit, preflight-gated 20%/one-concurrent operational authorization.

**Architecture:** Add an append-only authorization/epoch ledger alongside immutable Local evidence. Admission requires both a matching enabled configuration and one active authorization. The CLI performs an interactive preflight and a crash-safe staged activation; any later hard safety outcome revokes authorization and disables config.

**Tech Stack:** Python 3, SQLite migrations, existing Synlynk CLI/config/identity primitives, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-local-pilot-operational-resume-design.md`

## Global Constraints

- Preserve all existing Local safety evidence and historical 8/12 summary unchanged.
- Resume only at share `0.20`, one concurrent Local job, qualified Ornith, and the existing isolated runner.
- Require interactive confirmation, remediation and independent-verification references, and an available local Ed25519 signing key; do not claim human identity verification.
- No live Local dispatch is created by resume; no task-class, model, permission, GitHub-write, review, deploy, daemon, or promotion authority expands.
- A Local dispatch requires exact config/authorization agreement. Any uncertainty, staged state, failed preflight, or post-authorization safety failure must route to the existing frontier fallback.
- Use migrations and canonical state.db only; no generated roadmap file is a source of truth.

## Review Focus

- A historical hard failure must remain visible, but a fresh active epoch must not inherit its validation/expansion denominator.
- A crash between the config replacement and database activation must admit no Local work.
- A concurrent safety pause must revoke a staged/active authorization so it cannot re-enable Local afterward.
- Non-interactive or unsigned commands must leave both config and authorization state disabled.
- Local fallback must retain a request's `pr` context.

---

### Task 1: Durable resume authorization and epoch-aware state

**Files:**
- Create: `synlynk/migrations/m0026_local_pilot_resume_authorization.py`
- Modify: `synlynk/migrations/runner.py`
- Modify: `synlynk/local_pilot_ledger.py`
- Modify: `synlynk/local_pilot.py`
- Test: `tests/test_local_pilot_ledger.py`
- Test: `tests/test_local_pilot.py`

**Interfaces:**
- Produces: `create_resume_authorization(conn, payload: dict) -> dict`, `activate_resume_authorization(conn, authorization_id: str) -> dict`, `revoke_active_resume_authorization(conn, reason: str) -> dict | None`, `active_resume_authorization(conn) -> dict | None`, and `load_pilot_status(conn) -> dict`.
- `load_pilot_status` exposes the latest authorization and active-epoch cohort counts.
- `evaluate_rebaseline(status: dict) -> RebaselineDecision` requires an active authorization after a historical safety failure.

- [ ] **Step 1: Write failing ledger and policy tests**

Add tests for an immutable authorization record with a safety-rowid watermark; refusal to mutate/delete it; status showing historical versus active-epoch safety failures; a historical failure requiring authorization; and an active authorization resetting validation/expansion arithmetic to rows after its watermark.

- [ ] **Step 2: Verify the new tests fail**

Run: `pytest tests/test_local_pilot_ledger.py tests/test_local_pilot.py -k "resume or epoch or rebaseline" -v`  
Expected: FAIL because authorization/epoch APIs do not exist.

- [ ] **Step 3: Implement migration 26 and epoch-aware evaluation**

Create the append-only authorization table with signed payload/digest, preflight payload/digest, remediation and verification references, watermark, and lifecycle states `activating|active|revoked|failed`. Enforce one active authorization and terminal lifecycle fields in SQLite. Make status and `evaluate_rebaseline` count all cohort evidence only after the active watermark; a later safety failure must deny admission.

- [ ] **Step 4: Verify focused tests pass**

Run: `pytest tests/test_local_pilot_ledger.py tests/test_local_pilot.py -k "resume or epoch or rebaseline" -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/migrations/m0026_local_pilot_resume_authorization.py synlynk/migrations/runner.py synlynk/local_pilot_ledger.py synlynk/local_pilot.py tests/test_local_pilot_ledger.py tests/test_local_pilot.py
git commit -m "feat(local): add pilot resume authorization epochs"
```

### Task 2: Interactive preflight and staged CLI activation

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `synlynk/local_agent.py`
- Modify: `synlynk/local_pilot.py`
- Modify: `synlynk/local_pilot_ledger.py`
- Test: `tests/test_agent_cli.py`
- Test: `tests/test_local_pilot.py`

**Interfaces:**
- CLI: `synlynk local pilot resume --remediation-ref <ref> --verification-ref <ref>`.
- Produces: `preflight_local_pilot_resume(repo_root: str, conn) -> dict` and `resume_local_pilot(repo_root: str, conn, remediation_ref: str, verification_ref: str, confirm: Callable[[str], str]) -> dict`.

- [ ] **Step 1: Write failing CLI and preflight tests**

Cover non-TTY/refused confirmation, missing references, unavailable signing key, disabled-config/share mismatch, qualified-model/isolation/endpoint failure, active reservation or pending reconciliation, and a successful confirmation that produces a signed `activating` then `active` authorization with exactly `enabled=true`, `share=0.20`, and concurrency one. Assert no dispatch is created.

- [ ] **Step 2: Verify the new tests fail**

Run: `pytest tests/test_agent_cli.py tests/test_local_pilot.py -k "pilot_resume or resume_preflight" -v`  
Expected: FAIL because the command and preflight functions do not exist.

- [ ] **Step 3: Implement the fail-closed resume command**

Add the parser and local-agent handler. Reuse existing live model resolution and owned config update primitives, but require a usable Docker/Compose runner, endpoint health, ledger migration/readability, zero Local reservation, and zero reconciliation debt. Stage a signed authorization before atomically replacing config, then re-check state and activate it. On all errors retain disabled config and non-active authorization. Reconciliation must mark stranded `activating` records failed rather than infer approval from config.

- [ ] **Step 4: Verify focused tests pass**

Run: `pytest tests/test_agent_cli.py tests/test_local_pilot.py -k "pilot_resume or resume_preflight" -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py synlynk/local_agent.py synlynk/local_pilot.py synlynk/local_pilot_ledger.py tests/test_agent_cli.py tests/test_local_pilot.py
git commit -m "feat(local): add preflight-gated pilot resume"
```

### Task 3: Dispatch enforcement, pause serialization, and fallback context

**Files:**
- Modify: `synlynk/dispatch.py`
- Modify: `synlynk/jobs.py`
- Modify: `synlynk/local_pilot_ledger.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_jobs.py`
- Test: `tests/test_local_pilot_ledger.py`
- Modify: `docs/reference/local-harness-pilot-operations.md`

**Interfaces:**
- Dispatch consumes `active_resume_authorization(conn)` and only admits Local when it matches the enabled 20%/one-concurrent runtime.
- `pause_local_pilot(reason: str)` revokes the active authorization before/with disabling config.
- Local frontier fallback passes the original `pr` argument to recursive dispatch.

- [ ] **Step 1: Write failing integration tests**

Assert a matching enabled configuration without active authorization falls back; an active authorization with config drift falls back; post-watermark safety failure revokes and disables; staged authorization never admits; a pause/resume ordering race cannot leave enabled config with active authorization; and fallback preserves `pr`.

- [ ] **Step 2: Verify the new tests fail**

Run: `pytest tests/test_dispatch.py tests/test_jobs.py tests/test_local_pilot_ledger.py -k "local_pilot or resume_authorization" -v`  
Expected: FAIL because dispatch and pause do not yet enforce authorization state.

- [ ] **Step 3: Implement dispatch and pause enforcement**

Bind admission to one matching active authorization and fail closed to the already selected frontier. Serialize pause/revocation with authorization lifecycle changes and preserve immutable receipts/evidence. Add the one-line `pr=pr` fallback propagation correction.

- [ ] **Step 4: Verify focused and integration suites pass**

Run: `pytest tests/test_local_pilot.py tests/test_local_pilot_ledger.py tests/test_agent_cli.py tests/test_dispatch.py tests/test_jobs.py -v`  
Expected: PASS, aside from any separately documented pre-existing failures.

- [ ] **Step 5: Update the operator runbook and commit**

Document the explicit human ceremony, operator-attestation limitation, preflight fields, states, crash recovery, and no-live-dispatch rule.

```bash
git add synlynk/dispatch.py synlynk/jobs.py synlynk/local_pilot_ledger.py tests/test_dispatch.py tests/test_jobs.py tests/test_local_pilot_ledger.py docs/reference/local-harness-pilot-operations.md
git commit -m "fix(local): enforce resume authorization at dispatch"
```

### Task 4: Whole-change verification and independent review

**Files:**
- Test: all Local pilot test modules and repository suite

- [ ] **Step 1: Run focused suite**

Run: `pytest tests/test_local_pilot.py tests/test_local_pilot_ledger.py tests/test_agent_cli.py tests/test_dispatch.py tests/test_jobs.py -v`  
Expected: PASS or report exact unrelated baseline failures.

- [ ] **Step 2: Run the full repository suite**

Run: `pytest -q`  
Expected: PASS or report exact failures with comparison to the pre-change baseline.

- [ ] **Step 3: Dispatch an independent whole-branch review**

Review the complete diff against the 2026-10-21 design, focusing on authority, epoch isolation, crash windows, config/DB disagreement, and no accidental Local dispatch.

- [ ] **Step 4: Record results**

Update the SDD ledger with commits, commands, results, and review disposition. Do not enable Local or merge/push as part of implementation.

