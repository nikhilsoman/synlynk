# Capability Sweep Quality Signal — Design

**Status:** Draft, pending user approval
**Related:** gh:#2170 (bug — this design fixes it), gh:#2169 (worktree self-cleanup — separate, unrelated fix), gh:#353 (self-attestation gap — already fixed, this issue is downstream of it), gh:#1993 (capability report generator — blocked on this)

## Problem

`synlynk capability sweep` seeds `capability_ratings` with calibration samples scored by a cross-harness verifier. On the 2026-10-10 run, all 20 samples — every harness (claude, codex, agy, grok), every model, all 3 task types (PROG/TEST/REQM) — scored exactly `quality=5.0`. A score that never varies carries no signal, which defeats the Empirical Capability Assessment Policy's entire premise: routing decisions driven by measured `quality`, not hand-written tables.

Root cause, confirmed by reading the code (not yet confirmed against a live verifier response — see Approach):

- `_verify_calibration_result` (`synlynk/capability_sweep.py:217-243`) dispatches a verifier harness, then calls `extract_verifier_meta` (`synlynk/costs.py:514-539`) to parse a `# synlynk-meta\nquality=<N>` block out of the verifier's raw output.
- If that block is absent or unparseable, `extract_verifier_meta` returns `None`.
- The caller then silently defaults: `"quality": float(meta.get("quality", 5.0))` (`capability_sweep.py:241`).
- Every sample landing on exactly `5.0` means this fallback fired on every single verifier dispatch this run — the verifier's actual response is never reaching the parser successfully.

This is distinct from gh:#353 (same-agent self-rating / gaming). #353's fix — `_pick_verifier_harness`/`_pick_verifier_agent` picking a genuinely different harness — is correctly wired here (log lines show real harness rotation, e.g. "verified by codex", "verified by claude"). The independence #353 bought is being thrown away downstream by a default that looks like a real verdict.

## Why this needs a fix before anything else

- `capability_ratings` rows written by every sweep run to date (this run's 20, and an unknown number of prior runs — not yet audited) are polluted with a non-discriminating constant.
- The failure is silent: no error, no warning, no distinguishable marker between "the verifier said 5.0" and "the verifier's response couldn't be parsed." Both look identical in the data today.
- `synlynk capability report` (gh:#1993) and the Empirical Capability Assessment Policy's sample-size gate both consume this data; neither has any way to tell real signal from fallback noise right now.

## Approach

Three options were considered:

**A — Fail loud, don't default silently.** Stop writing a plausible-looking `5.0` when parsing fails. Instead, mark the row distinctly (unverified, not just "verified at exactly the midpoint") and log the raw verifier output that failed to parse. This doesn't fix *why* parsing fails, but it turns an invisible bug into a visible, debuggable one, and it stops `capability_ratings` from being silently polluted going forward.

**B — Harden the verifier prompt/parsing contract.** Assume verifier harnesses aren't reliably emitting the exact `# synlynk-meta\nquality=<N>` format from the current natural-language ask (`capability_sweep.py:226-235`). Fix by tightening the prompt, adding a reformat retry, or loosening the parser. Risk: fixing a guessed cause without evidence that it's the actual one.

**C — A, then B, informed by what A reveals.** Ship A first — it's small, self-contained, and makes the failure observable. Capture the verifier's actual raw output in the loud-failure path (log line, not just a counter) so the next sweep run tells us definitively why parsing is failing: wrong format from the model, prompt not surviving dispatch, or a regex mismatch with real-world phrasing. Then fix whatever A's evidence points to, as a fast follow-up — not guessed now.

**Decision: C.** (User-approved in brainstorm discussion.)

## What this spec covers

Only the Approach-A half: making the fallback failure loud and evidence-producing. The actual root cause of why verifier output doesn't parse (the "B" half) is explicitly **out of scope** for this fix — it will be diagnosed from the evidence A produces on the next sweep run and filed/fixed separately. Do not guess the root cause and fix it here; that's the mistake Approach B-without-A would make.

## Design

### 1. Distinguish "verified" from "fallback" in the data

Add a new field to the verdict dict returned by `_verify_calibration_result`: `"quality_verified": bool` — `True` when `extract_verifier_meta` actually found and parsed a `quality` value, `False` when it fell back.

```python
def _verify_calibration_result(
    verifier_harness: str,
    executor_harness: str,
    model: str,
    skill: str,
    executor_output: dict,
) -> dict:
    ...
    result = _dispatch_calibration_task(verifier_harness, verify_task)
    from synlynk.costs import extract_verifier_meta

    raw_output = result.get("output", "")
    meta = extract_verifier_meta(raw_output) or {}
    quality_verified = "quality" in meta

    if not quality_verified:
        print(
            f"  [sweep] WARNING: verifier {verifier_harness} output for "
            f"{executor_harness}/{model} ({skill}) had no parseable "
            f"'# synlynk-meta' quality block — falling back, marking unverified.\n"
            f"  --- raw verifier output (first 2000 chars) ---\n"
            f"{raw_output[:2000]}\n"
            f"  --- end raw verifier output ---",
            file=sys.stderr,
        )

    return {
        "quality": float(meta.get("quality", 5.0)),
        "correct": bool(meta.get("correct", True)),
        "quality_verified": quality_verified,
    }
```

The raw-output dump is the key piece: it's what lets a human (or the next sweep-triage pass) actually see why parsing failed, instead of inferring it from silence.

### 2. Thread `quality_verified` through to the written rows

Two call sites write `capability_ratings`/`capability_calibration_results` rows using the verdict: `_run_sweep` (the main sweep path, writes `capability_ratings` with `quality_auto`) and the calibration-task path that writes `capability_calibration_results` (around `capability_sweep.py:176-190`).

- `capability_calibration_results`: add a `quality_verified INTEGER` column (SQLite boolean-as-int, matching the existing idiom for boolean columns in this schema — check `db.py`'s migration block for the exact pattern used elsewhere, e.g. the `unpushed_branch_check_attempts`-style idempotent `ALTER TABLE` + `try/except OperationalError` guard). Write `verdict["quality_verified"]` into it.
- `capability_ratings`: this table already has a `quality_auto` column (boolean, "was this score auto-generated vs. human-entered"). Reuse it correctly: `quality_auto` should be `True` only when `quality_verified` is `True`. Currently `_run_sweep` writes `quality_auto` unconditionally (need to check its current value at `capability_sweep.py` around the `INSERT INTO capability_ratings` block near line 288-301 and confirm/fix this). If `quality_auto` already means something else in this table's existing contract (it may mean "machine-scored at all, including defaults" — check other writers of this column before assuming), add a new boolean column (`quality_verified`) rather than overloading an existing one with a different meaning — the implementer must check existing `quality_auto` semantics across the codebase before deciding which path to take, and should ask if ambiguous rather than guess.

### 3. Downstream consumers skip unverified rows by default

Any current or future reader (`synlynk capability report`'s generator, gh:#1993; the Empirical Capability Assessment Policy's sample-size gate) should treat `quality_verified=False` rows as "no signal" — not countable toward the ≥5-merged-job sample-size minimum, and not averaged into a reported `quality` figure. Since the report generator (gh:#1993) hasn't shipped yet, this spec doesn't need to modify it — just needs the column/flag to exist so #1993's implementation can filter on it from day one. Note this dependency in #1993 as a comment when this fix lands.

### 4. No change to the dispatch/prompt/parsing logic itself

Per the Decision-C scoping above: `_verify_calibration_result`'s verifier prompt (lines 226-235) and `extract_verifier_meta`'s regex (costs.py:519) are **not touched** in this fix. They may well be the actual root cause, but we don't know that yet — A's job is to produce the evidence that tells us, not to guess ahead of it.

## Testing

- Unit test: `extract_verifier_meta` returns `None` on malformed/missing `# synlynk-meta` block (existing behavior — add a regression test if one doesn't already exist, to lock in the "returns None, doesn't raise" contract this fix depends on).
- Unit test: `_verify_calibration_result` returns `quality_verified=False` and logs the raw-output warning when `extract_verifier_meta` returns `None`; returns `quality_verified=True` when it returns a valid dict.
- Unit test: `_verify_calibration_result` with a mocked verifier dispatch returning a valid `# synlynk-meta\nquality=7\ncorrect=true` block produces `quality_verified=True`, `quality=7.0`.
- Unit test: the `capability_calibration_results` INSERT writes the correct `quality_verified` value for both branches.
- Unit test: the `capability_ratings` INSERT (`_run_sweep`) writes a consistent `quality_auto`/`quality_verified` value — confirm existing `quality_auto` semantics via a grep/read of other writers before asserting the "right" value in the test.
- Migration test: `ALTER TABLE capability_calibration_results ADD COLUMN quality_verified` is idempotent (running the migration twice doesn't error), matching the existing idempotent-migration pattern in `db.py`.
- No integration/live-dispatch test is required for this fix — it only changes bookkeeping/logging around an existing dispatch call, not the dispatch itself.

## Out of scope (explicitly, for the next person reading this)

- Fixing *why* the verifier's output doesn't parse (the actual root cause of the flat 5.0s). This is Approach B, deferred until A's evidence (the raw-output log dump) is available from a real sweep run.
- Backfilling/auditing historical `capability_calibration_results`/`capability_ratings` rows for the same pattern. Worth doing, but a separate pass once this fix is live (mentioned in gh:#2170 as a follow-up, not committed to here).
- `synlynk capability report`'s actual implementation (gh:#1993) — this spec only ensures the data it will read has a `quality_verified` flag to filter on.
- gh:#2169 (worktree/branch self-cleanup) — unrelated fix, tracked separately, not part of this spec.
