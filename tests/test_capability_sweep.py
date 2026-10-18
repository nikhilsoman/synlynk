import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ""))


def test_estimate_sweep_cost_multiplies_agents_models_skills(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from synlynk.capability_sweep import _estimate_sweep_cost

    discovered = {
        "codex": ["gpt-5-codex"],
        "agy": ["gemini-2.5-pro"],
    }
    skills = ["PROG", "TEST"]

    cost = _estimate_sweep_cost(discovered, skills)

    assert cost > 0
    assert isinstance(cost, float)


def test_estimate_sweep_cost_scales_with_more_models():
    from synlynk.capability_sweep import _estimate_sweep_cost

    small = _estimate_sweep_cost({"codex": ["gpt-5-codex"]}, ["PROG"])
    large = _estimate_sweep_cost({"codex": ["gpt-5-codex", "gpt-5.4-mini"]}, ["PROG"])

    assert large > small


def test_sweep_aborts_when_estimate_exceeds_cap(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.capability_sweep import cmd_capability_sweep
    import pytest

    monkeypatch.setattr(
        "synlynk.capability_sweep._discover_models",
        lambda: {"codex": [f"model-{i}" for i in range(50)]},
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_capability_sweep(cost_cap_override=0.01)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "exceeds cap" in captured.out.lower() or "exceeds cap" in captured.err.lower()


def test_seed_from_baseline_only_when_ledger_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.capability_sweep import _seed_capability_ledger_from_baseline

    baseline_path = os.path.join(os.path.dirname(sl.__file__), "capability_baseline.json")
    with open(baseline_path) as f:
        baseline = json.load(f)
    assert isinstance(baseline, list)
    assert len(baseline) > 0
    for row in baseline:
        assert row["signal_source"] == "baseline_seed"
        assert row["sample_count"] in (3, 4, 5)

    conn = sl._get_db()
    before = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    _seed_capability_ledger_from_baseline(conn)
    after = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    assert after > before

    _seed_capability_ledger_from_baseline(conn)
    after_second = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    assert after_second == after
    conn.close()


def test_baseline_seed_routes_default_tagged_story(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.capability_sweep import _seed_capability_ledger_from_baseline
    from synlynk.jobs import _capability_candidates_for_story

    conn = sl._get_db()
    _seed_capability_ledger_from_baseline(conn)

    candidates = _capability_candidates_for_story(conn, "backend", "platform", "unknown", "build")
    conn.close()

    assert candidates, "seeded baseline rows must be visible to real cold-start routing"
    agents_seen = {row[0] for row in candidates}
    assert "codex" in agents_seen or "grok" in agents_seen


def test_capability_baseline_json_ships_inside_package():
    import synlynk.capability_sweep as cs_module

    baseline_path = os.path.join(os.path.dirname(cs_module.__file__), "capability_baseline.json")
    assert os.path.exists(baseline_path), (
        "capability_baseline.json must live inside the synlynk/ package directory "
        "so it is included in package-data and ships with pip/pipx installs"
    )
    with open(baseline_path) as f:
        rows = json.load(f)
    assert isinstance(rows, list) and len(rows) > 0


def test_run_sweep_writes_baseline_seed_rows_with_independent_verifier(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.capability_sweep import _run_sweep

    calls = []

    def fake_dispatch(agent, task, **kwargs):
        calls.append((agent, task))
        return {"exit_code": 0, "output": "task complete", "agent": agent}

    def fake_verify(verifier_agent, executor_agent, model, skill, executor_output):
        assert verifier_agent != executor_agent
        return {"quality": 8.0, "correct": True, "quality_verified": True}

    monkeypatch.setattr("synlynk.capability_sweep._dispatch_calibration_task", fake_dispatch)
    monkeypatch.setattr("synlynk.capability_sweep._verify_calibration_result", fake_verify)

    discovered = {"codex": ["gpt-5-codex"], "agy": ["gemini-2.5-pro"]}
    _run_sweep(discovered, ["PROG"])

    conn = sl._get_db()
    rows = conn.execute(
        "SELECT agent, signal_source, quality FROM capability_ratings WHERE signal_source='baseline_seed'"
    ).fetchall()
    conn.close()

    assert len(rows) >= 2
    for agent, signal_source, quality in rows:
        assert signal_source == "baseline_seed"
        assert quality == 8.0


def test_pick_verifier_harness_is_not_executor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.capability_sweep import _pick_verifier_harness

    verifier = _pick_verifier_harness(
        executor_harness="codex", available_harnesses=["codex", "agy", "grok"]
    )
    assert verifier != "codex"
    assert verifier in ("agy", "grok")


def test_verify_calibration_result_marks_verified_on_valid_meta(monkeypatch):
    from synlynk import capability_sweep

    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda verifier, task, **kwargs: {
            "output": "# synlynk-meta\nquality=7\ncorrect=true\n"
        },
    )

    verdict = capability_sweep._verify_calibration_result(
        "codex", "agy", "gemini-2.5-pro", "PROG", {"output": "some code"}
    )

    assert verdict == {"quality": 7.0, "correct": True, "quality_verified": True}


def test_verify_calibration_result_falls_back_and_warns_on_unparseable_output(monkeypatch, capsys):
    from synlynk import capability_sweep

    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda verifier, task, **kwargs: {"output": "I reviewed it, looks fine."},
    )

    verdict = capability_sweep._verify_calibration_result(
        "codex", "agy", "gemini-2.5-pro", "PROG", {"output": "some code"}
    )

    assert verdict == {"quality": 5.0, "correct": True, "quality_verified": False}
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "codex" in captured.err
    assert "agy" in captured.err
    assert "I reviewed it, looks fine." in captured.err


def test_calibration_pool_has_all_role_difficulty_combinations(tmp_path, monkeypatch):
    from synlynk import db
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    roles = ("pm", "architect", "tpm", "dev", "designer", "qa", "marketing", "synlynk-bot")
    difficulties = ("basic", "intermediate", "advanced")
    rows = conn.execute("SELECT role, difficulty FROM capability_calibration_tasks").fetchall()
    present = {(r, d) for r, d in rows}
    missing = [(r, d) for r in roles for d in difficulties if (r, d) not in present]
    assert not missing, f"missing calibration tasks for: {missing}"


def test_sweep_for_harness_model_writes_calibration_result(tmp_path, monkeypatch):
    from synlynk import db, capability_sweep

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    monkeypatch.setattr(capability_sweep, "_get_db", lambda: conn)
    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda agent, task, **kwargs: {"output": "example output"},
    )
    monkeypatch.setattr(
        capability_sweep, "_verify_calibration_result",
        lambda verifier_agent, executor_agent, model, skill, executor_output: {
            "quality": 8.0, "correct": True, "quality_verified": True,
        },
    )
    monkeypatch.setattr(capability_sweep, "_pick_verifier_agent", lambda executor, available: "codex")

    capability_sweep.cmd_capability_sweep_for_harness_model("agy", "gemini-3-pro")

    rows = conn.execute(
        "SELECT harness_name, model_id, score FROM capability_calibration_results WHERE harness_name='agy'"
    ).fetchall()
    assert len(rows) >= 1
    assert all(r[2] == 0.8 for r in rows)  # quality 8.0 normalized to a 0-1 score


def test_sweep_for_harness_model_dispatches_selected_model(tmp_path, monkeypatch):
    from synlynk import db, capability_sweep

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    monkeypatch.setattr(capability_sweep, "_get_db", lambda: conn)
    calls = []

    def fake_dispatch(agent, task, **kwargs):
        calls.append((agent, kwargs))
        return {"output": "example output"}

    monkeypatch.setattr(capability_sweep, "_dispatch_calibration_task", fake_dispatch)
    monkeypatch.setattr(
        capability_sweep,
        "_verify_calibration_result",
        lambda *args: {"quality": 8.0, "correct": True, "quality_verified": True},
    )
    monkeypatch.setattr(capability_sweep, "_pick_verifier_agent", lambda *args: "codex")

    capability_sweep.cmd_capability_sweep_for_harness_model("agy", "gemini-specific")

    assert calls
    agent, kwargs = calls[0]
    assert agent == "agy"
    assert kwargs["model"] == "gemini-specific"
    assert kwargs["db_conn"] is conn


def test_sweep_for_harness_model_persists_quality_verified_false_on_fallback(tmp_path, monkeypatch):
    from synlynk import db, capability_sweep

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = db._get_db()
    monkeypatch.setattr(capability_sweep, "_get_db", lambda: conn)
    monkeypatch.setattr(
        capability_sweep, "_dispatch_calibration_task",
        lambda agent, task, **kwargs: {"output": "example output"},
    )
    monkeypatch.setattr(
        capability_sweep, "_verify_calibration_result",
        lambda verifier_agent, executor_agent, model, skill, executor_output: {
            "quality": 5.0, "correct": True, "quality_verified": False,
        },
    )
    monkeypatch.setattr(capability_sweep, "_pick_verifier_agent", lambda executor, available: "codex")

    capability_sweep.cmd_capability_sweep_for_harness_model("agy", "gemini-3-pro")

    rows = conn.execute(
        "SELECT quality_verified FROM capability_calibration_results WHERE harness_name='agy'"
    ).fetchall()
    assert len(rows) >= 1
    assert all(r[0] == 0 for r in rows)


def test_run_sweep_persists_quality_verified_true_on_real_verdict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.capability_sweep import _run_sweep

    monkeypatch.setattr(
        "synlynk.capability_sweep._dispatch_calibration_task",
        lambda agent, task, **kwargs: {"exit_code": 0, "output": "task complete", "agent": agent},
    )
    monkeypatch.setattr(
        "synlynk.capability_sweep._verify_calibration_result",
        lambda verifier_agent, executor_agent, model, skill, executor_output: {
            "quality": 8.0, "correct": True, "quality_verified": True,
        },
    )

    discovered = {"codex": ["gpt-5-codex"], "agy": ["gemini-2.5-pro"]}
    _run_sweep(discovered, ["PROG"])

    conn = sl._get_db()
    rows = conn.execute(
        "SELECT quality_verified FROM capability_ratings WHERE signal_source='baseline_seed'"
    ).fetchall()
    conn.close()

    assert len(rows) >= 2
    assert all(r[0] == 1 for r in rows)


def test_dispatch_calibration_task_passes_model_to_dispatch_agent(monkeypatch):
    from synlynk import capability_sweep

    calls = []

    def fake_dispatch(agent, task, **kwargs):
        calls.append((agent, task, kwargs))
        return {"output": "ok"}

    monkeypatch.setattr("synlynk.dispatch.dispatch_agent", fake_dispatch)

    capability_sweep._dispatch_calibration_task(
        "agy", "calibrate", model="gemini-specific"
    )

    assert calls == [
        (
            "agy",
            "calibrate",
            {"model": "gemini-specific", "force_agent": True, "skip_preflight": True},
        )
    ]


def test_dispatch_calibration_task_awaits_async_job_and_captures_output(tmp_path, monkeypatch):
    """Issue #2350: dispatch_agent returns an async job with pid and log_file, but NO 'output' key.
    _dispatch_calibration_task must await the job and populate 'output' from the log file.
    """
    from synlynk import capability_sweep

    log_file = tmp_path / "job-123.log"
    log_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    # Real dispatch_agent return: status running, pid, log_file, NO 'output'
    raw_job = {
        "job_id": "job-123",
        "agent": "codex",
        "status": "running",
        "pid": 11111,
        "log_file": str(log_file),
    }

    monkeypatch.setattr("synlynk.dispatch.dispatch_agent", lambda *a, **kw: dict(raw_job))
    # Mock PID check so process appears immediately finished
    monkeypatch.setattr("os.kill", lambda pid, sig: None if sig != 0 else (_ for _ in ()).throw(ProcessLookupError()))

    reconciled = []
    monkeypatch.setattr("synlynk.jobs._reconcile_jobs", lambda: reconciled.append(True))

    result = capability_sweep._dispatch_calibration_task("codex", "write a hello function")

    assert "output" in result, "dispatch_calibration_task must populate 'output' key"
    assert "def hello():" in result["output"]
    assert reconciled, "_reconcile_jobs must be called after job process exits"


def test_verify_calibration_result_captures_real_verifier_meta_from_log(tmp_path, monkeypatch):
    """Issue #2350: When executor and verifier run, verifier must receive executor's output,
    and verifier's '# synlynk-meta' block in log file must be parsed into quality_verified=True.
    """
    from synlynk import capability_sweep

    executor_log = tmp_path / "executor.log"
    executor_log.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    verifier_log = tmp_path / "verifier.log"
    verifier_log.write_text(
        "The implementation is correct.\n\n# synlynk-meta\nquality=9.2\ncorrect=true\n",
        encoding="utf-8",
    )

    dispatched_tasks = []

    def fake_dispatch_task(harness, task, **kwargs):
        dispatched_tasks.append((harness, task))
        if "Review this" in task:
            return {
                "job_id": "job-verifier",
                "output": verifier_log.read_text(encoding="utf-8"),
                "status": "completed",
            }
        return {
            "job_id": "job-executor",
            "output": executor_log.read_text(encoding="utf-8"),
            "status": "completed",
        }

    monkeypatch.setattr(capability_sweep, "_dispatch_calibration_task", fake_dispatch_task)

    executor_output = {"job_id": "job-executor", "output": executor_log.read_text(encoding="utf-8")}
    verdict = capability_sweep._verify_calibration_result(
        verifier_harness="claude",
        executor_harness="codex",
        model="gpt-5-codex",
        skill="PROG",
        executor_output=executor_output,
    )

    assert verdict["quality_verified"] is True
    assert verdict["quality"] == 9.2
    assert verdict["correct"] is True
    # Ensure the verifier task prompt actually contained the executor output!
    assert any("def add(a, b):" in t[1] for t in dispatched_tasks)


def test_await_calibration_job_handles_timeout(tmp_path, monkeypatch):
    import signal
    from synlynk import capability_sweep

    log_file = tmp_path / "timeout.log"
    log_file.write_text("partial output before hang", encoding="utf-8")

    job = {
        "job_id": "job-timeout",
        "agent": "grok",
        "status": "running",
        "pid": 55555,
        "log_file": str(log_file),
    }

    killed_signals = []

    def fake_kill(pid, sig):
        if sig != 0:
            killed_signals.append((pid, sig))
        return None

    monkeypatch.setattr("os.kill", fake_kill)
    cur_time = [100.0]
    monkeypatch.setattr("time.time", lambda: cur_time[0])

    def fake_sleep(secs):
        cur_time[0] += 200.0

    monkeypatch.setattr("time.sleep", fake_sleep)

    result = capability_sweep._await_calibration_job(job, timeout_s=10)

    assert result["status"] == "timeout"
    assert result["output"] == "partial output before hang"
    assert any(sig == signal.SIGTERM for _, sig in killed_signals)


def test_run_sweep_passes_model_to_dispatch_calibration_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.capability_sweep import _run_sweep

    dispatched_calls = []

    def fake_dispatch(harness, task, **kwargs):
        dispatched_calls.append((harness, task, kwargs))
        return {"output": "ok", "status": "completed"}

    monkeypatch.setattr("synlynk.capability_sweep._dispatch_calibration_task", fake_dispatch)
    monkeypatch.setattr(
        "synlynk.capability_sweep._verify_calibration_result",
        lambda *args, **kwargs: {"quality": 9.0, "correct": True, "quality_verified": True},
    )

    discovered = {"codex": ["gpt-5-codex", "gpt-5.4-mini"]}
    _run_sweep(discovered, ["PROG"])

    assert len(dispatched_calls) == 2
    assert dispatched_calls[0][2].get("model") == "gpt-5-codex"
    assert dispatched_calls[1][2].get("model") == "gpt-5.4-mini"


def test_cmd_capability_sweep_filters_by_harness(tmp_path, monkeypatch):
    from synlynk import capability_sweep

    swept = []
    monkeypatch.setattr(
        capability_sweep, "_discover_models",
        lambda: {"codex": ["gpt-5-codex"], "claude": ["claude-sonnet-5"], "agy": ["gemini-pro"]},
    )
    monkeypatch.setattr(
        capability_sweep, "_run_sweep",
        lambda discovered, skills: swept.append(discovered),
    )
    monkeypatch.setattr(
        "synlynk.capability_watch.mark_capability_sweep_run",
        lambda db: None,
    )

    capability_sweep.cmd_capability_sweep(harness="codex")

    assert len(swept) == 1
    assert list(swept[0].keys()) == ["codex"]


def test_discover_models_prefers_active_db_models_over_fallback(tmp_path, monkeypatch):
    import synlynk as sl
    from synlynk import capability_sweep

    conn = sl._get_db()
    # Insert an active model for codex
    conn.execute(
        "INSERT OR REPLACE INTO harness_models "
        "(harness_name, model_id, first_seen_at, last_seen_at, status, provider, discovered_at) "
        "VALUES ('codex', 'gpt-5.6-terra', '2026-10-18', '2026-10-18', 'active', 'native', '2026-10-18')"
    )
    conn.commit()

    discovered = capability_sweep._discover_models(conn=conn)
    assert "codex" in discovered
    assert "gpt-5.6-terra" in discovered["codex"]
    # Legacy hardcoded fallback should NOT be chosen when active models exist in DB
    assert "gpt-5-codex" not in discovered["codex"]





