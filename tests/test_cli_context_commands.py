import os
import subprocess


def _init_git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)


def test_cli_context_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    os.makedirs("project-docs/devlogs", exist_ok=True)
    monkeypatch.setattr("subprocess.run", subprocess.run)  # real git calls

    import getpass
    monkeypatch.setattr(getpass, "getuser", lambda: "testuser")
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.cli import main
    main(["context", "checkpoint", "--story-id", "story-abc"])

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=story-abc" in content


def test_cli_context_pack_and_inject(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)

    from synlynk.cli import main
    main(["context", "pack", "--story-id", "story-abc", "--task-description", "implement widget"])
    out = capsys.readouterr().out
    assert "implement widget" in out
