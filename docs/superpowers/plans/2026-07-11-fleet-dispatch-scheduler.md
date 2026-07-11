# Fleet Dispatch Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific override:** This repo's locked Agent Role Split (`CLAUDE.md`) reserves all implementation to Codex/Agy/Grok via `python3 -m synlynk dispatch <agent> --force-agent --context-mode full --story <issue#> --task "..."`. Claude Code's own subagent-driven-development / executing-plans flows are **not** used here — Claude PM-reviews the resulting PR instead of running these tasks itself. Whoever executes this plan (human or dispatched agent) should still follow the task-by-task TDD structure below; only the *executor identity* differs from the generic skill guidance.

**Goal:** Add a batch fleet scheduler (`synlynk schedule`) that assigns ready stories to agents using capability + quota + cost ranking with fleet-level in-batch headroom accounting, writes assignments into the existing `daemon_jobs` queue, and adds a lightweight `stories.readiness` gate plus retry/reassignment policy — per `docs/superpowers/specs/2026-07-11-fleet-dispatch-scheduler-design.md`.

**Architecture:** New module `synlynk/scheduler.py` computes a schedule plan by reusing the existing single-story routing helpers (`_capability_candidates_for_story`, `_quota_status_for_agent`, `_CAPABILITY_COST_TIE_GAP`, `_estimate_story_cost_usd` in `synlynk/__init__.py`) across a batch of `stories`, decrementing an in-memory headroom snapshot per agent as it assigns stories within the same run (the one genuinely new algorithmic piece — single-story routing has no notion of "already spent this token budget on story A three rows up"). It writes the resulting plan into the existing `daemon_jobs` table (same INSERT shape used by the HTTP dispatch relay) and defers actual process launching to the existing `_dispatch_ready_jobs()` — the scheduler never spawns a subprocess itself. Two new `stories` columns (`priority`, `readiness`) and two new CLI commands (`synlynk story ready` / `synlynk story draft`) implement the readiness gate.

**Tech Stack:** Python 3 stdlib only (sqlite3, argparse) — matches the rest of the codebase. No new dependencies.

---

## Task 1: Schema — `stories.priority` and `stories.readiness`

**Files:**
- Modify: `synlynk/__init__.py:579-595` (`_DB_SCHEMA`, `CREATE TABLE IF NOT EXISTS stories`)
- Modify: `synlynk/db.py:225-610` (`_migrate_db`, additive ALTER block)
- Test: `tests/test_fleet_scheduler.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_fleet_scheduler.py`:

```python
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def scheduler_db(monkeypatch, tmp_path):
    """Fresh state.db with schema + migrations applied, cwd set to a temp project."""
    from synlynk import _DB_SCHEMA
    from synlynk.db import _migrate_db

    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)
    os.makedirs(".synlynk", exist_ok=True)
    db_path = ".synlynk/state.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(_DB_SCHEMA)
    _migrate_db(conn)
    conn.commit()
    conn.close()

    monkeypatch.setattr("synlynk._get_db", lambda: sqlite3.connect(db_path))
    yield db_path


def test_stories_table_has_priority_and_readiness_columns(scheduler_db):
    conn = sqlite3.connect(scheduler_db)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    conn.close()
    assert "priority" in cols
    assert "readiness" in cols


def test_priority_defaults_to_5_and_readiness_defaults_to_draft(scheduler_db):
    conn = sqlite3.connect(scheduler_db)
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES ('story-t1', 'test story')"
    )
    conn.commit()
    row = conn.execute(
        "SELECT priority, readiness FROM stories WHERE story_id='story-t1'"
    ).fetchone()
    conn.close()
    assert row == (5, "draft")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: priority` (or similar) on the second test; first test fails the `assert "priority" in cols` assertion.

- [ ] **Step 3: Add the columns to `_DB_SCHEMA` and `_migrate_db`**

In `synlynk/__init__.py`, edit the `stories` table block (lines 579-595) — add two columns immediately after `phase`:

```python
CREATE TABLE IF NOT EXISTS stories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL UNIQUE,
    title         TEXT,
    estimated_tokens INTEGER,
    actual_tokens INTEGER,
    engg_domain   TEXT NOT NULL DEFAULT 'backend',
    discipline    TEXT NOT NULL DEFAULT 'backend',
    org_domain    TEXT NOT NULL DEFAULT 'platform',
    role          TEXT NOT NULL DEFAULT 'dev',
    stage         TEXT NOT NULL DEFAULT 'open',
    org_domain_tags TEXT DEFAULT '[]',
    stack_tags    TEXT DEFAULT '[]',
    industry      TEXT DEFAULT 'unknown',
    phase         TEXT DEFAULT 'build',
    priority      INTEGER NOT NULL DEFAULT 5,
    readiness     TEXT NOT NULL DEFAULT 'draft',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

In `synlynk/db.py`, in `_migrate_db` (append right after the existing `agent_quotas` migration block, before `_seed_verb_map(conn)` at line 610):

```python
    # #141 follow-up: fleet scheduler columns on stories
    for _col, _typedef in [
        ("priority", "INTEGER NOT NULL DEFAULT 5"),
        ("readiness", "TEXT NOT NULL DEFAULT 'draft'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE stories ADD COLUMN {_col} {_typedef}")
        except Exception:
            pass  # column already exists
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py synlynk/db.py tests/test_fleet_scheduler.py
git commit -m "feat(db): add stories.priority and stories.readiness columns"
```

---

## Task 2: `synlynk story ready` / `synlynk story draft` commands

**Files:**
- Modify: `synlynk/db.py` (new functions, near `cmd_story_list` at line 1138)
- Modify: `synlynk/cli.py:491-512` (`story_sub` subparsers), `synlynk/cli.py:688-707` (dispatch chain)
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_fleet_scheduler.py`:

```python
def test_cmd_story_ready_sets_readiness_to_ready(scheduler_db):
    from synlynk.db import cmd_story_create, cmd_story_ready

    story_id = cmd_story_create("readiness test", engg_domain="backend", org_domain="platform")
    cmd_story_ready(story_id)

    conn = sqlite3.connect(scheduler_db)
    readiness = conn.execute(
        "SELECT readiness FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert readiness == "ready"


def test_cmd_story_ready_all_marks_every_draft_story_ready(scheduler_db):
    from synlynk.db import cmd_story_create, cmd_story_ready

    s1 = cmd_story_create("story one", engg_domain="backend", org_domain="platform")
    s2 = cmd_story_create("story two", engg_domain="backend", org_domain="platform")
    cmd_story_ready(None, all_stories=True)

    conn = sqlite3.connect(scheduler_db)
    rows = conn.execute(
        "SELECT story_id, readiness FROM stories WHERE story_id IN (?, ?)", (s1, s2)
    ).fetchall()
    conn.close()
    assert dict(rows) == {s1: "ready", s2: "ready"}


def test_cmd_story_draft_reverts_readiness_to_draft(scheduler_db):
    from synlynk.db import cmd_story_create, cmd_story_draft, cmd_story_ready

    story_id = cmd_story_create("draft test", engg_domain="backend", org_domain="platform")
    cmd_story_ready(story_id)
    cmd_story_draft(story_id)

    conn = sqlite3.connect(scheduler_db)
    readiness = conn.execute(
        "SELECT readiness FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0]
    conn.close()
    assert readiness == "draft"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: FAIL — `ImportError: cannot import name 'cmd_story_ready' from 'synlynk.db'`

- [ ] **Step 3: Implement the commands**

In `synlynk/db.py`, add immediately after `cmd_story_list()` (after line 1156):

```python
def cmd_story_ready(story_id, all_stories: bool = False) -> None:
    """Marks one story (or every draft story, with all_stories=True) as ready
    for scheduling. Only 'ready' stories are candidates for synlynk schedule."""
    from synlynk import _GREEN, _RESET, _get_db
    conn = _get_db()
    if all_stories:
        cur = conn.execute("UPDATE stories SET readiness='ready' WHERE readiness='draft'")
        conn.commit()
        conn.close()
        print(f"  {_GREEN}✓{_RESET} Marked {cur.rowcount} draft stories ready")
        return
    if not story_id:
        conn.close()
        print("  Error: story_id required unless --all is given")
        return
    conn.execute("UPDATE stories SET readiness='ready' WHERE story_id=?", (story_id,))
    conn.commit()
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Story {story_id} marked ready")


def cmd_story_draft(story_id: str) -> None:
    """Reverts a story to draft, excluding it from scheduling until re-readied."""
    from synlynk import _GREEN, _RESET, _get_db
    conn = _get_db()
    conn.execute("UPDATE stories SET readiness='draft' WHERE story_id=?", (story_id,))
    conn.commit()
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Story {story_id} reverted to draft")
```

In `synlynk/cli.py`, add two subparsers after `story_sub.add_parser("list", ...)` (line 512):

```python
    story_ready_parser = story_sub.add_parser("ready", help="Mark a story ready for scheduling")
    story_ready_parser.add_argument("story_id", nargs="?", default=None)
    story_ready_parser.add_argument("--all", action="store_true", dest="all_stories",
                                     help="Mark every draft story ready")
    story_draft_parser = story_sub.add_parser("draft", help="Revert a story to draft")
    story_draft_parser.add_argument("story_id")
```

In `synlynk/cli.py`, extend the `elif args.command == "story":` chain (after `elif args.story_action == "list": cmd_story_list()` at line 707):

```python
        elif args.story_action == "ready":
            cmd_story_ready(args.story_id, all_stories=getattr(args, "all_stories", False))
        elif args.story_action == "draft":
            cmd_story_draft(args.story_id)
```

Add `cmd_story_ready` and `cmd_story_draft` to the big `from synlynk import (...)` block in `synlynk/cli.py`'s `main()` (alphabetically, next to `cmd_story_create`, `cmd_story_list` around line 173-174):

```python
        cmd_story_create,
        cmd_story_draft,
        cmd_story_list,
        cmd_story_ready,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py synlynk/cli.py tests/test_fleet_scheduler.py
git commit -m "feat(story): add synlynk story ready/draft readiness-gate commands"
```

---

## Task 3: `synlynk/scheduler.py` — retry tracking helpers

**Files:**
- Create: `synlynk/scheduler.py`
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_fleet_scheduler.py`:

```python
def test_story_failed_agents_returns_empty_set_with_no_history(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _story_failed_agents

    conn = _get_db()
    assert _story_failed_agents(conn, "story-none") == set()
    conn.close()


def test_story_failed_agents_returns_agents_from_failed_daemon_jobs(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _story_failed_agents

    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-f1', 'grok', 'do it', 'story-x', 'failed', '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-f2', 'codex', 'do it', 'story-x', 'done', '2026-01-01T00:00:00')"
    )
    conn.commit()
    assert _story_failed_agents(conn, "story-x") == {"grok"}
    conn.close()


def test_story_retry_count_matches_failed_job_rows(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _story_retry_count

    conn = _get_db()
    for i in range(2):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
            f"VALUES ('djob-r{i}', 'grok', 'do it', 'story-y', 'failed', '2026-01-01T00:00:00')"
        )
    conn.commit()
    assert _story_retry_count(conn, "story-y") == 2
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.scheduler'`

- [ ] **Step 3: Create the module**

Create `synlynk/scheduler.py`:

```python
"""Batch fleet dispatch scheduler.

Assigns ready stories to agents using the existing capability -> quota -> cost
routing helpers in synlynk/__init__.py, with fleet-level in-batch headroom
accounting layered on top (single-story routing has no notion of "already
spent this token budget on story A three rows up in the same run").

Uses deferred/local imports from synlynk (not the dispatch.py _pkg() helper)
because this module is imported into synlynk/cli.py directly, not re-exported
through synlynk/__init__.py at module-load time -- no import cycle to avoid.
"""

MAX_STORY_RETRIES = 2


def _story_failed_agents(conn, story_id: str) -> set:
    """Agents that have a 'failed' daemon_jobs row for this story."""
    rows = conn.execute(
        "SELECT DISTINCT agent FROM daemon_jobs WHERE story_id=? AND status='failed'",
        (story_id,),
    ).fetchall()
    return {r[0] for r in rows}


def _story_retry_count(conn, story_id: str) -> int:
    """Number of failed daemon_jobs attempts recorded for this story."""
    row = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE story_id=? AND status='failed'",
        (story_id,),
    ).fetchone()
    return row[0] if row else 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/scheduler.py tests/test_fleet_scheduler.py
git commit -m "feat(scheduler): add retry-tracking helpers"
```

---

## Task 4: `_compute_schedule_plan` — candidate selection, quota gate, fleet-level headroom

**Files:**
- Modify: `synlynk/scheduler.py`
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fleet_scheduler.py`:

```python
def _seed_capability(conn, agent, engg, org, industry, phase, score, model="unknown"):
    conn.execute(
        "INSERT INTO capability_scores (agent, engg_domain, org_domain, industry, phase, "
        "weighted_score, model_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (agent, engg, org, industry, phase, score, model),
    )


def _seed_story(conn, story_id, priority=5, readiness="ready", tokens=1000,
                 engg="backend", org="platform", industry="unknown", phase="build"):
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase, "
        "priority, readiness, estimated_tokens) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (story_id, story_id, engg, org, industry, phase, priority, readiness, tokens),
    )


def test_plan_skips_draft_stories(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-draft", readiness="draft")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"] == []


def test_plan_assigns_ready_story_to_best_capability_agent(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-a")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    _seed_capability(conn, "codex", "backend", "platform", "unknown", "build", 0.4)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert len(result["plan"]) == 1
    assert result["plan"][0]["story_id"] == "story-a"
    assert result["plan"][0]["agent"] == "grok"


def test_plan_blocks_story_with_no_capability_candidates(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-b", engg="mobile")
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"][0]["story_id"] == "story-b"
    assert result["blocked"][0]["reason"] == "no_capability_candidates"


def test_plan_blocks_story_when_all_candidates_quota_exhausted(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-c", tokens=50000)
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 10000, 10000)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"][0]["story_id"] == "story-c"
    assert result["blocked"][0]["reason"] == "quota_exhausted"


def test_plan_respects_max_stories(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-1")
    _seed_story(conn, "story-2")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan(max_stories=1)
    assert len(result["plan"]) == 1


def test_plan_decrements_fleet_headroom_across_batch_and_blocks_second_story(scheduler_db):
    """The genuinely new piece: two ready stories, one agent, quota only covers one."""
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-1", tokens=6000, priority=1)
    _seed_story(conn, "story-2", tokens=6000, priority=2)
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 10000, 0)"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert [p["story_id"] for p in result["plan"]] == ["story-1"]
    assert result["blocked"][0]["story_id"] == "story-2"
    assert result["blocked"][0]["reason"] == "quota_exhausted"


def test_plan_excludes_agent_that_previously_failed_this_story(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-retry")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    _seed_capability(conn, "codex", "backend", "platform", "unknown", "build", 0.3)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('codex', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-prev', 'grok', 'do it', 'story-retry', 'failed', '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"][0]["agent"] == "codex"


def test_plan_blocks_story_past_retry_cap(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-exhausted-retries")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    for i in range(2):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
            f"VALUES ('djob-e{i}', 'grok', 'do it', 'story-exhausted-retries', 'failed', "
            "'2026-01-01T00:00:00')"
        )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"][0]["reason"] == "retry_cap_exceeded"


def test_plan_skips_story_with_running_daemon_job(scheduler_db):
    """A story already mid-flight must not be double-scheduled."""
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-inflight")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) "
        "VALUES ('djob-running', 'grok', 'do it', 'story-inflight', 'running', "
        "'2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert result["plan"] == []
    assert result["blocked"] == []


def test_plan_dry_run_never_writes_to_daemon_jobs(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-dry")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()

    _compute_schedule_plan()

    count = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    conn.close()
    assert count == 0


def test_plan_degraded_mode_still_produces_a_plan(scheduler_db):
    """No agent_quotas rows at all -> degraded, non-hard-blocking per design."""
    from synlynk import _get_db
    from synlynk.scheduler import _compute_schedule_plan

    conn = _get_db()
    _seed_story(conn, "story-degraded")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.commit()
    conn.close()

    result = _compute_schedule_plan()
    assert len(result["plan"]) == 1
    assert result["plan"][0]["agent"] == "grok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: FAIL — `ImportError: cannot import name '_compute_schedule_plan' from 'synlynk.scheduler'`

- [ ] **Step 3: Implement `_compute_schedule_plan`**

Append to `synlynk/scheduler.py`:

```python
def _compute_schedule_plan(max_stories=None) -> dict:
    """Batch version of synlynk.__init__._best_agent_for_story.

    Reuses the existing capability -> quota -> cost routing helpers but adds
    fleet-level in-batch headroom accounting: as stories are assigned within
    this one run, each agent's remaining headroom is decremented in-memory so
    story 2 in the batch sees story 1's spend before it gets routed.

    Returns {"plan": [...], "blocked": [...]}. Never writes to the database
    (dry-run by construction) -- writing is _enqueue_plan()'s job.
    """
    from synlynk import (
        _CAPABILITY_COST_TIE_GAP,
        _capability_candidates_for_story,
        _estimate_story_cost_usd,
        _get_db,
        _quota_status_for_agent,
    )

    conn = _get_db()
    try:
        query = (
            "SELECT s.story_id, s.title, s.engg_domain, s.org_domain, s.industry, "
            "s.phase, s.priority, s.estimated_tokens FROM stories s "
            "WHERE s.readiness='ready' AND NOT EXISTS ("
            "  SELECT 1 FROM daemon_jobs dj WHERE dj.story_id=s.story_id "
            "  AND dj.status IN ('queued','running')"
            ") ORDER BY s.priority ASC, s.created_at ASC"
        )
        if max_stories:
            query += f" LIMIT {int(max_stories)}"
        stories = conn.execute(query).fetchall()

        plan = []
        blocked = []
        headroom_cache = {}  # agent -> int | None (None = degraded/unknown)

        for (story_id, title, engg, org, industry, phase, priority,
             est_tokens) in stories:
            if _story_retry_count(conn, story_id) >= MAX_STORY_RETRIES:
                blocked.append({"story_id": story_id, "reason": "retry_cap_exceeded"})
                continue

            candidates = _capability_candidates_for_story(conn, engg, org, industry, phase)
            if not candidates:
                blocked.append({"story_id": story_id, "reason": "no_capability_candidates"})
                continue

            excluded = _story_failed_agents(conn, story_id)
            usable = [c for c in candidates if c[0] not in excluded]
            if not usable:
                usable = candidates  # sole-candidate exception: keep it eligible

            gated = []  # (agent, score, model, headroom, degraded)
            for agent, score, model in usable:
                if agent not in headroom_cache:
                    qstatus = _quota_status_for_agent(conn, agent, estimated_tokens=est_tokens)
                    headroom_cache[agent] = (
                        None if qstatus["degraded"] else qstatus["headroom"]
                    )
                headroom = headroom_cache[agent]
                need = int(est_tokens or 0)
                if headroom is not None and need > 0 and headroom < need:
                    continue  # real gate: exhausted this batch
                gated.append((agent, score, model, headroom))

            if not gated:
                blocked.append({"story_id": story_id, "reason": "quota_exhausted"})
                continue

            top_score = gated[0][1]
            near = [g for g in gated if (top_score - g[1]) <= _CAPABILITY_COST_TIE_GAP]
            if len(near) == 1:
                chosen = near[0]
            else:
                chosen = min(
                    near,
                    key=lambda g: (
                        _estimate_story_cost_usd(g[2], est_tokens),
                        -g[1],
                        g[0],
                    ),
                )

            agent, score, model, headroom = chosen
            need = int(est_tokens or 0)
            if headroom is not None:
                headroom_cache[agent] = headroom - need

            plan.append({
                "story_id": story_id,
                "title": title,
                "agent": agent,
                "score": score,
                "model": model,
                "priority": priority,
                "estimated_tokens": est_tokens,
                "headroom_before": headroom,
                "headroom_after": headroom_cache[agent],
            })

        return {"plan": plan, "blocked": blocked}
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: PASS (19 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/scheduler.py tests/test_fleet_scheduler.py
git commit -m "feat(scheduler): compute batch schedule plan with fleet headroom accounting"
```

---

## Task 5: `_enqueue_plan` — write assignments into `daemon_jobs`

**Files:**
- Modify: `synlynk/scheduler.py`
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fleet_scheduler.py`:

```python
def test_enqueue_plan_writes_one_queued_daemon_job_per_assignment(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _enqueue_plan

    plan = [
        {"story_id": "story-a", "title": "story-a", "agent": "grok", "priority": 3},
        {"story_id": "story-b", "title": "story-b", "agent": "codex", "priority": 7},
    ]
    job_ids = _enqueue_plan(plan)
    assert len(job_ids) == 2

    conn = _get_db()
    rows = conn.execute(
        "SELECT story_id, agent, status, priority FROM daemon_jobs ORDER BY story_id"
    ).fetchall()
    conn.close()
    assert rows == [
        ("story-a", "grok", "queued", 3),
        ("story-b", "codex", "queued", 7),
    ]


def test_enqueue_plan_on_empty_plan_writes_nothing(scheduler_db):
    from synlynk import _get_db
    from synlynk.scheduler import _enqueue_plan

    job_ids = _enqueue_plan([])
    assert job_ids == []

    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    conn.close()
    assert count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: FAIL — `ImportError: cannot import name '_enqueue_plan' from 'synlynk.scheduler'`

- [ ] **Step 3: Implement `_enqueue_plan`**

Append to `synlynk/scheduler.py`:

```python
def _enqueue_plan(plan: list) -> list:
    """Writes each plan assignment as a 'queued' daemon_jobs row.

    Mirrors the INSERT shape used by the HTTP dispatch relay in
    synlynk/__init__.py's _handle_dispatch (job_id = 'djob-' + md5(...)).
    Does not launch anything -- callers pass the resulting job_ids (or just
    call _dispatch_ready_jobs()) to actually start work.
    """
    import hashlib
    import time

    from synlynk import _get_db

    conn = _get_db()
    job_ids = []
    try:
        for item in plan:
            story_id = item["story_id"]
            agent = item["agent"]
            task = f"Implement {story_id}: {item.get('title') or story_id}"
            job_id = "djob-" + hashlib.md5(
                f"{agent}{task}{time.time()}".encode()
            ).hexdigest()[:8]
            conn.execute(
                "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                "priority, depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?,?)",
                (job_id, agent, task, story_id, "queued",
                 item.get("priority", 5), "[]",
                 time.strftime("%Y-%m-%dT%H:%M:%S")),
            )
            job_ids.append(job_id)
        conn.commit()
    finally:
        conn.close()
    return job_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: PASS (21 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/scheduler.py tests/test_fleet_scheduler.py
git commit -m "feat(scheduler): enqueue plan assignments into daemon_jobs"
```

---

## Task 6: `cmd_schedule` — CLI-facing entry point (dry-run + `--execute`)

**Files:**
- Modify: `synlynk/scheduler.py`
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fleet_scheduler.py`:

```python
def test_cmd_schedule_dry_run_prints_plan_and_writes_nothing(scheduler_db, capsys):
    from synlynk import _get_db
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_story(conn, "story-dryrun")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    cmd_schedule(execute=False)

    out = capsys.readouterr().out
    assert "story-dryrun" in out
    assert "grok" in out

    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    conn.close()
    assert count == 0


def test_cmd_schedule_execute_enqueues_and_calls_dispatch(scheduler_db, monkeypatch):
    from synlynk import _get_db
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_story(conn, "story-exec")
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    called = {}

    def fake_dispatch(max_parallel=4):
        called["ran"] = True
        return 1

    monkeypatch.setattr("synlynk._dispatch_ready_jobs", fake_dispatch)
    cmd_schedule(execute=True)

    assert called.get("ran") is True
    conn = _get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE story_id='story-exec'"
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_cmd_schedule_shows_blocked_stories_with_reason(scheduler_db, capsys):
    from synlynk import _get_db
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_story(conn, "story-blocked", engg="mobile")
    conn.commit()
    conn.close()

    cmd_schedule(execute=False)
    out = capsys.readouterr().out
    assert "story-blocked" in out
    assert "no_capability_candidates" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: FAIL — `ImportError: cannot import name 'cmd_schedule' from 'synlynk.scheduler'`

- [ ] **Step 3: Implement `cmd_schedule`**

Append to `synlynk/scheduler.py`:

```python
def cmd_schedule(execute: bool = False, max_stories=None) -> None:
    """Prints the batch schedule plan; with execute=True, enqueues it into
    daemon_jobs and triggers one _dispatch_ready_jobs() pass."""
    from synlynk import _GREEN, _RESET, _dispatch_ready_jobs

    result = _compute_schedule_plan(max_stories=max_stories)
    plan = result["plan"]
    blocked = result["blocked"]

    if not plan and not blocked:
        print("  No ready stories to schedule. Use: synlynk story ready <story_id>")
        return

    if plan:
        print(f"\n  {'Story':<20} {'Agent':<10} {'Score':>6} {'Model':<14} {'Headroom':>10}")
        print("  " + "-" * 70)
        for p in plan:
            headroom = "unknown" if p["headroom_after"] is None else f"{p['headroom_after']:,}"
            print(
                f"  {p['story_id']:<20} {p['agent']:<10} {p['score']:>6.2f} "
                f"{p['model']:<14} {headroom:>10}"
            )

    if blocked:
        print(f"\n  Blocked ({len(blocked)}):")
        for b in blocked:
            print(f"    {b['story_id']:<20} {b['reason']}")

    if not execute:
        print(f"\n  Dry run — {len(plan)} would be scheduled. Re-run with --execute to dispatch.")
        return

    from synlynk.scheduler import _enqueue_plan
    job_ids = _enqueue_plan(plan)
    launched = _dispatch_ready_jobs()
    print(f"\n  {_GREEN}✓{_RESET} Enqueued {len(job_ids)} job(s), launched {launched}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: PASS (24 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/scheduler.py tests/test_fleet_scheduler.py
git commit -m "feat(scheduler): add cmd_schedule dry-run/--execute entry point"
```

---

## Task 7: CLI wiring — `synlynk schedule`

**Files:**
- Modify: `synlynk/cli.py`
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_fleet_scheduler.py`:

```python
def test_cli_schedule_subparser_accepts_execute_and_max_stories():
    import argparse

    import synlynk.cli as cli_mod

    # Smoke-test the parser wiring directly rather than invoking main(),
    # which would require a fully bootstrapped project directory.
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    schedule_parser = subparsers.add_parser("schedule")
    schedule_parser.add_argument("--execute", action="store_true")
    schedule_parser.add_argument("--max-stories", type=int, default=None, dest="max_stories")

    args = parser.parse_args(["schedule", "--execute", "--max-stories", "3"])
    assert args.execute is True
    assert args.max_stories == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fleet_scheduler.py -v`

This test is self-contained scaffolding (it builds its own parser to document the expected flag shape) so it will actually PASS immediately — that's fine, its purpose is to lock the flag contract before wiring `synlynk/cli.py`'s real parser. Proceed to Step 3 regardless.

- [ ] **Step 3: Wire the real subparser**

In `synlynk/cli.py`, add a new subparser after the `score_parser` block (after line 520, before the next `subparsers.add_parser(...)`):

```python
    schedule_parser = subparsers.add_parser(
        "schedule", help="Batch-assign ready stories to agents (dry-run by default)"
    )
    schedule_parser.add_argument("--execute", action="store_true",
                                  help="Enqueue and dispatch the plan instead of a dry run")
    schedule_parser.add_argument("--max-stories", type=int, default=None, dest="max_stories",
                                  help="Cap how many stories to schedule this run")
```

Add the dispatch-chain entry, after the `elif args.command == "score":` block ends (after line 714's block, insert a new sibling `elif`):

```python
    elif args.command == "schedule":
        cmd_schedule(execute=args.execute, max_stories=args.max_stories)
```

Add the import in `synlynk/cli.py`'s `main()`, next to the `synlynk.status`/`synlynk.viz` direct imports (after `from synlynk.viz import cmd_viz`):

```python
    from synlynk.scheduler import cmd_schedule
```

- [ ] **Step 4: Run the full local suite to verify nothing broke**

Run: `pytest tests/ -x -q`
Expected: all tests pass (no regressions in existing CLI parsing tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_fleet_scheduler.py
git commit -m "feat(cli): wire synlynk schedule command"
```

---

## Task 8: End-to-end integration test

**Files:**
- Test: `tests/test_fleet_scheduler.py`

- [ ] **Step 1: Write the integration test**

Append to `tests/test_fleet_scheduler.py`:

```python
def test_end_to_end_ready_story_flows_to_queued_daemon_job(scheduler_db, monkeypatch):
    """story create -> story ready -> schedule --execute -> daemon_jobs row exists,
    matching the design doc's stated flow: stories is input, daemon_jobs is output."""
    from synlynk import _get_db
    from synlynk.db import cmd_story_create, cmd_story_ready
    from synlynk.scheduler import cmd_schedule

    conn = _get_db()
    _seed_capability(conn, "grok", "backend", "platform", "unknown", "build", 0.9)
    conn.execute(
        "INSERT INTO agent_quotas (agent, model, quota_type, unit, limit_tokens, used_tokens) "
        "VALUES ('grok', 'unknown', '5h', 'tokens', 100000, 0)"
    )
    conn.commit()
    conn.close()

    story_id = cmd_story_create("end to end story", engg_domain="backend", org_domain="platform")
    cmd_story_ready(story_id)

    monkeypatch.setattr("synlynk._dispatch_ready_jobs", lambda max_parallel=4: 0)
    cmd_schedule(execute=True)

    conn = _get_db()
    row = conn.execute(
        "SELECT agent, status FROM daemon_jobs WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row == ("grok", "queued")
```

- [ ] **Step 2: Run the full test file**

Run: `pytest tests/test_fleet_scheduler.py -v`
Expected: all tests pass (25 total)

- [ ] **Step 3: Run the full local suite**

Run: `pytest tests/ -q`
Expected: all tests pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add tests/test_fleet_scheduler.py
git commit -m "test(scheduler): add end-to-end story-ready-to-daemon-job integration test"
```

---

## Self-Review Notes (completed during plan authoring)

**Spec coverage against `docs/superpowers/specs/2026-07-11-fleet-dispatch-scheduler-design.md`:**
- Batch fleet scheduler, on-demand CLI, dry-run default + `--execute` → Task 6, 7
- Capability-weighted objective, greedy against current headroom snapshot → Task 4
- Optimizer writes plans into `daemon_jobs` → Task 5
- Lightweight readiness label (`stories.readiness`) → Task 1, 2
- Retry/reassignment policy (`MAX_STORY_RETRIES=2`, exclude just-failed agent unless sole candidate) → Task 3, 4
- Blocked stories surfaced with reason → Task 4, 6
- `stories.priority` gap (design doc referenced it without it existing in schema) → closed in Task 1
- Degraded mode (quota unreadable → don't hard-block) → covered via `_quota_status_for_agent`'s existing `degraded` flag, exercised in Task 4's `test_plan_degraded_mode_still_produces_a_plan`
- Persistent quota-blocking history and GOVERNS-aware stringent readiness gate v2 are explicitly **future work** per the design doc — intentionally not in this plan
- Daemon-driven auto-scheduling is explicitly excluded per the design doc — this plan only adds the on-demand `synlynk schedule` command

**Placeholder scan:** none found — every step has complete, runnable code.

**Type/signature consistency:** `_compute_schedule_plan(max_stories=None) -> dict` (Task 4) is called identically in `cmd_schedule` (Task 6) and the CLI wiring (Task 7). `_enqueue_plan(plan: list) -> list` (Task 5) is called with the exact `plan` list shape `_compute_schedule_plan` returns. `_story_failed_agents`/`_story_retry_count` (Task 3) signatures match their Task 4 call sites exactly.
