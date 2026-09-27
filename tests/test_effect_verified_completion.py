"""Integration tests for Dispatch & Job Finalizer Effect Verification (Invariant 1)."""

import hashlib
import os
import subprocess
import sys
import tempfile
from unittest.mock import patch
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import synlynk
from synlynk.jobs import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITHOUT_CHANGES,
    STATUS_FAILED_NOOP_DENIED,
    STATUS_FAILED_VERIFICATION,
)


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


def test_reconcile_mutating_job_zero_diff_becomes_completed_without_changes(temp_git_worktree, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    worktree, base_sha = temp_git_worktree
    
    task_text = "Implement feature foo"
    task_digest = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
    
    job_id = "job-test-noop"
    log_dir = tmp_path / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{job_id}.log"
    exit_file = log_dir / f"{job_id}.log.exit"
    log_file.write_text(f"SYNLYNK_TASK_RECEIVED: {task_digest}\nAll done without touching anything.")
    exit_file.write_text("0")
    
    job = {
        "id": job_id,
        "agent": "agy",
        "task": task_text,
        "status": "running",
        "pid": 99999999,
        "worktree_path": worktree,
        "worktree_branch": "feat/foo",
        "base_sha": base_sha,
        "log_file": str(log_file),
        "started_at": "2026-09-27T12:00:00",
        "ended_at": None,
        "exit_code": None,
    }
    synlynk._save_jobs([job])
    
    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    synlynk._reconcile_jobs()
    
    reconciled = synlynk._load_jobs()
    assert reconciled[0]["status"] == STATUS_COMPLETED_WITHOUT_CHANGES


def test_reconcile_mutating_job_with_diff_becomes_completed(temp_git_worktree, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    worktree, base_sha = temp_git_worktree
    
    # Mutate worktree
    new_file = os.path.join(worktree, "code.py")
    with open(new_file, "w") as f:
        f.write("print(1)\n")
    
    task_text = "Implement code.py"
    task_digest = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
    
    job_id = "job-test-success"
    log_dir = tmp_path / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{job_id}.log"
    exit_file = log_dir / f"{job_id}.log.exit"
    log_file.write_text(f"SYNLYNK_TASK_RECEIVED: {task_digest}\nCreated code.py")
    exit_file.write_text("0")
    
    job = {
        "id": job_id,
        "agent": "agy",
        "task": task_text,
        "status": "running",
        "pid": 99999999,
        "worktree_path": worktree,
        "worktree_branch": "feat/foo",
        "base_sha": base_sha,
        "log_file": str(log_file),
        "started_at": "2026-09-27T12:00:00",
        "ended_at": None,
        "exit_code": None,
    }
    synlynk._save_jobs([job])
    
    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    synlynk._reconcile_jobs()
    
    reconciled = synlynk._load_jobs()
    assert reconciled[0]["status"] == STATUS_COMPLETED


def test_reconcile_gh_write_unverified_becomes_failed_noop_denied(temp_git_worktree, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    worktree, base_sha = temp_git_worktree
    
    task_text = "Review PR #99"
    task_digest = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
    
    job_id = "job-test-gh-noop"
    log_dir = tmp_path / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{job_id}.log"
    exit_file = log_dir / f"{job_id}.log.exit"
    log_file.write_text(f"SYNLYNK_TASK_RECEIVED: {task_digest}\nReview complete.")
    exit_file.write_text("0")
    
    job = {
        "id": job_id,
        "agent": "codex",
        "task": task_text,
        "task_type": "review",
        "requires_gh_write": True,
        "gh_write_target": "pr:99",
        "gh_write_expect": "review_posted",
        "worktree_path": worktree,
        "base_sha": base_sha,
        "status": "running",
        "pid": 99999999,
        "log_file": str(log_file),
        "started_at": "2026-09-27T12:00:00",
        "ended_at": None,
        "exit_code": None,
    }
    synlynk._save_jobs([job])
    
    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    with patch("synlynk.verify_effects.gh_write_verified", return_value=False):
        synlynk._reconcile_jobs()
        
    reconciled = synlynk._load_jobs()
    assert reconciled[0]["status"] == STATUS_FAILED_NOOP_DENIED


def test_reconcile_mutating_job_with_failing_verification_cmd_becomes_failed_verification(temp_git_worktree, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    worktree, base_sha = temp_git_worktree
    
    # Mutate worktree
    new_file = os.path.join(worktree, "code.py")
    with open(new_file, "w") as f:
        f.write("print(1)\n")
    
    task_text = "Implement code.py with tests"
    task_digest = hashlib.sha256(task_text.encode("utf-8")).hexdigest()
    
    job_id = "job-test-verify-fail"
    log_dir = tmp_path / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{job_id}.log"
    exit_file = log_dir / f"{job_id}.log.exit"
    log_file.write_text(f"SYNLYNK_TASK_RECEIVED: {task_digest}\nCreated code.py")
    exit_file.write_text("0")
    
    job = {
        "id": job_id,
        "agent": "agy",
        "task": task_text,
        "status": "running",
        "pid": 99999999,
        "worktree_path": worktree,
        "worktree_branch": "feat/foo",
        "base_sha": base_sha,
        "verification_cmd": "python3 -c 'import sys; sys.exit(1)'",
        "log_file": str(log_file),
        "started_at": "2026-09-27T12:00:00",
        "ended_at": None,
        "exit_code": None,
    }
    synlynk._save_jobs([job])
    
    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    synlynk._reconcile_jobs()
    
    reconciled = synlynk._load_jobs()
    assert reconciled[0]["status"] == STATUS_FAILED_VERIFICATION
