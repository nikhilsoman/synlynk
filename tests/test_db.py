import os

from synlynk.db import _generate_costs_md, _generate_roadmap_md, cmd_cost_log, cmd_roadmap_add


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
    cmd_roadmap_add(
        version="v0.14.0",
        phase_title="Build the thing",
        status="planned",
        priority="p1",
    )

    from synlynk import _get_db

    conn = _get_db()
    row = conn.execute(
        "SELECT phase_title, priority FROM roadmap_phases WHERE arc_version=?",
        ("v0.14.0",),
    ).fetchone()
    conn.close()
    assert row == ("Build the thing", "p1")


def test_cmd_roadmap_add_phase_without_arc_raises(project_dir):
    import pytest

    with pytest.raises(ValueError, match="no roadmap arc"):
        cmd_roadmap_add(version="v9.9.9", phase_title="Orphan phase")


def test_generate_costs_md_creates_file_pre_migration(project_dir):
    from synlynk import _insert_cost_row

    _insert_cost_row(
        session_date="2026-07-25 10:00",
        agent="claude",
        model="claude-sonnet-5",
        input_tokens=1000,
        output_tokens=200,
        cache_read_tokens=0,
        cost_source="estimated_manual",
        estimate_basis="cli_manual_entry",
        total_cost_usd=0.0057,
        notes="test row",
        story_id=None,
        api_equivalent_usd=0.0057,
        actual_usd=None,
        payment_mode=None,
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
    import json

    from tests.test_migrate import _setup_migrated

    dr_dir = tmp_path / "dr_mirror"
    dr_dir.mkdir()
    _setup_migrated(tmp_path, monkeypatch)
    cfg_path = os.path.join(".synlynk", "config.json")
    with open(cfg_path, "w") as f:
        json.dump({"dr_sync_path": str(dr_dir)}, f)

    cmd_cost_log(agent="gemini", tokens_in=10, tokens_out=5)

    md_path = os.path.join(".synlynk", "project-docs", "costs.md")
    assert os.path.exists(md_path)
    dr_path = os.path.join(str(dr_dir), "project-docs", "costs.md")
    assert os.path.exists(dr_path)
