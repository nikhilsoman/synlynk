"""TPM workspace-agent hook stubs.

Not a TPM agent implementation -- the stable, independently-testable surface
a future role='tpm' dispatch calls to observe/reorder/reallocate the dispatch
reservation ledger, instead of touching harness_reservations / daemon_jobs
directly.
"""


def tpm_observe_reservations(conn, scope: str = None, scope_id: str = None) -> list:
    """Read open reservations plus live headroom, optionally scope-filtered."""
    from synlynk import _quota_status_for_agent

    query = (
        "SELECT id, harness, tokens, scope, scope_id, job_id, created_at "
        "FROM harness_reservations WHERE status='open'"
    )
    params = []
    if scope:
        query += " AND scope=?"
        params.append(scope)
    if scope_id:
        query += " AND scope_id=?"
        params.append(scope_id)
    query += " ORDER BY created_at ASC"

    rows = conn.execute(query, params).fetchall()
    result = []
    seen_headroom = {}
    for rid, harness, tokens, res_scope, res_scope_id, job_id, created_at in rows:
        if harness not in seen_headroom:
            status = _quota_status_for_agent(conn, harness)
            seen_headroom[harness] = status.get("headroom")
        result.append({
            "id": rid,
            "harness": harness,
            "tokens": tokens,
            "scope": res_scope,
            "scope_id": res_scope_id,
            "job_id": job_id,
            "created_at": created_at,
            "current_headroom": seen_headroom[harness],
        })
    return result


def tpm_reorder_queue(conn, priorities: dict) -> int:
    """Bulk-update queued daemon job priorities and return changed rows."""
    changed = 0
    for job_id, new_priority in priorities.items():
        cur = conn.execute(
            "UPDATE daemon_jobs SET priority=? WHERE job_id=? AND status='queued'",
            (int(new_priority), job_id),
        )
        changed += cur.rowcount
    conn.commit()
    return changed


def tpm_reallocate(conn, job_id: str, new_harness: str) -> dict:
    """Move a queued job and its open reservation to another harness."""
    from synlynk import _open_reservation, _release_reservation

    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No such job_id: {job_id!r}")
    if row[0] != "queued":
        raise ValueError(
            f"Cannot reallocate job_id={job_id!r}: status is {row[0]!r}, not 'queued'"
        )

    res_row = conn.execute(
        "SELECT id, tokens, scope, scope_id FROM harness_reservations "
        "WHERE job_id=? AND status='open'",
        (job_id,),
    ).fetchone()

    conn.execute(
        "UPDATE daemon_jobs SET agent=? WHERE job_id=?", (new_harness, job_id)
    )

    new_reservation_id = None
    if res_row:
        old_id, tokens, scope, scope_id = res_row
        _release_reservation(conn, old_id)
        new_reservation_id = _open_reservation(
            conn, new_harness, tokens, scope=scope, scope_id=scope_id, job_id=job_id
        )
    conn.commit()

    return {
        "job_id": job_id,
        "new_harness": new_harness,
        "new_reservation_id": new_reservation_id,
    }
