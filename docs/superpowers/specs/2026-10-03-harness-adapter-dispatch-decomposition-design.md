# HarnessAdapter Protocol + Dispatch Pipeline Decomposition

- **Date:** 2026-10-03
- **Tracks:** gh:#1924 (architecture #5)
- **Status:** Draft — pending sign-off

## Problem

`synlynk/dispatch.py` is 4,163 lines. `dispatch_agent()` alone is ~1,040 lines
and takes 27 keyword arguments. Harness-specific behavior (Codex, Grok, Agy,
Claude, local) is implemented as scattered `agent == "codex"` / `"grok"` /
`"agy"` / `"claude"` branches — 25 of them at last count — spanning command
construction, output/event parsing, permission-flag translation, auth/quota
failure detection, and model-name resolution.

This is a high-churn, safety-critical file: most of the last 20 merged PRs
touched it, several landing invariant-enforcement fixes (circuit breaker,
single-writer WAL ledger, capability-probed routing). This session alone hit
four distinct harness-specific failure modes that each needed a bespoke
carve-out: Grok's sandbox silently denying `bash` (exit 0, no real work),
Codex's `--ask-for-approval` flag incompatibility, Agy's 429 credit
exhaustion, and Grok's 402 billing exhaustion / session expiry.

Every new harness, or every fix to one harness's quirk, currently means
editing the same shared conditionals — raising the risk of regressing an
unrelated harness or an unrelated invariant.

## Goals

- Give each harness a single class owning everything that varies by harness
  name: command construction, output/event parsing, permission-flag
  translation, auth/quota-failure classification, and model-name resolution.
- Replace `dispatch_agent()`'s monolithic body with explicit pipeline stages
  (`resolve → authorize → prepare_worktree → spawn → observe → finalize`)
  driven by a typed `DispatchRequest`, without breaking any existing caller.
- Make adding a new harness, or fixing one harness's quirk, touch exactly one
  adapter file — never the shared pipeline.

## Non-goals

- No change to dispatch *routing policy* (`resolve_dispatch_harness`,
  `policy.json` capability allocation). This is purely an internal
  restructuring of how a dispatch is *executed* once a harness is chosen.
- No change to the public CLI surface (`synlynk dispatch ...` flags are
  unaffected).
- Not solving gh:#1922's completion-oracle/state-machine gap, or gh:#1926's
  state.db consolidation — related, tracked separately.
- No new model/media providers (OpenRouter, Fal.ai). Those are not harnesses
  under this design's definition (see "Why not OpenRouter/Fal.ai" below) and
  are already tracked as a separate, parked BYOA initiative.

## Why not OpenRouter / Fal.ai as harnesses

A harness in synlynk's vocabulary is an execution backend that runs a
dispatched *coding* task: it has a CLI binary to spawn as a subprocess, writes
real file diffs into a git worktree, opens PRs, and has permission/sandbox
semantics. `HarnessAdapter.build_cmd()` → subprocess spawn → git diff is the
whole contract this design is built around.

OpenRouter (an LLM API aggregation gateway) and Fal.ai (a generative-media
inference API) are model/API *providers*, not coding agents — neither writes
code into a worktree or opens a PR, and neither has a CLI process to spawn.
They already have a home in `synlynk/registry.py`'s BYOK provider entries and
are explicitly tracked as their own initiative (see
`docs/blog/25-pr64-v0.9.7-grok-agent-support.md`'s parked BYOA scope and
`docs/superpowers/plans/2026-09-19-master-4-wave-roadmap-and-autonomous-execution.md`'s
"Universal Aggregator" line item). Folding them into this spec would mix two
different shapes of problem (coding-harness execution vs. model-provider
integration) and is explicitly out of scope here.

## Architecture

```
DispatchRequest (frozen dataclass)
  — one field per current dispatch_agent() kwarg, built once at the top of
    the compatibility shim (see Migration, PR 1)

HarnessAdapter (Protocol, synlynk/harness_adapters/base.py)
  build_cmd(request: DispatchRequest) -> list[str]
  parse_output(raw_text: str) -> DispatchEvent      # structured, not a
                                                      # regex-scrape of stdout
  translate_permissions(permissions: list, read_only: bool) -> list[str]
  classify_failure(exit_code: int, stderr: str, raw_text: str) -> FailureKind | None
      # FailureKind: AUTH_EXPIRED | QUOTA_EXHAUSTED | SANDBOX_DENIED | None
  resolve_model(tier: str, effort: str | None) -> str

CodexAdapter / GrokAdapter / AgyAdapter / ClaudeAdapter / LocalAdapter
  — implement the Protocol; live in synlynk/harness_adapters/<name>.py
  — a small registry (ADAPTERS: dict[str, HarnessAdapter]) replaces the
    agent == "..." conditionals

Pipeline stages (new module synlynk/dispatch_pipeline.py)
  resolve()          — harness routing; calls existing resolve_dispatch_harness
                        unchanged
  authorize()        — policy/authority checks, gh-write gating; existing
                        logic, relocated unchanged
  prepare_worktree() — existing worktree creation / base-ref freshness logic,
                        relocated unchanged
  spawn()            — adapter.build_cmd() + subprocess spawn, replacing the
                        branching inside _spawn_with_pty_fallback
  observe()          — adapter.parse_output() + adapter.classify_failure()
                        per event/line
  finalize()         — job summary, telemetry, cost log; existing logic,
                        relocated unchanged
```

`dispatch_agent()` becomes a thin compatibility shim: build a
`DispatchRequest` from its existing 27 kwargs, call the five stages in order,
return the same `dict` shape it always has. **No caller changes** — every
existing CLI command, test, and internal call site keeps working as-is.

## Migration: strangler pattern, Codex pilot

Given the file's churn rate and the safety invariants it enforces, this ships
incrementally, one harness at a time, with old and new paths coexisting until
migration completes.

1. **PR 1** — Land `DispatchRequest`, the `HarnessAdapter` Protocol, the
   registry, and `dispatch_pipeline.py`. For every harness except Codex, the
   new stages call a `LegacyAdapter` that just delegates to the existing
   branching code, unchanged. Zero behavior change for Grok/Agy/Claude/local.
2. **PR 2** — Implement `CodexAdapter` for real (pilot harness: default
   GitHub-write router per #426, relatively predictable failure modes).
   Route Codex dispatches through it. Verify against real dispatch traffic —
   ground-truth via `gh pr view --json ...` / direct diff checks, not job
   status labels alone, per the standing "never trust job status alone"
   lesson — before calling it proven.
3. **PR 3–5** — Port Grok, Agy, and Claude/local, one PR each, with the same
   verify-before-next-port discipline. Delete `LegacyAdapter` once all four
   are ported.
4. **Follow-up (separate issue, out of scope here)** — migrate internal call
   sites to construct `DispatchRequest` directly instead of passing kwargs,
   once the pipeline has been stable in production for a while.

`DispatchRequest` wraps internally first: `dispatch_agent()`'s public
signature does not change in this effort.

## Testing

- Each adapter gets a focused unit-test file (`test_codex_adapter.py`, etc.)
  covering `build_cmd` / `classify_failure` against fixtures recorded from
  this session's real incidents: Grok's bash-denying sandbox silent no-op,
  Codex's `--ask-for-approval` incompatibility, Agy's 429, Grok's 402 —
  as regression cases.
- Pipeline stages get isolated tests against a fake adapter, so
  `authorize`/`prepare_worktree`/`finalize` logic is tested without spawning
  real subprocesses.
- Existing `dispatch_agent()` integration tests must keep passing unmodified
  throughout — the shim preserves the exact signature and return shape, so
  no test changes should be needed until the follow-up `DispatchRequest`
  caller migration.

## Error handling

`classify_failure` returning `AUTH_EXPIRED` / `QUOTA_EXHAUSTED` /
`SANDBOX_DENIED` replaces today's ad hoc stderr string-matching scattered
through `dispatch.py`. This becomes the natural hook point for a future
auto-fallback-to-another-harness feature (e.g., Grok 402 → auto-redispatch to
Agy per the existing manual fallback pattern) — but implementing that
fallback automation is out of scope for this spec; it only needs the
classification to exist as a clean seam.

## Open questions for sign-off

None outstanding — scope, adapter surface, migration order, and pilot harness
were all confirmed during brainstorming. Ready for the implementation plan.
