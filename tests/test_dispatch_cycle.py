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


def test_dispatch_agent_attaches_fence_estimate(monkeypatch, tmp_path):
    import synlynk
    import sqlite3

    saved = []

    class FakeProc:
        pid = 99999

    def make_conn():
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE stories (story_id TEXT PRIMARY KEY, discipline TEXT, phase TEXT, estimated_tokens INTEGER)"
        )
        conn.execute(
            "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, story_id TEXT, status TEXT, priority INTEGER, depends_on TEXT, pid INTEGER, enqueued_at TEXT, started_at TEXT, log_path TEXT, dispatch_context TEXT)"
        )
        conn.commit()
        return conn

    monkeypatch.setattr(synlynk, "JOBS_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [])
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: saved.extend(jobs))
    monkeypatch.setattr(synlynk, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(synlynk, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(synlynk, "_get_db", make_conn)
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

    from synlynk.fencing import FenceData

    assert isinstance(job["fence"], FenceData)
    assert saved[0]["cycle"] == "work"


def test_dispatch_agent_fence_uses_prompt_estimate_with_context(monkeypatch, tmp_path):
    import synlynk
    import sqlite3

    saved = []

    class FakeProc:
        pid = 99999

    def make_conn():
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE stories (story_id TEXT PRIMARY KEY, discipline TEXT, phase TEXT, estimated_tokens INTEGER)"
        )
        conn.execute(
            "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, story_id TEXT, status TEXT, priority INTEGER, depends_on TEXT, pid INTEGER, enqueued_at TEXT, started_at TEXT, log_path TEXT, dispatch_context TEXT)"
        )
        conn.commit()
        return conn

    monkeypatch.setattr(synlynk, "JOBS_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [])
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: saved.extend(jobs))
    monkeypatch.setattr(synlynk, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(synlynk, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(synlynk, "_get_db", make_conn)
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

    job = synlynk.dispatch_agent("codex", "feat/bs20-deep-scan", cycle="work", context_mode="full")

    assert job["fence"].basis == "prompt_estimate"
    assert saved[0]["cycle"] == "work"


def test_dispatch_agent_fence_uses_fallback_without_context(monkeypatch, tmp_path):
    import synlynk
    import sqlite3

    saved = []

    class FakeProc:
        pid = 99999

    def make_conn():
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE stories (story_id TEXT PRIMARY KEY, discipline TEXT, phase TEXT, estimated_tokens INTEGER)"
        )
        conn.execute(
            "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, story_id TEXT, status TEXT, priority INTEGER, depends_on TEXT, pid INTEGER, enqueued_at TEXT, started_at TEXT, log_path TEXT, dispatch_context TEXT)"
        )
        conn.commit()
        return conn

    monkeypatch.setattr(synlynk, "JOBS_FILE", str(tmp_path / "jobs.json"))
    monkeypatch.setattr(synlynk, "_load_jobs", lambda: [])
    monkeypatch.setattr(synlynk, "_save_jobs", lambda jobs: saved.extend(jobs))
    monkeypatch.setattr(synlynk, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(synlynk, "_best_agent_for_story", lambda _story_id: None)
    monkeypatch.setattr(synlynk, "_get_db", make_conn)
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

    job = synlynk.dispatch_agent("codex", "feat/bs20-deep-scan", cycle="work", context_mode="none")

    assert job["fence"].basis in ("story_estimate", "historical_avg", "fixed_default")
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
