import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from synlynk.viz import (
    generate_roles_onboarding_html,
    handle_github_app_conversion,
    get_role_manifest_payload,
)


def test_get_role_manifest_payload():
    payload = get_role_manifest_payload("qa", repo_name="test-repo", port=27472)
    assert payload["name"] == "synlynk-qa-test-repo"
    assert "pull_requests" in payload["default_permissions"]
    assert payload["default_permissions"]["pull_requests"] == "write"
    assert "http://localhost:27472/auth/callback" in payload["redirect_url"]
    assert payload["hook_attributes"]["url"] == "https://synlynk.com/github-apps/test-repo/qa/webhook"
    assert payload["hook_attributes"]["active"] is False
    assert payload["default_events"] == []


def test_generate_roles_onboarding_html(tmp_path):
    html = generate_roles_onboarding_html(repo_root=str(tmp_path), port=27472)
    assert "Workspace Role Provisioning Wizard" in html
    assert "pm" in html
    assert "tpm" in html
    assert "qa" in html
    assert "dev" in html
    assert "architect" in html
    assert "marketing" in html
    assert "infra" in html
    assert "https://github.com/settings/apps/new" in html
    assert "/api/readiness/live" in html


def test_generate_roles_onboarding_html_org_and_identity_slug(tmp_path, monkeypatch):
    from synlynk import team
    monkeypatch.setattr(team, "_resolve_repo_owner", lambda cwd: ("org", "Dialify"))
    
    # Configure identity_slug: "vdowrx"
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({"identity_slug": "vdowrx"}))

    html = generate_roles_onboarding_html(repo_root=str(tmp_path), port=27472)
    assert "https://github.com/organizations/Dialify/settings/apps/new" in html
    assert "synlynk-dialify-vdowrx-pm" in html
    assert "synlynk-dialify-vdowrx-qa" in html
    assert "synlynk-dialify-vdowrx-dev" in html
    assert "synlynk-dialify-vdowrx-infra" in html


def test_handle_github_app_conversion_mock(tmp_path):
    mock_response = {
        "id": 123456,
        "slug": "synlynk-qa-test",
        "client_id": "Iv1.test",
        "client_secret": "secret123",
        "pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----",
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = handle_github_app_conversion(
            code="test_code_123",
            role="qa",
            repo_root=str(tmp_path),
        )

        assert res["ok"] is True
        assert res["role"] == "qa"
        assert res["app_id"] == 123456

        # Verify files written
        apps_dir = tmp_path / ".synlynk" / "github_apps" / "qa"
        assert (apps_dir / "qa.app.json").exists()
        assert (apps_dir / "qa.private-key.pem").exists()
        app_json = json.loads((apps_dir / "qa.app.json").read_text())
        assert app_json["id"] == 123456


def test_viz_auth_sync_handler(tmp_path, monkeypatch):
    from synlynk.viz import VizorHandler
    import io
    monkeypatch.chdir(tmp_path)

    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "pm.json").write_text(json.dumps({
        "role": "pm",
        "app_id": 12345,
        "private_key_path": str(apps_dir / "pm.pem"),
    }))
    (apps_dir / "pm.pem").write_text("FAKE_PEM")

    class DummyServer:
        server_port = 27472

    handler = VizorHandler.__new__(VizorHandler)
    handler.server = DummyServer()
    handler.requestline = "GET /auth/sync?role=pm HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.path = "/auth/sync?role=pm"
    handler.rfile = io.BytesIO()
    handler.wfile = io.BytesIO()
    handler.headers = {}
    handler._headers_buffer = []

    def fake_sign_jwt(app_id, pem_path):
        return "fake.jwt.token"

    monkeypatch.setattr("synlynk.github_app_auth._sign_jwt", fake_sign_jwt)
    monkeypatch.setattr("synlynk.github_app_auth.refresh_installation_token", lambda *a, **kw: None)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([{"id": 998877, "account": {"login": "Dialify"}}]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        handler.do_GET()

    # Verify installation_id was recorded in pm.json
    conf = json.loads((apps_dir / "pm.json").read_text())
    assert conf.get("installation_id") == 998877

