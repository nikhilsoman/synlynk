import os
import sqlite3
import time

import pytest

from synlynk.state_inventory import _read_stories, inventory


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
    """Create a stories table and insert rows.

    Each row is a (story_id, title, gh_issue) 3-tuple, or a
    (story_id, title, gh_issue, created_at) 4-tuple when the test needs to
    pin an explicit created_at value instead of relying on the column's
    DEFAULT CURRENT_TIMESTAMP.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT, "
        "gh_issue TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    for row in rows:
        if len(row) == 4:
            story_id, title, gh_issue, created_at = row
            conn.execute(
                "INSERT INTO stories (story_id, title, gh_issue, created_at) VALUES (?, ?, ?, ?)",
                (story_id, title, gh_issue, created_at),
            )
        else:
            story_id, title, gh_issue = row
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


def test_apply_reconcile_backs_up_and_merges(tmp_path):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", None), ("s-2", "Story B", None)])
    _make_stories_db(canonical, [("c-1", "Story C", None)])

    result = apply_reconcile(shard, canonical)

    assert result["added"] == 2
    assert result["skipped_conflicts"] == 0
    backups = list(canonical.parent.glob("state.db.pre-reconcile-*.bak"))
    assert len(backups) == 1

    merged = _read_stories(canonical)
    assert set(merged.keys()) == {"c-1", "s-1", "s-2"}


def test_apply_reconcile_preserves_gh_issue_and_created_at(tmp_path):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", "#100", "2026-01-01 00:00:00")])
    _make_stories_db(canonical, [])

    result = apply_reconcile(shard, canonical)

    assert result["added"] == 1
    merged = _read_stories(canonical)
    assert merged["s-1"]["gh_issue"] == "#100"
    assert merged["s-1"]["created_at"] == "2026-01-01 00:00:00"


def test_apply_reconcile_skips_conflicts_by_default(tmp_path):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A, shard version", None)])
    _make_stories_db(canonical, [("s-1", "Story A, canonical version", None)])

    result = apply_reconcile(shard, canonical)

    assert result["added"] == 0
    assert result["skipped_conflicts"] == 1
    merged = _read_stories(canonical)
    assert merged["s-1"]["title"] == "Story A, canonical version"


def test_apply_reconcile_raises_on_conflict_without_ignore_flag(tmp_path):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A, shard version", None)])
    _make_stories_db(canonical, [("s-1", "Story A, canonical version", None)])

    with pytest.raises(ValueError, match="conflict"):
        apply_reconcile(shard, canonical, ignore_conflicts=False)


def test_apply_reconcile_rolls_back_on_failure(tmp_path, monkeypatch):
    from synlynk.state_inventory import apply_reconcile

    shard = tmp_path / "shard" / "state.db"
    canonical = tmp_path / "canonical" / "state.db"
    _make_stories_db(shard, [("s-1", "Story A", None)])
    _make_stories_db(canonical, [("c-1", "Story C", None)])

    before = _read_stories(canonical)

    import sqlite3 as sqlite3_module
    real_connect = sqlite3_module.connect

    class _BoomConnection(sqlite3_module.Connection):
        def execute(self, sql, *a, **k):
            if sql.strip().upper().startswith("INSERT"):
                raise sqlite3_module.OperationalError("simulated failure")
            return super().execute(sql, *a, **k)

    def _boom(*args, **kwargs):
        kwargs["factory"] = _BoomConnection
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3_module, "connect", _boom)

    with pytest.raises(sqlite3_module.OperationalError):
        apply_reconcile(shard, canonical)

    after = _read_stories(canonical)
    assert after == before


def _add_identity(path, product_id):
    """Stamp an existing stories DB with a state_identity row for fingerprint matching."""
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
    conn.commit()
    conn.close()


def test_cmd_state_inventory_reconcile_dry_run_prints_plan(tmp_path, monkeypatch, capsys):
    from synlynk.state_inventory import cmd_state_inventory

    home = tmp_path / "home" / ".synlynk"
    monkeypatch.setattr(
        "os.path.expanduser",
        lambda p: str(tmp_path / "home" / ".synlynk") if p == "~/.synlynk" else p,
    )

    canonical = home / "workspaces" / "myproj" / "state.db"
    _make_stories_db(canonical, [("c-1", "Existing story", None)])
    legacy = home / "projects" / "abc12345" / "state.db"
    _make_stories_db(legacy, [("s-1", "Orphaned story", None)])
    # Give the shard and canonical a shared product_id so _match_project's
    # fingerprint matching can resolve the legacy shard to slug "myproj"
    # (the two DBs have no overlapping story titles to match on otherwise).
    _add_identity(canonical, "prod-myproj")
    _add_identity(legacy, "prod-myproj")

    repo = tmp_path / "repo"
    repo.mkdir()

    exit_code = cmd_state_inventory(repo_root=str(repo), reconcile_slug="myproj", apply=False)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "to_add" in captured.out or "Orphaned story" in captured.out
    # Dry run: canonical must be untouched
    canonical_after = _read_stories(canonical)
    assert set(canonical_after.keys()) == {"c-1"}
    assert canonical_after["c-1"]["story_id"] == "c-1"
    assert canonical_after["c-1"]["title"] == "Existing story"


def test_cmd_state_inventory_reconcile_respects_cutoff_days(tmp_path, monkeypatch, capsys):
    from synlynk.state_inventory import cmd_state_inventory

    monkeypatch.setattr(
        "os.path.expanduser",
        lambda p: str(tmp_path / "home" / ".synlynk") if p == "~/.synlynk" else p,
    )
    home = tmp_path / "home" / ".synlynk"

    canonical = home / "workspaces" / "myproj" / "state.db"
    _make_stories_db(canonical, [("c-1", "Existing story", None)])
    legacy = home / "projects" / "abc12345" / "state.db"
    _make_stories_db(legacy, [("s-1", "Orphaned story", None)])
    _add_identity(canonical, "prod-myproj")
    _add_identity(legacy, "prod-myproj")

    old_time = time.time() - (100 * 86400)
    os.utime(legacy, (old_time, old_time))

    repo = tmp_path / "repo"
    repo.mkdir()

    exit_code = cmd_state_inventory(
        repo_root=str(repo), reconcile_slug="myproj", apply=False, cutoff_days=10,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "skipping" in captured.out
    assert "no legacy shards matched" in captured.out or "skipping" in captured.out
