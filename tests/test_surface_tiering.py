import os
import pytest
import sys
from unittest.mock import patch

import synlynk.cli as cli_mod
from synlynk.taxonomy import CORE_COMMANDS, EXPERIMENTAL_COMMANDS


def test_default_help_shows_only_core_verbs(capsys):
    parser = cli_mod.build_parser()
    help_text = parser.format_help()

    assert "synlynk: The Universal Context Switchboard for AI Devs" in help_text
    assert "Core Commands:" in help_text

    for cmd in CORE_COMMANDS:
        assert f"  {cmd}" in help_text, f"Expected core command '{cmd}' in help output"

    # Non-core operational commands should not be listed in root help
    assert "  sentinel" not in help_text
    assert "  story" not in help_text
    assert "  policy" not in help_text

    # Experimental commands should not be listed in root help
    for exp in ("concierge", "addon", "media", "spike", "board", "gateway", "relay", "mesh"):
        assert f"  {exp}" not in help_text, f"Experimental '{exp}' should not be in default help"

    assert "synlynk help --all" in help_text
    assert "--experimental" in help_text


def test_experimental_warning_without_flag(monkeypatch, capsys):
    monkeypatch.delenv("SYNLYNK_EXPERIMENTAL", raising=False)
    with patch("synlynk.mesh.cmd_multirepo_mesh", return_value=0):
        with pytest.raises(SystemExit):
            cli_mod.main(["mesh"])
    
    err = capsys.readouterr().err
    assert "Notice: 'mesh' is an experimental prototype. Use 'synlynk --experimental mesh ...' to proceed." in err


def test_experimental_no_warning_with_flag(monkeypatch, capsys):
    monkeypatch.delenv("SYNLYNK_EXPERIMENTAL", raising=False)
    with patch("synlynk.mesh.cmd_multirepo_mesh", return_value=0):
        with pytest.raises(SystemExit):
            cli_mod.main(["--experimental", "mesh"])
    
    err = capsys.readouterr().err
    assert "is an experimental prototype" not in err


def test_experimental_no_warning_with_env(monkeypatch, capsys):
    monkeypatch.setenv("SYNLYNK_EXPERIMENTAL", "1")
    with patch("synlynk.mesh.cmd_multirepo_mesh", return_value=0):
        with pytest.raises(SystemExit):
            cli_mod.main(["mesh"])
    
    err = capsys.readouterr().err
    assert "is an experimental prototype" not in err
