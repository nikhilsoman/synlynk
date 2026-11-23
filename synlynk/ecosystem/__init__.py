"""Synlynk Ecosystem Bridge Facade.

Bridges Synlynk Core to the standalone developer tooling suite in packages/:
- tokenprice (Model Pricing & Valuation Engine)
- tokentrail (Universal Session & Gateway Transcript Extractor)
- worktree-lease (Atomic Git Worktree Concurrency & Lease Manager)
- harness-spec (Universal Agent CLI Discovery & Sandboxing Protocol)
- token-breaker (In-Flight Token & Spend Circuit Breaker)
"""

import os
import sys

# Ensure local monorepo packages/ are importable if not installed as system packages
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_PACKAGES_DIR = os.path.join(_REPO_ROOT, "packages")

if os.path.isdir(_PACKAGES_DIR):
    for pkg in ["tokenprice", "tokentrail", "worktree-lease", "harness-spec", "token-breaker"]:
        pkg_src = os.path.join(_PACKAGES_DIR, pkg, "src")
        if os.path.isdir(pkg_src) and pkg_src not in sys.path:
            sys.path.insert(0, pkg_src)

# Re-export key interfaces from standalone suite
try:
    import tokenprice
except ImportError:
    tokenprice = None  # type: ignore

try:
    import tokentrail
except ImportError:
    tokentrail = None  # type: ignore

try:
    import worktree_lease
except ImportError:
    worktree_lease = None  # type: ignore

try:
    import harness_spec
except ImportError:
    harness_spec = None  # type: ignore

try:
    import token_breaker
except ImportError:
    token_breaker = None  # type: ignore


__all__ = [
    "tokenprice",
    "tokentrail",
    "worktree_lease",
    "harness_spec",
    "token_breaker",
]
