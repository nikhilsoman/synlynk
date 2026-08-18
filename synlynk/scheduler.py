"""Batch fleet dispatch scheduler.

Assigns ready stories to agents using the existing capability -> quota -> cost
routing helpers in synlynk/__init__.py, with fleet-level in-batch headroom
accounting layered on top (single-story routing has no notion of "already
spent this token budget on story A three rows up in the same run").

Uses deferred/local imports from synlynk (not the dispatch.py _pkg() helper)
because this module is imported into synlynk/cli.py directly, not re-exported
through synlynk/__init__.py at module-load time -- no import cycle to avoid.
"""

MAX_STORY_RETRIES = 2


def _story_failed_agents(conn, story_id: str) -> set:
    """Agents that have a 'failed' daemon_jobs row for this story."""
    rows = conn.execute(
        "SELECT DISTINCT agent FROM daemon_jobs WHERE story_id=? AND status='failed'",
        (story_id,),
    ).fetchall()
    return {r[0] for r in rows}


def _story_retry_count(conn, story_id: str) -> int:
    """Number of failed daemon_jobs attempts recorded for this story."""
    row = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE story_id=? AND status='failed'",
        (story_id,),
    ).fetchone()
    return row[0] if row else 0


def _compute_schedule_plan(max_stories=None) -> dict:
    """Batch version of synlynk.__init__._best_agent_for_story.

    Reuses the existing capability -> quota -> cost routing helpers but adds
    fleet-level in-batch headroom accounting: as stories are assigned within
    this one run, each agent's remaining headroom is decremented in-memory so
    story 2 in the batch sees story 1's spend before it gets routed.

    Returns {"plan": [...], "blocked": [...]}. Never writes to the database
    (dry-run by construction) -- writing is _enqueue_plan()'s job.
    """
    from synlynk import (
        _CAPABILITY_COST_TIE_GAP,
        _capability_candidates_for_story,
        _estimate_story_cost_usd,
        _get_db,
        _quota_status_for_agent,
        _refresh_agent_quotas_from_telemetry,
    )

    conn = _get_db()
    try:
        # #291: populate harness_quotas from telemetry before fleet stage-2 gate
        try:
            _refresh_agent_quotas_from_telemetry(conn=conn)
        except Exception:
            pass

        query = (
            "SELECT s.story_id, s.title, s.engg_domain, s.org_domain, s.industry, "
            "s.phase, s.priority, s.estimated_tokens FROM stories s "
            "WHERE s.readiness='ready' AND NOT EXISTS ("
            "  SELECT 1 FROM daemon_jobs dj WHERE dj.story_id=s.story_id "
            "  AND dj.status IN ('queued','running')"
            ") ORDER BY s.priority ASC, s.created_at ASC"
        )
        if max_stories:
            query += f" LIMIT {int(max_stories)}"
        stories = conn.execute(query).fetchall()

        plan = []
        blocked = []
        headroom_cache = {}  # agent -> int | None (None = degraded/unknown)

        for (story_id, title, engg, org, industry, phase, priority,
             est_tokens) in stories:
            if _story_retry_count(conn, story_id) >= MAX_STORY_RETRIES:
                blocked.append({"story_id": story_id, "reason": "retry_cap_exceeded"})
                continue

            candidates = _capability_candidates_for_story(conn, engg, org, industry, phase)
            if not candidates:
                blocked.append({"story_id": story_id, "reason": "no_capability_candidates"})
                continue

            excluded = _story_failed_agents(conn, story_id)
            usable = [c for c in candidates if c[0] not in excluded]
            if not usable:
                usable = candidates  # sole-candidate exception: keep it eligible

            gated = []  # (agent, score, model, headroom)
            for agent, score, model in usable:
                if agent not in headroom_cache:
                    qstatus = _quota_status_for_agent(conn, agent, estimated_tokens=est_tokens)
                    # Fleet in-batch accounting is token-denominated. Non-token
                    # headroom (e.g. project request budget) and degraded/unknown
                    # signals stay non-hard-blocking for token compares — matching
                    # _best_agent_for_story's degraded-mode policy. Hard-exhausted
                    # non-token status still blocks the agent for the batch.
                    if qstatus["degraded"] or qstatus.get("unit") != "tokens":
                        if qstatus["status"] == "exhausted" and not qstatus["degraded"]:
                            headroom_cache[agent] = 0
                        else:
                            headroom_cache[agent] = None
                    else:
                        headroom_cache[agent] = qstatus["headroom"]
                headroom = headroom_cache[agent]
                need = int(est_tokens or 0)
                if headroom is not None and need > 0 and headroom < need:
                    continue  # real gate: exhausted this batch
                gated.append((agent, score, model, headroom))

            if not gated:
                blocked.append({"story_id": story_id, "reason": "quota_exhausted"})
                continue

            top_score = gated[0][1]
            near = [g for g in gated if (top_score - g[1]) <= _CAPABILITY_COST_TIE_GAP]
            if len(near) == 1:
                chosen = near[0]
            else:
                chosen = min(
                    near,
                    key=lambda g: (
                        _estimate_story_cost_usd(g[2], est_tokens, agent=g[0]),
                        -g[1],
                        g[0],
                    ),
                )

            agent, score, model, headroom = chosen
            need = int(est_tokens or 0)
            if headroom is not None:
                headroom_cache[agent] = headroom - need

            plan.append({
                "story_id": story_id,
                "title": title,
                "agent": agent,
                "score": score,
                "model": model,
                "priority": priority,
                "estimated_tokens": est_tokens,
                "headroom_before": headroom,
                "headroom_after": headroom_cache[agent],
            })

        return {"plan": plan, "blocked": blocked}
    finally:
        conn.close()


def _enqueue_plan(plan: list) -> list:
    """Writes each plan assignment as a 'queued' daemon_jobs row.

    Mirrors the INSERT shape used by the HTTP dispatch relay in
    synlynk/__init__.py's _handle_dispatch (job_id = 'djob-' + md5(...)).
    Does not launch anything -- callers pass the resulting job_ids (or just
    call _dispatch_ready_jobs()) to actually start work.
    """
    import hashlib
    import time

    from synlynk import _get_db, _open_reservation

    conn = _get_db()
    job_ids = []
    run_id = "sched-" + hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    try:
        for item in plan:
            story_id = item["story_id"]
            agent = item["agent"]
            task = f"Implement {story_id}: {item.get('title') or story_id}"
            job_id = "djob-" + hashlib.md5(
                f"{agent}{task}{time.time()}".encode()
            ).hexdigest()[:8]
            # Batch scheduling runs without an interactive operator.
            dispatch_context = "headless"
            conn.execute(
                "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                "priority, depends_on, enqueued_at, dispatch_context) VALUES (?,?,?,?,?,?,?,?,?)",
                (job_id, agent, task, story_id, "queued",
                 item.get("priority", 5), "[]",
                 time.strftime("%Y-%m-%dT%H:%M:%S"), dispatch_context),
            )
            _open_reservation(
                conn, agent, int(item.get("estimated_tokens") or 0),
                scope="plan", scope_id=run_id, job_id=job_id,
            )
            job_ids.append(job_id)
        conn.commit()
    finally:
        conn.close()
    return job_ids


def cmd_schedule(execute: bool = False, max_stories=None) -> None:
    """Prints the batch schedule plan; with execute=True, enqueues it into
    daemon_jobs and triggers one _dispatch_ready_jobs() pass."""
    from synlynk import _GREEN, _RESET, _dispatch_ready_jobs

    result = _compute_schedule_plan(max_stories=max_stories)
    plan = result["plan"]
    blocked = result["blocked"]

    if not plan and not blocked:
        print("  No ready stories to schedule. Use: synlynk story ready <story_id>")
        return

    if plan:
        print(f"\n  {'Story':<20} {'Agent':<10} {'Score':>6} {'Model':<14} {'Headroom':>10}")
        print("  " + "-" * 70)
        for p in plan:
            headroom = "unknown" if p["headroom_after"] is None else f"{p['headroom_after']:,}"
            print(
                f"  {p['story_id']:<20} {p['agent']:<10} {p['score']:>6.2f} "
                f"{p['model']:<14} {headroom:>10}"
            )

    if blocked:
        print(f"\n  Blocked ({len(blocked)}):")
        for b in blocked:
            print(f"    {b['story_id']:<20} {b['reason']}")

    if not execute:
        print(f"\n  Dry run — {len(plan)} would be scheduled. Re-run with --execute to dispatch.")
        return

    from synlynk.scheduler import _enqueue_plan
    job_ids = _enqueue_plan(plan)
    launched = _dispatch_ready_jobs()
    print(f"\n  {_GREEN}✓{_RESET} Enqueued {len(job_ids)} job(s), launched {launched}")
