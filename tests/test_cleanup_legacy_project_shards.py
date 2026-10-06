# tests/test_cleanup_legacy_project_shards.py
import os
import time
from pathlib import Path


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


# tests/test_cleanup_legacy_project_shards.py (append)
from datetime import date


def test_dry_run_reports_counts_and_leaves_files_untouched(tmp_path, capsys):
    from scripts.cleanup_legacy_project_shards import run_cleanup

    projects_root = tmp_path / "projects"
    (projects_root / "old1").mkdir(parents=True)
    (projects_root / "old2").mkdir(parents=True)
    (projects_root / "recent").mkdir(parents=True)
    _touch_with_mtime(projects_root / "old1" / "state.db", time.mktime(date(2026, 8, 1).timetuple()))
    _touch_with_mtime(projects_root / "old2" / "state.db", time.mktime(date(2026, 8, 15).timetuple()))
    _touch_with_mtime(projects_root / "recent" / "state.db", time.mktime(date(2026, 9, 20).timetuple()))

    report_path = tmp_path / "report.txt"
    result = run_cleanup(
        projects_root=projects_root,
        cutoff=date(2026, 9, 16),
        execute=False,
        report_path=report_path,
    )

    assert result.deletable_count == 2
    assert result.skipped_count == 1
    assert result.deleted_count == 0
    assert (projects_root / "old1" / "state.db").exists()
    assert (projects_root / "old2" / "state.db").exists()
    assert (projects_root / "recent" / "state.db").exists()
    assert report_path.exists()
    report_text = report_path.read_text()
    assert "old1" in report_text
    assert "old2" in report_text
    assert "recent" in report_text


# tests/test_cleanup_legacy_project_shards.py (append)
def test_execute_deletes_only_shards_older_than_cutoff(tmp_path):
    from scripts.cleanup_legacy_project_shards import run_cleanup

    projects_root = tmp_path / "projects"
    (projects_root / "old1").mkdir(parents=True)
    (projects_root / "recent").mkdir(parents=True)
    old_path = projects_root / "old1" / "state.db"
    recent_path = projects_root / "recent" / "state.db"
    _touch_with_mtime(old_path, time.mktime(date(2026, 8, 1).timetuple()))
    _touch_with_mtime(recent_path, time.mktime(date(2026, 9, 20).timetuple()))

    report_path = tmp_path / "report.txt"
    result = run_cleanup(
        projects_root=projects_root,
        cutoff=date(2026, 9, 16),
        execute=True,
        report_path=report_path,
    )

    assert result.deleted_count == 1
    assert not old_path.exists()
    assert recent_path.exists()


# tests/test_cleanup_legacy_project_shards.py (append)
def test_parse_args_defaults():
    from scripts.cleanup_legacy_project_shards import parse_args

    args = parse_args([])
    assert args.execute is False
    assert args.cutoff_date == date(2026, 9, 16)
    assert args.projects_root == Path.home() / ".synlynk" / "projects"


def test_parse_args_overrides():
    from scripts.cleanup_legacy_project_shards import parse_args

    args = parse_args(["--execute", "--cutoff-date", "2026-10-01"])
    assert args.execute is True
    assert args.cutoff_date == date(2026, 10, 1)
