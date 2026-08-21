"""qa delegated merge-gate authority (block-only mode).

Computes a fail-closed gate verdict from two signals: CI matrix status and
open Support-Engineer-filed sentinel-alert issues.
See docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md.
"""

import json
import subprocess
from typing import Optional

from synlynk.sentinel import _extract_verified_by_ci
from synlynk import detect_remote_owner_repo


def _qa_gate_ci_status(worktree_path=None, worktree_branch=None) -> Optional[bool]:
    """True/False/None (undeterminable) CI matrix status for the active branch."""
    return _extract_verified_by_ci(
        worktree_path=worktree_path, worktree_branch=worktree_branch
    )
