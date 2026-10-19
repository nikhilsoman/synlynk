import html
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

import synlynk.team as team_mod


def _manifest_from_url(url):
    form_path = Path(unquote(urlparse(url).path))
    form_html = form_path.read_text()
    match = re.search(r'name="manifest" value="([^"]*)"', form_html)
    assert match is not None
    return json.loads(html.unescape(match.group(1)))


def test_implement_1436_leftover_charter_patch_so_merge_roles_request_actions_write(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        team_mod,
        "load_policy",
        lambda repo_path: {"merge_authority": {"can_merge": ["qa"]}},
    )

    qa_manifest = _manifest_from_url(
        team_mod._build_app_manifest_url("project", "qa", "http://127.0.0.1/callback")
    )
    dev_manifest = _manifest_from_url(
        team_mod._build_app_manifest_url("project", "dev", "http://127.0.0.1/callback")
    )

    assert qa_manifest["default_permissions"]["administration"] == "write"
    assert qa_manifest["default_permissions"]["actions"] == "write"
    assert "administration" not in dev_manifest["default_permissions"]
    assert "actions" not in dev_manifest["default_permissions"]


def test_write_role_app_paths_uses_product_store_after_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"identity_slug": "test-product"}, f)
    from synlynk.team import _write_role_app_paths
    app_dir, app_json, app_pem = _write_role_app_paths("dev")
    # Must not silently fall back to the bare legacy dir once the repo is configured.
    assert str(app_dir) != os.path.join(".synlynk", "github_apps")


def test_ensure_type_for_identity_init_does_not_skip_after_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"identity_slug": "test-product"}, f)
    from synlynk.team import ensure_type_for_identity_init, UnknownType
    # Must reach the type-lookup logic (and raise UnknownType for a bogus
    # type) instead of returning silently because it thinks the repo is
    # unconfigured.
    with pytest.raises(UnknownType):
        ensure_type_for_identity_init("definitely-not-a-real-type")


def test_panel_text_handles_bytes():
    from synlynk.team import _panel_text

    raw_bytes = b"hello from stderr bytes"
    assert _panel_text(raw_bytes) == "hello from stderr bytes"
    long_bytes = b"x" * 2000
    assert len(_panel_text(long_bytes, limit=100)) == 103

