import io
import json
import os
import sqlite3
import sys
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def db(tmp_path):
    from synlynk.db import _migrate_db

    conn = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(conn)
    yield conn
    conn.close()


def _write_config(tmp_path, dispatch_mode="daily-grind"):
    os.makedirs(tmp_path / ".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"budget": {"limit_usd": 10, "limit_requests": 100}, "dispatch_mode": dispatch_mode})
    )


def test_harness_status_table_exists(db):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='harness_status'"
    ).fetchone()
    assert row is not None


def test_cycle_capability_table_exists(db):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cycle_capability'"
    ).fetchone()
    assert row is not None


def test_harness_status_columns(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(harness_status)")}
    required = {
        "agent_name", "attach_rate_24h", "attach_point_in_time", "adherence_score",
        "completion_rate_24h", "rescue_count_24h", "output_velocity_p50",
        "installed_version", "latest_version", "plan_tier", "plan_type",
        "ctx_window_tokens", "read_budget_tokens", "write_budget_tokens",
        "tool_budget_count", "tc1_status", "tc2_status", "tc3_status", "tc4_status",
        "harness_compat_score", "last_probe_at", "last_telemetry_at",
    }
    assert required <= cols


def test_cycle_capability_columns(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(cycle_capability)")}
    required = {"agent_name", "cycle", "support", "notes", "verb_count", "full_count", "partial_count", "updated_at"}
    assert required <= cols


def test_load_config_defaults_dispatch_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import load_config

    config = load_config()
    assert config["dispatch_mode"] == "daily-grind"


def test_config_set_dispatch_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"budget": {"limit_usd": 10, "limit_requests": 100}}))
    from synlynk import cmd_config_set

    cmd_config_set("dispatch_mode", "eco")
    config = json.loads((tmp_path / ".synlynk" / "config.json").read_text())
    assert config["dispatch_mode"] == "eco"


def test_classify_task_type():
    from synlynk.status import _classify_task_type

    assert _classify_task_type("implement the new dispatch system") == "implement"
    assert _classify_task_type("review this PR and check for bugs") == "review"
    assert _classify_task_type("do some random thing") == "default"


def test_estimate_dispatch_tokens():
    from synlynk.status import estimate_dispatch_tokens

    small = estimate_dispatch_tokens("fix bug", "short context", "claude")
    assert small["input"] < 10_000
    assert small["output"] > 0
    assert small["tools"] >= 0

    big_context = "word " * 400_000
    large = estimate_dispatch_tokens("implement feature", big_context, "claude")
    assert large["input"] > 400_000


def test_get_avg_tool_calls_default():
    from synlynk.status import _get_avg_tool_calls

    assert _get_avg_tool_calls("claude", db_conn=None) == 25.0


def test_compute_cycle_capability_upserts(db):
    import time as _t
    from synlynk.status import _compute_cycle_capability

    now = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
    db.execute(
        "INSERT INTO harness_verb_map (synlynk_verb, verb_category, agent_name, verb, cycle_hint, support, notes, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        ("dispatch.task", "dispatch", "testbot", "dispatch.task", "work", "full", "", now),
    )
    db.commit()
    result = _compute_cycle_capability("testbot", db)
    assert result["execute"]["support"] == "full"
    row = db.execute(
        "SELECT support, verb_count, full_count FROM cycle_capability WHERE agent_name='testbot' AND cycle='execute'"
    ).fetchone()
    assert row[0] == "full"
    assert row[1] >= 1
    assert row[2] >= 1


def test_harness_snapshot_empty(tmp_path):
    from synlynk.hud import HarnessSnapshot

    snap = HarnessSnapshot(str(tmp_path / "missing.db"))
    assert snap.load() == {}


def test_harness_snapshot_loads_rows(db, tmp_path):
    from synlynk.hud import HarnessSnapshot

    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3"),
    )
    db.commit()
    snap = HarnessSnapshot(str(tmp_path / "state.db"))
    data = snap.load()
    assert "claude" in data
    assert data["claude"]["attach_point_in_time"] == 1


def test_format_status_terminal_structure(db):
    from synlynk.status import _format_status_terminal

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": 0.99, "installed_version": "1.2.3", "latest_version": "1.2.3"}]
    cycle_map = {"claude": {c: "full" for c in ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]}}
    output = _format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0)
    assert "HEADLESS EFFICIENCY" in output
    assert "4.2×" in output
    assert "FLEET" in output
    assert "CAPACITY" in output
    assert "CYCLE CAPABILITY" in output
    assert "SENTINELS" in output


def test_format_status_terminal_shows_rates_updated_date():
    from synlynk.status import _format_status_terminal

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": 0.99, "installed_version": "1.2.3", "latest_version": "1.2.3"}]
    cycle_map = {"claude": {c: "full" for c in ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]}}
    output = _format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0, rates_updated_at="2026-07-13")
    assert "RATES   updated 2026-07-13" in output


def test_format_status_terminal_shows_rates_never_updated_warning():
    from synlynk.status import _format_status_terminal

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": 0.99, "installed_version": "1.2.3", "latest_version": "1.2.3"}]
    cycle_map = {"claude": {c: "full" for c in ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]}}
    output = _format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0)
    assert "RATES   never updated ⚠ (hardcoded defaults)" in output


def test_format_status_json_valid():
    from synlynk.status import _format_status_terminal

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": None, "installed_version": "1.2.3", "latest_version": None}]
    output = _format_status_terminal(rows, {}, 1.0, "eco", 2, json_output=True)
    data = json.loads(output)
    assert data["fleet"]["dispatch_mode"] == "eco"
    assert data["sentinels_active"] == 2
    assert "headless_efficiency" in data


def test_format_status_json_includes_rates_updated_at():
    from synlynk.status import _format_status_terminal

    rows = [{"agent_name": "claude", "attach_rate_24h": 1.0, "attach_point_in_time": 1, "completion_rate_24h": None, "installed_version": "1.2.3", "latest_version": None}]
    output = _format_status_terminal(rows, {}, 1.0, "eco", 2, json_output=True, rates_updated_at="2026-07-13")
    data = json.loads(output)
    assert data["rates_updated_at"] == "2026-07-13"


def test_cmd_status_outputs_sections(tmp_path, monkeypatch, db):
    from synlynk.status import cmd_status

    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3"),
    )
    db.commit()
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=False)
    output = buf.getvalue()
    assert "HEADLESS EFFICIENCY" in output
    assert "FLEET" in output
    assert "CYCLE CAPABILITY" in output


def test_cmd_status_json_output(tmp_path, monkeypatch, db):
    from synlynk.status import cmd_status

    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, dispatch_mode="eco")
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3"),
    )
    db.commit()
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=True)
    data = json.loads(buf.getvalue())
    assert data["fleet"]["dispatch_mode"] == "eco"
    assert "cycle_capability" in data


def test_cmd_status_json_output_reads_rates_from_file(tmp_path, monkeypatch, db):
    from synlynk.status import cmd_status

    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    os.makedirs(tmp_path / ".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "model_rates.json").write_text(
        json.dumps({
            "rates_updated_at": "2026-07-13",
            "unit": "usd_per_1k_tokens",
            "models": {},
            "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
            "billing_mode": {"default": "subscription", "local": "actual"},
        })
    )
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3"),
    )
    db.commit()
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=True)
    data = json.loads(buf.getvalue())
    assert data["rates_updated_at"] == "2026-07-13"


def test_cmd_status_json_output_rates_null_when_no_file(tmp_path, monkeypatch, db):
    from synlynk.status import cmd_status

    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_point_in_time, installed_version) VALUES (?,?,?)",
        ("claude", 1, "1.2.3"),
    )
    db.commit()
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_status(db_conn=db, json_output=True)
    data = json.loads(buf.getvalue())
    assert data["rates_updated_at"] is None


def test_preflight_blocks_input_overflow(db, tmp_path, monkeypatch):
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "context.md").write_text("word " * 160_000)
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, read_budget_tokens, write_budget_tokens, tool_budget_count) VALUES (?,?,?,?)",
        ("codex", 110_000, 16_000, 128),
    )
    db.commit()
    result = _preflight_dispatch("codex", [], db_conn=db, _task_hint="implement a feature")
    assert result["passed"] is False
    assert result["sentinel"] == "CAPACITY_EXCEEDED_INPUT"


def test_preflight_blocks_output_overflow(db, tmp_path, monkeypatch):
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, read_budget_tokens, write_budget_tokens, tool_budget_count) VALUES (?,?,?,?)",
        ("codex", 110_000, 7_999, 128),
    )
    db.commit()
    result = _preflight_dispatch("codex", [], db_conn=db, _task_hint="implement a large complex system with many files")
    assert result["passed"] is False
    assert result["sentinel"] == "CAPACITY_EXCEEDED_OUTPUT"


def test_preflight_warns_tool_pressure(db, tmp_path, monkeypatch):
    from synlynk.dispatch import _preflight_dispatch
    from synlynk.status import estimate_dispatch_tokens

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, read_budget_tokens, write_budget_tokens, tool_budget_count) VALUES (?,?,?,?)",
        ("claude", 999_999, 999_999, 1),
    )
    db.commit()
    result = _preflight_dispatch("claude", [], db_conn=db, _task_hint="review this small function")
    assert "passed" in result
    assert estimate_dispatch_tokens("review this small function", "", "claude")["tools"] > 0


def test_probe_writes_status_and_cycle_capability(db, tmp_path, monkeypatch):
    from synlynk import probe as probe_mod

    monkeypatch.chdir(tmp_path)

    def fake_run(cmd, capture_output=False, text=False, timeout=None):
        if cmd[:2] == ["claude", "--version"]:
            return type("R", (), {"stdout": "claude 1.2.3\n", "returncode": 0, "stderr": ""})()
        if cmd[:3] == ["npm", "info", "@anthropic-ai/claude-code"]:
            return type("R", (), {"stdout": "1.2.4\n", "returncode": 0, "stderr": ""})()
        return type("R", (), {"stdout": "", "returncode": 0, "stderr": ""})()

    monkeypatch.setattr(probe_mod.subprocess, "run", fake_run)
    result = probe_mod._probe_agent("claude", db, fast_path_ok=False)
    assert result["status"] in {"ok", "degraded"}
    row = db.execute(
        "SELECT installed_version, ctx_window_tokens, read_budget_tokens FROM harness_status WHERE agent_name='claude'"
    ).fetchone()
    assert row is not None
    assert row[0] == "1.2.3"
    cycle_row = db.execute(
        "SELECT COUNT(*) FROM cycle_capability WHERE agent_name='claude'"
    ).fetchone()
    assert cycle_row[0] == 7


def test_dispatch_agent_records_dispatch_mode(monkeypatch, tmp_path):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"dispatch_mode": "eco", "budget": {"limit_usd": 10, "limit_requests": 100}}))

    class FakeProc:
        pid = 12345

    saved = []
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [])
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: saved.extend(jobs))
    monkeypatch.setattr(synlynk, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(synlynk, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(synlynk, "_get_db", lambda: None)
    monkeypatch.setattr(synlynk, "_preflight_dispatch", lambda **kwargs: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda _agent: {})
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda _agent, _cli: "model")
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda _context: None)
    monkeypatch.setattr(synlynk, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(synlynk, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(synlynk, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())

    job = synlynk.dispatch_agent("codex", "fix bug")
    assert job["dispatch_mode"] == "eco"
    assert saved[0]["dispatch_mode"] == "eco"


def test_exec_command_telemetry_enrichment(monkeypatch, tmp_path):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    captured = []
    monkeypatch.setattr(synlynk, "generate_context", lambda *a, **kw: None)
    monkeypatch.setattr(synlynk, "check_budgets", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "_check_pre_exec_gate", lambda force=False: True)
    monkeypatch.setattr(synlynk, "set_state", lambda *_a, **_kw: None)
    monkeypatch.setattr(synlynk, "_check_costs_freshness", lambda: None)
    monkeypatch.setattr(synlynk, "update_costs", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(synlynk, "extract_tokens", lambda text, agent=None: (0, 0), raising=False)
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    monkeypatch.setattr(synlynk, "check_sentinel_patterns", lambda **kw: None)
    monkeypatch.setattr(synlynk, "_check_instruction_drift", lambda: None)
    monkeypatch.setattr(synlynk, "WatchDaemon", None)
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda event: captured.append(event))

    exit_code = dispatch_mod.exec_command(["python3", "-c", "print('Tool: one');print('tool_use')", "--print"])
    assert exit_code == 0
    event = captured[-1]
    assert event["first_output_at"] is not None
    assert event["tool_call_count"] >= 2
    assert event["output_velocity_bpm"] is not None
    assert event["rescue_agent"] is None


def test_preflight_receives_real_db_conn(monkeypatch, tmp_path, db):
    """dispatch_agent() passes a real db_conn to _preflight_dispatch, not None."""
    import synlynk
    from synlynk import dispatch as dispatch_mod

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"dispatch_mode": "daily-grind", "budget": {"limit_usd": 10, "limit_requests": 100}})
    )

    received = {}

    def fake_preflight(agent_name, dispatch_flags, db_conn=None, _task_hint=""):
        received["db_conn"] = db_conn
        return {"passed": True, "sentinel": None, "reason": None}

    class FakeProc:
        pid = 99999

    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [])
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: None)
    monkeypatch.setattr(synlynk, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(synlynk, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(synlynk, "_get_db", lambda: db)
    monkeypatch.setattr(synlynk, "_preflight_dispatch", fake_preflight)
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda _agent: {})
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda _agent, _cli: "model")
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda _context: None)
    monkeypatch.setattr(synlynk, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(synlynk, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(synlynk, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())

    synlynk.dispatch_agent("codex", "fix a small bug")
    assert received["db_conn"] is db, "dispatch_agent must pass a real db_conn to _preflight_dispatch"
