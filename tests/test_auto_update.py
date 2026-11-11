"""Unit tests for Smart Auto-Update & Background Notification Engine (v0.32.1)."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from synlynk.upgrade import (
    _ver_tuple,
    check_for_updates_cached,
    get_update_notice,
    maybe_auto_upgrade,
    read_update_cache,
    write_update_cache,
)


def test_version_tuple_comparison():
    assert _ver_tuple("0.32.1") > _ver_tuple("0.32.0")
    assert _ver_tuple("0.33.0") > _ver_tuple("0.32.9")
    assert _ver_tuple("1.0.0") > _ver_tuple("0.99.99")
    assert _ver_tuple("0.32.0") == _ver_tuple("0.32.0")


def test_write_and_read_update_cache(tmp_path):
    cache_file = tmp_path / "update_check.json"
    write_update_cache(
        current_version="0.32.0",
        latest_version="0.32.1",
        update_available=True,
        cache_path=str(cache_file),
    )
    assert cache_file.exists()

    data = read_update_cache(cache_path=str(cache_file))
    assert data is not None
    assert data["current_version"] == "0.32.0"
    assert data["latest_version"] == "0.32.1"
    assert data["update_available"] is True


def test_get_update_notice_when_update_available(tmp_path):
    cache_file = tmp_path / "update_check.json"
    write_update_cache(
        current_version="0.32.0",
        latest_version="0.32.1",
        update_available=True,
        cache_path=str(cache_file),
    )

    notice = get_update_notice(cache_path=str(cache_file))
    assert notice is not None
    assert "0.32.0" in notice
    assert "0.32.1" in notice
    assert "synlynk upgrade" in notice


def test_get_update_notice_when_up_to_date(tmp_path):
    cache_file = tmp_path / "update_check.json"
    write_update_cache(
        current_version="0.32.0",
        latest_version="0.32.0",
        update_available=False,
        cache_path=str(cache_file),
    )

    notice = get_update_notice(cache_path=str(cache_file))
    assert notice is None


def test_check_for_updates_respects_cache_ttl(tmp_path):
    cache_file = tmp_path / "update_check.json"
    # Seed fresh cache (5 minutes ago)
    now = time.time()
    data = {
        "checked_at_ts": now - 300,
        "current_version": "0.32.0",
        "latest_version": "0.32.0",
        "update_available": False,
    }
    cache_file.write_text(json.dumps(data), encoding="utf-8")

    # Call check_for_updates_cached - network call should NOT happen
    with patch("synlynk.upgrade.fetch_latest_remote_version") as mock_fetch:
        res = check_for_updates_cached(cache_path=str(cache_file), ttl_seconds=86400)
        assert mock_fetch.call_count == 0
        assert res["update_available"] is False


def test_check_for_updates_fetches_when_expired(tmp_path):
    cache_file = tmp_path / "update_check.json"
    # Seed stale cache (25 hours ago)
    now = time.time()
    data = {
        "checked_at_ts": now - 90000,
        "current_version": "0.32.0",
        "latest_version": "0.32.0",
        "update_available": False,
    }
    cache_file.write_text(json.dumps(data), encoding="utf-8")

    with patch("synlynk.upgrade.fetch_latest_remote_version", return_value="0.32.1"):
        res = check_for_updates_cached(
            current_version="0.32.0", cache_path=str(cache_file), ttl_seconds=86400
        )
        assert res["latest_version"] == "0.32.1"
        assert res["update_available"] is True


def test_maybe_auto_upgrade_disabled_by_default(tmp_path):
    with patch("synlynk.upgrade.upgrade") as mock_upgrade:
        executed = maybe_auto_upgrade(config={"auto_upgrade": False})
        assert executed is False
        assert mock_upgrade.call_count == 0


def test_maybe_auto_upgrade_when_enabled(tmp_path):
    cache_file = tmp_path / "update_check.json"
    write_update_cache(
        current_version="0.32.0",
        latest_version="0.32.1",
        update_available=True,
        cache_path=str(cache_file),
    )

    with patch("synlynk.upgrade.upgrade") as mock_upgrade:
        executed = maybe_auto_upgrade(
            config={"auto_upgrade": True}, cache_path=str(cache_file)
        )
        assert executed is True
        assert mock_upgrade.call_count == 1
