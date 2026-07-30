"""#291: agent_quotas populated from telemetry + synlynk quota CLI."""

import json
import os
import sqlite3
import time
from pathlib import Path
import importlib.util
import subprocess

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


def _write_repair_config(tmp_path, config):
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps(config))


def test_repair_sops_only_injects_synlynks_own_h_repo_specific_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_repair_config(
        tmp_path,
        {
            "roles": {
                "agy": ["pm", "review"],
                "codex": ["implement", "test", "refactor"],
            },
            "workgroup_agents": ["agy", "codex"],
            "branch_conventions": {
                "agy": "feat/agy/<description>",
                "codex": "feat/codex/<description>",
            },
        },
    )
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / "GEMINI.md").write_text("# Gemini\n")
    (tmp_path / "AGENTS.md").write_text("# Codex\n")

    import synlynk as sl

    sl._repair_sops_only(dry_run=False)

    gemini = (tmp_path / "GEMINI.md").read_text()
    agents = (tmp_path / "AGENTS.md").read_text()

    assert "escalate to Agy." in gemini
    assert "`feat/agy/<description>`" in gemini
    assert "| pm / review | Agy | pm, review |" in gemini
    assert "| implement / test / refactor | Codex | implement, test, refactor |" in gemini

    assert "escalate to Agy." in agents
    assert "`feat/codex/<description>`" in agents
    assert "| pm / review | Agy | pm, review |" in agents


def test_repair_sops_only_injects_synlynks_own_h_generic_branch_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_repair_config(
        tmp_path,
        {
            "roles": {"claude": ["pm", "review"]},
            "workgroup_agents": ["claude"],
        },
    )
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Claude\n")

    import synlynk as sl

    sl._repair_sops_only(dry_run=False)

    content = (tmp_path / "CLAUDE.md").read_text()
    assert "Use the repo's documented task-scoped branch pattern" in content
    assert "feat/<agent>/<description>" not in content
    assert "escalate to Claude." in content


def test_repair_sops_only_injects_synlynks_own_h_default_config_keeps_current_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_repair_config(
        tmp_path,
        {
            "roles": {
                "claude": ["pm", "review", "deploy"],
                "agy": ["implement", "test", "css", "templates", "content"],
                "codex": ["implement", "test", "refactor"],
                "grok": ["implement", "test", "canvas", "js", "infra"],
            },
            "workgroup_agents": ["claude", "agy", "codex", "grok"],
            "branch_convention": "feat/<description>",
        },
    )
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Claude\n")

    import synlynk as sl

    sl._repair_sops_only(dry_run=False)

    content = (tmp_path / "CLAUDE.md").read_text()
    assert "escalate to Claude." in content
    assert "`feat/<description>`" in content
    assert "| pm / review / deploy | Claude | pm, review, deploy |" in content
    assert "| implement / test / css / templates / content | Agy | implement, test, css, templates, content |" in content


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


def test_phase_7_of_docssuperpowersplans20260730h_panel_timeout_override_respected(monkeypatch):
    import synlynk.team as team

    calls = []

    class Result:
        stdout = "panel output\n"

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Result()

    monkeypatch.setattr(team.subprocess, "run", fake_run)

    codex_output = team._run_agent_sync("codex", "review prompt")
    claude_output = team._run_agent_sync("claude", "review prompt")

    assert codex_output == "panel output"
    assert claude_output == "panel output"
    assert calls[0][1]["timeout"] == 300
    assert calls[1][1]["timeout"] == 120


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


@pytest.mark.parametrize(
    "reconcile_order",
    [
        ("jobs", "daemon"),
        ("daemon", "jobs"),
    ],
)
def test_fix_synlynk_jobs_all_permanently_shows_unknown_shared_exit_marker_race(
    project_dir, monkeypatch, reconcile_order
):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    log_path = project_dir / ".synlynk" / "logs" / "job-shared.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Input tokens: 12\nOutput tokens: 34\n")
    exit_path = str(log_path) + ".exit"
    with open(exit_path, "w") as f:
        f.write("0")

    sl._save_jobs([
        {
            "id": "job-shared",
            "agent": "claude",
            "story_id": "story-shared",
            "task": "shared exit marker test",
            "pid": 99999999,
            "log_file": str(log_path),
            "worktree_path": "",
            "worktree_branch": "",
            "started_at": "2026-07-25T10:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, pid, enqueued_at, started_at, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "job-shared",
            "claude",
            "shared exit marker test",
            "story-shared",
            "running",
            5,
            "[]",
            99999999,
            "2026-07-25T10:00:00",
            "2026-07-25T10:00:00",
            str(log_path),
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        jobs_mod.os,
        "kill",
        lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()),
    )
    monkeypatch.setattr(
        jobs_mod.os,
        "waitpid",
        lambda *a, **kw: (_ for _ in ()).throw(ChildProcessError()),
    )

    for reconcile in reconcile_order:
        if reconcile == "jobs":
            jobs_mod._reconcile_jobs()
        else:
            jobs_mod._reconcile_daemon_jobs()

    jobs = sl._load_jobs()
    job_row = next(job for job in jobs if job["id"] == "job-shared")
    assert job_row["status"] == "completed"
    assert job_row["exit_code"] == 0

    conn = sl._get_db()
    try:
        daemon_row = conn.execute(
            "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?",
            ("job-shared",),
        ).fetchone()
    finally:
        conn.close()
    assert daemon_row == ("done", 0)
    assert os.path.exists(exit_path)


def test_wire_health_checks_into_real_synlynk_doc(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.doctor as doctor_mod

    monkeypatch.setattr(
        doctor_mod,
        "HEALTH_CHECKS",
        [lambda: sl.HealthCheck("identity_roles", "ok", "all declared roles provisioned")],
    )
    monkeypatch.setattr(
        doctor_mod,
        "AGENT_CAPABILITY_BASELINES",
        {
            "agy": {
                "cli": "agy",
                "dispatch_flags": {},
                "network_deps": {"required_endpoints": []},
                "headless_contract": {},
            }
        },
    )
    monkeypatch.setattr(sl, "_run_tc1", lambda agent: {"passed": True})
    monkeypatch.setattr(sl, "_run_tc2", lambda agent, flags_spec: {"passed": True, "failed_flags": []})
    monkeypatch.setattr(sl, "_run_tc3", lambda endpoints: {"passed": True, "unreachable": []})
    monkeypatch.setattr(sl, "_run_tc4", lambda agent, db_conn: {"passed": True, "failed_verbs": []})
    monkeypatch.setattr(sl, "_run_tc5", lambda files: {"passed": True, "missing": {}})
    monkeypatch.setattr(sl, "load_config", lambda: {"roles": {}})

    exit_code = sl.cmd_doctor()
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "synlynk doctor" in out
    assert "identity_roles" in out
    assert "doctor [agy]" in out


def test_fix_stale_capability_scores_view_missing_discipline_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import synlynk as sl

    db_path = tmp_path / ".synlynk" / "state.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(sl._DB_SCHEMA)
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('story-stale', 'Stale view')")
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, discipline, org_domain, role, stage, "
        " industry, phase, signal_source, quality) "
        "VALUES ('story-stale', 'claude', 'claude-sonnet-4-6', 'backend', 'backend', "
        "'platform', 'dev', 'open', 'ott', 'build', 'auto', 9.0)"
    )
    conn.execute("DROP VIEW IF EXISTS capability_scores")
    conn.executescript("""
        CREATE VIEW capability_scores AS
        SELECT
            agent,
            model_version,
            engg_domain,
            org_domain,
            industry,
            phase,
            SUM(quality * pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER))) /
              SUM(pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER)))
              AS weighted_score,
            COUNT(*) AS sample_count,
            MAX(ts) AS last_seen
        FROM capability_ratings
        WHERE split_model = 0
        GROUP BY agent, model_version, engg_domain, org_domain, industry, phase;
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr(sl, "DB_PATH", str(db_path))

    conn = sl._get_db()
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_scores)")}
        assert {"discipline", "role", "stage"} <= cols

        discipline = conn.execute(
            "SELECT discipline FROM capability_scores LIMIT 1"
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM capability_scores WHERE discipline=?",
            (discipline,),
        ).fetchone()[0]
        assert count >= 1
    finally:
        conn.close()


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


def test_chore_synlynk_jobs_all_shows_stale_faile_terminal_summary_survives_daemon_reconcile(
    project_dir, monkeypatch
):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(sl, "load_config", lambda: {"fenced_commands": []})

    summary_path = project_dir / ".synlynk" / "logs" / "job-race.summary"
    terminal = sl._write_job_summary(
        "job-race",
        "codex",
        "story-202",
        0,
        4.0,
        120,
        30,
        0.02,
        ["src/terminal.py"],
        status_label="OK (exit 0)",
    )

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, pid, enqueued_at, started_at, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "job-race",
            "codex",
            "task",
            "story-202",
            "running",
            5,
            "[]",
            99999999,
            "2026-07-25T00:00:00",
            "2026-07-25T00:00:01",
            str(project_dir / ".synlynk" / "logs" / "job-race.log"),
        ),
    )
    conn.commit()
    conn.close()

    def pkg_side_effect(name, default=None):
        if name == "_get_db":
            return sl._get_db
        if name == "extract_tokens":
            return lambda log_text, agent="": (0, 0)
        if name == "extract_model_version":
            return lambda log_text, agent="": "unknown"
        if name == "update_costs":
            return lambda *args, **kwargs: None
        return getattr(sl, name, default)

    monkeypatch.setattr(jobs_mod, "_pkg", pkg_side_effect)
    monkeypatch.setattr(jobs_mod.os, "waitpid", lambda pid, opts: (_ for _ in ()).throw(ChildProcessError()))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    jobs_mod._reconcile_daemon_jobs()

    assert summary_path.read_text() == terminal
    assert "FAILED (exit -1)" not in summary_path.read_text()
    assert "files:    0 touched" not in summary_path.read_text()


def _load_backfill_script():
    script_path = Path(__file__).resolve().parents[1] / "bin" / "backfill_api_equivalent_usd.py"
    spec = importlib.util.spec_from_file_location("backfill_api_equivalent_usd", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _seed_cost_entries_db(db_path):
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            api_equivalent_usd REAL,
            payment_mode TEXT,
            actual_usd REAL,
            cost_source TEXT NOT NULL,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-01", "claude", "claude-sonnet-4-6", 1000, 500, 250, None, "subscription", None, "estimated_manual"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-02", "codex", "gpt-5-codex", 2000, 1000, 0, None, "subscription", None, "estimated_manual"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-03", "claude", "claude-sonnet-4-6", 3000, 1500, 0, None, "subscription", None, "legacy_unknown"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-04", "claude", "claude-sonnet-4-6", 4000, 2000, 0, 0.99, "subscription", 1.23, "estimated_manual"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-05", "claude", "claude-sonnet-4-6", 5000, None, 0, None, "subscription", None, "estimated_manual"),
    )
    conn.commit()
    conn.close()


def test_fix_github_issue_382_nikhilsomansynlynk_backfill_updates_only_eligible_rows(project_dir, monkeypatch, capsys):
    import sqlite3
    import synlynk as sl

    db_path = project_dir / "state.db"
    _seed_cost_entries_db(db_path)
    monkeypatch.setattr(sl, "_resolve_db_path", lambda: str(db_path))

    backfill_mod = _load_backfill_script()
    assert backfill_mod.main([]) == 0

    out = capsys.readouterr().out
    assert "Updated 2 rows" in out

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT session_date, agent, model, api_equivalent_usd, payment_mode, actual_usd, cost_source "
            "FROM cost_entries ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    assert rows[0][3] == pytest.approx(
        sl._model_rate_for_version("claude-sonnet-4-6", agent="claude")["input"] +
        (0.5 * sl._model_rate_for_version("claude-sonnet-4-6", agent="claude")["output"]) +
        (0.25 * sl._model_rate_for_version("claude-sonnet-4-6", agent="claude")["cache_read"])
    )
    assert rows[1][3] == pytest.approx(
        (2.0 * sl._model_rate_for_version("gpt-5-codex", agent="codex")["input"]) +
        (1.0 * sl._model_rate_for_version("gpt-5-codex", agent="codex")["output"])
    )
    assert rows[2][3] is None
    assert rows[3][3] == pytest.approx(0.99)
    assert rows[4][3] is None
    assert rows[0][4] == "subscription"
    assert rows[0][5] is None
    assert rows[1][4] == "subscription"
    assert rows[1][5] is None
    assert rows[2][4] == "subscription"
    assert rows[2][5] is None


def test_synlynk_selftest_live_clobbers_real_repo(monkeypatch, tmp_path):
    from synlynk import selftest as selftest_mod
    import synlynk.scheduler as scheduler_mod

    real_repo = tmp_path / "real-repo"
    (real_repo / "project-docs").mkdir(parents=True)
    (real_repo / ".synlynk").mkdir(parents=True)
    (real_repo / "project-docs" / "todo.md").write_text(
        "# Project Todo List\n"
        "- [ ] keep me <!-- id: story-keep -->\n"
    )
    (real_repo / "GEMINI.md").write_text(
        "<!-- synlynk:start version=\"1\" tool=\"agy\" -->\n"
        "## keep me\n"
        "<!-- synlynk:end -->\n"
    )
    (real_repo / ".synlynk" / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "budget": {"limit_usd": 10.0, "limit_requests": 100},
                "project_docs_dir": "project-docs",
                "dispatch_mode": "daily-grind",
            }
        )
    )
    subprocess.run(["git", "init", "-q"], cwd=real_repo, check=True)
    subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=real_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Codex"], cwd=real_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=real_repo, check=True)
    subprocess.run(["git", "commit", "-m", "baseline", "-q"], cwd=real_repo, check=True)

    todo_before = (real_repo / "project-docs" / "todo.md").read_text()
    gemini_before = (real_repo / "GEMINI.md").read_text()

    monkeypatch.chdir(real_repo)
    monkeypatch.setattr(
        selftest_mod,
        "dispatch_agent",
        lambda *args, **kwargs: {"id": "job-selftest", "pid": 1, "fence": None},
    )
    monkeypatch.setattr(selftest_mod, "exec_command", lambda argv: 0)
    monkeypatch.setattr(scheduler_mod, "cmd_schedule", lambda execute=True, max_stories=1: None)

    results = selftest_mod.run_selftest(live=True)

    assert all(result.status != "fail" for result in results)
    assert subprocess.run(
        ["git", "status", "--short"],
        cwd=real_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == ""
    assert (real_repo / "project-docs" / "todo.md").read_text() == todo_before
    assert (real_repo / "GEMINI.md").read_text() == gemini_before


def test_live_selftest_scenario_coverage_gap_init(tmp_path):
    from synlynk import selftest as selftest_mod

    ctx = selftest_mod.ScenarioContext(repo_path=str(tmp_path), live=True)
    entry = {"command": "init"}

    result = selftest_mod.SELFTEST_SCENARIOS["init"](entry, ctx)

    assert result.status == "pass"
    assert "without clobbering existing files" in result.detail
