import os
import sqlite3
import pytest

from synlynk.cli import main


def test_status_handles_missing_database_gracefully(monkeypatch, capsys):
    """synlynk status must not crash if state.db does not exist and read_only connect raises OperationalError."""
    import synlynk

    def failing_get_db(*args, **kwargs):
        if kwargs.get("read_only"):
            raise sqlite3.OperationalError("unable to open database file")
        return sqlite3.connect(":memory:")

    monkeypatch.setattr(synlynk, "_get_db", failing_get_db)

    # synlynk status should handle this gracefully and print the ecosystem status
    main(["status"])

    out = capsys.readouterr().out
    assert "SYNLYNK ECOSYSTEM STATUS" in out
