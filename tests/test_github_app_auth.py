"""Tests for synlynk.github_app_auth."""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.github_app_auth import _b64url_decode, _build_jwt_signing_input


def test_build_jwt_signing_input_has_correct_header_and_claims():
    signing_input, header, payload = _build_jwt_signing_input(app_id="123456", now=1700000000)
    header_json = json.loads(_b64url_decode(header))
    payload_json = json.loads(_b64url_decode(payload))
    assert header_json == {"alg": "RS256", "typ": "JWT"}
    assert payload_json["iss"] == "123456"
    assert payload_json["iat"] == 1700000000 - 60
    assert payload_json["exp"] == 1700000000 + 540
    assert signing_input == header + b"." + payload


def test_resolve_openssl_path_raises_clear_error_when_missing(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._openssl_path_cache = None
    monkeypatch.setattr(gh_auth.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="openssl not found"):
        gh_auth._resolve_openssl_path()


def test_resolve_openssl_path_caches_after_first_resolution(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._openssl_path_cache = None
    calls = []
    monkeypatch.setattr(gh_auth.shutil, "which", lambda name: calls.append(name) or "/usr/bin/openssl")
    first = gh_auth._resolve_openssl_path()
    second = gh_auth._resolve_openssl_path()
    assert first == second == "/usr/bin/openssl"
    assert len(calls) == 1


def test_read_cached_installation_token_returns_fresh_token(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".synlynk" / "github_apps"
    cache_dir.mkdir(parents=True)
    (cache_dir / "dev.token.json").write_text(json.dumps({
        "token": "fresh-token", "expires_at": time.time() + 300,
    }))

    assert gh_auth.read_cached_installation_token("dev") == "fresh-token"


def test_read_cached_installation_token_returns_none_when_stale(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".synlynk" / "github_apps"
    cache_dir.mkdir(parents=True)
    (cache_dir / "dev.token.json").write_text(json.dumps({
        "token": "stale-token", "expires_at": time.time() - 10,
    }))

    assert gh_auth.read_cached_installation_token("dev") is None


def test_read_cached_installation_token_returns_none_when_missing(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    assert gh_auth.read_cached_installation_token("dev") is None


def test_read_cached_installation_token_returns_none_when_corrupt(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".synlynk" / "github_apps"
    cache_dir.mkdir(parents=True)
    (cache_dir / "dev.token.json").write_text("not json")

    assert gh_auth.read_cached_installation_token("dev") is None


def test_refresh_installation_token_writes_cache_file_with_0600(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    expires = time.time() + 3600
    monkeypatch.setattr(
        gh_auth,
        "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("fresh-token", expires),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}

    gh_auth.refresh_installation_token("dev", app_config)

    cache_path = tmp_path / ".synlynk" / "github_apps" / "dev.token.json"
    assert cache_path.exists()
    data = json.loads(cache_path.read_text())
    assert data["token"] == "fresh-token"
    assert data["expires_at"] == expires
    assert (cache_path.stat().st_mode & 0o777) == 0o600


def test_refresh_installation_token_persists_redaction_cache(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gh_auth,
        "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("persisted-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}

    gh_auth.refresh_installation_token("dev", app_config)

    cache_path = tmp_path / ".synlynk" / "token_redaction_cache.json"
    assert cache_path.exists()
    cache_data = json.loads(cache_path.read_text())
    assert cache_data["persisted-token"]["role"] == "dev"


def test_refresh_installation_token_round_trips_into_read_cache(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gh_auth,
        "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("round-trip-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}

    gh_auth.refresh_installation_token("qa", app_config)

    assert gh_auth.read_cached_installation_token("qa") == "round-trip-token"


def test_load_redaction_tokens_omits_expired_entries(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    cache_path = tmp_path / ".synlynk" / "token_redaction_cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({
        "expired-token": {"expires_at": time.time() - 10, "role": "dev"},
        "valid-token": {"expires_at": time.time() + 3600, "role": "dev"},
    }))

    tokens = gh_auth._load_redaction_tokens()

    assert tokens == ["valid-token"]


def test_refresh_installation_token_writes_to_explicit_apps_dir(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    other_cwd = tmp_path / "unrelated_cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    apps_dir = tmp_path / "worktree_common" / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    expires = time.time() + 3600
    monkeypatch.setattr(gh_auth, "_mint_installation_token",
                        lambda app_id, installation_id, private_key_path: ("worktree-token", expires))
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}
    gh_auth.refresh_installation_token("qa", app_config, apps_dir=str(apps_dir))
    cache_path = apps_dir / "qa.token.json"
    assert cache_path.exists()
    assert json.loads(cache_path.read_text())["token"] == "worktree-token"
    assert not (other_cwd / ".synlynk" / "github_apps" / "qa.token.json").exists()


def test_resolve_private_key_path_from_worktree(tmp_path, monkeypatch):
    from synlynk import github_app_auth as gh_auth

    repo_dir = tmp_path / "main_repo"
    apps_dir = repo_dir / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_file = apps_dir / "architect.pem"
    pem_file.write_text("fake-pem-key")

    worktree_dir = tmp_path / "worktrees" / "job-12345"
    worktree_dir.mkdir(parents=True)
    monkeypatch.chdir(worktree_dir)

    # 1. Given relative path .synlynk/github_apps/architect.pem and explicit apps_dir
    resolved = gh_auth._resolve_private_key_path(".synlynk/github_apps/architect.pem", apps_dir=str(apps_dir))
    assert os.path.isabs(resolved)
    assert os.path.samefile(resolved, pem_file)

    # 2. Given just filename architect.pem and explicit apps_dir
    resolved2 = gh_auth._resolve_private_key_path("architect.pem", apps_dir=str(apps_dir))
    assert os.path.isabs(resolved2)
    assert os.path.samefile(resolved2, pem_file)

    # 3. Already absolute path
    resolved3 = gh_auth._resolve_private_key_path(str(pem_file))
    assert resolved3 == str(pem_file)


def test_refresh_installation_token_resolves_relative_pem_path_to_absolute(tmp_path, monkeypatch):
    from synlynk import github_app_auth as gh_auth

    apps_dir = tmp_path / "repo" / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_file = apps_dir / "architect.pem"
    pem_file.write_text("fake-pem-key")

    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()
    monkeypatch.chdir(worktree_dir)

    minted_pem_paths = []
    monkeypatch.setattr(
        gh_auth,
        "_mint_installation_token",
        lambda app_id, inst_id, pem_path: minted_pem_paths.append(pem_path) or ("tok", time.time() + 300)
    )

    app_config = {
        "app_id": "4536677",
        "installation_id": "12345",
        "private_key_path": ".synlynk/github_apps/architect.pem",
    }
    gh_auth.refresh_installation_token("architect", app_config, apps_dir=str(apps_dir))

    assert len(minted_pem_paths) == 1
    assert os.path.isabs(minted_pem_paths[0])
    assert os.path.samefile(minted_pem_paths[0], pem_file)

