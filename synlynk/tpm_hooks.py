"""TPM workspace-agent hook stubs.

Not a TPM agent implementation -- the stable, independently-testable surface
a future role='tpm' dispatch calls to observe/reorder/reallocate the dispatch
reservation ledger, instead of touching harness_reservations / daemon_jobs
directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


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


def tpm_reconcile_slipping_deadline(
    *,
    milestone: str,
    days_to_deadline: float,
    remaining_work_days: float,
    blocked_dependencies: List[Dict[str, Any]],
    parallel_capacity: float = 1.0,
) -> Dict[str, Any]:
    """Reconcile a slipping deadline against blocked dependencies (TPM advanced).

    Pure planning helper: no DB writes. Takes a milestone with remaining work,
    calendar runway, and the currently blocked deps, then returns a structured
    reconciliation — status, slip estimate, ranked options, and a recommended
    action plan.

    ``blocked_dependencies`` entries accept:
      id, title, unblock_days (required), owner, can_bypass (bool),
      bypass_cost_days (float), severity ('high'|'medium'|'low').
    """
    if days_to_deadline < 0:
        raise ValueError("days_to_deadline must be >= 0")
    if remaining_work_days < 0:
        raise ValueError("remaining_work_days must be >= 0")
    if parallel_capacity <= 0:
        raise ValueError("parallel_capacity must be > 0")
    if not isinstance(blocked_dependencies, list) or len(blocked_dependencies) < 1:
        raise ValueError("blocked_dependencies must contain at least one entry")

    deps: List[Dict[str, Any]] = []
    for raw in blocked_dependencies:
        if "unblock_days" not in raw:
            raise ValueError(f"dependency {raw.get('id')!r} missing unblock_days")
        unblock = float(raw["unblock_days"])
        if unblock < 0:
            raise ValueError(f"dependency {raw.get('id')!r} unblock_days must be >= 0")
        deps.append(
            {
                "id": str(raw.get("id") or raw.get("title") or "dep"),
                "title": str(raw.get("title") or raw.get("id") or "dependency"),
                "unblock_days": unblock,
                "owner": raw.get("owner"),
                "can_bypass": bool(raw.get("can_bypass", False)),
                "bypass_cost_days": float(raw.get("bypass_cost_days") or 0.0),
                "severity": str(raw.get("severity") or "medium").lower(),
            }
        )

    # Critical path: longest unblock gate, then residual work under capacity.
    longest_block = max(d["unblock_days"] for d in deps)
    work_elapsed = remaining_work_days / parallel_capacity
    # Work cannot start on the critical path until the longest blocker clears
    # unless a bypass exists for that blocker.
    critical_deps = [d for d in deps if d["unblock_days"] == longest_block]
    projected_finish = longest_block + work_elapsed
    slip_days = max(0.0, projected_finish - days_to_deadline)

    if slip_days <= 0:
        status = "on_track"
    elif slip_days <= max(1.0, days_to_deadline * 0.15):
        status = "at_risk"
    else:
        status = "slipped"

    options: List[Dict[str, Any]] = []

    # Option A: escalate / crash the blockers in parallel.
    escalate_days = max(0.5, longest_block * 0.5)
    escalate_finish = escalate_days + work_elapsed
    escalate_slip = max(0.0, escalate_finish - days_to_deadline)
    options.append(
        {
            "id": "escalate_blockers",
            "label": "Escalate both blocked dependencies in parallel",
            "description": (
                "Daily unblock standups with owners; swap assignees if stalled; "
                "treat the longest gate as the single critical-path constraint."
            ),
            "projected_finish_days": round(escalate_finish, 2),
            "residual_slip_days": round(escalate_slip, 2),
            "requires_human_authority": False,
            "targets": [d["id"] for d in deps],
        }
    )

    # Option B: bypass one or both blockers when allowed.
    bypassable = [d for d in deps if d["can_bypass"]]
    if bypassable:
        # Bypass every bypassable dep; remaining gates still apply.
        remaining_gates = [
            0.0 if d["can_bypass"] else d["unblock_days"] for d in deps
        ]
        bypass_gate = max(remaining_gates) if remaining_gates else 0.0
        bypass_cost = sum(d["bypass_cost_days"] for d in bypassable)
        bypass_finish = bypass_gate + work_elapsed + bypass_cost
        bypass_slip = max(0.0, bypass_finish - days_to_deadline)
        options.append(
            {
                "id": "bypass_blockers",
                "label": "Ship a temporary bypass around unblockable gates",
                "description": (
                    "Accept known tech-debt / reduced scope on "
                    + ", ".join(d["id"] for d in bypassable)
                    + f" (+{bypass_cost:.1f}d rework later)."
                ),
                "projected_finish_days": round(bypass_finish, 2),
                "residual_slip_days": round(bypass_slip, 2),
                "requires_human_authority": any(
                    d["severity"] == "high" for d in bypassable
                ),
                "targets": [d["id"] for d in bypassable],
            }
        )

    # Option C: re-scope remaining work to fit the runway after gates clear.
    available_after_gate = max(0.0, days_to_deadline - longest_block)
    capacity_after_gate = available_after_gate * parallel_capacity
    cut_days = max(0.0, remaining_work_days - capacity_after_gate)
    if cut_days > 0:
        rescope_finish = longest_block + (remaining_work_days - cut_days) / parallel_capacity
        options.append(
            {
                "id": "rescope_work",
                "label": "Cut scope so remaining work fits post-unblock runway",
                "description": (
                    f"Defer or drop ~{cut_days:.1f}d of non-critical work so the "
                    "milestone still lands on the original date."
                ),
                "projected_finish_days": round(rescope_finish, 2),
                "residual_slip_days": 0.0,
                "requires_human_authority": True,
                "scope_cut_days": round(cut_days, 2),
                "targets": [d["id"] for d in critical_deps],
            }
        )

    # Option D: extend the deadline (always available; needs human sign-off).
    extend_by = round(slip_days, 2) if slip_days > 0 else 0.0
    options.append(
        {
            "id": "extend_deadline",
            "label": "Move the milestone date",
            "description": (
                f"Extend deadline by {extend_by:.1f}d to absorb the longest "
                "blocked dependency plus remaining work."
                if extend_by > 0
                else "No extension needed under the current projection."
            ),
            "projected_finish_days": round(projected_finish, 2),
            "residual_slip_days": 0.0 if extend_by > 0 else round(slip_days, 2),
            "requires_human_authority": True,
            "extend_by_days": extend_by,
            "targets": [d["id"] for d in critical_deps],
        }
    )

    # Prefer the option that clears slip without human authority when possible;
    # otherwise the lowest residual slip among authority-gated options.
    def _rank_key(opt: Dict[str, Any]) -> tuple:
        return (
            0 if opt["residual_slip_days"] <= 0 else 1,
            0 if not opt["requires_human_authority"] else 1,
            opt["residual_slip_days"],
            opt["projected_finish_days"],
        )

    ranked = sorted(options, key=_rank_key)
    recommended = ranked[0]

    action_plan = [
        {
            "step": 1,
            "action": "freeze_scope",
            "detail": (
                f"Freeze new scope on '{milestone}'. Treat the two blocked "
                "dependencies as the only gates that may move the date."
            ),
        },
        {
            "step": 2,
            "action": "attack_critical_path",
            "detail": (
                "Unblock "
                + ", ".join(d["id"] for d in critical_deps)
                + f" first (longest gate = {longest_block:.1f}d). Run the second "
                "blocker in parallel so it is not a serial surprise."
            ),
        },
        {
            "step": 3,
            "action": "execute_recommendation",
            "detail": f"{recommended['id']}: {recommended['description']}",
        },
        {
            "step": 4,
            "action": "reforecast_daily",
            "detail": (
                "Recompute slip each day from live unblock_days. Escalate to "
                "human_authority_role only if residual_slip stays > 0 after "
                "non-authority options are exhausted."
            ),
        },
    ]

    narrative = (
        f"Milestone '{milestone}' has {days_to_deadline:.1f}d of runway against "
        f"{remaining_work_days:.1f}d remaining work (capacity {parallel_capacity:.1f}x). "
        f"Two blocked dependencies gate the critical path; the longest unblock is "
        f"{longest_block:.1f}d, projecting finish at {projected_finish:.1f}d "
        f"({status}, slip {slip_days:.1f}d). Recommended: {recommended['id']} — "
        f"{recommended['description']}"
    )

    return {
        "milestone": milestone,
        "status": status,
        "days_to_deadline": float(days_to_deadline),
        "remaining_work_days": float(remaining_work_days),
        "parallel_capacity": float(parallel_capacity),
        "longest_block_days": float(longest_block),
        "projected_finish_days": round(projected_finish, 2),
        "slip_days": round(slip_days, 2),
        "blocked_dependencies": deps,
        "critical_path_dependency_ids": [d["id"] for d in critical_deps],
        "options": ranked,
        "recommended": recommended,
        "action_plan": action_plan,
        "narrative": narrative,
    }
