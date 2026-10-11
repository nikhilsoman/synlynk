# Circuit Breaker Blind Spot in Long Codex Turns — Design

gh:#1937 (cost-inflation record, $133/44M tokens, 2026-10-03)

## Problem

The in-flight circuit breaker (`synlynk/circuit_breaker.py::evaluate_job_circuit_breaker`)
is enforced on a steady cadence independent of CLI activity — confirmed by reading
`_reconcile_daemon_jobs` (`synlynk/jobs.py:4420-4489`), which documents explicitly:
"Invariant 2 must be enforced by the daemon's own polling path. CLI reconciliation
is opportunistic and does not run while `synlynk dispatch` jobs are active." So the
breaker's *polling cadence* is not the gap.

The gap is in **token visibility**. `_extract_codex_structured`
(`synlynk/costs.py:166-195`) derives usage exclusively from `turn.completed` events
in the Codex JSONL stream — it scans every line, keeps overwriting `usage` with
each `turn.completed` it finds, and returns the last (cumulative) one seen so far.
This works correctly *between* turns. It is blind *within* a turn: Codex's own
event stream reports usage only once a turn completes, and a single turn can
contain an unbounded number of tool-loop round trips (e.g. an agent dispatched to
"watch CI" repeatedly shelling out to `gh pr checks --watch` / `gh run watch` /
pytest-poll loops, each round trip re-sending the full growing cached context as a
tool call *within the same turn*, not as a new turn).

When no `turn.completed` line exists yet, `extract_tokens()` falls through to the
legacy regex patterns (`synlynk/costs.py:491-528`), which look for human-readable
strings like `"Input tokens: ... Output tokens: ..."` that Codex's JSONL stream
does not contain. The result is `in_tokens=0, out_tokens=0` for the breaker's
entire check, every poll, for the full duration of that one open turn — however
long it runs, however much it costs. gh:#1937's job spent 42 minutes and $133/44M
tokens inside what the evidence indicates was effectively one such long open turn;
the breaker's own ceiling ($15 cost / 5M tokens for the reasoning tier) was crossed
around minute 8 by the job's real billed usage, but the breaker had no signal to
compare against until a `turn.completed` line finally appeared — by which point
the job had already run to completion or external termination.

This is the same failure shape as five previously-closed issues (#1531, #1827,
#1738, #1850, #1880) — empty-poll-loop token re-billing — but none of their fixes
address the *detection* gap; they address downstream symptoms (dispatch task
framing, zero-file heuristics) that don't help when the extractor itself reports
zero activity throughout the runaway turn.

## Non-goals

- Not attempting to change Codex's own event schema or get it to emit
  intra-turn usage deltas — that's not ours to change, and no evidence in this
  codebase suggests Codex's `exec --json` stream emits any such signal (searched
  `synlynk/costs.py` for every known event type it currently parses: `turn.completed`,
  `turn.failed`, `error` — no intermediate usage-bearing event type is referenced
  anywhere in this codebase).
- Not attempting to change dispatch task-framing conventions (discouraging
  `--watch`-style polling loops in task prompts) — that is a policy/prompt-text
  change, not a code fix, and is already partially covered by #1531/#1827/#1738/#1850/#1880's
  prior framing-level mitigations. This spec is scoped to the detection gap only.
- Not reworking `_extract_codex_structured`'s per-turn semantics (`parse_dispatch_turns`
  already correctly derives per-turn deltas from `turn.completed` events for the
  cost ledger) — that logic is correct for what it measures; it's just not a
  sufficient *live safety* signal.

## Approach: log-size runaway as a vendor-agnostic safety net

Add a second, independent breaker trigger in `evaluate_job_circuit_breaker` that
does not depend on structured token extraction at all: **raw log file size**.

Rationale: an open tool-loop turn that re-sends growing cached context on every
round trip necessarily re-logs that growing transcript to the job's log file,
even though `extract_tokens()` can't yet attribute it to a token count. Log size
is a crude but vendor-agnostic proxy that fires regardless of which harness is
running or whether that harness's structured-output schema has a mid-turn blind
spot — it would have caught gh:#1937's job turn well before minute 8 purely from
transcript growth, with no dependency on Codex's event semantics.

This is deliberately a safety net, not a replacement for token/cost accounting:
it trips a coarser, size-based ceiling that exists purely to bound worst-case
blast radius during a detection blind spot, independent of harness and model.

### Config

Extend `circuit_breaker` config block (`synlynk/circuit_breaker.py` constants) with:

```python
DEFAULT_MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
```

Added to `_resolve_circuit_breaker_limits`'s return and to `DEFAULT_TIER_OVERRIDES`
tier dicts (reuse the existing `max_job_tokens`/`max_job_cost_usd` per-tier override
pattern — e.g. `"reasoning": {..., "max_log_size_bytes": 50 * 1024 * 1024}`).

50MB is chosen as roughly 10x the log size of a normal completed job in this
codebase's existing telemetry (to be confirmed against `telemetry.json` samples
during implementation — if actual completed-job log sizes run larger than
expected, the implementing engineer should adjust this constant and note the
evidence in the PR, not silently change it without justification).

### Trigger logic

In `evaluate_job_circuit_breaker` (`synlynk/circuit_breaker.py:181-191`), add a
check alongside the existing cost/token/zero-file checks:

```python
log_size_bytes = 0
if log_file and os.path.exists(log_file):
    try:
        log_size_bytes = os.path.getsize(log_file)
    except OSError:
        log_size_bytes = 0

reason = None
if cost_usd >= max_cost:
    reason = f"Cost limit breached: ${cost_usd:.2f} >= ${max_cost:.2f}"
elif total_tokens >= max_tokens:
    reason = f"Token limit breached: {total_tokens:,} >= {max_tokens:,} tokens"
elif log_size_bytes >= max_log_size_bytes:
    reason = (
        f"Log size runaway: {log_size_bytes:,} bytes >= {max_log_size_bytes:,} bytes "
        f"(extracted tokens: {total_tokens:,} — likely mid-turn token-extraction blind spot)"
    )
elif total_tokens >= zero_file_threshold:
    ...  # existing zero-file check, unchanged
```

Placed after the token/cost checks (so a harness with correct live token
visibility never trips the coarser log-size net first) but before the zero-file
check (a log-size runaway is a stronger, more specific signal than zero-file —
it should preempt the zero-file message rather than let a vaguer "0 files
touched" reason win when both are true).

The reason string explicitly surfaces `total_tokens` alongside the log-size
trigger so the resulting sentinel alert and telemetry record carry forward the
diagnostic fact (extracted tokens are implausibly low relative to log volume) for
whoever investigates the tripped job — directly useful for any future reassessment
of whether a given harness's extractor has its own blind spot.

### Telemetry

No new telemetry fields — the existing `circuit_breaker` telemetry event
(`synlynk/circuit_breaker.py:249-257`) already carries `reason`, which will now
include the log-size-runaway case. No schema migration needed.

## Testing

Unit tests in `tests/` (exact path: `tests/test_circuit_breaker.py` — confirm this
file exists and extend it, or create it if circuit breaker currently has no
dedicated test file; implementing engineer should check first):

1. **Log-size runaway trips independent of token extraction returning zero**:
   construct a job with a `log_file` fixture that is a plain-text file (no
   `turn.completed` JSON lines at all — simulating the mid-turn blind spot)
   padded to exceed `max_log_size_bytes`, assert `evaluate_job_circuit_breaker`
   returns `tripped=True` with reason containing `"Log size runaway"`.
2. **Log-size check does not fire below threshold**: same fixture shape, log
   file padded to just under the threshold, assert `tripped=False`.
3. **Cost/token checks still win when both would trigger**: a log file large
   enough to cross `max_log_size_bytes` AND containing a `turn.completed` event
   whose usage crosses `max_cost`/`max_tokens` — assert the reason string is the
   cost/token message, not the log-size message (order-of-checks regression
   guard).
4. **Zero-file check still fires when log-size is below threshold but tokens
   cross `zero_file_threshold`**: regression guard that this spec's reordering
   didn't break the existing zero-file path.
5. **Tier override resolution**: assert `_resolve_circuit_breaker_limits` returns
   a tier-specific `max_log_size_bytes` when `job["tier"]` matches a
   `DEFAULT_TIER_OVERRIDES` key with that key set, and the top-level default
   otherwise — mirrors the existing test pattern for `max_job_tokens`/`max_job_cost_usd`
   tier overrides (check whatever existing test already covers that pattern in
   `tests/test_circuit_breaker.py` and follow its structure).

## Rollout risk

A 50MB log is also plausible for a long, legitimate multi-file refactor job with
verbose tool output (not just a runaway poll loop). This is a real false-positive
risk. Mitigate by:

- Logging the trip reason with the extracted token count visible (already
  covered above) so a legitimate-but-verbose job's false positive is easy to
  distinguish at review time from a genuine blind-spot runaway (the former will
  show a *plausible* token count near the log size; the latter will show
  `total_tokens: 0` or near-zero against a 50MB+ log).
- Starting the default at 50MB (intentionally generous) rather than tuning
  tightly on day one. If live telemetry after rollout shows the trigger firing
  on legitimate jobs, raise the default — this is an explicit trade-off to
  record in the follow-up issue, not something to pre-optimize without data.

## Open question for implementing engineer

Confirm against `telemetry.json`/`cost_entries` whether any currently-running
legitimate job type (e.g. a large multi-file Grok/Agy dispatch) regularly
produces logs anywhere near 50MB before completing successfully. If so, surface
that in the PR description — it may justify a higher default or a
per-harness/per-tier override rather than a single global constant.
