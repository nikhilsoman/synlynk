"""GitHub-native sync for roadmap/story/decision rows (gh:#2653 design).

Renders already-authoritative state.db rows onto GitHub Milestones/Issues
(Pattern A: core primitives only, no Projects v2 custom fields -- see the
design spec's "Why Pattern A, not Pattern B" section). github_sync_map is
a cache of GitHub-side facts, never a second source of truth.
"""

import hashlib
import json

from synlynk.gh_shim import run_gh


def _content_hash(fields: dict) -> str:
    """Stable hash of the fields that determine a synced item's rendered content."""
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gh_api_json(args: list, role: str = "pm", **kwargs):
    """Run ``gh api <args>`` and parse JSON stdout. Raises RuntimeError on failure."""
    result = run_gh(["api"] + args, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"gh api {args} failed: {result.stderr.strip()}")
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)
