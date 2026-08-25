"""Tests for WatchDaemon's GitHub App token refresh responsibility."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))

from synlynk.daemon import WatchDaemon


def test_refresh_github_tokens_refreshes_each_provisioned_role(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "2", "installation_id": "20", "private_key_path": "qa.pem",
    }))

    refreshed = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth, "refresh_installation_token",
        lambda role, app_config: refreshed.append(role),
    )

    WatchDaemon()._refresh_github_tokens()

    assert sorted(refreshed) == ["dev", "qa"]


def test_refresh_github_tokens_one_role_failure_does_not_block_others(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "2", "installation_id": "20", "private_key_path": "qa.pem",
    }))

    refreshed = []
    import synlynk.daemon as daemon_mod

    def fake_refresh(role, app_config):
        if role == "dev":
            raise RuntimeError("installation revoked")
        refreshed.append(role)

    monkeypatch.setattr(daemon_mod.github_app_auth, "refresh_installation_token", fake_refresh)

    WatchDaemon()._refresh_github_tokens()

    assert refreshed == ["qa"]
    assert "installation revoked" in capsys.readouterr().err


def test_refresh_github_tokens_skips_token_cache_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "dev.token.json").write_text(json.dumps({"token": "x", "expires_at": time.time() + 3600}))

    refreshed = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth, "refresh_installation_token",
        lambda role, app_config: refreshed.append(role),
    )

    WatchDaemon()._refresh_github_tokens()

    assert refreshed == ["dev"]
