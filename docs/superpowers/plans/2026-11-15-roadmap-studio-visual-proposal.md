# Roadmap Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new Vizor page, Roadmap Studio, that lets Nikhil visually drag/drop/approve/hold/revise/pin stories against the existing TPM-sweep `approval_tickets` release-proposal mechanism, instead of typing GitHub comment commands.

**Architecture:** A new read/write module (`synlynk/roadmap_studio.py`) exposes module-level functions over the existing `stories`/`approval_tickets` tables (no new tables, one additive nullable column `stories.proposal_order`). Four of its writes reuse shared helper functions extracted from `synlynk/tpm_sweep.py`'s `process_proposal_comments()` so the comment-grammar path and the new Vizor path can never drift apart; two writes (`reorder`, `pin`) are net-new since they have no comment-grammar equivalent. A new Vizor view (`synlynk/viz/roadmap_studio.py`) renders a JS-driven drag/drop board, wired into `synlynk/viz/cache.py`'s render loop, `synlynk/viz/server.py`'s daemon routes, `synlynk/viz/write_routes.py`'s classification table, and `synlynk/viz/home.py`'s STATUS nav.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `json`), no new dependencies. Front-end is hand-written vanilla JS embedded in a Python f-string (no framework, no build step, no separate `.js` file — matching the existing per-view generator convention in `synlynk/viz/*.py`, e.g. `board.py`).

**Spec deviation note (corrected during planning):** the approved spec (`docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md`) says the new generator lives in `synlynk/viz.py` and that the front-end ships as a separate `roadmap_studio.js` file. Neither matches the actual codebase: `synlynk/viz/` is a package of one generator-per-view file (`board.py`, `gantt.py`, ...), and every existing view embeds its JS inline in the Python-returned HTML string (see `synlynk/viz/board.py`'s `generate_board_html`). This plan follows the real convention — new file `synlynk/viz/roadmap_studio.py`, JS embedded inline — rather than the spec's literal (non-existent) file references. No behavior described in the spec changes; only the file-layout detail does.

---

### Task 1: Migration 33 — `stories.proposal_order`

**Files:**
- Create: `synlynk/migrations/m0033_stories_proposal_order.py`
- Modify: `synlynk/migrations/runner.py:23,31-34`
- Test: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrations_framework.py`:

```python
def test_migration_0033_adds_stories_proposal_order(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations import runner
    from synlynk.migrations.m0033_stories_proposal_order import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE stories (
            story_id TEXT PRIMARY KEY,
            title TEXT,
            readiness TEXT
        )"""
    )
    conn.execute("PRAGMA user_version = 32")
    conn.commit()

    monkeypatch.setattr(runner, "MIGRATIONS", [MIGRATION])
    runner.run_pending_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "proposal_order" in cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 33

    # Re-running against an already-migrated db is a no-op, not a crash.
    runner.run_pending_migrations(conn)
    cols_after = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert cols_after == cols
    conn.close()


def test_m0033_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0033_stories_proposal_order import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE stories (
            story_id TEXT PRIMARY KEY,
            title TEXT,
            readiness TEXT
        )"""
    )
    MIGRATION.up(conn)
    MIGRATION.up(conn)
    conn.commit()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "proposal_order" in cols
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_migrations_framework.py -k m0033 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0033_stories_proposal_order'`

- [ ] **Step 3: Write the migration**

Create `synlynk/migrations/m0033_stories_proposal_order.py`:

```python
"""Migration 33: add stories.proposal_order for Roadmap Studio drag-to-reorder.

See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
This is a display-ordering hint local to a single release_proposal ticket — it
does not feed goals.roadmap_priority or the Approach C roadmap_arcs/roadmap_phases
views, and today's /prioritize binary flag (stories.priority) is untouched.
"""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stories'"
    ).fetchone()
    if not table_exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    if "proposal_order" not in cols:
        conn.execute("ALTER TABLE stories ADD COLUMN proposal_order INTEGER")


MIGRATION = Migration(version=33, name="add_stories_proposal_order", up=_up)
```

- [ ] **Step 4: Register the migration in the runner**

In `synlynk/migrations/runner.py`, after the `M0032` import line (line 23), add:

```python
from synlynk.migrations.m0033_stories_proposal_order import MIGRATION as M0033
```

Then change the `MIGRATIONS` list (lines 31-34) from:

```python
MIGRATIONS: list[Migration] = [
    M0016, M0017, M0018, M0019, M0020, M0021, M0022, M0023,
    M0024, M0025, M0026, M0027, M0028, M0029, M0030, M0031,
    M0032,
]
```

to:

```python
MIGRATIONS: list[Migration] = [
    M0016, M0017, M0018, M0019, M0020, M0021, M0022, M0023,
    M0024, M0025, M0026, M0027, M0028, M0029, M0030, M0031,
    M0032, M0033,
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_migrations_framework.py -v`
Expected: PASS, all tests including the two new ones and the existing M0032 tests.

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0033_stories_proposal_order.py synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "feat(db): add migration 33 for stories.proposal_order (Roadmap Studio)"
```

---

### Task 2: Extract ticket-scoped shared helpers in `tpm_sweep.py`

**Files:**
- Modify: `synlynk/tpm_sweep.py:868-954` (refactor `process_proposal_comments`, add 4 new module-level helpers above it)
- Test: `tests/test_tpm_l1_advisory.py`

The comment-grammar path (`process_proposal_comments`) currently inlines its SQL and acts across *all* open `release_proposal` tickets (no `ticket_id` filter) because a GitHub issue's comment thread only ever has one proposal issue open at a time in practice. Roadmap Studio's UI shows multiple columns simultaneously and must act on exactly one. Per the decide-panel clarification folded into the spec, the comment path's behavior must not change — only the new Vizor-side callers get ticket scoping. The extraction below adds an optional `ticket_id` parameter to each helper: `None` preserves today's exact SQL/behavior (used by `process_proposal_comments`), an explicit value adds `AND id=?` (used only by `synlynk/roadmap_studio.py` in Task 3).

- [ ] **Step 1: Write the failing regression test**

Add to `tests/test_tpm_l1_advisory.py` (append at end of file):

```python
def test_approve_hold_helpers_are_ticket_scoped_when_given_a_ticket_id(tmp_path):
    import sqlite3
    import synlynk as sl
    from synlynk.tpm_sweep import _apply_approve, _apply_hold

    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS stories (
                story_id TEXT PRIMARY KEY,
                title TEXT,
                readiness TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS approval_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT,
                action TEXT,
                issue_url TEXT,
                status TEXT,
                resolved_at TIMESTAMP,
                constituent_story_ids TEXT
            )"""
        )
        conn.execute("INSERT INTO stories (story_id, title, readiness) VALUES ('s1', 'Task 1', 'advisory')")
        conn.execute("INSERT INTO stories (story_id, title, readiness) VALUES ('s2', 'Task 2', 'advisory')")
        conn.execute(
            "INSERT INTO approval_tickets (id, story_id, action, issue_url, status) "
            "VALUES (1, 'v0.33.0', 'release_proposal', 'https://github.com/test/1', 'open')"
        )
        conn.execute(
            "INSERT INTO approval_tickets (id, story_id, action, issue_url, status) "
            "VALUES (2, 'v0.33.1', 'release_proposal', 'https://github.com/test/2', 'open')"
        )
        conn.commit()

        # Ticket-scoped hold only touches ticket id=1, leaving id=2 open.
        _apply_hold(conn, ticket_id=1)
        rows = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM approval_tickets").fetchall()}
        assert rows[1] == "held"
        assert rows[2] == "open"

        # Ticket-scoped approve only resolves ticket id=2 and only promotes s1.
        promoted = _apply_approve(conn, constituent_story_ids=["s1"], dropped_stories=[], ticket_id=2)
        assert promoted == 1
        rows_after = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM approval_tickets").fetchall()}
        assert rows_after[2] == "resolved"
        assert rows_after[1] == "held"
        s1_readiness = conn.execute("SELECT readiness FROM stories WHERE story_id='s1'").fetchone()[0]
        assert s1_readiness == "ready"
        s2_readiness = conn.execute("SELECT readiness FROM stories WHERE story_id='s2'").fetchone()[0]
        assert s2_readiness == "advisory"
    finally:
        conn.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_tpm_l1_advisory.py -k ticket_scoped -v`
Expected: FAIL with `ImportError: cannot import name '_apply_approve'`

- [ ] **Step 3: Extract the four helpers and refactor `process_proposal_comments`**

In `synlynk/tpm_sweep.py`, insert these four module-level functions immediately above the `def process_proposal_comments(` line (868):

```python
def _apply_approve(
    conn, constituent_story_ids: list[str], dropped_stories: list[str], ticket_id: "int | None" = None
) -> int:
    """Promote every non-dropped constituent to readiness='ready' and resolve the ticket.

    ticket_id=None preserves the comment-grammar path's historical behavior of
    resolving every currently-open release_proposal ticket (only one is normally
    open at a time on that path). An explicit ticket_id scopes the UPDATE to that
    one ticket only — used by the Vizor Roadmap Studio write path.
    """
    promoted = 0
    for sid in constituent_story_ids:
        if sid not in dropped_stories:
            conn.execute("UPDATE stories SET readiness='ready' WHERE story_id=?", (sid,))
            promoted += 1
    try:
        if ticket_id is not None:
            conn.execute(
                "UPDATE approval_tickets SET status='resolved', resolved_at=CURRENT_TIMESTAMP "
                "WHERE action='release_proposal' AND status='open' AND id=?",
                (ticket_id,),
            )
        else:
            conn.execute(
                "UPDATE approval_tickets SET status='resolved', resolved_at=CURRENT_TIMESTAMP "
                "WHERE action='release_proposal' AND status='open'"
            )
    except Exception:
        pass
    conn.commit()
    return promoted


def _apply_hold(conn, ticket_id: "int | None" = None) -> None:
    """Hold the open release_proposal ticket(s). See _apply_approve for ticket_id semantics."""
    try:
        if ticket_id is not None:
            conn.execute(
                "UPDATE approval_tickets SET status='held' "
                "WHERE action='release_proposal' AND status='open' AND id=?",
                (ticket_id,),
            )
        else:
            conn.execute(
                "UPDATE approval_tickets SET status='held' "
                "WHERE action='release_proposal' AND status='open'"
            )
        conn.commit()
    except Exception:
        pass


def _apply_drop(conn, story_id: str) -> None:
    """Defer one story's readiness. Story-scoped already; no ticket_id needed."""
    conn.execute("UPDATE stories SET readiness='deferred' WHERE story_id=?", (story_id,))
    conn.commit()


def _apply_prioritize(conn, story_id: str) -> None:
    """Flip one story's binary priority flag. Story-scoped already; no ticket_id needed."""
    conn.execute("UPDATE stories SET priority=1 WHERE story_id=?", (story_id,))
    conn.commit()


```

Then replace the body of `process_proposal_comments` (the `for line in lines:` block, lines 888-942 in the pre-edit file) so it calls the new helpers instead of inlining SQL. Replace:

```python
                if low_sline.startswith("/approve") or low_sline == "lgtm" or "lgtm" in low_sline:
                    verdict = "approved"
                    for sid in constituent_story_ids:
                        if sid not in dropped_stories:
                            conn.execute(
                                "UPDATE stories SET readiness='ready' WHERE story_id=?", (sid,)
                            )
                            promoted += 1
                    try:
                        conn.execute(
                            "UPDATE approval_tickets SET status='resolved', resolved_at=CURRENT_TIMESTAMP "
                            "WHERE action='release_proposal' AND status='open'"
                        )
                    except Exception:
                        pass
                    conn.commit()

                elif low_sline.startswith("/revise"):
                    verdict = "revisions_requested"
                    instruction = sline[7:].strip()
                    if instruction:
                        revision_instructions.append(instruction)

                elif low_sline.startswith("/drop"):
                    target_id = sline[5:].strip()
                    if target_id:
                        dropped_stories.append(target_id)
                        conn.execute(
                            "UPDATE stories SET readiness='deferred' WHERE story_id=?", (target_id,)
                        )
                        conn.commit()

                elif low_sline.startswith("/prioritize"):
                    target_id = sline[11:].strip()
                    if target_id:
                        prioritized_stories.append(target_id)
                        conn.execute(
                            "UPDATE stories SET priority=1 WHERE story_id=?", (target_id,)
                        )
                        conn.commit()

                elif low_sline.startswith("/hold"):
                    verdict = "held"
                    try:
                        conn.execute(
                            "UPDATE approval_tickets SET status='held' "
                            "WHERE action='release_proposal' AND status='open'"
                        )
                        conn.commit()
                    except Exception:
                        pass
```

with:

```python
                if low_sline.startswith("/approve") or low_sline == "lgtm" or "lgtm" in low_sline:
                    verdict = "approved"
                    promoted += _apply_approve(conn, constituent_story_ids, dropped_stories)

                elif low_sline.startswith("/revise"):
                    verdict = "revisions_requested"
                    instruction = sline[7:].strip()
                    if instruction:
                        revision_instructions.append(instruction)

                elif low_sline.startswith("/drop"):
                    target_id = sline[5:].strip()
                    if target_id:
                        dropped_stories.append(target_id)
                        _apply_drop(conn, target_id)

                elif low_sline.startswith("/prioritize"):
                    target_id = sline[11:].strip()
                    if target_id:
                        prioritized_stories.append(target_id)
                        _apply_prioritize(conn, target_id)

                elif low_sline.startswith("/hold"):
                    verdict = "held"
                    _apply_hold(conn)
```

Note `promoted += _apply_approve(...)` replaces the old per-call `promoted += 1` loop — `_apply_approve` already returns the count, so if `/approve` appears on more than one comment line the accumulation semantics are unchanged (each call still adds its own promoted count).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_tpm_l1_advisory.py -v`
Expected: PASS — both the new ticket-scoping test and the two pre-existing tests (`test_process_proposal_comment_approval`, `test_process_proposal_comment_commands_revise_drop_prioritize_hold`), proving the refactor didn't change the comment-grammar path's behavior.

- [ ] **Step 5: Commit**

```bash
git add synlynk/tpm_sweep.py tests/test_tpm_l1_advisory.py
git commit -m "refactor(tpm): extract ticket-scoped approve/hold/drop/prioritize helpers"
```

---

### Task 3: `synlynk/roadmap_studio.py` — read + write module

**Files:**
- Create: `synlynk/roadmap_studio.py`
- Test: `tests/test_roadmap_studio.py`

This module is the Vizor-facing equivalent of `synlynk/board.py`: it opens the product `state.db` via the same `_open_product_db`-style connection helper, and exposes one read function (`studio_data`) plus six write functions (`approve_ticket`, `hold_ticket`, `revise_ticket`, `drop_story`, `reorder_stories`, `pin_story`) that `synlynk/viz/server.py` (Task 4) will call.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_roadmap_studio.py`:

```python
"""Tests for synlynk/roadmap_studio.py — Roadmap Studio's Vizor-side read/write layer.

See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
"""
import json

import pytest
import synlynk as sl


def _seed(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS stories (
            story_id TEXT PRIMARY KEY,
            title TEXT,
            role TEXT,
            readiness TEXT,
            status TEXT,
            priority INTEGER DEFAULT 5,
            estimated_tokens INTEGER,
            gh_issue TEXT,
            proposal_order INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT,
            action TEXT,
            issue_url TEXT,
            status TEXT,
            opened_at TIMESTAMP,
            resolved_at TIMESTAMP,
            constituent_story_ids TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, role, readiness, status, priority) VALUES "
        "('s1','Task 1','dev','ready','open',5), "
        "('s2','Task 2','qa','ready','open',5), "
        "('s3','Task 3','dev','advisory','open',5), "
        "('s4','Task 4','dev','draft','done',5)"
    )
    conn.execute(
        "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids) VALUES "
        "(1, 'v0.33.0', 'release_proposal', 'https://github.com/test/1', 'open', ?)",
        (json.dumps(["s1", "s2"]),),
    )
    conn.commit()


def test_studio_data_returns_open_tickets_and_backlog(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import studio_data

        data = studio_data(conn=conn)
        assert len(data["tickets"]) == 1
        ticket = data["tickets"][0]
        assert ticket["id"] == 1
        assert ticket["release_version"] == "v0.33.0"
        story_ids = {s["story_id"] for s in ticket["stories"]}
        assert story_ids == {"s1", "s2"}
        # s3 is advisory and unclaimed -> backlog. s4 is draft but status='done' -> excluded.
        backlog_ids = {s["story_id"] for s in data["backlog"]}
        assert backlog_ids == {"s3"}
    finally:
        conn.close()


def test_approve_ticket_resolves_only_that_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        conn.execute(
            "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids) VALUES "
            "(2, 'v0.33.1', 'release_proposal', 'https://github.com/test/2', 'open', ?)",
            (json.dumps(["s3"]),),
        )
        conn.commit()

        from synlynk.roadmap_studio import approve_ticket

        result = approve_ticket(1, conn=conn)
        assert result["ok"] is True
        assert result["promoted_count"] == 2
        statuses = {r[0]: r[1] for r in conn.execute("SELECT id, status FROM approval_tickets").fetchall()}
        assert statuses[1] == "resolved"
        assert statuses[2] == "open"
        readiness = {r[0]: r[1] for r in conn.execute("SELECT story_id, readiness FROM stories").fetchall()}
        assert readiness["s1"] == "ready"
        assert readiness["s2"] == "ready"
        assert readiness["s3"] == "advisory"
    finally:
        conn.close()


def test_approve_ticket_raises_keyerror_for_unknown_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import approve_ticket

        with pytest.raises(KeyError):
            approve_ticket(999, conn=conn)
    finally:
        conn.close()


def test_hold_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import hold_ticket

        result = hold_ticket(1, conn=conn)
        assert result["ok"] is True
        status = conn.execute("SELECT status FROM approval_tickets WHERE id=1").fetchone()[0]
        assert status == "held"
    finally:
        conn.close()


def test_revise_ticket_is_non_persistent(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import revise_ticket

        result = revise_ticket(1, "please split this into two releases", conn=conn)
        assert result == {
            "ok": True,
            "ticket_id": 1,
            "instructions": "please split this into two releases",
            "persisted": False,
        }
        # No table/column anywhere stores the instruction — ticket row is untouched.
        row = dict(conn.execute("SELECT * FROM approval_tickets WHERE id=1").fetchone())
        assert row["status"] == "open"
    finally:
        conn.close()


def test_drop_story(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import drop_story

        result = drop_story("s1", conn=conn)
        assert result["ok"] is True
        readiness = conn.execute("SELECT readiness FROM stories WHERE story_id='s1'").fetchone()[0]
        assert readiness == "deferred"
    finally:
        conn.close()


def test_reorder_stories_writes_sequential_proposal_order(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import reorder_stories

        result = reorder_stories(1, ["s2", "s1"], conn=conn)
        assert result["ok"] is True
        orders = {r[0]: r[1] for r in conn.execute("SELECT story_id, proposal_order FROM stories WHERE story_id IN ('s1','s2')").fetchall()}
        assert orders == {"s2": 0, "s1": 1}
    finally:
        conn.close()


def test_reorder_stories_rejects_story_not_in_ticket(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import reorder_stories

        with pytest.raises(ValueError):
            reorder_stories(1, ["s1", "s3"], conn=conn)
    finally:
        conn.close()


def test_pin_story_appends_to_constituent_story_ids(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import pin_story

        result = pin_story(1, "s3", conn=conn)
        assert result["ok"] is True
        assert result["over_cap"] is False
        raw = conn.execute("SELECT constituent_story_ids FROM approval_tickets WHERE id=1").fetchone()[0]
        assert set(json.loads(raw)) == {"s1", "s2", "s3"}
    finally:
        conn.close()


def test_pin_story_flags_over_cap_but_still_pins(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        conn.execute(
            "INSERT INTO stories (story_id, title, role, readiness, status, priority) VALUES "
            "('s5','Task 5','dev','advisory','open',5), "
            "('s6','Task 6','dev','advisory','open',5), "
            "('s7','Task 7','dev','advisory','open',5)"
        )
        conn.execute(
            "UPDATE approval_tickets SET constituent_story_ids=? WHERE id=1",
            (json.dumps(["s1", "s2", "s3", "s5", "s6"]),),
        )
        conn.commit()
        from synlynk.roadmap_studio import pin_story

        result = pin_story(1, "s7", conn=conn)
        assert result["ok"] is True
        assert result["over_cap"] is True
        raw = conn.execute("SELECT constituent_story_ids FROM approval_tickets WHERE id=1").fetchone()[0]
        assert len(json.loads(raw)) == 6
    finally:
        conn.close()


def test_pin_story_is_idempotent(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed(conn)
        from synlynk.roadmap_studio import pin_story

        pin_story(1, "s1", conn=conn)
        raw = conn.execute("SELECT constituent_story_ids FROM approval_tickets WHERE id=1").fetchone()[0]
        assert json.loads(raw) == ["s1", "s2"]
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_roadmap_studio.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.roadmap_studio'`

- [ ] **Step 3: Implement the module**

Create `synlynk/roadmap_studio.py`:

```python
"""Vizor Roadmap Studio: ticket-scoped read/write operations over approval_tickets.

Visualizes and drives the existing TPM-sweep release-proposal mechanism
(synlynk/tpm_sweep.py) as a drag/drop board. Four of the six writes here
delegate to shared helpers extracted from tpm_sweep.process_proposal_comments()
so the GitHub-comment path and this Vizor path can't drift apart; reorder and
pin are net-new (no comment-grammar equivalent existed for them).

See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from synlynk.board import _columns, _open_product_db
from synlynk.tpm_sweep import _apply_approve, _apply_drop, _apply_hold

RELEASE_PROPOSAL_ACTION = "release_proposal"


def _conn(conn: Optional[sqlite3.Connection], repo_path: str) -> tuple[sqlite3.Connection, bool]:
    if conn is not None:
        return conn, False
    opened, _slug = _open_product_db(repo_path, migrate=False)
    return opened, True


def _ticket_row(conn: sqlite3.Connection, ticket_id: int) -> dict:
    row = conn.execute(
        "SELECT id, story_id, status, constituent_story_ids FROM approval_tickets WHERE id=? AND action=?",
        (ticket_id, RELEASE_PROPOSAL_ACTION),
    ).fetchone()
    if row is None:
        raise KeyError(f"release_proposal ticket not found: {ticket_id}")
    return dict(row)


def _constituent_ids(ticket_row: dict) -> list[str]:
    raw = ticket_row.get("constituent_story_ids")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(sid) for sid in parsed] if isinstance(parsed, list) else []


def studio_data(repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    """Return open/held release_proposal tickets (with resolved constituent stories) and the backlog pool."""
    active_conn, owns = _conn(conn, repo_path)
    try:
        ticket_rows = active_conn.execute(
            "SELECT id, story_id AS release_version, issue_url, status, constituent_story_ids "
            "FROM approval_tickets WHERE action=? AND status IN ('open','held')",
            (RELEASE_PROPOSAL_ACTION,),
        ).fetchall()

        claimed: set[str] = set()
        tickets = []
        for row in ticket_rows:
            row_dict = dict(row)
            story_ids = _constituent_ids(row_dict)
            claimed.update(story_ids)
            stories = []
            if story_ids:
                placeholders = ",".join("?" for _ in story_ids)
                story_rows = active_conn.execute(
                    f"SELECT story_id, title, role, estimated_tokens, gh_issue, readiness, status, "
                    f"priority, proposal_order FROM stories WHERE story_id IN ({placeholders}) "
                    f"ORDER BY proposal_order ASC NULLS LAST, rowid ASC",
                    story_ids,
                ).fetchall()
                stories = [dict(r) for r in story_rows]
            tickets.append(
                {
                    "id": row_dict["id"],
                    "release_version": row_dict["release_version"],
                    "issue_url": row_dict["issue_url"],
                    "status": row_dict["status"],
                    "stories": stories,
                }
            )

        backlog_rows = active_conn.execute(
            "SELECT story_id, title, role, estimated_tokens, gh_issue FROM stories "
            "WHERE (readiness='advisory' OR (readiness IN ('ready','draft') AND status NOT IN ('done','archived')))"
        ).fetchall()
        backlog = [dict(r) for r in backlog_rows if r["story_id"] not in claimed]

        return {"tickets": tickets, "backlog": backlog}
    finally:
        if owns:
            active_conn.close()


def approve_ticket(ticket_id: int, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    active_conn, owns = _conn(conn, repo_path)
    try:
        ticket_row = _ticket_row(active_conn, ticket_id)
        constituent_story_ids = _constituent_ids(ticket_row)
        promoted = _apply_approve(active_conn, constituent_story_ids, [], ticket_id=ticket_id)
        return {"ok": True, "ticket_id": ticket_id, "promoted_count": promoted}
    finally:
        if owns:
            active_conn.close()


def hold_ticket(ticket_id: int, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    active_conn, owns = _conn(conn, repo_path)
    try:
        _ticket_row(active_conn, ticket_id)
        _apply_hold(active_conn, ticket_id=ticket_id)
        return {"ok": True, "ticket_id": ticket_id}
    finally:
        if owns:
            active_conn.close()


def revise_ticket(
    ticket_id: int, instructions: str, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Mirror process_proposal_comments()'s /revise: return the instruction, persist nothing.

    See the spec's confirmed finding (grep -n revision_instructions synlynk/tpm_sweep.py) that
    today's /revise instruction is never written to any table or column on the comment path either.
    """
    active_conn, owns = _conn(conn, repo_path)
    try:
        _ticket_row(active_conn, ticket_id)
        return {"ok": True, "ticket_id": ticket_id, "instructions": instructions, "persisted": False}
    finally:
        if owns:
            active_conn.close()


def drop_story(story_id: str, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None) -> dict:
    active_conn, owns = _conn(conn, repo_path)
    try:
        _apply_drop(active_conn, story_id)
        return {"ok": True, "story_id": story_id}
    finally:
        if owns:
            active_conn.close()


def reorder_stories(
    ticket_id: int, ordered_story_ids: list[str], repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Write sequential proposal_order for ordered_story_ids, scoped to ticket_id's own constituents.

    Rejects (does not silently ignore) any story_id not a member of this ticket's
    constituent_story_ids — the proposal_order scoping invariant from the spec.
    """
    active_conn, owns = _conn(conn, repo_path)
    try:
        ticket_row = _ticket_row(active_conn, ticket_id)
        members = set(_constituent_ids(ticket_row))
        for story_id in ordered_story_ids:
            if story_id not in members:
                raise ValueError(f"story_id {story_id!r} is not a constituent of ticket {ticket_id}")
        for index, story_id in enumerate(ordered_story_ids):
            active_conn.execute("UPDATE stories SET proposal_order=? WHERE story_id=?", (index, story_id))
        active_conn.commit()
        return {"ok": True, "ticket_id": ticket_id, "ordered_story_ids": list(ordered_story_ids)}
    finally:
        if owns:
            active_conn.close()


def pin_story(
    ticket_id: int, story_id: str, repo_path: str = ".", *, conn: Optional[sqlite3.Connection] = None
) -> dict:
    """Append story_id into ticket's constituent_story_ids JSON column if not already present.

    Allowed to push the ticket past package_next_release_proposal()'s 5-story cap — this is a
    deliberate manual override, per the spec. Returns over_cap so the UI can show a non-blocking
    warning badge; package_next_release_proposal() itself is untouched.
    """
    active_conn, owns = _conn(conn, repo_path)
    try:
        ticket_row = _ticket_row(active_conn, ticket_id)
        members = _constituent_ids(ticket_row)
        if story_id not in members:
            members.append(story_id)
            active_conn.execute(
                "UPDATE approval_tickets SET constituent_story_ids=? WHERE id=?",
                (json.dumps(members), ticket_id),
            )
            active_conn.commit()
        return {"ok": True, "ticket_id": ticket_id, "story_id": story_id, "over_cap": len(members) > 5}
    finally:
        if owns:
            active_conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_roadmap_studio.py -v`
Expected: PASS, all 11 tests.

- [ ] **Step 5: Commit**

```bash
git add synlynk/roadmap_studio.py tests/test_roadmap_studio.py
git commit -m "feat(roadmap-studio): add read/write module over approval_tickets"
```

---

### Task 4: Vizor view — `synlynk/viz/roadmap_studio.py`

**Files:**
- Create: `synlynk/viz/roadmap_studio.py`
- Modify: `synlynk/viz/cache.py:17,32` (import + wire into `_write_cache`)
- Test: `tests/test_viz_roadmap_studio.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_viz_roadmap_studio.py`:

```python
"""Rendering test for synlynk/viz/roadmap_studio.py's generate_roadmap_studio_html()."""
from synlynk.viz.roadmap_studio import generate_roadmap_studio_html


def test_generate_roadmap_studio_html_has_shell_and_actions():
    out = generate_roadmap_studio_html(44444)
    assert "<!DOCTYPE html>" in out
    assert "Roadmap Studio" in out
    assert "api/roadmap_studio" in out
    for action in ("approve", "hold", "revise", "drop", "reorder", "pin"):
        assert f"api/roadmap_studio/{action}" in out
    assert "vizorAuthHeaders" in out


def test_generate_roadmap_studio_html_is_deterministic_per_port():
    first = generate_roadmap_studio_html(55555)
    second = generate_roadmap_studio_html(55555)
    assert first == second
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_viz_roadmap_studio.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.viz.roadmap_studio'`

- [ ] **Step 3: Implement the generator**

Create `synlynk/viz/roadmap_studio.py`:

```python
"""Roadmap Studio: drag/drop Vizor front-end over tpm_sweep's release_proposal tickets.

First Vizor view with real client-side JS (confirmed acceptable in the design
spec — Vizor's zero-JS convention is a convention, not a hard constraint).
See docs/superpowers/specs/2026-11-15-roadmap-studio-visual-proposal-ui-design.md.
"""
from synlynk.viz.chrome import _live_js


def generate_roadmap_studio_html(port: int) -> str:
    """Render the Roadmap Studio shell; ticket/backlog data comes from GET api/roadmap_studio."""
    live = _live_js(port)
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>synlynk Vizor — Roadmap Studio</title>
<style>
:root{--bg:#f6f8fa;--panel:#fff;--panel-2:#f1f5f9;--ink:#1f2328;--muted:#667085;--line:#d8dee4;--accent:#0d9e87;--accent-bg:#e6f7f4;--warn:#dc2626;--shadow:0 2px 8px rgba(31,35,40,0.06)}
@media (prefers-color-scheme: dark){
  :root{--bg:#0d1117;--panel:#161b22;--panel-2:#21262d;--ink:#f0f6fc;--muted:#8b949e;--line:#30363d;--accent:#3de0c0;--accent-bg:#0d2137;--warn:#f87171;--shadow:0 2px 12px rgba(0,0,0,0.4)}
}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1600px;margin:0 auto;padding:28px 24px 70px}
.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px}
h1{font-size:30px;margin:6px 0 4px;font-weight:700}
.subtitle{color:var(--muted);margin:0 0 20px;font-size:13px}
.board{display:flex;gap:14px;align-items:start;overflow-x:auto;padding-bottom:16px}
.column{background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:10px;min-width:260px;min-height:280px;display:flex;flex-direction:column}
.column.dragover{border-color:var(--accent)}
.column-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.column h2{font-size:13px;margin:0;font-weight:700}
.cap-warn{color:var(--warn);font-size:10px;font-weight:700}
.column-actions{display:flex;gap:6px;margin-bottom:10px}
.btn{border:1px solid var(--line);background:var(--panel);border-radius:4px;padding:4px 8px;font-size:11px;cursor:pointer;font-family:inherit;font-weight:600}
.btn:hover{border-color:var(--accent)}
.revise-box{width:100%;font-size:11px;margin-top:6px;padding:4px;border-radius:4px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:8px;box-shadow:var(--shadow);cursor:grab}
.card h3{font-size:12px;margin:0 0 4px}
.card .meta{color:var(--muted);font-size:10px}
.backlog{margin-top:10px;background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:10px}
.backlog.dragover{border-color:var(--accent)}
.backlog h2{font-size:13px;margin:0 0 10px}
.empty{color:var(--muted);padding:16px 8px;font-size:11px;text-align:center;font-style:italic}
</style></head><body><main>
<div class="eyebrow">Vizor / Roadmap Studio</div>
<h1>Roadmap Studio</h1>
<p class="subtitle">Drag, approve, hold, revise, drop, and pin stories against open release proposals. Writes go straight to the product <code>state.db</code> via the same paths as the GitHub-comment grammar.</p>
<div id="board" class="board"></div>
<div class="backlog" id="backlog-pane">
  <h2>Backlog</h2>
  <div id="backlog-list"></div>
</div>
</main>""" + live + """<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let studioData={tickets:[],backlog:[]};

function cardHtml(story,ticketId){
  return `<article class="card" draggable="true" data-story-id="${esc(story.story_id)}" data-ticket-id="${ticketId??''}">
    <h3>${esc(story.title||story.story_id)}</h3>
    <div class="meta">${esc(story.story_id)} &middot; ${esc(story.role||'')}</div>
  </article>`;
}

function draw(){
  document.getElementById('board').innerHTML=studioData.tickets.map(t=>{
    const overCap=(t.stories||[]).length>5;
    return `<section class="column" data-ticket-id="${t.id}">
      <div class="column-header">
        <h2>${esc(t.release_version)} &middot; ${esc(t.status)}</h2>
        ${overCap?`<span class="cap-warn">${t.stories.length} of 5 suggested</span>`:''}
      </div>
      <div class="column-actions">
        <button class="btn" onclick="approveTicket(${t.id})">Approve</button>
        <button class="btn" onclick="holdTicket(${t.id})">Hold</button>
      </div>
      <input class="revise-box" placeholder="Revise instructions..." onkeydown="if(event.key==='Enter')reviseTicket(${t.id},this.value)">
      <div class="cards" data-ticket-id="${t.id}">${(t.stories||[]).map(s=>cardHtml(s,t.id)).join('')||'<div class="empty">No stories</div>'}</div>
    </section>`;
  }).join('')||'<div class="empty">No open proposals</div>';

  document.getElementById('backlog-list').innerHTML=(studioData.backlog||[]).map(s=>cardHtml(s,null)).join('')||'<div class="empty">Backlog empty</div>';

  wireDragAndDrop();
}

function wireDragAndDrop(){
  document.querySelectorAll('.card').forEach(card=>{
    card.addEventListener('dragstart',e=>{
      e.dataTransfer.setData('story_id',card.dataset.storyId);
      e.dataTransfer.setData('from_ticket_id',card.dataset.ticketId||'');
    });
  });
  document.querySelectorAll('.column .cards').forEach(zone=>{
    zone.addEventListener('dragover',e=>{e.preventDefault();zone.closest('.column').classList.add('dragover')});
    zone.addEventListener('dragleave',()=>zone.closest('.column').classList.remove('dragover'));
    zone.addEventListener('drop',e=>{
      e.preventDefault();
      zone.closest('.column').classList.remove('dragover');
      const storyId=e.dataTransfer.getData('story_id');
      const fromTicket=e.dataTransfer.getData('from_ticket_id');
      const toTicket=Number(zone.dataset.ticketId);
      if(!fromTicket){pinStory(toTicket,storyId);}
      else{
        const ids=[...zone.querySelectorAll('.card')].map(c=>c.dataset.storyId);
        ids.push(storyId);
        reorderStories(toTicket,ids);
      }
    });
  });
  const backlogZone=document.getElementById('backlog-pane');
  backlogZone.addEventListener('dragover',e=>{e.preventDefault();backlogZone.classList.add('dragover')});
  backlogZone.addEventListener('dragleave',()=>backlogZone.classList.remove('dragover'));
  backlogZone.addEventListener('drop',e=>{
    e.preventDefault();
    backlogZone.classList.remove('dragover');
    const storyId=e.dataTransfer.getData('story_id');
    const fromTicket=e.dataTransfer.getData('from_ticket_id');
    if(fromTicket)dropStory(storyId);
  });
}

async function load(){
  const r=await fetch('api/roadmap_studio');
  if(!r.ok){document.getElementById('board').textContent='Roadmap Studio unavailable';return}
  studioData=await r.json();
  draw();
}
async function post(path,body){
  const r=await fetch(path,{method:'POST',headers:window.vizorAuthHeaders({'Content-Type':'application/json'}),body:JSON.stringify(body)});
  if(!r.ok){alert('Request failed');return}
  await load();
}
function approveTicket(id){post('api/roadmap_studio/approve',{ticket_id:id})}
function holdTicket(id){post('api/roadmap_studio/hold',{ticket_id:id})}
function reviseTicket(id,instructions){post('api/roadmap_studio/revise',{ticket_id:id,instructions})}
function dropStory(storyId){post('api/roadmap_studio/drop',{story_id:storyId})}
function reorderStories(ticketId,orderedStoryIds){post('api/roadmap_studio/reorder',{ticket_id:ticketId,ordered_story_ids:orderedStoryIds})}
function pinStory(ticketId,storyId){post('api/roadmap_studio/pin',{ticket_id:ticketId,story_id:storyId})}
load();
</script></body></html>"""
```

- [ ] **Step 4: Wire into `_write_cache`**

In `synlynk/viz/cache.py`, add this import after line 17 (`from synlynk.viz.observatory import generate_observatory_html`):

```python
from synlynk.viz.roadmap_studio import generate_roadmap_studio_html
```

Then in the `views` dict (line 32, right after `"board.html": generate_board_html(port),`), add:

```python
        "roadmap_studio.html": generate_roadmap_studio_html(port),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_viz_roadmap_studio.py -v`
Expected: PASS, both tests.

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz/roadmap_studio.py synlynk/viz/cache.py tests/test_viz_roadmap_studio.py
git commit -m "feat(viz): add Roadmap Studio view and wire into cache render loop"
```

---

### Task 5: Daemon routes in `synlynk/viz/server.py`

**Files:**
- Modify: `synlynk/viz/server.py:246-258` (new GET handler), `:262-269` (OPTIONS), `:271-304` (POST dispatch), plus 6 new handler methods after `_handle_board_stage_request` (ends at line 506 in the pre-edit file)
- Test: `tests/test_viz_roadmap_studio_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_viz_roadmap_studio_routes.py`. This drives the module-level functions the handlers delegate to (the handlers themselves are thin dispatch — see `_handle_board_status_request` for the existing precedent that this repo's own test suite for board routes follows the same "test the module function, not the HTTP layer" pattern):

```python
"""Smoke tests that the roadmap_studio module functions server.py delegates to
raise the same exception types _handle_board_status_request's pattern expects
(ValueError->400, KeyError->404), so the new _handle_roadmap_studio_* handlers
added in synlynk/viz/server.py behave consistently with the Board route handlers.
"""
import json

import pytest
import synlynk as sl
from synlynk.roadmap_studio import approve_ticket, pin_story, reorder_stories


def _seed(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS stories (
            story_id TEXT PRIMARY KEY, title TEXT, role TEXT, readiness TEXT,
            status TEXT, priority INTEGER DEFAULT 5, estimated_tokens INTEGER,
            gh_issue TEXT, proposal_order INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS approval_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, action TEXT,
            issue_url TEXT, status TEXT, opened_at TIMESTAMP, resolved_at TIMESTAMP,
            constituent_story_ids TEXT
        )"""
    )
    conn.execute("INSERT INTO stories (story_id, title, readiness, status) VALUES ('s1','T1','ready','open')")
    conn.execute(
        "INSERT INTO approval_tickets (id, story_id, action, issue_url, status, constituent_story_ids) "
        "VALUES (1, 'v1', 'release_proposal', 'https://x/1', 'open', ?)",
        (json.dumps(["s1"]),),
    )
    conn.commit()


def test_approve_ticket_raises_keyerror_maps_to_404_in_handler(tmp_path):
    conn = sl._get_db(str(tmp_path / "state.db"))
    try:
        _seed(conn)
        with pytest.raises(KeyError):
            approve_ticket(12345, conn=conn)
    finally:
        conn.close()


def test_reorder_stories_raises_valueerror_maps_to_400_in_handler(tmp_path):
    conn = sl._get_db(str(tmp_path / "state.db"))
    try:
        _seed(conn)
        with pytest.raises(ValueError):
            reorder_stories(1, ["not-a-member"], conn=conn)
    finally:
        conn.close()


def test_pin_story_returns_ok_dict_shape_handler_passes_through(tmp_path):
    conn = sl._get_db(str(tmp_path / "state.db"))
    try:
        _seed(conn)
        result = pin_story(1, "s1", conn=conn)
        assert result == {"ok": True, "ticket_id": 1, "story_id": "s1", "over_cap": False}
    finally:
        conn.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_viz_roadmap_studio_routes.py -v`
Expected: FAIL with `ImportError` (this test file imports from `synlynk.roadmap_studio`, which exists after Task 3 — if Tasks are run in order this step will actually PASS already; run it anyway to confirm, since it locks in the exception-type contract the new `server.py` handlers below rely on before touching `server.py`).

- [ ] **Step 3: Add the GET data route**

In `synlynk/viz/server.py`, immediately after the existing `/api/board` block (ends at line 258, `return`), add:

```python

        if path == "/api/roadmap_studio":
            from synlynk.roadmap_studio import studio_data
            try:
                payload = studio_data()
            except FileNotFoundError:
                payload = {"tickets": [], "backlog": []}
            self._send_json_ok(payload)
            return
```

- [ ] **Step 4: Register the 6 POST paths in `do_OPTIONS`**

Change line 264's `valid_paths` tuple from:

```python
        valid_paths = ("/note", "/dispatch", "/approve", "/kill", "/architect-map/view-pref", "/roles/create", "/roles/charter/update", "/worktrees/clean", "/tools/install", "/api/tools/install", "/api/board/status", "/api/board/stage", "/graph/refresh", "/api/graph/refresh", "/api/v1/graph/refresh")
```

to:

```python
        valid_paths = ("/note", "/dispatch", "/approve", "/kill", "/architect-map/view-pref", "/roles/create", "/roles/charter/update", "/worktrees/clean", "/tools/install", "/api/tools/install", "/api/board/status", "/api/board/stage", "/graph/refresh", "/api/graph/refresh", "/api/v1/graph/refresh", "/api/roadmap_studio/approve", "/api/roadmap_studio/hold", "/api/roadmap_studio/revise", "/api/roadmap_studio/drop", "/api/roadmap_studio/reorder", "/api/roadmap_studio/pin")
```

- [ ] **Step 5: Add the 6 POST dispatch entries**

In `do_POST`, after the existing `elif clean_path == "/api/board/stage" or clean_path.endswith("/api/board/stage"):` block (lines 299-300), add:

```python
        elif clean_path == "/api/roadmap_studio/approve" or clean_path.endswith("/api/roadmap_studio/approve"):
            self._handle_roadmap_studio_approve_request()
        elif clean_path == "/api/roadmap_studio/hold" or clean_path.endswith("/api/roadmap_studio/hold"):
            self._handle_roadmap_studio_hold_request()
        elif clean_path == "/api/roadmap_studio/revise" or clean_path.endswith("/api/roadmap_studio/revise"):
            self._handle_roadmap_studio_revise_request()
        elif clean_path == "/api/roadmap_studio/drop" or clean_path.endswith("/api/roadmap_studio/drop"):
            self._handle_roadmap_studio_drop_request()
        elif clean_path == "/api/roadmap_studio/reorder" or clean_path.endswith("/api/roadmap_studio/reorder"):
            self._handle_roadmap_studio_reorder_request()
        elif clean_path == "/api/roadmap_studio/pin" or clean_path.endswith("/api/roadmap_studio/pin"):
            self._handle_roadmap_studio_pin_request()
```

- [ ] **Step 6: Add the 6 handler methods**

Immediately after `_handle_board_stage_request` (the method ending `self._send_json_ok(result)` before `def _handle_tool_install_request`), add:

```python
    def _handle_roadmap_studio_approve_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.roadmap_studio import approve_ticket
            result = approve_ticket(payload.get("ticket_id"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_roadmap_studio_hold_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.roadmap_studio import hold_ticket
            result = hold_ticket(payload.get("ticket_id"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_roadmap_studio_revise_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.roadmap_studio import revise_ticket
            result = revise_ticket(payload.get("ticket_id"), payload.get("instructions", ""))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_roadmap_studio_drop_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.roadmap_studio import drop_story
            result = drop_story(payload.get("story_id"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_roadmap_studio_reorder_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.roadmap_studio import reorder_stories
            result = reorder_stories(payload.get("ticket_id"), payload.get("ordered_story_ids") or [])
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)

    def _handle_roadmap_studio_pin_request(self):
        try:
            payload = self._read_json_body()
            from synlynk.roadmap_studio import pin_story
            result = pin_story(payload.get("ticket_id"), payload.get("story_id"))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.send_error(400, str(exc) or "Invalid JSON")
            return
        except KeyError as exc:
            self.send_error(404, str(exc))
            return
        except FileNotFoundError as exc:
            self.send_error(404, str(exc))
            return
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_viz_roadmap_studio_routes.py tests/test_roadmap_studio.py -v`
Expected: PASS, all tests.

- [ ] **Step 8: Commit**

```bash
git add synlynk/viz/server.py tests/test_viz_roadmap_studio_routes.py
git commit -m "feat(viz): add Roadmap Studio daemon routes (GET + 6 POST actions)"
```

---

### Task 6: `write_routes.py` classification + `home.py` nav entry

**Files:**
- Modify: `synlynk/viz/write_routes.py:4-16`
- Modify: `synlynk/viz/home.py` (STATUS nav category, after the Gantt `<a>` block)
- Test: `tests/test_viz_write_routes_roadmap_studio.py`, `tests/test_viz_nav_roadmap_studio.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_viz_write_routes_roadmap_studio.py`:

```python
from synlynk.viz.write_routes import WRITE_ROUTES


def test_roadmap_studio_routes_are_classified_keep():
    for action in ("approve", "hold", "revise", "drop", "reorder", "pin"):
        assert WRITE_ROUTES[f"roadmap_studio/{action}"] == "keep"
```

Create `tests/test_viz_nav_roadmap_studio.py`:

```python
from synlynk.viz.home import generate_index_html


def test_status_nav_includes_roadmap_studio():
    out = generate_index_html({"workspace": {"repos": []}}, 44444)
    assert 'href="roadmap_studio.html"' in out
    assert 'data-view="roadmap_studio"' in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_viz_write_routes_roadmap_studio.py tests/test_viz_nav_roadmap_studio.py -v`
Expected: FAIL — `KeyError: 'roadmap_studio/approve'` and an `assert` failure for the missing nav link, respectively.

- [ ] **Step 3: Add the write_routes entries**

In `synlynk/viz/write_routes.py`, add after the `"board/status": "keep",` line:

```python
    "roadmap_studio/approve": "keep",
    "roadmap_studio/hold": "keep",
    "roadmap_studio/revise": "keep",
    "roadmap_studio/drop": "keep",
    "roadmap_studio/reorder": "keep",
    "roadmap_studio/pin": "keep",
```

- [ ] **Step 4: Add the nav entry**

In `synlynk/viz/home.py`, immediately after the Gantt `<a class="nav-link" ...>` block (the one ending `</a>` after `<span class="nav-label">Gantt</span>`), add:

```html
      <a class="nav-link" href="roadmap_studio.html" data-view="roadmap_studio" data-cat="STATUS" data-label="Roadmap Studio">
        <span class="nav-icon">🗂</span>
        <span class="nav-label">Roadmap Studio</span>
      </a>
```

Match the indentation of the surrounding Board/Gantt `<a>` tags exactly as found in the file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_viz_write_routes_roadmap_studio.py tests/test_viz_nav_roadmap_studio.py -v`
Expected: PASS, both tests.

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz/write_routes.py synlynk/viz/home.py tests/test_viz_write_routes_roadmap_studio.py tests/test_viz_nav_roadmap_studio.py
git commit -m "feat(viz): classify Roadmap Studio write routes and add STATUS nav entry"
```

---

### Task 7: Full-suite verification and PR update

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest -q`
Expected: all tests pass, including every test added in Tasks 1-6 and the pre-existing `test_tpm_l1_advisory.py`/`test_migrations_framework.py` tests (proving Task 2's refactor and Task 1's new migration didn't regress anything).

- [ ] **Step 2: Manual drag/drop verification (not unit-testable, per spec's Testing section)**

Run: `synlynk viz` (or the project's existing local Vizor-launch command) and in a browser:
1. Navigate to Roadmap Studio from the STATUS nav.
2. Confirm at least one open `release_proposal` ticket's column renders with its constituent cards.
3. Drag a card within a column and confirm the page re-fetches/re-renders afterward (no stale optimistic state).
4. Drag a backlog card into a column and confirm it appears as pinned (and, if it pushes the column past 5, confirm the "N of 5 suggested" warning badge appears without blocking the pin).
5. Click Approve on a column and confirm its cards disappear from Roadmap Studio (their `readiness` is now `ready`).

If there is no open `release_proposal` ticket in the local `state.db` to test against, this step can be deferred to the PR's own review cycle rather than fabricating one — note that explicitly in the PR description's test plan.

- [ ] **Step 3: Update the blog post / PR per this repo's protocols**

Per CLAUDE.md's Multi-Task & Multi-Goal Series Tracking Protocol, this PR's status rollup belongs as a comment on its GOVERNS parent tracking issue (create one first if none exists linking this work — see the Pending Tasks note below) rather than as a new per-PR blog stub (the Blog Post Protocol's per-PR mechanical generation is retired; milestone retrospectives only).

- [ ] **Step 4: Final commit and push**

```bash
git add -A
git status --short
```

Review the output — expect no unstaged changes beyond what Tasks 1-6 already committed. If clean:

```bash
SYNLYNK_GH_ROLE=pm git push origin chore/roadmap-studio-visual-proposal-spec
```

---

## Open item carried from spec sign-off (not a plan task — flag before dispatch)

Per the Hardened PR Review Policy and GOVERNS-linkage gate in this repo's `CLAUDE.md`, every dispatched job needs a linked GOVERNS goal/story, and the Multi-Task & Multi-Goal Series Tracking Protocol requires a parent tracking issue for multi-task work. Neither has been created yet for Roadmap Studio. Before dispatching any task above to a subagent or another harness, create and link that GOVERNS goal/parent issue — otherwise dispatch preflight will block on the linkage gate.
