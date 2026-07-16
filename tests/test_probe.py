import os
import sqlite3


class _DummySocket:
    def close(self):
        pass


def _make_stub_agent(tmp_path, name, version, version_output=None):
    script = tmp_path / name
    version_line = version_output or f"{name} {version}"
    script.write_text(
        f"""#!/bin/sh
case "$1" in
  --version) echo "{version_line}"; exit 0 ;;
  --help)    echo "  --flag  Example flag"; exit 0 ;;
  *)         echo "stub output"; exit 0 ;;
esac
"""
    )
    script.chmod(0o755)
    return script


def _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0", capability_hash="oldhash"):
    import synlynk

    conn = sqlite3.connect(str(db_path))
    synlynk._migrate_db(conn)
    conn.execute(
        """
        INSERT INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at
        ) VALUES (?, ?, ?, 'ok', '{}', '{}', ?, datetime('now'))
        """,
        (agent_name, agent_name, installed_version, capability_hash),
    )
    conn.commit()
    conn.close()


def _read_installed_version(db_path, agent_name):
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT installed_version FROM harness_records WHERE agent_name=?",
            (agent_name,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def test_probe_clears_drift_alert_for_matching_agent(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-15 10:00] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [CRITICAL] [2026-07-15 10:01] OTHER_ALERT: leave this alone\n"
    )

    cmd_probe(agent="agy")

    content = sentinel_path.read_text()
    assert "HARNESS_VERSION_DRIFT" not in content
    assert "OTHER_ALERT" in content
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_leaves_other_agent_drift_alert_untouched(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-15 10:00] HARNESS_VERSION_DRIFT: Agent 'codex' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-15 10:01] OTHER_AGENT_ALERT: keep this too\n"
    )
    before = sentinel_path.read_text()

    cmd_probe(agent="agy")

    assert sentinel_path.read_text() == before
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_no_drift_alerts_is_noop_for_sentinel_state(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [INFO] [2026-07-15 10:00] VERIFY_SKIP: unrelated sentinel state\n"
    )
    before = sentinel_path.read_text()

    cmd_probe(agent="agy")

    assert sentinel_path.read_text() == before
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_clears_all_drift_alerts_for_same_agent(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-15 10:00] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-15 10:01] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 2.0.0 -> 3.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-15 10:02] HARNESS_VERSION_DRIFT: Agent 'codex' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
    )

    cmd_probe(agent="agy")

    content = sentinel_path.read_text()
    assert content.count("HARNESS_VERSION_DRIFT") == 1
    assert "Agent 'codex' version changed" in content
    assert "Agent 'agy' version changed" not in content
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_extracts_claude_version_from_descriptive_output(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="claude", installed_version="2.0.0")
    _make_stub_agent(tmp_path, "claude", "2.1.208", version_output="2.1.208 (Claude Code)")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    cmd_probe(agent="claude")

    assert _read_installed_version(db_path, "claude") == "2.1.208"
