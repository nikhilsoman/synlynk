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


def test_fence_upsert_replaces_existing_fence(tmp_path):
    from synlynk import _upsert_harness_fence
    md = tmp_path / "GEMINI.md"
    md.write_text("# Human content above\n\n<!-- synlynk:harness v0.1 verified:2026-01-01T00:00:00Z -->\nold content\n<!-- /synlynk:harness -->\n\n# Human content below\n")

    _upsert_harness_fence(str(md), "v0.2", "new fence content line")

    text = md.read_text()
    assert "new fence content line" in text
    assert "old content" not in text
    assert "# Human content above" in text
    assert "# Human content below" in text

def test_fence_upsert_appends_when_missing(tmp_path):
    from synlynk import _upsert_harness_fence
    md = tmp_path / "CLAUDE.md"
    md.write_text("# Human only content\n")

    _upsert_harness_fence(str(md), "v0.1", "fence body here")

    text = md.read_text()
    assert "<!-- synlynk:harness" in text
    assert "fence body here" in text
    assert "# Human only content" in text

def test_fence_upsert_skips_missing_file(tmp_path, capsys):
    from synlynk import _upsert_harness_fence
    _upsert_harness_fence(str(tmp_path / "NONEXISTENT.md"), "v0.1", "body")
    captured = capsys.readouterr()
    assert "fence skipped" in captured.out or "fence skipped" in captured.err

def test_fence_preserves_surrounding_bytes(tmp_path):
    from synlynk import _upsert_harness_fence
    before = "# Top\nLine A\nLine B\n"
    after = "\n# Bottom\nLine C\n"
    md = tmp_path / "GEMINI.md"
    md.write_text(before + "<!-- synlynk:harness v0.1 verified:X -->\nOLD\n<!-- /synlynk:harness -->" + after)

    _upsert_harness_fence(str(md), "v0.2", "NEW")

    text = md.read_text()
    assert text.startswith(before)
    assert text.endswith(after)


def test_preflight_fires_drift_sentinel_on_version_change(tmp_path, monkeypatch):
    import sqlite3
    import time
    import synlynk
    from synlynk import _migrate_db, _preflight_dispatch

    db = sqlite3.connect(":memory:")
    _migrate_db(db)

    old_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200))
    db.execute(
        """
        INSERT INTO harness_records (agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at)
        VALUES ('agy','agy','1.0.0','ok','{}','{}','abc123',?)
        """,
        (old_time,),
    )
    db.commit()

    stub = tmp_path / "agy"
    stub.write_text("#!/bin/sh\necho 'agy 2.0.0'\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    sentinel_events = []
    original_write = synlynk._write_sentinel_alert

    def capture_sentinel(level, pattern, msg, *args):
        sentinel_events.append(pattern)
        original_write(level, pattern, msg, *args)

    monkeypatch.setattr(synlynk, "_write_sentinel_alert", capture_sentinel)

    result = _preflight_dispatch("agy", [], db_conn=db)
    assert result["passed"] is True
    assert "HARNESS_VERSION_DRIFT" in sentinel_events
