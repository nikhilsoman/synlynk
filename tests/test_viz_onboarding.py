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


def test_generate_roles_onboarding_html(tmp_path):
    html = generate_roles_onboarding_html(repo_root=str(tmp_path), port=27472)
    assert "Workspace Role Provisioning Wizard" in html
    assert "pm" in html
    assert "tpm" in html
    assert "qa" in html
    assert "dev" in html
    assert "architect" in html
    assert "marketing" in html
    assert "https://github.com/settings/apps/new" in html
    assert "/api/readiness/live" in html


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
