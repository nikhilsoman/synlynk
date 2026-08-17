# Workspace Context Write-Through (#936) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `state.db` authoritative for devlog entries and decision records (same precedent already established for roadmap/todo), and fix every migration-unaware `_docs_dir()` read across the 5-file audit scope so post-migration reads resolve the correct path.

**Architecture:** Mirror the existing `cmd_memory_add()`/`_write_memory_md()` pattern in `synlynk/db.py` exactly: DB write+commit first, then unconditional flat-file regeneration (migration-aware path resolution), then `_dr_sync()` gated on migration. Add a new `decisions` table and `cmd_decision_record()`/`_write_decision_record_md()` pair following that pattern. Rewire `checkpoint()` (`__init__.py`) and `cmd_decide()` (`team.py`) to call through the DB-backed functions instead of doing direct file I/O. Fix the three read-only migration-unaware call sites (`doctor.py`, `sentinel.py`) to branch on `_is_migrated()`.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest.

---

## Task 1: `decisions` table schema

**Files:**
- Modify: `synlynk/db.py:576-588` (inside the `executescript` block in `_migrate_db`, right after the `devlog_entries` table + its indexes)
- Test: `tests/test_migrate.py` (new test, append to end of file)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_migrate.py`:

```python
def test_decisions_table_created_idempotently(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    conn = synlynk._get_db()
    conn.close()
    conn = synlynk._get_db()  # second call must not raise
    cols = {row[1] for row in conn.execute("PRAGMA table_info(decisions)")}
    conn.close()
    assert cols == {
        "decision_id", "topic", "date", "panel", "status", "inputs",
        "synthesis", "decision_text", "signature", "created_at",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrate.py::test_decisions_table_created_idempotently -v`
Expected: FAIL with `sqlite3.OperationalError: no such table: decisions` (or an empty `cols` set assertion failure)

- [ ] **Step 3: Add the table to the schema**

In `synlynk/db.py`, in the `executescript` block that starts at line 516 (the one containing `devlog_entries`), insert the new table right after the `devlog_entries` indexes (currently lines 587-588: `CREATE INDEX IF NOT EXISTS idx_devlog_author ...` / `idx_devlog_date ...`) and before `CREATE TABLE IF NOT EXISTS members`:

```sql
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id   TEXT PRIMARY KEY,
            topic         TEXT NOT NULL,
            date          TEXT NOT NULL,
            panel         TEXT NOT NULL,
            status        TEXT NOT NULL,
            inputs        TEXT NOT NULL,
            synthesis     TEXT NOT NULL,
            decision_text TEXT NOT NULL,
            signature     TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );
```

So the surrounding block reads:

```sql
        CREATE INDEX IF NOT EXISTS idx_devlog_author ON devlog_entries(author);
        CREATE INDEX IF NOT EXISTS idx_devlog_date   ON devlog_entries(entry_date);
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id   TEXT PRIMARY KEY,
            topic         TEXT NOT NULL,
            date          TEXT NOT NULL,
            panel         TEXT NOT NULL,
            status        TEXT NOT NULL,
            inputs        TEXT NOT NULL,
            synthesis     TEXT NOT NULL,
            decision_text TEXT NOT NULL,
            signature     TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS members (
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrate.py::test_decisions_table_created_idempotently -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_migrate.py
git commit -m "feat(db): add decisions table schema (#936)"
```

---

## Task 2: `cmd_decision_record()` + `_write_decision_record_md()` in `db.py`

**Files:**
- Modify: `synlynk/db.py` (add two new functions right after `cmd_devlog_append`, which currently ends at line 1885 — i.e. insert before `def _import_todo_to_stories` at line 1887)
- Test: `tests/test_migrate.py` (new tests, append to end)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrate.py`:

```python
def test_cmd_decision_record_writes_db_and_md_json_when_migrated(tmp_path, monkeypatch):
    backup = _setup_migrated(tmp_path, monkeypatch)
    synlynk.cmd_decision_record(
        "dec-abc12345", "Relay ownership", "2026-08-18", ["claude", "agy"],
        {"claude": "Claude's input", "agy": "Agy's input"},
        "Synthesis text", "Decision: use option B.",
    )
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT topic, status, decision_text FROM decisions WHERE decision_id=?",
        ("dec-abc12345",)
    ).fetchone()
    conn.close()
    assert row == ("Relay ownership", "approved", "Decision: use option B.")

    decisions_dir = backup / "decisions"
    md_files = list(decisions_dir.glob("*.md"))
    json_files = list(decisions_dir.glob("*.json"))
    assert len(md_files) == 1
    assert len(json_files) == 1
    import json as _json
    record = _json.loads(json_files[0].read_text())
    assert record["decision_id"] == "dec-abc12345"
    assert record["decision"] == "Decision: use option B."
    md_content = md_files[0].read_text()
    assert "<!-- generated - source of truth is state.db -->" in md_content
    assert "### claude" in md_content
    assert "### agy" in md_content
    assert "## Synthesis" in md_content
    assert "> Signatures:" in md_content


def test_cmd_decision_record_writes_pre_migration_too(project_dir):
    from synlynk.db import cmd_decision_record

    cmd_decision_record(
        "dec-def67890", "DB choice", "2026-08-18", ["claude"],
        {"claude": "input text"}, "synthesis text", "Decision: yes.",
    )

    decisions_dir = project_dir / "project-docs" / "decisions"
    md_files = list(decisions_dir.glob("*.md"))
    assert len(md_files) == 1
    assert "DB choice" in md_files[0].read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_migrate.py::test_cmd_decision_record_writes_db_and_md_json_when_migrated tests/test_migrate.py::test_cmd_decision_record_writes_pre_migration_too -v`
Expected: FAIL with `AttributeError: module 'synlynk' has no attribute 'cmd_decision_record'` (or `ImportError` for the second test's `from synlynk.db import cmd_decision_record`)

- [ ] **Step 3: Write the implementation**

In `synlynk/db.py`, insert immediately after `cmd_devlog_append` (which ends at line 1885) and before `def _import_todo_to_stories` (line 1887):

```python
def _write_decision_record_md(decision_id: str) -> None:
    """Regenerate the .md + .json sidecar for a decision from the decisions table.
    Post-migration: writes to .synlynk/project-docs/decisions/.
    Pre-migration: writes to project-docs/decisions/."""
    from synlynk import _docs_dir, _get_db, _is_migrated, _synlynk_project_docs_dir

    conn = _get_db()
    row = conn.execute(
        "SELECT decision_id, topic, date, panel, status, inputs, synthesis, "
        "decision_text, signature FROM decisions WHERE decision_id=?",
        (decision_id,)
    ).fetchone()
    conn.close()
    decision_id, topic, date, panel_json, status, inputs_json, synthesis, decision_text, signature = row
    panel = json.loads(panel_json)
    inputs = json.loads(inputs_json)

    if _is_migrated():
        decisions_dir = os.path.join(_synlynk_project_docs_dir(), "decisions")
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        decisions_dir = os.path.join(docs_dir, "decisions")
    os.makedirs(decisions_dir, exist_ok=True)

    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:40].strip('-')
    base = os.path.join(decisions_dir, f"{date}-{slug}")

    record = {
        "decision_id": decision_id,
        "topic": topic,
        "date": date,
        "panel": panel,
        "status": status,
        "inputs": inputs,
        "synthesis": synthesis,
        "decision": decision_text,
    }
    if signature:
        record["signature"] = signature

    with open(f"{base}.json", "w") as f:
        json.dump(record, f, indent=2)

    panel_inputs_md = ""
    for member, text in inputs.items():
        panel_inputs_md += f"\n### {member}\n{text}\n"

    md_content = (
        f"<!-- generated - source of truth is state.db -->\n"
        f"---\n"
        f"decision_id: {decision_id}\n"
        f"topic: \"{topic}\"\n"
        f"date: {date}\n"
        f"panel: [{', '.join(panel)}]\n"
        f"status: {status}\n"
        f"---\n\n"
        f"## Topic\n{topic}\n\n"
        f"## Panel Inputs\n{panel_inputs_md}\n"
        f"## Synthesis\n{synthesis}\n\n"
        f"## Decision\n{decision_text}\n\n"
        f"> Signatures: see {date}-{slug}.json\n"
    )
    with open(f"{base}.md", "w") as f:
        f.write(md_content)


def cmd_decision_record(decision_id: str, topic: str, date: str, panel: list,
                         inputs: dict, synthesis: str, decision_text: str) -> None:
    """Insert a decision row into state.db, then write through to the flat file pair."""
    from synlynk import _dr_sync, _get_db, _is_migrated
    from synlynk.team import _sign_capability_rating

    record_for_signing = {
        "decision_id": decision_id, "topic": topic, "date": date, "panel": panel,
        "status": "approved", "inputs": inputs, "synthesis": synthesis,
        "decision": decision_text,
    }
    signature = _sign_capability_rating(record_for_signing)
    if not signature:
        print("  ⚠ No identity key — decision written unsigned. "
              "Run `synlynk identity init` first.")

    conn = _get_db()
    conn.execute(
        "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, "
        "synthesis, decision_text, signature) VALUES (?,?,?,?,?,?,?,?,?)",
        (decision_id, topic, date, json.dumps(panel), "approved", json.dumps(inputs),
         synthesis, decision_text, signature)
    )
    conn.commit()
    conn.close()

    _write_decision_record_md(decision_id)
    if _is_migrated():
        slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:40].strip('-')
        _dr_sync(f"decisions/{date}-{slug}.md")
        _dr_sync(f"decisions/{date}-{slug}.json")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_migrate.py::test_cmd_decision_record_writes_db_and_md_json_when_migrated tests/test_migrate.py::test_cmd_decision_record_writes_pre_migration_too -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_migrate.py
git commit -m "feat(db): add cmd_decision_record write-through (#936)"
```

---

## Task 3: Rewire `team.py`'s `cmd_decide()` to use `cmd_decision_record()`

**Files:**
- Modify: `synlynk/team.py:489-614` (delete `_write_decision_record`, rewire the tail of `cmd_decide`)
- Modify: `synlynk/__init__.py:3950-3977` (add `cmd_decision_record` to the `from synlynk.db import (...)` block)
- Test: `tests/test_synlynk.py` (extend existing decide tests, they already exist at lines 5787-5841)

- [ ] **Step 1: Write the failing test**

Add this new test to `tests/test_synlynk.py`, right after `test_decide_json_has_decision_id` (currently ending at line 5820):

```python
def test_decide_record_writes_decisions_row(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "_run_agent_sync",
        lambda agent, prompt, timeout=120: f"Analysis from {agent}. Decision: use option B.")
    synlynk.cmd_decide("Relay ownership", panel=["claude", "agy"], record=True)
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT topic, status FROM decisions WHERE topic=?", ("Relay ownership",)
    ).fetchone()
    conn.close()
    assert row == ("Relay ownership", "approved")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_synlynk.py::test_decide_record_writes_decisions_row -v`
Expected: FAIL — either `sqlite3.OperationalError: no such table: decisions` was already fixed in Task 1, so this actually fails on `assert row == (...)` because `row` is `None` (the current `cmd_decide` never inserts into `decisions`)

- [ ] **Step 3: Add `cmd_decision_record` to the `__init__.py` import block**

In `synlynk/__init__.py`, in the `from synlynk.db import (` block starting at line 3950, add `cmd_decision_record,` next to `cmd_devlog_append,`:

```python
from synlynk.db import (  # noqa: E402
    _detect_hand_edit,
    _generate_costs_md,
    _generate_todo_md,
    _import_todo_to_stories,
    _migrate_db,
    _migrate_import,
    _insert_cost_row,
    _parse_costs_md,
    _parse_devlog_file,
    _parse_memory_md,
    _parse_roadmap_md,
    _parse_todo_metadata,
    cmd_decision_record,
    cmd_devlog_append,
    cmd_cost_log,
    cmd_audit_docs,
    cmd_remediation_log,
    cmd_roadmap_add,
    cmd_memory_add,
    cmd_migrate,
    cmd_pr_check,
    cmd_score_add,
    cmd_score_attest,
    cmd_score_list,
    cmd_story_create,
    cmd_story_draft,
    cmd_story_list,
    cmd_story_ready,
)
```

- [ ] **Step 4: Rewire `cmd_decide()` and delete `_write_decision_record()` in `team.py`**

In `synlynk/team.py`, delete the entire `_write_decision_record` function (lines 489-537, from `def _write_decision_record(` through the closing of that function right before `def cmd_decide`).

Then replace the tail of `cmd_decide` (currently lines 597-614):

```python
    _pkg("_check_upstream_divergence")()

    decision_id = "dec-" + hashlib.md5(
        f"{topic}{time.time()}".encode()
    ).hexdigest()[:8]

    today = time.strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:40].strip('-')

    decisions_dir = os.path.join(_pkg("_docs_dir")(), "decisions")
    os.makedirs(decisions_dir, exist_ok=True)

    _write_decision_record(
        decision_id, topic, today, panel,
        inputs, synthesis, decision_text, decisions_dir, slug
    )

    print(f"  {_GREEN}✓{_RESET} Decision recorded: {decisions_dir}/{today}-{slug}.md")
```

with:

```python
    _pkg("_check_upstream_divergence")()

    decision_id = "dec-" + hashlib.md5(
        f"{topic}{time.time()}".encode()
    ).hexdigest()[:8]

    today = time.strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:40].strip('-')

    _pkg("cmd_decision_record")(
        decision_id, topic, today, panel, inputs, synthesis, decision_text
    )

    print(f"  {_GREEN}✓{_RESET} Decision recorded: {today}-{slug}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_synlynk.py -k test_decide -v`
Expected: PASS for all of `test_decide_dry_run_no_files`, `test_decide_record_writes_md_and_json`, `test_decide_json_has_decision_id`, `test_decide_md_contains_panel_inputs`, `test_decide_all_agents_fail_exits`, `test_decide_record_writes_decisions_row`

- [ ] **Step 6: Fix `_build_team_digest()`'s migration-unaware `devlogs_dir` read**

`_build_team_digest()` (`synlynk/team.py:617-621`) reads `devlogs_dir` via raw `_pkg("_docs_dir")()` — read-only, but post-migration it would silently read the stale pre-migration path and show an incomplete/stale team digest (per the spec's file classification table for `team.py`). Fix it the same way as Task 5/6's read-only fixes.

Write the failing test first — add to `tests/test_synlynk.py` right after `test_build_team_digest_reads_devlogs` (currently ending at line 5684):

```python
def test_build_team_digest_reads_devlogs_when_migrated(tmp_path, monkeypatch):
    import synlynk, os
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / ".synlynk_migrated").write_text("2026-07-01")
    migrated_devlogs = tmp_path / ".synlynk" / "project-docs" / "devlogs"
    migrated_devlogs.mkdir(parents=True)
    (migrated_devlogs / "alice.md").write_text(
        "# Devlog — @alice\n\n## 2026-06-20\nDid stuff.\n"
    )
    digest = synlynk._build_team_digest()
    users = [m["user"] for m in digest["members"]]
    assert "alice" in users
```

Run: `pytest tests/test_synlynk.py::test_build_team_digest_reads_devlogs_when_migrated -v`
Expected: FAIL — `"alice" not in users` (current code reads raw `_docs_dir()` = `"project-docs"`, which has no `devlogs/` in this fixture)

In `synlynk/team.py`, replace line 621:

```python
    devlogs_dir = os.path.join(_pkg("_docs_dir")(), "devlogs")
```

with:

```python
    docs_root = _pkg("_synlynk_project_docs_dir")() if _pkg("_is_migrated")() else _pkg("_docs_dir")()
    devlogs_dir = os.path.join(docs_root, "devlogs")
```

Run: `pytest tests/test_synlynk.py -k build_team_digest -v`
Expected: PASS for `test_build_team_digest_reads_devlogs`, `test_build_team_digest_no_db`, `test_build_team_digest_includes_stories`, `test_build_team_digest_top_todo`, `test_build_team_digest_reads_devlogs_when_migrated`

- [ ] **Step 7: Commit**

```bash
git add synlynk/team.py synlynk/__init__.py tests/test_synlynk.py
git commit -m "refactor(team): route cmd_decide through cmd_decision_record write-through; fix team digest migration-awareness (#936)"
```

---

## Task 4: Rewire `checkpoint()` to write devlogs through the DB

This task requires extending `_write_devlog_file()`/`cmd_devlog_append()` in `db.py` with a pre-migration branch (mirroring `_write_memory_md`'s existing pattern) before `checkpoint()` can be safely rewired — otherwise pre-migration callers of `checkpoint()` (which is what all existing tests exercise, via the non-migrated `project_dir` fixture) would stop writing any devlog file at all, since today `cmd_devlog_append()` only calls `_write_devlog_file()` when `_is_migrated()` is true.

**Files:**
- Modify: `synlynk/db.py:1846-1885` (`_write_devlog_file`, `cmd_devlog_append`)
- Modify: `synlynk/__init__.py:2942-2974` (`checkpoint`)
- Test: `tests/test_migrate.py` (new pre-migration devlog test), `tests/test_synlynk.py` (new DB-row assertion on checkpoint)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrate.py`:

```python
def test_write_devlog_file_pre_migration(project_dir):
    from synlynk.db import cmd_devlog_append

    cmd_devlog_append("nikhil", "2026-08-18", "### Resolved (checkpoint)\n- Ship the thing\n")

    path = project_dir / "project-docs" / "devlogs" / "nikhil.md"
    assert path.exists()
    assert "Ship the thing" in path.read_text()
```

Add this new test to `tests/test_synlynk.py`, right after `test_checkpoint_appends_to_devlog` (currently ending at line 1365):

```python
def test_checkpoint_writes_devlog_entries_row(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [x] Finished feature <!-- id: 5 -->\n"
    )
    synlynk.checkpoint()
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT author, body FROM devlog_entries WHERE author=?", ("nikhilsoman",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert "Finished feature" in row[1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_migrate.py::test_write_devlog_file_pre_migration tests/test_synlynk.py::test_checkpoint_writes_devlog_entries_row -v`
Expected: `test_write_devlog_file_pre_migration` FAILs with `AssertionError: assert False` (path doesn't exist — today `cmd_devlog_append` skips the file write pre-migration). `test_checkpoint_writes_devlog_entries_row` FAILs with `assert row is not None` failing (today `checkpoint()` never touches `devlog_entries`).

- [ ] **Step 3: Extend `_write_devlog_file` with a pre-migration branch, and make `cmd_devlog_append` write unconditionally**

In `synlynk/db.py`, replace lines 1846-1885 (`_write_devlog_file` through the end of `cmd_devlog_append`):

```python
def _write_devlog_file(author: str) -> None:
    """Regenerate devlogs/<author>.md from devlog_entries.
    Post-migration: writes to .synlynk/project-docs/devlogs/.
    Pre-migration: writes to project-docs/devlogs/."""
    from synlynk import _docs_dir, _get_db, _is_migrated, _synlynk_project_docs_dir
    conn = _get_db()
    rows = conn.execute(
        "SELECT entry_date, session_title, body FROM devlog_entries "
        "WHERE author=? ORDER BY entry_date ASC",
        (author,)
    ).fetchall()
    conn.close()
    lines = [f"# {author} Devlog\n\n"]
    for entry_date, session_title, body in rows:
        header = f"## {entry_date}"
        if session_title:
            header += f" — {session_title}"
        lines.append(f"{header}\n\n{body}\n\n")

    if _is_migrated():
        devlog_dir = os.path.join(_synlynk_project_docs_dir(), "devlogs")
    else:
        docs_dir = _docs_dir()
        if not os.path.exists(docs_dir):
            return
        devlog_dir = os.path.join(docs_dir, "devlogs")
    os.makedirs(devlog_dir, exist_ok=True)
    with open(os.path.join(devlog_dir, f"{author}.md"), "w") as f:
        f.writelines(lines)

def cmd_devlog_append(author: str, entry_date: str, body: str,
                      session_title: str = None, session_id: str = None,
                      goal_id: str = None) -> None:
    """Append a devlog entry to DB. Always writes through to the flat file;
    DR sync only fires once this repo is migrated."""
    from synlynk import _dr_sync, _get_db, _is_migrated
    from synlynk.session import _read_active_session
    if session_id is None:
        session_id = _read_active_session()
    conn = _get_db()
    conn.execute(
        "INSERT INTO devlog_entries (author, entry_date, session_title, session_id, goal_id, body) "
        "VALUES (?,?,?,?,?,?)",
        (author, entry_date, session_title, session_id, goal_id, body)
    )
    conn.commit()
    conn.close()
    _write_devlog_file(author)
    if _is_migrated():
        _dr_sync(f"devlogs/{author}.md")
```

- [ ] **Step 4: Run the pre-migration devlog test to verify it passes**

Run: `pytest tests/test_migrate.py::test_write_devlog_file_pre_migration tests/test_migrate.py::test_cmd_devlog_append_writes_entry -v`
Expected: PASS for both (the migrated-case test must keep passing too — it's unaffected since `_is_migrated()` is true in that fixture)

- [ ] **Step 5: Rewire `checkpoint()` in `synlynk/__init__.py`**

Replace lines 2942-2974 (the full `checkpoint()` function up through the `_archive_old_devlog_entries`/`generate_context()` calls):

```python
def checkpoint() -> None:
    """Archives done tasks, refreshes context, and emits a telemetry event."""
    set_state("active")
    _check_upstream_divergence()
    username = get_username()
    canonical_id = _resolve_member_id(username)
    todo_path = "project-docs/todo.md"
    if _is_migrated():
        devlog_path = os.path.join(_synlynk_project_docs_dir(), "devlogs", f"{canonical_id}.md")
    else:
        devlog_path = os.path.join(_docs_dir(), "devlogs", f"{canonical_id}.md")

    # Collect resolved tasks (done/superseded/absorbed) and keep the rest
    completed, active_lines = [], []
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if re.match(r'\s*-\s*\[(x|~|>)\]', line, re.IGNORECASE):
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[(x|~|>)\]\s*', '', line, flags=re.IGNORECASE).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    completed.append({"id": id_m.group(1) if id_m else None, "text": text})
                else:
                    active_lines.append(line)

    # Write resolved tasks through to the devlog (DB row + regenerated flat file)
    if completed:
        body_lines = ["### Resolved (checkpoint)"]
        for task in completed:
            body_lines.append(f"- {task['text']}")
        cmd_devlog_append(canonical_id, time.strftime('%Y-%m-%d'), "\n".join(body_lines) + "\n")
        with open(todo_path, "w") as f:
            f.writelines(active_lines)

    _archive_old_devlog_entries(devlog_path)
    generate_context()
```

Everything after `generate_context()` in the original function (the telemetry event, budget summary, print statements) is unchanged — do not modify it, only the block above it.

- [ ] **Step 6: Run all checkpoint tests to verify they pass**

Run: `pytest tests/test_synlynk.py -k checkpoint tests/test_checkpoint_identity.py -v`
Expected: PASS for `test_checkpoint_archives_done_tasks`, `test_checkpoint_appends_to_devlog`, `test_checkpoint_emits_telemetry_event`, `test_checkpoint_idempotent_when_no_done_tasks`, `test_checkpoint_writes_devlog_entries_row`, `test_checkpoint_writes_to_canonical_member_path`

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py synlynk/__init__.py tests/test_migrate.py tests/test_synlynk.py
git commit -m "refactor: rewire checkpoint() devlog writes through state.db (#936)"
```

---

## Task 5: Fix `doctor.py`'s `_hc_docs_dir()` migration-awareness

**Files:**
- Modify: `synlynk/doctor.py:98-113`
- Test: `tests/test_synlynk.py` (new migrated-fixture test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_synlynk.py`, right after `test_hc_docs_dir_warn_missing_files` (currently ending at line 6950):

```python
def test_hc_docs_dir_resolves_migrated_path(tmp_path, monkeypatch):
    import synlynk, os
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / ".synlynk_migrated").write_text("2026-07-01")
    (tmp_path / ".synlynk" / "config.json").write_text('{"project_docs_dir": "project-docs"}')
    migrated_docs = tmp_path / ".synlynk" / "project-docs"
    migrated_docs.mkdir()
    for fname in ["roadmap.md", "todo.md", "memory.md"]:
        (migrated_docs / fname).write_text("")
    # Old pre-migration path does NOT exist — if _hc_docs_dir() still reads
    # the raw _docs_dir(), this must fail/warn instead of reporting ok.
    result = synlynk._hc_docs_dir()
    assert result.status == "ok"
    assert str(migrated_docs) in result.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_synlynk.py::test_hc_docs_dir_resolves_migrated_path -v`
Expected: FAIL — `result.status == "warn"` (current code resolves raw `_docs_dir()` = `"project-docs"`, which doesn't exist in this fixture, so all three required files are reported missing)

- [ ] **Step 3: Write the implementation**

In `synlynk/doctor.py`, replace lines 98-113 (`_hc_docs_dir`, its `try`/`except` docs resolution):

```python
def _hc_docs_dir() -> HealthCheck:
    try:
        if _pkg("_is_migrated")():
            docs = _pkg("_synlynk_project_docs_dir")()
        else:
            docs = _pkg("_docs_dir")()
    except Exception:
        return HealthCheck(
            "docs_dir",
            "warn",
            "Could not resolve docs directory (project may not be initialized)",
            fix="Run: synlynk init",
        )
    required = ["roadmap.md", "todo.md", "memory.md"]
    missing = [f for f in required if not os.path.exists(os.path.join(docs, f))]
    if not missing:
        return HealthCheck("docs_dir", "ok", f"project-docs complete ({docs})")
    return HealthCheck(
        "docs_dir",
        "warn",
        f"project-docs missing: {', '.join(missing)}",
```

(The rest of the function after this — the `fix=` argument closing the `warn` `HealthCheck` — is unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_synlynk.py::test_hc_docs_dir_resolves_migrated_path tests/test_synlynk.py::test_hc_docs_dir_ok tests/test_synlynk.py::test_hc_docs_dir_warn_missing_files -v`
Expected: PASS for all three

- [ ] **Step 5: Commit**

```bash
git add synlynk/doctor.py tests/test_synlynk.py
git commit -m "fix(doctor): resolve migrated docs path in _hc_docs_dir (#936)"
```

---

## Task 6: Fix `sentinel.py`'s duplicate `_docs_dir()` and `_check_costs_freshness()` migration-awareness

**Files:**
- Modify: `synlynk/sentinel.py:1-60` (delete the private `_docs_dir`, fix `_check_costs_freshness`)
- Test: `tests/test_synlynk.py` (new migrated-fixture test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_synlynk.py`, right after `test_check_costs_freshness_silent_when_fresh` (currently ending at line 1310):

```python
def test_check_costs_freshness_resolves_migrated_path(tmp_path, monkeypatch, capsys):
    import synlynk, os, time
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / ".synlynk_migrated").write_text("2026-07-01")
    migrated_docs = tmp_path / ".synlynk" / "project-docs"
    migrated_docs.mkdir()
    costs_path = migrated_docs / "costs.md"
    costs_path.write_text("| date | ... |\n")
    old_time = time.time() - 7200
    os.utime(str(costs_path), (old_time, old_time))
    synlynk._check_costs_freshness()
    captured = capsys.readouterr()
    assert "costs.md not updated" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_synlynk.py::test_check_costs_freshness_resolves_migrated_path -v`
Expected: FAIL — current code checks `project-docs/costs.md` (doesn't exist in this fixture), so `os.path.exists(costs_file)` is false and the function returns silently, meaning `"costs.md not updated"` never prints

- [ ] **Step 3: Write the implementation**

In `synlynk/sentinel.py`, delete the private `_docs_dir()` function (lines 24-32):

```python
def _docs_dir() -> str:
    """Returns the configured project docs directory (defaults to 'project-docs')."""
    config_file = ".synlynk/config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                return json.load(f).get("project_docs_dir", "project-docs")
        except (json.JSONDecodeError, IOError):
            pass
    return "project-docs"
```

Replace `_check_costs_freshness()` (lines 54-59):

```python
def _check_costs_freshness() -> None:
    """Warns if costs.md hasn't been updated in the current session (>1 hour)."""
    from synlynk import _docs_dir, _is_migrated, _synlynk_project_docs_dir
    docs = _synlynk_project_docs_dir() if _is_migrated() else _docs_dir()
    costs_file = os.path.join(docs, "costs.md")
    if not os.path.exists(costs_file):
        return
    if time.time() - os.path.getmtime(costs_file) > 3600:
        print("  ⚠ costs.md not updated this session — AI may have missed logging")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synlynk.py -k costs_freshness -v`
Expected: PASS for `test_check_costs_freshness_warns_when_stale`, `test_check_costs_freshness_silent_when_fresh`, `test_check_costs_freshness_resolves_migrated_path`

- [ ] **Step 5: Verify nothing else imports `sentinel._docs_dir` directly**

Run: `grep -rn "sentinel\._docs_dir\|from synlynk.sentinel import.*_docs_dir" synlynk/ tests/`
Expected: no output (already confirmed during investigation — no other consumer exists)

- [ ] **Step 6: Commit**

```bash
git add synlynk/sentinel.py tests/test_synlynk.py
git commit -m "fix(sentinel): remove duplicate _docs_dir, resolve migrated costs.md path (#936)"
```

---

## Task 7: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass (baseline before this plan was `2038 passed, 2 skipped`; this plan adds 9 new tests — `test_decisions_table_created_idempotently`, `test_cmd_decision_record_writes_db_and_md_json_when_migrated`, `test_cmd_decision_record_writes_pre_migration_too`, `test_decide_record_writes_decisions_row`, `test_build_team_digest_reads_devlogs_when_migrated`, `test_write_devlog_file_pre_migration`, `test_checkpoint_writes_devlog_entries_row`, `test_hc_docs_dir_resolves_migrated_path`, `test_check_costs_freshness_resolves_migrated_path` — so expect `2047 passed, 2 skipped`)

- [ ] **Step 2: Confirm no stray `_docs_dir()` call sites were missed**

Run: `grep -n "_docs_dir()" synlynk/*.py`

Expected: every call site either (a) is inside a function already gated by `_is_migrated()` (confirmed during Task 1-6 work and the original spec's ~18 already-correct call sites in `db.py`), or (b) is the canonical `_docs_dir()` definition itself in `synlynk/__init__.py`. If any ungated call site turns up outside the 5 files already audited in the spec, flag it — do not silently fix it outside this plan's scope.

- [ ] **Step 3: Commit is not needed for this task (verification only)**

If Step 1 or Step 2 surfaces a failure, fix it as a small follow-up commit referencing which task's tests regressed, then re-run Step 1.
