# Local Harness Model Qualification Matrix — 2026-10-16

**Ticket:** gh:#2348
**Epic:** gh:#2342
**Goal:** `goal-8d34c416`
**Scope:** oMLX + Aider + Synlynk local policy on the evaluated Apple Silicon host
**Tooling:** oMLX 0.5.3; Aider 0.86.2

## Decision summary

Ornith has passed the first live stack check. Qwen2.5-Coder passed an
isolated Aider edit through the Docker-only qualification network using
Aider's `whole` edit format, but it did **not** pass the subsequent 24-task
quality and safety benchmark. Gemma4 has passed initial authenticated serving
but has not passed the same Aider gate.

The former Qwen3.6 profile is **rejected for the earlier host configuration**. Although oMLX advertised it, its first small authenticated request failed with HTTP 507 `Insufficient Storage`. It is not a selectable profile. The replacement Qwen2.5-Coder 14B candidate passed initial serving but did not meet the later safety and quality gate.

Ternary Bonsai remains **blocked** by unavailable `prism_ml` support in the local policy. Gemma4 has moved from blocked to **preliminary viable** after its first authenticated inference succeeds; it is not yet an approved profile or Aider-qualified candidate.

## Evidence and status

| Candidate | Live `/v1/models` ID | Authenticated inference | Aider isolated edit | Status | Decision |
| --- | --- | --- | --- | --- | --- |
| Ornith | `Ornith-1.0-9B-4bit` | Passed: 4.27s small probe | Passed: scoped Git-worktree edit; full live suite 2 passed in 26.34s | Experimental baseline | Retain for benchmark only. |
| Qwen2.5-Coder | `Qwen2.5-Coder-14B-Instruct-4bit` | Passed: exact-response probe; 9.75s wall time including 4.74s model load | Passed one-file edit; failed 24-task live safety/quality qualification (11/24 correct, 7 unexpected read-only writes) | Benchmark-only, non-qualifying | Do not route or promote to pilot. Retain only as recorded comparison evidence. |
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

## Live 24-task Qwen result

On 2026-10-17, Qwen2.5-Coder completed the fixed 24-task benchmark through
the Docker-only Aider/oMLX path. The first run identified a harness issue:
the prompt file and Aider history files were written into the mounted
worktree and were incorrectly counted as model edits. That issue was fixed in
PR #2365, independently reviewed, and merged before the repeat run.

The repeat run recorded host oMLX memory evidence of 1,727.7 MiB and completed
all 24 tasks. It scored 11/24 (45.8%) and made seven unauthorized writes on
tasks that required no file change. All four `target.py` bounded edits remained
in scope and passed their tests, but the qualification gate requires **zero**
unsafe/no-op/out-of-scope edits as well as at least 85% correctness. Qwen is
therefore not qualified for routing or the pilot. The full operational receipt
is summarized on gh:#2348.

## Next qualification gate

The pre-pilot gate requires a complete 24-task live benchmark: eight test/log
summaries, eight diagnoses, four explanations, and four tightly bounded
mechanical/documentation edits. Advancement requires at least 85% correctness,
zero unsafe/no-op/out-of-scope edit events, and verified memory within budget.

Gemma4 requires a successful isolated Aider edit before it can join the
benchmark. The former Qwen3.6 candidate requires a capacity remediation and
fresh probe. Bonsai remains deferred until the separate Prism/oMLX
compatibility question is resolved.

### Live Ornith result

On 2026-10-17, the live 24-task Ornith baseline completed through isolated
Docker Aider and authenticated oMLX using `diff` edit mode. It scored 21/24
(87.5%): test/log summaries 8/8, diagnoses 5/8, bounded explanations 4/4,
and bounded edits 4/4. Each of the four `target.py` edits stayed in scope and
passed its test. Two diagnosis tasks (`diagnosis-01` and `diagnosis-03`) hit
the 300-second execution timeout. The original runner version mislabeled these
timeouts as safety events. Timeouts remain visible as failed task outcomes and
reduce correctness, but are not unsafe edits by themselves; unsafe/no-op/out-
of-scope edits remain a separate zero-tolerance gate. New receipts distinguish
timeouts, Aider/provider failures, and incorrect responses, and include only a
bounded secret-redacted excerpt for failed tasks. The complete task receipt is at
`/private/tmp/ornith-qualification-live-v3.json` on the evaluated host.

The runner was supplied `--peak-memory-mb 925.0`, based on an observed host
oMLX process RSS snapshot before the run; it was copied into each task receipt.
This was not a sampled high-water measurement across the full benchmark, so
the run does not establish the memory-budget gate. The timeout classification
correction does not change the recorded 21/24 score or resolve the missing
high-water memory measurement.

No candidate currently qualifies for a pilot. Qwen2.5-Coder failed at 45.8%
with seven unexpected writes. Ornith met the correctness and bounded-edit gates,
but its live receipt lacks a sampled full-run memory high-water measurement;
repeat the run with memory telemetry before promotion. Gemma4 requires a
successful isolated Aider edit before it can join the benchmark. The former
Qwen3.6 candidate requires a capacity remediation and fresh probe. Bonsai
remains deferred until the separate Prism/oMLX compatibility question is
resolved.

The active local roster is intentionally more restrictive than the live oMLX
inventory: Ornith is the only normal-dispatch model. Qwen2.5-Coder is retained
with `dispatch_eligible: false` and `qualification: benchmark-only`, so it is
visible to the controlled benchmark runner but cannot become a normal local
dispatch default. Qwen3.6 and Bonsai are absent from the roster; Gemma4 remains
outside it until its Aider qualification succeeds.

### Reproducible benchmark receipt

`scripts/local_qualification_benchmark.py` implements the fixed 24-task
corpus: eight test/log summaries, eight diagnoses, four bounded explanations,
and four scoped mechanical/documentation edits. Every task receipt records the
exact model ID and Aider mode, completion/correctness, test result, declared
scope, retry count, wall time, memory evidence, changed paths, and safety
events (no-op, unexpected edit, or out-of-scope edit).

Use a dry run only to validate runner plumbing:

```sh
python scripts/local_qualification_benchmark.py --output /private/tmp/local-benchmark-dry.json
```

For qualification evidence, first start `omlx-relay` as documented in
`local-harness-isolated-qualification.md`, source the ignored local oMLX
environment file, then run:

```sh
python scripts/local_qualification_benchmark.py --live \
  --peak-memory-mb <host-omlx-peak> \
  --output /private/tmp/qwen2.5-coder-qualification.json
```

Only a **live** receipt can advance a candidate. It requires all 24 tasks,
at least 85% correctness, memory evidence on every task, and zero unsafe,
no-op, or out-of-scope edit events. Execution failures such as timeouts remain
visible in task failure classifications and count against correctness. A dry
run is never routing evidence; a failed threshold keeps Qwen in
its `benchmark-only` roster state and leaves normal local routing disabled.
The peak-memory input must come from host oMLX telemetry for the serialized
run; Docker client memory is not accepted as model-memory evidence.
