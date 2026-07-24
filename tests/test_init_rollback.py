import subprocess

import pytest

import synlynk


def _init_git_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)


def _stub_init_inputs(monkeypatch):
    monkeypatch.setattr(synlynk, "discover_agents", lambda: [])
    monkeypatch.setattr(
        synlynk,
        "_static_scan",
        lambda path: {
            "project_name": "test",
            "commit_count": 1,
            "languages": ["Python"],
            "recent_topics": [],
            "has_structured_commits": True,
        },
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": "")


def test_init_preserves_existing_claude_content_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "seed", "-q"], cwd=tmp_path, check=True)
    existing_claude = tmp_path / "CLAUDE.md"
    existing_claude.write_text("pre-existing content\n")

    _stub_init_inputs(monkeypatch)
    monkeypatch.setattr(synlynk, "install_pre_commit_hook", lambda repo_root: None)

    synlynk.init(force=False, agents=["claude"], mode="solo")

    text = existing_claude.read_text()
    assert "pre-existing content\n" in text
    assert "<!-- synlynk:start" in text
    assert text.index("pre-existing content\n") < text.index("<!-- synlynk:start")


def test_init_rolls_back_on_mid_operation_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "seed", "-q"], cwd=tmp_path, check=True)
    existing_claude = tmp_path / "CLAUDE.md"
    existing_claude.write_text("pre-existing content\n")

    _stub_init_inputs(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure installing pre-commit hook")

    monkeypatch.setattr(synlynk, "install_pre_commit_hook", boom)

    with pytest.raises(RuntimeError):
        synlynk.init(force=False, agents=["claude"], mode="solo")

    assert existing_claude.read_text() == "pre-existing content\n"
