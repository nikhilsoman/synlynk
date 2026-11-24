"""Models for worktree-lease."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LeaseInfo:
    worktree_path: str
    branch: str
    lease_holder: str
    acquired_at: str
    ttl_seconds: int
    pid: int
    lock_file: str
