# Local Harness Model Qualification Matrix — 2026-10-16

**Ticket:** gh:#2348
**Epic:** gh:#2342
**Goal:** `goal-8d34c416`
**Scope:** oMLX + Aider + Synlynk local policy on the evaluated Apple Silicon host
**Tooling:** oMLX 0.5.3; Aider 0.86.2

## Decision summary

Only Ornith has passed the first live stack check. It is an **experimental baseline**, not yet a pilot-approved coding model: it still needs the planned 24-task quality and safety benchmark.

Qwen3.6 is **rejected for the current host configuration**. Although oMLX advertises it, its first small authenticated request failed with HTTP 507 `Insufficient Storage`. It must not be selected or silently used as a fallback until host capacity and a repeatable Aider evaluation are demonstrated.

Ternary Bonsai and Gemma4 are **blocked**, not failed quality candidates: Bonsai is gated by unavailable `prism_ml` support in the current local policy, and Gemma4 is neither served by the live endpoint nor present in the local policy roster.

## Evidence and status

| Candidate | Live `/v1/models` ID | Authenticated inference | Aider isolated edit | Status | Decision |
| --- | --- | --- | --- | --- | --- |
| Ornith | `Ornith-1.0-9B-4bit` | Passed: 4.27s small probe | Passed: scoped Git-worktree edit; full live suite 2 passed in 26.34s | Experimental baseline | Retain for benchmark only. |
| Qwen3.6 | `Qwen3.6-27B-4bit` | Failed: HTTP 507 `Insufficient Storage` in 0.30s | Not attempted; serving precondition failed | Rejected on current host | Do not route. Re-evaluate only after a capacity change. |
| Ternary Bonsai | `Ternary-Bonsai-2-27B-mlx-2bit` | Not attempted | Not attempted | Blocked | `prism_ml` is absent; existing policy falls back to Ornith. No loader work in v1. |
| Gemma4 | None | Not attempted | Not attempted | Blocked | Not live in oMLX inventory and not an approved local profile. |

The live inventory at test time contained only the three IDs above. The endpoint required `OPENAI_API_KEY`; unauthenticated requests returned HTTP 401. The credential was supplied from a local ignored environment file and was not logged or committed.

## Method

1. Discover the authenticated `/v1/models` inventory.
2. Send one sequential OpenAI-compatible `chat/completions` request per candidate with a 16-token response limit; capture status, latency, and usage without exposing credentials.
3. For a candidate that serves successfully, run the opt-in hardware test: `pytest -q tests/test_local_agent_hardware.py -m local_hardware -v`. It verifies authenticated inventory and a real Aider edit in a disposable Git repository using the active local profile.
4. Do not invoke a candidate that fails capacity or loader preconditions just to obtain a second failure. Record it as blocked/rejected and preserve the working baseline.

## Compatibility notes

Qwen3.6 has documented oMLX operational risks beyond this host’s capacity failure, including context/vision handling regressions and concurrent-request engine crashes. The local harness remains serialized at one dispatch, but the HTTP 507 result is independently sufficient to reject it here. See the oMLX [Qwen3.6 context issue](https://github.com/jundot/omlx/issues/1545) and [concurrency issue](https://github.com/jundot/omlx/issues/1800).

Gemma4 has evidence of oMLX support, but its DFlash optimization has known limitations for the common `gemma4_unified` model form. It is not an eligible candidate until an exact MLX quantization is loaded, appears in authenticated inventory, and passes the same Aider stack test. See the oMLX [Gemma4 DFlash issue](https://github.com/jundot/omlx/issues/2153).

## Next qualification gate

Before traffic routing, Ornith must complete the 24-task benchmark from the approved plan: eight test/log summaries, eight diagnoses, four explanations, and four tightly bounded mechanical/documentation edits. Advancement requires at least 85% correctness, zero unsafe/no-op/out-of-scope edits, and memory within budget.

Qwen requires a host-capacity remediation and then a fresh probe. Gemma4 requires an approved profile plus a served exact model ID. Bonsai remains deferred until the separate Prism/oMLX compatibility question is resolved.
