import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _utc_iso(hours_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_cmd_status_platform_no_harnesses(project_dir, monkeypatch, capsys):
    import synlynk

    monkeypatch.setattr(synlynk.shutil, "which", lambda name: None)

    with pytest.raises(SystemExit) as exc:
        synlynk.cmd_status(platform=True)

    out = capsys.readouterr().out
    assert "synlynk platform health" in out
    assert "HARNESSES" in out
    assert out.count("not probed") >= 5
    assert "SENTINELS" in out
    assert exc.value.code == 0


def test_cmd_status_platform_with_harness_record(project_dir, monkeypatch, capsys):
    import synlynk

    conn = synlynk._get_db()
    conn.execute(
        """
        INSERT INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, last_probe_at, capability_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "claude",
            "claude-cli",
            "1.2.3",
            "ok",
            "{}",
            "{}",
            _utc_iso(2),
            "hash-123",
        ),
    )
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit):
        synlynk.cmd_status(platform=True)

    out = capsys.readouterr().out
    assert "claude" in out
    assert "1.2.3" in out
    assert "2h ago" in out
    assert "✓ OK" in out


def test_cmd_status_platform_drift_detected(project_dir, capsys):
    import synlynk

    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-03 00:00] HARNESS_VERSION_DRIFT: Agent 'claude' version drift detected\n"
    )

    with pytest.raises(SystemExit):
        synlynk.cmd_status(platform=True)

    out = capsys.readouterr().out
    assert "DRIFT" in out
    assert "HARNESS_VERSION_DRIFT" in out
    assert "claude" in out


def test_cmd_status_platform_budget_pulse(project_dir, capsys):
    import synlynk

    events = [
        {"type": "cost", "timestamp": _utc_iso(1), "cost_usd": 1.25},
        {"type": "cost", "timestamp": _utc_iso(12), "cost_usd": 2.75},
        {"type": "cost", "timestamp": _utc_iso(48), "cost_usd": 3.50},
        {"type": "cost", "timestamp": _utc_iso(200), "cost_usd": 5.00},
    ]
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(events))

    with pytest.raises(SystemExit):
        synlynk.cmd_status(platform=True)

    out = capsys.readouterr().out
    assert "today: $4.00" in out
    assert "week: $7.50" in out
    assert "remaining: $2.50 / $10.00" in out
    assert "75% used" in out


def test_cmd_status_platform_flag_wired(project_dir, monkeypatch):
    import synlynk

    captured = {}

    def fake_status(*, json_output=False, platform=False):
        captured["json_output"] = json_output
        captured["platform"] = platform
        raise SystemExit(0)

    monkeypatch.setattr(synlynk, "_reconcile_jobs", lambda: None)
    monkeypatch.setattr(synlynk, "cmd_status", fake_status)
    monkeypatch.setattr(sys, "argv", ["synlynk", "status", "--platform"])

    with pytest.raises(SystemExit) as exc:
        synlynk.main()

    assert exc.value.code == 0
    assert captured == {"json_output": False, "platform": True}
