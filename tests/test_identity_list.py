import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cmd_identity_list_reports_provisioned_and_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("roles:\n  - dev\n  - qa\n")
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir()
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "app_slug": "proj-dev", "installation_id": "9",
    }))

    from synlynk.team import cmd_identity_list

    cmd_identity_list()
    out = capsys.readouterr().out
    assert "dev" in out and "proj-dev" in out
    assert "qa" in out and "not provisioned" in out


def test_identity_revoke_removes_app_files_and_disables_agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(fake_home)))
    from synlynk import agent_store, team
    from synlynk.identity_roles import write_declared_roles
    from synlynk.product_store import resolve_github_apps_dir

    agent_store.register_agent("secops", [{"kind": "role_slug", "value": "secops"}])
    write_declared_roles(["secops"])
    apps_dir = resolve_github_apps_dir(".")
    apps_dir.mkdir(parents=True, exist_ok=True)
    (apps_dir / "secops.json").write_text("{}")
    (apps_dir / "secops.pem").write_text("fake-key")

    team.cmd_identity_revoke("secops", actor="nikhil")

    assert not (apps_dir / "secops.json").exists()
    assert not (apps_dir / "secops.pem").exists()
    from synlynk.identity_roles import load_declared_roles
    assert "secops" not in load_declared_roles()
    entries = [e for e in agent_store.list_agents() if e["agent_id"] == "secops"]
    assert entries[0]["disabled"] is True

