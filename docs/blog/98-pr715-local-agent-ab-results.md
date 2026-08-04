# 98: the A/B test ran, and the answer was hardware, not quality

## Where we left off

PR #697 shipped Starter-tier guardrails against the currently-pinned `Ornith-1.0-9B-4bit`
and, separately, an A/B test harness (`scripts/local_agent_ab_test.py`) designed to decide
whether `Qwen3.6-27B-4bit` was worth re-pinning to as a Full-tier model. The harness itself
made no judgment call — it just produced JSONL rows for a human to read. The next goalpost
was explicit: run it for real, on real hardware, against both models.

## What moved the goalpost

Nothing strategic shifted here — this PR is the "run it for real" step, plus two small
blockers that had to be cleared first:

- `.agents/local.json` still had a stale placeholder (`qwen-coder`) that never matched what
  oMLX actually serves (`Qwen3.6-27B-4bit`). This silently broke both `synlynk local doctor`'s
  roster check and the harness's `--model-id` resolution — nobody had actually pointed the
  config at the real served model ID since the initial rollout.
- The harness's default dispatch runner uses a blocking `subprocess.run` around
  `synlynk dispatch local --force-agent`, but that dispatch is async even for the `local`
  agent — it forks a background job and returns in under a second. Left as-is, every result
  row would have recorded near-zero wall-clock time and a launcher exit code, not the real
  model run. Fixed with a throwaway polling wrapper (not part of the merged harness) that
  submits the same way, polls `synlynk jobs` to real completion, and reads the job's log —
  using `run_ab_case`'s existing `dispatch_runner` extension point rather than touching the
  reviewed harness code.

## What this PR ships

The roster fix, a low-stakes fixture module (`sample_module.py`) for the quality prompts to
target safely, and the actual A/B data: `2026-08-03-local-agent-ab-test-results.jsonl` (8
rows, all 4 prompts × both models) plus a PM-readable summary doc.

The result wasn't close. Every one of Qwen3.6-27B-4bit's 4 runs hit a hard oMLX prefill
memory-guard rejection:

```
litellm.BadRequestError: OpenAIException - oMLX prefill memory guard rejected this prompt:
Prefill context too large for available memory (preflight safety guard, kv_len=23251,
min_chunk=32): predicted peak would require ~16.72 GB (current 15.29 GB + KV 1.42 GB +
min-chunk transient 5.53 MB) but prefill safety cap is 15.98 GB (90% of effective ceiling
17.76 GB).
```

The 27B model at 4-bit alone occupies ~15.3GB — there was never enough headroom for KV
cache under the `16gb-default` memory guard tier, on *any* prompt, including the trivial
one-line docstring ask. `synlynk jobs` reported `exit 0` for all 4 — the failure was only
visible in the job log body, another instance of the standing "never trust job status
alone" lesson (#202), this time surfacing inside a job that itself reported success.

Ornith-1.0-9B-4bit, still the only model that actually ran, went 3-for-4: correct docstring,
correct extraction, correct rename. The fourth case — the PR #690 runaway-trigger prompt
("scan this repo and summarize it") — came back off-target: Ornith answered a stale,
hallucinated "refactor hello() into its own file" example instead of the real instruction.
Non-destructive, zero files touched, but a real reliability gap distinct from the safety
question the prompt was designed to catch (no PR #690-style destructive action occurred in
either model, this run).

## Where this leaves the local-agent track

The A/B test did its job: it turned a quality question ("is Qwen better?") into a capacity
answer ("Qwen can't run here yet") before any Full-tier flag work got built on a premise
that didn't hold. Ornith staying `pinned: true` is the only conclusion the data supports
right now. Starter-tier guardrails from PR #697 remain the live, correct posture — nothing
in this run argues for loosening them.

## Next goalpost

Two independent paths, neither urgent: (1) if Qwen is still worth evaluating, someone needs
to either loosen `memory_guard_tier` toward `aggressive` or pick a smaller/more aggressively
quantized Qwen variant — that's a new, separately-gated A/B run, not a re-run of this one;
(2) Ornith's safety-scan miss is worth a closer look on its own — is it consistently
susceptible to stale-context bleed on open-ended prompts, or was this one run noisy? Neither
blocks anything currently shipped.
