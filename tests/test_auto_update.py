"""Unit tests for Smart Auto-Update & Background Notification Engine (v0.32.1)."""

import importlib
import json
import time
from pathlib import Path

import pytest

upgrade_mod = importlib.import_module("synlynk.upgrade")
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


def test_check_for_updates_respects_cache_ttl(tmp_path, monkeypatch):
    cache_file = tmp_path / "update_check.json"
    now = time.time()
    data = {
        "checked_at_ts": now - 300,
        "current_version": "0.32.0",
        "latest_version": "0.32.0",
        "update_available": False,
    }
    cache_file.write_text(json.dumps(data), encoding="utf-8")

    fetch_called = []
    monkeypatch.setattr(upgrade_mod, "fetch_latest_remote_version", lambda: fetch_called.append(1))
    res = check_for_updates_cached(cache_path=str(cache_file), ttl_seconds=86400)
    assert fetch_called == []
    assert res["update_available"] is False


def test_check_for_updates_fetches_when_expired(tmp_path, monkeypatch):
    cache_file = tmp_path / "update_check.json"
    now = time.time()
    data = {
        "checked_at_ts": now - 90000,
        "current_version": "0.32.0",
        "latest_version": "0.32.0",
        "update_available": False,
    }
    cache_file.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(upgrade_mod, "fetch_latest_remote_version", lambda: "0.32.1")
    res = check_for_updates_cached(
        current_version="0.32.0", cache_path=str(cache_file), ttl_seconds=86400
    )
    assert res["latest_version"] == "0.32.1"
    assert res["update_available"] is True


def test_maybe_auto_upgrade_disabled_by_default(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(upgrade_mod, "upgrade", lambda dry_run=False: calls.append(1))
    executed = maybe_auto_upgrade(config={"auto_upgrade": False})
    assert executed is False
    assert calls == []


def test_maybe_auto_upgrade_when_enabled(tmp_path, monkeypatch):
    cache_file = tmp_path / "update_check.json"
    write_update_cache(
        current_version="0.32.0",
        latest_version="0.32.1",
        update_available=True,
        cache_path=str(cache_file),
    )

    calls = []
    monkeypatch.setattr(upgrade_mod, "upgrade", lambda dry_run=False: calls.append(1))
    executed = maybe_auto_upgrade(
        config={"auto_upgrade": True}, cache_path=str(cache_file)
    )
    assert executed is True
    assert calls == [1]

