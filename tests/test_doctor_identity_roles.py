import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_hc_identity_roles_warns_on_missing_provisioning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("roles:\n  - dev\n  - qa\n")

    from synlynk.doctor import _hc_identity_roles

    result = _hc_identity_roles()
    assert result.status == "warn"
    assert "dev" in result.message and "qa" in result.message
    assert "synlynk identity init --role" in result.fix


def test_hc_identity_roles_ok_when_all_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("roles:\n  - dev\n")
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir()
    (apps_dir / "dev.json").write_text('{"role": "dev", "installation_id": "1"}')

    from synlynk.doctor import _hc_identity_roles

    result = _hc_identity_roles()
    assert result.status == "ok"


def _durable_agent(monkeypatch, role="dev"):
    from synlynk import agent_store

    monkeypatch.setattr(
        agent_store,
        "list_agents",
        lambda: [{"agent_id": f"{role}-primary", "aliases": [{"kind": "role_slug", "value": role}]}],
    )
    monkeypatch.setattr(
        agent_store,
        "read_charter",
        lambda _agent_id: (f"---\ndurability: durable\n---\n", 1),
    )


def test_hc_identity_roles_fails_durable_role_without_app_material(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text('{"task_allocation": {"gh_write": {}}}')
    _durable_agent(monkeypatch)

    from synlynk.doctor import _hc_identity_roles

    result = _hc_identity_roles()
    assert result.status == "fail"
    assert "dev" in result.message
    assert "App material" in result.message


def test_hc_identity_roles_accepts_nested_app_material(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text('{"task_allocation": {"gh_write": {}}}')
    app_dir = tmp_path / ".synlynk" / "github_apps" / "dev"
    app_dir.mkdir(parents=True)
    (app_dir / "dev.app.json").write_text("{}")
    _durable_agent(monkeypatch)

    from synlynk.doctor import _hc_identity_roles

    result = _hc_identity_roles()
    assert result.status == "warn"
