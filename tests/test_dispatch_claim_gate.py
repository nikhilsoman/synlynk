import subprocess
import os
import pytest
from synlynk import _get_db
from synlynk.jobs import acquire_task_lease, get_active_lease
from synlynk.dispatch import dispatch_agent


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_dispatch_claims.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    claims_file = str(tmp_path / "active_claims.json")
    monkeypatch.setattr("synlynk.session._active_claims_path", lambda: claims_file)

    conn = _get_db(db_path=db_path)
    conn.execute("""
        INSERT INTO stories (story_id, title, role, stage, status, readiness)
        VALUES ('story-gate-1', 'Gate test story', 'dev', 'open', 'ready', 'ready')
    """)
    conn.commit()
    return conn


class FakeProc:
    def __init__(self, pid=8888):
        self.pid = pid
        self.returncode = 0

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def communicate(self, input=None, timeout=None):
        return ("", "")

    def kill(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def _selective_popen(fake_proc):
    real_popen = subprocess.Popen
    def _popen(cmd, *a, **kw):
        if isinstance(cmd, list) and cmd and cmd[0] == "git":
            return real_popen(cmd, *a, **kw)
        return fake_proc
    return _popen


def test_dispatch_blocks_on_active_home_session_claim(db_conn, monkeypatch):
    # Live claim held by claude session
    acquire_task_lease(
        "story-gate-1", "claude:testhost:1234", pid=os.getpid(), harness="claude", conn=db_conn
    )

    monkeypatch.setattr("synlynk.dispatch._preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr("subprocess.Popen", _selective_popen(FakeProc()))

    with pytest.raises(RuntimeError, match=r"Story story-gate-1 is currently claimed by active home session claude:testhost:1234"):
        dispatch_agent("codex", "implement task", story_id="story-gate-1", skip_preflight=True)


def test_dispatch_override_bypasses_active_claim(db_conn, monkeypatch):
    acquire_task_lease(
        "story-gate-1", "claude:testhost:1234", pid=os.getpid(), harness="claude", conn=db_conn
    )

    fake_proc = FakeProc(pid=9999)
    monkeypatch.setattr("synlynk.dispatch._preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr("subprocess.Popen", _selective_popen(fake_proc))

    job = dispatch_agent("codex", "implement task", story_id="story-gate-1", skip_preflight=True, override=True)
    assert job["id"] is not None

    lease = get_active_lease("story-gate-1", conn=db_conn)
    assert lease is not None
    assert lease["harness"] == "codex"
    assert lease["pid"] == 9999
    assert lease["status"] == "active"


def test_dispatch_records_lease_on_success(db_conn, monkeypatch):
    fake_proc = FakeProc(pid=7777)
    monkeypatch.setattr("synlynk.dispatch._preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr("subprocess.Popen", _selective_popen(fake_proc))

    job = dispatch_agent("codex", "implement task", story_id="story-gate-1", skip_preflight=True)
    assert job["id"] is not None

    lease = get_active_lease("story-gate-1", conn=db_conn)
    assert lease is not None
    assert lease["harness"] == "codex"
    assert lease["pid"] == 7777
    assert lease["status"] == "active"


def test_dispatch_cli_blocks_and_override_flag(db_conn, monkeypatch):
    from synlynk.cli import main

    acquire_task_lease(
        "story-gate-1", "claude:testhost:1234", pid=os.getpid(), harness="claude", conn=db_conn
    )
    fake_proc = FakeProc(pid=5555)
    monkeypatch.setattr("synlynk.dispatch._preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr("subprocess.Popen", _selective_popen(fake_proc))

    # 1. Without override/force -> exits with code 1
    with pytest.raises(SystemExit) as excinfo:
        main(["dispatch", "codex", "--task", "implement task", "--story", "story-gate-1", "--skip-preflight"])
    assert excinfo.value.code == 1

    # 2. With --override -> succeeds (exit 0)
    exit_code = None
    try:
        main(["dispatch", "codex", "--task", "implement task", "--story", "story-gate-1", "--skip-preflight", "--override"])
        exit_code = 0
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code in (0, None)
    lease = get_active_lease("story-gate-1", conn=db_conn)
    assert lease is not None
    assert lease["harness"] == "codex"
    assert lease["pid"] == 5555

