import os


def test_cmd_logs_appends_summary_when_present(project_dir, capsys):
    import synlynk as sl

    job_id = "job-summary"
    log_path = os.path.join(".synlynk", "logs", f"{job_id}.log")
    summary_path = os.path.join(".synlynk", "logs", f"{job_id}.summary")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    sl._save_jobs([
        {
            "id": job_id,
            "agent": "agy",
            "status": "failed",
            "log_file": log_path,
            "pid": 1,
            "story_id": "",
            "task": "task",
            "started_at": "2026-07-04T10:00:00",
            "ended_at": "2026-07-04T10:05:00",
            "exit_code": -1,
            "prompt_file": "",
        }
    ])
    with open(log_path, "w") as f:
        f.write("log line 1\nlog line 2\n")
    with open(summary_path, "w") as f:
        f.write("-- job job-summary complete ---------\nstatus: FAILED (exit -1)\n")

    sl.cmd_logs(job_id, tail=10)
    out = capsys.readouterr().out
    assert "log line 1" in out
    assert "status: FAILED (exit -1)" in out


def test_cmd_logs_missing_summary_does_not_crash(project_dir, capsys):
    import synlynk as sl

    job_id = "job-no-summary"
    log_path = os.path.join(".synlynk", "logs", f"{job_id}.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    sl._save_jobs([
        {
            "id": job_id,
            "agent": "agy",
            "status": "running",
            "log_file": log_path,
            "pid": 1,
            "story_id": "",
            "task": "task",
            "started_at": "2026-07-04T10:00:00",
            "ended_at": None,
            "exit_code": None,
            "prompt_file": "",
        }
    ])
    with open(log_path, "w") as f:
        f.write("still running\n")

    sl.cmd_logs(job_id, tail=10)
    out = capsys.readouterr().out
    assert "still running" in out
    assert "No summary" not in out


def test_preflight_dispatch_returns_fail_on_missing_required_flag(monkeypatch):
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.setattr(
        dispatch_mod,
        "AGENT_CAPABILITY_BASELINES",
        {
            "testbot": {
                "dispatch_flags": {
                    "valid_flags": ["--present"],
                    "invalid_flags": [],
                    "required_flags": ["--required"],
                },
                "network_deps": {"required_endpoints": []},
            }
        },
        raising=False,
    )
    monkeypatch.setattr(
        "synlynk.probe._run_tc2",
        lambda agent_name, flags_spec: {"passed": False, "failed_flags": ["--required"]},
    )

    result = _preflight_dispatch("testbot", [], db_conn=None)
    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "--required" in result["reason"]


def test_preflight_dispatch_passes_when_tc2_passes(monkeypatch):
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.setattr(
        dispatch_mod,
        "AGENT_CAPABILITY_BASELINES",
        {
            "testbot": {
                "dispatch_flags": {
                    "valid_flags": ["--present"],
                    "invalid_flags": [],
                    "required_flags": ["--required"],
                },
                "network_deps": {"required_endpoints": []},
            }
        },
        raising=False,
    )
    monkeypatch.setattr(
        "synlynk.probe._run_tc2",
        lambda agent_name, flags_spec: {"passed": True, "failed_flags": []},
    )

    result = _preflight_dispatch("testbot", [], db_conn=None)
    assert result["passed"] is True


def test_preflight_dispatch_skips_tc2_for_minimal_flag_specs(monkeypatch):
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.setattr(
        dispatch_mod,
        "AGENT_CAPABILITY_BASELINES",
        {
            "testbot": {
                "dispatch_flags": {
                    "valid_flags": [],
                    "invalid_flags": [],
                    "required_flags": [],
                },
                "network_deps": {"required_endpoints": []},
            }
        },
        raising=False,
    )

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("TC-2 should not run for minimal flag specs")

    monkeypatch.setattr("synlynk.probe._run_tc2", _fail_if_called)

    result = _preflight_dispatch("testbot", [], db_conn=None)
    assert result["passed"] is True


def test_dispatch_agent_skip_preflight_bypasses_gate(monkeypatch, tmp_path):
    import synlynk as sl

    saved = []

    class FakeProc:
        pid = 4242

    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("preflight should be skipped")))
    monkeypatch.setattr(sl, "JOBS_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setattr(sl, "_load_jobs", lambda: [])
    monkeypatch.setattr(sl, "_save_jobs", lambda jobs: saved.extend(jobs))
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(sl, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(sl, "_get_db", lambda: None)
    monkeypatch.setattr(sl, "_load_agent_profile", lambda _agent: {})
    monkeypatch.setattr(sl, "_probe_model_version", lambda _agent, _cli: "model")
    monkeypatch.setattr(sl, "_warn_context_size", lambda _context: None)
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl.subprocess, "Popen", lambda *a, **kw: FakeProc())

    job = sl.dispatch_agent("codex", "fix bug", skip_preflight=True)
    assert job["pid"] == 4242
    assert saved[0]["id"] == job["id"]
