"""Unit tests for TASK_NOOP_DENIED Sentinel Alerting & Status Badging (Invariant 1)."""

import hashlib
import os
import subprocess
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import synlynk
from synlynk.jobs import STATUS_COMPLETED_WITHOUT_CHANGES, STATUS_FAILED_NOOP_DENIED
from synlynk.sentinel import _read_active_sentinel_alerts


@pytest.fixture
def temp_git_worktree():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@synlynk.dev"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.name", "Test Committer"], cwd=tmpdir, check=True)
        
        readme = os.path.join(tmpdir, "README.md")
        with open(readme, "w") as f:
            f.write("# Init\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmpdir, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, check=True, capture_output=True)
        
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmpdir, check=True, capture_output=True, text=True)
        base_sha = res.stdout.strip()
        yield tmpdir, base_sha


def test_noop_job_writes_task_noop_denied_sentinel_alert(temp_git_worktree, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    worktree, base_sha = temp_git_worktree
    
    task_text = "Implement feature bar"
    task_digest = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
    
    job_id = "job-noop-alert-test"
    log_dir = tmp_path / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{job_id}.log"
    exit_file = log_dir / f"{job_id}.log.exit"
    log_file.write_text(f"SYNLYNK_TASK_RECEIVED: {task_digest}\nNo files changed.")
    exit_file.write_text("0")
    
    job = {
        "id": job_id,
        "agent": "grok",
        "task": task_text,
        "status": "running",
        "pid": 99999999,
        "worktree_path": worktree,
        "worktree_branch": "feat/bar",
        "base_sha": base_sha,
        "log_file": str(log_file),
        "started_at": "2026-09-27T12:00:00",
        "ended_at": None,
        "exit_code": None,
    }
    synlynk._save_jobs([job])
    
    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    synlynk._reconcile_jobs()
    
    sentinel_file = tmp_path / ".synlynk" / "sentinel.md"
    assert sentinel_file.exists()
    content = sentinel_file.read_text()
    assert "TASK_NOOP_DENIED" in content
    assert "grok" in content
    
    # Also verify _read_active_sentinel_alerts parses it
    active_alerts = _read_active_sentinel_alerts(str(sentinel_file))
    noop_alerts = [a for a in active_alerts if a.get("code") == "TASK_NOOP_DENIED"]
    assert len(noop_alerts) >= 1
    assert "grok" in noop_alerts[0].get("message", "").lower()


def test_viz_renders_noop_status_chip():
    from synlynk.viz import generate_overview_html
    
    jobs = [{
        "id": "job-test-noop-viz",
        "agent": "agy",
        "task": "Test noop task",
        "status": "completed_without_changes",
        "worktree_path": "/tmp/test",
    }]
    
    html = generate_overview_html(
        {"workspace": {"name": "Test Product"}, "jobs": jobs},
        8721,
    )
    assert "status-chip noop" in html or "NOOP" in html
