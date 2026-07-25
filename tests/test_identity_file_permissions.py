import os
import stat
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_gitignore_excludes_github_apps_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True, cwd=tmp_path)
    gitignore_src = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
    with open(gitignore_src) as fh:
        gitignore_content = fh.read()
    (tmp_path / ".gitignore").write_text(gitignore_content)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text("{}")
    (apps_dir / "dev.pem").write_text("fake-key")

    result = subprocess.run(
        ["git", "check-ignore", ".synlynk/github_apps/dev.json", ".synlynk/github_apps/dev.pem"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f".synlynk/github_apps/*.json and *.pem must be gitignored — "
        f"git check-ignore exited {result.returncode}: {result.stderr}"
    )


def test_hc_identity_file_perms_warns_on_loose_permissions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_path = apps_dir / "dev.pem"
    pem_path.write_text("fake-key")
    os.chmod(pem_path, 0o644)  # too permissive

    from synlynk.doctor import _hc_identity_file_perms

    result = _hc_identity_file_perms()
    assert result.status == "warn"
    assert "dev.pem" in result.message


def test_hc_identity_file_perms_ok_when_0600(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_path = apps_dir / "dev.pem"
    pem_path.write_text("fake-key")
    os.chmod(pem_path, 0o600)
    json_path = apps_dir / "dev.json"
    json_path.write_text("{}")
    os.chmod(json_path, 0o600)

    from synlynk.doctor import _hc_identity_file_perms

    result = _hc_identity_file_perms()
    assert result.status == "ok"


def test_hc_identity_file_perms_ok_when_no_apps_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    from synlynk.doctor import _hc_identity_file_perms

    result = _hc_identity_file_perms()
    assert result.status == "ok"
