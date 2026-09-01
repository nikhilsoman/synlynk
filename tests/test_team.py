import html
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import synlynk.team as team_mod


def _manifest_from_url(url):
    form_path = Path(unquote(urlparse(url).path))
    form_html = form_path.read_text()
    match = re.search(r'name="manifest" value="([^"]*)"', form_html)
    assert match is not None
    return json.loads(html.unescape(match.group(1)))


def test_build_app_manifest_url_adds_administration_only_for_merge_roles(
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
    assert "administration" not in dev_manifest["default_permissions"]
