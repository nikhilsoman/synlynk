# Autonomous backlog pickup + scheduling wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `synlynk/backlog.py`'s ingest/triage/auto-promote pipeline and `synlynk/scheduler.py`'s capability-aware batch scheduler into `SynlynkDaemon._run_loop`'s existing poll tick, gated by `autonomy_mode`, so durable agents pick up backlog work without a human running `synlynk schedule`/`synlynk backlog ...` by hand.

**Architecture:** A new `_autonomy_pass(conn=None)` function in `synlynk/scheduler.py` chains `ingest_backlog() -> triage_backlog() -> auto_promote_backlog() -> (mode gate) -> cmd_schedule(execute=True)`. `SynlynkDaemon._run_loop` calls it under two triggers (interval elapsed, or fleet just went idle), both already inside the existing `while True: time.sleep(interval)` tick — no new thread. A new confidence threshold in `synthesize_story_from_issue()` (and a `require_explicit_goal` flag on `link_backlog_item_to_goal()`) stops auto-promoted stories from always getting a goal; `_compute_schedule_plan()` then hard-blocks any `goal_id IS NULL` story with reason `no_goal_link`.

**Tech Stack:** Python 3 stdlib only (sqlite3, no new deps). pytest for tests, using the existing `scheduler_db`-style fixture (chdir into `tmp_path`, fresh `_DB_SCHEMA` + `_migrate_db`).

**Spec:** `docs/superpowers/specs/2026-10-13-autonomous-backlog-scheduling-design.md` (gh:#2262, story-6e633122, linked to goal-8f64eff5)

---

## Pre-flight: naming collision to avoid

`SynlynkDaemon` already has an unrelated `autonomous`/`_autonomous_tick()`/`SYNLYNK_AUTONOMOUS` mechanism (`synlynk/daemon.py:1045-1077`) that runs a bounded heal/TPM sweep. **Do not** name anything in this plan `_autonomous_*` or reuse `self.autonomous`. This plan's new state lives in a separate attribute (`self._last_autonomy_pass_at`, `self._last_dispatch_count`) and a separate function (`_autonomy_pass`, which is scheduler.py's name, not daemon.py's — no edit to `_autonomous_tick` itself).

## Pre-flight: where the new interval setting lives

The spec's Part 1 calls for a new `.synlynk/config.json` key `autonomy_pass_interval_seconds`. `synlynk/__init__.py`'s `load_config()` (line 1336) composes `.synlynk/workspace.json` + `.synlynk/billing.json` + policy fields, with `.synlynk/config.json` only read as a legacy migration source — not a place to casually add one more key. `synlynk/autonomy.py`'s `get_autonomy_mode()` already reads `.synlynk/config.json` directly (not through `load_config()`) for exactly this reason. This plan follows that existing pattern: a new `_autonomy_pass_interval_seconds()` helper in `synlynk/scheduler.py` reads `.synlynk/config.json` directly, default `1800`, instead of routing through `load_config()`.

---

### Task 1: Confidence threshold in goal matching

**Files:**
- Modify: `synlynk/backlog.py:382-392` (`synthesize_story_from_issue`'s goal-matching loop)
- Modify: `synlynk/backlog.py:720-773` (`link_backlog_item_to_goal`)
- Modify: `synlynk/backlog.py:612-717` (`auto_promote_backlog`, the two call sites that currently assume `goal_id` is always set)
- Test: `tests/test_backlog.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_backlog.py` (use the existing `isolated_db`/`project_dir`-style fixture already used elsewhere in that file — check the file's top-of-file fixture import before adding a second one):

```python
def test_synthesize_story_from_issue_returns_none_goal_below_threshold():
    from synlynk.backlog import synthesize_story_from_issue

    issue = {
        "title": "Fix typo in README",
        "body": "One word is misspelled on line 4.",
        "labels": [],
        "number": 9001,
    }
    # No keyword overlap with any DEFAULT_ACTIVE_GOALS entry.
    result = synthesize_story_from_issue(issue, active_goals=[
        {"goal_id": "goal-unrelated", "title": "Swarm runners", "keywords": ["swarm", "fly", "k8s"]},
    ])
    assert result["goal_id"] is None


def test_synthesize_story_from_issue_returns_goal_id_above_threshold():
    from synlynk.backlog import synthesize_story_from_issue

    issue = {
        "title": "Add kubernetes pod runner for swarm dispatch",
        "body": "Needs a new k8s pod registry entry.",
        "labels": [],
        "number": 9002,
    }
    result = synthesize_story_from_issue(issue, active_goals=[
        {"goal_id": "goal-match", "title": "Swarm runners", "keywords": ["swarm", "pod", "k8s", "kubernetes", "registry", "dispatch"]},
    ])
    assert result["goal_id"] == "goal-match"


def test_link_backlog_item_to_goal_require_explicit_skips_default_fallback(scheduler_db):
    import sqlite3
    from synlynk.backlog import link_backlog_item_to_goal

    conn = sqlite3.connect(scheduler_db)
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES ('story-x1', 'test')"
    )
    conn.execute(
        "INSERT INTO backlog_items (item_id, title, story_id, status) "
        "VALUES ('item-x1', 'test', 'story-x1', 'triaged')"
    )
    conn.commit()

    result = link_backlog_item_to_goal(
        "item-x1", goal_id=None, db_conn=conn, require_explicit_goal=True
    )
    assert result["linked"] is False
    assert result["reason"] == "no_confident_match"

    row = conn.execute("SELECT goal_id FROM stories WHERE story_id='story-x1'").fetchone()
    assert row[0] is None
    conn.close()


def test_link_backlog_item_to_goal_default_fallback_still_works_when_not_required(scheduler_db):
    import sqlite3
    from synlynk.backlog import link_backlog_item_to_goal, DEFAULT_BACKLOG_GOAL_ID

    conn = sqlite3.connect(scheduler_db)
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES ('story-x2', 'test')"
    )
    conn.commit()

    result = link_backlog_item_to_goal("story-x2", goal_id=None, db_conn=conn)
    assert result["linked"] is True
    assert result["goal_id"] == DEFAULT_BACKLOG_GOAL_ID
    conn.close()
```

Import the `scheduler_db` fixture pattern from `tests/test_fleet_scheduler.py:11-27` into `tests/test_backlog.py` if it isn't already defined there (copy the fixture function verbatim into `tests/test_backlog.py` under a `conftest`-shared name, or add it locally — check first whether `tests/test_backlog.py` already defines an equivalent fixture before duplicating).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backlog.py -k "threshold or require_explicit or default_fallback" -q`
Expected: FAIL — `synthesize_story_from_issue` has no threshold yet (`goal_id` is never `None`), and `link_backlog_item_to_goal` has no `require_explicit_goal` parameter (`TypeError: unexpected keyword argument`).

- [ ] **Step 3: Implement the threshold in `synthesize_story_from_issue`**

In `synlynk/backlog.py`, locate this existing block (around line 382):

```python
    best_goal_id = "goal-6733bbf1"
    best_score = -1

    for g in goals:
        g_id = g.get("goal_id", "")
        g_kws = set(g.get("keywords", []))
        if not g_kws:
            g_kws = set(re.findall(r"\w+", (g.get("title", "") + " " + g.get("criterion", "")).lower()))
        score = len(tokens.intersection(g_kws))
        if score > best_score:
            best_score = score
            best_goal_id = g_id
```

Replace it with:

```python
    best_goal_id = None
    best_score = -1

    for g in goals:
        g_id = g.get("goal_id", "")
        g_kws = set(g.get("keywords", []))
        if not g_kws:
            g_kws = set(re.findall(r"\w+", (g.get("title", "") + " " + g.get("criterion", "")).lower()))
        score = len(tokens.intersection(g_kws))
        if score > best_score:
            best_score = score
            best_goal_id = g_id

    if best_score < MIN_GOAL_MATCH_SCORE:
        best_goal_id = None
```

Add the new module-level constant near `DEFAULT_BACKLOG_GOAL_ID` (synlynk/backlog.py:45):

```python
DEFAULT_BACKLOG_GOAL_ID = "goal-d3333441"

# Minimum keyword-overlap score for synthesize_story_from_issue() to assign a
# goal automatically. Below this, the story is created with goal_id=None and
# left for a human (or a later triage pass) to link explicitly — see
# docs/superpowers/specs/2026-10-13-autonomous-backlog-scheduling-design.md §3.
MIN_GOAL_MATCH_SCORE = 2
```

- [ ] **Step 4: Add `require_explicit_goal` to `link_backlog_item_to_goal`**

In `synlynk/backlog.py`, change the signature (line 720) from:

```python
def link_backlog_item_to_goal(
    item_id: str,
    goal_id: Optional[str] = None,
    db_conn=None,
) -> dict:
```

to:

```python
def link_backlog_item_to_goal(
    item_id: str,
    goal_id: Optional[str] = None,
    db_conn=None,
    require_explicit_goal: bool = False,
) -> dict:
```

And change the body immediately after the docstring (currently):

```python
    if not item_id or not str(item_id).strip():
        return {"linked": False, "reason": "empty_item_id"}

    selected_goal_id = (goal_id or DEFAULT_BACKLOG_GOAL_ID).strip()
    if not selected_goal_id:
        selected_goal_id = DEFAULT_BACKLOG_GOAL_ID
```

to:

```python
    if not item_id or not str(item_id).strip():
        return {"linked": False, "reason": "empty_item_id"}

    if require_explicit_goal and not (goal_id and str(goal_id).strip()):
        return {"linked": False, "reason": "no_confident_match", "item_id": str(item_id).strip()}

    selected_goal_id = (goal_id or DEFAULT_BACKLOG_GOAL_ID).strip()
    if not selected_goal_id:
        selected_goal_id = DEFAULT_BACKLOG_GOAL_ID
```

- [ ] **Step 5: Pass `require_explicit_goal=True` from `auto_promote_backlog`**

In `synlynk/backlog.py`'s `auto_promote_backlog` (around line 695), change:

```python
        link_result = link_backlog_item_to_goal(
            item_id,
            goal_id=goal_id,
            db_conn=conn,
        )
```

to:

```python
        link_result = link_backlog_item_to_goal(
            item_id,
            goal_id=goal_id,
            db_conn=conn,
            require_explicit_goal=True,
        )
```

This is the only call site that needs the new flag — `auto_promote_backlog` is the path the spec targets. Leave every other caller (e.g. the manual `synlynk goal link` CLI command) using the default `require_explicit_goal=False`, since a human explicitly running that command has already made the confident-match decision themselves.

Also confirm the `INSERT INTO stories (...)` statement a few lines above (already includes a `goal_id` column per `synlynk/backlog.py:645-663`) tolerates `goal_id=None` — SQLite allows `NULL` for a `TEXT REFERENCES goals(goal_id)` column with no `NOT NULL` constraint (confirmed via `synlynk/db_schema.py:27`'s `stories` table definition and the `ALTER TABLE stories ADD COLUMN goal_id TEXT REFERENCES goals(goal_id)` migration at `synlynk/db.py:1132` — no `NOT NULL`). No schema change needed.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_backlog.py -k "threshold or require_explicit or default_fallback" -q`
Expected: PASS

- [ ] **Step 7: Run the full backlog test suite to check for regressions**

Run: `pytest tests/test_backlog.py tests/test_backlog_automation.py tests/test_backlog_triage_triggers.py -q`
Expected: PASS. If any existing test asserted a non-null `goal_id` from a low-keyword-overlap issue, that test's fixture issue text was relying on the old "always assign some goal" behavior — update its fixture text to clearly overlap a goal's keywords (don't weaken the new threshold to make the old test pass).

- [ ] **Step 8: Commit**

```bash
git add synlynk/backlog.py tests/test_backlog.py
git commit -m "feat: add goal-match confidence threshold, no_confident_match signal (gh:#2262)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

### Task 2: `no_goal_link` blocked reason in the scheduler

**Files:**
- Modify: `synlynk/scheduler.py:62-72` (the `_compute_schedule_plan` story-selection query and per-story loop)
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_fleet_scheduler.py` (reuses the file's existing `scheduler_db` fixture):

```python
def test_compute_schedule_plan_blocks_story_with_no_goal_link(scheduler_db):
    import sqlite3
    from synlynk.scheduler import _compute_schedule_plan

    conn = sqlite3.connect(scheduler_db)
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, priority, readiness, goal_id) "
        "VALUES ('story-nogoal', 'test', 'backend', 'platform', 3, 'ready', NULL)"
    )
    conn.commit()
    conn.close()

    monkeypatch_target = "synlynk._capability_candidates_for_story"
    import synlynk
    orig = synlynk._capability_candidates_for_story
    synlynk._capability_candidates_for_story = lambda conn, engg, org, industry, phase: [("codex", 10.0, "gpt-5")]
    try:
        result = _compute_schedule_plan()
    finally:
        synlynk._capability_candidates_for_story = orig

    blocked_reasons = {b["story_id"]: b["reason"] for b in result["blocked"]}
    assert blocked_reasons.get("story-nogoal") == "no_goal_link"
    assert all(p["story_id"] != "story-nogoal" for p in result["plan"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -k no_goal_link -q`
Expected: FAIL — `_compute_schedule_plan` doesn't check `goal_id` yet, so `story-nogoal` ends up in `plan`, not `blocked`.

- [ ] **Step 3: Implement the block**

In `synlynk/scheduler.py`, the story-selection query (lines 62-69) currently reads:

```python
        query = (
            "SELECT s.story_id, s.title, s.engg_domain, s.org_domain, s.industry, "
            "s.phase, s.priority, s.estimated_tokens FROM stories s "
            "WHERE s.readiness='ready' AND NOT EXISTS ("
            "  SELECT 1 FROM daemon_jobs dj WHERE dj.story_id=s.story_id "
            "  AND dj.status IN ('queued','running')"
            ") ORDER BY s.priority ASC, s.created_at ASC"
        )
```

Change it to also select `goal_id`:

```python
        query = (
            "SELECT s.story_id, s.title, s.engg_domain, s.org_domain, s.industry, "
            "s.phase, s.priority, s.estimated_tokens, s.goal_id FROM stories s "
            "WHERE s.readiness='ready' AND NOT EXISTS ("
            "  SELECT 1 FROM daemon_jobs dj WHERE dj.story_id=s.story_id "
            "  AND dj.status IN ('queued','running')"
            ") ORDER BY s.priority ASC, s.created_at ASC"
        )
```

Then update the unpacking and add the new gate. Change:

```python
        for (story_id, title, engg, org, industry, phase, priority,
             est_tokens) in stories:
            if _story_retry_count(conn, story_id) >= MAX_STORY_RETRIES:
                blocked.append({"story_id": story_id, "reason": "retry_cap_exceeded"})
                continue

            candidates = _capability_candidates_for_story(conn, engg, org, industry, phase)
```

to:

```python
        for (story_id, title, engg, org, industry, phase, priority,
             est_tokens, goal_id) in stories:
            if not goal_id:
                blocked.append({"story_id": story_id, "reason": "no_goal_link"})
                continue

            if _story_retry_count(conn, story_id) >= MAX_STORY_RETRIES:
                blocked.append({"story_id": story_id, "reason": "retry_cap_exceeded"})
                continue

            candidates = _capability_candidates_for_story(conn, engg, org, industry, phase)
```

`no_goal_link` is checked first, ahead of `retry_cap_exceeded`/`no_capability_candidates`/`quota_exhausted` — a story a human hasn't linked to a goal yet shouldn't consume capability/quota lookups at all.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py -k no_goal_link -q`
Expected: PASS

- [ ] **Step 5: Run the full scheduler test suite to check for regressions**

Run: `pytest tests/test_fleet_scheduler.py -q`
Expected: PASS. Every existing test in this file that inserts a `stories` row without an explicit `goal_id` column value will now have `goal_id` default to `NULL` (no `DEFAULT` clause on that column per `synlynk/db_schema.py:27`) and will newly land in `blocked` with `no_goal_link` instead of `plan`. Fix each such test's `INSERT` to include a non-null `goal_id` (any placeholder string like `'goal-test'` — no foreign-key enforcement is active by default in SQLite unless `PRAGMA foreign_keys=ON` was run, so an arbitrary string works for test purposes) rather than loosening the new gate.

- [ ] **Step 6: Commit**

```bash
git add synlynk/scheduler.py tests/test_fleet_scheduler.py
git commit -m "feat: block scheduling of stories with no goal link (gh:#2262)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

### Task 3: `_autonomy_pass()` in `synlynk/scheduler.py`

**Files:**
- Modify: `synlynk/scheduler.py` (add `_autonomy_pass_interval_seconds()` and `_autonomy_pass()`)
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fleet_scheduler.py`:

```python
def test_autonomy_pass_interval_default_is_1800(scheduler_db):
    from synlynk.scheduler import _autonomy_pass_interval_seconds
    assert _autonomy_pass_interval_seconds() == 1800


def test_autonomy_pass_interval_reads_config_override(scheduler_db, tmp_path):
    import json
    from synlynk.scheduler import _autonomy_pass_interval_seconds

    with open(".synlynk/config.json", "w") as f:
        json.dump({"autonomy_pass_interval_seconds": 60}, f)

    assert _autonomy_pass_interval_seconds() == 60


def test_autonomy_pass_manual_mode_skips_scheduling(scheduler_db, monkeypatch):
    import json
    from synlynk import scheduler as scheduler_mod

    with open(".synlynk/config.json", "w") as f:
        json.dump({"autonomy_mode": "manual"}, f)

    calls = {"ingest": 0, "triage": 0, "promote": 0, "schedule": 0}
    monkeypatch.setattr(scheduler_mod, "ingest_backlog", lambda *a, **kw: calls.__setitem__("ingest", calls["ingest"] + 1))
    monkeypatch.setattr(scheduler_mod, "triage_backlog", lambda *a, **kw: calls.__setitem__("triage", calls["triage"] + 1))
    monkeypatch.setattr(scheduler_mod, "auto_promote_backlog", lambda *a, **kw: calls.__setitem__("promote", calls["promote"] + 1))
    monkeypatch.setattr(scheduler_mod, "cmd_schedule", lambda *a, **kw: calls.__setitem__("schedule", calls["schedule"] + 1))

    scheduler_mod._autonomy_pass()

    assert calls == {"ingest": 1, "triage": 1, "promote": 1, "schedule": 0}


def test_autonomy_pass_supervised_mode_runs_scheduling(scheduler_db, monkeypatch):
    import json
    from synlynk import scheduler as scheduler_mod

    with open(".synlynk/config.json", "w") as f:
        json.dump({"autonomy_mode": "supervised"}, f)

    calls = {"schedule": 0}
    monkeypatch.setattr(scheduler_mod, "ingest_backlog", lambda *a, **kw: None)
    monkeypatch.setattr(scheduler_mod, "triage_backlog", lambda *a, **kw: None)
    monkeypatch.setattr(scheduler_mod, "auto_promote_backlog", lambda *a, **kw: [])
    monkeypatch.setattr(scheduler_mod, "cmd_schedule", lambda *a, **kw: calls.__setitem__("schedule", calls["schedule"] + 1))

    scheduler_mod._autonomy_pass()

    assert calls["schedule"] == 1


def test_autonomy_pass_stage_failure_does_not_abort_remaining_stages(scheduler_db, monkeypatch, capsys):
    import json
    from synlynk import scheduler as scheduler_mod

    with open(".synlynk/config.json", "w") as f:
        json.dump({"autonomy_mode": "autonomous"}, f)

    calls = {"schedule": 0}

    def boom(*a, **kw):
        raise RuntimeError("ingest exploded")

    monkeypatch.setattr(scheduler_mod, "ingest_backlog", boom)
    monkeypatch.setattr(scheduler_mod, "triage_backlog", lambda *a, **kw: None)
    monkeypatch.setattr(scheduler_mod, "auto_promote_backlog", lambda *a, **kw: [])
    monkeypatch.setattr(scheduler_mod, "cmd_schedule", lambda *a, **kw: calls.__setitem__("schedule", calls["schedule"] + 1))

    scheduler_mod._autonomy_pass()  # must not raise

    assert calls["schedule"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fleet_scheduler.py -k autonomy_pass -q`
Expected: FAIL — `synlynk.scheduler` has no `_autonomy_pass`/`_autonomy_pass_interval_seconds`, and no `ingest_backlog`/`triage_backlog`/`auto_promote_backlog`/`cmd_schedule` module-level names are importable as monkeypatch targets yet (`cmd_schedule` already exists in this module; the other three need importing).

- [ ] **Step 3: Implement `_autonomy_pass_interval_seconds()` and `_autonomy_pass()`**

Add to the top of `synlynk/scheduler.py`, after the existing module docstring (before `MAX_STORY_RETRIES = 2`):

```python
import json
import os
import traceback

from synlynk.backlog import auto_promote_backlog, ingest_backlog, triage_backlog
```

Append to the end of `synlynk/scheduler.py` (after `cmd_schedule`):

```python
def _autonomy_pass_interval_seconds() -> int:
    """Seconds between unforced _autonomy_pass() runs.

    Reads .synlynk/config.json directly (not load_config()) for the same
    reason synlynk/autonomy.py's get_autonomy_mode() does: this key is a
    small daemon-loop tuning knob, not part of the workspace/billing split
    config load_config() composes.
    """
    path = os.path.join(os.getcwd(), ".synlynk", "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return int(data.get("autonomy_pass_interval_seconds", 1800))
        except (json.JSONDecodeError, ValueError, OSError):
            return 1800
    return 1800


def _autonomy_pass(conn=None) -> None:
    """Backlog bookkeeping (always) + capability-aware scheduling (mode-gated).

    Each stage runs independently: a failure in one stage is logged and does
    not prevent the remaining stages from running. Never raises -- callers
    (the daemon poll loop) must be able to call this every tick without a
    try/except of their own.

    See docs/superpowers/specs/2026-10-13-autonomous-backlog-scheduling-design.md
    """
    from synlynk.autonomy import AutonomyMode, get_autonomy_mode

    for stage_name, stage_fn in (
        ("ingest_backlog", lambda: ingest_backlog(db_conn=conn)),
        ("triage_backlog", lambda: triage_backlog(db_conn=conn)),
        ("auto_promote_backlog", lambda: auto_promote_backlog(db_conn=conn)),
    ):
        try:
            stage_fn()
        except Exception:
            print(f"  ⚠ _autonomy_pass: {stage_name} failed:")
            traceback.print_exc()

    try:
        mode = get_autonomy_mode()
    except Exception:
        print("  ⚠ _autonomy_pass: get_autonomy_mode failed, defaulting to MANUAL (no scheduling this pass):")
        traceback.print_exc()
        return

    if mode == AutonomyMode.MANUAL:
        return

    try:
        cmd_schedule(execute=True)
    except Exception:
        print("  ⚠ _autonomy_pass: cmd_schedule failed:")
        traceback.print_exc()
```

Note: `ingest_backlog`/`triage_backlog`/`auto_promote_backlog` are called with `db_conn=conn` — check each function's actual signature in `synlynk/backlog.py` accepts `db_conn` as a keyword (confirmed: `auto_promote_backlog(db_conn=None, min_tier: int = 1)` at line 612; `ingest_backlog`/`triage_backlog` both take `db_conn=None` per their definitions at lines 429 and 522 respectively — verify this still holds at implementation time since line numbers may have shifted after Tasks 1-2's edits).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fleet_scheduler.py -k autonomy_pass -q`
Expected: PASS

- [ ] **Step 5: Run the full scheduler + backlog suites to check for regressions**

Run: `pytest tests/test_fleet_scheduler.py tests/test_backlog.py tests/test_backlog_automation.py tests/test_backlog_triage_triggers.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/scheduler.py tests/test_fleet_scheduler.py
git commit -m "feat: add _autonomy_pass() chaining backlog pipeline + mode-gated scheduling (gh:#2262)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

### Task 4: Wire triggers into `SynlynkDaemon._run_loop`

**Files:**
- Modify: `synlynk/daemon.py:1045-1066` (`SynlynkDaemon.__init__`)
- Modify: `synlynk/daemon.py:1259-1351` (`SynlynkDaemon._run_loop`)
- Test: `tests/test_daemon_supervision_discovery.py` (or a new `tests/test_autonomy_pass_trigger.py` if that file's existing fixtures don't fit — check its fixtures first)

- [ ] **Step 1: Write the failing test**

First read `tests/test_daemon_supervision_discovery.py` in full to see how it instantiates `SynlynkDaemon` and drives `_run_loop` (or a unit-level piece of it) without actually forking/daemonizing or sleeping for real — reuse that harness. Then add a test with this shape (adjust fixture names to match what that file already provides):

```python
def test_run_loop_triggers_autonomy_pass_on_interval_elapse(daemon_test_env, monkeypatch):
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = 0.0  # force "elapsed" on first tick
    d._last_dispatch_count = 0

    calls = {"autonomy_pass": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("autonomy_pass", calls["autonomy_pass"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 0)  # always "elapsed"

    d._maybe_run_autonomy_pass(launched=0)

    assert calls["autonomy_pass"] == 1


def test_run_loop_triggers_autonomy_pass_on_idle_transition(daemon_test_env, monkeypatch):
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod
    import time

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = time.time()  # interval just reset, not elapsed
    d._last_dispatch_count = 2  # previous tick launched 2 jobs

    calls = {"autonomy_pass": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("autonomy_pass", calls["autonomy_pass"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 999999)  # interval trigger would not fire
    monkeypatch.setattr(daemon_mod, "_pkg", lambda name: (lambda: _FakeConnNoRunningJobs()) if name == "_get_db" else None)

    d._maybe_run_autonomy_pass(launched=0)  # this tick launched 0, previous tick launched 2 -> idle transition

    assert calls["autonomy_pass"] == 1


class _FakeConnNoRunningJobs:
    def execute(self, query, params=()):
        class _Row:
            def fetchone(self):
                return (0,)
        return _Row()

    def close(self):
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon_supervision_discovery.py -k autonomy_pass_trigger -q` (adjust the `-k` pattern/file to wherever you placed the tests)
Expected: FAIL — `SynlynkDaemon` has no `_maybe_run_autonomy_pass` method yet, and `synlynk.daemon` has no `_autonomy_pass`/`_autonomy_pass_interval_seconds` imported/visible names yet.

- [ ] **Step 3: Implement the trigger method and wire it into `_run_loop`**

In `synlynk/daemon.py`, add the import near the top of the file (find the existing `from synlynk...import` block, e.g. near other `from synlynk.X import Y` lines — check the current import block before this line since the exact line number will have shifted after this plan's own earlier edits are absent from daemon.py; this file is untouched by Tasks 1-3):

```python
from synlynk.scheduler import _autonomy_pass, _autonomy_pass_interval_seconds
```

In `SynlynkDaemon.__init__` (`synlynk/daemon.py:1045-1066`), add two new attributes alongside the existing `self._last_autonomous_run = 0.0` line:

```python
        self.autonomous = autonomous
        self._last_autonomous_run = 0.0
        self._last_autonomy_pass_at = 0.0
        self._last_dispatch_count = 0
```

Add a new method to `SynlynkDaemon`, placed right after `_run_capability_watch_tick` (after `synlynk/daemon.py:1100`, before `_prepare_start`):

```python
    def _maybe_run_autonomy_pass(self, launched: int) -> None:
        """Hybrid interval+idle trigger for the backlog/scheduling autonomy pass.

        Both triggers call the exact same _autonomy_pass() -- no divergent
        logic path (per the design spec's Part 1). Resets the interval timer
        on every actual run so the two triggers can't double-fire back to
        back in the same tick.
        """
        now = time.time()
        interval_elapsed = (now - self._last_autonomy_pass_at) >= _autonomy_pass_interval_seconds()

        idle_transition = False
        if self._last_dispatch_count > 0 and launched == 0:
            conn = None
            try:
                conn = _pkg("_get_db")()
                row = conn.execute(
                    "SELECT COUNT(*) FROM daemon_jobs WHERE status IN ('queued','running')"
                ).fetchone()
                idle_transition = bool(row and row[0] == 0)
            except Exception:
                idle_transition = False
            finally:
                if conn is not None:
                    conn.close()

        if interval_elapsed or idle_transition:
            try:
                _autonomy_pass()
            except Exception:
                import traceback as _traceback
                _traceback.print_exc()
            self._last_autonomy_pass_at = now

        self._last_dispatch_count = launched
```

In `_run_loop` (`synlynk/daemon.py:1325-1329`), change:

```python
            try:
                _reconcile_daemon_jobs()
                _dispatch_ready_jobs(max_parallel=max_parallel)
            except Exception:
                _traceback.print_exc()
```

to:

```python
            try:
                _reconcile_daemon_jobs()
                launched = _dispatch_ready_jobs(max_parallel=max_parallel)
            except Exception:
                _traceback.print_exc()
                launched = 0
            self._maybe_run_autonomy_pass(launched)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon_supervision_discovery.py -k autonomy_pass_trigger -q`
Expected: PASS

- [ ] **Step 5: Run the full daemon test suite to check for regressions**

Run: `pytest tests/test_daemon_supervision_discovery.py tests/test_control_plane_daemon_health.py tests/test_daemon_liveness_1572.py tests/test_daemon_token_refresh.py tests/test_vizor_daemon.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_supervision_discovery.py
git commit -m "feat: wire hybrid interval+idle autonomy-pass trigger into daemon poll loop (gh:#2262)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ"
```

---

### Task 5: Full-suite verification and PR

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `pytest -q`
Expected: all tests pass (per gh:#2240's standing feedback memory, use `-q`, not `-v`, to avoid an oversized transcript).

- [ ] **Step 2: Manual smoke check of `_autonomy_pass()` end to end**

```bash
python3 -c "
import tempfile, os, sqlite3
tmp = tempfile.mkdtemp()
os.chdir(tmp)
os.makedirs('.synlynk', exist_ok=True)
os.makedirs('project-docs', exist_ok=True)
from synlynk import _DB_SCHEMA
from synlynk.db import _migrate_db
conn = sqlite3.connect('.synlynk/state.db')
conn.executescript(_DB_SCHEMA)
_migrate_db(conn)
conn.commit()
conn.close()
import synlynk
synlynk._get_db = lambda: sqlite3.connect('.synlynk/state.db')
import json
with open('.synlynk/config.json', 'w') as f:
    json.dump({'autonomy_mode': 'manual'}, f)
from synlynk.scheduler import _autonomy_pass
_autonomy_pass()
print('OK: _autonomy_pass() completed without raising in a fresh empty project')
"
```

Expected output: `OK: _autonomy_pass() completed without raising in a fresh empty project` (an empty backlog/no GitHub remote means `ingest_backlog`/`triage_backlog`/`auto_promote_backlog` are each no-ops, and `manual` mode means `cmd_schedule` is never called).

- [ ] **Step 3: Open the PR**

Follow the project's PR Review Discipline (CLAUDE.md): assign a non-authoring, cross-harness+model reviewer; the reviewer's own dispatch runs `synlynk pr check` and performs the merge itself (per the 2026-10-09 RCA in CLAUDE.md's PR Review Discipline §3). Link the PR to story-6e633122/goal-8f64eff5 (100% GOVERNS adherence) and reference gh:#2262.

Also update `.synlynk/vizor-workspace-map.json` only if this PR's description ends up describing a new cross-repo relationship (it doesn't — this is entirely internal to synlynk's own daemon/scheduler/backlog modules) per the Workspace Map Update Protocol — note explicitly in the PR that this step was considered and does not apply.

---

## Execution Handoff

Per this project's Capability-Based Task Allocation (CLAUDE.md), implementation and testing are delegated to Agy/Grok/Codex via `synlynk dispatch` — this session (Claude, PM/review/deploy lane) does not execute these tasks directly. Dispatch each task above as its own `synlynk dispatch` job (same pattern already used for gh:#2261/#2263: `synlynk dispatch --role dev --story <id> --task "<task text>" <harness-hint>`), in order (Task 2 depends on Task 1's `goal_id` column data shape; Task 3 depends on Task 2's `no_goal_link` reason existing for completeness though it doesn't hard-depend on it at the code level; Task 4 depends on Task 3's `_autonomy_pass`/`_autonomy_pass_interval_seconds` existing as importable names). Task 5 (full-suite verification + PR) runs after Task 4's dispatch completes and its PR is reviewed — it is the reviewer-dispatch's own final step, not a separate dispatch.

This reconciles the generic writing-plans skill's "Subagent-Driven vs. Inline Execution" choice with the project's own dispatch-based convention: neither generic option applies here — the actual execution mechanism is `synlynk dispatch`, not a Claude-side subagent or Claude-inline execution of this plan's code changes.
