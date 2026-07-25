import os

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
