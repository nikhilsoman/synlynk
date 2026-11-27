# tests/test_cli_maintainer_wake.py
import subprocess
import sys


def test_cli_maintainer_wake_subcommand_parses(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    result = subprocess.run(
        [sys.executable, str(__import__("pathlib").Path(__file__).parent.parent / "bin" / "synlynk.py"),
         "maintainer", "wake", "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    assert "wake" in result.stdout.lower()


def test_maintainer_wake_taxonomy_entry_exists():
    from synlynk.taxonomy import COMMAND_TAXONOMY

    commands = [entry["command"] for entry in COMMAND_TAXONOMY]
    assert "maintainer wake" in commands
