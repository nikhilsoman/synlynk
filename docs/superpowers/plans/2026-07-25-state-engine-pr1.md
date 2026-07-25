# State Engine PR1: DB-Canonicalize roadmap.md, memory.md, costs.md

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `state.db` the sole mutation point for `roadmap.md`, `memory.md`, and `costs.md` — extending the write-through/regenerate pattern that `todo.md` already proves out — so these three files become disposable, regenerated projections instead of hand-edited prose, closing the `costs.md` drift class of incident (#481, #482, #485) for good.

**Architecture:** Each file gets a `_generate_<file>_md()` function mirroring `_generate_todo_md()` (`synlynk/db.py:1309-1347`) exactly: it queries the relevant table(s), writes the file to `_docs_dir()` pre-migration or `_synlynk_project_docs_dir()` post-migration, and calls `_dr_sync(<filename>)` only when `_is_migrated()`. New CLI verbs (`synlynk roadmap add`, extending `synlynk cost log`) call the regeneration function after every DB write, following the `cmd_story_create()` → `_generate_todo_md()` and `cmd_memory_add()` → `_write_memory_md()` call patterns. `check_budgets()` moves off the `parse_costs_md()` regex path onto a direct `cost_entries` query. Rotation moves aged entries into `project-docs/archive/`. The mutation guard warns (never blocks) when a file's on-disk content doesn't match either the last git-committed blob or current regeneration output. The final task runs `synlynk migrate` on this repo itself.

**Tech Stack:** Python 3 stdlib only (sqlite3, argparse, os, re) — no new dependencies, per this project's zero-dependency constraint (`CLAUDE.md`).

---

## Reference: existing patterns you must follow exactly

**`_generate_todo_md()`** (`synlynk/db.py:1309-1347`) — the dual-path (pre/post migration) regeneration pattern every new `_generate_*_md()` function in this plan follows:

```python
def _generate_todo_md() -> None:
    from synlynk import _docs_dir, _dr_sync, _get_db, _is_migrated, _synlynk_project_docs_dir
    if _is_migrated():
        todo_path = os.path.join(_synlynk_project_docs_dir(), "todo.md")
        os.makedirs(os.path.dirname(todo_path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        todo_path = os.path.join(docs_dir, "todo.md")
    conn = _get_db()
    rows = conn.execute("SELECT story_id, title, engg_domain, status FROM stories ORDER BY created_at ASC").fetchall()
    conn.close()
    lines = ["# Tasks (generated - source of truth is state.db)\n", "# Edit via: synlynk story create/update | Do NOT hand-edit this file\n\n"]
    for story_id, title, engg_domain, status in rows:
        check = "x" if status == "done" else ("-" if status == "deferred" else " ")
        domain = f" [{engg_domain}]" if engg_domain and engg_domain != "unknown" else ""
        lines.append(f"- [{check}] {title or story_id}{domain} <!-- id:{story_id} -->\n")
    with open(todo_path, "w") as f:
        f.writelines(lines)
    if _is_migrated():
        _dr_sync("todo.md")
```

Note the key difference from `_write_memory_md()`/`cmd_memory_add()` (`synlynk/db.py:1349-1386`): `_generate_todo_md()` **always** writes the file (to whichever path is correct for the migration state), and only the `_dr_sync()` call is gated behind `_is_migrated()`. `_write_memory_md()` today is only ever called from inside an `if _is_migrated():` block in `cmd_memory_add()`, so pre-migration, `memory.md` gets zero write-through at all — a real gap. Task 3 below fixes this by giving `memory.md` the same always-write, gate-only-the-DR-sync treatment `todo.md` already has.

**Existing tables to build on:**
```sql
-- synlynk/db.py:423-439
CREATE TABLE IF NOT EXISTS roadmap_arcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT NOT NULL UNIQUE,
    title TEXT, status TEXT DEFAULT 'planned', target_date TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS roadmap_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT, arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
    phase_title TEXT NOT NULL, status TEXT DEFAULT 'planned', priority TEXT,
    story_id TEXT REFERENCES stories(story_id), notes TEXT
);
-- goal_id column added via a migration shim at db.py:472-477 (PRAGMA table_info + conditional ALTER TABLE)
```
`cost_entries` already exists and is written by `_insert_cost_row()` (`synlynk/db.py:786-889`); no new columns needed.

**Test fixtures** (`tests/conftest.py`): `isolated_db` (autouse — redirects `DB_PATH` to a temp file per test); `project_dir` — builds a **pre-migration** layout with seeded `project-docs/{todo,memory,roadmap,costs}.md` and `.synlynk/config.json`. For post-migration tests, use the local `_setup_migrated(tmp_path, monkeypatch)` helper defined in `tests/test_migrate.py:467` (writes the `.synlynk_migrated` sentinel, creates `.synlynk/project-docs/devlogs/`).

---

## Task 1: `_generate_roadmap_md()` + `synlynk roadmap add` CLI verb

**Files:**
- Modify: `synlynk/db.py` (add `_generate_roadmap_md()` near `_generate_todo_md()` at line 1347, add `cmd_roadmap_add()` near `cmd_story_create()`)
- Modify: `synlynk/cli.py` (add `roadmap` subparser near the `story`/`cost` blocks, ~line 595 and ~line 954)
- Test: `tests/test_db.py` (new file)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
import os
import sqlite3

from synlynk.db import _generate_roadmap_md, cmd_roadmap_add


def _seed_arc(conn, version="v0.13.0", title="State Engine", status="planned"):
    conn.execute(
        "INSERT INTO roadmap_arcs (version, title, status) VALUES (?, ?, ?)",
        (version, title, status),
    )
    conn.commit()


def test_generate_roadmap_md_creates_file_pre_migration(project_dir):
    from synlynk import _get_db
    conn = _get_db()
    _seed_arc(conn)
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title, status, priority) VALUES (?, ?, ?, ?)",
        ("v0.13.0", "PR1 — DB-canonicalize project-docs", "in_progress", "p0"),
    )
    conn.commit()
    conn.close()

    _generate_roadmap_md()

    path = os.path.join(str(project_dir), "project-docs", "roadmap.md")
    assert os.path.exists(path)
    content = open(path).read()
    assert "v0.13.0" in content
    assert "State Engine" in content
    assert "PR1 — DB-canonicalize project-docs" in content
    assert "Do NOT hand-edit" in content


def test_generate_roadmap_md_writes_post_migration_path(tmp_path, monkeypatch):
    from tests.test_migrate import _setup_migrated
    from synlynk import _get_db
    _setup_migrated(tmp_path, monkeypatch)
    conn = _get_db()
    _seed_arc(conn)
    conn.close()

    _generate_roadmap_md()

    path = os.path.join(".synlynk", "project-docs", "roadmap.md")
    assert os.path.exists(path)
    assert "v0.13.0" in open(path).read()


def test_cmd_roadmap_add_inserts_arc_and_regenerates_md(project_dir):
    cmd_roadmap_add(version="v0.14.0", title="Next Thing", status="planned")

    from synlynk import _get_db
    conn = _get_db()
    row = conn.execute(
        "SELECT title, status FROM roadmap_arcs WHERE version=?", ("v0.14.0",)
    ).fetchone()
    conn.close()
    assert row == ("Next Thing", "planned")

    path = os.path.join(str(project_dir), "project-docs", "roadmap.md")
    assert "Next Thing" in open(path).read()


def test_cmd_roadmap_add_phase_links_to_existing_arc(project_dir):
    cmd_roadmap_add(version="v0.14.0", title="Next Thing", status="planned")
    cmd_roadmap_add(version="v0.14.0", phase_title="Build the thing", status="planned", priority="p1")

    from synlynk import _get_db
    conn = _get_db()
    row = conn.execute(
        "SELECT phase_title, priority FROM roadmap_phases WHERE arc_version=?", ("v0.14.0",)
    ).fetchone()
    conn.close()
    assert row == ("Build the thing", "p1")


def test_cmd_roadmap_add_phase_without_arc_raises(project_dir):
    import pytest
    with pytest.raises(ValueError, match="no roadmap arc"):
        cmd_roadmap_add(version="v9.9.9", phase_title="Orphan phase")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ImportError: cannot import name '_generate_roadmap_md' from 'synlynk.db'`

- [ ] **Step 3: Implement `_generate_roadmap_md()` and `cmd_roadmap_add()`**

Add to `synlynk/db.py` immediately after `_generate_todo_md()` (after line 1347):

```python
def _generate_roadmap_md() -> None:
    """Writes roadmap.md as a generated view of roadmap_arcs/roadmap_phases.
    Post-migration: writes to .synlynk/project-docs/roadmap.md.
    Pre-migration: writes to project-docs/roadmap.md."""
    from synlynk import _docs_dir, _dr_sync, _get_db, _is_migrated, _synlynk_project_docs_dir
    if _is_migrated():
        roadmap_path = os.path.join(_synlynk_project_docs_dir(), "roadmap.md")
        os.makedirs(os.path.dirname(roadmap_path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        roadmap_path = os.path.join(docs_dir, "roadmap.md")

    conn = _get_db()
    arcs = conn.execute(
        "SELECT version, title, status, target_date, notes FROM roadmap_arcs ORDER BY id ASC"
    ).fetchall()
    phases_by_arc = {}
    for arc_version, phase_title, status, priority, story_id, notes in conn.execute(
        "SELECT arc_version, phase_title, status, priority, story_id, notes "
        "FROM roadmap_phases ORDER BY id ASC"
    ).fetchall():
        phases_by_arc.setdefault(arc_version, []).append((phase_title, status, priority, story_id, notes))
    conn.close()

    lines = [
        "# Roadmap (generated - source of truth is state.db)\n",
        "# Edit via: synlynk roadmap add | Do NOT hand-edit this file\n\n",
    ]
    for version, title, status, target_date, notes in arcs:
        date_str = f" (target: {target_date})" if target_date else ""
        lines.append(f"## {version} — {title or version} [{status}]{date_str}\n\n")
        if notes:
            lines.append(f"{notes}\n\n")
        for phase_title, p_status, priority, story_id, p_notes in phases_by_arc.get(version, []):
            check = "x" if p_status == "done" else ("-" if p_status == "deferred" else " ")
            prio = f" ({priority})" if priority else ""
            story = f" <!-- story:{story_id} -->" if story_id else ""
            lines.append(f"- [{check}] {phase_title}{prio}{story}\n")
            if p_notes:
                lines.append(f"  {p_notes}\n")
        lines.append("\n")

    with open(roadmap_path, "w") as f:
        f.writelines(lines)

    if _is_migrated():
        _dr_sync("roadmap.md")


def cmd_roadmap_add(
    version: str,
    title: str = None,
    status: str = "planned",
    target_date: str = None,
    notes: str = None,
    phase_title: str = None,
    priority: str = None,
    story_id: str = None,
) -> None:
    """Add or update a roadmap arc, or a phase within an existing arc.

    If phase_title is None: create/update the arc row identified by `version`.
    If phase_title is set: add a phase to the arc `version` (which must already exist).
    """
    from synlynk import _GREEN, _RESET, _get_db

    conn = _get_db()
    try:
        arc_row = conn.execute(
            "SELECT version FROM roadmap_arcs WHERE version=?", (version,)
        ).fetchone()

        if phase_title is None:
            if arc_row:
                conn.execute(
                    "UPDATE roadmap_arcs SET title=?, status=?, target_date=?, notes=? WHERE version=?",
                    (title, status, target_date, notes, version),
                )
            else:
                conn.execute(
                    "INSERT INTO roadmap_arcs (version, title, status, target_date, notes) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (version, title, status, target_date, notes),
                )
        else:
            if not arc_row:
                raise ValueError(f"no roadmap arc with version={version!r}; create it first")
            conn.execute(
                "INSERT INTO roadmap_phases (arc_version, phase_title, status, priority, story_id, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (version, phase_title, status, priority, story_id, notes),
            )
        conn.commit()
    finally:
        conn.close()

    _generate_roadmap_md()
    label = phase_title if phase_title else (title or version)
    print(f"  {_GREEN}✓{_RESET} Roadmap updated — {version}: {label}")
```

- [ ] **Step 4: Wire the CLI verb**

In `synlynk/cli.py`, add after the `cost_parser` block (~line 595, before the next `subparsers.add_parser` call):

```python
    roadmap_parser = subparsers.add_parser("roadmap", help="Manage the roadmap")
    roadmap_sub = roadmap_parser.add_subparsers(dest="roadmap_action")
    roadmap_add_parser = roadmap_sub.add_parser("add", help="Add or update a roadmap arc or phase")
    roadmap_add_parser.add_argument("--version", required=True)
    roadmap_add_parser.add_argument("--title", default=None)
    roadmap_add_parser.add_argument("--status", default="planned")
    roadmap_add_parser.add_argument("--target-date", default=None, dest="target_date")
    roadmap_add_parser.add_argument("--notes", default=None)
    roadmap_add_parser.add_argument("--phase-title", default=None, dest="phase_title")
    roadmap_add_parser.add_argument("--priority", default=None)
    roadmap_add_parser.add_argument("--story-id", default=None, dest="story_id")
```

In the dispatch section, add after the `elif args.command == "cost":` block (~line 954):

```python
    elif args.command == "roadmap":
        if args.roadmap_action == "add":
            try:
                cmd_roadmap_add(
                    args.version,
                    title=args.title,
                    status=args.status,
                    target_date=args.target_date,
                    notes=args.notes,
                    phase_title=args.phase_title,
                    priority=args.priority,
                    story_id=args.story_id,
                )
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
```

Add `cmd_roadmap_add` to the existing `from synlynk.db import (...)` block at the top of `synlynk/cli.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: 5 passed

- [ ] **Step 6: Manual CLI smoke test**

Run: `python3 -m synlynk roadmap add --version v0.99.0-test --title "smoke test" && cat project-docs/roadmap.md | grep smoke && python3 -m synlynk roadmap add --version v0.99.0-test --phase-title "smoke phase" --status planned && cat project-docs/roadmap.md | grep "smoke phase"`
Expected: both greps print a match. Then manually revert: `git checkout -- project-docs/roadmap.md` (this test run mutates local `state.db` too — acceptable for a smoke test in a throwaway worktree, do not run this against a shared DB).

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py synlynk/cli.py tests/test_db.py
git commit -m "feat: DB-canonicalize roadmap.md via _generate_roadmap_md() + synlynk roadmap add"
```

---

## Task 2: `_generate_costs_md()` + wire `cmd_cost_log()`

**Files:**
- Modify: `synlynk/db.py` (add `_generate_costs_md()`, modify `cmd_cost_log()` at line 1729)
- Test: `tests/test_db.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`:

```python
from synlynk.db import _generate_costs_md, cmd_cost_log


def test_generate_costs_md_creates_file_pre_migration(project_dir):
    from synlynk import _insert_cost_row
    _insert_cost_row(
        session_date="2026-07-25 10:00", agent="claude", model="claude-sonnet-5",
        input_tokens=1000, output_tokens=200, cache_read_tokens=0,
        cost_source="estimated_manual", estimate_basis="cli_manual_entry",
        total_cost_usd=0.0057, notes="test row", story_id=None,
        api_equivalent_usd=0.0057, actual_usd=None, payment_mode=None,
    )

    _generate_costs_md()

    path = os.path.join(str(project_dir), "project-docs", "costs.md")
    assert os.path.exists(path)
    content = open(path).read()
    assert "claude" in content
    assert "test row" in content
    assert "Do NOT hand-edit" in content


def test_cmd_cost_log_regenerates_costs_md(project_dir):
    cmd_cost_log(agent="codex", tokens_in=500, tokens_out=100, note="from cmd_cost_log")

    path = os.path.join(str(project_dir), "project-docs", "costs.md")
    assert os.path.exists(path)
    assert "from cmd_cost_log" in open(path).read()


def test_cmd_cost_log_writes_post_migration_and_dr_syncs(tmp_path, monkeypatch):
    from tests.test_migrate import _setup_migrated
    dr_dir = tmp_path / "dr_mirror"
    dr_dir.mkdir()
    _setup_migrated(tmp_path, monkeypatch)
    import json
    cfg_path = os.path.join(".synlynk", "config.json")
    cfg = json.load(open(cfg_path))
    cfg["dr_sync_path"] = str(dr_dir)
    json.dump(cfg, open(cfg_path, "w"))

    cmd_cost_log(agent="gemini", tokens_in=10, tokens_out=5)

    md_path = os.path.join(".synlynk", "project-docs", "costs.md")
    assert os.path.exists(md_path)
    dr_path = os.path.join(str(dr_dir), "project-docs", "costs.md")
    assert os.path.exists(dr_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v -k costs`
Expected: FAIL — `ImportError: cannot import name '_generate_costs_md'`

- [ ] **Step 3: Implement `_generate_costs_md()` and wire it into `cmd_cost_log()`**

Add to `synlynk/db.py` immediately after `_generate_roadmap_md()`:

```python
def _generate_costs_md() -> None:
    """Writes costs.md as a generated view of cost_entries.
    Post-migration: writes to .synlynk/project-docs/costs.md.
    Pre-migration: writes to project-docs/costs.md."""
    from synlynk import _docs_dir, _dr_sync, _get_db, _is_migrated, _synlynk_project_docs_dir
    if _is_migrated():
        costs_path = os.path.join(_synlynk_project_docs_dir(), "costs.md")
        os.makedirs(os.path.dirname(costs_path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        costs_path = os.path.join(docs_dir, "costs.md")

    conn = _get_db()
    rows = conn.execute(
        "SELECT session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, notes, story_id "
        "FROM cost_entries ORDER BY id ASC"
    ).fetchall()
    conn.close()

    lines = [
        "# Costs (generated - source of truth is state.db)\n",
        "# Edit via: synlynk cost log | Do NOT hand-edit this file\n\n",
        "| Date | Agent | Model | Tokens In | Tokens Out | Cost | Source | Story | Notes |\n",
        "|---|---|---|---|---|---|---|---|---|\n",
    ]
    for session_date, agent, model, tin, tout, cost, source, notes, story_id in rows:
        cost_str = f"${cost:.4f}" if cost is not None else "-"
        lines.append(
            f"| {session_date} | {agent} | {model or '-'} | {tin} | {tout} | "
            f"{cost_str} | {source} | {story_id or '-'} | {notes or ''} |\n"
        )

    with open(costs_path, "w") as f:
        f.writelines(lines)

    if _is_migrated():
        _dr_sync("costs.md")
```

Modify `cmd_cost_log()` (`synlynk/db.py:1729`): add `_generate_costs_md()` and `_dr_sync("costs.md")` after `_insert_cost_row(...)`, before the `print(...)` line:

```python
    _insert_cost_row(
        session_date=ts,
        agent=agent,
        model=model_version,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cache_read_tokens=0,
        cost_source="estimated_manual",
        estimate_basis="cli_manual_entry",
        total_cost_usd=est_cost,
        notes=note,
        story_id=story_id,
        api_equivalent_usd=payment_value.api_equivalent_usd,
        actual_usd=payment_value.actual_usd,
        payment_mode=payment_value.mode,
    )
    _generate_costs_md()
    if _is_migrated_available := True:  # noqa: local import below keeps this simple
        pass
    from synlynk import _dr_sync, _is_migrated
    if _is_migrated():
        _dr_sync("costs.md")
    label = f"story {story_id}" if story_id else f"phase={phase or 'dream/plan'} (no story)"
```

Remove the throwaway `if _is_migrated_available := True: pass` line above — it was left in by mistake during drafting; the real diff is just:

```python
    _insert_cost_row(...)  # unchanged, existing call
    _generate_costs_md()
    from synlynk import _dr_sync, _is_migrated
    if _is_migrated():
        _dr_sync("costs.md")
    label = f"story {story_id}" if story_id else f"phase={phase or 'dream/plan'} (no story)"
```

Also update `exec_command()`'s existing `update_costs()` call path (the one used by `synlynk exec`, distinct from `cmd_cost_log()`) — grep `def update_costs` in `synlynk/__init__.py` and add the same `_generate_costs_md()` + gated `_dr_sync("costs.md")` calls at the end of that function, mirroring what you just did in `cmd_cost_log()`. This is the code path that produced the actual `costs.md` drift incidents (#482, #485), since those were `exec:` rows, not `cost log` rows — skipping this half would leave the original bug unfixed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py synlynk/__init__.py tests/test_db.py
git commit -m "feat: DB-canonicalize costs.md, wire into cmd_cost_log() and update_costs()"
```

---

## Task 3: Un-gate `memory.md` write-through to match `todo.md`'s always-write pattern

**Files:**
- Modify: `synlynk/db.py:1349-1386` (`_write_memory_md()`, `cmd_memory_add()`)
- Test: `tests/test_migrate.py` (append — this repo's existing convention for memory.md tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_migrate.py`:

```python
def test_cmd_memory_add_writes_pre_migration_too(project_dir):
    from synlynk.db import cmd_memory_add
    cmd_memory_add("Test Section", "test body", author="nikhil")

    path = os.path.join(str(project_dir), "project-docs", "memory.md")
    assert os.path.exists(path)
    content = open(path).read()
    assert "Test Section" in content
    assert "test body" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrate.py -v -k test_cmd_memory_add_writes_pre_migration_too`
Expected: FAIL — no `project-docs/memory.md` written (current code only writes when `_is_migrated()` is true)

- [ ] **Step 3: Rewrite `_write_memory_md()` and `cmd_memory_add()` to match `_generate_todo_md()`'s dual-path pattern**

Replace `synlynk/db.py:1349-1386` with:

```python
def _write_memory_md() -> None:
    """Regenerate memory.md from memory_entries table.
    Post-migration: writes to .synlynk/project-docs/memory.md.
    Pre-migration: writes to project-docs/memory.md."""
    from synlynk import _docs_dir, _get_db, _is_migrated, _synlynk_project_docs_dir
    if _is_migrated():
        path = os.path.join(_synlynk_project_docs_dir(), "memory.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        path = os.path.join(docs_dir, "memory.md")

    conn = _get_db()
    rows = conn.execute("SELECT section, body FROM memory_entries ORDER BY id").fetchall()
    conn.close()
    lines = ["# synlynk Memory (generated - source of truth is state.db)\n",
             "# Edit via: synlynk memory add | Do NOT hand-edit this file\n\n"]
    for section, body in rows:
        lines.append(f"## {section}\n\n{body}\n\n")
    with open(path, "w") as f:
        f.writelines(lines)


def cmd_memory_add(section: str, body: str, author: str = None) -> None:
    """Add or update a memory entry. Always writes through to the flat file;
    DR sync only fires once this repo is migrated."""
    from synlynk import _dr_sync, _get_db, _is_migrated
    conn = _get_db()
    existing = conn.execute("SELECT id FROM memory_entries WHERE section=?", (section,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE memory_entries SET body=?, author=?, updated_at=datetime('now') WHERE section=?",
            (body, author, section),
        )
    else:
        conn.execute(
            "INSERT INTO memory_entries (section, body, author) VALUES (?,?,?)",
            (section, body, author),
        )
    conn.commit()
    conn.close()
    _write_memory_md()
    if _is_migrated():
        _dr_sync("memory.md")
```

Note the header text changed (added `# Edit via: synlynk memory add` line matching `todo.md`'s style) — the old header was just `# synlynk Memory\n\n` with no guard banner. Check `tests/test_migrate.py::test_cmd_memory_add_writes_to_db_and_flat_file` and `test_cmd_memory_add_updates_existing_section` still pass with the new header (they should, since they assert on `section`/`body` presence, not exact header text — verify in Step 4).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_migrate.py -v -k memory`
Expected: 3 passed (the new test plus the two pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_migrate.py
git commit -m "fix: memory.md write-through now fires pre-migration too, matching todo.md's pattern"
```

---

## Task 4: `check_budgets()` reads `cost_entries` directly, not `parse_costs_md()`

**Files:**
- Modify: `synlynk/costs.py:756-873` (`check_budgets()`, `parse_costs_md()`)
- Test: `tests/test_synlynk.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_synlynk.py`:

```python
def test_check_budgets_reads_cost_entries_not_markdown(project_dir, capsys, monkeypatch):
    from synlynk import _insert_cost_row
    from synlynk.costs import check_budgets

    # costs.md on disk claims $0 spent; DB says $9.50 — DB must win.
    costs_path = os.path.join(str(project_dir), "project-docs", "costs.md")
    with open(costs_path, "w") as f:
        f.write("# Costs\n\n| Date | Agent | Cost |\n|---|---|---|\n")

    _insert_cost_row(
        session_date="2026-07-25 10:00", agent="claude", model="claude-sonnet-5",
        input_tokens=1, output_tokens=1, cache_read_tokens=0,
        cost_source="estimated_manual", estimate_basis="cli_manual_entry",
        total_cost_usd=9.50, notes=None, story_id=None,
        api_equivalent_usd=9.50, actual_usd=None, payment_mode=None,
    )

    check_budgets()  # project_dir fixture sets limit_usd=10.0 -> 9.50 crosses the 80% warn line

    captured = capsys.readouterr()
    assert "Budget Warning" in captured.out
    assert "9.50" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_synlynk.py -v -k test_check_budgets_reads_cost_entries_not_markdown`
Expected: FAIL — `check_budgets()` currently reads the (empty) `costs.md` via `parse_costs_md()`, so no warning fires and `$0.00` (not `$9.50`) appears

- [ ] **Step 3: Rewrite the spend-total read path in `check_budgets()`**

In `synlynk/costs.py`, replace this line inside `check_budgets()`:

```python
    total_usd, _ = _pkg("parse_costs_md")()
```

with:

```python
    conn = _pkg("_get_db")()
    try:
        total_usd = conn.execute(
            "SELECT COALESCE(SUM(total_cost_usd), 0) FROM cost_entries"
        ).fetchone()[0]
    finally:
        conn.close()
```

Leave `parse_costs_md()` itself unchanged — per spec §7 DoD it's "removed or demoted to a fallback-only path," and it's kept here as the fallback used by `synlynk selftest` scenarios and any other caller still reading the markdown directly (grep `parse_costs_md` across the codebase to confirm no other caller needs updating; if any other caller exists that should also read `cost_entries` directly, note it but do not change it in this task — out of scope, flag it in the PR description instead).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synlynk.py -v -k "budget or costs_md"`
Expected: all pass, including the pre-existing `test_parse_costs_md` (unchanged function, should be untouched by this diff)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_synlynk.py
git commit -m "fix: check_budgets() reads cost_entries directly, closing the DB/markdown split-brain"
```

---

## Task 5: Rotation and archive for roadmap.md / memory.md / costs.md

**Files:**
- Modify: `synlynk/db.py` (add `_rotate_project_doc()` helper, call it from the three `_generate_*_md()` functions)
- Test: `tests/test_db.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db.py`:

```python
def test_rotate_moves_old_cost_entries_to_archive(tmp_path, monkeypatch):
    from tests.test_migrate import _setup_migrated
    from synlynk import _get_db, _insert_cost_row
    from synlynk.db import _generate_costs_md
    _setup_migrated(tmp_path, monkeypatch)

    # 3 entries older than the rotation window, 1 recent — default keep window is tested
    # via a monkeypatched small N so the test doesn't depend on real dates.
    monkeypatch.setattr("synlynk.db._PROJECT_DOC_KEEP_N", 1)

    for i in range(4):
        _insert_cost_row(
            session_date=f"2026-01-0{i+1} 10:00", agent="claude", model="claude-sonnet-5",
            input_tokens=1, output_tokens=1, cache_read_tokens=0,
            cost_source="estimated_manual", estimate_basis="cli_manual_entry",
            total_cost_usd=1.0, notes=f"row{i}", story_id=None,
            api_equivalent_usd=1.0, actual_usd=None, payment_mode=None,
        )

    _generate_costs_md()

    live = open(os.path.join(".synlynk", "project-docs", "costs.md")).read()
    assert "row3" in live  # most recent entry stays live
    assert "row0" not in live  # oldest entry rotated out

    archive_dir = os.path.join(".synlynk", "project-docs", "archive")
    archive_files = os.listdir(archive_dir)
    assert any(f.startswith("costs-") for f in archive_files)
    archived_content = open(os.path.join(archive_dir, [f for f in archive_files if f.startswith("costs-")][0])).read()
    assert "row0" in archived_content

    index_path = os.path.join(archive_dir, "INDEX.md")
    assert os.path.exists(index_path)
    assert "costs-" in open(index_path).read()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v -k test_rotate_moves_old_cost_entries_to_archive`
Expected: FAIL — `AttributeError: module 'synlynk.db' has no attribute '_PROJECT_DOC_KEEP_N'`

- [ ] **Step 3: Implement `_rotate_project_doc()` and wire it into all three generators**

Add to `synlynk/db.py` near the top of the file, alongside other module-level constants:

```python
_PROJECT_DOC_KEEP_N = 50  # default: keep the last ~50 entries live, matches ~1 release cycle of activity
```

Add a shared helper after `_generate_todo_md()`:

```python
def _rotate_project_doc(file_stem: str, all_rows: list, keep_n: int = None) -> list:
    """Splits all_rows into (live_rows, archived_rows) by recency, and if any rows
    were archived, writes/updates project-docs/archive/<file_stem>-<period>.md and
    archive/INDEX.md. Returns the live_rows slice the caller should render.

    all_rows must be ordered oldest-first (same order the caller already queries in).
    Archiving is a no-op (returns all_rows unchanged) if len(all_rows) <= keep_n.
    """
    from synlynk import _is_migrated, _synlynk_project_docs_dir
    n = keep_n if keep_n is not None else _PROJECT_DOC_KEEP_N
    if len(all_rows) <= n:
        return all_rows

    archived_rows = all_rows[:-n]
    live_rows = all_rows[-n:]

    base_dir = _synlynk_project_docs_dir() if _is_migrated() else _docs_dir()
    archive_dir = os.path.join(base_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    period = time.strftime("%Y-H%m")  # coarse period bucket, e.g. 2026-H07
    archive_filename = f"{file_stem}-{period}.md"
    archive_path = os.path.join(archive_dir, archive_filename)
    with open(archive_path, "a") as f:
        for row in archived_rows:
            f.write(str(row) + "\n")

    index_path = os.path.join(archive_dir, "INDEX.md")
    existing_index = ""
    if os.path.exists(index_path):
        existing_index = open(index_path).read()
    if archive_filename not in existing_index:
        with open(index_path, "a") as f:
            if not existing_index:
                f.write("# Archive Index\n\n")
            f.write(f"- [{archive_filename}]({archive_filename}) — {file_stem} entries older than the live window\n")

    return live_rows
```

Wire it into `_generate_costs_md()` (modify the query result handling added in Task 2): replace

```python
    rows = conn.execute(
        "SELECT session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, notes, story_id "
        "FROM cost_entries ORDER BY id ASC"
    ).fetchall()
    conn.close()
```

with:

```python
    rows = conn.execute(
        "SELECT session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, notes, story_id "
        "FROM cost_entries ORDER BY id ASC"
    ).fetchall()
    conn.close()
    rows = _rotate_project_doc("costs", rows)
```

Apply the identical one-line `rows = _rotate_project_doc("<stem>", rows)` insertion (right after the `conn.close()` that follows the SELECT, before the row is used to build `lines`) to `_generate_roadmap_md()` (stem `"roadmap"`, rotating the flattened `arcs` list — note: for roadmap, rotate on `arcs`, not `phases_by_arc`, since arcs are the natural per-release unit) and `_write_memory_md()` (stem `"memory"`, rotating the `rows` list of `(section, body)` tuples).

**`_docs_dir` import note:** `_rotate_project_doc()` calls the module-level `_docs_dir` name directly (not via `from synlynk import`) because it's already imported at module scope in `synlynk/db.py` for other functions — confirm this with `grep "^from synlynk import\|^import" synlynk/db.py` before writing the function; if `_docs_dir` isn't already imported at module scope, add `from synlynk import _docs_dir` inside `_rotate_project_doc()` matching the other functions' local-import style.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: all pass (9 total)

- [ ] **Step 5: Regression-check the non-rotation tests still pass**

Run: `pytest tests/test_db.py tests/test_migrate.py tests/test_synlynk.py -v`
Expected: all pass — rotation must be a no-op for every existing test's small row counts (`_PROJECT_DOC_KEEP_N = 50` default is large enough that no existing fixture data triggers archiving)

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_db.py
git commit -m "feat: rotation/archive for roadmap.md, memory.md, costs.md write-through"
```

---

## Task 6: Mutation guard (warn-and-continue, per spec §2.1/§8.2)

**Files:**
- Modify: `synlynk/db.py` (add `_detect_hand_edit()`, call sites in `generate_context()` and `pr check`)
- Test: `tests/test_db.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`:

```python
from synlynk.db import _detect_hand_edit


def test_detect_hand_edit_no_warning_when_content_matches_regeneration(tmp_path, monkeypatch):
    from tests.test_migrate import _setup_migrated
    from synlynk.db import _generate_costs_md
    _setup_migrated(tmp_path, monkeypatch)
    _generate_costs_md()

    warning = _detect_hand_edit("costs.md")
    assert warning is None


def test_detect_hand_edit_warns_on_genuine_uncommitted_edit(tmp_path, monkeypatch):
    from tests.test_migrate import _setup_migrated
    from synlynk.db import _generate_costs_md
    _setup_migrated(tmp_path, monkeypatch)
    _generate_costs_md()

    path = os.path.join(".synlynk", "project-docs", "costs.md")
    with open(path, "a") as f:
        f.write("\nSOMEONE HAND-EDITED THIS LINE\n")

    warning = _detect_hand_edit("costs.md")
    assert warning is not None
    assert "costs.md" in warning
    assert "hand-edit" in warning.lower()


def test_detect_hand_edit_no_warning_on_pull_then_resync_case(tmp_path, monkeypatch):
    """A file that matches its last git-committed blob but is stale relative to
    current regeneration output (e.g. a teammate's merged change landed via git
    pull, local DB hasn't caught up yet) must NOT be flagged as a hand-edit."""
    import subprocess
    from tests.test_migrate import _setup_migrated
    from synlynk.db import _generate_costs_md
    _setup_migrated(tmp_path, monkeypatch)
    _generate_costs_md()

    path = os.path.join(".synlynk", "project-docs", "costs.md")
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "add", path], check=True)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "seed"], check=True)

    # Simulate: DB gains a new row (regeneration output now differs from the committed
    # file), but the on-disk file itself hasn't been touched since that commit —
    # i.e. it still matches HEAD exactly. This must not warn.
    from synlynk import _insert_cost_row
    _insert_cost_row(
        session_date="2026-07-25 10:00", agent="claude", model="claude-sonnet-5",
        input_tokens=1, output_tokens=1, cache_read_tokens=0,
        cost_source="estimated_manual", estimate_basis="cli_manual_entry",
        total_cost_usd=1.0, notes="not yet regenerated", story_id=None,
        api_equivalent_usd=1.0, actual_usd=None, payment_mode=None,
    )

    warning = _detect_hand_edit("costs.md")
    assert warning is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v -k detect_hand_edit`
Expected: FAIL — `ImportError: cannot import name '_detect_hand_edit'`

- [ ] **Step 3: Implement `_detect_hand_edit()`**

Add to `synlynk/db.py`:

```python
_GENERATORS_BY_FILENAME = {
    "todo.md": "_generate_todo_md",
    "roadmap.md": "_generate_roadmap_md",
    "memory.md": "_write_memory_md",
    "costs.md": "_generate_costs_md",
}


def _detect_hand_edit(filename: str) -> str:
    """Warn-and-continue mutation guard, per spec §2.1 (revised).

    Returns a warning string if `filename` (one of todo.md/roadmap.md/memory.md/
    costs.md) has a genuine uncommitted hand-edit: its working-tree content
    diverges from BOTH (a) the last git-committed blob for that path AND
    (b) what regeneration would currently produce. Returns None otherwise —
    including the case where the file differs from regeneration output only
    because a `git pull` brought in changes the local DB hasn't caught up to
    yet (that case matches the git blob, so it's not flagged).
    """
    import subprocess
    from synlynk import _is_migrated, _synlynk_project_docs_dir

    if filename not in _GENERATORS_BY_FILENAME:
        return None

    base_dir = _synlynk_project_docs_dir() if _is_migrated() else _docs_dir()
    path = os.path.join(base_dir, filename)
    if not os.path.exists(path):
        return None

    with open(path) as f:
        working_tree_content = f.read()

    git_blob_content = None
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            git_blob_content = result.stdout
    except FileNotFoundError:
        pass  # git not available — treat as "no committed blob to compare"

    if git_blob_content is not None and working_tree_content == git_blob_content:
        return None  # matches last commit — not a hand-edit, at worst a pull-then-resync gap

    generator_name = _GENERATORS_BY_FILENAME[filename]
    generator = globals()[generator_name]
    with open(path) as f:
        pre_call_snapshot = f.read()
    generator()
    with open(path) as f:
        regenerated_content = f.read()
    with open(path, "w") as f:
        f.write(pre_call_snapshot)  # restore — this is a read-only probe, not a real regen

    if working_tree_content == regenerated_content:
        return None  # already matches current DB state

    return (
        f"⚠️  {filename} has uncommitted changes that don't match state.db "
        f"(neither the last commit nor a fresh regeneration). It will be "
        f"overwritten the next time it regenerates — copy out anything you "
        f"need first, or run the appropriate `synlynk <noun> add` command "
        f"instead of hand-editing."
    )
```

- [ ] **Step 4: Wire the guard into context injection and `pr check`**

Grep `def generate_context` in `synlynk/__init__.py` and, right before it reads `roadmap.md`/`memory.md`/`costs.md` into the concatenated context, add:

```python
    from synlynk.db import _detect_hand_edit
    for _fname in ("todo.md", "roadmap.md", "memory.md", "costs.md"):
        _warning = _detect_hand_edit(_fname)
        if _warning:
            print(_warning)
```

Grep `def cmd_pr_check` (or equivalent — the function backing `synlynk pr check`) and add the identical loop near its start, before its existing checks run, so a hand-edit warning surfaces during PR review too — per §8.2's confirmed warn-and-continue behavior, this print statement must never be followed by `sys.exit()` or a `return` that skips the rest of `pr check`'s existing checks.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: all pass (12 total)

- [ ] **Step 6: Run full test suite for regressions**

Run: `pytest -v`
Expected: all pass, 0 failures (this touches `generate_context()` and `pr check`, both exercised broadly elsewhere in the suite)

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py synlynk/__init__.py tests/test_db.py
git commit -m "feat: mutation guard warns on genuine hand-edits, ignores pull-then-resync (spec §2.1/§8.2)"
```

---

## Task 7: Run `synlynk migrate` on this repo (spec §8.1)

This is the task that actually closes the loop for `synlynk`'s own repo — everything in Tasks 1-6 is inert here until this runs, exactly like `memory.md`'s partial fix was inert before Task 3.

**Files:**
- No new source files. This task runs the CLI against the real repo and commits the result.

- [ ] **Step 1: Confirm pre-conditions**

Run: `git status --short` (must be clean before migrating — migrate stages/commits changes itself)
Run: `ls .synlynk/.synlynk_migrated 2>&1` — expected: `No such file or directory` (confirms this repo has never migrated)

- [ ] **Step 2: Dry-run first**

Run: `python3 -m synlynk migrate --dry-run`
Expected: prints the resolved `DB_PATH`, reports what would be imported from `project-docs/{todo,memory,roadmap,costs}.md` and `project-docs/devlogs/*.md`, makes no changes. Read the output carefully — if it reports any `0-row import` failures for a non-empty source file, STOP and investigate before proceeding (this is `MigrationImportError`'s fail-loud guard from #126; do not work around it, find out why a source parsed as empty).

- [ ] **Step 3: Run the real migration**

Run: `python3 -m synlynk migrate`
Expected: imports `memory.md` → `memory_entries`, `roadmap.md` → `roadmap_arcs`/`roadmap_phases`, `costs.md` → `cost_entries`, `devlogs/*.md` → `devlog_entries`, copies `project-docs/` → `.synlynk/project-docs/`, `git rm --cached -r project-docs`, adds `project-docs/` to `.gitignore`, writes `.synlynk/.synlynk_migrated`, and commits everything as `chore: synlynk migrate — ...` (this happens automatically inside `cmd_migrate()`, per the reference behavior read in Task setup — do not manually `git add`/`git commit` on top of it).

- [ ] **Step 4: Verify the migration**

Run: `ls .synlynk/.synlynk_migrated && ls .synlynk/project-docs/ && git log -1 --stat`
Expected: sentinel exists; `.synlynk/project-docs/` contains `todo.md`, `roadmap.md`, `memory.md`, `costs.md`, `devlogs/`; the last commit's stat shows `project-docs/` files removed and `.synlynk/project-docs/` files added, plus `.gitignore` modified.

- [ ] **Step 5: Live round-trip verification (manual, not a unit test)**

Run each of these against the real, now-migrated repo and confirm the effect by reading the resulting file:

```bash
python3 -m synlynk cost log --agent claude --tokens-in 100 --tokens-out 50 --note "PR1 migrate verification"
tail -5 .synlynk/project-docs/costs.md   # expect: the new row is present

python3 -m synlynk roadmap add --version v0.13.0 --title "State Engine Tier 1" --status in_progress
grep "State Engine Tier 1" .synlynk/project-docs/roadmap.md   # expect: match

python3 -m synlynk memory add "PR1 verification" "confirming write-through works post-migrate" --author nikhilsoman
grep "PR1 verification" .synlynk/project-docs/memory.md   # expect: match
```

If `synlynk memory add` has no CLI verb yet (Task 3 only fixed the underlying function, not necessarily a CLI wrapper — check `synlynk/cli.py` for an existing `memory` subparser before running this; if none exists, call `cmd_memory_add()` directly via `python3 -c "from synlynk.db import cmd_memory_add; cmd_memory_add('PR1 verification', 'confirming write-through works post-migrate', author='nikhilsoman')"` instead, and separately flag in the PR description that a `synlynk memory add` CLI verb doesn't exist and should be a fast-follow, since it's out of this plan's originally-scoped tasks).

- [ ] **Step 6: Clean up the verification data**

The three verification writes in Step 5 are real rows in the migrated `state.db` and real lines in the regenerated files — decide with the PR reviewer whether to keep them (they're harmless, truthful records: "PR1 shipped and was verified") or remove them. Recommended: **keep them** — they're accurate history, not test pollution, and removing them would require hand-editing a file this very PR just made DB-canonical (contradicting the PR's own point).

- [ ] **Step 7: Run full test suite one more time**

Run: `pytest -v`
Expected: all pass. This confirms the migration didn't break anything that depends on `project-docs/` being at the repo root pre-migration (check any test that hardcodes that path assumption — `tests/conftest.py`'s `project_dir` fixture builds a fresh `tmp_path` per test, so it's unaffected by this repo's own migration state, but grep for any test or CLI code that hardcodes `"project-docs"` outside of `_docs_dir()` as an extra safety check).

- [ ] **Step 8: Final commit (if Step 5's verification writes need a wrap-up commit)**

The migration itself already commits in Step 3. If Step 5's verification commands didn't get swept into that commit (they run after it), commit them separately:

```bash
git add .synlynk/project-docs/costs.md .synlynk/project-docs/roadmap.md .synlynk/project-docs/memory.md
git commit -m "chore: PR1 post-migrate write-through verification (real rows, kept per plan Task 7 Step 6)"
```

---

## Self-Review

**1. Spec coverage** (against `docs/superpowers/specs/2026-07-20-state-engine-tiered-design.md` §2/§7/§8):
- "roadmap.md/memory.md/costs.md regenerate from state.db on every mutating command" → Tasks 1, 2, 3. ✅
- "check_budgets() switches to cost_entries" → Task 4. ✅
- "Rotation policy... archive/INDEX.md" → Task 5. ✅
- "Mutation guard... warn loudly... including a test for the pull-then-resync case" → Task 6, specifically `test_detect_hand_edit_no_warning_on_pull_then_resync_case`. ✅
- "§8.1: this repo runs synlynk migrate as part of PR1, with live round-trip verification" → Task 7. ✅
- "§8.3: dr_sync_path extended to fire from all three write-through paths, documentation-only, not configured for this repo" → Tasks 1/2/3 each call `_dr_sync(<filename>)` when migrated; Task 7 does not set `dr_sync_path` in this repo's config. ✅
- PR2 (`vizor-workspace-map.json`, `viz.py` live query) and PR3 (scoped dispatch context, `files`/`symbols` tables) are explicitly out of scope for this plan — separate plans, per the spec's own PR1→PR2→PR3 sequencing.

**2. Placeholder scan:** No TBD/TODO markers. Task 2 Step 3 originally drafted a stray `if _is_migrated_available := True: pass` line while explaining the diff — caught and removed in the same step, with the clean version shown immediately after as the actual instruction.

**3. Type consistency:** `_generate_roadmap_md`, `_generate_costs_md`, `_write_memory_md`, `_generate_todo_md` (existing) all share the same zero-arg, zero-return signature. `_rotate_project_doc(file_stem: str, all_rows: list, keep_n: int = None) -> list` is used identically across Task 5's three call sites. `_detect_hand_edit(filename: str) -> str | None` matches its two call sites in Task 6 Step 4. `cmd_roadmap_add()`'s keyword args (`version`, `title`, `status`, `target_date`, `notes`, `phase_title`, `priority`, `story_id`) match the CLI parser's `dest=` names exactly in Task 1 Step 4.
