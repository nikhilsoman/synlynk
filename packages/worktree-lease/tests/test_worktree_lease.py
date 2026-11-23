"""Tests for worktree-lease modularity and atomic concurrency."""

import ast
import os
import tempfile
import pytest
from worktree_lease.manager import WorktreeLeaseManager, WorktreeLeaseError


def test_modularity_zero_synlynk_imports():
    """Verify that packages/worktree-lease/src contains ZERO imports of synlynk."""
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as pyfile:
                    tree = ast.parse(pyfile.read(), filename=fpath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert not alias.name.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {alias.name}"
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                assert not node.module.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {node.module}"


def test_worktree_lease_locking():
    """Verify lock file contention prevents duplicate acquisition."""
    with tempfile.TemporaryDirectory() as temp_repo:
        mgr = WorktreeLeaseManager(repo_root=temp_repo)
        
        # Manually hold lock file to simulate open lease
        lock_path = mgr._get_lock_path("test-worker")
        import fcntl
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)

        try:
            with pytest.raises(WorktreeLeaseError, match="locked by another process"):
                mgr.acquire("test-worker")
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def test_worktree_lease_prune_stale():
    """Verify pruning stale lease when PID is dead."""
    with tempfile.TemporaryDirectory() as temp_repo:
        mgr = WorktreeLeaseManager(repo_root=temp_repo)
        
        # Write a dummy lease with an impossible PID (e.g., 99999999)
        lock_path = mgr._get_lock_path("stale-worker")
        lease_data = {
            "worktree_path": os.path.join(mgr.base_dir, "stale-worker"),
            "branch": "feat/stale",
            "lease_holder": "dead-agent",
            "acquired_at": "2026-11-20T00:00:00Z",
            "ttl_seconds": 300,
            "pid": 99999999,
            "lock_file": lock_path,
        }
        import json
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(lease_data, f)

        # Dry run should report stale-worker
        stale = mgr.prune(dry_run=True)
        assert "stale-worker" in stale
        assert os.path.exists(lock_path)

        # Real prune should remove it
        stale_real = mgr.prune(dry_run=False)
        assert "stale-worker" in stale_real
        assert not os.path.exists(lock_path)
