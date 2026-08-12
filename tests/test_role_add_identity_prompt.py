import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_identity_init_role_registers_new_role_in_roles_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.team as team_mod

    monkeypatch.setattr(
        team_mod,
        "_build_app_manifest_url",
        lambda project, role, redirect_url=None, owner_type="user", owner_login="", app_name=None: "http://fake",
    )
    monkeypatch.setattr(team_mod, "_run_manifest_callback_server", lambda: (1234, lambda: None, lambda: None))
    monkeypatch.setattr(team_mod, "input", lambda prompt: "fake-code", raising=False)
    monkeypatch.setattr(team_mod, "_exchange_manifest_code", lambda code: {
        "id": 1, "client_id": "c1", "slug": "proj-designer", "pem": "fake-pem",
    })
    monkeypatch.setattr(team_mod, "_confirm_installation", lambda slug, path: None)

    team_mod.cmd_identity_init_role("designer")

    from synlynk.identity_roles import load_declared_roles

    assert "designer" in load_declared_roles()
