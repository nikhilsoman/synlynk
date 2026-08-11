import html as html_lib
import io
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse

import synlynk as sl
import synlynk.team as team_mod


def test_build_app_manifest_url_encodes_role_and_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    redirect_url = "http://127.0.0.1:4321/callback"
    url = sl._build_app_manifest_url("alpha-project", "review", redirect_url)

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
    assert manifest["redirect_url"] == redirect_url


def test_build_app_manifest_url_uses_org_or_personal_endpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    redirect_url = "http://127.0.0.1:4321/callback"

    org_url = sl._build_app_manifest_url("project", "review", redirect_url, "org", "Dialify")
    org_html = Path(unquote(urlparse(org_url).path)).read_text()
    assert 'action="https://github.com/organizations/Dialify/settings/apps/new"' in org_html

    user_url = sl._build_app_manifest_url("project", "review", redirect_url, "user", "nikhilsoman")
    user_html = Path(unquote(urlparse(user_url).path)).read_text()
    assert 'action="https://github.com/settings/apps/new"' in user_html


def test_resolve_repo_owner_classifies_org_and_user(monkeypatch):
    responses = iter([
        SimpleNamespace(returncode=0, stdout="Dialify\n", stderr=""),
        SimpleNamespace(returncode=0, stdout="Organization\n", stderr=""),
        SimpleNamespace(returncode=0, stdout="nikhilsoman\n", stderr=""),
        SimpleNamespace(returncode=0, stdout="User\n", stderr=""),
    ])
    monkeypatch.setattr(team_mod.subprocess, "run", lambda *args, **kwargs: next(responses))

    assert team_mod._resolve_repo_owner() == ("org", "Dialify")
    assert team_mod._resolve_repo_owner() == ("user", "nikhilsoman")


def test_resolve_repo_owner_falls_back_on_gh_failure(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(team_mod.subprocess, "run", fail)

    assert team_mod._resolve_repo_owner() == ("user", "")
    assert "could not resolve repository owner" in capsys.readouterr().out


def test_cmd_identity_init_role_retries_taken_app_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(team_mod, "_resolve_repo_owner", lambda cwd=None: ("org", "Dialify"))
    monkeypatch.setattr(team_mod, "_run_manifest_callback_server", lambda: (4321, iter(["first-code", "second-code"]).__next__, lambda: None))
    manifest_calls = []

    def build_manifest(project, role, redirect_url, owner_type, owner_login, app_name=None):
        manifest_calls.append((owner_type, owner_login, app_name))
        return f"file:///manifest-{len(manifest_calls)}.html"

    monkeypatch.setattr(team_mod, "_build_app_manifest_url", build_manifest)
    monkeypatch.setattr(team_mod.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(team_mod, "_confirm_installation", lambda slug, path: None)
    monkeypatch.setattr("synlynk.identity_roles.load_declared_roles", lambda: [])
    monkeypatch.setattr("synlynk.identity_roles.write_declared_roles", lambda roles: None)

    calls = []

    def exchange(code):
        calls.append(code)
        if len(calls) == 1:
            raise HTTPError(
                "https://api.github.com/app-manifests/code/conversions",
                422,
                "Validation Failed",
                {},
                io.BytesIO(b'{"message":"Validation Failed","errors":["Name is already taken"]}'),
            )
        return {"id": 1, "client_id": "client", "slug": "app", "pem": "pem"}

    monkeypatch.setattr(team_mod, "_exchange_manifest_code", exchange)

    team_mod.cmd_identity_init_role("review", project="project")

    assert calls == ["first-code", "second-code"]
    assert manifest_calls[0] == ("org", "Dialify", None)
    assert manifest_calls[1] == ("org", "Dialify", "synlynk-project-review-2")


def test_manifest_callback_server_captures_code():
    from urllib.request import urlopen

    port, wait_for_code, shutdown = sl._run_manifest_callback_server(timeout_seconds=2)
    try:
        with urlopen(f"http://127.0.0.1:{port}/callback?code=test123") as response:
            assert response.status == 200
            assert "close this tab" in response.read().decode()
        assert wait_for_code() == "test123"
    finally:
        shutdown()


def test_manifest_callback_server_times_out_without_code():
    port, wait_for_code, shutdown = sl._run_manifest_callback_server(timeout_seconds=1)
    try:
        assert port > 0
        assert wait_for_code() is None
    finally:
        shutdown()


def test_build_app_manifest_url_resolves_project_from_git_root_and_caps_name_length(tmp_path, monkeypatch):
    long_dir = tmp_path / "a-very-long-worktree-directory-name-for-a-feature-branch"
    long_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=long_dir, check=True)
    monkeypatch.chdir(long_dir)

    url = sl._build_app_manifest_url(None, "dev", "http://127.0.0.1:4321/callback")

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

    app_dir = tmp_path / ".synlynk" / "github_apps"
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
