import os
import subprocess
import sys
import tempfile
from unittest.mock import patch
from synlynk import init


def test_init_dry_run_leaves_zero_traces(tmp_path, monkeypatch, capsys):
    """synlynk init --dry-run must leave zero disk artifacts in clean directory (Fixes #5299)."""
    monkeypatch.chdir(tmp_path)
    init(dry_run=True, non_interactive=True)
    captured = capsys.readouterr().out
    assert "DRY RUN — no files will be written" in captured
    assert not os.path.exists(".synlynk")
    assert not os.path.exists(tmp_path / ".synlynk")
    # Assert directory is completely empty
    assert len(os.listdir(tmp_path)) == 0


def test_init_clean_repo_no_stale_warning(tmp_path, monkeypatch, capsys):
    """synlynk init on a fresh directory must not warn about already existing .synlynk."""
    monkeypatch.chdir(tmp_path)
    # Even if an empty .synlynk/ folder happened to exist before config is written
    os.makedirs(".synlynk", exist_ok=True)
    init(dry_run=False, non_interactive=True)
    captured = capsys.readouterr().out
    assert "⚠ .synlynk/ already exists" not in captured
    assert os.path.exists(".synlynk/config.json")
