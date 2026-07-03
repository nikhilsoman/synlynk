import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_dispatch_stores_cycle(monkeypatch, tmp_path):
    import synlynk

    saved = []

    class FakeProc:
        pid = 99999

    monkeypatch.setattr(synlynk, "JOBS_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [])
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: saved.extend(jobs))
    monkeypatch.setattr(synlynk, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(synlynk, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(synlynk, "_get_db", lambda: None)
    monkeypatch.setattr(
        synlynk,
        "_preflight_dispatch",
        lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None},
    )
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda _agent: {})
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda _agent, _cli: "model")
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda _context: None)
    monkeypatch.setattr(synlynk, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(synlynk, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(synlynk, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(synlynk.subprocess, "Popen", lambda *a, **kw: FakeProc())

    job = synlynk.dispatch_agent("codex", "feat/bs20-deep-scan", cycle="work")

    assert job["cycle"] == "work"
    assert saved[0]["cycle"] == "work"


def test_dispatch_cycle_defaults_to_work(monkeypatch, tmp_path):
    import synlynk

    saved = []

    class FakeProc:
        pid = 99999

    monkeypatch.setattr(synlynk, "JOBS_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [])
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: saved.extend(jobs))
    monkeypatch.setattr(synlynk, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(synlynk, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(synlynk, "_get_db", lambda: None)
    monkeypatch.setattr(
        synlynk,
        "_preflight_dispatch",
        lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None},
    )
    monkeypatch.setattr(synlynk, "_load_agent_profile", lambda _agent: {})
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda _agent, _cli: "model")
    monkeypatch.setattr(synlynk, "_warn_context_size", lambda _context: None)
    monkeypatch.setattr(synlynk, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(synlynk, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(synlynk, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(synlynk.subprocess, "Popen", lambda *a, **kw: FakeProc())

    job = synlynk.dispatch_agent("agy", "docs task")

    assert job["cycle"] == "work"
    assert saved[0]["cycle"] == "work"
