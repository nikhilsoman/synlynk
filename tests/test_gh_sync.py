def test_content_hash_is_stable_for_same_input():
    from synlynk.gh_sync import _content_hash

    a = _content_hash({"title": "v1.0.0", "status": "shipped", "due_on": "2026-01-01"})
    b = _content_hash({"title": "v1.0.0", "status": "shipped", "due_on": "2026-01-01"})
    assert a == b


def test_content_hash_differs_when_input_differs():
    from synlynk.gh_sync import _content_hash

    a = _content_hash({"title": "v1.0.0", "status": "shipped"})
    b = _content_hash({"title": "v1.0.0", "status": "planned"})
    assert a != b


def test_gh_api_json_parses_successful_response(monkeypatch):
    import subprocess

    from synlynk import gh_sync

    def fake_run_gh(args, **kwargs):
        assert args[0] == "api"
        return subprocess.CompletedProcess(args, 0, '[{"number": 1, "title": "v1.0.0"}]', "")

    monkeypatch.setattr(gh_sync, "run_gh", fake_run_gh)
    result = gh_sync._gh_api_json(["repos/o/r/milestones", "--paginate"])
    assert result == [{"number": 1, "title": "v1.0.0"}]


def test_gh_api_json_raises_on_nonzero_exit(monkeypatch):
    import subprocess

    import pytest

    from synlynk import gh_sync

    def fake_run_gh(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "", "refused")

    monkeypatch.setattr(gh_sync, "run_gh", fake_run_gh)
    with pytest.raises(RuntimeError, match="refused"):
        gh_sync._gh_api_json(["repos/o/r/milestones"])


def test_sync_arc_creates_milestone_when_absent(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS roadmap_phases ("
        "id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cost_entries ("
        "actual_usd REAL, estimate_basis TEXT, epic_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1)"
    )
    conn.commit()

    calls = []

    def fake_gh_api_json(args, **kwargs):
        calls.append(args)
        if args[0] == "repos/o/r/milestones" and "--method" not in args:
            return []
        return {"number": 99, "node_id": "MI_abc"}

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")

    mapped = conn.execute(
        "SELECT github_number FROM github_sync_map WHERE entity_type='roadmap_arc' AND entity_id='1'"
    ).fetchone()
    assert mapped == (99,)
    create_calls = [c for c in calls if "--method" in c and "POST" in c]
    assert len(create_calls) == 1
    conn.close()


def test_sync_arc_skips_patch_when_content_hash_unchanged(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS roadmap_phases ("
        "id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cost_entries ("
        "actual_usd REAL, estimate_basis TEXT, epic_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1)"
    )
    fields = gh_sync._arc_sync_fields(conn, arc_id=1)
    existing_hash = gh_sync._content_hash(fields)
    conn.execute(
        "INSERT INTO github_sync_map VALUES ('roadmap_arc', '1', 99, 'MI_abc', ?, datetime('now'))",
        (existing_hash,),
    )
    conn.commit()

    calls = []

    def fake_gh_api_json(args, **kwargs):
        calls.append(args)
        return []

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")

    assert calls == []  # no API calls at all -- nothing changed
    conn.close()


def test_sync_arc_noop_when_not_milestone_eligible(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS roadmap_phases ("
        "id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cost_entries ("
        "actual_usd REAL, estimate_basis TEXT, epic_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (2, 'Future Expansions', NULL, 'planned', NULL, NULL, 0)"
    )
    conn.commit()

    calls = []
    monkeypatch.setattr(gh_sync, "_gh_api_json", lambda args, **kw: calls.append(args))

    gh_sync.sync_arc(conn, arc_id=2, owner="o", repo="r")

    assert calls == []
    conn.close()
