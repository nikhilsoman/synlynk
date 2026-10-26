"""Batch fleet dispatch scheduler.

Assigns ready stories to agents using the existing capability -> quota -> cost
routing helpers in synlynk/__init__.py, with fleet-level in-batch headroom
accounting layered on top (single-story routing has no notion of "already
spent this token budget on story A three rows up in the same run").

Uses deferred/local imports from synlynk (not the dispatch.py _pkg() helper)
because this module is imported into synlynk/cli.py directly, not re-exported
through synlynk/__init__.py at module-load time -- no import cycle to avoid.
"""

import json
import os
import traceback

from synlynk.backlog import auto_promote_backlog, ingest_backlog, triage_backlog

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
            "s.phase, s.priority, s.estimated_tokens, s.goal_id FROM stories s "
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
             est_tokens, goal_id) in stories:
            if not goal_id:
                blocked.append({"story_id": story_id, "reason": "no_goal_link"})
                continue

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
            estimated_tokens = item.get("estimated_tokens")
            if estimated_tokens is not None and int(estimated_tokens) > 0:
                _open_reservation(
                    conn, agent, int(estimated_tokens),
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


def _autonomy_pass_interval_seconds() -> int:
    """Seconds between unforced _autonomy_pass() runs.

    Reads .synlynk/config.json directly (not load_config()) for the same
    reason synlynk/autonomy.py's get_autonomy_mode() does: this key is a
    small daemon-loop tuning knob, not part of the workspace/billing split
    config load_config() composes.
    """
    path = os.path.join(os.getcwd(), ".synlynk", "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return int(data.get("autonomy_pass_interval_seconds", 1800))
        except (json.JSONDecodeError, ValueError, OSError):
            return 1800
    return 1800


def _run_maintainer_triage_pass() -> None:
    try:
        from synlynk.maintainer import triage_sentinel_alerts
        triage_sentinel_alerts(max_age_days=7)
    except Exception:
        pass


def _autonomy_pass(conn=None) -> None:
    """Backlog bookkeeping (always) + capability-aware scheduling (mode-gated).

    Each stage runs independently: a failure in one stage is logged and does
    not prevent the remaining stages from running. Never raises -- callers
    (the daemon poll loop) must be able to call this every tick without a
    try/except of their own.

    See docs/superpowers/specs/2026-10-13-autonomous-backlog-scheduling-design.md
    """
    from synlynk.autonomy import AutonomyMode, get_autonomy_mode

    for stage_name, stage_fn in (
        ("ingest_backlog", lambda: ingest_backlog(db_conn=conn)),
        ("triage_backlog", lambda: triage_backlog(db_conn=conn)),
        ("auto_promote_backlog", lambda: auto_promote_backlog(db_conn=conn)),
        ("maintainer_triage", lambda: _run_maintainer_triage_pass()),
    ):
        try:
            stage_fn()
        except Exception:
            print(f"  ⚠ _autonomy_pass: {stage_name} failed:")
            traceback.print_exc()

    try:
        mode = get_autonomy_mode()
    except Exception:
        print("  ⚠ _autonomy_pass: get_autonomy_mode failed, defaulting to MANUAL (no scheduling this pass):")
        traceback.print_exc()
        return

    if mode == AutonomyMode.MANUAL:
        return

    try:
        cmd_schedule(execute=True)
    except Exception:
        print("  ⚠ _autonomy_pass: cmd_schedule failed:")
        traceback.print_exc()
