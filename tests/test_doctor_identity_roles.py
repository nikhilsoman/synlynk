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
