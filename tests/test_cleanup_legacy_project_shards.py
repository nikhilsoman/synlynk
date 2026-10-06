# tests/test_cleanup_legacy_project_shards.py
import os
import time


def _touch_with_mtime(path, mtime_ts):
    path.write_text("not a real sqlite file, just needs to exist")
    os.utime(path, (mtime_ts, mtime_ts))


def test_scan_shards_finds_all_state_db_files(tmp_path):
    from scripts.cleanup_legacy_project_shards import scan_shards

    projects_root = tmp_path / "projects"
    (projects_root / "abc123").mkdir(parents=True)
    (projects_root / "def456").mkdir(parents=True)
    _touch_with_mtime(projects_root / "abc123" / "state.db", time.time() - 86400)
    _touch_with_mtime(projects_root / "def456" / "state.db", time.time() - 86400)

    shards = scan_shards(projects_root)

    assert len(shards) == 2
    assert {s.path.parent.name for s in shards} == {"abc123", "def456"}


def test_is_safe_to_delete_rejects_shards_newer_than_cutoff(tmp_path):
    from scripts.cleanup_legacy_project_shards import is_safe_to_delete
    from datetime import date

    old_path = tmp_path / "old_state.db"
    _touch_with_mtime(old_path, time.mktime(date(2026, 9, 1).timetuple()))

    new_path = tmp_path / "new_state.db"
    _touch_with_mtime(new_path, time.mktime(date(2026, 9, 20).timetuple()))

    cutoff = date(2026, 9, 16)

    assert is_safe_to_delete(old_path, cutoff) is True
    assert is_safe_to_delete(new_path, cutoff) is False
