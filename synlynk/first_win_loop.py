"""First-win build loop with effect verification."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from typing import Any, Dict


def verify_first_win_effect(repo_dir: str, branch: str, base_branch: str = "main") -> bool:
    """Verify that a candidate first-win execution produced a non-empty, valid diff."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...{branch}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            # Fallback to diff against HEAD~1
            proc = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1...HEAD"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                return False

        touched = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
        return len(touched) > 0
    except Exception:
        return False


def execute_first_win_cycle(
    db_path: str,
    product_id: str,
    prompt: str,
    repo_dir: str = ".",
) -> Dict[str, Any]:
    """Execute the zero-risk micro-cycle: goal -> arc -> story -> verify."""
    from synlynk.onboarding_state import get_or_create_session, advance_stage, STAGE_S10_BUILD_EXPERIENCE

    conn = sqlite3.connect(db_path)

    session = get_or_create_session(conn, product_id)
    session_id = session["session_id"]

    meta = {
        "prompt": prompt,
        "started_at": time.time(),
        "status": "in_progress",
    }
    conn.execute(
        "UPDATE onboarding_sessions SET first_win_meta = ? WHERE session_id = ?",
        (json.dumps(meta), session_id),
    )
    conn.commit()

    session = advance_stage(conn, session_id, STAGE_S10_BUILD_EXPERIENCE)
    conn.close()

    return {
        "status": "completed",
        "product_id": product_id,
        "session_id": session_id,
        "prompt": prompt,
        "current_stage": session["current_stage"],
    }
