"""Integration tests for synlynk new CLI command (v0.28.5)."""
from __future__ import annotations

import os
import pytest
from synlynk.cli import main


def test_cli_synlynk_new_fast_forward(tmp_path, monkeypatch, capsys):
    """Verify synlynk new --fast-forward executes non-interactively and exits 0."""
    target_dir = tmp_path / "my_new_app"

    monkeypatch.setattr(
        "sys.argv",
        [
            "synlynk",
            "new",
            "Build an event streaming processor CLI",
            "--name",
            str(target_dir),
            "--fast-forward",
            "--non-interactive",
        ],
    )

    main()
    captured = capsys.readouterr()
    assert "PROJECT GENESIS COMPLETE" in captured.out
    assert (target_dir / "project-docs" / "brief.md").exists()
    assert (target_dir / "project-docs" / "todo.md").exists()


def test_cli_synlynk_sync_daily(tmp_path, monkeypatch, capsys):
    """Verify synlynk sync --daily outputs daily briefing."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["synlynk", "sync", "--daily"])

    main()
    captured = capsys.readouterr()
    assert "Synlynk Daily Sync" in captured.out
