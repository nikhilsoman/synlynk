import json
import os
import sqlite3

import pytest

from synlynk.costs import _estimate_tshirt_tokens
from synlynk.costs import check_budgets
from synlynk.costs import parse_costs_md as costs_parse_costs_md
from synlynk.db import _parse_costs_md as db_parse_costs_md


def test_cost_entries_has_provenance_columns(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    conn.close()
    assert "cost_source" in cols
    assert "estimate_basis" in cols
    assert "job_id" in cols
    assert "api_equivalent_usd" in cols
    assert "actual_usd" in cols
    assert "payment_mode" in cols


def test_cost_source_not_null_no_default(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens) "
            "VALUES ('2026-07-13', 'claude', 'claude-sonnet-4-6', 100, 50)"
        )
    conn.close()


def test_migration_backfills_existing_rows_as_legacy_unknown(project_dir, monkeypatch):
    """A DB created before this migration (no provenance columns, has rows) must
    backfill cost_source='legacy_unknown' on rebuild, never 'actual'.
    """

    import synlynk

    db_path = os.path.join(project_dir, "state.db")
    monkeypatch.setattr(synlynk, "DB_PATH", db_path)

    pre_conn = sqlite3.connect(db_path)
    pre_conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            story_id TEXT,
            epic_id INTEGER,
            phase_id INTEGER,
            total_cost_usd REAL,
            notes TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    pre_conn.execute(
        "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens, total_cost_usd) "
        "VALUES ('2026-01-01', 'claude', 'claude-sonnet-4-6', 1000, 500, 0.01)"
    )
    pre_conn.commit()
    pre_conn.close()

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, estimate_basis FROM cost_entries WHERE session_date='2026-01-01'"
    ).fetchone()
    conn.close()
    assert row == ("legacy_unknown", None)


def test_insert_cost_row_rejects_invalid_cost_source(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    with pytest.raises(ValueError):
        _insert_cost_row(
            session_date="2026-07-13",
            agent="claude",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cost_source="made_up_tier",
            total_cost_usd=0.01,
        )


def test_insert_cost_row_writes_a_row(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    _insert_cost_row(
        session_date="2026-07-13",
        agent="claude",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cost_source="actual",
        total_cost_usd=0.01,
    )
    conn = synlynk._get_db()
    row = conn.execute("SELECT agent, cost_source FROM cost_entries").fetchone()
    conn.close()
    assert row == ("claude", "actual")


def test_insert_cost_row_idempotent_on_job_id(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    _insert_cost_row(
        session_date="2026-07-13",
        agent="claude",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cost_source="estimated_tshirt",
        total_cost_usd=0.01,
        job_id="job-abc123",
    )
    _insert_cost_row(
        session_date="2026-07-13",
        agent="claude",
        model="claude-sonnet-4-6",
        input_tokens=200,
        output_tokens=80,
        cache_read_tokens=0,
        cost_source="actual",
        total_cost_usd=0.02,
        job_id="job-abc123",
    )
    conn = synlynk._get_db()
    rows = conn.execute(
        "SELECT input_tokens, cost_source FROM cost_entries WHERE job_id='job-abc123'"
    ).fetchall()
    conn.close()
    assert rows == [(200, "actual")]


def test_exec_command_passes_agent_to_extract_tokens(project_dir, monkeypatch, tmp_path):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    captured = {}

    def fake_extract_tokens(output_text, agent=None):
        captured["agent"] = agent
        from synlynk.costs import _TokenCounts

        return _TokenCounts(0, 0, 0, "none")

    class _FakeStdout:
        def readline(self):
            return b""

        def close(self):
            return None

    class _FakeProcess:
        returncode = 0
        stdout = _FakeStdout()

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(synlynk, "extract_tokens", fake_extract_tokens, raising=False)
    monkeypatch.setattr(synlynk, "update_costs", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "generate_context", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "check_budgets", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "set_state", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(dispatch_mod, "_check_pre_exec_gate", lambda force=False: True, raising=False)
    monkeypatch.setattr(synlynk, "extract_model_version", lambda *a, **k: "unknown", raising=False)
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **k: _FakeProcess())

    dispatch_mod.exec_command(["echo", "--print", "hi"], force=True)

    assert captured["agent"] == "echo"


def test_jobs_stall_path_passes_agent_to_extract_tokens(monkeypatch):
    from synlynk import jobs as jobs_mod
    import synlynk

    captured = {}

    def fake_extract_tokens(text, agent=None):
        captured["agent"] = agent
        from synlynk.costs import _TokenCounts

        return _TokenCounts(0, 0, 0, "none")

    monkeypatch.setattr(synlynk, "extract_tokens", fake_extract_tokens, raising=False)
    monkeypatch.setattr(synlynk, "update_costs", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "_check_job_stall", lambda *a, **k: True, raising=False)
    monkeypatch.setattr(synlynk, "_write_job_summary", lambda *a, **k: "", raising=False)
    monkeypatch.setattr(synlynk, "_worktree_files_touched", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(
        synlynk,
        "load_config",
        lambda: {"budget": {"limit_usd": 100, "limit_requests": 100}},
        raising=False,
    )

    job = {
        "id": "job-1",
        "agent": "codex",
        "status": "running",
        "started_at": "2026-07-14T00:00:00",
        "ended_at": None,
        "log_file": "",
    }
    monkeypatch.setattr(jobs_mod, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(jobs_mod, "_job_retry_count", lambda j: 0, raising=False)

    jobs_mod._reconcile_jobs()

    assert captured["agent"] == "codex"


def test_support_engineer_investigate_passes_agent_to_extract_tokens():
    import inspect
    from synlynk import support_engineer as se_mod

    source = inspect.getsource(se_mod)
    assert '_pkg("extract_tokens")(log_text, agent=agent)' in source


def test_dispatch_agent_codex_flags_include_json(project_dir, monkeypatch):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    captured_flags = {}

    def fake_popen(cmd, **kwargs):
        captured_flags["shell_cmd"] = cmd[2]

        class FakeProc:
            pid = 12345

        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(synlynk, "_create_job_worktree", lambda job_id, agent: str(project_dir / "worktree"), raising=False)
    monkeypatch.setattr(synlynk, "_job_worktree_details", lambda job_id, agent: ("", "branch"), raising=False)
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [], raising=False)
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: None, raising=False)
    monkeypatch.setattr(synlynk, "_get_db", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda agent: {}, raising=False)
    monkeypatch.setattr(synlynk, "generate_context", lambda **kwargs: "", raising=False)
    monkeypatch.setattr(synlynk, "_format_prompt_for_agent", lambda *a, **k: "prompt", raising=False)
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda agent, cli: "unknown", raising=False)

    dispatch_mod.dispatch_agent("codex", "do a thing", skip_preflight=True, job_id="job-test123")

    assert "--json" in captured_flags["shell_cmd"]


def test_dispatch_agent_claude_flags_include_stream_json_verbose(project_dir, monkeypatch):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    captured_flags = {}

    def fake_popen(cmd, **kwargs):
        captured_flags["shell_cmd"] = cmd[2]

        class FakeProc:
            pid = 12345

        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(synlynk, "_create_job_worktree", lambda job_id, agent: str(project_dir / "worktree"), raising=False)
    monkeypatch.setattr(synlynk, "_job_worktree_details", lambda job_id, agent: ("", "branch"), raising=False)
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [], raising=False)
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: None, raising=False)
    monkeypatch.setattr(synlynk, "_get_db", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda agent: {}, raising=False)
    monkeypatch.setattr(synlynk, "generate_context", lambda **kwargs: "", raising=False)
    monkeypatch.setattr(synlynk, "_format_prompt_for_agent", lambda *a, **k: "prompt", raising=False)
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda agent, cli: "unknown", raising=False)

    dispatch_mod.dispatch_agent("claude", "do a thing", skip_preflight=True, job_id="job-test456")

    assert "--output-format" in captured_flags["shell_cmd"]
    assert "stream-json" in captured_flags["shell_cmd"]
    assert "--verbose" in captured_flags["shell_cmd"]


def test_dispatch_agent_agy_flags_include_output_format_json(project_dir, monkeypatch):
    import synlynk
    from synlynk import dispatch as dispatch_mod

    captured_flags = {}

    def fake_popen(cmd, **kwargs):
        captured_flags["shell_cmd"] = cmd[2]

        class FakeProc:
            pid = 12345

        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(synlynk, "_create_job_worktree", lambda job_id, agent: str(project_dir / "worktree"), raising=False)
    monkeypatch.setattr(synlynk, "_job_worktree_details", lambda job_id, agent: ("", "branch"), raising=False)
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [], raising=False)
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: None, raising=False)
    monkeypatch.setattr(synlynk, "_get_db", lambda: None, raising=False)
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda agent: {}, raising=False)
    monkeypatch.setattr(synlynk, "generate_context", lambda **kwargs: "", raising=False)
    monkeypatch.setattr(synlynk, "_format_prompt_for_agent", lambda *a, **k: "prompt", raising=False)
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda agent, cli: "unknown", raising=False)

    dispatch_mod.dispatch_agent("agy", "do a thing", skip_preflight=True, job_id="job-test789")

    assert "--output-format" in captured_flags["shell_cmd"]
    assert "json" in captured_flags["shell_cmd"]


def test_extract_tokens_basis_regex_pair():
    from synlynk.costs import extract_tokens

    result = extract_tokens("Input tokens: 1,200\nOutput tokens: 340\n")
    assert (result.input_tokens, result.output_tokens) == (1200, 340)
    assert result.basis == "regex_pair"


def test_extract_tokens_basis_total_split():
    from synlynk.costs import extract_tokens

    result = extract_tokens("Total tokens: 1000")
    assert result.basis == "total_split"


def test_extract_tokens_basis_none():
    from synlynk.costs import extract_tokens

    result = extract_tokens("no token info in this output at all")
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert result.basis == "none"


def test_extract_tokens_still_unpacks_as_pair():
    from synlynk.costs import extract_tokens

    in_tokens, out_tokens = extract_tokens("Input tokens: 10\nOutput tokens: 5\n")
    assert (in_tokens, out_tokens) == (10, 5)


def test_extract_codex_structured_single_turn():
    from synlynk.costs import _extract_codex_structured

    output = (
        '{"type":"thread.started","thread_id":"019f609a-abc"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hello"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":39286,"cached_input_tokens":29824,'
        '"output_tokens":167,"reasoning_output_tokens":42}}\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 39286
    assert result.output_tokens == 167 + 42
    assert result.cache_read_tokens == 29824
    assert result.basis == "structured_output"


def test_extract_codex_structured_multi_tool_call_cumulative():
    from synlynk.costs import _extract_codex_structured

    output = (
        '{"type":"thread.started","thread_id":"019f609a-def"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.started","item":{"id":"item_1","type":"command_execution",'
        '"command":"ls","aggregated_output":"","exit_code":null,"status":"in_progress"}}\n'
        '{"type":"item.completed","item":{"id":"item_1","type":"command_execution",'
        '"command":"ls","aggregated_output":"a.txt\\n","exit_code":0,"status":"completed"}}\n'
        '{"type":"item.started","item":{"id":"item_2","type":"command_execution",'
        '"command":"cat a.txt","aggregated_output":"","exit_code":null,"status":"in_progress"}}\n'
        '{"type":"item.completed","item":{"id":"item_2","type":"command_execution",'
        '"command":"cat a.txt","aggregated_output":"hi\\n","exit_code":0,"status":"completed"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":51000,"cached_input_tokens":40000,'
        '"output_tokens":300,"reasoning_output_tokens":10}}\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 51000
    assert result.output_tokens == 310
    assert result.cache_read_tokens == 40000
    assert result.basis == "structured_output"


def test_extract_codex_structured_empty_string_returns_none():
    from synlynk.costs import _extract_codex_structured

    assert _extract_codex_structured("") is None


def test_extract_codex_structured_no_turn_completed_returns_none():
    from synlynk.costs import _extract_codex_structured

    output = '{"type":"thread.started","thread_id":"x"}\n{"type":"turn.started"}\n'
    assert _extract_codex_structured(output) is None


def test_extract_codex_structured_garbage_lines_mixed_with_valid_event():
    from synlynk.costs import _extract_codex_structured

    output = (
        'not json at all\n'
        '\n'
        '   \n'
        '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":50}}\n'
        'trailing garbage after the stream\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.cache_read_tokens == 0


def test_extract_codex_structured_missing_reasoning_tokens_defaults_zero():
    from synlynk.costs import _extract_codex_structured

    output = '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n'
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.output_tokens == 5
    assert result.cache_read_tokens == 0


def test_extract_codex_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_codex_structured

    output = '{"type":"turn.completed","usage":{"input_tokens":"not-a-number","output_tokens":5}}\n'
    assert _extract_codex_structured(output) is None


def test_extract_codex_structured_last_turn_completed_wins():
    from synlynk.costs import _extract_codex_structured

    output = (
        '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":999,"output_tokens":888}}\n'
    )
    result = _extract_codex_structured(output)
    assert result is not None
    assert result.input_tokens == 999
    assert result.output_tokens == 888


def test_extract_claude_structured_single_turn():
    from synlynk.costs import _extract_claude_structured

    output = (
        '{"type":"system","subtype":"init","cwd":"/tmp"}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"hello"}]}}\n'
        '{"type":"result","subtype":"success","is_error":false,"num_turns":1,"result":"hello",'
        '"total_cost_usd":0.1175592,"usage":{"input_tokens":2,"cache_creation_input_tokens":18810,'
        '"cache_read_input_tokens":15444,"output_tokens":4}}\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 2 + 18810
    assert result.output_tokens == 4
    assert result.cache_read_tokens == 15444
    assert result.basis == "structured_output"


def test_extract_claude_structured_multi_turn_tool_call_cumulative():
    from synlynk.costs import _extract_claude_structured

    output = (
        '{"type":"system","subtype":"init","cwd":"/tmp"}\n'
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"ls"}}]}}\n'
        '{"type":"user","message":{"role":"user","content":['
        '{"type":"tool_result","tool_use_id":"toolu_1","content":"a.txt\\nb.txt"}]}}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"done"}]}}\n'
        '{"type":"result","subtype":"success","is_error":false,"num_turns":2,"result":"done",'
        '"total_cost_usd":0.10485,"usage":{"input_tokens":4,"cache_creation_input_tokens":14177,'
        '"cache_read_input_tokens":55170,"output_tokens":215}}\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 4 + 14177
    assert result.output_tokens == 215
    assert result.cache_read_tokens == 55170
    assert result.basis == "structured_output"


def test_extract_claude_structured_empty_string_returns_none():
    from synlynk.costs import _extract_claude_structured

    assert _extract_claude_structured("") is None


def test_extract_claude_structured_no_result_event_returns_none():
    from synlynk.costs import _extract_claude_structured

    output = '{"type":"system","subtype":"init","cwd":"/tmp"}\n{"type":"assistant","message":{}}\n'
    assert _extract_claude_structured(output) is None


def test_extract_claude_structured_garbage_lines_mixed_with_valid_event():
    from synlynk.costs import _extract_claude_structured

    output = (
        'not json at all\n'
        '\n'
        '   \n'
        '{"type":"result","usage":{"input_tokens":100,"output_tokens":50}}\n'
        'trailing garbage after the stream\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.cache_read_tokens == 0


def test_extract_claude_structured_missing_cache_fields_default_zero():
    from synlynk.costs import _extract_claude_structured

    output = '{"type":"result","usage":{"input_tokens":10,"output_tokens":5}}\n'
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.cache_read_tokens == 0


def test_extract_claude_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_claude_structured

    output = '{"type":"result","usage":{"input_tokens":"not-a-number","output_tokens":5}}\n'
    assert _extract_claude_structured(output) is None


def test_extract_claude_structured_last_result_wins():
    from synlynk.costs import _extract_claude_structured

    output = (
        '{"type":"result","usage":{"input_tokens":10,"output_tokens":5}}\n'
        '{"type":"result","usage":{"input_tokens":999,"output_tokens":888}}\n'
    )
    result = _extract_claude_structured(output)
    assert result is not None
    assert result.input_tokens == 999
    assert result.output_tokens == 888


def test_extract_agy_structured_basic():
    from synlynk.costs import _extract_agy_structured

    output = (
        '{"conversation_id":"c1","status":"SUCCESS","response":"hello",'
        '"duration_seconds":12.34,"num_turns":1,'
        '"usage":{"input_tokens":80648,"output_tokens":2390,'
        '"thinking_tokens":1922,"total_tokens":83038}}\n'
    )
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 80648
    assert result.output_tokens == 2390 + 1922
    assert result.cache_read_tokens == 0
    assert result.basis == "structured_output"


def test_extract_agy_structured_tool_use_sample():
    from synlynk.costs import _extract_agy_structured

    output = (
        '{"conversation_id":"c2","status":"SUCCESS","response":"there are 5 files",'
        '"duration_seconds":18.02,"num_turns":1,'
        '"usage":{"input_tokens":84375,"output_tokens":3294,'
        '"thinking_tokens":2632,"total_tokens":87669}}\n'
    )
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 84375
    assert result.output_tokens == 3294 + 2632
    assert result.cache_read_tokens == 0
    assert result.basis == "structured_output"


def test_extract_agy_structured_empty_string_returns_none():
    from synlynk.costs import _extract_agy_structured

    assert _extract_agy_structured("") is None


def test_extract_agy_structured_trailing_blank_lines_still_parses():
    from synlynk.costs import _extract_agy_structured

    output = (
        '{"status":"SUCCESS","usage":{"input_tokens":10,"output_tokens":5}}\n'
        '\n'
        '   \n'
    )
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_agy_structured_status_not_success_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"FAILED","usage":{"input_tokens":10,"output_tokens":5}}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_missing_status_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"usage":{"input_tokens":10,"output_tokens":5}}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_missing_usage_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","response":"hi"}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_missing_thinking_tokens_defaults_zero():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","usage":{"input_tokens":10,"output_tokens":5}}\n'
    result = _extract_agy_structured(output)
    assert result is not None
    assert result.output_tokens == 5


def test_extract_agy_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","usage":{"input_tokens":"not-a-number","output_tokens":5}}\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_malformed_json_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = 'not json at all\n'
    assert _extract_agy_structured(output) is None


def test_extract_agy_structured_truncated_json_returns_none():
    from synlynk.costs import _extract_agy_structured

    output = '{"status":"SUCCESS","usage":{"input_tokens":10,"outp'
    assert _extract_agy_structured(output) is None

def test_extract_grok_structured_basic():
    from synlynk.costs import _extract_grok_structured

    output = (
        '{\n'
        '  "text": "Hi there.",\n'
        '  "stopReason": "EndTurn",\n'
        '  "sessionId": "019f6431-b20a-7060-bece-8ef68badf264",\n'
        '  "requestId": "4a07d1bf-9834-482b-88d5-af7072581354",\n'
        '  "thought": "The user wants a simple greeting.",\n'
        '  "usage": {\n'
        '    "input_tokens": 10118,\n'
        '    "cache_read_input_tokens": 11136,\n'
        '    "output_tokens": 29,\n'
        '    "reasoning_tokens": 22,\n'
        '    "total_tokens": 21283\n'
        '  },\n'
        '  "num_turns": 1,\n'
        '  "modelUsage": {"grok-4.5": {"inputTokens": 10118, "outputTokens": 29}}\n'
        '}\n'
    )
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 10118
    assert result.output_tokens == 29 + 22
    assert result.cache_read_tokens == 11136
    assert result.basis == "structured_output"


def test_extract_grok_structured_tool_use_sample():
    from synlynk.costs import _extract_grok_structured

    output = (
        '{\n'
        '  "text": "Here is what is in the directory.",\n'
        '  "stopReason": "EndTurn",\n'
        '  "sessionId": "019f6431-e8be-7e82-8cfa-0badf0b4bbf5",\n'
        '  "requestId": "81d3e406-f05f-46f6-9832-eeacd85a4c60",\n'
        '  "thought": "The user wants a file listing.",\n'
        '  "usage": {\n'
        '    "input_tokens": 11139,\n'
        '    "cache_read_input_tokens": 32256,\n'
        '    "output_tokens": 603,\n'
        '    "reasoning_tokens": 338,\n'
        '    "total_tokens": 43998\n'
        '  },\n'
        '  "num_turns": 2,\n'
        '  "modelUsage": {"grok-4.5": {"inputTokens": 11139, "outputTokens": 603, "modelCalls": 2}}\n'
        '}\n'
    )
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 11139
    assert result.output_tokens == 603 + 338
    assert result.cache_read_tokens == 32256
    assert result.basis == "structured_output"


def test_extract_grok_structured_cache_read_kept_separate_not_folded():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 100, "cache_read_input_tokens": 9000, "output_tokens": 20}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 100
    assert result.cache_read_tokens == 9000


def test_extract_grok_structured_empty_string_returns_none():
    from synlynk.costs import _extract_grok_structured

    assert _extract_grok_structured("") is None


def test_extract_grok_structured_single_line_json_also_parses():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 10, "output_tokens": 5}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_grok_structured_error_response_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = (
        '{"type":"error","message":"Couldn\'t set model \'bad-model\': '
        'Invalid params: \\"unknown model id\\"."}\n'
    )
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_missing_usage_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = '{"text": "hi", "stopReason": "EndTurn"}\n'
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_missing_reasoning_tokens_defaults_zero():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 10, "output_tokens": 5}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.output_tokens == 5


def test_extract_grok_structured_missing_cache_read_defaults_zero():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": 10, "output_tokens": 5}}\n'
    result = _extract_grok_structured(output)
    assert result is not None
    assert result.cache_read_tokens == 0


def test_extract_grok_structured_malformed_usage_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = '{"usage": {"input_tokens": "not-a-number", "output_tokens": 5}}\n'
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_malformed_json_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = 'not json at all\n'
    assert _extract_grok_structured(output) is None


def test_extract_grok_structured_truncated_json_returns_none():
    from synlynk.costs import _extract_grok_structured

    output = '{\n  "usage": {\n    "input_tokens": 10,\n    "outp'
    assert _extract_grok_structured(output) is None



def test_extract_tokens_agent_codex_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="codex")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_codex_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="codex")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_codex_agent_never_uses_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_claude_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"type":"result","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_claude_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="claude")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_claude_agent_never_uses_claude_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"type":"result","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="codex")
    assert result.basis != "structured_output"


def test_extract_tokens_agent_agy_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"status":"SUCCESS","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="agy")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_agy_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="agy")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_agy_agent_never_uses_agy_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"status":"SUCCESS","usage":{"input_tokens":100,"output_tokens":50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis != "structured_output"


def test_extract_tokens_agent_grok_uses_structured_output():
    from synlynk.costs import extract_tokens

    output = '{"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
    result = extract_tokens(output, agent="grok")
    assert result.basis == "structured_output"
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_extract_tokens_agent_grok_falls_back_to_regex_on_plain_text():
    from synlynk.costs import extract_tokens

    output = "Input tokens: 10\nOutput tokens: 5\n"
    result = extract_tokens(output, agent="grok")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_extract_tokens_non_grok_agent_never_uses_grok_structured_path():
    from synlynk.costs import extract_tokens

    output = '{"usage": {"input_tokens": 100, "output_tokens": 50}}\n'
    result = extract_tokens(output, agent="claude")
    assert result.basis != "structured_output"


def test_extract_tokens_default_agent_none_unchanged_behavior():
    from synlynk.costs import extract_tokens

    result = extract_tokens("Input tokens: 10\nOutput tokens: 5\n")
    assert result.basis == "regex_pair"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_load_model_rates_valid_file(project_dir):
    from synlynk.costs import _load_model_rates

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {
                "rates_updated_at": "2026-07-13",
                "unit": "usd_per_1k_tokens",
                "models": {"claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}},
                "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
                "billing_mode": {"default": "subscription", "local": "actual"},
            },
            f,
        )
    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["models"]["claude-sonnet-4-6"]["input"] == 0.003
    assert rates["billing_mode"]["default"] == "subscription"


def test_load_model_rates_missing_unit_falls_back(project_dir, capsys):
    from synlynk.costs import _load_model_rates

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {"models": {}, "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}},
            f,
        )
    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["default"] == {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
    captured = capsys.readouterr()
    assert "unit" in captured.out.lower() or "unit" in captured.err.lower()


def test_init_writes_model_rates_json(tmp_path, monkeypatch):
    import synlynk

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    synlynk.init()
    rates_path = tmp_path / ".synlynk" / "model_rates.json"
    assert rates_path.exists()
    data = json.loads(rates_path.read_text())
    assert data["unit"] == "usd_per_1k_tokens"
    assert data["billing_mode"]["local"] == "actual"


from synlynk.costs import _resolve_cost_tier, update_costs


def test_resolve_cost_tier_regex_pair_subscription():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="regex_pair")
    assert (cost_source, basis) == ("estimated_token_rate", "regex_pair")


def test_resolve_cost_tier_regex_pair_local_is_actual():
    cost_source, basis = _resolve_cost_tier(agent="local", basis="regex_pair")
    assert cost_source == "actual"
    assert basis is None


def test_resolve_cost_tier_total_split_always_tshirt():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="total_split")
    assert (cost_source, basis) == ("estimated_tshirt", "total_split")


def test_resolve_cost_tier_none_returns_none():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="none")
    assert cost_source is None


def test_check_budgets_reports_failed_job_placeholders_separately(project_dir, monkeypatch, capsys):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "load_config", lambda: {
        "budget": {"limit_usd": 1000.0, "limit_requests": 1000}
    })
    monkeypatch.setattr(synlynk.costs, "parse_costs_md", lambda: (0.5, 3))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, estimate_basis, notes) VALUES "
        "('2026-07-13', 'claude', 'claude-sonnet-4-6', 5000, 2000, 0.1, 'estimated_tshirt', "
        "'fixed_default', 'exec: failed job, exit 1')"
    )
    conn.commit()
    conn.close()

    check_budgets()
    captured = capsys.readouterr()
    assert "failed-job placeholder" in captured.out.lower()


def test_update_costs_writes_agent_name_not_username(project_dir, monkeypatch):
    """Regression test for the cost_entries agent-stores-username bug (Grok's review)."""
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    update_costs(
        "claude -p 'do the thing'", 1000, 500, 12.3,
        model_version="claude-sonnet-4-6", agent="claude",
    )
    conn = synlynk._get_db()
    row = conn.execute("SELECT agent FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "claude"


def test_costs_py_parse_costs_md_handles_est_prefix(project_dir, monkeypatch):
    import synlynk

    docs_dir = os.path.join(project_dir, "project-docs")
    os.makedirs(docs_dir, exist_ok=True)
    monkeypatch.setattr(synlynk, "_docs_dir", lambda: docs_dir)
    with open(os.path.join(docs_dir, "costs.md"), "w") as f:
        f.write("| 2026-07-13 10:00 | claude | 1 | 1000/500 | [est] $0.0270 | exec: claude -p |\n")
        f.write("| 2026-07-13 10:02 | claude | 1 | 1000/500 | [est?] $0.0270 | exec: claude -p |\n")
        f.write("| 2026-07-13 10:05 | claude | 1 | 800/400 | [legacy] $0.0100 | exec: claude -p |\n")
        f.write("| 2026-07-13 10:10 | claude | 1 | 200/100 | $0.0050 | exec: claude -p |\n")
    total_usd, total_requests = costs_parse_costs_md()
    assert total_requests == 4
    assert round(total_usd, 4) == round(0.0270 + 0.0270 + 0.0100 + 0.0050, 4)


def test_db_parse_costs_md_handles_prefixed_cost_column():
    content = "| 2026-07-13 | claude | claude-sonnet-4-6 | 1000 | 500 | 0 | [est?] $0.0270 | note |\n"
    rows = db_parse_costs_md(content)
    assert len(rows) == 1
    assert rows[0]["total_cost_usd"] == 0.0270


from synlynk.db import cmd_cost_log


def test_cmd_cost_log_writes_estimated_manual_row(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    cmd_cost_log(agent="claude", tokens_in=2000, tokens_out=800, story_id=None, note="brainstorm session")
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, estimate_basis, input_tokens, output_tokens, phase_id, notes FROM cost_entries"
    ).fetchone()
    conn.close()
    assert row[0] == "estimated_manual"
    assert row[1] == "cli_manual_entry"
    assert (row[2], row[3]) == (2000, 800)
    assert row[5] == "brainstorm session"


def test_cmd_cost_log_populates_payment_columns(project_dir, monkeypatch):
    import synlynk
    from synlynk.costs import resolve_payment_value

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)

    agent = "claude"
    tokens_in = 1234
    tokens_out = 567
    story_id = "story-payment-columns"
    payment_value = resolve_payment_value(agent, tokens_in, tokens_out)

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, discipline, phase) VALUES (?, 'T', 'backend', 'build')",
        (story_id,),
    )
    conn.commit()
    conn.close()

    cmd_cost_log(
        agent=agent,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        story_id=story_id,
        note="payment columns regression",
    )

    conn = synlynk._get_db()
    row = conn.execute(
        """
        SELECT total_cost_usd, api_equivalent_usd, actual_usd, payment_mode
        FROM cost_entries
        WHERE story_id=?
        """,
        (story_id,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[1] == pytest.approx(payment_value.api_equivalent_usd)
    assert row[2] == pytest.approx(payment_value.actual_usd)
    assert row[3] == payment_value.mode
    assert row[0] == pytest.approx(payment_value.api_equivalent_usd)


def test_cmd_cost_log_with_story_id(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    conn = synlynk._get_db()
    conn.execute("INSERT INTO stories (story_id, title, discipline, phase) VALUES ('story-9', 'T', 'backend', 'build')")
    conn.commit()
    conn.close()
    cmd_cost_log(agent="claude", tokens_in=500, tokens_out=200, story_id="story-9", note=None)
    conn = synlynk._get_db()
    row = conn.execute("SELECT story_id FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "story-9"


def test_cmd_cost_log_rejects_negative_tokens(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    with pytest.raises(ValueError):
        cmd_cost_log(agent="claude", tokens_in=-1, tokens_out=200, story_id=None, note=None)


def test_run_investigation_writes_one_cost_row(project_dir, monkeypatch):
    import re
    from types import SimpleNamespace

    import synlynk
    import synlynk.support_engineer as se_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "generate_context", lambda scope=None: None)
    monkeypatch.setattr(synlynk, "LOGS_DIR", str(project_dir))
    monkeypatch.setattr(synlynk, "PROMPTS_DIR", str(project_dir))

    def fake_run(cmd, **kwargs):
        shell_cmd = cmd[2]
        match = re.search(r">\s*(?P<log>\S+)\s+2>&1", shell_cmd)
        assert match is not None
        log_path = match.group("log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as f:
            f.write(
                "Input tokens: 12\n"
                "Output tokens: 8\n"
                "# synlynk-meta\n"
                "model_version = claude-sonnet-4-6\n"
            )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(se_mod.subprocess, "run", fake_run)

    finding = {
        "signal_hash": "abc123",
        "type": "flatline",
        "severity": "high",
        "detail": "3 consecutive failures",
        "summary": "flatline detected",
    }
    agent_cfg = {"investigator": "claude"}

    se_mod._run_investigation(finding, agent_cfg)

    conn = synlynk._get_db()
    rows = conn.execute("SELECT cost_source FROM cost_entries").fetchall()
    conn.close()
    assert len(rows) == 1


def test_cmd_launch_writes_estimated_tshirt_not_bare_zero(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "generate_context", lambda scope=None: None)
    monkeypatch.setattr(synlynk.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda e: None)

    synlynk.cmd_launch("claude", story_id=None)

    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, input_tokens FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0


def test_reconcile_daemon_jobs_writes_cost_row(project_dir, monkeypatch):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, pid, status, started_at, enqueued_at, log_path) "
        "VALUES ('job-recon-1', 'claude', 'reconcile test', NULL, 999999, 'running', '2026-07-13T00:00:00', "
        "'2026-07-13T00:00:00', ?)",
        (os.path.join(project_dir, "job-recon-1.log"),),
    )
    conn.commit()
    conn.close()

    with open(os.path.join(project_dir, "job-recon-1.log"), "w") as f:
        f.write("Input tokens: 500\nOutput tokens: 200\n")

    monkeypatch.setattr(jobs_mod.os, "waitpid", lambda pid, opts: (pid, 0))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda pid, sig: None)

    jobs_mod._reconcile_daemon_jobs()

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, input_tokens FROM cost_entries WHERE job_id='job-recon-1'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[1] == 500


def test_dispatch_writes_cost_row_even_on_zero_token_extraction(project_dir, monkeypatch):
    import synlynk
    import synlynk.dispatch as dispatch_mod
    from synlynk.costs import _TokenCounts

    class _FakeStdout:
        def readline(self):
            return b""

        def close(self):
            return None

    class _FakeProcess:
        returncode = 0
        stdout = _FakeStdout()

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "_check_pre_exec_gate", lambda force=False: True)
    monkeypatch.setattr(synlynk, "generate_context", lambda scope="full", out_path=None: None)
    monkeypatch.setattr(synlynk, "check_budgets", lambda: None)
    monkeypatch.setattr(synlynk, "set_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(synlynk, "_check_costs_freshness", lambda: None)
    monkeypatch.setattr(synlynk, "check_sentinel_patterns", lambda **_kwargs: None)
    monkeypatch.setattr(synlynk, "_check_instruction_drift", lambda: None)
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    monkeypatch.setattr(synlynk, "_dr_sync", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        synlynk,
        "_synlynk_project_docs_dir",
        lambda: os.path.join(project_dir, ".synlynk", "project-docs"),
    )
    monkeypatch.setattr(
        synlynk,
        "extract_tokens",
        lambda _text, agent=None: _TokenCounts(0, 0, 0, "none"),
    )
    monkeypatch.setattr(
        synlynk,
        "extract_model_version",
        lambda _text, agent=None: "claude-sonnet-4-6",
    )
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **k: _FakeProcess())

    exit_code = dispatch_mod.exec_command(["claude", "-p", "hi"])

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, input_tokens, output_tokens FROM cost_entries"
    ).fetchone()
    conn.close()

    assert exit_code == 0
    assert row is not None
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0
    assert row[2] > 0


def test_update_costs_zero_tokens_still_writes_tshirt_row(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    update_costs("claude -p 'x'", 0, 0, 5.0, model_version="claude-sonnet-4-6", agent="claude")
    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, input_tokens FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0


def test_update_costs_failed_job_marker_survives_short_cmd_truncation(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)

    long_command = "claude -p some-long-task-description-that-is-way-over-twenty-chars"
    update_costs(
        "[failed job] " + long_command,
        0,
        0,
        5.0,
        model_version="claude-sonnet-4-6",
        agent="claude",
    )

    conn = synlynk._get_db()
    notes = conn.execute("SELECT notes FROM cost_entries").fetchone()[0]
    conn.close()

    assert len(long_command) > 20
    assert "failed job" in notes
    assert notes.startswith("exec: [failed job] ")


def test_update_costs_costs_md_includes_provenance_prefix(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)

    costs_path = project_dir / ".synlynk" / "project-docs" / "costs.md"

    update_costs("claude -p 'x'", 0, 0, 5.0, model_version="claude-sonnet-4-6", agent="claude")
    estimated_line = costs_path.read_text().strip().splitlines()[-1]
    assert "[est] $" in estimated_line

    update_costs(
        "local -p 'x'",
        100,
        50,
        5.0,
        model_version="claude-sonnet-4-6",
        agent="local",
        basis="regex_pair",
    )
    actual_line = costs_path.read_text().strip().splitlines()[-1]
    assert "| $" in actual_line
    assert "[est] $" not in actual_line
    assert "[legacy] $" not in actual_line


def test_update_costs_flags_implausible_token_outlier(project_dir, monkeypatch, capsys):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)

    costs_path = project_dir / ".synlynk" / "project-docs" / "costs.md"

    update_costs(
        "codex -p 'x'",
        2_500_000,
        120,
        5.0,
        model_version="gpt-5-codex",
        agent="codex",
        basis="regex_pair",
    )

    captured = capsys.readouterr().out
    assert "WARNING: extracted token count 2,500,000/120 exceeds the 2,000,000 ceiling" in captured

    last_line = costs_path.read_text().strip().splitlines()[-1]
    assert "[est?] $" in last_line


def test_load_model_rates_missing_file_uses_hardcoded_default(project_dir):
    from synlynk.costs import _load_model_rates

    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["default"]["input"] == 0.003


def test_resolve_billing_mode_local_hardcoded_actual(project_dir):
    from synlynk.costs import _resolve_billing_mode

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {
                "unit": "usd_per_1k_tokens",
                "models": {},
                "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0},
                "billing_mode": {"default": "subscription", "local": "subscription"},
            },
            f,
        )
    os.chdir(project_dir)
    assert _resolve_billing_mode("local") == "actual"


def test_resolve_billing_mode_falls_back_to_default(project_dir):
    from synlynk.costs import _resolve_billing_mode

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {
                "unit": "usd_per_1k_tokens",
                "models": {},
                "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0},
                "billing_mode": {"default": "subscription"},
            },
            f,
        )
    os.chdir(project_dir)
    assert _resolve_billing_mode("codex") == "subscription"

def test_estimate_tshirt_tier1_story_estimate(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, discipline, phase, estimated_tokens) "
        "VALUES ('story-1', 'Test', 'backend', 'build', 4000)"
    )
    conn.commit()
    conn.close()
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id="story-1", discipline="backend", phase="build")
    assert basis == "story_estimate"
    assert in_t + out_t == 4000


def test_estimate_tshirt_tier2_historical_avg(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    for i in range(3):
        conn.execute(
            "INSERT INTO stories (story_id, title, discipline, phase) VALUES (?, 'T', 'backend', 'build')",
            (f"story-hist-{i}",),
        )
    conn.commit()
    conn.close()
    for i in range(3):
        _insert_cost_row(
            session_date="2026-07-01", agent="claude", model="claude-sonnet-4-6",
            input_tokens=1000, output_tokens=500, cache_read_tokens=0,
            cost_source="actual", total_cost_usd=0.01, story_id=f"story-hist-{i}",
        )
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="backend", phase="build")
    assert basis == "historical_avg"
    assert (in_t, out_t) == (1000, 500)


def test_estimate_tshirt_tier3_fixed_default(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="backend", phase="build")
    assert basis == "fixed_default"
    assert in_t > 0 and out_t > 0


def test_estimate_tshirt_ignores_estimated_tshirt_rows_in_history(project_dir, monkeypatch):
    """Historical averaging must not recycle guessed rows into future guesses (Grok's finding)."""
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    for i in range(3):
        conn.execute(
            "INSERT INTO stories (story_id, title, discipline, phase) VALUES (?, 'T', 'frontend', 'build')",
            (f"story-guess-{i}",),
        )
    conn.commit()
    conn.close()
    for i in range(3):
        _insert_cost_row(
            session_date="2026-07-01", agent="claude", model="claude-sonnet-4-6",
            input_tokens=9999, output_tokens=9999, cache_read_tokens=0,
            cost_source="estimated_tshirt", estimate_basis="fixed_default",
            total_cost_usd=0.01, story_id=f"story-guess-{i}",
        )
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="frontend", phase="build")
    assert basis == "fixed_default"
    assert in_t != 9999


def test_insert_cost_row_reachable_via_pkg_lookup():
    import synlynk

    assert hasattr(synlynk, "_insert_cost_row")


def test_only_insert_cost_row_writes_to_cost_entries():
    """Every INSERT/UPDATE against cost_entries in the source tree must go
    through _insert_cost_row - no other call site is allowed to write directly.
    """

    allowed_files_with_direct_sql = {
        "synlynk/db.py",
    }
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    violations = []
    for dirpath, _, filenames in os.walk(os.path.join(repo_root, "synlynk")):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            rel_path = os.path.relpath(os.path.join(dirpath, fname), repo_root)
            with open(os.path.join(dirpath, fname)) as f:
                content = f.read()
            if rel_path in allowed_files_with_direct_sql:
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                if "INSERT INTO cost_entries" in line or "UPDATE cost_entries" in line:
                    violations.append(f"{rel_path}:{lineno}")
    assert violations == [], f"Direct cost_entries writes outside db.py: {violations}"


def test_render_codex_log_line_agent_message():
    from synlynk import _render_codex_log_line

    line = '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Hello there"}}'
    assert _render_codex_log_line(line) == "Hello there\n\n"


def test_render_codex_log_line_command_execution():
    from synlynk import _render_codex_log_line

    line = (
        '{"type":"item.completed","item":{"id":"item_1","type":"command_execution",'
        '"command":"ls -la","aggregated_output":"a.txt\\nb.txt\\n","exit_code":0}}'
    )
    assert _render_codex_log_line(line) == "$ ls -la\na.txt\nb.txt\n\n"


def test_render_codex_log_line_item_started_omitted():
    from synlynk import _render_codex_log_line

    line = '{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"ls"}}'
    assert _render_codex_log_line(line) is None


def test_render_codex_log_line_turn_completed_omitted():
    from synlynk import _render_codex_log_line

    line = '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}'
    assert _render_codex_log_line(line) is None


def test_render_codex_log_line_unparseable_prints_as_is():
    from synlynk import _render_codex_log_line

    line = "unrecognized flag: --json"
    assert _render_codex_log_line(line) == line


def test_render_claude_log_line_text_block():
    from synlynk import _render_claude_log_line

    line = '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hello there"}]}}'
    assert _render_claude_log_line(line) == "Hello there\n\n"


def test_render_claude_log_line_tool_use_block():
    from synlynk import _render_claude_log_line

    line = (
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"ls -la"}}]}}'
    )
    assert _render_claude_log_line(line) == '$ Bash({"command":"ls -la"})\n\n'


def test_render_claude_log_line_multiple_content_blocks_concatenated():
    from synlynk import _render_claude_log_line

    line = (
        '{"type":"assistant","message":{"role":"assistant","content":['
        '{"type":"text","text":"Running it now."},'
        '{"type":"tool_use","id":"toolu_1","name":"Bash","input":{"command":"ls"}}]}}'
    )
    assert _render_claude_log_line(line) == '$ Bash({"command":"ls"})\n\n'.join(
        ["Running it now.\n\n", ""]
    )


def test_render_claude_log_line_system_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"system","subtype":"init","cwd":"/tmp"}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_rate_limit_event_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"rate_limit_event","rate_limit_info":{"status":"allowed"}}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_result_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"result","subtype":"success","result":"done","usage":{"input_tokens":10,"output_tokens":5}}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_user_tool_result_omitted():
    from synlynk import _render_claude_log_line

    line = '{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_1","content":"a.txt"}]}}'
    assert _render_claude_log_line(line) is None


def test_render_claude_log_line_unparseable_prints_as_is():
    from synlynk import _render_claude_log_line

    line = "unrecognized flag: --output-format"
    assert _render_claude_log_line(line) == line


def test_cmd_logs_renders_codex_jsonl(project_dir, monkeypatch, tmp_path, capsys):
    import synlynk

    log_file = tmp_path / "job-codex1.log"
    log_file.write_text(
        '{"type":"thread.started","thread_id":"x"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Done"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}\n'
    )
    job = {"id": "job-codex1", "agent": "codex", "log_file": str(log_file)}
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(synlynk, "_job_summary_path", lambda job_id: "/nonexistent", raising=False)

    synlynk.cmd_logs("job-codex1")

    out = capsys.readouterr().out
    assert "Done" in out
    assert '"type":"thread.started"' not in out
    assert '"type":"turn.completed"' not in out


def test_cmd_logs_non_codex_agent_unchanged(project_dir, monkeypatch, tmp_path, capsys):
    import synlynk

    log_file = tmp_path / "job-claude1.log"
    log_file.write_text("plain text transcript\nmore output\n")
    job = {"id": "job-claude1", "agent": "claude", "log_file": str(log_file)}
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(synlynk, "_job_summary_path", lambda job_id: "/nonexistent", raising=False)

    synlynk.cmd_logs("job-claude1")

    out = capsys.readouterr().out
    assert "plain text transcript" in out
    assert "more output" in out


def test_cmd_logs_renders_claude_stream_json(project_dir, monkeypatch, tmp_path, capsys):
    import synlynk

    log_file = tmp_path / "job-claude2.log"
    log_file.write_text(
        '{"type":"system","subtype":"init","cwd":"/tmp"}\n'
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done"}]}}\n'
        '{"type":"result","subtype":"success","result":"Done","usage":{"input_tokens":10,"output_tokens":5}}\n'
    )
    job = {"id": "job-claude2", "agent": "claude", "log_file": str(log_file)}
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [job], raising=False)
    monkeypatch.setattr(synlynk, "_job_summary_path", lambda job_id: "/nonexistent", raising=False)

    synlynk.cmd_logs("job-claude2")

    out = capsys.readouterr().out
    assert "Done" in out
    assert '"type":"system"' not in out
    assert '"type":"result"' not in out
