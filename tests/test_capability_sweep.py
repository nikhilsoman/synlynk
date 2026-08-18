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
        return {"quality": 8.0, "correct": True}

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
        lambda verifier_agent, executor_agent, model, skill, executor_output: {"quality": 8.0, "correct": True},
    )
    monkeypatch.setattr(capability_sweep, "_pick_verifier_agent", lambda executor, available: "codex")

    capability_sweep.cmd_capability_sweep_for_harness_model("agy", "gemini-3-pro")

    rows = conn.execute(
        "SELECT harness_name, model_id, score FROM capability_calibration_results WHERE harness_name='agy'"
    ).fetchall()
    assert len(rows) >= 1
    assert all(r[2] == 0.8 for r in rows)  # quality 8.0 normalized to a 0-1 score


