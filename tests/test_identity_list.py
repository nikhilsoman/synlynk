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
