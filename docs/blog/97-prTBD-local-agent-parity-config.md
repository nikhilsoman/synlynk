# 97: two-tier parity, shipped one tier at a time

## Where we left off

PR #95 (litellm provider-prefix fix) closed the loop on the `local` agent actually
*working* — a real dispatch reached Ornith and got a response instead of silently
no-opping. That fixed correctness. It said nothing about safety posture: `local`
dispatched with the same flag surface as every other agent, no guardrails scoped to
the fact that this agent runs against a small (9B, 4-bit) self-hosted model with no
vendor-side abuse controls behind it.

## What moved the goalpost

Brainstorming surfaced that "parity" for the `local` agent isn't one config, it's two:
a **Starter tier** (small model, conservative flags, safe defaults) and a **Full tier**
(larger model, `--architect` mode, autonomous lint/test) — gated by which model is
actually pinned in `.agents/local.json`. The open question was whether to build both
tiers now, or ship Starter immediately and defer Full.

The design spec resolved it by adding an A/B test as a gate: dispatch the same battery
of prompts (docstring add, mechanical rename, small extraction, plus the PR #690
runaway-trigger prompt) against both `Ornith-1.0-9B-4bit` (currently pinned) and
`Qwen3.6-27B-4bit` (Full-tier candidate), capture diff-correctness/safety-drift/wall-clock
data directly — not from job status — and let that data decide whether Full-tier is
worth building at all. The last open question, resolved explicitly rather than left
implicit: **ship Starter-tier guardrails now, against whichever model is currently
pinned, regardless of what the A/B test eventually shows.** Re-pinning to a different
model later is a separate, small change — it shouldn't block shipping the safety
guardrails that apply either way.

## What this PR ships

Two independent pieces, sequenced per the plan (`docs/superpowers/plans/2026-08-03-local-agent-parity-config.md`):

**The A/B harness** (`scripts/local_agent_ab_test.py`) — a standalone CLI, not a permanent
part of the dispatch path:

```python
def _build_temp_config(base_config: dict, model_id: str) -> dict:
    ...  # pins model_id, unpins everything else, never mutates the original
def run_ab_case(model_id, label, prompt, dispatch_runner=None) -> dict:
    ...  # swaps .agents/local.json, dispatches, restores config in a finally block
```

`run_ab_case` backs up and restores `.agents/local.json` around every run — including on
a raised exception from the dispatch itself — so a crashed A/B run can never leave the
repo's real agent config pointed at the wrong model. Results append as JSONL to
`project-docs/decisions/2026-08-03-local-agent-ab-test-results.jsonl`, one row per
model/prompt pair, for Claude/PM to read and decide from — the harness itself makes no
judgment call about which model wins.

**Starter-tier guardrails** (`synlynk/local_agent.py`), shipped against the currently-pinned
`Ornith-1.0-9B-4bit` per the resolved open question above:

```python
_STARTER_TIER_GUARDRAIL_FLAGS = [
    "--no-auto-lint", "--no-auto-test", "--map-tokens", "0",
]
```

appended unconditionally to every `local` dispatch's flags — no `--architect`, no
autonomous lint/test execution, no repo-map context leak. Full-tier flags are explicitly
*not* in this codepath; the function's docstring says so directly, so the boundary
survives the next person who edits this file without having read the spec.

Built via four sequential `synlynk dispatch codex` tasks for the harness (config-transform
→ config I/O/result-row → run_ab_case orchestration → CLI entrypoint) plus one for the
guardrail flags, each reviewed directly — diff read, tests re-run independently, never
trusting job self-report — before fast-forward merging into the branch. Codex caught two
real gaps in the plan itself without a round-trip: a missing `import json` in a test
snippet, and two pre-existing exact-match flag-list assertions (in both
`tests/test_local_agent.py` and `tests/test_dispatch_local_agent.py`) that needed updating
for the new flags — both anticipated in the plan's own regression-risk note, so this was
the plan working as intended, not a surprise.

## Where this leaves the local-agent track

Full project suite: 1622 passed, 2 skipped (baseline 1575 + ~15 new tests from this plan +
existing growth, 0 failures). Starter-tier guardrails are live against the currently-pinned
model regardless of what the A/B test later shows. Full-tier (`--architect`,
autonomous lint/test) remains explicitly out of scope for this plan — a future,
separately-gated change once the A/B data actually justifies re-pinning to a larger model.

## Next goalpost

Run the A/B harness for real against both models and read the results. If Qwen3.6-27B-4bit
wins on the data, re-pin `.agents/local.json` and build the Full-tier flag surface as its
own small, separately-reviewed change — the guardrail boundary this PR drew makes that a
config change plus a new flag set, not a rewrite.
