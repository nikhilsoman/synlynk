import json
import os

from synlynk.doctor import _hc_identity_file_perms, _hc_identity_roles
from synlynk.product_store import github_apps_dir


def test_doctor_reads_product_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": "synlynk"}))
    apps = github_apps_dir("synlynk")
    apps.mkdir(parents=True)
    (apps / "qa.json").write_text(json.dumps({"installation_id": 1}))
    (apps / "qa.pem").write_text("k")
    os.chmod(apps / "qa.json", 0o600)
    os.chmod(apps / "qa.pem", 0o600)
    monkeypatch.setattr("synlynk.identity_roles.load_declared_roles", lambda: ["qa"])
    assert _hc_identity_file_perms().status == "ok"
    assert _hc_identity_roles().status == "ok"
