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


def test_doctor_codex_catalog_matches_authenticated_config(tmp_path, monkeypatch):
    from synlynk.doctor import _hc_codex_model_catalog

    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-5.6-luna"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr("synlynk.doctor.shutil.which", lambda name: "/bin/codex")

    class Result:
        returncode = 0
        stdout = "Logged in using ChatGPT\n"
        stderr = ""

    monkeypatch.setattr("synlynk.doctor.subprocess.run", lambda *args, **kwargs: Result())
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "models.json").write_text(
        '{"tiers":{"fast":{"codex":"gpt-5.6-luna"}},"models":[{"model_id":"gpt-5.6-luna","harness":"codex"}]}'
    )

    result = _hc_codex_model_catalog()
    assert result.status == "ok"
    assert "gpt-5.6-luna" in result.message


def test_doctor_codex_catalog_warns_on_model_drift(tmp_path, monkeypatch):
    from synlynk.doctor import _hc_codex_model_catalog

    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-5.6-luna"\n')
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr("synlynk.doctor.shutil.which", lambda name: "/bin/codex")
    monkeypatch.setattr(
        "synlynk.doctor.subprocess.run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stdout": "Logged in using ChatGPT", "stderr": ""})(),
    )
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "models.json").write_text(
        '{"tiers":{"fast":{"codex":"gpt-5"}},"models":[{"model_id":"gpt-5","harness":"codex"}]}'
    )

    assert _hc_codex_model_catalog().status == "warn"
