"""Tests for 'synlynk edition {show,set}' CLI commands."""

import json
from unittest.mock import patch

from synlynk.editions import cmd_edition_set, cmd_edition_show


def test_edition_show_defaults(tmp_path, capsys):
    """Show displays default 'personal' edition when config is empty."""
    with patch("os.path.exists", return_value=False):
        exit_code = cmd_edition_show()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Synlynk Edition: personal" in captured.out
        assert "Enabled Hosted Capabilities: none" in captured.out


def test_edition_set_valid_tier(tmp_path, capsys):
    """Set updates config.json with target edition and adds default hosted preset."""
    cfg_dir = tmp_path / ".synlynk"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "config.json"
    cfg_path.write_text(json.dumps({"edition": "personal", "hosted": []}))

    with patch("os.path.join", return_value=str(cfg_path)), patch("os.path.exists", return_value=True):
        exit_code = cmd_edition_set("team")
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Synlynk edition set to 'team'" in captured.out
        assert "hosted_relay" in captured.out

        # Verify on-disk content
        saved = json.loads(cfg_path.read_text())
        assert saved["edition"] == "team"
        assert "hosted_relay" in saved["hosted"]


def test_edition_set_preserves_custom_hosted_keys(tmp_path):
    """Setting an edition must never remove pre-existing hosted keys."""
    cfg_dir = tmp_path / ".synlynk"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "config.json"
    cfg_path.write_text(json.dumps({"edition": "team", "hosted": ["custom_broker", "hosted_relay"]}))

    with patch("os.path.join", return_value=str(cfg_path)), patch("os.path.exists", return_value=True):
        exit_code = cmd_edition_set("enterprise")
        assert exit_code == 0
        saved = json.loads(cfg_path.read_text())
        assert saved["edition"] == "enterprise"
        assert "custom_broker" in saved["hosted"]
        assert "sso" in saved["hosted"]


def test_edition_set_invalid_tier(capsys):
    """Setting an invalid tier returns exit code 2 and error output."""
    exit_code = cmd_edition_set("invalid_tier")
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "invalid edition tier 'invalid_tier'" in captured.err
