# Doctor Check: Elevated PR Review Cycles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `synlynk doctor` health check that surfaces agents/roles with an elevated average `pr_review_cycles` over a recent window as a `warn`-level result, closing gh#1200.

**Architecture:** `capability_ratings.pr_review_cycles` is already populated per-rating by `synlynk/jobs.py` (see `synlynk/jobs.py:1042-1050`). Add one new pure function `_hc_pr_review_cycles()` to `synlynk/doctor.py`, following the exact existing pattern of `_hc_model_rates()`/`_hc_agent_profiles()` (a zero-arg function returning a `HealthCheck`, registered in the `HEALTH_CHECKS` list). The averaging/windowing query mirrors the existing `_collect_capability_drop()` pattern in `synlynk/support_engineer.py:277` (per-agent `AVG(...)` over a recent `ts` window via SQLite's `datetime('now', '-N days')`), but reads `pr_review_cycles` instead of `quality` and has no "prior window" comparison — this is an absolute-threshold check, not a drop-detection check.

**Tech Stack:** Python 3 stdlib, sqlite3 (via `synlynk._get_db()`), pytest.

**Decisions locked for this plan** (per issue #1200's own suggestion, made concrete here since they were the only open parameters):
- **Window:** last 30 days (`ts > datetime('now', '-30 days')`).
- **Minimum sample size:** an agent needs at least 3 ratings with a non-null `pr_review_cycles` in the window to be evaluated — matches the anti-noise intent of the existing capability-drop check's `< 2` skip, bumped to 3 because `pr_review_cycles` swings harder on tiny samples than `quality` does.
- **Warn threshold:** average `pr_review_cycles` > `1.5` — 0 means merged first try, 1 means one round of changes-requested; averaging above 1.5 means most PRs from that agent need 2+ rounds, which is the "elevated" signal the issue asks for.
- **Status:** `ok` when no agent breaches the threshold (including the "no data at all yet" case — a fresh/unadopted project must not warn); `warn` when one or more agents breach it, naming them and their averages in the message. No `fail` case — this is advisory, matching every other doctor check's severity model except `python_version`/`project_init`.

---

### Task 1: Add `_hc_pr_review_cycles()` health check

**Files:**
- Modify: `synlynk/doctor.py`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_synlynk.py`, placed immediately after `test_hc_model_rates_invalid_date` (around line 7454, right before `test_sentinel_model_rates_no_file`):

```python
def _insert_capability_rating(conn, story_id, agent, pr_review_cycles, days_ago=0):
    conn.execute(
        "INSERT INTO stories (story_id) VALUES (?)",
        (story_id,),
    )
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, "
        "signal_source, quality, pr_review_cycles, ts) VALUES "
        "(?, ?, 'test-model', 'auto', 5.0, ?, datetime('now', ?))",
        (story_id, agent, pr_review_cycles, f'-{days_ago} days'),
    )
    conn.commit()


def test_hc_pr_review_cycles_no_data(isolated_db):
    import synlynk
    result = synlynk._hc_pr_review_cycles()
    assert result.status == "ok"
    assert "no data" in result.message.lower()


def test_hc_pr_review_cycles_below_threshold(isolated_db):
    import synlynk
    conn = synlynk._get_db()
    for i in range(4):
        _insert_capability_rating(conn, f"story-below-{i}", "codex", pr_review_cycles=1)
    conn.close()
    result = synlynk._hc_pr_review_cycles()
    assert result.status == "ok"


def test_hc_pr_review_cycles_elevated(isolated_db):
    import synlynk
    conn = synlynk._get_db()
    for i in range(4):
        _insert_capability_rating(conn, f"story-hi-{i}", "agy", pr_review_cycles=3)
    conn.close()
    result = synlynk._hc_pr_review_cycles()
    assert result.status == "warn"
    assert "agy" in result.message
    assert "3.0" in result.message or "3" in result.message


def test_hc_pr_review_cycles_below_min_sample_size(isolated_db):
    import synlynk
    conn = synlynk._get_db()
    # Only 2 ratings — below the minimum-sample-size floor of 3, must not warn
    # even though the average (3.0) is above the threshold.
    for i in range(2):
        _insert_capability_rating(conn, f"story-small-{i}", "grok", pr_review_cycles=3)
    conn.close()
    result = synlynk._hc_pr_review_cycles()
    assert result.status == "ok"


def test_hc_pr_review_cycles_ignores_stale_ratings(isolated_db):
    import synlynk
    conn = synlynk._get_db()
    # 4 elevated ratings, but all outside the 30-day window — must not warn.
    for i in range(4):
        _insert_capability_rating(conn, f"story-stale-{i}", "codex", pr_review_cycles=3, days_ago=45)
    conn.close()
    result = synlynk._hc_pr_review_cycles()
    assert result.status == "ok"


def test_hc_pr_review_cycles_ignores_null_cycles(isolated_db):
    import synlynk
    conn = synlynk._get_db()
    for i in range(4):
        story_id = f"story-null-{i}"
        conn.execute("INSERT INTO stories (story_id) VALUES (?)", (story_id,))
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, model_version, "
            "signal_source, quality) VALUES (?, 'codex', 'test-model', 'auto', 5.0)",
            (story_id,),
        )
    conn.commit()
    conn.close()
    result = synlynk._hc_pr_review_cycles()
    assert result.status == "ok"
    assert "no data" in result.message.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_synlynk.py -k hc_pr_review_cycles -v`
Expected: FAIL with `AttributeError: module 'synlynk' has no attribute '_hc_pr_review_cycles'` for every new test.

- [ ] **Step 3: Implement the health check**

In `synlynk/doctor.py`, add this function immediately after `_hc_model_rates()` (after line 453, before `def cleanup_selftest_workspaces`):

```python
_PR_REVIEW_CYCLES_WINDOW_DAYS = 30
_PR_REVIEW_CYCLES_MIN_SAMPLES = 3
_PR_REVIEW_CYCLES_WARN_THRESHOLD = 1.5


def _hc_pr_review_cycles() -> HealthCheck:
    """Flags agents/roles with an elevated average pr_review_cycles over a recent window."""
    try:
        conn = _pkg("_get_db")()
        rows = conn.execute(
            "SELECT agent, AVG(pr_review_cycles), COUNT(*) FROM capability_ratings "
            "WHERE pr_review_cycles IS NOT NULL "
            f"AND ts > datetime('now', '-{_PR_REVIEW_CYCLES_WINDOW_DAYS} days') "
            "GROUP BY agent"
        ).fetchall()
    except Exception:
        return HealthCheck(
            "pr_review_cycles",
            "warn",
            "Could not read capability_ratings — skipping pr_review_cycles check",
        )

    elevated = [
        (agent, avg_cycles, count)
        for agent, avg_cycles, count in rows
        if count >= _PR_REVIEW_CYCLES_MIN_SAMPLES and avg_cycles is not None
        and avg_cycles > _PR_REVIEW_CYCLES_WARN_THRESHOLD
    ]

    if not elevated:
        return HealthCheck(
            "pr_review_cycles",
            "ok",
            f"No agent has elevated PR review cycles (no data, or all below "
            f"{_PR_REVIEW_CYCLES_WARN_THRESHOLD} avg over last {_PR_REVIEW_CYCLES_WINDOW_DAYS}d)",
        )

    elevated.sort(key=lambda t: t[1], reverse=True)
    summary = ", ".join(f"{agent} ({avg_cycles:.1f} avg, n={count})" for agent, avg_cycles, count in elevated)
    return HealthCheck(
        "pr_review_cycles",
        "warn",
        f"Elevated PR review cycles over last {_PR_REVIEW_CYCLES_WINDOW_DAYS}d: {summary}",
        fix="Review recent PRs from the flagged agent(s) for recurring rework patterns; "
            "consider adjusting task_allocation routing in .synlynk/policy.json if the pattern holds",
    )
```

- [ ] **Step 4: Register in `HEALTH_CHECKS`**

In `synlynk/doctor.py`, modify the `HEALTH_CHECKS` list (currently at line 478):

```python
HEALTH_CHECKS = [
    _hc_python_version,
    _hc_project_init,
    _hc_docs_dir,
    _hc_identity_key,
    _hc_identity_roles,
    _hc_identity_file_perms,
    _hc_agent_profiles,
    _hc_instruction_files,
    _hc_model_rates,
    _hc_pr_review_cycles,
    _hc_version_current,
]
```

(Inserted before `_hc_version_current` since that one makes a network call and other checks conventionally run before it.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_synlynk.py -k hc_pr_review_cycles -v`
Expected: PASS (7 tests: no_data, below_threshold, elevated, below_min_sample_size, ignores_stale_ratings, ignores_null_cycles).

- [ ] **Step 6: Run the full existing doctor test suite to confirm no regression**

Run: `python3 -m pytest tests/test_synlynk.py -k "doctor or hc_" -v`
Expected: all PASS, same count as baseline plus the 7 new tests.

- [ ] **Step 7: Commit**

```bash
git add synlynk/doctor.py tests/test_synlynk.py
git commit -m "feat: add doctor check for elevated PR review cycles (#1200)"
```

---

### Task 2: Full regression run

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest -q`
Expected: same pass/fail/skip counts as the pre-existing baseline (2 failed — `test_agent_quota_tracking.py::test_cmd_probewrite_fencetrue_clobbers_sop_harness` and `test_roles.py::test_cmd_agent_add_onboards_agent`, both pre-existing sqlite-locking issues unrelated to this change — plus the 7 new tests passing, 2 skipped as before).

- [ ] **Step 2: Manual smoke test**

Run: `python3 -m synlynk doctor` (or `python3 bin/synlynk.py doctor` if not installed) in this worktree.
Expected: output includes a `pr_review_cycles` line with `ok` status (this repo's own dev DB won't have seeded capability_ratings data unless prior dispatch jobs ran locally against it — either `ok`/no-data or `ok`/below-threshold is an acceptable smoke-test result; a `warn` here is also fine and not a bug, it would reflect this repo's own real telemetry).

No commit for this task — verification only.

---

## Self-Review Notes

- **Spec coverage:** Issue #1200's ask is "Add a new health check to `HEALTH_CHECKS` that flags agents/roles with an elevated average `pr_review_cycles` over a recent window ... as a `warn`-level result" — Task 1 does exactly this, with the window/threshold/min-sample parameters made explicit and testable rather than left as placeholders.
- **No placeholders:** every step has literal code, no "add appropriate X" language.
- **Type/signature consistency:** `_hc_pr_review_cycles() -> HealthCheck` matches the exact signature and dataclass (`HealthCheck(name, status, message, fix="")`) already used by every other check in this file — no new types introduced.
- **Scope discipline:** this plan does not touch `sentinel.py`, `pr_multiplier.py`, or `jobs.py` — those already compute and persist `pr_review_cycles` correctly per the issue's own text ("Data plumbing already exists — this is a scoped addition, not new instrumentation"). Only `doctor.py` and its test file are touched.
