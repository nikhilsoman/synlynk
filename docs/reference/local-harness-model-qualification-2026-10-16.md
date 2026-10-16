# Local Harness Model Qualification Matrix — 2026-10-16

**Ticket:** gh:#2348
**Epic:** gh:#2342
**Goal:** `goal-8d34c416`
**Scope:** oMLX + Aider + Synlynk local policy on the evaluated Apple Silicon host
**Tooling:** oMLX 0.5.3; Aider 0.86.2

## Decision summary

Ornith has passed the first live stack check. Qwen2.5-Coder has now also
passed an isolated Aider edit through the Docker-only qualification network,
using Aider's `whole` edit format. It is the primary candidate for the
24-task quality and safety benchmark, but is not pilot-approved yet. Gemma4
has passed initial authenticated serving but has not passed the same Aider
gate.

The former Qwen3.6 profile is **rejected for the earlier host configuration**. Although oMLX advertised it, its first small authenticated request failed with HTTP 507 `Insufficient Storage`. It is not a selectable profile. The replacement Qwen2.5-Coder 14B candidate has passed initial serving and is the primary coding challenger.

Ternary Bonsai remains **blocked** by unavailable `prism_ml` support in the local policy. Gemma4 has moved from blocked to **preliminary viable** after its first authenticated inference succeeds; it is not yet an approved profile or Aider-qualified candidate.

## Evidence and status

| Candidate | Live `/v1/models` ID | Authenticated inference | Aider isolated edit | Status | Decision |
| --- | --- | --- | --- | --- | --- |
| Ornith | `Ornith-1.0-9B-4bit` | Passed: 4.27s small probe | Passed: scoped Git-worktree edit; full live suite 2 passed in 26.34s | Experimental baseline | Retain for benchmark only. |
| Qwen2.5-Coder | `Qwen2.5-Coder-14B-Instruct-4bit` | Passed: exact-response probe; 9.75s wall time including 4.74s model load | Passed: requested one-file Python edit in isolated Docker Aider 0.86.2; `whole` format | Benchmark candidate | Primary coding candidate; run the 24-task benchmark before routing any work. |
| Qwen3.6 (historical) | No longer live | Failed: HTTP 507 `Insufficient Storage` in 0.30s | Not attempted; serving precondition failed | Rejected | Do not route. Re-evaluate only after a capacity change. |
| Ternary Bonsai | `Ternary-Bonsai-2-27B-mlx-2bit` | Not attempted | Not attempted | Blocked | `prism_ml` is absent; existing policy falls back to Ornith. No loader work in v1. |
| Gemma4 | `gemma-4-12B-it-qat-4bit` | Passed: exact-response probe; 21.70s wall time including 14.20s model load | Did not complete the equivalent isolated Aider edit | Serving-only | Hold from coding dispatch; investigate Aider compatibility before re-testing. |

The initial live inventory contained Ornith, Qwen3.6, and Bonsai. After the host roster was intentionally revised, the authenticated live inventory contains Ornith, Qwen2.5-Coder, and Gemma4. The endpoint required `OPENAI_API_KEY`; unauthenticated requests returned HTTP 401. The credential was supplied from a local ignored environment file and was not logged or committed.

## Method

1. Discover the authenticated `/v1/models` inventory.
2. Send one sequential OpenAI-compatible `chat/completions` request per candidate with a 16-token response limit; capture status, latency, and usage without exposing credentials.
3. For a candidate that serves successfully, run the opt-in hardware test: `pytest -q tests/test_local_agent_hardware.py -m local_hardware -v`. It verifies authenticated inventory and a real Aider edit in a disposable Git repository using the active local profile.
4. For a coding candidate, run the equivalent edit in the dedicated internal Docker network. Aider gets only a disposable Git worktree mount; an `alpine/socat` relay is its sole network peer and forwards only to native host oMLX on port 8000. The Compose contract is documented in `docs/reference/local-harness-isolated-qualification.md`.
5. Do not invoke a candidate that fails capacity or loader preconditions just to obtain a second failure. Record it as blocked/rejected and preserve the working baseline.

## Compatibility notes

Qwen3.6 has documented oMLX operational risks beyond this host’s capacity failure, including context/vision handling regressions and concurrent-request engine crashes. The local harness remains serialized at one dispatch, but the HTTP 507 result is independently sufficient to reject it here. See the oMLX [Qwen3.6 context issue](https://github.com/jundot/omlx/issues/1545) and [concurrency issue](https://github.com/jundot/omlx/issues/1800).

Gemma4 has evidence of oMLX support, but its DFlash optimization has known limitations for the common `gemma4_unified` model form. The exact QAT 4-bit candidate now appears in authenticated inventory and passes a first inference probe, but it still must pass the same isolated Aider stack test. See the oMLX [Gemma4 DFlash issue](https://github.com/jundot/omlx/issues/2153).

## Next qualification gate

Before traffic routing, Ornith must complete the 24-task benchmark from the approved plan: eight test/log summaries, eight diagnoses, four explanations, and four tightly bounded mechanical/documentation edits. Advancement requires at least 85% correctness, zero unsafe/no-op/out-of-scope edits, and memory within budget.

Qwen2.5-Coder is the only current candidate eligible for the 24-task benchmark.
Its first Aider `diff` edit attempt did not complete; use the proven `whole`
format for this gate. Gemma4 requires a successful isolated Aider edit before
it can join the benchmark. The former Qwen3.6 candidate requires a capacity
remediation and fresh probe. Bonsai remains deferred until the separate
Prism/oMLX compatibility question is resolved.

The active local roster is intentionally more restrictive than the live oMLX
inventory: Ornith is the only normal-dispatch model. Qwen2.5-Coder is retained
with `dispatch_eligible: false` and `qualification: benchmark-only`, so it is
visible to the controlled benchmark runner but cannot become a normal local
dispatch default. Qwen3.6 and Bonsai are absent from the roster; Gemma4 remains
outside it until its Aider qualification succeeds.
