# Local Harness Pilot Re-baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved safety-first Local pilot re-baseline without resuming Local traffic or widening its authority.

**Architecture:** Keep admission and container containment in `synlynk.local_pilot`, but add a durable, append-only Local-pilot evidence ledger in the canonical SQLite state database. Dispatch registers only a pending, receipt-bound sample; terminal reconciliation verifies the isolated-runner receipt and records safety independently from factual-review quality. A `local pilot` CLI surface renders the separated historical, validation, and expansion-evidence cohorts and coordinates automatic frontier-review selection.

**Tech Stack:** Python 3, SQLite migrations, existing Synlynk CLI/dispatch/job reconciliation, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-local-pilot-rebaseline-design.md`

## Global Constraints

- Preserve the historical **8 accepted / 12 distinct eligible tasks** as immutable, separately labelled evidence; never blend it with the re-baseline denominator.
- Keep `local_pilot.enabled=false` until a separate human operational-resume decision; this implementation must not turn it on.
- Re-baseline eligibility is only `test_summary` and `codepath_summary`, Ornith only, isolated Docker/Compose runner only, read-only, one concurrent Local job, and a 20% maximum allocation.
- Explicit `local` plus `--local-pilot-class` remains a fail-closed error; GitHub write, deploy, review/merge, daemon authority, host execution, and unqualified models remain excluded.
- Hard safety/admission/receipt/credential/scope/rollback/preflight failures pause Local immediately and cannot be offset by answer quality.
- Five independent accepted validation tasks are required before expansion evidence begins. A distinct run of ten consecutive accepted expansion-evidence tasks only makes a 35% proposal eligible; it does not change the share.
- One quality rejection resets only the ten-task expansion-evidence run and retains 20%; a hard safety failure pauses the pilot.
- Use the canonical state DB, not generated roadmap/todo projections, for durable pilot state. Use versioned migrations; never hand-edit generated roadmap files.
- Do not dispatch live Local work or add a live acceptance receipt during implementation tests.

## Review Focus

- A historical 8/12 summary must remain visible but cannot alter validation 5/5 or expansion 10/10 arithmetic; cover in Task 2.
- A signed admission receipt that no longer matches the runner receipt, scope, model, or job must become a safety pause, not a quality rejection; cover in Task 4.
- A task that is safe but factually rejected must reset only the expansion run and keep the 20% cap; cover in Task 2 and Task 5.
- Reviewer routing must not choose Local or the task author even when either has the highest capability score; cover in Task 5.
- A configuration/preflight/reservation disagreement must keep Local disabled and surface the reason without falling back to host-side Aider; cover in Task 3 and Task 6.

---

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/migrations/m0024_local_pilot_ledger.py` | Create immutable cohort/evidence/reviewer tables and seed the fixed historical 8/12 summary. |
| `synlynk/migrations/runner.py` | Register migration 24 in ascending order. |
| `synlynk/local_pilot_ledger.py` | Canonical SQLite reads/writes for pilot configuration snapshot, sample evidence, review verdicts, cohort progress, safety pauses, and status rendering data. |
| `synlynk/local_pilot.py` | Re-baseline policy constants and pure state-machine decisions; preserve isolation/admission primitives. |
| `synlynk/dispatch.py` | Bind admitted Local jobs to durable pending samples and refuse any drift before spawn. |
| `synlynk/jobs.py` | Reconcile runner receipt with the admitted sample; atomically record safety outcome and pause Local when required. |
| `synlynk/cli.py` | Add `synlynk local pilot status`, `review-start`, and `record-review` command parsing and dispatch. |
| `synlynk/local_agent.py` | Implement read-only pilot status rendering and review-control command handlers. |
| `tests/test_local_pilot.py` | Pure policy and re-baseline cohort-state tests. |
| `tests/test_local_pilot_ledger.py` | Migration, append-only ledger, arithmetic, receipt, pause, and reviewer selection tests. |
| `tests/test_dispatch.py` | Admission-to-ledger and no-host-fallback dispatch tests. |
| `tests/test_jobs.py` | Terminal receipt reconciliation and safety-pause tests. |
| `tests/test_agent_cli.py` | CLI status and review workflow tests. |
| `docs/reference/local-harness-pilot-operations.md` | Operator runbook for the three approval gates, status meanings, and evidence attachment to #2342/#2349. |

### Task 1: Canonical Local-pilot evidence ledger

**Files:**
- Create: `synlynk/migrations/m0024_local_pilot_ledger.py`
- Modify: `synlynk/migrations/runner.py`
- Create: `synlynk/local_pilot_ledger.py`
- Test: `tests/test_local_pilot_ledger.py`

**Interfaces:**
- Produces: `ensure_local_pilot_ledger(conn) -> None`, `record_admission(conn, sample: dict) -> dict`, `record_safety_outcome(conn, job_id: str, verdict: str, reason: str, receipt: dict | None) -> dict`, `record_quality_verdict(conn, job_id: str, reviewer: str, verdict: str, rationale: str, selection_reason: str) -> dict`, and `load_pilot_status(conn) -> dict`.
- Consumes: existing canonical SQLite connection from `synlynk._get_db()`; no new flat-file truth source.

- [ ] **Step 1: Write migration and ledger tests**

Add tests that migrate a fresh SQLite fixture, assert the historical cohort is exactly `{"cohort": "historical", "accepted": 8, "eligible": 12}`, and assert a second migration run neither duplicates nor changes it. Add tests that reject a duplicate job ID, reject an unknown cohort/verdict, and preserve an earlier evidence row when a later review is recorded.

- [ ] **Step 2: Run the new ledger tests to verify they fail**

Run: `pytest tests/test_local_pilot_ledger.py -v`  
Expected: FAIL because migration 24 and `synlynk.local_pilot_ledger` do not exist.

- [ ] **Step 3: Add migration 24 and the append-only ledger API**

Create tables for one fixed cohort summary and per-job evidence. Store: cohort (`historical`, `validation`, or `expansion`), task class, job ID, task digest, admitted receipt digest, safety verdict/reason, quality verdict, reviewer harness, reviewer-selection reason, receipt JSON/digest, and UTC timestamps. Enforce one sample per job and legal verdict values with SQLite constraints. Seed the historical summary only with `accepted=8` and `eligible=12`; do not fabricate twelve individual samples. Keep all later writes additive except a pending-to-terminal field update for the same immutable job record.

Implement the listed functions with explicit transactions. `load_pilot_status` must return separate objects for historical, validation, and expansion data rather than an aggregate acceptance percentage.

- [ ] **Step 4: Run the ledger tests to verify they pass**

Run: `pytest tests/test_local_pilot_ledger.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/migrations/m0024_local_pilot_ledger.py synlynk/migrations/runner.py synlynk/local_pilot_ledger.py tests/test_local_pilot_ledger.py
git commit -m "feat(local): add durable pilot evidence ledger"
```

### Task 2: Re-baseline state machine and promotion-proposal gate

**Files:**
- Modify: `synlynk/local_pilot.py`
- Modify: `synlynk/local_pilot_ledger.py`
- Test: `tests/test_local_pilot.py`
- Test: `tests/test_local_pilot_ledger.py`

**Interfaces:**
- Consumes: `load_pilot_status(conn) -> dict`.
- Produces: `REBASELINE_PILOT_CLASSES = frozenset({"test_summary", "codepath_summary"})`, `RebaselineDecision`, and `evaluate_rebaseline(status: dict) -> RebaselineDecision`.
- `RebaselineDecision` fields: `allow_admission: bool`, `cohort: str | None`, `share: float`, `pause_required: bool`, `proposal_35_eligible: bool`, and `reason: str`.

- [ ] **Step 1: Write failing state-machine tests**

Replace the obsolete 30-job/90% and automatic 35%/50% promotion expectations with tests for: a separate 8/12 historical display; validation admission until five accepted samples; validation 5/5 advancing to expansion while share remains `0.20`; one expansion quality rejection resetting its consecutive count to zero; ten consecutive expansion acceptances setting only `proposal_35_eligible=True`; and every hard-safety verdict setting `pause_required=True` and `allow_admission=False`.

- [ ] **Step 2: Run the targeted policy tests to verify they fail**

Run: `pytest tests/test_local_pilot.py tests/test_local_pilot_ledger.py -v`  
Expected: FAIL because the legacy `evaluate_promotion_gate` has 30/90 and automatic-share behavior.

- [ ] **Step 3: Implement the pure re-baseline decision model**

Keep `evaluate_local_pilot` as the fail-closed containment admission primitive, but require its pilot class to be in `REBASELINE_PILOT_CLASSES` when re-baseline mode is active. Replace automatic-promotion semantics with `evaluate_rebaseline`, deriving validation/expansion progress only from ledger rows whose safety verdict is passed and whose quality verdict is accepted. A quality rejection is not a safety failure. A safety failure always yields share `0.20` as the configured ceiling but `allow_admission=False`; it never returns `0.35` or `0.50`.

Retire or adapt `evaluate_promotion_gate` so no caller can obtain an automatic 35%/50% decision from historical aggregate counts. Preserve a clear fail-closed response for callers using the old interface until they migrate.

- [ ] **Step 4: Run the targeted policy tests to verify they pass**

Run: `pytest tests/test_local_pilot.py tests/test_local_pilot_ledger.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/local_pilot.py synlynk/local_pilot_ledger.py tests/test_local_pilot.py tests/test_local_pilot_ledger.py
git commit -m "feat(local): enforce re-baseline cohort gates"
```

### Task 3: Bind Local admission to the new ledger and keep disabled state fail-closed

**Files:**
- Modify: `synlynk/dispatch.py: _resolve_dispatch_agent and dispatch_agent`
- Modify: `synlynk/local_pilot.py: load_pilot_runtime`
- Modify: `synlynk/local_pilot_ledger.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_local_pilot.py`

**Interfaces:**
- Consumes: `evaluate_rebaseline(status)`, `record_admission(conn, sample)`, and existing signed receipt functions.
- Produces: a Local pilot receipt containing `cohort`, `admission_id`, receipt digest, qualified Ornith model, exact scope, and 20% share; no raw dispatch key is persisted.

- [ ] **Step 1: Write failing dispatch tests**

Add tests that a disabled runtime routes every opted-in re-baseline task to the configured frontier fallback and creates no Local ledger sample; an enabled test fixture records one pending validation sample only after signed receipt admission; a non-Ornith model, non-allowlisted class, missing scope, GitHub-write request, host-runner unavailability, or preflight/reservation disagreement records no admitted Local sample and cannot reach host-side Aider.

- [ ] **Step 2: Run the focused dispatch tests to verify they fail**

Run: `pytest tests/test_dispatch.py -k "local_pilot" tests/test_local_pilot.py -v`  
Expected: FAIL because dispatch neither records re-baseline cohort metadata nor consults durable progress.

- [ ] **Step 3: Integrate durable admission before Local spawn**

In `_resolve_dispatch_agent`, open the canonical state DB read-only for decision data and use `evaluate_rebaseline` before issuing a Local receipt. Permit only the two re-baseline classes and the qualified Ornith effective model. In `dispatch_agent`, after receipt replay validation but before process spawn, write one pending ledger sample in a transaction and include its immutable ID/cohort in the persisted job receipt.

If ledger write, runtime reconciliation, receipt verification, model qualification, or isolated-runner setup fails, refuse Local and use the already selected frontier fallback without a later capability reroute back to Local. Do not modify `.synlynk/workspace.json` to enable the pilot.

- [ ] **Step 4: Run the focused dispatch tests to verify they pass**

Run: `pytest tests/test_dispatch.py -k "local_pilot" tests/test_local_pilot.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py synlynk/local_pilot.py synlynk/local_pilot_ledger.py tests/test_dispatch.py tests/test_local_pilot.py
git commit -m "feat(local): bind pilot admission to re-baseline ledger"
```

### Task 4: Reconcile isolated-runner receipts and pause safely

**Files:**
- Modify: `synlynk/jobs.py: Local pilot terminal reconciliation path`
- Modify: `synlynk/local_pilot_ledger.py`
- Test: `tests/test_jobs.py`
- Test: `tests/test_local_pilot_ledger.py`

**Interfaces:**
- Consumes: the job's persisted `local_pilot_receipt` and `result_receipt_file`.
- Produces: `reconcile_local_pilot_terminal(conn, job: dict) -> dict` returning a recorded `safety_verdict`, reason, and pause action.

- [ ] **Step 1: Write failing terminal-reconciliation tests**

Add fixtures for a matching completed-read-only runner receipt with empty changed/applied paths, and for mismatched job/task digest, out-of-scope path, changed path, unqualified model, missing/invalid receipt, host-execution marker, and rollback/preflight integrity failure. Assert the matching fixture records a safety pass but no quality verdict; assert each invalid fixture records a hard safety failure, keeps the sample outside quality accounting, and disables further Local admission.

- [ ] **Step 2: Run the terminal-reconciliation tests to verify they fail**

Run: `pytest tests/test_jobs.py -k "local_pilot" tests/test_local_pilot_ledger.py -v`  
Expected: FAIL because job reconciliation does not parse and cross-check pilot runner receipts.

- [ ] **Step 3: Implement receipt reconciliation and the fail-closed pause**

When a Local pilot job reaches terminal reconciliation, load the runner's JSON receipt from the registered path, verify it against the persisted admission fields, and atomically record its safety outcome in the ledger. Treat absent, malformed, mismatched, or non-read-only evidence as a hard safety failure. The pause operation must set the operational runtime state to disabled through the existing approved configuration helper, retain the original evidence, and cause future pilot admissions to select the frontier fallback.

Do not turn quality acceptance into an automatic terminal result: a receipt only proves containment and safety.

- [ ] **Step 4: Run the terminal-reconciliation tests to verify they pass**

Run: `pytest tests/test_jobs.py -k "local_pilot" tests/test_local_pilot_ledger.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/jobs.py synlynk/local_pilot_ledger.py tests/test_jobs.py tests/test_local_pilot_ledger.py
git commit -m "feat(local): reconcile pilot receipts and pause on safety drift"
```

### Task 5: Automatically select an independent frontier reviewer and record factual verdicts

**Files:**
- Modify: `synlynk/local_pilot_ledger.py`
- Modify: `synlynk/local_agent.py`
- Modify: `synlynk/cli.py: local subcommands and command dispatch`
- Test: `tests/test_local_pilot_ledger.py`
- Test: `tests/test_agent_cli.py`

**Interfaces:**
- Produces: `select_local_pilot_reviewer(conn, *, author_harness: str, eligible: list[str]) -> ReviewerSelection`, `start_local_pilot_review(conn, job_id: str) -> dict`, and `record_local_pilot_review(conn, job_id: str, reviewer: str, verdict: str, rationale: str) -> dict`.
- CLI: `synlynk local pilot status [--json]`, `synlynk local pilot review-start <job-id>`, and `synlynk local pilot record-review <job-id> --reviewer <harness> --verdict accept|reject --rationale <text>`.

- [ ] **Step 1: Write failing reviewer-selection and CLI tests**

Add tests that selection considers qualified frontier harnesses in capability order, excludes Local and the task author, emits its deterministic selection reason, and refuses to start a review for a sample without a passing safety receipt. Add CLI tests that `status` displays the three separate cohorts, the 20%/one-concurrent boundaries, enabled/paused state, model, and proposal eligibility; `review-start` emits a structured factual-review brief; and `record-review` refuses an unselected reviewer, duplicate verdict, invalid verdict, or missing rationale.

- [ ] **Step 2: Run the focused reviewer and CLI tests to verify they fail**

Run: `pytest tests/test_local_pilot_ledger.py tests/test_agent_cli.py -k "local_pilot or local_pilot_review" -v`  
Expected: FAIL because no reviewer-selection or Local pilot CLI commands exist.

- [ ] **Step 3: Implement reviewer routing and factual-review controls**

Use the current capability-routing data as a deterministic ranking input, but never select Local or the task author. Persist the candidate set, selected harness, and a human-readable selection reason before emitting the review brief. The brief must contain task intent, expected factual claims, Local answer/log reference, and automated receipt result, but no secret-bearing environment data.

`record-review` must accept only the stored selected frontier harness and `accept`/ `reject` verdicts, persist a non-empty rationale, and update only quality accounting. It must never alter safety evidence, enable Local, or change the share. Do not grant the reviewer GitHub, merge, deploy, or promotion authority.

- [ ] **Step 4: Run the focused reviewer and CLI tests to verify they pass**

Run: `pytest tests/test_local_pilot_ledger.py tests/test_agent_cli.py -k "local_pilot or local_pilot_review" -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/local_pilot_ledger.py synlynk/local_agent.py synlynk/cli.py tests/test_local_pilot_ledger.py tests/test_agent_cli.py
git commit -m "feat(local): add independent pilot review workflow"
```

### Task 6: Operator status, documentation, and full verification

**Files:**
- Modify: `synlynk/local_agent.py`
- Create: `docs/reference/local-harness-pilot-operations.md`
- Modify: `tests/test_agent_cli.py`
- Test: `tests/test_local_pilot.py`
- Test: `tests/test_local_pilot_ledger.py`
- Test: `tests/test_dispatch.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: `load_pilot_status(conn) -> dict`.
- Produces: an operator-visible, read-only status view with no combined acceptance percentage and a runbook naming the Design, Operational Resume, and Expansion approval gates.

- [ ] **Step 1: Write failing status-output and documentation-contract tests**

Add assertions that JSON and text status label historical 8/12 separately, show validation `accepted/5`, expansion `consecutive accepted/10`, 20% cap, concurrency 1, qualified Ornith model, pilot enabled/paused reason, and proposal eligibility. Add a documentation test or exact-content assertion that the runbook states a 35% proposal is never automatic and no live work is authorized by code merge alone.

- [ ] **Step 2: Run status and documentation tests to verify they fail**

Run: `pytest tests/test_agent_cli.py -k "local_pilot_status" -v`  
Expected: FAIL because the status renderer and runbook contract do not exist.

- [ ] **Step 3: Implement read-only status rendering and the operator runbook**

Render machine-readable and concise text status from the canonical ledger. State explicit operational mismatches (endpoint, credentials, model qualification, runner availability, reservation state) without exposing secrets. Document the procedure to attach each cohort result, pause, resume approval, and 35% proposal decision to #2342/#2349. State that merging this branch leaves `local_pilot.enabled` disabled and that only Nikhil's later operational-resume approval authorizes live samples.

- [ ] **Step 4: Run focused and full verification**

Run:
```bash
pytest tests/test_local_pilot.py tests/test_local_pilot_ledger.py tests/test_dispatch.py tests/test_jobs.py tests/test_agent_cli.py -v
synlynk local pilot status --json
git diff --check
```
Expected: all tests PASS; status reads the canonical DB without enabling or dispatching Local; no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add synlynk/local_agent.py docs/reference/local-harness-pilot-operations.md tests/test_agent_cli.py
git commit -m "docs(local): publish pilot re-baseline operations"
```

## Self-Review

- **Spec coverage:** Tasks 1–2 preserve separate denominators and implement the 5/5 plus 10-consecutive state machine. Tasks 3–4 enforce the isolated, Ornith-only, no-host-execution safety boundary and hard pause. Task 5 provides automatic independent factual review. Task 6 makes the state inspectable and records the human gates. No task enables the pilot or widens authority.
- **Step scan:** Each task starts with named failing tests, has a specific implementation interface, verifies expected behavior, and ends in an isolated conventional commit.
- **Type consistency:** `load_pilot_status`, `evaluate_rebaseline`, `record_admission`, `reconcile_local_pilot_terminal`, and reviewer APIs are defined before their consuming tasks.
- **Review focus:** Each listed failure mode has an explicit owning task and test.
- **Proportion:** The plan fixes interfaces and evidence semantics while leaving normal Python/SQLite implementation details to the builder.

## Execution Handoff

The plan must be committed before implementation work is dispatched. Use a fresh feature worktree for execution; do not implement in this documentation branch. After implementation and independent PR review, stop at the operational-resume approval gate rather than dispatching live Local work.

