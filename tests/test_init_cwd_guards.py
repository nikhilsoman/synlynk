import subprocess

import pytest

import synlynk
from synlynk import cli
from synlynk import wizard


def _init_git_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def _make_synlynk_checkout(path):
    _init_git_repo(path)
    (path / "pyproject.toml").write_text('[project]\nname = "synlynk"\n')
    (path / "VERSION").write_text("0.0.0\n")


def test_init_refuses_non_git_directory_before_creating_workspace_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="valid Git repository root"):
        synlynk.init(non_interactive=True)

    assert not (tmp_path / ".synlynk").exists()


def test_wizard_init_refuses_synlynk_source_checkout_before_writing(tmp_path, monkeypatch):
    _make_synlynk_checkout(tmp_path)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="Synlynk tool checkout"):
        wizard.cmd_wizard_init(non_interactive=True)

    assert not (tmp_path / ".synlynk").exists()


def test_cli_init_rejects_non_git_directory_before_docs_dir_write(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        synlynk,
        "init",
        lambda **_kwargs: pytest.fail("cli must reject the directory before calling init"),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["init", "--yes", "--docs-dir", "custom-docs"])

    assert exc_info.value.code == 2
    assert "valid Git repository root" in capsys.readouterr().err
    assert not (tmp_path / ".synlynk").exists()
