"""Tests that role provisioning seeds the token cache immediately."""

import json

import synlynk.github_app_auth as github_app_auth
import synlynk.team as team_mod


def test_identity_init_role_resuming_branch_seeds_token_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_path = apps_dir / "dev.pem"
    pem_path.write_text("fake-pem")
    json_path = apps_dir / "dev.json"
    json_path.write_text(
        json.dumps(
            {
                "role": "dev",
                "app_id": "1",
                "client_id": "c1",
                "app_slug": "synlynk-dev",
                "installation_id": None,
                "private_key_path": str(pem_path),
            }
        )
    )

    def fake_confirm_installation(app_slug, json_path_arg):
        data = json.loads(json_path_arg.read_text())
        data["installation_id"] = "999"
        json_path_arg.write_text(json.dumps(data))
        return {"id": "999"}

    refreshed = []
    monkeypatch.setattr(team_mod, "_confirm_installation", fake_confirm_installation)
    monkeypatch.setattr(
        github_app_auth,
        "refresh_installation_token",
        lambda role, app_config: refreshed.append((role, app_config["installation_id"])),
    )
    monkeypatch.setattr("synlynk.identity_roles.load_declared_roles", lambda: [])
    monkeypatch.setattr("synlynk.identity_roles.write_declared_roles", lambda roles: None)

    team_mod.cmd_identity_init_role("dev")

    assert refreshed == [("dev", "999")]
