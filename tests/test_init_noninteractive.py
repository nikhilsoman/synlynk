import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

import synlynk
from synlynk.cli import build_parser


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)


def test_init_yes_completes_with_closed_stdin_without_input(tmp_path, monkeypatch, capsys):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(synlynk, "discover_agents", lambda **_: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *args, **kwargs: False)
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("init must not call input"))
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    synlynk.init(non_interactive=True)

    assert (tmp_path / ".synlynk" / "config.json").exists()
    assert "Auto-selected defaults:" in capsys.readouterr().out


def test_init_yes_subprocess_with_closed_stdin_exits_zero(tmp_path):
    _init_git_repo(tmp_path)
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env["SYNLYNK_STATE_DB_PATH"] = str(tmp_path / "state.db")

    result = subprocess.run(
        [sys.executable, "-m", "synlynk", "init", "--yes"],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert "Auto-selected defaults:" in result.stdout


def test_init_non_interactive_aliases_are_accepted():
    for flag in ("--yes", "--non-interactive"):
        args = build_parser().parse_args(["init", flag])
        assert args.non_interactive is True


def test_init_keeps_prompting_with_a_terminal(tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        synlynk,
        "discover_agents",
        lambda **_: [{"name": "claude", "functional": True, "roles": [], "version": "test", "cli": "claude"}],
    )
    monkeypatch.setattr(synlynk, "_infer_industry", lambda: "ott")
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *args, **kwargs: False)
    monkeypatch.setattr(sys, "stdin", type("TerminalStdin", (), {"isatty": lambda self: True})())
    answers = iter(["", "person@example.com", "ott"])
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    synlynk.init()

    assert prompts == ["  [y/N] ", "  Email or synlynk ID: ", "  Industry vertical [ott]: "]
    config = (tmp_path / ".synlynk" / "config.json").read_text()
    assert "person@example.com" in config
    assert '"industry": "ott"' in config
