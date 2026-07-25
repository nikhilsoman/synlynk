import html as html_lib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

import synlynk as sl


def test_build_app_manifest_url_encodes_role_and_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    url = sl._build_app_manifest_url("alpha-project", "review")

    assert url.startswith("file://")
    form_path = Path(unquote(urlparse(url).path))
    form_html = form_path.read_text()
    assert 'action="https://github.com/settings/apps/new"' in form_html
    assert 'method="post"' in form_html

    match = re.search(r'name="manifest" value="([^"]*)"', form_html)
    assert match is not None
    manifest = json.loads(html_lib.unescape(match.group(1)))
    assert manifest["name"] == "synlynk-alpha-project-review"
    assert "alpha-project" in manifest["hook_attributes"]["url"]
    assert "review" in manifest["redirect_url"]


def test_build_app_manifest_url_resolves_project_from_git_root_and_caps_name_length(tmp_path, monkeypatch):
    long_dir = tmp_path / "a-very-long-worktree-directory-name-for-a-feature-branch"
    long_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=long_dir, check=True)
    monkeypatch.chdir(long_dir)

    url = sl._build_app_manifest_url(None, "dev")

    form_path = Path(unquote(urlparse(url).path))
    form_html = form_path.read_text()
    match = re.search(r'name="manifest" value="([^"]*)"', form_html)
    assert match is not None
    manifest = json.loads(html_lib.unescape(match.group(1)))

    assert len(manifest["name"]) <= 34
    assert manifest["name"].startswith("synlynk-")
    assert manifest["name"].endswith("-dev")
    assert manifest["name"] != "synlynk-a-very-long-worktree-directory-name-for-a-feature-branch-dev"


def test_cmd_identity_init_role_noops_if_already_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    app_dir = tmp_path / "synlynk" / "github_apps"
    app_dir.mkdir(parents=True)
    pem_path = app_dir / "review.pem"
    pem_path.write_text("PRIVATE KEY")

    json_path = app_dir / "review.json"
    json_path.write_text(
        json.dumps(
            {
                "role": "review",
                "app_id": 42,
                "client_id": "client-1",
                "app_slug": "synlynk-review",
                "installation_id": 99,
                "private_key_path": str(pem_path),
            },
            indent=2,
        )
        + "\n"
    )

    monkeypatch.setattr(sl, "_exchange_manifest_code", lambda code: (_ for _ in ()).throw(AssertionError("should not exchange")))
    monkeypatch.setattr(sl, "_confirm_installation", lambda app_slug, path: (_ for _ in ()).throw(AssertionError("should not confirm")))
    monkeypatch.setattr("builtins.input", lambda prompt="": (_ for _ in ()).throw(AssertionError("should not prompt")))

    sl.cmd_identity_init_role("review")

    assert json.loads(json_path.read_text())["installation_id"] == 99
