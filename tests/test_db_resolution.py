"""Canonical state-ledger resolution coverage (#2413)."""

from __future__ import annotations


def test_isolated_test_flag_permits_explicit_test_ledger(tmp_path, monkeypatch):
    import synlynk

    isolated = tmp_path / "isolated" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "canonical" / "state.db"))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(isolated))
    monkeypatch.setenv("SYNLYNK_TEST_ISOLATED_DB", "1")

    conn = synlynk._get_db()
    try:
        assert isolated.exists()
    finally:
        conn.close()
