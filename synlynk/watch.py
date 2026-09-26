"""Background workspace watcher and AST extraction drift monitor (#1787)."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional


def _get_head_commit(repo_root: str) -> Optional[str]:
    """Return current git HEAD commit SHA or None."""
    try:
        res = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def check_and_refresh_ast_on_drift(repo_root: str) -> bool:
    """Check if workspace git HEAD has drifted from AST graph manifest and refresh if needed."""
    head_sha = _get_head_commit(repo_root)
    if not head_sha:
        return False

    out_dir = os.path.join(repo_root, ".synlynk", "graphify-out")
    manifest_path = os.path.join(out_dir, "manifest.json")

    built_at = None
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                built_at = data.get("built_at_commit") or data.get("built_at")
        except Exception:
            built_at = None

    if built_at and built_at == head_sha:
        return False

    # Drift detected or missing manifest -> trigger extraction
    try:
        from synlynk.scan import _run_graphify_extract
        ok = _run_graphify_extract(repo_root)
        if ok:
            try:
                from synlynk.viz import _write_cache
                _write_cache(repo_root)
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False
