import json
import os
import subprocess

import synlynk


def test_migrate_db_creates_new_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    conn = synlynk._get_db()
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "memory_entries" in tables
    assert "roadmap_arcs" in tables
    assert "roadmap_phases" in tables
    assert "cost_entries" in tables
    assert "devlog_entries" in tables


def test_stories_has_gh_issue_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    conn.close()
    assert "gh_issue" in cols


def test_parse_memory_md_sections():
    content = """# synlynk Memory

## First Section

Some body text [@alice] here.

## Second Section

Another body.
"""
    rows = synlynk._parse_memory_md(content)
    assert len(rows) == 2
    assert rows[0]["section"] == "First Section"
    assert "Some body text" in rows[0]["body"]
    assert rows[0]["author"] == "alice"
    assert rows[1]["author"] is None


def test_parse_roadmap_md_arcs_and_phases():
    content = """# Roadmap

## v0.9.0 — Shipped ✅

- feat: core [P0]
- fix: patch

## v0.10.0 — Developer Preview

- 🚧 wizard [P0]
- packaging [P1]
"""
    arcs, phases = synlynk._parse_roadmap_md(content)
    assert len(arcs) == 2
    assert arcs[0]["version"] == "v0.9.0"
    assert arcs[0]["status"] == "shipped"
    assert arcs[1]["version"] == "v0.10.0"
    assert arcs[1]["status"] == "planned"
    assert len(phases) == 4
    assert phases[0]["arc_version"] == "v0.9.0"
    assert phases[2]["status"] == "in_progress"


def test_parse_costs_md_rows():
    content = """| Date | Agent | Model | In | Out | Cache | Cost | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-01 | claude | sonnet | 150000 | 30000 | 0 | $0.85 | exec: scan |
| 2026-07-01 | agy | gemini | 80000 | 20000 | 0 | ~$0.45 | exec: blog |
"""
    rows = synlynk._parse_costs_md(content)
    assert len(rows) == 2
    assert rows[0]["session_date"] == "2026-07-01"
    assert rows[0]["input_tokens"] == 150000
    assert rows[1]["total_cost_usd"] == 0.45


def test_parse_devlog_file_entries():
    content = """# Nikhil Devlog

## 2026-06-29 — Session: BS-5 Phase 1

### Shipped
- feat: website scaffold

## 2026-07-01

Session end checkpoint.
"""
    entries = synlynk._parse_devlog_file(content, "nikhil")
    assert len(entries) == 2
    assert entries[0]["author"] == "nikhil"
    assert entries[0]["entry_date"] == "2026-06-29"
    assert entries[0]["session_title"] == "BS-5 Phase 1"
    assert "Shipped" in entries[0]["body"]
    assert entries[1]["session_title"] is None
    assert entries[1]["entry_date"] == "2026-07-01"


def test_parse_todo_metadata():
    content = """- [x] BS-12a roles [platform] <!-- id:story-bs12a-roles --> <!-- gh:#79 --> <!-- priority:next -->
- [ ] plain story <!-- id:story-abc123 -->
- [ ] story with gh only <!-- id:story-def456 --> <!-- gh:#81 -->
"""
    rows = synlynk._parse_todo_metadata(content)
    assert len(rows) == 2
    assert rows[0]["story_id"] == "story-bs12a-roles"
    assert rows[0]["gh_issue"] == "#79"
    assert rows[0]["priority"] == "next"
    assert rows[1]["story_id"] == "story-def456"
    assert rows[1]["gh_issue"] == "#81"
    assert rows[1]["priority"] is None


def test_is_migrated_false_without_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    assert synlynk._is_migrated() is False


def test_is_migrated_true_with_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / ".synlynk_migrated").write_text("2026-07-01T00:00:00Z")
    assert synlynk._is_migrated() is True


def test_synlynk_project_docs_dir_returns_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = synlynk._synlynk_project_docs_dir()
    assert result == os.path.join(".synlynk", "project-docs")


def test_dr_sync_copies_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    backup = tmp_path / ".synlynk" / "project-docs"
    backup.mkdir(parents=True)
    (backup / "todo.md").write_text("# Tasks\n")
    dr_path = tmp_path / "dr-mirror"
    dr_path.mkdir()
    cfg = tmp_path / ".synlynk" / "config.json"
    cfg.write_text(json.dumps({"dr_sync_path": str(dr_path)}))
    synlynk._dr_sync("todo.md")
    assert (dr_path / "project-docs" / "todo.md").exists()


def test_dr_sync_silent_skip_if_path_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    backup = tmp_path / ".synlynk" / "project-docs"
    backup.mkdir(parents=True)
    (backup / "todo.md").write_text("# Tasks\n")
    cfg = tmp_path / ".synlynk" / "config.json"
    cfg.write_text(json.dumps({"dr_sync_path": str(tmp_path / "nonexistent")}))
    synlynk._dr_sync("todo.md")


def _make_project_docs(tmp_path):
    """Helper: create a minimal project-docs/ structure for testing."""
    pd = tmp_path / "project-docs"
    pd.mkdir()
    (pd / "memory.md").write_text(
        "# synlynk Memory\n\n## Design Decisions\n\nSome note [@nikhil].\n\n## Agents\n\nAgent policy.\n"
    )
    (pd / "roadmap.md").write_text(
        "# Roadmap\n\n## v0.9.0 — Shipped ✅\n\n- feat: core [P0]\n\n## v0.10.0\n\n- wizard [P0]\n"
    )
    (pd / "costs.md").write_text(
        "| Date | Agent | Model | In | Out | Cache | Cost | Notes |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 2026-07-01 | claude | sonnet | 100000 | 20000 | 0 | $0.60 | exec: scan |\n"
    )
    devlogs = pd / "devlogs"
    devlogs.mkdir()
    (devlogs / "nikhil.md").write_text(
        "# Nikhil Devlog\n\n## 2026-07-01 — Session: BS-18\n\n### Shipped\n- migrate cmd\n"
    )
    (pd / "todo.md").write_text(
        "- [ ] BS-12a roles <!-- id:story-bs12a-roles --> <!-- gh:#79 -->\n"
        "- [ ] packaging <!-- id:story-plain -->\n"
    )
    return pd


def test_migrate_dry_run_imports_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    _make_project_docs(tmp_path)
    synlynk.cmd_migrate(dry_run=True)
    conn = synlynk._get_db()
    assert conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM devlog_entries").fetchone()[0] == 0
    conn.close()
    assert not (tmp_path / ".synlynk" / ".synlynk_migrated").exists()


def test_migrate_imports_all_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
    _make_project_docs(tmp_path)
    synlynk.cmd_migrate()
    conn = synlynk._get_db()
    assert conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM roadmap_arcs").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM roadmap_phases").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM devlog_entries").fetchone()[0] == 1
    conn.close()


def test_migrate_copies_to_synlynk_project_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
    _make_project_docs(tmp_path)
    synlynk.cmd_migrate()
    backup = tmp_path / ".synlynk" / "project-docs"
    assert (backup / "memory.md").exists()
    assert (backup / "costs.md").exists()
    assert (backup / "devlogs" / "nikhil.md").exists()


def test_migrate_writes_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
    _make_project_docs(tmp_path)
    synlynk.cmd_migrate()
    assert (tmp_path / ".synlynk" / ".synlynk_migrated").exists()


def test_migrate_idempotent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / ".synlynk_migrated").write_text("2026-07-01")
    synlynk.cmd_migrate()
    out = capsys.readouterr().out
    assert "Already migrated" in out


def test_migrate_recover_reimports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / ".synlynk_migrated").write_text("2026-07-01")
    backup = tmp_path / ".synlynk" / "project-docs"
    backup.mkdir(parents=True)
    (backup / "memory.md").write_text(
        "# Memory\n\n## Recovery Test\n\nBody here.\n"
    )
    synlynk.cmd_migrate(recover=True)
    conn = synlynk._get_db()
    count = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
    conn.close()
    assert count == 1


def test_migrate_dr_sync_on_migrate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
    dr_path = tmp_path / "dr-mirror"
    dr_path.mkdir()
    cfg = tmp_path / ".synlynk" / "config.json"
    cfg.write_text(json.dumps({"dr_sync_path": str(dr_path)}))
    _make_project_docs(tmp_path)
    synlynk.cmd_migrate()
    assert (dr_path / "project-docs" / "memory.md").exists()


def _setup_migrated(tmp_path, monkeypatch):
    """Helper: set up a migrated environment."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / ".synlynk_migrated").write_text("2026-07-01")
    backup = tmp_path / ".synlynk" / "project-docs"
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "devlogs").mkdir(exist_ok=True)
    return backup


def test_write_through_todo_goes_to_synlynk_path(tmp_path, monkeypatch):
    backup = _setup_migrated(tmp_path, monkeypatch)
    synlynk._generate_todo_md()
    assert (backup / "todo.md").exists()
    # old path must NOT be written
    assert not (tmp_path / "project-docs" / "todo.md").exists()


def test_write_through_noop_before_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    # No sentinel — _generate_todo_md should write to project-docs/ (old path)
    # but since project-docs/ doesn't exist either, it just returns silently
    synlynk._generate_todo_md()  # must not raise
    assert not (tmp_path / ".synlynk" / "project-docs" / "todo.md").exists()


def test_cmd_memory_add_writes_to_db_and_flat_file(tmp_path, monkeypatch):
    backup = _setup_migrated(tmp_path, monkeypatch)
    synlynk.cmd_memory_add("Test Section", "Some body text", author="nikhil")
    conn = synlynk._get_db()
    row = conn.execute("SELECT section, body, author FROM memory_entries").fetchone()
    conn.close()
    assert row[0] == "Test Section"
    assert row[2] == "nikhil"
    assert (backup / "memory.md").exists()
    content = (backup / "memory.md").read_text()
    assert "Test Section" in content


def test_cmd_memory_add_updates_existing_section(tmp_path, monkeypatch):
    _setup_migrated(tmp_path, monkeypatch)
    synlynk.cmd_memory_add("My Section", "Original body")
    synlynk.cmd_memory_add("My Section", "Updated body")
    conn = synlynk._get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM memory_entries WHERE section='My Section'"
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_cmd_devlog_append_writes_entry(tmp_path, monkeypatch):
    backup = _setup_migrated(tmp_path, monkeypatch)
    synlynk.cmd_devlog_append(
        author="nikhil",
        entry_date="2026-07-01",
        body="### Shipped\n- migrate cmd\n",
        session_title="BS-18"
    )
    conn = synlynk._get_db()
    row = conn.execute("SELECT author, session_title FROM devlog_entries").fetchone()
    conn.close()
    assert row[0] == "nikhil"
    assert row[1] == "BS-18"
    devlog_file = backup / "devlogs" / "nikhil.md"
    assert devlog_file.exists()
    assert "BS-18" in devlog_file.read_text()


def test_update_costs_writes_to_db_and_flat_file_post_migration(tmp_path, monkeypatch):
    backup = _setup_migrated(tmp_path, monkeypatch)
    (backup / "costs.md").write_text("| Date | Agent | In | Out | Cost | Notes |\n")
    synlynk.update_costs("scan", 50000, 10000, 12.5)
    conn = synlynk._get_db()
    count = conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0]
    conn.close()
    assert count == 1
    content = (backup / "costs.md").read_text()
    assert "scan" in content


def test_generate_context_uses_db_when_migrated(tmp_path, monkeypatch):
    backup = _setup_migrated(tmp_path, monkeypatch)
    conn = synlynk._get_db()
    # Seed a story
    conn.execute(
        "INSERT INTO stories (story_id, title, status) VALUES ('s1','Do the thing','open')"
    )
    # Seed a devlog entry
    conn.execute(
        "INSERT INTO devlog_entries (author, entry_date, body) VALUES ('nikhil','2026-07-01','Shipped it.')"
    )
    conn.commit()
    conn.close()
    ctx = synlynk.generate_context(out_path=str(tmp_path / "ctx.md"))
    assert "Do the thing" in ctx
    assert "nikhil" in ctx


def test_generate_context_uses_files_when_not_migrated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    # No sentinel — should use flat-file path (returns empty since no docs_dir)
    ctx = synlynk.generate_context(out_path=str(tmp_path / "ctx.md"))
    assert isinstance(ctx, str)  # doesn't crash, returns string


def test_full_migration_end_to_end(tmp_path, monkeypatch):
    import json, subprocess as _sp
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('HOME', str(tmp_path))
    (tmp_path / '.synlynk').mkdir()
    monkeypatch.setattr(_sp, 'run', lambda *a, **kw: None)

    pd = tmp_path / 'project-docs'
    pd.mkdir()
    (pd / 'memory.md').write_text('# synlynk Memory\n\n## Key Decisions\n\nDecision A. [@nikhil]\n\n## Agents\n\nAgent rules.\n')
    (pd / 'roadmap.md').write_text('# Roadmap\n\n## v0.10.0 — Developer Preview\n\n- wizard [P0]\n- scan [P0]\n')
    (pd / 'costs.md').write_text('| Date | Agent | Model | In | Out | Cache | Cost | Notes |\n|---|---|---|---|---|---|---|---|\n| 2026-07-01 | claude | sonnet | 200000 | 40000 | 0 | .20 | exec: migrate |\n')
    devlogs = pd / 'devlogs'
    devlogs.mkdir()
    (devlogs / 'nikhil.md').write_text('# Nikhil Devlog\n\n## 2026-07-01 — Session: BS-18\n\n### Shipped\n- full migration\n')
    (pd / 'todo.md').write_text('- [ ] packaging <!-- id:story-v010-pkg --> <!-- gh:#90 -->\n')

    # Dry-run imports nothing
    synlynk.cmd_migrate(dry_run=True)
    conn = synlynk._get_db()
    assert conn.execute('SELECT COUNT(*) FROM memory_entries').fetchone()[0] == 0
    conn.close()

    # Real migrate
    synlynk.cmd_migrate()
    assert synlynk._is_migrated()

    conn = synlynk._get_db()
    assert conn.execute('SELECT COUNT(*) FROM memory_entries').fetchone()[0] == 2
    assert conn.execute('SELECT COUNT(*) FROM roadmap_arcs').fetchone()[0] == 1
    assert conn.execute('SELECT COUNT(*) FROM roadmap_phases').fetchone()[0] == 2
    assert conn.execute('SELECT COUNT(*) FROM cost_entries').fetchone()[0] == 1
    assert conn.execute('SELECT COUNT(*) FROM devlog_entries').fetchone()[0] == 1
    conn.close()

    backup = tmp_path / '.synlynk' / 'project-docs'
    assert (backup / 'memory.md').exists()
    assert (backup / 'devlogs' / 'nikhil.md').exists()

    # Write-through
    synlynk.cmd_memory_add('New Decision', 'Something important.', author='nikhil')
    assert 'New Decision' in (backup / 'memory.md').read_text()

    synlynk.cmd_devlog_append('nikhil', '2026-07-02', '### Done\n- follow-up\n', 'Follow-up')
    assert 'Follow-up' in (backup / 'devlogs' / 'nikhil.md').read_text()

    # generate_context reads from DB
    ctx = synlynk.generate_context(out_path=str(tmp_path / 'ctx.md'))
    assert isinstance(ctx, str) and len(ctx) > 0

    # Recover re-imports from backup
    conn = synlynk._get_db()
    conn.execute('DELETE FROM memory_entries')
    conn.commit()
    conn.close()
    synlynk.cmd_migrate(recover=True)
    conn = synlynk._get_db()
    count = conn.execute('SELECT COUNT(*) FROM memory_entries').fetchone()[0]
    conn.close()
    assert count == 3  # 2 original + 1 written-through

