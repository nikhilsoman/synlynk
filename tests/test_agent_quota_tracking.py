"""#291: agent_quotas populated from telemetry + synlynk quota CLI."""

import json
import os
import time

import pytest


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """Minimal initialized project cwd for quota helpers."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({
        "schema_version": 1,
        "budget": {
            "limit_usd": 10.0,
            "limit_requests": 100,
            "quota_limits": {
                "5h": {"tokens": 200_000, "requests": 50},
                "hourly": {"tokens": 100_000, "requests": 20},
                "daily": {"tokens": 500_000, "requests": 100},
                "weekly": {"tokens": 2_000_000, "requests": 500},
                "monthly": {"tokens": 5_000_000, "requests": 2000},
            },
        },
    }))
    return tmp_path


def _write_telemetry(project_dir, events):
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(events))


def test_refresh_populates_agent_quotas_from_telemetry(project_dir):
    import synlynk as sl

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "claude --print do stuff",
            "_ts": now - 60,
            "in_tokens": 10_000,
            "out_tokens": 2_000,
        },
        {
            "type": "exec",
            "command": "claude --print more",
            "_ts": now - 120,
            "in_tokens": 5_000,
            "out_tokens": 1_000,
        },
        {
            "type": "exec",
            "agent": "codex",
            "_ts": now - 30,
            "in_tokens": 3_000,
            "out_tokens": 500,
        },
        # Outside all short windows but inside monthly/weekly — still counts for those
        {
            "type": "exec",
            "command": "agy -p task",
            "_ts": now - (3 * 86400),
            "in_tokens": 1_000,
            "out_tokens": 0,
        },
    ])

    written = sl.refresh_agent_quotas_from_telemetry(now=now)
    assert written > 0

    conn = sl._get_db()
    try:
        rows = conn.execute(
            "SELECT agent, quota_type, unit, limit_tokens, used_tokens, reset_at "
            "FROM agent_quotas ORDER BY agent, quota_type, unit"
        ).fetchall()
    finally:
        conn.close()

    assert rows, "agent_quotas must be non-empty after telemetry refresh"
    by_key = {(r[0], r[1], r[2]): r for r in rows}

    # claude: 12k + 6k = 18k tokens, 2 requests inside 5h/hourly/daily/...
    claude_5h_tok = by_key[("claude", "5h", "tokens")]
    assert claude_5h_tok[4] == 18_000
    assert claude_5h_tok[3] == 200_000  # limit from config
    assert claude_5h_tok[5]  # reset_at set

    claude_5h_req = by_key[("claude", "5h", "requests")]
    assert claude_5h_req[4] == 2

    codex_hourly = by_key[("codex", "hourly", "tokens")]
    assert codex_hourly[4] == 3_500

    # agy event is 3 days old → not in 5h, is in weekly/monthly
    assert ("agy", "5h", "tokens") not in by_key or by_key[("agy", "5h", "tokens")][4] == 0
    agy_weekly = by_key[("agy", "weekly", "tokens")]
    assert agy_weekly[4] == 1_000


def test_quota_headroom_helper_used_by_refresh(project_dir):
    import synlynk as sl

    assert sl._quota_headroom(100_000, 18_000) == 82_000
    assert sl._quota_headroom(50, 50) == 0
    assert sl._quota_headroom(10, 99) == 0


def test_stage2_gate_sees_nonzero_usage_after_refresh(project_dir, monkeypatch):
    """Stage-2 quota gate must not stay stuck in degraded empty-table mode
    once telemetry has been rolled into agent_quotas (#291 acceptance)."""
    import synlynk as sl

    monkeypatch.setattr(sl, "_project_request_quota_from_config", lambda: None)

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "claude --print",
            "_ts": now - 10,
            "in_tokens": 40_000,
            "out_tokens": 10_000,
        },
    ])

    # Before refresh: empty table → degraded/unknown
    conn = sl._get_db()
    try:
        before = sl._quota_status_for_agent(conn, "claude", estimated_tokens=1_000)
        assert before["status"] == "unknown"
        assert before["degraded"] is True
        assert before["reason"] == "no_quota_rows"
    finally:
        conn.close()

    written = sl.refresh_agent_quotas_from_telemetry(now=now)
    assert written > 0

    conn = sl._get_db()
    try:
        after = sl._quota_status_for_agent(conn, "claude", estimated_tokens=1_000)
        assert after["degraded"] is False
        assert after["status"] == "ok"
        assert after["unit"] == "tokens"
        assert after["headroom"] is not None
        assert after["headroom"] > 0
        # used was 50k on a 100k hourly default → headroom finite and < limit
        assert after["headroom"] < 200_000

        # Exhausting estimate: 200k needed, headroom should block if lower
        exhausted = sl._quota_status_for_agent(
            conn, "claude", estimated_tokens=10_000_000
        )
        assert exhausted["status"] == "exhausted"
        assert exhausted["degraded"] is False
    finally:
        conn.close()


def test_best_agent_refreshes_quotas_before_gate(project_dir, monkeypatch):
    """_best_agent_for_story must call telemetry refresh so gate sees real usage."""
    import synlynk as sl

    monkeypatch.setattr(sl, "_project_request_quota_from_config", lambda: None)

    now = time.time()
    # Exhaust claude via telemetry; leave agy with capacity
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "claude --print",
            "_ts": now - 5,
            # blow past hourly 100k default for tokens
            "in_tokens": 99_000,
            "out_tokens": 5_000,
        },
    ])

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories "
        "(story_id, title, engg_domain, org_domain, industry, phase, estimated_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("story-q291", "Quota wire", "backend", "platform", "ott", "build", 10_000),
    )
    for agent, quality, model in (
        ("claude", 9.0, "claude-sonnet-4-6"),
        ("agy", 6.0, "gemini-2.5-pro"),
    ):
        conn.execute(
            "INSERT INTO capability_ratings "
            "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
            " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("story-q291", agent, model, "backend", "platform", "ott", "build",
             "auto", quality, quality),
        )
    # Seed agy with known headroom so it is not degraded-only
    sl._upsert_agent_quota(
        "agy", "hourly", limit_tokens=200_000, used_tokens=0,
        model="gemini-2.5-pro", unit="tokens", conn=conn,
    )
    conn.commit()
    conn.close()

    # Routing should drop exhausted claude and pick agy (after refresh)
    chosen = sl._best_agent_for_story("story-q291")
    assert chosen == "agy"

    # Confirm claude rows were written with non-zero used
    conn = sl._get_db()
    try:
        used = conn.execute(
            "SELECT used_tokens FROM agent_quotas "
            "WHERE agent='claude' AND unit='tokens' AND quota_type='hourly'"
        ).fetchone()
    finally:
        conn.close()
    assert used is not None
    assert used[0] == 104_000


def test_cmd_quota_prints_headroom(project_dir, capsys):
    import synlynk as sl

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "codex exec -",
            "_ts": now - 1,
            "in_tokens": 1_000,
            "out_tokens": 200,
        },
    ])

    sl.cmd_quota()
    out = capsys.readouterr().out
    assert "codex" in out
    assert "headroom" in out.lower() or "Headroom" in out or "status=" in out
    assert "telemetry" in out.lower()


def test_cmd_quota_json(project_dir, capsys):
    import synlynk as sl

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "agent": "grok",
            "_ts": now - 1,
            "in_tokens": 500,
            "out_tokens": 100,
        },
    ])

    sl.cmd_quota(json_output=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["source"] == "telemetry_proxy"
    agents = {a["agent"]: a for a in payload["agents"]}
    assert "grok" in agents
    assert agents["grok"]["windows"]
    assert any(w["used"] == 600 for w in agents["grok"]["windows"] if w["unit"] == "tokens")


def test_agent_from_command_path_and_gemini_alias(project_dir):
    from synlynk.quota import _agent_from_telemetry_event, _aggregate_usage_from_telemetry

    assert _agent_from_telemetry_event({"command": "/usr/local/bin/claude --print"}) == "claude"
    assert _agent_from_telemetry_event({"agent": "gemini"}) == "agy"
    assert _agent_from_telemetry_event({"command": "gemini -p x"}) == "agy"
    assert _agent_from_telemetry_event({"command": "echo hi"}) is None

    now = time.time()
    usage = _aggregate_usage_from_telemetry(
        [{"type": "exec", "command": "gemini -p", "_ts": now, "in_tokens": 10, "out_tokens": 0}],
        now=now,
    )
    assert "agy" in usage
    assert usage["agy"]["hourly"]["tokens"] == 10


def test_empty_telemetry_writes_nothing(project_dir):
    import synlynk as sl

    _write_telemetry(project_dir, [])
    assert sl.refresh_agent_quotas_from_telemetry() == 0
    conn = sl._get_db()
    try:
        n = conn.execute("SELECT COUNT(*) FROM agent_quotas").fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_fix_github_issue_378_nikhilsomansynk_terminal_summary_survives_unknown_overwrite(project_dir, monkeypatch):
    import synlynk as sl

    monkeypatch.setattr(sl, "load_config", lambda: {"fenced_commands": []})

    terminal = sl._write_job_summary(
        "job-race",
        "codex",
        "story-378",
        0,
        4.0,
        120,
        30,
        0.02,
        ["src/terminal.py"],
        status_label="OK (exit 0)",
    )

    overwritten = sl._write_job_summary(
        "job-race",
        "codex",
        "story-378",
        None,
        5.0,
        0,
        0,
        0.00,
        [],
        status_label="UNKNOWN (exit unknown)",
    )

    summary_path = project_dir / ".synlynk" / "logs" / "job-race.summary"
    assert summary_path.read_text() == terminal
    assert overwritten == terminal
