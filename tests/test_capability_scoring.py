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


# --- Hotfix #43: quality_auto normalization ---

def test_quality_auto_normalizes_when_tests_absent(tmp_path, monkeypatch):
    """Perfect build + zero rework must score 10.0 even when test_pass_rate is None."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    import json

    # Log with no test output but a clean build and synlynk-meta model line
    log_content = "# synlynk-meta\nmodel_version=claude-opus-4-8\nBuild succeeded."
    log_path = str(tmp_path / ".synlynk/logs/job-norm.log")
    open(log_path, "w").write(log_content)
    open(log_path + ".exit", "w").write("0")  # exit 0 → build_success=True

    jobs = [{
        "id": "job-norm", "agent": "claude", "story_id": "story-norm",
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
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-norm", "Docs update"))
    conn.commit(); conn.close()

    _reconcile_jobs()

    conn = _get_db()
    row = conn.execute(
        "SELECT quality_auto FROM capability_ratings WHERE story_id=?", ("story-norm",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == pytest.approx(10.0, abs=0.01), \
        f"Expected 10.0 (normalized), got {row[0]:.2f} (capped at 6.5 without normalization)"

def test_quality_auto_full_signals_still_scores_correctly(tmp_path, monkeypatch):
    """When all signals present, normalization must not change the correct result."""
    from synlynk import _write_capability_rating, _get_db
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-full", "Full"))
    conn.commit(); conn.close()

    job = {
        "agent": "claude", "story_id": "story-full",
        "started_at": "2026-06-14T10:00:00", "ended_at": "2026-06-14T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
        "model_at_dispatch": "claude-opus-4-8",
    }
    # 100% test pass rate + build success + zero rework = 10.0
    log = "# synlynk-meta\nmodel_version=claude-opus-4-8\n19 passed"
    _write_capability_rating(job, log)

    conn = _get_db()
    row = conn.execute(
        "SELECT quality_auto FROM capability_ratings WHERE story_id=?", ("story-full",)
    ).fetchone()
    conn.close()
    assert row[0] == pytest.approx(10.0, abs=0.01)


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






