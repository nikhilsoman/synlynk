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
    )

    conn = _get_db()
    try:
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
                        _estimate_story_cost_usd(g[2], est_tokens),
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

    from synlynk import _get_db

    conn = _get_db()
    job_ids = []
    try:
        for item in plan:
            story_id = item["story_id"]
            agent = item["agent"]
            task = f"Implement {story_id}: {item.get('title') or story_id}"
            job_id = "djob-" + hashlib.md5(
                f"{agent}{task}{time.time()}".encode()
            ).hexdigest()[:8]
            conn.execute(
                "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, "
                "priority, depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?,?)",
                (job_id, agent, task, story_id, "queued",
                 item.get("priority", 5), "[]",
                 time.strftime("%Y-%m-%dT%H:%M:%S")),
            )
            job_ids.append(job_id)
        conn.commit()
    finally:
        conn.close()
    return job_ids
