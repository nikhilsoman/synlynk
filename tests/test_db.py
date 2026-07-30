import os
import subprocess

from synlynk.db import (
    _detect_hand_edit,
    _generate_costs_md,
    _generate_roadmap_md,
    cmd_cost_log,
    cmd_roadmap_add,
)


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


def test_cmd_remediation_log_appends_past_telemetry_cap(project_dir):
    import synlynk
    from synlynk.db import cmd_remediation_log

    for idx in range(101):
        hour = 10 + (idx // 60)
        minute = idx % 60
        cmd_remediation_log(
            timestamp=f"2026-07-30 {hour:02d}:{minute:02d}",
            agent="agy",
            target_file="synlynk/doctor.py",
            exact_diff=f"diff-{idx}",
            operator="non-interactive --yes",
        )

    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(remediation_actions)")}
    rows = conn.execute(
        "SELECT timestamp, agent, target_file, exact_diff, operator "
        "FROM remediation_actions ORDER BY id ASC"
    ).fetchall()
    conn.close()

    assert {"timestamp", "agent", "target_file", "exact_diff", "operator"} <= cols
    assert len(rows) == 101
    assert rows[0] == (
        "2026-07-30 10:00",
        "agy",
        "synlynk/doctor.py",
        "diff-0",
        "non-interactive --yes",
    )
    assert rows[-1] == (
        "2026-07-30 11:40",
        "agy",
        "synlynk/doctor.py",
        "diff-100",
        "non-interactive --yes",
    )


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


def test_rotate_moves_old_cost_entries_to_archive(tmp_path, monkeypatch):
    from tests.test_migrate import _setup_migrated
    from synlynk import _insert_cost_row
    from synlynk.db import _generate_costs_md

    _setup_migrated(tmp_path, monkeypatch)
    monkeypatch.setattr("synlynk.db._PROJECT_DOC_KEEP_N", 1)

    for i in range(4):
        _insert_cost_row(
            session_date=f"2026-01-0{i+1} 10:00",
            agent="claude",
            model="claude-sonnet-5",
            input_tokens=1,
            output_tokens=1,
            cache_read_tokens=0,
            cost_source="estimated_manual",
            estimate_basis="cli_manual_entry",
            total_cost_usd=1.0,
            notes=f"row{i}",
            story_id=None,
            api_equivalent_usd=1.0,
            actual_usd=None,
            payment_mode=None,
        )

    _generate_costs_md()

    live = open(os.path.join(".synlynk", "project-docs", "costs.md")).read()
    assert "row3" in live
    assert "row0" not in live

    archive_dir = os.path.join(".synlynk", "project-docs", "archive")
    archive_files = os.listdir(archive_dir)
    assert any(f.startswith("costs-") for f in archive_files)
    archived_content = open(
        os.path.join(archive_dir, [f for f in archive_files if f.startswith("costs-")][0])
    ).read()
    assert "row0" in archived_content

    index_path = os.path.join(archive_dir, "INDEX.md")
    assert os.path.exists(index_path)
    assert "costs-" in open(index_path).read()


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
    from tests.test_migrate import _setup_migrated
    from synlynk import _insert_cost_row
    from synlynk.db import _generate_costs_md

    _setup_migrated(tmp_path, monkeypatch)
    _generate_costs_md()

    path = os.path.join(".synlynk", "project-docs", "costs.md")
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "add", path], check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "seed"],
        check=True,
    )

    _insert_cost_row(
        session_date="2026-07-25 10:00",
        agent="claude",
        model="claude-sonnet-5",
        input_tokens=1,
        output_tokens=1,
        cache_read_tokens=0,
        cost_source="estimated_manual",
        estimate_basis="cli_manual_entry",
        total_cost_usd=1.0,
        notes="not yet regenerated",
        story_id=None,
        api_equivalent_usd=1.0,
        actual_usd=None,
        payment_mode=None,
    )

    warning = _detect_hand_edit("costs.md")
    assert warning is None
