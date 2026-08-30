# GOVERNS Backlog Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give synlynk a way to file discovered/planned work to the backlog with correct GOVERNS association (GitHub sub-issue of a tracking issue, plus a linked `stories`/`goals` row), reachable two ways: an explicit `synlynk backlog note` command an agent calls live in-session, and a `synlynk backlog scan-session` command that surfaces session-close material for a human-confirmed safety-net pass.

**Architecture:** New module `synlynk/backlog_automation.py` holds dedup, goal-resolution, and filing logic, reusing existing `cmd_goal_create`/`cmd_goal_link` (`synlynk/db.py`) rather than reinventing goal linkage. A new `backlog_proposals` ledger table (sibling to the existing `autopilot_runs` table in `synlynk/support_engineer.py`) records every proposal — filed or declined — keyed by a content hash, so a declined idea isn't re-proposed indefinitely. Two new `synlynk backlog <note|scan-session>` CLI subcommands wire it up. See `docs/superpowers/specs/2026-08-29-governs-backlog-automation-design.md` for the full design rationale.

**Tech Stack:** Python stdlib + `gh` CLI via `subprocess` (matches `synlynk/support_engineer.py`'s `_file_gh_issue` pattern). No new dependencies.

**Non-goals (do not touch):** `support_engineer.py`'s existing `test_suite`/`sentinel_alerts` collectors or `_attempt_fix` flow; no UI for reviewing `backlog_proposals` (query it with `gh issue list` / direct SQL); no backfill of pre-existing discovered work (e.g. #1264/#1263); no `--dry-run` flag on `synlynk backlog note` — `scan-session` already gives a preview step for the confirm-gated path, and the marker path's whole premise is that calling it *is* the deliberate act, so a dry-run mode would just add a second way to do what `scan-session` already does.

**Resolving the spec's open items:** dedup threshold is exact match on normalized title against `gh search_issues` results (see `file_backlog_item`, Task 3) rather than a fuzzy score — offloads relevance ranking to GitHub's own search, and exact-match keeps false-positive blocking of legitimately-different work near zero; no archetype config is needed since the session-close path is a standalone CLI command, not a `cmd_agent_run` collector (see spec's "Prior art" section, revised).

---

### Task 1: `backlog_proposals` ledger table

**Files:**
- Modify: `synlynk/__init__.py` (`_DB_SCHEMA` string, ~line 1037, immediately after the `goal_contributions` table)
- Modify: `synlynk/db.py:100` (`_DB_MIGRATION_VERSION`)
- Test: `tests/test_backlog_automation.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_backlog_automation.py`:

```python
import os
import sqlite3

import pytest


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    from synlynk import _get_db
    conn = _get_db()
    yield conn
    conn.close()


def test_backlog_proposals_table_exists(db_conn):
    cols = {row[1] for row in db_conn.execute("PRAGMA table_info(backlog_proposals)")}
    assert cols == {
        "id", "signal_hash", "title", "source", "status",
        "gh_issue_url", "story_id", "goal_id", "goal_match_basis",
        "session_id", "ts",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such table: backlog_proposals` (or an empty `cols` set / assertion mismatch).

- [ ] **Step 3: Add the table to `_DB_SCHEMA`**

In `synlynk/__init__.py`, find the `goal_contributions` table definition (it ends with `UNIQUE(goal_id, story_id)\n);`). Immediately after it, insert:

```sql

CREATE TABLE IF NOT EXISTS backlog_proposals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_hash      TEXT NOT NULL,
    title            TEXT NOT NULL,
    source           TEXT NOT NULL,
    status           TEXT NOT NULL,
    gh_issue_url     TEXT,
    story_id         TEXT,
    goal_id          TEXT,
    goal_match_basis TEXT,
    session_id       TEXT,
    ts               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_backlog_proposals_hash ON backlog_proposals(signal_hash);
```

- [ ] **Step 4: Bump the migration version**

In `synlynk/db.py:100`, change:

```python
_DB_MIGRATION_VERSION = 2
```

to:

```python
_DB_MIGRATION_VERSION = 3
```

This forces `_migrate_db` to re-run `conn.executescript(_DB_SCHEMA)` (idempotent — every statement is `CREATE TABLE IF NOT EXISTS`) against existing installs, so the new table appears without a hand-written `ALTER TABLE` block.

- [ ] **Step 5: Run test to verify it passes**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py synlynk/db.py tests/test_backlog_automation.py
git commit -m "feat: add backlog_proposals ledger table (#1203)"
```

---

### Task 2: Dedup helpers

**Files:**
- Create: `synlynk/backlog_automation.py`
- Test: `tests/test_backlog_automation.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_backlog_automation.py`:

```python
from unittest.mock import MagicMock, patch


def test_compute_signal_hash_is_stable_and_source_sensitive():
    from synlynk.backlog_automation import compute_signal_hash
    h1 = compute_signal_hash("Fix the flaky retry test", "marker")
    h2 = compute_signal_hash("fix the FLAKY retry test", "marker")
    h3 = compute_signal_hash("Fix the flaky retry test", "session_close")
    assert h1 == h2  # normalized (case/whitespace insensitive)
    assert h1 != h3  # source is part of the hash


def test_has_ledger_duplicate_true_after_insert(db_conn):
    from synlynk.backlog_automation import compute_signal_hash, has_ledger_duplicate, record_proposal
    h = compute_signal_hash("Some discovered thing", "marker")
    assert has_ledger_duplicate(db_conn, h) is False
    record_proposal(
        db_conn, signal_hash=h, title="Some discovered thing", source="marker",
        status="declined", gh_issue_url=None, story_id=None, goal_id=None,
        goal_match_basis=None, session_id=None,
    )
    assert has_ledger_duplicate(db_conn, h) is True


def test_search_similar_issues_parses_gh_output():
    from synlynk.backlog_automation import search_similar_issues
    fake_result = MagicMock(returncode=0, stdout='[{"title": "Fix the flaky retry test", "url": "https://github.com/x/y/issues/42"}]')
    with patch("subprocess.run", return_value=fake_result) as mock_run:
        hits = search_similar_issues("Fix flaky retry test")
    assert hits == [{"title": "Fix the flaky retry test", "url": "https://github.com/x/y/issues/42"}]
    args = mock_run.call_args[0][0]
    assert args[:3] == ["gh", "issue", "list"]


def test_search_similar_issues_empty_on_gh_failure():
    from synlynk.backlog_automation import search_similar_issues
    fake_result = MagicMock(returncode=1, stdout="", stderr="rate limited")
    with patch("subprocess.run", return_value=fake_result):
        assert search_similar_issues("anything") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.backlog_automation'`

- [ ] **Step 3: Write `synlynk/backlog_automation.py`**

```python
"""GOVERNS backlog automation: dedup, goal resolution, and filing for
discovered/planned work. See docs/superpowers/specs/2026-08-29-governs-backlog-automation-design.md.
"""

import hashlib
import json
import re
import subprocess


def compute_signal_hash(title: str, source: str) -> str:
    """Stable hash of a normalized title + source, used as the dedup key."""
    normalized = re.sub(r"\s+", " ", title.strip().lower())
    return hashlib.md5(f"{source}:{normalized}".encode()).hexdigest()[:16]


def has_ledger_duplicate(conn, signal_hash: str) -> bool:
    """True if signal_hash already has a backlog_proposals row (filed or declined)."""
    row = conn.execute(
        "SELECT 1 FROM backlog_proposals WHERE signal_hash=? LIMIT 1", (signal_hash,)
    ).fetchone()
    return row is not None


def record_proposal(conn, signal_hash: str, title: str, source: str, status: str,
                     gh_issue_url, story_id, goal_id, goal_match_basis, session_id) -> None:
    """Insert a backlog_proposals ledger row. Caller commits."""
    conn.execute(
        "INSERT INTO backlog_proposals "
        "(signal_hash, title, source, status, gh_issue_url, story_id, goal_id, goal_match_basis, session_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal_hash, title, source, status, gh_issue_url, story_id, goal_id, goal_match_basis, session_id),
    )
    conn.commit()


def search_similar_issues(title: str) -> list:
    """Search open+closed GitHub issues for similar titles via `gh issue list --search`.

    Returns a list of {"title": ..., "url": ...} dicts, or [] on any gh failure.
    """
    result = subprocess.run(
        ["gh", "issue", "list", "--search", title, "--state", "all",
         "--json", "title,url", "--limit", "10"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/backlog_automation.py tests/test_backlog_automation.py
git commit -m "feat: add backlog dedup helpers (#1203)"
```

---

### Task 3: Goal resolution + filing

**Files:**
- Modify: `synlynk/backlog_automation.py`
- Test: `tests/test_backlog_automation.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_backlog_automation.py`:

```python
def test_resolve_goal_uses_explicit_goal_id(db_conn):
    from synlynk.db import cmd_goal_create
    from synlynk.backlog_automation import resolve_goal
    goal_id = cmd_goal_create("Ship X", "X is shipped", role="pm")
    resolved_id, basis = resolve_goal(db_conn, goal_id=goal_id)
    assert resolved_id == goal_id
    assert "explicit" in basis


def test_resolve_goal_creates_new_goal_when_requested(db_conn):
    from synlynk.backlog_automation import resolve_goal
    resolved_id, basis = resolve_goal(
        db_conn, new_goal_outcome="Backlog stays current",
        new_goal_criterion="No discovered work sits unfiled for >1 session",
    )
    row = db_conn.execute("SELECT outcome FROM goals WHERE goal_id=?", (resolved_id,)).fetchone()
    assert row[0] == "Backlog stays current"
    assert "new goal created" in basis


def test_resolve_goal_returns_none_when_nothing_given(db_conn):
    from synlynk.backlog_automation import resolve_goal
    resolved_id, basis = resolve_goal(db_conn)
    assert resolved_id is None
    assert "no goal" in basis


def test_file_backlog_item_happy_path(db_conn):
    from synlynk.backlog_automation import file_backlog_item
    from synlynk.db import cmd_goal_create

    goal_id = cmd_goal_create("Ship X", "X is shipped", role="pm")

    search_result = MagicMock(returncode=0, stdout="[]", stderr="")
    create_result = MagicMock(returncode=0, stdout="https://github.com/nikhilsoman/synlynk/issues/9001\n", stderr="")
    repo_result = MagicMock(returncode=0, stdout="nikhilsoman/synlynk\n", stderr="")
    view_result = MagicMock(returncode=0, stdout="555", stderr="")
    subissue_result = MagicMock(returncode=0, stdout="{}", stderr="")

    # Call order matches file_backlog_item -> search_similar_issues, then
    # _create_github_issue's internal sequence: create, repo_view, id_view, sub_issue_post.
    with patch("subprocess.run", side_effect=[search_result, create_result, repo_result, view_result, subissue_result]):
        outcome = file_backlog_item(
            db_conn, title="Investigate flaky test", body="details here",
            source="marker", goal_id=goal_id, parent_issue=1198,
        )

    assert outcome["status"] == "filed"
    assert outcome["gh_issue_url"] == "https://github.com/nikhilsoman/synlynk/issues/9001"
    story = db_conn.execute(
        "SELECT title, goal_id FROM stories WHERE story_id=?", (outcome["story_id"],)
    ).fetchone()
    assert story == ("Investigate flaky test", goal_id)
    ledger_row = db_conn.execute(
        "SELECT status, gh_issue_url, story_id FROM backlog_proposals WHERE story_id=?",
        (outcome["story_id"],),
    ).fetchone()
    assert ledger_row == ("filed", outcome["gh_issue_url"], outcome["story_id"])


def test_file_backlog_item_skips_ledger_duplicate(db_conn):
    from synlynk.backlog_automation import file_backlog_item, compute_signal_hash, record_proposal
    h = compute_signal_hash("Already proposed thing", "marker")
    record_proposal(db_conn, signal_hash=h, title="Already proposed thing", source="marker",
                     status="declined", gh_issue_url=None, story_id=None, goal_id=None,
                     goal_match_basis=None, session_id=None)
    with patch("subprocess.run") as mock_run:
        outcome = file_backlog_item(db_conn, title="Already proposed thing", body="x", source="marker")
    assert outcome["status"] == "skipped_duplicate"
    mock_run.assert_not_called()


def test_file_backlog_item_skips_gh_title_duplicate(db_conn):
    from synlynk.backlog_automation import file_backlog_item
    search_result = MagicMock(
        returncode=0,
        stdout='[{"title": "Investigate flaky test", "url": "https://github.com/x/y/issues/42"}]',
        stderr="",
    )
    with patch("subprocess.run", return_value=search_result) as mock_run:
        outcome = file_backlog_item(db_conn, title="Investigate flaky test", body="x", source="marker")
    assert outcome["status"] == "skipped_duplicate_gh"
    assert outcome["gh_issue_url"] == "https://github.com/x/y/issues/42"
    # only the search call — no issue was created
    assert mock_run.call_count == 1
    assert mock_run.call_args[0][0][:3] == ["gh", "issue", "list"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_goal'` (and `file_backlog_item`)

- [ ] **Step 3: Add `resolve_goal` and `file_backlog_item`**

Append to `synlynk/backlog_automation.py`:

```python
def resolve_goal(conn, goal_id: str = None, new_goal_outcome: str = None,
                  new_goal_criterion: str = None) -> tuple:
    """Resolve which goal a story should link to.

    Priority: explicit goal_id > create-new (outcome+criterion given) > no goal.
    The caller (an interactive agent) has already done any "which goal fits best"
    reasoning before calling this — this function only executes the decision.
    Returns (goal_id_or_None, basis_string).
    """
    from synlynk.db import cmd_goal_create

    if goal_id:
        row = conn.execute("SELECT goal_id FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
        if row:
            return goal_id, f"explicit goal_id passed: {goal_id}"
        return None, f"no goal: explicit goal_id {goal_id!r} not found in goals table"

    if new_goal_outcome and new_goal_criterion:
        new_id = cmd_goal_create(new_goal_outcome, new_goal_criterion, role="pm")
        return new_id, f"new goal created: no existing goal matched ({new_goal_outcome!r})"

    return None, "no goal: no goal_id, session goal, or new-goal outcome/criterion given"


def _repo_slug() -> str:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _create_github_issue(title: str, body: str, parent_issue, labels: str) -> str:
    """Create the issue, then register it as a GitHub sub-issue of parent_issue.
    Returns the new issue's URL, or '' on failure.
    """
    result = subprocess.run(
        ["gh", "issue", "create", "--title", title, "--body", body, "--label", labels],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return ""
    issue_url = result.stdout.strip()
    if not parent_issue:
        return issue_url

    issue_number = issue_url.rstrip("/").rsplit("/", 1)[-1]
    repo = _repo_slug()
    if not repo:
        return issue_url

    view_result = subprocess.run(
        ["gh", "api", f"repos/{repo}/issues/{issue_number}", "--jq", ".id"],
        capture_output=True, text=True,
    )
    if view_result.returncode != 0 or not view_result.stdout.strip():
        return issue_url
    child_db_id = view_result.stdout.strip()

    subprocess.run(
        ["gh", "api", f"repos/{repo}/issues/{parent_issue}/sub_issues",
         "-X", "POST", "-f", f"sub_issue_id={child_db_id}"],
        capture_output=True, text=True,
    )
    return issue_url


def file_backlog_item(conn, title: str, body: str, source: str, session_id: str = None,
                       goal_id: str = None, new_goal_outcome: str = None,
                       new_goal_criterion: str = None, parent_issue=1198,
                       labels: str = "enhancement") -> dict:
    """Dedup (local ledger, then GitHub title search), resolve goal, file the GitHub
    issue + story + ledger row.

    Returns {"status": "filed"|"skipped_duplicate"|"skipped_duplicate_gh",
             "gh_issue_url": str|None, "story_id": str|None}.
    """
    signal_hash = compute_signal_hash(title, source)
    if has_ledger_duplicate(conn, signal_hash):
        return {"status": "skipped_duplicate", "gh_issue_url": None, "story_id": None}

    normalized_title = re.sub(r"\s+", " ", title.strip().lower())
    for hit in search_similar_issues(title):
        hit_title = re.sub(r"\s+", " ", hit.get("title", "").strip().lower())
        if hit_title == normalized_title:
            return {"status": "skipped_duplicate_gh", "gh_issue_url": hit.get("url"), "story_id": None}

    resolved_goal_id, basis = resolve_goal(
        conn, goal_id=goal_id, new_goal_outcome=new_goal_outcome, new_goal_criterion=new_goal_criterion
    )

    gh_issue_url = _create_github_issue(title, body, parent_issue, labels)

    story_id = "backlog-" + hashlib.md5(f"{signal_hash}{gh_issue_url}".encode()).hexdigest()[:8]
    conn.execute(
        "INSERT OR IGNORE INTO stories (story_id, title, goal_id) VALUES (?, ?, ?)",
        (story_id, title[:100], resolved_goal_id),
    )
    conn.commit()

    record_proposal(
        conn, signal_hash=signal_hash, title=title, source=source, status="filed",
        gh_issue_url=gh_issue_url or None, story_id=story_id, goal_id=resolved_goal_id,
        goal_match_basis=basis, session_id=session_id,
    )
    return {"status": "filed", "gh_issue_url": gh_issue_url or None, "story_id": story_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/backlog_automation.py tests/test_backlog_automation.py
git commit -m "feat: add goal resolution and filing to backlog automation (#1203)"
```

---

### Task 4: CLI wiring — `synlynk backlog note` and `synlynk backlog scan-session`

**Files:**
- Modify: `synlynk/cli.py` (add `backlog` subparser near the `events` subparser added at `synlynk/cli.py:440`)
- Modify: `synlynk/backlog_automation.py` (add `collect_session_material` + CLI entrypoints)
- Test: `tests/test_backlog_automation.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_backlog_automation.py`:

```python
def test_collect_session_material_reads_closing_summary(db_conn, tmp_path, monkeypatch):
    from synlynk.backlog_automation import collect_session_material
    db_conn.execute(
        "INSERT INTO sessions (session_id, title, status, opened_at, closing_summary) "
        "VALUES (?, ?, 'closed', '2026-08-29T10:00:00', ?)",
        ("sess-1", "Test session", "Shipped X, discovered Y needs follow-up"),
    )
    db_conn.commit()
    material = collect_session_material(db_conn, "sess-1")
    assert material["closing_summary"] == "Shipped X, discovered Y needs follow-up"
    assert material["session_id"] == "sess-1"


def test_collect_session_material_missing_session(db_conn):
    from synlynk.backlog_automation import collect_session_material
    material = collect_session_material(db_conn, "does-not-exist")
    assert material is None


def test_cli_backlog_note_invokes_file_backlog_item(db_conn, capsys):
    from synlynk import cli
    with patch("synlynk.backlog_automation.file_backlog_item") as mock_file:
        mock_file.return_value = {"status": "filed", "gh_issue_url": "https://x/9001", "story_id": "backlog-abc"}
        cli.main(["backlog", "note", "Found a gap", "--body", "details"])
    mock_file.assert_called_once()
    _, kwargs = mock_file.call_args
    assert kwargs["title"] == "Found a gap"
    assert kwargs["body"] == "details"
    assert kwargs["source"] == "marker"
    out = capsys.readouterr().out
    assert "filed" in out
    assert "https://x/9001" in out


def test_cli_backlog_scan_session_prints_material(db_conn, capsys):
    from synlynk import cli
    db_conn.execute(
        "INSERT INTO sessions (session_id, title, status, opened_at, closing_summary) "
        "VALUES (?, ?, 'closed', '2026-08-29T10:00:00', ?)",
        ("sess-2", "Another session", "Nothing notable"),
    )
    db_conn.commit()
    cli.main(["backlog", "scan-session", "--session-id", "sess-2"])
    out = capsys.readouterr().out
    assert "Nothing notable" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_session_material'`, then (after that's added) `SystemExit`/`argparse` errors for the unrecognized `backlog` subcommand.

- [ ] **Step 3: Add `collect_session_material` and CLI entrypoints to `backlog_automation.py`**

Append to `synlynk/backlog_automation.py`:

```python
def collect_session_material(conn, session_id: str) -> dict:
    """Read raw material for a closed session: closing_summary plus a devlog tail.
    Returns None if the session doesn't exist. Deterministic data-gathering only —
    classifying this material into backlog candidates is the calling agent's job.
    """
    row = conn.execute(
        "SELECT session_id, title, closing_summary FROM sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None

    devlog_tail = ""
    devlog_user = subprocess.run(
        ["git", "config", "user.name"], capture_output=True, text=True
    ).stdout.strip()
    if devlog_user:
        devlog_path = f"project-docs/devlogs/{devlog_user}.md"
        try:
            with open(devlog_path) as f:
                content = f.read()
            devlog_tail = content[-2000:]
        except OSError:
            devlog_tail = ""

    return {
        "session_id": row[0],
        "title": row[1],
        "closing_summary": row[2] or "",
        "devlog_tail": devlog_tail,
    }


def cmd_backlog_note(title: str, body: str, source: str = "marker", session_id: str = None,
                      goal_id: str = None, new_goal_outcome: str = None,
                      new_goal_criterion: str = None, parent_issue=1198) -> None:
    """CLI entrypoint for the explicit-marker path. Files immediately (no confirm gate) —
    calling this command is itself the deliberate act.
    """
    from synlynk import _get_db
    conn = _get_db()
    try:
        outcome = file_backlog_item(
            conn, title=title, body=body, source=source, session_id=session_id,
            goal_id=goal_id, new_goal_outcome=new_goal_outcome,
            new_goal_criterion=new_goal_criterion, parent_issue=parent_issue,
        )
    finally:
        conn.close()

    if outcome["status"] == "skipped_duplicate":
        print(f"  [backlog] skipped — already proposed: {title!r}")
        return
    if outcome["status"] == "skipped_duplicate_gh":
        print(f"  [backlog] skipped — matches existing GitHub issue: {outcome['gh_issue_url']}")
        return
    print(f"  [backlog] filed: {outcome['gh_issue_url']}  (story: {outcome['story_id']})")


def cmd_backlog_scan_session(session_id: str) -> None:
    """CLI entrypoint for the session-close safety net. Prints raw material for the
    calling agent to read and classify — filing candidates is a separate
    `synlynk backlog note` call per confirmed item, not automatic.
    """
    from synlynk import _get_db
    conn = _get_db()
    try:
        material = collect_session_material(conn, session_id)
    finally:
        conn.close()

    if material is None:
        print(f"  [backlog] no session found: {session_id}")
        return

    print(f"  [backlog] session {material['session_id']} — {material['title']}")
    print(f"\n  closing_summary:\n  {material['closing_summary']}\n")
    if material["devlog_tail"]:
        print(f"  devlog tail:\n{material['devlog_tail']}\n")
```

- [ ] **Step 4: Wire the `backlog` subparser into `synlynk/cli.py`**

In `synlynk/cli.py`, near the `events` subparser block (around line 440), add:

```python
    backlog_parser = subparsers.add_parser("backlog", help="GOVERNS backlog automation")
    backlog_sub = backlog_parser.add_subparsers(dest="backlog_command")

    note_parser = backlog_sub.add_parser("note", help="File a discovered/planned work item now")
    note_parser.add_argument("title")
    note_parser.add_argument("--body", default="")
    note_parser.add_argument("--session-id", default=None)
    note_parser.add_argument("--goal-id", default=None)
    note_parser.add_argument("--new-goal-outcome", default=None)
    note_parser.add_argument("--new-goal-criterion", default=None)
    note_parser.add_argument("--parent-issue", type=int, default=1198)

    scan_parser = backlog_sub.add_parser("scan-session", help="Print session material for a discovery re-scan")
    scan_parser.add_argument("--session-id", required=True)
```

Find where parsed subcommands are dispatched (the `if args.command == "events":` block, or equivalent) and add:

```python
    elif args.command == "backlog":
        from synlynk.backlog_automation import cmd_backlog_note, cmd_backlog_scan_session
        if args.backlog_command == "note":
            cmd_backlog_note(
                title=args.title, body=args.body, session_id=args.session_id,
                goal_id=args.goal_id, new_goal_outcome=args.new_goal_outcome,
                new_goal_criterion=args.new_goal_criterion, parent_issue=args.parent_issue,
            )
        elif args.backlog_command == "scan-session":
            cmd_backlog_scan_session(args.session_id)
        else:
            backlog_parser.print_help()
```

(Match the exact `if`/`elif` chain style already present at that point in `cli.py` — read the surrounding ~20 lines before editing so indentation and the dispatch variable name line up with the existing pattern.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/test_backlog_automation.py -v`
Expected: PASS (15 tests)

- [ ] **Step 6: Run the full test suite**

Run: `SYNLYNK_ALLOW_SHARED_STATE_DB=1 python3 -m pytest tests/ -q --tb=short`
Expected: PASS, no regressions (matches the existing `pytest tests/ -q --tb=short` command used by `support_engineer.py`'s own `test_suite` collector).

- [ ] **Step 7: Commit**

```bash
git add synlynk/backlog_automation.py synlynk/cli.py tests/test_backlog_automation.py
git commit -m "feat: wire synlynk backlog note/scan-session CLI (#1203)"
```

---

## Post-merge: SOP note (docs-only follow-up, not part of this PR)

Once this merges, add a short line to `CLAUDE.md`'s Herdr Workspace Protocol (or a new section)
telling Claude to call `synlynk backlog scan-session --session-id <id>` as part of session-close
housekeeping, and `synlynk backlog note "<title>"` live whenever it notices discovered/planned
work worth tracking. Per this repo's "Docs updates always go in a separate PR" rule, this is a
separate PR from the code above, opened after this plan's PR merges.
