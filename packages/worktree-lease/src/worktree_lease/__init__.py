"""worktree-lease: Atomic Git Worktree Concurrency & Lease Manager."""

from worktree_lease.models import LeaseInfo
from worktree_lease.manager import WorktreeLeaseManager, WorktreeLeaseError

__version__ = "0.1.0"
__all__ = ["LeaseInfo", "WorktreeLeaseManager", "WorktreeLeaseError"]
