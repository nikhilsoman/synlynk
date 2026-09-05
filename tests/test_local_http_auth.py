import os

from synlynk.local_http_auth import (
    TOKEN_HEADER,
    authorize_local_request,
    ensure_local_token,
    local_browser_origin_ok,
)


def test_ensure_local_token_creates_file_with_0600(tmp_path):
    path = tmp_path / "daemon.token"
    token = ensure_local_token(str(path))
    assert token
    assert path.is_file()
    assert (path.stat().st_mode & 0o777) == 0o600
    assert path.read_text() == token
    assert ensure_local_token(str(path)) == token


def test_ensure_local_token_tightens_existing_permissions(tmp_path):
    path = tmp_path / "daemon.token"
    path.write_text("already-there")
    os.chmod(path, 0o644)
    token = ensure_local_token(str(path))
    assert token == "already-there"
    assert (path.stat().st_mode & 0o777) == 0o600


def test_authorize_rejects_missing_and_wrong_token(tmp_path):
    path = str(tmp_path / "daemon.token")
    expected = ensure_local_token(path)
    ok, code, _ = authorize_local_request({}, path=path)
    assert ok is False
    assert code == 401
    ok, code, _ = authorize_local_request({TOKEN_HEADER: "nope"}, path=path)
    assert ok is False
    assert code == 401
    ok, code, _ = authorize_local_request({TOKEN_HEADER: expected}, path=path)
    assert ok is True
    assert code == 200


def test_local_origin_allows_cli_and_localhost_rejects_foreign():
    assert local_browser_origin_ok({}) is True
    assert local_browser_origin_ok({"Origin": "http://localhost:8721"}) is True
    assert local_browser_origin_ok({"Origin": "http://127.0.0.1:27471"}) is True
    assert local_browser_origin_ok({"Referer": "http://localhost:8721/gantt.html"}) is True
    assert local_browser_origin_ok({"Origin": "https://evil.example"}) is False
    assert local_browser_origin_ok({"Origin": "null"}) is False
