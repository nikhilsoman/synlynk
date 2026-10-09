import sqlite3

from synlynk.state_inventory import inventory


def test_inventory_is_read_only_and_classifies_repo_artifact(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sample (value TEXT)")
    conn.commit()
    conn.close()

    before = db.read_bytes()
    rows = inventory(repo)

    assert len(rows) == 1
    assert rows[0]["class"] == "repo-local"
    assert rows[0]["integrity"] == "ok"
    assert rows[0]["sha256"]
    assert db.read_bytes() == before


def test_inventory_reports_row_count_and_staleness(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('s-1', 'Example story')")
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('s-2', 'Another story')")
    conn.commit()
    conn.close()

    rows = inventory(repo)

    assert len(rows) == 1
    assert rows[0]["row_count"] == 2
    assert "mtime_iso" in rows[0]
    assert rows[0]["staleness_days"] >= 0


def test_inventory_row_count_zero_when_no_stories_table(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sample (value TEXT)")
    conn.commit()
    conn.close()

    rows = inventory(repo)

    assert rows[0]["row_count"] is None


def _make_db_with_identity(path, product_id, stories=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE state_identity (
            product_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            canonical_path TEXT NOT NULL,
            lineage_generation INTEGER NOT NULL DEFAULT 1,
            source_sha256 TEXT,
            bootstrapped_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO state_identity(product_id, mode, canonical_path) VALUES (?, 'canonical', ?)",
        (product_id, str(path)),
    )
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    for story_id, title, gh_issue in stories:
        conn.execute(
            "INSERT INTO stories (story_id, title, gh_issue) VALUES (?, ?, ?)",
            (story_id, title, gh_issue),
        )
    conn.commit()
    conn.close()


def test_match_project_exact_fingerprint(tmp_path):
    from synlynk.state_inventory import _match_project

    workspaces_root = tmp_path / "workspaces"
    canonical_db = workspaces_root / "myproj" / "state.db"
    _make_db_with_identity(canonical_db, "prod-abc123")

    legacy_db = tmp_path / "legacy" / "state.db"
    _make_db_with_identity(legacy_db, "prod-abc123")

    match = _match_project(legacy_db, workspaces_root)

    assert match["slug"] == "myproj"
    assert match["method"] == "fingerprint"
    assert match["confidence"] == "exact"


def test_match_project_heuristic_fallback(tmp_path):
    from synlynk.state_inventory import _match_project

    workspaces_root = tmp_path / "workspaces"
    canonical_db = workspaces_root / "synlynk" / "state.db"
    _make_db_with_identity(
        canonical_db, "prod-xyz",
        stories=[("s-1", "feat(workspace): add product repo registration", "#2101")],
    )

    legacy_db = tmp_path / "legacy" / "state.db"
    legacy_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(legacy_db)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, gh_issue) VALUES "
        "('legacy-1', 'feat(workspace): add product repo registration', '#2101')"
    )
    conn.commit()
    conn.close()

    match = _match_project(legacy_db, workspaces_root)

    assert match["slug"] == "synlynk"
    assert match["method"] == "heuristic"
    assert match["confidence"] == "heuristic"


def test_match_project_no_match(tmp_path):
    from synlynk.state_inventory import _match_project

    workspaces_root = tmp_path / "workspaces"
    canonical_db = workspaces_root / "other" / "state.db"
    _make_db_with_identity(
        canonical_db, "prod-other",
        stories=[("s-1", "completely unrelated story about widgets", None)],
    )

    legacy_db = tmp_path / "legacy" / "state.db"
    legacy_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(legacy_db)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, gh_issue) VALUES "
        "('legacy-1', 'nothing in common with anything', NULL)"
    )
    conn.commit()
    conn.close()

    match = _match_project(legacy_db, workspaces_root)

    assert match["slug"] is None
    assert match["method"] == "none"


def test_inventory_adds_project_match_for_legacy_shards(tmp_path, monkeypatch):
    home = tmp_path / "home" / ".synlynk"
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path / "home" / ".synlynk") if p == "~/.synlynk" else p)

    canonical_db = home / "workspaces" / "myproj" / "state.db"
    _make_db_with_identity(canonical_db, "prod-match-me")

    legacy_db = home / "projects" / "abc12345" / "state.db"
    _make_db_with_identity(legacy_db, "prod-match-me")

    repo = tmp_path / "repo"
    repo.mkdir()

    rows = inventory(repo, all_artifacts=True)

    legacy_rows = [r for r in rows if r["class"] == "legacy-project"]
    assert len(legacy_rows) == 1
    assert legacy_rows[0]["project_match"]["slug"] == "myproj"


def _make_stories_db(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    for story_id, title, gh_issue in rows:
        conn.execute(
            "INSERT INTO stories (story_id, title, gh_issue) VALUES (?, ?, ?)",
            (story_id, title, gh_issue),
        )
    conn.commit()
    conn.close()


def test_reconcile_plan_no_overlap_unions_everything(tmp_path):
    from synlynk.state_inventory import _reconcile_plan

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", None)])
    _make_stories_db(canonical, [("c-1", "Story B", None)])

    plan = _reconcile_plan(shard, canonical)

    assert [r["story_id"] for r in plan["to_add"]] == ["s-1"]
    assert plan["already_present"] == []
    assert plan["conflicts"] == []


def test_reconcile_plan_full_overlap_is_noop(tmp_path):
    from synlynk.state_inventory import _reconcile_plan

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", "#100")])
    _make_stories_db(canonical, [("s-1", "Story A", "#100")])

    plan = _reconcile_plan(shard, canonical)

    assert plan["to_add"] == []
    assert [r["story_id"] for r in plan["already_present"]] == ["s-1"]
    assert plan["conflicts"] == []


def test_reconcile_plan_detects_conflict(tmp_path):
    from synlynk.state_inventory import _reconcile_plan

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A, edited in shard", "#100")])
    _make_stories_db(canonical, [("s-1", "Story A, edited in canonical", "#100")])

    plan = _reconcile_plan(shard, canonical)

    assert plan["to_add"] == []
    assert plan["already_present"] == []
    assert [r["story_id"] for r in plan["conflicts"]] == ["s-1"]
