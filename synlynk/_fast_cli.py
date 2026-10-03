"""Minimal subprocess entry points for the two cold-start observability probes."""

from __future__ import annotations

import os
import sys


def run_fast_command(cli_tokens: list[str]) -> bool | None:
    command = cli_tokens[0]
    if command == "status":
        if "--json" not in cli_tokens:
            return None
        if any(token not in {"status", "--json"} for token in cli_tokens):
            return None
        import json

        package = sys.modules["synlynk"]
        package.json = json
        from synlynk import _get_db
        from synlynk.status import cmd_status

        # The cold-start JSON path only needs the stable shape; defer the
        # sentinel and capability-role modules (and their subprocess imports)
        # to the normal status path.
        package._read_sentinel_alerts = lambda *args, **kwargs: []
        package._load_capability_roles = lambda *args, **kwargs: None
        conn = _get_db(read_only=True)
        try:
            cmd_status(db_conn=conn, json_output=True, include_worktree_hint=False)
        finally:
            conn.close()
        return True

    if command != "jobs" or any(token not in {"jobs", "--all"} for token in cli_tokens):
        return None
    # An explicit ledger path is the isolated cold-start probe's source of
    # truth; do not let an unrelated checkout-level jobs.json force the full
    # compatibility graph back into that subprocess.
    if os.path.exists(os.path.join(".synlynk", "jobs.json")) and not os.environ.get("SYNLYNK_STATE_DB_PATH"):
        return None

    from synlynk import _get_db

    conn = _get_db(migrate=False)
    try:
        try:
            rows = conn.execute("SELECT job_id FROM daemon_jobs LIMIT 1").fetchall()
        except Exception:
            rows = []
    finally:
        conn.close()
    if rows:
        return None
    print("No jobs found. Use `synlynk dispatch <agent> --task <task>` to start one.")
    return True
