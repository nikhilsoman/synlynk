# Local Harness Operationalization Plan

**Date:** 2026-10-16
**Status:** Approved by Nikhil on 2026-10-16
**Design:** `docs/superpowers/specs/2026-10-16-local-harness-operationalization-design.md`
**Epic:** gh:#2342
**Goal:** `goal-8d34c416`

## Outcome

Deliver a measured local dispatch path in which an operator may select an
already-served, policy-approved oMLX model per dispatch. The path must use the
production HarnessAdapter contract, invoke Aider safely, provide classified
diagnostics and receipts, and admit only qualified work to an isolated pilot.

## Invariants

- A v1 model request never downloads, loads, unloads, restarts, or silently
  substitutes a model.
- The model must be both live in `/v1/models` and approved by local policy.
- `OPENAI_API_KEY` remains the oMLX/Aider credential flow; logs and receipts
  never expose it.
- Local concurrency remains one until an explicit future design changes it.
- Normal local test-running remains disabled until the isolated environment
  and permission contract are implemented.
- Each story lands behind focused tests and leaves the rest of dispatch
  behavior unchanged.

## Phase 0 — Baseline and host truth (#2344)

1. Inventory the installed Aider and oMLX versions, configured endpoint, and
   exact `/v1/models` behavior with and without the configured API key.
2. Add/adjust diagnostic tests that distinguish: endpoint unavailable, timeout,
   HTTP 401, malformed inventory, and healthy inventory. Redact credentials.
3. Verify environment forwarding from Synlynk to the Aider invocation in an
   isolated fixture. Do not add an alternate token scheme.
4. Record the evaluated host/model inventory in the ticket receipt, not in a
   hard-coded source roster.

**Exit gate:** authenticated inventory discovery works on the target host, and
all five health outcomes are test-covered.

## Phase 1 — Qualification harness (#2348)

1. Create an isolated disposable-worktree fixture with no GitHub credentials
   or unrelated secrets and network access restricted to local oMLX.
2. Build the 24-task evaluation corpus: eight test/log summaries, eight
   diagnoses, four explanations, and four narrowly-scoped mechanical/doc
   exercises.
3. Add a results schema that records model ID, Aider mode, correctness,
   completion, test result, scope adherence, retries, wall time, memory, and
   unsafe/no-op events.
4. Evaluate Qwen3-Coder first, Gemma 4 only after compatibility confirmation,
   and Ornith as baseline. Keep PrismML Ternary Bonsai blocked.
5. Exercise Aider forwarding, repository map, prompt files, `diff` and
   `whole` modes, scoped diff/no-op behavior, and approved test-command
   handling.

**Exit gate:** a candidate passes authenticated E2E stack qualification with
at least 85% benchmark correctness, zero unsafe/no-op/out-of-scope edits, and
memory within the host budget.

## Phase 2 — Production adapter path (#2345)

1. Trace current local invocation construction in `dispatch.py` and the
   adapter registry; retain existing dispatch compatibility while moving local
   execution to `LocalAdapter`'s command and result interfaces.
2. Define structured local result/failure categories for auth, inventory,
   unavailable model, timeout, malformed response, Aider failure, and no-op.
3. Ensure adapter-generated commands receive only sanitized environment and
   declared permissions.
4. Add adapter conformance and production-dispatch integration tests proving
   that the legacy inline path is no longer the execution owner.

**Exit gate:** an existing local dispatch uses the adapter end-to-end and
emits a classified result without regressions in other adapters.

## Phase 3 — Resolution and observability (#2346)

1. Implement a resolver with explicit inputs from live oMLX inventory, local
   policy (`.agents/local.json`), and global catalog metadata.
2. Report drift precisely: live-but-unapproved, policy-approved-but-not-live,
   and catalog-only models. Never coerce one identifier to another.
3. Add receipt/telemetry fields for requested and resolved model ID, source
   layers, Aider edit mode, health classification, timings, retry count, and
   memory where available.
4. Preserve existing `local doctor --init`, hardware tier tests, and
   concurrency guard; add integration coverage around their interactions.

**Exit gate:** the resolver exposes every mismatch clearly and receipts can
separate results by model and failure type.

## Phase 4 — Existing-model per-dispatch selection (#2347)

1. Add the documented `--model <omlx-model-id>` dispatch input for local.
2. Validate it against the Phase 3 resolver before starting Aider.
3. Pass the exact resolved ID and policy edit mode into Aider; reject missing,
   unknown, unavailable, or disallowed IDs before a subprocess starts.
4. Keep pinned/default selection only when no explicit model is requested;
   make the selected default observable in the receipt.
5. Test selection, rejection, exact forwarding, no fallback, and preserved
   `max_concurrent: 1` behavior.

**Exit gate:** a manually selected live approved model completes through
Synlynk -> adapter -> Aider -> oMLX with a verifiable receipt.

## Phase 5 — Graduated pilot (#2349)

1. Enforce the eligible-work allowlist and excluded-work denylist at routing
   time, including the requirement for an isolated disposable environment.
2. Route no more than 20% of eligible work after qualification. Keep frontier
   routing as the default and the immediate fallback.
3. Review receipts at 30 and 75 eligible jobs against the 90% acceptance,
   incident, latency, memory, and rollback criteria from the design.
4. Advance only to 35% and then 50% after the documented gates; on a serious
   regression, return to frontier routing and open an investigation ticket.

**Exit gate:** measured evidence supports the next traffic level or records a
clear rollback decision.

## Delivery order and ownership

| Order | Ticket | Primary work | Required proof |
| --- | --- | --- | --- |
| 1 | #2344 | Host/auth diagnostics | Authenticated live inventory and error matrix |
| 2 | #2348 | Isolated stack qualification | Benchmark receipt and chosen candidate |
| 3 | #2345 | Adapter execution parity | Adapter conformance plus dispatch integration |
| 4 | #2346 | Resolver and telemetry | Drift tests and per-model receipt |
| 5 | #2347 | Explicit selection | Exact ID forwarding and no-fallback tests |
| 6 | #2349 | Guarded traffic pilot | Gate review and rollback drill |

Implementation tasks use dedicated worktrees. Any discovery that changes the
model-lifecycle, security, or pilot-safety boundary returns to a design update
and approval rather than being absorbed into a ticket.

## Verification suite

Run the smallest relevant subset at each change, then the shared local suite:

```text
pytest -q tests/test_local_agent.py tests/test_local_adapter.py \
  tests/test_harness_adapter_registry.py tests/test_adapter_conformance.py \
  tests/test_dispatch.py -m 'not local_hardware'
```

Hardware and live oMLX checks are opt-in and must run only in the isolated
qualification environment. No test may depend on a real key in source control.
