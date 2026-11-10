import json
import os
from unittest.mock import patch, MagicMock
import pytest
import synlynk
from synlynk.events import (
    _existing_review_submitted_keys,
    _existing_spec_verified_pr_numbers,
    _existing_approval_resolved_keys,
    pending_events,
    scan_local_events,
)


def test_check_write_capability_uses_access_without_opening_raw_fd(tmp_path):
    """gh:#5197: Opening and closing a raw fd on an active SQLite database path
    strips all POSIX advisory locks held by the process for that inode.
    _check_write_capability must use os.access on existing files instead of os.open/os.close.
    """
    db_path = str(tmp_path / "test.db")
    with open(db_path, "w") as f:
        f.write("")

    with patch("os.open") as mock_open, patch("os.close") as mock_close:
        conn = synlynk._get_db(db_path)
        conn.close()

        open_args = [call.args[0] for call in mock_open.call_args_list if call.args]
        assert db_path not in open_args, f"os.open was called with {db_path!r}, which invalidates POSIX locks"
        assert mock_close.call_count == 0 or not any(
            call.args and call.args[0] == db_path for call in mock_close.call_args_list
        )


def test_events_inspection_helpers_use_read_only_db(tmp_path):
    """gh:#5197: Read-only inspection helpers in synlynk/events.py must use
    read_only=True so they do not churn write locks, run migrations, or execute BEGIN IMMEDIATE.
    """
    db_path = str(tmp_path / "test.db")
    init_conn = synlynk._get_db(db_path)
    init_conn.close()

    recorded_kwargs = []
    orig_get_db = synlynk._get_db

    def spy_get_db(*args, **kwargs):
        recorded_kwargs.append(dict(kwargs))
        return orig_get_db(db_path, *args, **kwargs)

    with patch.dict(os.environ, {"SYNLYNK_STATE_DB_PATH": db_path}):
        with patch.object(synlynk, "_get_db", side_effect=spy_get_db):
            recorded_kwargs.clear()
            _existing_review_submitted_keys(123)
            assert len(recorded_kwargs) == 1
            assert recorded_kwargs[0].get("read_only") is True, f"expected read_only=True for _existing_review_submitted_keys, got {recorded_kwargs[0]}"

            recorded_kwargs.clear()
            _existing_spec_verified_pr_numbers()
            assert len(recorded_kwargs) == 1
            assert recorded_kwargs[0].get("read_only") is True, f"expected read_only=True for _existing_spec_verified_pr_numbers, got {recorded_kwargs[0]}"

            recorded_kwargs.clear()
            _existing_approval_resolved_keys()
            assert len(recorded_kwargs) == 1
            assert recorded_kwargs[0].get("read_only") is True, f"expected read_only=True for _existing_approval_resolved_keys, got {recorded_kwargs[0]}"

            recorded_kwargs.clear()
            pending_events("harness", "event_type")
            assert len(recorded_kwargs) == 1
            assert recorded_kwargs[0].get("read_only") is True, f"expected read_only=True for pending_events, got {recorded_kwargs[0]}"


def test_scan_local_events_with_disk_backed_db_and_pr_reviews(tmp_path):
    """gh:#5197: End-to-end regression test for scan_local_events against a real
    disk-backed SQLite database with multiple merged PRs and review reviews.
    Must not encounter any disk I/O error or lock state mismatch.
    """
    db_path = str(tmp_path / "nudge" / "state.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    pr_list_stdout = json.dumps([
        {"number": 5196, "title": "Release v0.31.0", "mergedAt": "2026-11-10T13:25:00Z"},
        {"number": 5195, "title": "Track 2 Autonomous Fleet", "mergedAt": "2026-11-10T12:00:00Z"},
    ])
    reviews_stdout = json.dumps({
        "reviews": [
            {"author": {"login": "synlynk-synlynk-qa[bot]"}, "state": "APPROVED", "submittedAt": "2026-11-10T13:25:30Z"},
        ]
    })

    with patch.dict(os.environ, {"SYNLYNK_STATE_DB_PATH": db_path}):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout=pr_list_stdout),
                MagicMock(returncode=0, stdout=reviews_stdout),
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=0, stdout=reviews_stdout),
                MagicMock(returncode=0, stdout=""),
                MagicMock(returncode=0, stdout="[]"),
            ]
            scan_local_events("workspace-lifecycle-nudge")

    # Verify events recorded in the disk-backed database
    conn = synlynk._get_db(db_path, read_only=True)
    events = conn.execute("SELECT event_type FROM events ORDER BY id ASC").fetchall()
    conn.close()
    event_types = [e[0] for e in events]
    assert "cron_heartbeat" in event_types
    assert "pr_merged" in event_types
    assert "review_submitted" in event_types
