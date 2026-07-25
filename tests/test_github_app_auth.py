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


def test_get_installation_token_uses_cache_when_unexpired(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._token_cache.clear()
    gh_auth._token_cache["dev"] = {"token": "cached-token", "expires_at": time.time() + 300}

    def fail_if_called(*a, **kw):
        raise AssertionError("should not mint a new token when cache is fresh")

    monkeypatch.setattr(gh_auth, "_mint_installation_token", fail_if_called)
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}
    token = gh_auth.get_installation_token("dev", app_config)
    assert token == "cached-token"


def test_get_installation_token_mints_when_cache_expired(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._token_cache.clear()
    gh_auth._token_cache["dev"] = {"token": "stale-token", "expires_at": time.time() - 10}

    monkeypatch.setattr(
        gh_auth, "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("fresh-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}
    token = gh_auth.get_installation_token("dev", app_config)
    assert token == "fresh-token"
    assert gh_auth._token_cache["dev"]["token"] == "fresh-token"


def test_get_installation_token_mints_when_no_cache_entry(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._token_cache.clear()
    monkeypatch.setattr(
        gh_auth, "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("brand-new-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}
    token = gh_auth.get_installation_token("qa", app_config)
    assert token == "brand-new-token"
