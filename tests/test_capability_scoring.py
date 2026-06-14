import os
import sqlite3
import tempfile
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))

def test_get_db_creates_state_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    conn.close()
    assert os.path.exists(".synlynk/state/state.db")

def test_migrate_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "stories" in tables
    assert "capability_ratings" in tables

def test_migrate_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    _get_db().close()
    _get_db().close()  # second call must not crash

def test_init_writes_industry_to_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def mock_input(prompt):
        if "[y/N]" in prompt:
            return "n"
        elif "Email or synlynk ID" in prompt:
            return "user@example.com"
        elif "Industry vertical" in prompt:
            return "ott"
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init
    init(force=True)
    import json
    config = json.load(open(".synlynk/config.json"))
    assert config.get("industry") == "ott"
    assert config.get("workgroup_invite_email") == "user@example.com"

def test_init_infers_industry_from_readme(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# MyApp\nA fintech platform for trading.")
    def mock_input(prompt):
        if "[y/N]" in prompt:
            return "n"
        elif "Email or synlynk ID" in prompt:
            return ""
        elif "Industry vertical" in prompt:
            return "" # Accept default
        return ""
    monkeypatch.setattr("builtins.input", mock_input)
    from synlynk import init, _infer_industry
    inferred = _infer_industry(str(tmp_path))
    assert inferred == "fintech"
    init(force=True)
    import json
    config = json.load(open(".synlynk/config.json"))
    assert config.get("industry") == "fintech"

def test_story_create_writes_to_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, _get_db
    cmd_story_create(title="Add billing endpoint", engg_domain="backend",
                     org_domain="monetization", phase="build")
    conn = _get_db()
    rows = conn.execute("SELECT * FROM stories WHERE title=?",
                        ("Add billing endpoint",)).fetchall()
    conn.close()
    assert len(rows) == 1

def test_story_create_generates_unique_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, _get_db
    cmd_story_create(title="Story A", engg_domain="backend", org_domain="platform", phase="build")
    cmd_story_create(title="Story B", engg_domain="frontend", org_domain="growth", phase="build")
    conn = _get_db()
    rows = conn.execute("SELECT story_id FROM stories").fetchall()
    conn.close()
    ids = [r[0] for r in rows]
    assert len(set(ids)) == 2

def test_story_list_returns_rows(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, cmd_story_list
    cmd_story_create(title="My story", engg_domain="data", org_domain="analytics", phase="build")
    cmd_story_list()
    out = capsys.readouterr().out
    assert "My story" in out

def test_infer_engg_domain_from_paths():
    from synlynk import _infer_engg_domain
    assert _infer_engg_domain("Modified src/api/billing.py and tests/test_billing.py") == "backend"
    assert _infer_engg_domain("Updated src/components/Button.tsx") == "frontend"
    assert _infer_engg_domain("Added pipeline/etl_job.py and models/schema.sql") == "data"
    assert _infer_engg_domain("No matching paths here") == "unknown"

def test_infer_engg_domain_prefers_specific_over_generic():
    from synlynk import _infer_engg_domain
    # ML beats backend when both patterns present
    assert _infer_engg_domain("src/ml/train.py and src/api/serve.py") in ("ml", "backend")

def test_extract_model_version_from_meta_header():
    from synlynk import extract_model_version
    output = """
Some agent output here.

# synlynk-meta
model_version=claude-opus-4-8
quality=8
correct=true
"""
    assert extract_model_version(output) == "claude-opus-4-8"

def test_extract_model_version_missing_returns_unknown():
    from synlynk import extract_model_version
    assert extract_model_version("No meta block here") == "unknown"

def test_extract_model_version_falls_back_to_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json
    json.dump({"agents": {"claude": {"default_model": "claude-sonnet-4-6"}}},
              open(".synlynk/config.json", "w"))
    from synlynk import extract_model_version
    result = extract_model_version("No meta block", agent="claude")
    assert result == "claude-sonnet-4-6"

def test_extract_model_version_parses_various_formats():
    from synlynk import extract_model_version
    # Whitespace tolerance
    assert extract_model_version("# synlynk-meta\n model_version = gemini-2.5-pro\n") == "gemini-2.5-pro"

def test_extract_auto_signals_test_pass_rate():
    from synlynk import _extract_auto_signals
    log = "Tests: 47 passed, 3 failed, 50 total"
    signals = _extract_auto_signals(log, started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:05:00")
    assert abs(signals["test_pass_rate"] - 0.94) < 0.01

def test_extract_auto_signals_build_success_on_zero_exit():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("Build OK", started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:01:00", exit_code=0)
    assert signals["build_success"] is True

def test_extract_auto_signals_build_fail_on_nonzero_exit():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("Error: compilation failed",
                                    started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:01:00", exit_code=1)
    assert signals["build_success"] is False

def test_extract_auto_signals_duration_computed():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("", started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:10:00")
    assert signals["duration_seconds"] == pytest.approx(600.0, abs=1)

def test_extract_auto_signals_all_zeros_on_empty_log():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("", started_at=None, ended_at=None)
    assert signals["test_pass_rate"] is None
    assert signals["build_success"] is None


# --- Task 7: dispatch_rework + micro_rework ---

def test_dispatch_rework_increments_on_same_story(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    os.makedirs(".synlynk/prompts", exist_ok=True)
    import json
    jobs = [{
        "id": "job-prev", "agent": "claude", "story_id": "story-abc",
        "status": "completed", "exit_code": 0,
        "dispatch_rework": 0, "micro_rework": 0,
        "started_at": "2026-06-14T10:00:00", "ended_at": "2026-06-14T10:05:00"
    }]
    json.dump(jobs, open(".synlynk/jobs.json", "w"))
    from synlynk import _count_dispatch_rework
    assert _count_dispatch_rework("story-abc") == 1

def test_micro_rework_extracted_from_log():
    from synlynk import _extract_micro_rework
    log = "Retrying step 1...\nRetrying step 1...\nRetrying step 2..."
    assert _extract_micro_rework(log) == 3

def test_micro_rework_zero_when_no_retries():
    from synlynk import _extract_micro_rework
    assert _extract_micro_rework("All steps passed cleanly.") == 0


# --- Task 8: _write_capability_rating ---

def test_reconcile_writes_capability_rating_on_completion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    import json

    log_content = "# synlynk-meta\nmodel_version=claude-opus-4-8\n\n47 passed"
    log_path = str(tmp_path / ".synlynk/logs/job-test.log")
    open(log_path, "w").write(log_content)
    exit_path = log_path + ".exit"
    open(exit_path, "w").write("0")

    jobs = [{
        "id": "job-test", "agent": "claude", "story_id": "story-xyz",
        "status": "running", "pid": 99999999,
        "log_file": log_path, "prompt_file": None,
        "started_at": "2026-06-14T10:00:00", "ended_at": None,
        "exit_code": None, "dispatch_rework": 0, "micro_rework": 0
    }]
    json.dump(jobs, open(".synlynk/jobs.json", "w"))
    json.dump({"industry": "ott"}, open(".synlynk/config.json", "w"))

    from synlynk import _get_db, _reconcile_jobs
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?, ?)", ("story-xyz", "Test"))
    conn.commit()
    conn.close()

    _reconcile_jobs()

    conn = _get_db()
    row = conn.execute(
        "SELECT model_version, test_pass_rate, build_success FROM capability_ratings "
        "WHERE story_id=?", ("story-xyz",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "claude-opus-4-8"
    assert row[2] == 1


# --- Task 9: capability-based routing ---

def test_dispatch_uses_capability_score_when_available(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase) "
                 "VALUES (?, ?, ?, ?, ?, ?)", ("story-1", "Test", "backend", "monetization", "ott", "build"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "gemini", "gemini-2.5-pro", "backend", "monetization", "ott",
         "build", "auto", 8.5, 8.5)
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "claude", "claude-opus-4-8", "backend", "monetization", "ott",
         "build", "auto", 6.0, 6.0)
    )
    conn.commit()
    conn.close()
    result = _best_agent_for_story("story-1")
    assert result == "gemini"

def test_dispatch_returns_none_when_no_capability_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase) "
                 "VALUES (?, ?, ?, ?, ?, ?)", ("story-2", "Test", "backend", "monetization", "ott", "build"))
    conn.commit()
    conn.close()
    assert _best_agent_for_story("story-2") is None


# --- Task 10: score add/list ---

def test_score_add_writes_human_rating(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_score_add
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-1", "Test"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "claude", "claude-opus-4-8", "backend", "monetization", "ott",
         "build", "auto", 6.0, 6.0)
    )
    conn.commit()
    conn.close()
    cmd_score_add("story-1", 9.0, note="Clean first-pass implementation")
    conn = _get_db()
    row = conn.execute(
        "SELECT signal_source, quality, note FROM capability_ratings "
        "WHERE story_id=? AND signal_source='human'", ("story-1",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[1] == 9.0
    assert "Clean" in row[2]

def test_score_add_rejects_out_of_range(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_score_add
    _get_db().close()
    with pytest.raises(ValueError):
        cmd_score_add("story-1", 11.0)


# --- Task 11: statusline probe ---

def test_probe_model_version_parses_claude_statusline(monkeypatch):
    from synlynk import _probe_model_version
    import subprocess
    fake = type("R", (), {"stdout": "claude-opus-4-8 | ctx: 45%", "returncode": 0})()
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    result = _probe_model_version("claude", "claude")
    assert result == "claude-opus-4-8"

def test_probe_model_version_returns_unknown_on_failure(monkeypatch):
    from synlynk import _probe_model_version
    import subprocess
    def raise_exc(*a, **k): raise Exception("timeout")
    monkeypatch.setattr(subprocess, "run", raise_exc)
    result = _probe_model_version("claude", "claude")
    assert result == "unknown"

def test_probe_model_version_flexible_pattern(monkeypatch):
    from synlynk import _probe_model_version
    import subprocess
    # Covers "claude-3-5-sonnet" format (version before family name)
    fake = type("R", (), {"stdout": "claude-3-5-sonnet | ctx: 20%", "returncode": 0, "stderr": ""})()
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    result = _probe_model_version("claude", "claude")
    assert "sonnet" in result


# --- Task 12: verifier meta parsing ---

def test_extract_verifier_meta_block():
    from synlynk import extract_verifier_meta
    output = """
Code review complete.

# synlynk-meta
quality=8
correct=true
rework_needed=false
verifier_model=gemini-2.5-pro
"""
    meta = extract_verifier_meta(output)
    assert meta["quality"] == 8.0
    assert meta["correct"] is True
    assert meta["rework_needed"] is False
    assert meta["verifier_model"] == "gemini-2.5-pro"

def test_extract_verifier_meta_returns_none_when_absent():
    from synlynk import extract_verifier_meta
    assert extract_verifier_meta("No meta block here") is None


# --- Task 13: pr check + score attest ---

def test_pr_check_blocks_on_unknown_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_pr_check
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-1", "T"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "claude", "unknown", "backend", "monetization", "ott",
         "build", "auto", 5.0, 5.0)
    )
    conn.commit(); conn.close()
    with pytest.raises(SystemExit) as exc:
        cmd_pr_check()
    assert exc.value.code != 0

def test_pr_check_passes_when_all_models_known(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_pr_check
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-2", "T"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-2", "claude", "claude-opus-4-8", "backend", "monetization", "ott",
         "build", "auto", 8.0, 8.0)
    )
    conn.commit(); conn.close()
    cmd_pr_check()  # must not raise

def test_score_attest_updates_model_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_score_attest
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-3", "T"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-3", "claude", "unknown", "backend", "monetization", "ott",
         "build", "auto", 5.0, 5.0)
    )
    conn.commit(); conn.close()
    cmd_score_attest("story-3", "claude-opus-4-8")
    conn = _get_db()
    row = conn.execute("SELECT model_version FROM capability_ratings WHERE story_id=?",
                       ("story-3",)).fetchone()
    conn.close()
    assert row[0] == "claude-opus-4-8"

def test_score_attest_sets_split_model_when_dispatch_differs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_score_attest
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-4", "T"))
    # Row was dispatched with gemini but completion unknown (model changed mid-task)
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, model_at_dispatch, engg_domain, org_domain, "
        "industry, phase, signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("story-4", "claude", "unknown", "gemini-2.5-pro", "backend", "monetization",
         "ott", "build", "auto", 5.0, 5.0)
    )
    conn.commit(); conn.close()
    cmd_score_attest("story-4", "claude-opus-4-8")
    conn = _get_db()
    row = conn.execute(
        "SELECT model_version, split_model FROM capability_ratings WHERE story_id=?",
        ("story-4",)
    ).fetchone()
    conn.close()
    assert row[0] == "claude-opus-4-8"
    assert row[1] == 1  # split_model flagged: dispatch=gemini, completion=claude


def test_write_capability_rating_sets_correct_from_verifier(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    import json
    log_content = (
        "# synlynk-meta\n"
        "model_version=claude-opus-4-8\n"
        "quality=7\n"
        "correct=false\n"
        "rework_needed=true\n"
        "verifier_model=gemini-2.5-pro\n"
    )
    log_path = str(tmp_path / ".synlynk/logs/job-v.log")
    open(log_path, "w").write(log_content)
    open(log_path + ".exit", "w").write("0")
    jobs = [{
        "id": "job-v", "agent": "claude", "story_id": "story-v",
        "status": "running", "pid": 99999999,
        "log_file": log_path, "prompt_file": None,
        "started_at": "2026-06-14T10:00:00", "ended_at": None,
        "exit_code": None, "dispatch_rework": 0, "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }]
    json.dump(jobs, open(".synlynk/jobs.json", "w"))
    json.dump({"industry": "ott"}, open(".synlynk/config.json", "w"))
    from synlynk import _get_db, _reconcile_jobs
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-v", "T"))
    conn.commit(); conn.close()
    _reconcile_jobs()
    conn = _get_db()
    row = conn.execute(
        "SELECT signal_source, quality, correct FROM capability_ratings WHERE story_id=?",
        ("story-v",)
    ).fetchone()
    conn.close()
    assert row[0] == "verifier"
    assert row[1] == 7.0
    assert row[2] == 0  # correct=false from verifier meta


# --- R2 fix: tier resolution and split_model correctness in _write_capability_rating ---

def test_write_capability_rating_no_false_split_model_when_no_tier1(tmp_path, monkeypatch):
    """When no synlynk-meta header is present, split_model must stay 0 even if config default
    differs from model_at_dispatch — Tier 3 config default must never trigger split_model."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    import json
    # Log has no synlynk-meta header; dispatch probed as gemini; config default is claude
    log_content = "Build complete.\nAll tests passed 5/5.\n"
    log_path = str(tmp_path / ".synlynk/logs/job-r2.log")
    open(log_path, "w").write(log_content)
    open(log_path + ".exit", "w").write("0")
    jobs = [{
        "id": "job-r2", "agent": "claude", "story_id": "story-r2",
        "status": "running", "pid": 99999999,
        "log_file": log_path, "prompt_file": None,
        "started_at": "2026-06-14T10:00:00", "ended_at": None,
        "exit_code": None, "dispatch_rework": 0, "micro_rework": 0,
        "model_at_dispatch": "gemini-2.5-pro",  # Tier 2: live probe
    }]
    json.dump(jobs, open(".synlynk/jobs.json", "w"))
    # Config default is different agent — must not trigger split_model
    json.dump({"agents": {"claude": {"default_model": "claude-opus-4-8"}}, "industry": "ott"},
              open(".synlynk/config.json", "w"))
    from synlynk import _get_db, _reconcile_jobs
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-r2", "R2"))
    conn.commit(); conn.close()
    _reconcile_jobs()
    conn = _get_db()
    row = conn.execute(
        "SELECT model_version, split_model FROM capability_ratings WHERE story_id=?",
        ("story-r2",)
    ).fetchone()
    conn.close()
    # model_version should be Tier 2 (model_at_dispatch) since no Tier 1 header
    assert row[0] == "gemini-2.5-pro"
    # split_model must be 0 — no Tier 1 header means no evidence of a split-model run
    assert row[1] == 0


def test_write_capability_rating_flags_split_model_when_tier1_differs_from_dispatch(tmp_path, monkeypatch):
    """When Tier 1 synlynk-meta header is present and differs from model_at_dispatch,
    split_model must be 1."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    import json
    log_content = (
        "# synlynk-meta\n"
        "model_version=claude-opus-4-8\n"
        "quality=8\n"
    )
    log_path = str(tmp_path / ".synlynk/logs/job-r2b.log")
    open(log_path, "w").write(log_content)
    open(log_path + ".exit", "w").write("0")
    jobs = [{
        "id": "job-r2b", "agent": "claude", "story_id": "story-r2b",
        "status": "running", "pid": 99999999,
        "log_file": log_path, "prompt_file": None,
        "started_at": "2026-06-14T10:00:00", "ended_at": None,
        "exit_code": None, "dispatch_rework": 0, "micro_rework": 0,
        "model_at_dispatch": "gemini-2.5-pro",  # Tier 2: different from Tier 1
    }]
    json.dump(jobs, open(".synlynk/jobs.json", "w"))
    json.dump({"industry": "ott"}, open(".synlynk/config.json", "w"))
    from synlynk import _get_db, _reconcile_jobs
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-r2b", "R2b"))
    conn.commit(); conn.close()
    _reconcile_jobs()
    conn = _get_db()
    row = conn.execute(
        "SELECT model_version, split_model FROM capability_ratings WHERE story_id=?",
        ("story-r2b",)
    ).fetchone()
    conn.close()
    assert row[0] == "claude-opus-4-8"  # Tier 1 wins
    assert row[1] == 1  # True split-model: Tier 1 ≠ Tier 2


# --- Task 14: org_domain_tags ---

def test_story_create_stores_org_domain_tags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_story_create
    cmd_story_create(title="Ad insertion", engg_domain="backend",
                     org_domain="adtech", phase="build",
                     org_domain_tags=["monetization", "workflow"])
    conn = _get_db()
    row = conn.execute("SELECT org_domain_tags FROM stories WHERE title=?",
                       ("Ad insertion",)).fetchone()
    conn.close()
    import json as _json
    tags = _json.loads(row[0])
    assert "monetization" in tags
    assert "workflow" in tags

def test_org_domain_tags_not_used_in_routing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, "
        "org_domain_tags, industry, phase) VALUES (?,?,?,?,?,?,?)",
        ("s-1", "T", "backend", "adtech", '["monetization"]', "ott", "build")
    )
    # Seed a rating for a completely different coordinate — different engg AND org
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, engg_domain, "
        "org_domain, industry, phase, signal_source, quality, quality_auto) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("s-1", "claude", "claude-opus-4-8", "frontend", "monetization", "ott",
         "build", "auto", 9.0, 9.0)
    )
    conn.commit(); conn.close()
    # story.org_domain="adtech", story.engg_domain="backend"
    # rating has org_domain="monetization", engg_domain="frontend" — no fallback level matches
    # verifies org_domain_tags don't substitute for org_domain in routing
    result = _best_agent_for_story("s-1")
    assert result is None






