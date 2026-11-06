# v0.26.10 Harness Capability and Quota Preflight Parity

## Intent

Prevent governed dispatch from silently selecting the wrong harness or starting work that the selected provider cannot fund. This closes the two v0.26.10 investigations represented by GitHub issues #5011 and #5012 while preserving the existing state.db authority and GOVERNS workflow.

## Goals

- An explicitly named harness is binding by default. Learned/story routing applies only when the harness is omitted or explicitly `auto`.
- Capability checks evaluate the harness the user selected and fail closed with an actionable reason when it cannot satisfy the task.
- Dispatch preflight checks the resolved harness, model, and track against subscription quota, active credit grants, and open reservations before spawning a job.
- Reservations use the same harness/model/track identity as the preflight calculation and remain atomic under concurrent dispatch.
- Provider quota/credit exhaustion is represented distinctly from ordinary task failure and preserves any partial worktree as evidence.
- Existing tables and telemetry are extended or corrected; no new registry or parallel source of truth is introduced.

## Non-goals

- No automatic purchase, account mutation, or use of a human user's token or authority.
- No change to the canonical roadmap/state.db model.
- No broad rewrite of capability scoring or provider adapters.
- No automatic retry against another paid provider after a preflight or provider quota failure.

## Anti-goals

- Silently rerouting an explicit harness.
- Treating unknown quota data as healthy for a provider/model that requires paid capacity.
- Deleting or hiding a worktree after a provider failure has produced partial output.

## Current evidence

- Job `job-3cb4dd1e` reproduced `resolve_dispatch_harness("codex", force_agent=False)` resolving to Agy because learned routing precedes the requested harness. Merged `origin/main` commit `1f91bf7d` contains this behavior.
- Job `job-e90d8d95` observed parallel Agy jobs pass harness-wide reservations while the selected provider pool returned `RESOURCE_EXHAUSTED (429)`; one job left partial files.
- `synlynk quota federated` currently reports Codex weekly quota but Agy weekly/5h as unknown, demonstrating why unknown data cannot be treated as a successful preflight for a paid dispatch.

## Design

### 1. Harness selection

Introduce one explicit distinction in the existing dispatch resolution path: positional harness names (`codex`, `agy`, `claude`, `grok`) are binding; omitted/`auto` harnesses are eligible for learned capability routing. `--force-harness` remains supported for compatibility and continues to bypass capability substitution only where policy requires it. The selected harness is passed unchanged to capability probing and appears in the dispatch decision/audit message.

### 2. Quota identity and preflight

Resolve the provider model/track before quota evaluation. Reuse `harness_quotas`, `quota_snapshots`, `credit_grants`, and `harness_reservations` in state.db. The preflight computes the projected token/cost requirement using the existing estimate, selects the applicable subscription window, and includes unexpired credits and open reservations for the same `(harness, model, track)` identity. Unknown or stale required quota data returns a visible degraded/preflight result rather than an unqualified green result.

### 3. Atomic reservation

Extend the existing reservation identity with model/track fields using an idempotent migration. The check-and-reserve operation runs in one transaction and rejects a request when the selected quota/credit pool cannot cover the projected requirement. Existing callers that do not have model/track data retain the documented `unknown/default` compatibility values, but paid provider dispatches must resolve them before spawning.

### 4. Provider failure and partial work

Classify provider `429`, credit exhaustion, and equivalent quota errors with a quota-specific terminal reason. Preserve the job worktree and record touched files or the partial-work marker in the existing job/evidence structures. Do not relabel the event as an ordinary verification failure and do not silently retry on another harness.

### 5. Observability and GOVERNS

Expose the selected harness/model/track, preflight result, reservation identity, and terminal reason in existing status/cost output. Link implementation work only to goal `goal-90277c9c`, phase `116`, and stories `story-4cc90b48` / `story-5f8410f4`. Tests must use temporary state.db instances and must not create a new registry.

## Acceptance criteria

1. A positional Codex dispatch cannot resolve to Agy without an explicit caller-requested fallback, while `auto` still uses capability routing.
2. The selected model/track is used consistently by preflight and reservation.
3. A depleted or unknown required Agy subscription/credit pool blocks paid work before process/worktree execution.
4. Concurrent reservations cannot oversubscribe the same model/track pool.
5. A simulated provider 429 leaves an auditable partial-work result and distinct quota terminal reason.
6. Existing quota, routing, dispatch, and job tests remain green apart from documented environment baselines.

## Implementation calls

- Keep the change in existing dispatch/quota/job modules rather than introducing a registry.
- Prefer additive schema migration and compatibility defaults over rewriting historical rows.
- Use TDD for every behavior change: regression first, observed failure, minimal implementation, focused and full verification.
