import sqlite3

import synlynk


def _db_with_schema(tmp_path):
    db = sqlite3.connect(str(tmp_path / "state.db"))
    synlynk._migrate_db(db)
    return db


def test_init_probe_helper_populates_harness_records(tmp_path, monkeypatch):
    db = _db_with_schema(tmp_path)
    db.close()

    def fake_probe(name, conn, **kwargs):
        conn.execute(
            """INSERT INTO harness_records
               (harness_name, installed_version, compliance_status,
                active_contract, active_flags, last_probe_at, capability_hash)
               VALUES (?, '1.0.0', 'ok', '{}', '{}', 'now', 'test')""",
            (name,),
        )
        return {"status": "ok", "version": "1.0.0"}

    monkeypatch.setattr(
        synlynk, "_get_db", lambda: sqlite3.connect(str(tmp_path / "state.db"))
    )
    monkeypatch.setattr("synlynk.probe._probe_agent", fake_probe)

    result = synlynk.probe_all_configured_harnesses(["codex"])

    assert result["codex"]["status"] == "ok"
    check_db = sqlite3.connect(str(tmp_path / "state.db"))
    assert check_db.execute(
        "SELECT compliance_status FROM harness_records WHERE harness_name='codex'"
    ).fetchone() == ("ok",)
    check_db.close()


def test_dispatch_preflight_inline_probes_missing_harness(tmp_path, monkeypatch):
    from synlynk.dispatch import _preflight_dispatch

    db = _db_with_schema(tmp_path)
    calls = []

    def fake_probe(name, conn, **kwargs):
        calls.append(name)
        conn.execute(
            """INSERT INTO harness_records
               (harness_name, installed_version, compliance_status,
                active_contract, active_flags, last_probe_at, capability_hash)
               VALUES (?, '1.0.0', 'ok', '{}', '{}', 'now', 'test')""",
            (name,),
        )
        return {"status": "ok"}

    monkeypatch.setattr("synlynk.probe._probe_agent", fake_probe)
    result = _preflight_dispatch("codex", ["--model", "test"], db_conn=db)

    assert result["passed"] is True
    assert calls == ["codex"]
    db.close()
