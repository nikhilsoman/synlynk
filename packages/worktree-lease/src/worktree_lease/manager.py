"""Core atomic worktree lease manager using OS-level file locks."""

import fcntl
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from worktree_lease.models import LeaseInfo


class WorktreeLeaseError(Exception):
    pass


class WorktreeLeaseManager:
    """Manages isolated git worktrees with flock-guarded concurrency leases."""

    def __init__(self, repo_root: str, base_dir: Optional[str] = None):
        self.repo_root = os.path.abspath(repo_root)
        self.base_dir = os.path.abspath(base_dir) if base_dir else os.path.join(self.repo_root, ".worktrees")
        self.lock_dir = os.path.join(self.base_dir, ".locks")
        os.makedirs(self.lock_dir, exist_ok=True)

    def _get_lock_path(self, name: str) -> str:
        return os.path.join(self.lock_dir, f"{name}.lease.json")

    def acquire(
        self,
        name: str,
        branch: Optional[str] = None,
        detached: bool = False,
        commit: str = "HEAD",
        ttl_seconds: int = 3600,
        holder: str = "agent",
    ) -> LeaseInfo:
        """Acquire a worktree lease atomically. Creates git worktree if not exists."""
        wt_path = os.path.join(self.base_dir, name)
        lock_path = self._get_lock_path(name)

        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            os.close(fd)
            raise WorktreeLeaseError(f"Worktree '{name}' is locked by another process.")

        # Check existing metadata if any
        now_iso = datetime.now(timezone.utc).isoformat()
        current_pid = os.getpid()

        lease = LeaseInfo(
            worktree_path=wt_path,
            branch=branch or ("(detached)" if detached else name),
            lease_holder=holder,
            acquired_at=now_iso,
            ttl_seconds=ttl_seconds,
            pid=current_pid,
            lock_file=lock_path,
        )

        # Write metadata into lock file
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, json.dumps(lease.__dict__, indent=2).encode("utf-8"))

        # Create git worktree if missing
        if not os.path.exists(wt_path):
            cmd = ["git", "-C", self.repo_root, "worktree", "add"]
            if detached:
                cmd.extend(["--detach", wt_path, commit])
            else:
                target_branch = branch or name
                cmd.extend(["-b", target_branch, wt_path, commit])
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                # Cleanup lock on failure
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
                raise WorktreeLeaseError(f"Failed to create git worktree: {res.stderr}")

        # Note: In standard usage, callers hold the open fd or lease file
        return lease

    def release(self, name: str, remove_worktree: bool = False) -> None:
        """Release lease lock and optionally remove the worktree."""
        lock_path = self._get_lock_path(name)
        wt_path = os.path.join(self.base_dir, name)

        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass

        if remove_worktree and os.path.exists(wt_path):
            subprocess.run(
                ["git", "-C", self.repo_root, "worktree", "remove", "--force", wt_path],
                capture_output=True,
                text=True,
            )

    def list_leases(self) -> List[LeaseInfo]:
        """List all active leases."""
        leases = []
        if not os.path.exists(self.lock_dir):
            return leases

        for f in os.listdir(self.lock_dir):
            if f.endswith(".lease.json"):
                path = os.path.join(self.lock_dir, f)
                try:
                    with open(path, "r", encoding="utf-8") as lf:
                        data = json.load(lf)
                        leases.append(LeaseInfo(**data))
                except Exception:
                    continue
        return leases

    def prune(self, dry_run: bool = False) -> List[str]:
        """Prune stale leases where the holding PID is no longer alive."""
        pruned = []
        for lease in self.list_leases():
            pid_alive = False
            try:
                os.kill(lease.pid, 0)
                pid_alive = True
            except OSError:
                pid_alive = False

            if not pid_alive:
                name = os.path.basename(lease.worktree_path)
                pruned.append(name)
                if not dry_run:
                    self.release(name, remove_worktree=True)
        return pruned
