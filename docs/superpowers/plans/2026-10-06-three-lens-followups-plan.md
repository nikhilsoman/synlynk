# Three-Lens Review Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship four independent fixes from `docs/superpowers/specs/2026-10-06-three-lens-followups-design.md`: un-suspend empirical dispatch routing with real sample-size-gated fallback (#2063), durably log dispatch routing-fallback decisions (#2064), add stdlib-only JSON Schema validation for `config.json`/`policy.json` via `synlynk doctor` (#2065), and add a cross-adapter conformance test suite (#2062, narrowed scope).

**Architecture:** Each of the four sections below (A-D) is a self-contained unit: its own files, its own tests, its own commit(s), dispatchable to a different harness/role in parallel. None of the four touches code the others touch. Section A is the only one that changes live dispatch-routing behavior; B, C, D are additive (logging, validation, tests) with no behavior change to existing code paths.

**Tech Stack:** Python 3.9+ stdlib only (`pyproject.toml: dependencies=[]` — no `jsonschema` or other third-party packages). SQLite via `sqlite3`. `pytest` for tests (existing suite, `tests/` flat layout).

---

## 0. Shared context every task needs

- Work from this worktree: `.worktrees/docs+three-lens-followups-design`, branch `docs/claude/three-lens-followups-design`. **Each section (A-D) should be dispatched to its own fresh worktree/branch** per the project's worktree-per-feature convention — this plan documents the work, it does not mean all four land on this docs branch. Suggested branch names: `fix/claude/2063-empirical-routing-fallback`, `fix/claude/2064-dispatch-fallback-logging`, `feat/claude/2065-config-schema-validation`, `test/claude/2062-adapter-conformance-suite`.
- Run tests with `pytest tests/<file>.py -v` from the repo root (not this docs worktree once each section gets its own worktree).
- Every commit needs the `Co-Authored-By` trailer for whichever harness executes it, per CLAUDE.md's Repo Hygiene section.
- Cross-harness review is required before merge (CLAUDE.md Hardened PR Review Policy) — the implementer and reviewer must differ in harness **and** model.

---

## Work breakdown

### Task A — #2063: Un-suspend empirical routing with sample-size fallback

**Files:**
- Modify: `synlynk/capability.py` (add `ranked_harness_for_task()`)
- Modify: `synlynk/dispatch.py:636` area, inside `compose_dispatch_preview()`
- Modify: `.synlynk/policy.json` (`capability_policy` block)
- Modify: `README.md:15`
- Test: `tests/test_capability.py` (extend — existing file, see pattern below)
- Test: `tests/test_dispatch_preview.py` (create if no existing preview test file; check first with `ls tests/ | grep -i preview`)

#### Step 1: Write the failing test for `ranked_harness_for_task()`

Add to `tests/test_capability.py` (it already imports `sqlite3`, `pytest`, and functions from `synlynk.capability`):

```python
def test_ranked_harness_for_task_promotes_candidate_with_better_metrics():
    from synlynk.db_schema import _DB_SCHEMA, _DB_SCORES_VIEW
    from synlynk.capability import ranked_harness_for_task

    conn = sqlite3.connect(":memory:")
    conn.executescript(_DB_SCHEMA)
    conn.executescript(_DB_SCORES_VIEW)

    # Incumbent "codex": 5 samples, pr_review_cycles=3 each, cost=$10 each.
    for i in range(5):
        story_id = f"story-codex-{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 3)",
            (story_id,),
        )
        conn.execute(
            "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd) "
            "VALUES ('2026-10-01', 'codex', ?, 'test', 10.0)",
            (story_id,),
        )
    # Challenger "grok": 5 samples, pr_review_cycles=1 each (better), cost=$4 each (better).
    for i in range(5):
        story_id = f"story-grok-{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1)",
            (story_id,),
        )
        conn.execute(
            "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd) "
            "VALUES ('2026-10-01', 'grok', ?, 'test', 4.0)",
            (story_id,),
        )
    conn.commit()

    result = ranked_harness_for_task("implement", ["codex", "grok"], conn=conn)
    assert result == "grok"


def test_ranked_harness_for_task_falls_back_below_sample_size():
    from synlynk.db_schema import _DB_SCHEMA, _DB_SCORES_VIEW
    from synlynk.capability import ranked_harness_for_task

    conn = sqlite3.connect(":memory:")
    conn.executescript(_DB_SCHEMA)
    conn.executescript(_DB_SCORES_VIEW)

    # Challenger "grok" only has 2 samples (below min_sample_size=5), even
    # though its metrics would otherwise win.
    for i in range(2):
        story_id = f"story-grok-{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1)",
            (story_id,),
        )
        conn.execute(
            "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd) "
            "VALUES ('2026-10-01', 'grok', ?, 'test', 4.0)",
            (story_id,),
        )
    conn.commit()

    result = ranked_harness_for_task("implement", ["codex", "grok"], conn=conn)
    assert result is None
```

#### Step 2: Run tests to verify they fail

Run: `pytest tests/test_capability.py -v -k ranked_harness`
Expected: FAIL with `ImportError: cannot import name 'ranked_harness_for_task'`

#### Step 3: Implement `ranked_harness_for_task()`

Add to `synlynk/capability.py` (after `route_expected_value()`, same file — it already has `_connection()` for the owned/borrowed-conn pattern used by every other function here):

```python
def ranked_harness_for_task(
    task_type: str,
    candidates: list,
    *,
    min_sample_size: int = 5,
    conn=None,
) -> str | None:
    """Return a candidate that beats the incumbent on measured outcomes.

    ``candidates[0]`` is the incumbent (the current ``task_allocation``
    default). A later candidate is only preferred when it has at least
    ``min_sample_size`` capability_ratings rows for this ``task_type`` (the
    closest existing dimension is ``discipline`` — capability_ratings has
    no task_type column) and beats the incumbent on both median
    pr_review_cycles and average total_cost_usd. Returns ``None`` when no
    candidate qualifies, so callers fall back to the incumbent unchanged.
    """
    if not candidates:
        return None
    db, owned = _connection(conn)
    try:
        incumbent = candidates[0]
        stats = {}
        for harness in candidates:
            rows = db.execute(
                """SELECT cr.pr_review_cycles, ce.total_cost_usd
                     FROM capability_ratings cr
                     JOIN cost_entries ce ON ce.story_id = cr.story_id
                    WHERE cr.agent = ? AND lower(cr.discipline) = lower(?)
                      AND ce.harness = cr.agent""",
                (harness, task_type),
            ).fetchall()
            if not rows:
                stats[harness] = None
                continue
            cycles = sorted(r[0] for r in rows if r[0] is not None)
            costs = [r[1] for r in rows if r[1] is not None]
            if not cycles or not costs:
                stats[harness] = None
                continue
            mid = len(cycles) // 2
            median_cycles = (
                cycles[mid] if len(cycles) % 2 else (cycles[mid - 1] + cycles[mid]) / 2
            )
            stats[harness] = {
                "sample_count": len(rows),
                "median_cycles": median_cycles,
                "avg_cost": sum(costs) / len(costs),
            }

        incumbent_stats = stats.get(incumbent)
        best = None
        for harness in candidates[1:]:
            candidate_stats = stats.get(harness)
            if not candidate_stats or candidate_stats["sample_count"] < min_sample_size:
                continue
            if incumbent_stats:
                if not (
                    candidate_stats["median_cycles"] < incumbent_stats["median_cycles"]
                    and candidate_stats["avg_cost"] < incumbent_stats["avg_cost"]
                ):
                    continue
            if best is None or (
                candidate_stats["median_cycles"] < stats[best]["median_cycles"]
            ):
                best = harness
        return best
    finally:
        if owned:
            db.close()
```

#### Step 4: Run tests to verify they pass

Run: `pytest tests/test_capability.py -v -k ranked_harness`
Expected: PASS (2 tests)

#### Step 5: Commit

```bash
git add synlynk/capability.py tests/test_capability.py
git commit -m "feat(capability): add sample-size-gated ranked_harness_for_task()

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

#### Step 6: Write the failing test for `compose_dispatch_preview()` consulting the ranking

First check what test file already covers `compose_dispatch_preview`:

Run: `grep -rln "compose_dispatch_preview" tests/`

Add a test to whichever file that returns (likely `tests/test_dispatch_preview.py` or similar — if none exists, create `tests/test_dispatch_preview.py`):

```python
import sqlite3
from unittest.mock import patch

from synlynk.dispatch import compose_dispatch_preview


def test_preview_promotes_empirically_better_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    policy_path = tmp_path / ".synlynk" / "policy.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        '{"schema_version": 1, "repo_id": "test", "capability_policy": {},'
        ' "overrides": {"dev_authority": {"task_allocation": '
        '{"implement": {"harness": "codex", "fallback": ["grok"]}}}}}'
    )
    with patch("synlynk.capability.ranked_harness_for_task", return_value="grok"):
        preview = compose_dispatch_preview("implement a new login form", task_type="implement")
    assert preview["agent"] == "grok"
```

Adjust the assertion key (`preview["agent"]`) and the exact call signature once you've read `compose_dispatch_preview()`'s full body past line 654 (the earlier read in this session was truncated there) — confirm the return dict's key name for the resolved harness before finalizing this test. Also confirm how `load_policy()` resolves `workspace_name` under a `tmp_path` fixture (it calls `identity_slug_from_config(repo_path)` when `workspace_name` is `None` — check whether this needs a `.synlynk/config.json` in `tmp_path` too, or mock `load_policy` directly instead of writing a real policy.json, whichever is less brittle).

#### Step 7: Run test to verify it fails

Run: `pytest tests/test_dispatch_preview.py -v -k promotes_empirically`
Expected: FAIL (either ImportError on the mock target, or the assertion — `preview["agent"] == "codex"` unchanged) since the ranking call isn't wired in yet.

#### Step 8: Wire the ranking into `compose_dispatch_preview()`

Read `synlynk/dispatch.py` from line 636 to the end of `compose_dispatch_preview()` (past where the prior read was truncated at line 654) before editing — the exact variable name holding `allocation[task_type]` and the final return statement must be known precisely; do not guess. Once read, locate the line that resolves the default harness from `allocation` (something like `default_harness = allocation.get(inferred_task_type, {}).get("harness")`) and the line(s) that build the fallback list, then insert:

```python
    from synlynk.capability import ranked_harness_for_task

    entry = allocation.get(inferred_task_type, {}) if inferred_task_type else {}
    default_harness = entry.get("harness")
    fallback_list = entry.get("fallback") or []
    if default_harness:
        promoted = ranked_harness_for_task(
            inferred_task_type, [default_harness] + list(fallback_list)
        )
        if promoted:
            default_harness = promoted
```

Then use `default_harness` wherever the function previously used `allocation[...]["harness"]` directly for the resolved agent, before the existing story/explicit-override precedence logic (story metadata and explicit CLI values still win over both the table default and the promoted harness, per the function's own docstring — do not change that precedence order).

#### Step 9: Run test to verify it passes

Run: `pytest tests/test_dispatch_preview.py -v -k promotes_empirically`
Expected: PASS

#### Step 10: Regression test — local-threshold path unchanged

Run: `pytest tests/ -v -k "local_capability or resolve_dispatch_agent or preflight_local"`
Expected: PASS, no change (confirms `_resolve_dispatch_agent()`'s separate local-vs-fallback logic, which this task does not touch, still behaves as before).

#### Step 11: Commit

```bash
git add synlynk/dispatch.py tests/test_dispatch_preview.py
git commit -m "feat(dispatch): consult empirical capability ranking in dispatch preview

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

#### Step 12: Update `.synlynk/policy.json`'s `capability_policy` block

Read the current block first (`python3 -c "import json; print(json.dumps(json.load(open('.synlynk/policy.json'))['capability_policy'], indent=2))"`) to confirm it still matches what this plan assumed, then edit by hand (small JSON file, no script needed) to:
- Remove the `suspended_since` and `suspended_rationale` keys.
- Rewrite `blocking_dependency` to: `"Single-workspace routing (this repo's own task_allocation) queries only this workspace's canonical state.db and does not require #1926. Fleet-wide synlynk capability report aggregation (#1993) across workspaces remains blocked on #1926/#1831's shard consolidation."`
- Append to the existing `note` field's sentence a clause naming `README.md:15` alongside `task_allocation` and `docs/harness-capability-baseline.md` as files to update together on a future suspension.
- Leave `mode`, `min_sample_size`, `metrics`, `metric_source`, `not_yet_calibrated`, `generator_status` unchanged.

#### Step 13: Update `README.md:15`

Replace the sentence containing "routes tasks to the best available harness using a live capability ledger" with: "routes tasks to the best-measured harness once it clears a minimum sample size on that task type, falling back to a documented default allocation otherwise". Leave line 5's banner text untouched (it doesn't make the overclaim).

#### Step 14: Commit docs

```bash
git add .synlynk/policy.json README.md
git commit -m "docs: un-suspend empirical routing policy, correct README claim

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task B — #2064: Durable logging of dispatch routing fallback

**Files:**
- Modify: `synlynk/dispatch.py:148-160` (`_resolve_dispatch_agent()`'s two `print()` fallback sites, confirmed at lines 149 and 156-159 in this session's reads)
- Reuse: the sentinel-writing helper added in `docs/superpowers/plans/2026-10-06-governs-velocity-unblock-plan.md` §4 — find its exact function name/import path first: `grep -rn "def.*sentinel" synlynk/*.py` (likely in `synlynk/sentinel.py` or inline in `dispatch.py`/`db.py` — confirm before writing code, do not assume a name).
- Test: `tests/test_dispatch_agent_resolution.py` (check first: `grep -rln "_resolve_dispatch_agent" tests/`)

#### Step 1: Find the sentinel helper and job-metadata write path

Run: `grep -rn "def.*sentinel\|sentinel.md" synlynk/*.py | grep -v test`

Confirm the helper's exact signature (it was added for the GOVERNS-linkage preflight warning in the governs-velocity-unblock work — likely something like `append_sentinel_alert(message: str, **kwargs)` writing to `sentinel.md`). Also find how job metadata is currently written for a dispatch (search `grep -rn "job_id.*metadata\|daemon_jobs" synlynk/dispatch.py | head -10`) to find the right place to add `requested_harness`/`actual_harness`/`fallback_reason` fields.

#### Step 2: Write the failing test

Add to the test file identified above (or create `tests/test_dispatch_fallback_logging.py` if `_resolve_dispatch_agent` has no existing dedicated test file):

```python
def test_local_unreachable_fallback_writes_sentinel_entry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: False)
    monkeypatch.setattr(dispatch, "_read_local_fallback", lambda config_path=".synlynk/config.json": "codex")

    conn = None  # _resolve_dispatch_agent's db param is unused on this path
    result = dispatch._resolve_dispatch_agent("auto", "implement", conn)

    assert result == "codex"
    sentinel_path = tmp_path / "sentinel.md"
    assert sentinel_path.exists()
    assert "codex" in sentinel_path.read_text()
    assert "local oMLX unreachable" in sentinel_path.read_text()
```

Adjust the exact assertion once Step 1 confirms the real sentinel-write helper's file target and message format (it may not write directly to `sentinel.md` in the cwd — confirm the path convention it uses before finalizing this test).

#### Step 3: Run test to verify it fails

Run: `pytest tests/test_dispatch_fallback_logging.py -v`
Expected: FAIL — no sentinel.md written yet.

#### Step 4: Add durable logging at both fallback print sites

In `synlynk/dispatch.py`, at the site currently reading:

```python
    if not _preflight_local_silent():
        print(f"Routing to: {fallback} (local oMLX unreachable)")
        return fallback
```

change to (using whichever helper name Step 1 confirmed — shown here as `append_sentinel_alert`, replace with the real name):

```python
    if not _preflight_local_silent():
        message = f"Routing to: {fallback} (local oMLX unreachable)"
        print(message)
        append_sentinel_alert(message, requested="local", actual=fallback)
        return fallback
```

And at the second site:

```python
    score = _get_local_capability_score(task_type, db)
    if score >= threshold:
        print(f"Routing to: local (tier-0, capability score: {score:.2f})")
        return "local"
    message = (
        f"Routing to: {fallback} (local capability score {score:.2f} "
        f"< threshold {threshold:.2f})"
    )
    print(message)
    append_sentinel_alert(message, requested="local", actual=fallback)
    return fallback
```

Do not change the function's return values or control flow — only add the logging call alongside each existing `print()`.

#### Step 5: Run test to verify it passes

Run: `pytest tests/test_dispatch_fallback_logging.py -v`
Expected: PASS

#### Step 6: Add job-metadata persistence

Using the job-metadata write path found in Step 1, thread the same `requested="local", actual=fallback` fact into the job record so `synlynk jobs` can surface it. Write a second test asserting a dispatched job's metadata (or `daemon_jobs` row, whichever table Step 1 identified) contains both `requested_harness` and `actual_harness` fields after a fallback dispatch, following the same tmp_path/monkeypatch pattern as Step 2.

#### Step 7: Run all dispatch tests for regressions

Run: `pytest tests/test_dispatch*.py -v`
Expected: PASS, no regressions in existing `_resolve_dispatch_agent()`/`_preflight_local_silent()` behavior.

#### Step 8: Commit

```bash
git add synlynk/dispatch.py tests/test_dispatch_fallback_logging.py
git commit -m "feat(dispatch): durably log routing-fallback decisions to sentinel.md and job metadata

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task C — #2065: JSON Schema validation for config.json/policy.json via `synlynk doctor`

**Files:**
- Create: `synlynk/config_schema.py`
- Modify: `synlynk/doctor.py` (add `_hc_config_schema()`, `_hc_policy_schema()`, register both in `HEALTH_CHECKS` at line 1030)
- Test: `tests/test_config_schema.py`
- Test: `tests/test_doctor.py` (check first: `ls tests/ | grep -i doctor`)

#### Step 1: Write the failing unit tests for the validator

Create `tests/test_config_schema.py`:

```python
from synlynk.config_schema import validate, CONFIG_SCHEMA, POLICY_SCHEMA


def test_valid_config_produces_no_errors():
    data = {"identity_slug": "synlynk", "local_fallback": "agy", "local_auto_threshold": 0.5}
    assert validate(data, CONFIG_SCHEMA) == []


def test_wrong_type_is_reported():
    data = {"identity_slug": 123}
    errors = validate(data, CONFIG_SCHEMA)
    assert any("identity_slug" in e and "type" in e for e in errors)


def test_missing_required_key_is_reported():
    errors = validate({}, POLICY_SCHEMA)
    assert any("schema_version" in e for e in errors)


def test_invalid_enum_value_is_reported():
    data = {"schema_version": 1, "repo_id": "x", "capability_policy": {"mode": "not-a-real-mode"}}
    errors = validate(data, POLICY_SCHEMA)
    assert any("mode" in e for e in errors)
```

#### Step 2: Run tests to verify they fail

Run: `pytest tests/test_config_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.config_schema'`

#### Step 3: Implement `synlynk/config_schema.py`

Before writing field lists, run `python3 -c "import json; print(list(json.load(open('.synlynk/config.json')).keys()))"` and the same for `.synlynk/policy.json`, to get the real current key sets rather than guessing — the design doc already names the top-level sections (`billing, workspace, harness_billing, agent_slots, swarm_runners, sentinel` for config.json; `schema_version, repo_id, capability_policy, overrides` for policy.json, the latter confirmed live in this session). Only validate top-level keys and known nested shapes that are stable (e.g. `capability_policy.mode`'s enum) — this is deliberately not a full recursive schema per the design's P1-1 scope note.

```python
"""Minimal, stdlib-only schema validation for .synlynk/config.json and policy.json.

No jsonschema dependency (pyproject.toml declares dependencies=[]). The key
set in both files is small and known, so a hand-rolled type/required/enum
checker covers the real failure modes (wrong type, missing key, bad enum)
without implementing $ref resolution or other full-JSON-Schema machinery.
"""

from __future__ import annotations

_MISSING = object()


def _check_field(data: dict, key: str, spec: dict, path: str, errors: list) -> None:
    value = data.get(key, _MISSING)
    if value is _MISSING:
        if spec.get("required"):
            errors.append(f"{path}{key}: required field is missing")
        return
    expected_type = spec.get("type")
    if expected_type and not isinstance(value, expected_type):
        type_name = getattr(expected_type, "__name__", str(expected_type))
        errors.append(f"{path}{key}: expected type {type_name}, got {type(value).__name__}")
        return
    enum = spec.get("enum")
    if enum and value not in enum:
        errors.append(f"{path}{key}: value {value!r} not in allowed set {enum}")
    nested = spec.get("fields")
    if nested and isinstance(value, dict):
        validate_fields(value, nested, path=f"{path}{key}.", errors=errors)


def validate_fields(data: dict, schema_fields: dict, *, path: str = "", errors: list = None) -> list:
    errors = errors if errors is not None else []
    for key, spec in schema_fields.items():
        _check_field(data, key, spec, path, errors)
    return errors


def validate(data: dict, schema: dict) -> list:
    """Return a list of human-readable error strings; empty means valid."""
    if not isinstance(data, dict):
        return [f"root: expected a JSON object, got {type(data).__name__}"]
    return validate_fields(data, schema["fields"])


CONFIG_SCHEMA = {
    "fields": {
        "identity_slug": {"type": str},
        "local_fallback": {"type": str},
        "local_auto_threshold": {"type": (int, float)},
    }
}

POLICY_SCHEMA = {
    "fields": {
        "schema_version": {"type": int, "required": True},
        "repo_id": {"type": str, "required": True},
        "capability_policy": {
            "type": dict,
            "fields": {
                "mode": {"type": str, "enum": ["empirical", "heuristic"]},
                "min_sample_size": {"type": int},
            },
        },
        "overrides": {"type": dict},
    }
}
```

Note: `validate_fields`'s nested call only fires when `value` is a dict and the field spec is itself missing `required` at that key (an absent nested dict is reported by the outer `required` check, not descended into) — this matches the "known, bounded key set" scope; do not generalize to arbitrary depth in this task.

#### Step 4: Run tests to verify they pass

Run: `pytest tests/test_config_schema.py -v`
Expected: PASS (4 tests)

#### Step 5: Commit the validator

```bash
git add synlynk/config_schema.py tests/test_config_schema.py
git commit -m "feat(config): add stdlib-only schema validator for config.json/policy.json

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

#### Step 6: Write the failing doctor integration test

Check for an existing doctor test file first: `ls tests/ | grep -i doctor`. Add to it (or create `tests/test_doctor_config_schema.py`):

```python
import json
import os


def test_doctor_flags_malformed_config_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"identity_slug": 123}, f)  # wrong type

    from synlynk.doctor import _hc_config_schema

    result = _hc_config_schema()
    assert result.status == "fail"
    assert "identity_slug" in result.message


def test_doctor_passes_valid_config_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"identity_slug": "ok"}, f)

    from synlynk.doctor import _hc_config_schema

    result = _hc_config_schema()
    assert result.status == "ok"
```

#### Step 7: Run test to verify it fails

Run: `pytest tests/test_doctor_config_schema.py -v`
Expected: FAIL — `_hc_config_schema` doesn't exist yet.

#### Step 8: Implement the two doctor checks

Add to `synlynk/doctor.py`, following the exact `_hc_project_init()`/`_hc_identity_slug()` pattern already in the file (both read `.synlynk/config.json` the same way):

```python
def _hc_config_schema() -> HealthCheck:
    """Validates .synlynk/config.json against the known field schema."""
    from synlynk.config_schema import validate, CONFIG_SCHEMA

    path = os.path.join(".synlynk", "config.json")
    if not os.path.exists(path):
        return HealthCheck("config_schema", "warn", "No .synlynk/config.json; schema check skipped")
    try:
        with open(path) as config_file:
            data = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        return HealthCheck("config_schema", "fail", f"Cannot parse .synlynk/config.json: {exc}")
    errors = validate(data, CONFIG_SCHEMA)
    if not errors:
        return HealthCheck("config_schema", "ok", ".synlynk/config.json matches expected schema")
    return HealthCheck(
        "config_schema", "fail", "; ".join(errors),
        fix="Fix the listed field(s) in .synlynk/config.json",
    )


def _hc_policy_schema() -> HealthCheck:
    """Validates .synlynk/policy.json against the known field schema."""
    from synlynk.config_schema import validate, POLICY_SCHEMA

    path = os.path.join(".synlynk", "policy.json")
    if not os.path.exists(path):
        return HealthCheck("policy_schema", "warn", "No .synlynk/policy.json; schema check skipped")
    try:
        with open(path) as policy_file:
            data = json.load(policy_file)
    except (OSError, json.JSONDecodeError) as exc:
        return HealthCheck("policy_schema", "fail", f"Cannot parse .synlynk/policy.json: {exc}")
    errors = validate(data, POLICY_SCHEMA)
    if not errors:
        return HealthCheck("policy_schema", "ok", ".synlynk/policy.json matches expected schema")
    return HealthCheck(
        "policy_schema", "fail", "; ".join(errors),
        fix="Fix the listed field(s) in .synlynk/policy.json",
    )
```

Then add both to `HEALTH_CHECKS` at line 1030, immediately after `_hc_identity_slug` (keep related config checks adjacent):

```python
HEALTH_CHECKS = [
    _hc_python_version,
    _hc_project_init,
    _hc_identity_slug,
    _hc_config_schema,
    _hc_policy_schema,
    _hc_model_registry,
    # ... (rest unchanged)
```

#### Step 9: Run test to verify it passes

Run: `pytest tests/test_doctor_config_schema.py -v`
Expected: PASS (2 tests)

#### Step 10: Run the full doctor suite for regressions

Run: `pytest tests/ -v -k doctor`
Expected: PASS, no regressions; `synlynk doctor` run against this repo's own live `.synlynk/config.json`/`policy.json` should report `ok` for both new checks (run `python3 bin/synlynk.py doctor` manually once to eyeball the output).

#### Step 11: Commit

```bash
git add synlynk/doctor.py tests/test_doctor_config_schema.py
git commit -m "feat(doctor): add config.json/policy.json schema validation checks

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task D — #2062: Adapter conformance test suite (narrowed scope)

**Files:**
- Create: `tests/test_adapter_conformance.py`
- Reference only, no modification: `synlynk/harness_adapters/{claude,codex,agy,grok,local}.py`, `synlynk/harness_adapters/base.py`, `synlynk/harness_adapters/request.py`, `synlynk/jobs.py` (`_check_task_receipt`), `synlynk/costs.py` (`extract_tokens`)

**Context confirmed this session:** the 5 registered adapters implement the `HarnessAdapter` Protocol from `base.py` (`build_cmd`, `parse_output`, `translate_permissions`, `classify_failure`, `resolve_model`). A real signature drift already exists: `base.py`'s Protocol declares `translate_permissions(self, permissions, read_only, skip_permissions=False)`, but `claude.py`, `codex.py`, and `agy.py` all define it with only 2 params (`permissions, read_only` — no `skip_permissions`), while `grok.py`, `legacy.py`, `local.py` were not yet checked for their exact arity. This conformance suite should surface that drift as a real, not synthetic, failing case — do not "fix" the drift as part of this task (out of scope per the design's narrowed Section D); just let the suite report it.

#### Step 1: Confirm each adapter's registered name and constructor

Run: `grep -n "class.*Adapter" synlynk/harness_adapters/{claude,codex,agy,grok,local}.py`
Run: `grep -n "register\|ADAPTERS\s*=" synlynk/harness_adapters/registry.py`

Use these to build the parametrized fixture list — the suite must instantiate each of the 5 adapter classes exactly as the registry does (same constructor args, if any).

#### Step 2: Write the failing conformance tests

Create `tests/test_adapter_conformance.py`:

```python
import hashlib
import inspect

import pytest

from synlynk.harness_adapters.agy import AgyAdapter
from synlynk.harness_adapters.claude import ClaudeAdapter
from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.harness_adapters.grok import GrokAdapter
from synlynk.harness_adapters.local import LocalAdapter
from synlynk.harness_adapters.base import HarnessAdapter

ALL_ADAPTERS = [ClaudeAdapter, CodexAdapter, AgyAdapter, GrokAdapter, LocalAdapter]


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_implements_protocol_methods(adapter_cls):
    for name in ("build_cmd", "parse_output", "translate_permissions", "classify_failure", "resolve_model"):
        assert hasattr(adapter_cls, name), f"{adapter_cls.__name__} missing {name}"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_translate_permissions_signature_matches_protocol(adapter_cls):
    protocol_params = list(inspect.signature(HarnessAdapter.translate_permissions).parameters)
    adapter_params = list(inspect.signature(adapter_cls.translate_permissions).parameters)
    assert adapter_params == protocol_params, (
        f"{adapter_cls.__name__}.translate_permissions{tuple(adapter_params)} "
        f"does not match Protocol{tuple(protocol_params)}"
    )


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_parse_output_extracts_receipt_marker(adapter_cls):
    from synlynk.jobs import _check_task_receipt

    adapter = adapter_cls()
    task_sha = hashlib.sha256(b"example task").hexdigest()
    raw_text = f"SYNLYNK_TASK_RECEIVED: {task_sha}\nsome other output\n"
    event = adapter.parse_output(raw_text)
    assert event.compatibility_evidence is not None
    assert event.compatibility_evidence.get("receipt") == task_sha
    assert _check_task_receipt(raw_text, task_sha) == "ok"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_parse_output_flags_missing_receipt_marker(adapter_cls):
    """A deliberately broken fixture (no receipt line) must be caught, not silently passed."""
    adapter = adapter_cls()
    task_sha = hashlib.sha256(b"example task").hexdigest()
    raw_text = "no receipt marker here\n"
    event = adapter.parse_output(raw_text)
    assert event.compatibility_evidence.get("receipt") is None
    from synlynk.jobs import _check_task_receipt
    assert _check_task_receipt(raw_text, task_sha) == "absent"


@pytest.mark.parametrize("adapter_cls", ALL_ADAPTERS)
def test_classify_failure_returns_known_failure_kind_or_none(adapter_cls):
    from synlynk.harness_adapters.base import FailureKind

    adapter = adapter_cls()
    result = adapter.classify_failure(1, "not signed in", "")
    assert result is None or isinstance(result, FailureKind)
```

Leave a `# TODO(human-reviewed)` style note out of this file per the no-placeholders rule — instead, if `cost_entries` write-through conformance needs a per-harness output fixture (one real stdout sample per harness showing token counts in that harness's native format), get those fixtures from `grep -B2 -A10 "def extract_tokens" synlynk/costs.py` to see the regex patterns it already matches per `agent` value, and write one `test_extract_tokens_recognizes_<harness>_format` test per harness using a minimal literal string matching that harness's documented format — read `synlynk/costs.py:413` in full before writing these, since the exact per-harness regex patterns were not read this session and must not be guessed.

#### Step 3: Run tests, note the expected real failure

Run: `pytest tests/test_adapter_conformance.py -v`
Expected: `test_translate_permissions_signature_matches_protocol` FAILS for `ClaudeAdapter`, `CodexAdapter`, `AgyAdapter` (confirmed signature drift — this is the suite doing its job, not a bug in the test). All other tests should PASS if the adapters' `parse_output`/`classify_failure` behave as read in `codex.py` this session.

#### Step 4: File the signature-drift finding, do not fix it here

Per the design's explicit narrowing ("no change to LegacyAdapter or the dispatch.py fallback" — and by the same logic, no unplanned fix to adapter signatures either, since that wasn't brainstormed), file a new issue: `gh:#NEW "translate_permissions signature drift: claude/codex/agy adapters missing skip_permissions param present in base.py Protocol"`, referencing this conformance suite's failing test as reproduction. Then mark the 3 failing parametrized cases `@pytest.mark.xfail(reason="gh:#NEW — signature drift, tracked separately")` so the suite is green and the drift is tracked, not silently red or silently fixed out-of-scope.

#### Step 5: Run full suite to verify green

Run: `pytest tests/test_adapter_conformance.py -v`
Expected: PASS (3 cases `xfail`, rest pass)

#### Step 6: Commit

```bash
git add tests/test_adapter_conformance.py
git commit -m "test(adapters): add cross-harness conformance suite for receipt/cost/failure contracts

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:** Section A (#2063) → Task A, all 4 fix items (ranking function, dispatch wiring, policy.json edit, README edit) covered. Section B (#2064) → Task B, both fallback sites + job metadata covered. Section C (#2065) → Task C, validator module + 2 doctor checks covered. Section D (#2062) → Task D, conformance suite covering receipt marker + a path to cost-attribution tests + failure-kind classification covered, with the `LegacyAdapter`-untouched constraint respected.

**Placeholder scan:** Task D's Step 2 intentionally defers the exact `extract_tokens()` per-harness fixture strings to execution time rather than guessing unread regex patterns — this is flagged explicitly as a read-before-write instruction, not a "TODO" left unresolved; the acceptable alternative (per the no-placeholders rule's spirit) would be reading `costs.py` now, but that file's content is outside the budget of this planning pass. The executing agent must read it before writing those specific tests — this is a precondition, not a skipped step.

**Type consistency:** `ranked_harness_for_task()`'s signature (Task A, Step 3) matches its two call sites in Step 6's test and Step 8's wiring code. `HealthCheck` usage in Task C matches the existing `_hc_project_init()`/`_hc_identity_slug()` pattern exactly (positional `name, status, message`, keyword `fix`).

---

## Sequencing

All four tasks are independent and may be dispatched in parallel to different harnesses, each in its own worktree/branch per CLAUDE.md's worktree-per-feature policy. Task A is the highest-risk (live routing behavior change) and should get the most careful cross-harness review; B, C, D are lower-risk/additive. None blocks any other.
