import os
import sqlite3


def _make_stub_cli(tmp_path, name, version="1.0.0", help_text="--flag1  A flag\n--flag2  Another\n"):
    stub = tmp_path / name
    stub.write_text(
        f"""#!/bin/sh
case "$1" in
  --version) echo "{name} {version}"; exit 0 ;;
  --help)    echo "{help_text}"; exit 0 ;;
  *)         echo "stub output"; exit 0 ;;
esac
"""
    )
    stub.chmod(0o755)
    return stub


def test_probe_fastpath_skips_deep_probe_when_hash_matches(tmp_path, monkeypatch):
    from synlynk import _probe_agent, _compute_capability_hash, AGENT_CAPABILITY_BASELINES, _migrate_db

    _make_stub_cli(tmp_path, "agy", version="1.0.0")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    db = sqlite3.connect(":memory:")
    _migrate_db(db)

    baseline = AGENT_CAPABILITY_BASELINES.get("agy", {})
    h = _compute_capability_hash(baseline.get("headless_contract", {}), baseline.get("dispatch_flags", {}))
    db.execute(
        """
        INSERT INTO harness_records (agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at)
        VALUES ('agy','agy','1.0.0','ok','{}','{}',?,datetime('now'))
        """,
        (h,),
    )
    db.commit()

    result = _probe_agent("agy", db, fast_path_ok=True)
    assert result["skipped"] is True


def test_probe_writes_harness_records_on_new_version(tmp_path, monkeypatch):
    from synlynk import _probe_agent, _migrate_db

    _make_stub_cli(tmp_path, "agy", version="2.0.0")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    db = sqlite3.connect(":memory:")
    _migrate_db(db)

    result = _probe_agent("agy", db, fast_path_ok=True)
    row = db.execute("SELECT installed_version FROM harness_records WHERE agent_name='agy'").fetchone()
    assert row and row[0] == "2.0.0"
    assert result["skipped"] is False


def test_probe_appends_history_on_version_change(tmp_path, monkeypatch):
    from synlynk import _probe_agent, _migrate_db

    _make_stub_cli(tmp_path, "agy", version="2.0.0")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    db = sqlite3.connect(":memory:")
    _migrate_db(db)
    db.execute(
        """
        INSERT INTO harness_records (agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at)
        VALUES ('agy','agy','1.0.0','ok','{}','{}','oldhash',datetime('now'))
        """
    )
    db.commit()

    _probe_agent("agy", db, fast_path_ok=True)
    history = db.execute("SELECT event_type FROM harness_version_history WHERE agent_name='agy'").fetchall()
    assert any(r[0] == "version_change" for r in history)


def test_tc1_detects_pipe_hang_and_records_pty_required(tmp_path, monkeypatch):
    stub = tmp_path / "agy_stub"
    stub.write_text("#!/bin/sh\nsleep 30\n")
    stub.chmod(0o755)
    import shutil

    shutil.copy(str(stub), str(tmp_path / "agy"))
    (tmp_path / "agy").chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    from synlynk import _run_tc1

    result = _run_tc1("agy", timeout=1)
    assert result["requires_pty"] is True
    assert result["passed"] is False


def test_tc2_flags_invalid_flag_as_noncompliant(tmp_path, monkeypatch):
    _make_stub_cli(tmp_path, "grok", help_text="--yes  Approve\n--model  Model\n")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    from synlynk import _run_tc2

    test_flags = {"valid_flags": ["--yes"], "invalid_flags": ["--always-approve"]}
    result = _run_tc2("grok", test_flags)
    assert "--always-approve" in result["failed_flags"]


def test_tc3_marks_unreachable_endpoint(monkeypatch):
    import socket

    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: (_ for _ in ()).throw(OSError("refused")))

    from synlynk import _run_tc3

    result = _run_tc3([("cli-chat-proxy.grok.com", 443)])
    assert result["reachable"] == []
    assert ("cli-chat-proxy.grok.com", 443) in result["unreachable"]
