# Circuit Breaker Log-Size Runaway Net Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a vendor-agnostic log-file-size trigger to `evaluate_job_circuit_breaker` so a runaway job trips even when the harness's structured token extractor reports zero activity for the whole duration of one long tool-loop turn (the gh:#1937 root cause).

**Architecture:** Extend `_resolve_circuit_breaker_limits` to also resolve a `max_log_size_bytes` ceiling (default 50MB, overridable per-tier via the existing `DEFAULT_TIER_OVERRIDES` pattern). Insert a new `elif` branch in `evaluate_job_circuit_breaker`'s trigger chain, positioned after the cost/token checks (so correct live token visibility always wins) and before the zero-file check (a log-size runaway is a stronger, more specific signal). No changes to `synlynk/costs.py` — this is a pure safety-net addition, independent of token extraction.

**Tech Stack:** Python 3 stdlib only (`os.path.getsize`), pytest for tests. Single file change: `synlynk/circuit_breaker.py`. Single test file change: `tests/test_circuit_breaker.py`.

**Reference spec:** `docs/superpowers/specs/2026-10-11-cost-inflation-circuit-breaker-visibility-design.md` (commit `482307da`, gh:#1937).

---

## Task 1: Add `max_log_size_bytes` to limits resolution

**Files:**
- Modify: `synlynk/circuit_breaker.py:23-31` (constants), `synlynk/circuit_breaker.py:46-76` (`_resolve_circuit_breaker_limits`)
- Test: `tests/test_circuit_breaker.py`

- [ ] **Step 1: Write the failing test for tier-override resolution**

Add to `tests/test_circuit_breaker.py` (append at end of file):

```python
def test_circuit_breaker_resolves_log_size_tier_override():
    from synlynk.circuit_breaker import _resolve_circuit_breaker_limits

    job = {"id": "job-tier-log-size", "agent": "codex", "model_tier": "fast"}
    config = {
        "circuit_breaker": {
            "max_job_tokens": 5_000_000,
            "max_job_cost_usd": 15.00,
            "zero_file_token_threshold": 500_000,
            "tier_overrides": {
                "fast": {
                    "max_job_tokens": 500_000,
                    "max_job_cost_usd": 2.00,
                    "max_log_size_bytes": 10 * 1024 * 1024,
                },
            },
        }
    }
    max_tokens, max_cost, zero_file_threshold, max_log_size_bytes = (
        _resolve_circuit_breaker_limits(job, config)
    )
    assert max_log_size_bytes == 10 * 1024 * 1024

    # No tier override set for this job's tier -> falls back to top-level default
    job_no_override = {"id": "job-default-log-size", "agent": "codex", "model_tier": "pro"}
    _, _, _, default_log_size = _resolve_circuit_breaker_limits(job_no_override, config)
    assert default_log_size == 50 * 1024 * 1024
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_circuit_breaker.py::test_circuit_breaker_resolves_log_size_tier_override -v`
Expected: FAIL — `_resolve_circuit_breaker_limits() takes ... returned 3 values ... cannot unpack 4` (or a similar unpack/TypeError, since the function currently returns a 3-tuple).

- [ ] **Step 3: Extend the constant and `_resolve_circuit_breaker_limits`**

In `synlynk/circuit_breaker.py`, change lines 23-31 from:

```python
DEFAULT_MAX_JOB_TOKENS = 5_000_000
DEFAULT_MAX_JOB_COST_USD = 15.00
DEFAULT_ZERO_FILE_TOKEN_THRESHOLD = 500_000

DEFAULT_TIER_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "fast": {"max_job_tokens": 500_000, "max_job_cost_usd": 2.00},
    "pro": {"max_job_tokens": 3_000_000, "max_job_cost_usd": 10.00},
    "reasoning": {"max_job_tokens": 5_000_000, "max_job_cost_usd": 15.00},
}
```

to:

```python
DEFAULT_MAX_JOB_TOKENS = 5_000_000
DEFAULT_MAX_JOB_COST_USD = 15.00
DEFAULT_ZERO_FILE_TOKEN_THRESHOLD = 500_000
DEFAULT_MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50MB

DEFAULT_TIER_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "fast": {"max_job_tokens": 500_000, "max_job_cost_usd": 2.00},
    "pro": {"max_job_tokens": 3_000_000, "max_job_cost_usd": 10.00},
    "reasoning": {"max_job_tokens": 5_000_000, "max_job_cost_usd": 15.00},
}
```

(Tier dicts are deliberately left without a `max_log_size_bytes` key by default — the 50MB global default applies uniformly across tiers unless a config explicitly overrides it, per the spec's "starting generously" rollout guidance.)

Then change the function signature and body (lines 46-76) from:

```python
def _resolve_circuit_breaker_limits(
    job: dict,
    config: Optional[dict] = None,
) -> Tuple[int, float, int]:
    """Resolve max_tokens, max_cost, and zero_file_threshold from config and tier overrides."""
    cb_config = {}
    if config and isinstance(config, dict):
        cb_config = config.get("circuit_breaker", {})
        if not isinstance(cb_config, dict):
            cb_config = {}

    max_tokens = int(cb_config.get("max_job_tokens", DEFAULT_MAX_JOB_TOKENS))
    max_cost = float(cb_config.get("max_job_cost_usd", DEFAULT_MAX_JOB_COST_USD))
    zero_file_threshold = int(
        cb_config.get("zero_file_token_threshold", DEFAULT_ZERO_FILE_TOKEN_THRESHOLD)
    )

    tier_overrides = cb_config.get("tier_overrides", DEFAULT_TIER_OVERRIDES)
    job_tier = str(job.get("model_tier") or job.get("tier") or "").strip().lower()

    if job_tier and isinstance(tier_overrides, dict) and job_tier in tier_overrides:
        tier_cfg = tier_overrides[job_tier]
        if isinstance(tier_cfg, dict):
            if "max_job_tokens" in tier_cfg:
                max_tokens = int(tier_cfg["max_job_tokens"])
            if "max_job_cost_usd" in tier_cfg:
                max_cost = float(tier_cfg["max_job_cost_usd"])
            if "zero_file_token_threshold" in tier_cfg:
                zero_file_threshold = int(tier_cfg["zero_file_token_threshold"])

    return max_tokens, max_cost, zero_file_threshold
```

to:

```python
def _resolve_circuit_breaker_limits(
    job: dict,
    config: Optional[dict] = None,
) -> Tuple[int, float, int, int]:
    """Resolve max_tokens, max_cost, zero_file_threshold, and max_log_size_bytes
    from config and tier overrides."""
    cb_config = {}
    if config and isinstance(config, dict):
        cb_config = config.get("circuit_breaker", {})
        if not isinstance(cb_config, dict):
            cb_config = {}

    max_tokens = int(cb_config.get("max_job_tokens", DEFAULT_MAX_JOB_TOKENS))
    max_cost = float(cb_config.get("max_job_cost_usd", DEFAULT_MAX_JOB_COST_USD))
    zero_file_threshold = int(
        cb_config.get("zero_file_token_threshold", DEFAULT_ZERO_FILE_TOKEN_THRESHOLD)
    )
    max_log_size_bytes = int(
        cb_config.get("max_log_size_bytes", DEFAULT_MAX_LOG_SIZE_BYTES)
    )

    tier_overrides = cb_config.get("tier_overrides", DEFAULT_TIER_OVERRIDES)
    job_tier = str(job.get("model_tier") or job.get("tier") or "").strip().lower()

    if job_tier and isinstance(tier_overrides, dict) and job_tier in tier_overrides:
        tier_cfg = tier_overrides[job_tier]
        if isinstance(tier_cfg, dict):
            if "max_job_tokens" in tier_cfg:
                max_tokens = int(tier_cfg["max_job_tokens"])
            if "max_job_cost_usd" in tier_cfg:
                max_cost = float(tier_cfg["max_job_cost_usd"])
            if "zero_file_token_threshold" in tier_cfg:
                zero_file_threshold = int(tier_cfg["zero_file_token_threshold"])
            if "max_log_size_bytes" in tier_cfg:
                max_log_size_bytes = int(tier_cfg["max_log_size_bytes"])

    return max_tokens, max_cost, zero_file_threshold, max_log_size_bytes
```

- [ ] **Step 4: Update the call site to unpack 4 values**

In `synlynk/circuit_breaker.py`, change line 179 from:

```python
    max_tokens, max_cost, zero_file_threshold = _resolve_circuit_breaker_limits(job, config)
```

to:

```python
    max_tokens, max_cost, zero_file_threshold, max_log_size_bytes = _resolve_circuit_breaker_limits(job, config)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_circuit_breaker.py::test_circuit_breaker_resolves_log_size_tier_override -v`
Expected: PASS

- [ ] **Step 6: Run the full existing circuit breaker suite to check for regressions from the signature change**

Run: `pytest tests/test_circuit_breaker.py -v`
Expected: All tests PASS (the 6 pre-existing tests only call `evaluate_job_circuit_breaker`, not `_resolve_circuit_breaker_limits` directly, so they are unaffected by the signature change — but verify anyway since this is a shared internal function).

- [ ] **Step 7: Commit**

```bash
git add synlynk/circuit_breaker.py tests/test_circuit_breaker.py
git commit -m "feat: resolve max_log_size_bytes in circuit breaker limits (gh:#1937)"
```

---

## Task 2: Add the log-size runaway trigger branch

**Files:**
- Modify: `synlynk/circuit_breaker.py:181-191` (trigger-check block)
- Test: `tests/test_circuit_breaker.py`

- [ ] **Step 1: Write the failing test — log-size runaway trips independent of token extraction**

Add to `tests/test_circuit_breaker.py`:

```python
def test_log_size_runaway_trips_with_zero_extracted_tokens(tmp_path, monkeypatch):
    """Simulates gh:#1937: a long open Codex turn with no turn.completed line
    yet, so extract_tokens() returns 0/0, but the transcript itself has grown
    past the log-size ceiling from repeated tool-loop round trips."""
    log_file = tmp_path / "runaway_no_usage.log"
    # Plain-text padding with no turn.completed JSON line anywhere - simulates
    # the mid-turn blind spot where extract_tokens() can't attribute any usage.
    log_file.write_text("tool call output\n" * 2_000_000)
    assert log_file.stat().st_size >= 10 * 1024 * 1024

    killed_pids = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed_pids.append((pid, sig)))

    job = {
        "id": "job-log-size-runaway",
        "agent": "codex",
        "pid": 99001,
        "log_file": str(log_file),
        "status": "running",
    }
    config = {
        "circuit_breaker": {
            "max_job_tokens": 5_000_000,
            "max_job_cost_usd": 15.00,
            "zero_file_token_threshold": 500_000,
            "max_log_size_bytes": 10 * 1024 * 1024,
        }
    }

    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(tmp_path / "sentinel.md"),
        skip_identity_check_for_test=True,
    )

    assert res.tripped is True
    assert res.process_killed is True
    assert job["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED
    assert "log size runaway" in res.reason.lower()
    assert "extracted tokens" in res.reason.lower()
    assert len(killed_pids) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_circuit_breaker.py::test_log_size_runaway_trips_with_zero_extracted_tokens -v`
Expected: FAIL — `res.tripped` is `False` (no trigger fires: the plain-text log has no `turn.completed` line, `total_tokens` stays `0`, and `0 >= zero_file_threshold` is also false, so `reason` stays `None`).

- [ ] **Step 3: Add the log-size check as a new `elif` branch**

In `synlynk/circuit_breaker.py`, change the trigger-check block (lines 181-191) from:

```python
    # 5. Check triggers
    reason = None
    if cost_usd >= max_cost:
        reason = f"Cost limit breached: ${cost_usd:.2f} >= ${max_cost:.2f}"
    elif total_tokens >= max_tokens:
        reason = f"Token limit breached: {total_tokens:,} >= {max_tokens:,} tokens"
    elif total_tokens >= zero_file_threshold:
        files_touched_list = _worktree_files_touched(worktree_path) if worktree_path else []
        files_touched = len(files_touched_list)
        if files_touched == 0:
            reason = f"Zero-file runaway: {total_tokens:,} tokens with 0 files touched (limit: {zero_file_threshold:,})"
```

to:

```python
    # 5. Check triggers
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
        files_touched_list = _worktree_files_touched(worktree_path) if worktree_path else []
        files_touched = len(files_touched_list)
        if files_touched == 0:
            reason = f"Zero-file runaway: {total_tokens:,} tokens with 0 files touched (limit: {zero_file_threshold:,})"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_circuit_breaker.py::test_log_size_runaway_trips_with_zero_extracted_tokens -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/circuit_breaker.py tests/test_circuit_breaker.py
git commit -m "feat: trip circuit breaker on log-size runaway as vendor-agnostic safety net (gh:#1937)"
```

---

## Task 3: Test — log-size check does not fire below threshold

**Files:**
- Test: `tests/test_circuit_breaker.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_circuit_breaker.py`:

```python
def test_log_size_below_threshold_does_not_trip(tmp_path, monkeypatch):
    log_file = tmp_path / "small_log.log"
    log_file.write_text("tool call output\n" * 100)
    assert log_file.stat().st_size < 10 * 1024 * 1024

    monkeypatch.setattr(os, "kill", lambda pid, sig: None)

    job = {
        "id": "job-small-log",
        "agent": "codex",
        "pid": 99002,
        "log_file": str(log_file),
        "worktree_path": str(tmp_path),
        "status": "running",
    }
    config = {
        "circuit_breaker": {
            "max_job_tokens": 5_000_000,
            "max_job_cost_usd": 15.00,
            "zero_file_token_threshold": 500_000,
            "max_log_size_bytes": 10 * 1024 * 1024,
        }
    }

    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(tmp_path / "sentinel.md"),
        skip_identity_check_for_test=True,
    )

    assert res.tripped is False
    assert job["status"] == "running"
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `pytest tests/test_circuit_breaker.py::test_log_size_below_threshold_does_not_trip -v`
Expected: PASS (this is a regression guard against the Task 2 implementation, not a new TDD red/green cycle — the implementation already exists; this step confirms no off-by-one or threshold-direction bug). If it FAILS, re-check the `elif log_size_bytes >= max_log_size_bytes` comparison direction in Task 2 Step 3 before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_circuit_breaker.py
git commit -m "test: log-size check stays quiet below threshold (gh:#1937)"
```

---

## Task 4: Test — cost/token checks win over log-size when both would trigger

**Files:**
- Test: `tests/test_circuit_breaker.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_circuit_breaker.py`:

```python
def test_cost_check_wins_over_log_size_when_both_trigger(tmp_path, monkeypatch):
    """Order-of-checks regression guard: a log large enough to cross
    max_log_size_bytes AND containing a turn.completed whose usage crosses
    max_job_cost_usd must report the cost reason, not the log-size reason."""
    log_file = tmp_path / "big_and_expensive.log"
    # Pad past the 10MB log-size ceiling, then append a turn.completed whose
    # cost crosses the $1.50 ceiling (400k in + 100k out, same shape as the
    # existing test_circuit_breaker_trips_on_cost_limit_breach fixture).
    padding = "tool call output\n" * 700_000
    log_file.write_text(padding + "Input tokens: 400000\nOutput tokens: 100000\n")
    assert log_file.stat().st_size >= 10 * 1024 * 1024

    killed_pids = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed_pids.append((pid, sig)))

    job = {
        "id": "job-cost-and-log-size",
        "agent": "claude",
        "pid": 99003,
        "log_file": str(log_file),
        "status": "running",
    }
    config = {
        "circuit_breaker": {
            "max_job_tokens": 1_000_000,
            "max_job_cost_usd": 1.50,
            "max_log_size_bytes": 10 * 1024 * 1024,
        }
    }

    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(tmp_path / "sentinel.md"),
        skip_identity_check_for_test=True,
    )

    assert res.tripped is True
    assert "cost" in res.reason.lower()
    assert "log size" not in res.reason.lower()
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `pytest tests/test_circuit_breaker.py::test_cost_check_wins_over_log_size_when_both_trigger -v`
Expected: PASS (confirms the `elif` ordering from Task 2 Step 3 keeps cost/token checks ahead of the log-size branch). If it FAILS, the log-size `elif` was placed before the cost/token checks instead of after — fix the ordering in `synlynk/circuit_breaker.py` to match Task 2 Step 3 exactly.

- [ ] **Step 3: Commit**

```bash
git add tests/test_circuit_breaker.py
git commit -m "test: cost/token checks preempt log-size branch (gh:#1937)"
```

---

## Task 5: Test — zero-file check still fires when log-size is below threshold

**Files:**
- Test: `tests/test_circuit_breaker.py`

- [ ] **Step 1: Write the test**

Add to `tests/test_circuit_breaker.py`:

```python
def test_zero_file_check_still_fires_below_log_size_threshold(tmp_path, monkeypatch):
    """Regression guard: inserting the log-size elif between the token check
    and the zero-file check must not break the existing zero-file path when
    the log itself is small but token count crosses zero_file_threshold."""
    log_file = tmp_path / "zero_file_small_log.log"
    log_file.write_text("Input tokens: 600000\nOutput tokens: 100\n")
    assert log_file.stat().st_size < 10 * 1024 * 1024

    monkeypatch.setattr(os, "kill", lambda pid, sig: None)

    job = {
        "id": "job-zero-file-small-log",
        "agent": "codex",
        "pid": 99004,
        "log_file": str(log_file),
        "worktree_path": str(tmp_path),
        "status": "running",
    }
    config = {
        "circuit_breaker": {
            "max_job_tokens": 5_000_000,
            "max_job_cost_usd": 100.0,
            "zero_file_token_threshold": 500_000,
            "max_log_size_bytes": 10 * 1024 * 1024,
        }
    }

    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(tmp_path / "sentinel.md"),
        skip_identity_check_for_test=True,
    )

    assert res.tripped is True
    assert job["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED
    assert "zero-file" in res.reason.lower()
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `pytest tests/test_circuit_breaker.py::test_zero_file_check_still_fires_below_log_size_threshold -v`
Expected: PASS. (`worktree_path` points at `tmp_path` with no files created in it, so `_worktree_files_touched` returns an empty list — same pattern as the pre-existing `test_codex_uncached_cumulative_input_still_trips_zero_file` test.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_circuit_breaker.py
git commit -m "test: zero-file check unaffected by log-size branch insertion (gh:#1937)"
```

---

## Task 6: Full suite verification and self-review

- [ ] **Step 1: Run the complete circuit breaker test file**

Run: `pytest tests/test_circuit_breaker.py -v`
Expected: 12 tests PASS (6 pre-existing + 6 new: tier-resolution, log-size-trips, log-size-below-threshold, cost-wins, zero-file-still-fires — wait, count check: Task 1 adds 1 test, Task 2 adds 1 test, Task 3 adds 1 test, Task 4 adds 1 test, Task 5 adds 1 test = 5 new tests + 6 pre-existing = 11 total). Expected: `11 passed`.

- [ ] **Step 2: Run the broader test suite to check for unrelated regressions**

Run: `pytest tests/ -k "circuit_breaker" -v`
Expected: all circuit-breaker-related tests across the repo (including `tests/test_reconcile_circuit_breaker.py`, `tests/test_viz_circuit_breaker.py`, `tests/test_milestone_circuit_breaker_failover.py`, `tests/test_circuit_breaker_live19.py` if any of them call `_resolve_circuit_breaker_limits` or `evaluate_job_circuit_breaker` directly) still pass. If any fail due to the 3-tuple→4-tuple signature change, update their call sites to unpack 4 values, following the same pattern as Task 1 Step 4.

- [ ] **Step 3: Self-review against the spec**

Check off each spec requirement against what was implemented:
- [x] Config: `DEFAULT_MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024` added, resolved via `_resolve_circuit_breaker_limits`, tier-overridable (Task 1).
- [x] Trigger logic: new `elif` branch placed after cost/token checks, before zero-file check, exact reason-string format from spec (Task 2).
- [x] Telemetry: no changes made — existing `reason` field flows through unchanged (confirmed: `log_telemetry_event` call at line ~249 already logs `reason` generically, no spec-required change here).
- [x] Testing: all 5 spec-enumerated test cases implemented (Tasks 1-5, mapped 1:1 to spec's Testing section items 1-5).
- [x] Non-goals respected: no changes to `synlynk/costs.py`, no dispatch task-framing changes, no `parse_dispatch_turns` rework.

- [ ] **Step 4: Note the open question for the PR description**

The spec's "Open question for implementing engineer" asks to confirm against telemetry whether any legitimate job type produces near-50MB logs before completing successfully. If `synlynk status`/`telemetry.json` is accessible and cheap to check during implementation, note the finding in the PR description. If checking requires a long detour, state in the PR description that this was carried forward unverified and the 50MB default was kept as-is per the spec's "start generously" guidance — do not block the PR on this.

---

## Execution Handoff

Per this project's Default Agent Role policy (CLAUDE.md), Claude's role is PM/review/deploy/brainstorm — implementation of this fix routes to **`synlynk dispatch`**, targeting **Codex** as the primary harness (fallback: Grok), since this is an infra fix touching synlynk's own dispatch-safety internals (`synlynk/circuit_breaker.py`), not a task Claude implements directly.

**GOVERNS linkage:** `story-84912225` ("fix: dispatch cost inflation #1937 — fresh investigation, prior mitigations closed") already exists in `project-docs/todo.md:1965` and is still open/unassigned — link this dispatch to that story rather than creating a duplicate. Confirm its current status immediately before dispatch (e.g. `synlynk story list` or equivalent) in case it was updated since this plan was written.

**Suggested dispatch invocation shape** (adjust flags to current CLI surface at dispatch time):

```bash
synlynk dispatch --as-agent dev --story story-84912225 \
  --task "Implement docs/superpowers/plans/2026-10-11-cost-inflation-circuit-breaker-visibility.md task-by-task (circuit breaker log-size runaway net, gh:#1937)" \
  --force-harness codex
```

After the implementing job completes: route review through a harness+model different from the implementer (per the Hardened PR Review Policy's `cross_harness_review_required`), run `synlynk pr check` from within the reviewer's own dispatch, and merge per the reviewer's own dispatched job (not this interactive session) per the PR Review Discipline section of CLAUDE.md.
