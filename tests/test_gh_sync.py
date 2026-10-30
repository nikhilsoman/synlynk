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


def test_gh_api_json_passes_role_through_environment(monkeypatch):
    import subprocess

    from synlynk import gh_sync

    received = {}

    def fake_run_gh(args, **kwargs):
        received.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "{}", "")

    monkeypatch.setattr(gh_sync, "run_gh", fake_run_gh)

    gh_sync._gh_api_json(
        ["repos/o/r/milestones"],
        role="qa",
        env={"SYNLYNK_GH_ROLE": "pm", "KEEP_ME": "yes"},
    )

    assert received["env"]["SYNLYNK_GH_ROLE"] == "qa"
    assert received["env"]["KEEP_ME"] == "yes"


def test_find_milestone_by_title_returns_match(monkeypatch):
    from synlynk import gh_sync

    milestones = [
        {"number": 41, "node_id": "MI_old", "title": "v0.25.0", "state": "closed"},
        {"number": 47, "node_id": "MI_match", "title": "v0.26.0", "state": "open"},
    ]
    monkeypatch.setattr(gh_sync, "_gh_api_json", lambda args, **kwargs: milestones)

    result = gh_sync._find_milestone_by_title("o", "r", "v0.26.0", role="qa")

    assert result == milestones[1]


def test_find_milestone_by_title_returns_none_when_no_match(monkeypatch):
    from synlynk import gh_sync

    milestones = [
        {"number": 41, "node_id": "MI_old", "title": "v0.25.0", "state": "closed"},
        {"number": 48, "node_id": "MI_new", "title": "v0.27.0", "state": "open"},
    ]
    monkeypatch.setattr(gh_sync, "_gh_api_json", lambda args, **kwargs: milestones)

    assert gh_sync._find_milestone_by_title("o", "r", "v0.26.0") is None


def _sync_arc_create_args(tmp_path, monkeypatch, target_date):
    import sqlite3

    from synlynk import gh_sync

    tmp_path.mkdir(parents=True, exist_ok=True)
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
        "CREATE TABLE roadmap_phases ("
        "id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE cost_entries (actual_usd REAL, estimate_basis TEXT, epic_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', "
        "'planned', ?, NULL, 1)",
        (target_date,),
    )
    conn.commit()

    created = {}

    def fake_gh_api_json(args, **kwargs):
        if args[1:3] == ["--method", "GET"]:
            return []
        created["args"] = args
        return {"number": 99, "node_id": "MI_abc"}

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)
    gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")
    conn.close()
    return created["args"]


def test_sync_arc_includes_due_on_for_full_iso_date(tmp_path, monkeypatch):
    args = _sync_arc_create_args(tmp_path, monkeypatch, "2026-08-23")

    assert "-fdue_on=2026-08-23T00:00:00Z" in args


def test_sync_arc_omits_due_on_for_non_iso_date(tmp_path, monkeypatch):
    for index, target_date in enumerate(("June 2026", "Q4 2026", "2026-08")):
        args = _sync_arc_create_args(tmp_path / str(index), monkeypatch, target_date)

        assert not any(arg.startswith("-fdue_on=") for arg in args)


def test_sync_arc_omits_due_on_when_target_date_is_none(tmp_path, monkeypatch):
    args = _sync_arc_create_args(tmp_path, monkeypatch, None)

    assert not any(arg.startswith("-fdue_on=") for arg in args)


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
        if args[1:3] == ["--method", "GET"]:
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


def test_sync_arc_adopts_existing_milestone_by_title_instead_of_posting(
    tmp_path, monkeypatch
):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.executescript(
        """
        CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY, version TEXT, title TEXT, status TEXT,
            target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN
        );
        CREATE TABLE github_sync_map (
            entity_type TEXT, entity_id TEXT, github_number INTEGER,
            github_node_id TEXT, content_hash TEXT, last_synced_at TEXT,
            PRIMARY KEY (entity_type, entity_id)
        );
        CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT
        );
        CREATE TABLE cost_entries (
            actual_usd REAL, estimate_basis TEXT, epic_id INTEGER
        );
        INSERT INTO roadmap_arcs
        VALUES (47, 'v0.26.0', 'Existing release', 'planned', NULL, NULL, 1);
        """
    )
    conn.commit()
    calls = []

    def fake_gh_api_json(args, **kwargs):
        calls.append(args)
        if args[1:3] == ["--method", "GET"]:
            return [{"number": 26, "node_id": "MI_existing", "title": "v0.26.0"}]
        return {"number": 26, "node_id": "MI_existing", "title": "v0.26.0"}

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_arc(conn, arc_id=47, owner="o", repo="r", role="qa")

    write_calls = [call for call in calls if "--method" in call and "GET" not in call]
    assert len(write_calls) == 1
    assert write_calls[0][:3] == ["repos/o/r/milestones/26", "--method", "PATCH"]
    assert not any("POST" in call for call in calls)
    mapped = conn.execute(
        "SELECT github_number, github_node_id FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id='47'"
    ).fetchone()
    assert mapped == (26, "MI_existing")
    conn.close()


def test_sync_arc_still_posts_when_no_existing_milestone_matches(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.executescript(
        """
        CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY, version TEXT, title TEXT, status TEXT,
            target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN
        );
        CREATE TABLE github_sync_map (
            entity_type TEXT, entity_id TEXT, github_number INTEGER,
            github_node_id TEXT, content_hash TEXT, last_synced_at TEXT,
            PRIMARY KEY (entity_type, entity_id)
        );
        CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT
        );
        CREATE TABLE cost_entries (
            actual_usd REAL, estimate_basis TEXT, epic_id INTEGER
        );
        INSERT INTO roadmap_arcs
        VALUES (47, 'v0.26.0', 'New release', 'planned', NULL, NULL, 1);
        """
    )
    conn.commit()
    calls = []

    def fake_gh_api_json(args, **kwargs):
        calls.append(args)
        if args[1:3] == ["--method", "GET"]:
            return [{"number": 25, "node_id": "MI_other", "title": "v0.25.0"}]
        return {"number": 99, "node_id": "MI_new", "title": "v0.26.0"}

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_arc(conn, arc_id=47, owner="o", repo="r")

    post_calls = [call for call in calls if "POST" in call]
    assert len(post_calls) == 1
    assert post_calls[0][0] == "repos/o/r/milestones"
    assert not any("PATCH" in call for call in calls)
    mapped = conn.execute(
        "SELECT github_number FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id='47'"
    ).fetchone()
    assert mapped == (99,)
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


def test_sync_story_creates_issue_with_footer(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT, gh_issue TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute("INSERT INTO stories VALUES ('story-abc', 'Core cluster', 'open', NULL)")
    conn.commit()

    created = {}

    def fake_gh_api_json(args, **kwargs):
        if "--method" in args and "POST" in args:
            created["args"] = args
            return {"number": 7, "node_id": "I_xyz"}
        return []

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_story(conn, story_id="story-abc", owner="o", repo="r", milestone_number=None)

    body_arg = next(a for a in created["args"] if a.startswith("-fbody="))
    assert "<!-- synlynk:story_id=story-abc -->" in body_arg
    mapped = conn.execute(
        "SELECT github_number FROM github_sync_map "
        "WHERE entity_type='story' AND entity_id='story-abc'"
    ).fetchone()
    assert mapped == (7,)
    conn.close()


def test_story_sync_fields_preserves_short_title_and_full_body(tmp_path):
    import sqlite3

    from synlynk.gh_sync import _story_sync_fields

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT)")
    conn.execute("INSERT INTO stories VALUES ('story-short', 'Short title', 'open')")

    fields = _story_sync_fields(conn, "story-short")

    assert fields["title"] == "Short title"
    assert fields["body"] == "Short title\n\n<!-- synlynk:story_id=story-short -->"
    conn.close()


def test_story_sync_fields_uses_only_stripped_first_line_for_issue_title(tmp_path):
    import sqlite3

    from synlynk.gh_sync import _story_sync_fields

    raw_title = "  First line  \nSecond line\n\nFourth line"
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT)")
    conn.execute("INSERT INTO stories VALUES ('story-multiline', ?, 'open')", (raw_title,))

    fields = _story_sync_fields(conn, "story-multiline")

    assert fields["title"] == "First line"
    assert fields["body"] == (
        f"{raw_title}\n\n<!-- synlynk:story_id=story-multiline -->"
    )
    conn.close()


def test_story_sync_fields_truncates_long_issue_title_but_not_body(tmp_path):
    import sqlite3

    from synlynk.gh_sync import _story_sync_fields

    raw_title = "x" * 121
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT)")
    conn.execute("INSERT INTO stories VALUES ('story-long', ?, 'done')", (raw_title,))

    fields = _story_sync_fields(conn, "story-long")

    assert fields["title"] == "x" * 117 + "..."
    assert len(fields["title"]) == 120
    assert fields["state"] == "closed"
    assert fields["body"] == f"{raw_title}\n\n<!-- synlynk:story_id=story-long -->"
    conn.close()


def test_sync_decision_creates_issue_with_decision_label(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE decisions (decision_id TEXT PRIMARY KEY, topic TEXT, status TEXT, "
        "synthesis TEXT, decision_text TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO decisions VALUES ('dec-1', 'Should we X?', 'decided', 'yes because', 'Do X')"
    )
    conn.commit()

    created = {}

    def fake_gh_api_json(args, **kwargs):
        if "--method" in args and "POST" in args:
            created["args"] = args
            return {"number": 12, "node_id": "I_dec"}
        return []

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)

    gh_sync.sync_decision(conn, decision_id="dec-1", owner="o", repo="r")

    assert "-flabels[]=decision" in created["args"]
    mapped = conn.execute(
        "SELECT github_number FROM github_sync_map "
        "WHERE entity_type='decision' AND entity_id='dec-1'"
    ).fetchone()
    assert mapped == (12,)
    conn.close()
