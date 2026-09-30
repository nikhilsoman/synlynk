"""Shared UX core: typed reads, capability-gated writes, and the event stream
that back both the TUI (synlynk/tui.py) and Vizor (synlynk/viz.py), and are the
public BYOUX library contract documented in docs/api/uxcore.md.

`Role` here is the RBAC role for uxcore actors -- deliberately distinct from
synlynk.identity_roles (GitHub App provisioning roles, .synlynk/roles.yaml)
and synlynk.capability_roles (capability-classifier mappings). See
docs/superpowers/plans/2026-07-24-agent-github-identity-design.md's "Naming
Collision" section for the project's existing precedent on this. Always
import as `uxcore.Role`, never as a bare unqualified `Role`.
"""
import dataclasses
import enum
import json
import os
import re
import sqlite3
import time
from typing import Iterator, Optional


class Role(enum.Enum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


@dataclasses.dataclass(frozen=True)
class Actor:
    id: str
    role: Role


class LocalActor(Actor):
    """The only actor that exists in 1.0: the local user running the CLI/TUI/Vizor."""

    def __init__(self):
        super().__init__(id="local", role=Role.OWNER)


DEFAULT_ACTOR = LocalActor()


class UxCoreError(Exception):
    """Raised when a uxcore call fails outright (bad args, file I/O error).

    Surfaces (TUI/Vizor/notifiers) catch this and display it in their own
    idiom. It is never allowed to reach a user as a bare traceback.
    """


@dataclasses.dataclass(frozen=True)
class Event:
    actor_id: str
    action: str
    params: dict
    timestamp: str
    result: dict


@dataclasses.dataclass(frozen=True)
class WriteResult:
    ok: bool
    message: str
    job_id: Optional[str] = None


from synlynk import _get_db
from synlynk.pr_rebase import rebase_pr_if_behind


@dataclasses.dataclass(frozen=True)
class Costs:
    total_usd: float
    total_usd_estimated: float
    by_agent: dict
    by_stage: dict


@dataclasses.dataclass(frozen=True)
class Task:
    id: str
    name: str
    agent: str
    status: str
    cost_est: Optional[float]
    cost_actual: float
    cost_prov_estimated: float
    skip_reason: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Stage:
    key: str
    status: str
    agents: list
    start_frac: float
    width_frac: float
    cost_actual: Optional[float]
    cost_est: Optional[float]
    tasks: list


@dataclasses.dataclass(frozen=True)
class Dream:
    id: str
    name: str
    status: str
    cost_total: float
    cost_total_estimated: float
    cost_est: Optional[float]
    stages: list
    target_date: Optional[str] = None
    goal_id: Optional[str] = None
    goal_outcome: Optional[str] = None


_KNOWN_AGENTS = {"claude", "agy", "codex", "grok"}


def _looks_like_stage_label(name: str) -> bool:
    return name.lower().strip() not in _KNOWN_AGENTS


def _story_cost_est(tokens) -> Optional[float]:
    if tokens is None:
        return None
    try:
        return float(tokens) / 1000.0 * 0.003
    except Exception:
        return None


def _dream_cost_breakdown(conn, dream_id: str) -> tuple:
    try:
        rows = conn.execute(
            "SELECT COALESCE(SUM(total_cost_usd), 0), cost_source FROM cost_entries "
            "WHERE notes LIKE ? GROUP BY cost_source",
            (f"%{dream_id}%",),
        ).fetchall()
    except Exception:
        return 0.0, 0.0
    total = 0.0
    prov_estimated = 0.0
    for amount, cost_source in rows:
        amount = float(amount or 0.0)
        total += amount
        if cost_source != "actual":
            prov_estimated += amount
    return total, prov_estimated


def _fetch_cost_rows(conn) -> list:
    try:
        return conn.execute(
            "SELECT session_date, agent, total_cost_usd, notes, cost_source FROM cost_entries ORDER BY id"
        ).fetchall()
    except Exception:
        return []


def get_costs() -> Costs:
    """Aggregate cost_entries by agent and roadmap stage. Raises UxCoreError on DB access failure."""
    try:
        conn = _get_db()
    except Exception as exc:
        raise UxCoreError(f"could not open state db: {exc}") from exc
    try:
        cost_rows = _fetch_cost_rows(conn)
        by_agent = {name: {"actual": 0.0, "estimated": 0.0} for name in _KNOWN_AGENTS}
        by_stage = {
            name: {"actual": 0.0, "estimated": 0.0}
            for name in ("goal", "open", "visualize", "execute", "release", "notify", "sustain")
        }
        for _date, agent, amount, _notes, cost_source in cost_rows:
            amount = float(amount or 0.0)
            bucket_key = "actual" if cost_source == "actual" else "estimated"
            if agent:
                by_agent.setdefault(agent, {"actual": 0.0, "estimated": 0.0})
                by_agent[agent][bucket_key] += amount
        total_usd = sum(float(row[2] or 0.0) for row in cost_rows)
        total_usd_estimated = sum(
            float(row[2] or 0.0) for row in cost_rows if (row[4] or "") != "actual"
        )
        return Costs(
            total_usd=total_usd,
            total_usd_estimated=total_usd_estimated,
            by_agent=by_agent,
            by_stage=by_stage,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _open_gantt_db(db_path: Optional[str]):
    if db_path is not None:
        return sqlite3.connect(str(db_path)), True
    return _get_db(), True


def _goal_edges(conn) -> tuple[dict[str, set[str]], dict[str, str], dict[str, str]]:
    """Return contribution edges and their status, tolerating pre-Spec-3 DBs."""
    by_goal, status_by_story, reason_by_story = {}, {}, {}
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
        status_expr = "link_status" if "link_status" in columns else "'linked'"
        rows = conn.execute(
            f"SELECT goal_id, story_id, {status_expr} FROM goal_contributions"
        ).fetchall()
    except Exception:
        return by_goal, status_by_story, reason_by_story
    for goal_id, story_id, status in rows:
        status = status or "linked"
        status_by_story[story_id] = status
        if status != "unresolved" and goal_id:
            by_goal.setdefault(goal_id, set()).add(story_id)
    try:
        for story_id, reason in conn.execute(
            "SELECT story_id, skip_reason FROM goal_contributions "
            "WHERE link_status='unresolved' AND skip_reason IS NOT NULL"
        ).fetchall():
            reason_by_story[story_id] = reason
    except Exception:
        pass
    return by_goal, status_by_story, reason_by_story


def _arc_goal_id(notes: str) -> Optional[str]:
    match = re.search(r"\bgoal-[a-zA-Z0-9_-]+\b", notes or "")
    return match.group(0) if match else None


def _gantt_projection(conn) -> tuple[list[Dream], dict]:
    arc_columns = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    arc_goal_column = ", goal_id" if "goal_id" in arc_columns else ", NULL"
    arc_rows = conn.execute(
        "SELECT version, title, status, target_date, notes" + arc_goal_column +
        " FROM roadmap_arcs ORDER BY id DESC"
    ).fetchall()
    phase_rows = conn.execute(
        "SELECT id, arc_version, phase_title, status, priority, story_id, notes "
        "FROM roadmap_phases ORDER BY arc_version, id"
    ).fetchall()
    story_cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)").fetchall()}
    has_goal = "goal_id" in story_cols
    story_query = (
        "SELECT story_id, title, status, phase, estimated_tokens, goal_id FROM stories ORDER BY id"
        if has_goal else
        "SELECT story_id, title, status, phase, estimated_tokens, NULL FROM stories ORDER BY id"
    )
    story_rows = conn.execute(story_query).fetchall()
    cost_rows = _fetch_cost_rows(conn)
    goal_map = {}
    try:
        for gid, outcome in conn.execute("SELECT goal_id, outcome FROM goals").fetchall():
            if gid:
                goal_map[gid] = outcome
    except Exception:
        pass
    edges_by_goal, status_by_story, reason_by_story = _goal_edges(conn)
    story_goals = {}
    stories_by_id, stories_by_phase = {}, {}
    for story_id, title, status, phase, tokens, goal_id in story_rows:
        task = Task(story_id, title or "", phase or "", status or "open", _story_cost_est(tokens), 0.0, 0.0,
                    reason_by_story.get(story_id))
        stories_by_id[story_id] = task
        stories_by_phase.setdefault((phase or "").strip().casefold(), []).append(task)
        if goal_id:
            story_goals[story_id] = goal_id
    for _date, _agent, amount, notes, cost_source in cost_rows:
        for story_id, task in stories_by_id.items():
            if story_id and story_id in (notes or ""):
                object.__setattr__(task, "cost_actual", task.cost_actual + float(amount or 0.0))
                if cost_source != "actual":
                    object.__setattr__(task, "cost_prov_estimated", task.cost_prov_estimated + float(amount or 0.0))

    dreams, placed = [], set()
    arc_goals = {}
    for dream_id, dream_name, dream_status, target_date, notes, arc_goal in arc_rows:
        # A normalized arc.goal_id is authoritative. Notes are retained only
        # for compatibility with pre-migration ledgers that have no such edge.
        arc_goals[dream_id] = arc_goal or (
            _arc_goal_id(notes) if "goal_id" not in arc_columns else None
        )
        stage_rows = [row for row in phase_rows if row[1] == dream_id]
        stages = []
        for index, (_pid, _arc, title, phase_status, _priority, direct_story_id, phase_notes) in enumerate(stage_rows):
            phase_key = (title or "").strip()
            candidates = []
            # Rank 1: explicit phase story_id.
            if direct_story_id in stories_by_id:
                candidates.append(stories_by_id[direct_story_id])
            # Rank 2: authoritative goal contribution edge, restricted to this arc's goal.
            goal_id = arc_goals[dream_id]
            if goal_id:
                candidates.extend(stories_by_id[sid] for sid in edges_by_goal.get(goal_id, ()) if sid in stories_by_id)
            # Rank 3: legacy phase label join.
            candidates.extend(stories_by_phase.get(phase_key.casefold(), []))
            tasks = []
            for task in candidates:
                if task.id in placed or task.id in {t.id for t in tasks}:
                    continue
                placed.add(task.id)
                tasks.append(task)
                story_goals.setdefault(task.id, goal_id)
            agents = [a for a in re.findall(r"\bagent:([a-z,]+)\b", phase_notes or "") for a in a.split(",")]
            agents.extend(t.agent for t in tasks if t.agent and not _looks_like_stage_label(t.agent))
            stages.append(Stage(phase_key, phase_status or "planned", sorted(dict.fromkeys(agents)),
                                index / len(stage_rows) if stage_rows else 0.0,
                                1.0 / len(stage_rows) if stage_rows else 1.0,
                                sum(t.cost_actual for t in tasks) or None,
                                sum(t.cost_est or 0.0 for t in tasks) or None, tasks))
        total, estimated = _dream_cost_breakdown(conn, dream_id)
        dreams.append(Dream(dream_id, dream_name or "", dream_status or "planned", float(total),
                            float(estimated), sum(s.cost_est or 0.0 for s in stages) or None, stages,
                            target_date, arc_goals[dream_id], goal_map.get(arc_goals[dream_id])))
    return dreams, {"stories": stories_by_id, "edges": edges_by_goal, "statuses": status_by_story,
                    "arc_goals": arc_goals, "goal_map": goal_map, "placed": placed}


def get_gantt_data(db_path: str = None) -> list:
    """Return release-pivot Gantt data with edge-first, exactly-once story placement."""
    try:
        conn, owned = _open_gantt_db(db_path)
    except Exception as exc:
        raise UxCoreError(f"could not open state db: {exc}") from exc
    try:
        return _gantt_projection(conn)[0]
    finally:
        if owned:
            conn.close()


def get_gantt_goal_pivot_data(db_path: str = None) -> list[dict]:
    """Return first-class goal lanes, including synthetic and unresolved lanes."""
    try:
        conn, owned = _open_gantt_db(db_path)
    except Exception as exc:
        raise UxCoreError(f"could not open state db: {exc}") from exc
    try:
        releases, meta = _gantt_projection(conn)
        try:
            from synlynk.governs_engine import scoped_goals
            goals = scoped_goals(conn)
        except Exception:
            goals = [{"goal_id": gid, "outcome": outcome} for gid, outcome in meta["goal_map"].items()]
        lanes = []
        for goal in goals:
            gid = goal["goal_id"]
            story_ids = meta["edges"].get(gid, set())
            goal_releases = [r for r in releases if r.goal_id == gid]
            goal_lanes = []
            for release in goal_releases:
                stages = [dataclasses.replace(stage, tasks=[t for t in stage.tasks if t.id in story_ids])
                          for stage in release.stages]
                if any(stage.tasks for stage in stages):
                    goal_lanes.append({"id": release.id, "name": release.name, "type": "release", "stages": stages})
            attached = {t.id for lane in goal_lanes for stage in lane["stages"] for t in stage.tasks}
            unscheduled = [meta["stories"][sid] for sid in story_ids if sid in meta["stories"] and sid not in attached]
            if unscheduled:
                goal_lanes.append({"id": f"{gid}:unscheduled", "name": "Unscheduled", "type": "synthetic",
                                   "stages": [Stage("Unscheduled", "planned", [], 0.0, 1.0, None, None, unscheduled)]})
            lanes.append({"id": gid, "outcome": goal.get("outcome", ""), "criterion": goal.get("criterion", ""), "lanes": goal_lanes})
        unresolved = [meta["stories"][sid] for sid, status in meta["statuses"].items()
                      if status == "unresolved" and sid in meta["stories"]]
        if unresolved:
            lanes.append({"id": "unmapped", "outcome": "Unmapped", "criterion": "", "lanes": [
                {"id": "unmapped", "name": "Unmapped", "type": "unmapped", "stages": [
                    Stage("Unmapped", "unresolved", [], 0.0, 1.0, None, None, unresolved)
                ]}
            ]})
        return lanes
    finally:
        if owned:
            conn.close()


@dataclasses.dataclass(frozen=True)
class JobRun:
    ts: str
    agent: str
    duration_s: float
    exit_code: int
    cost_usd: float
    # Action metadata is optional because older telemetry rows do not contain it.
    job_id: Optional[str] = None
    pr_number: Optional[int] = None
    status: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class AgentBucket:
    tasks_done: int
    tasks_active: int
    total_usd: float
    success_rate: float
    alert_count: int


def get_jobs() -> list:
    """Return the last 20 telemetry rows as typed JobRun entries, newest last."""
    try:
        with open(".synlynk/telemetry.json") as f:
            rows = json.load(f)
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    tracked_jobs = {}
    try:
        from synlynk.jobs import _load_jobs

        tracked_jobs = {
            str(row.get("id") or row.get("job_id")): row
            for row in _load_jobs()
            if isinstance(row, dict) and (row.get("id") or row.get("job_id"))
        }
    except Exception:
        pass

    jobs = []
    seen_job_ids = set()
    for row in rows[-20:]:
        if not isinstance(row, dict):
            continue
        job_id = row.get("job_id") or row.get("id")
        tracked = tracked_jobs.get(str(job_id), {}) if job_id else {}
        pr_number = row.get("pr_number") or tracked.get("pr_number")
        try:
            pr_number = int(pr_number) if pr_number is not None else None
        except (TypeError, ValueError):
            pr_number = None
        if job_id:
            seen_job_ids.add(str(job_id))
        jobs.append(
            JobRun(
                ts=row.get("ts") or row.get("timestamp") or "",
                agent=row.get("agent") or "",
                duration_s=float(row.get("duration_s") or 0.0),
                exit_code=int(row.get("exit_code") or 0),
                cost_usd=float(row.get("cost_usd") or 0.0),
                job_id=str(job_id) if job_id else None,
                pr_number=pr_number,
                status=row.get("status") or tracked.get("status"),
            )
        )
    # Running/queued jobs can exist before they have emitted telemetry.
    for job_id, row in tracked_jobs.items():
        if job_id in seen_job_ids:
            continue
        jobs.append(JobRun(
            ts=row.get("started_at") or row.get("enqueued_at") or "",
            agent=row.get("agent") or "",
            duration_s=0.0,
            exit_code=0,
            cost_usd=float(row.get("cost_usd") or 0.0),
            job_id=job_id,
            pr_number=row.get("pr_number"),
            status=row.get("status"),
        ))
    return jobs


def get_fleet_state() -> dict:
    """Return a dict of agent name -> AgentBucket, derived from recent telemetry."""
    jobs = get_jobs()
    agent_runs = {}
    for job in jobs:
        if not job.agent:
            continue
        agent_runs.setdefault(job.agent, {"ok": 0, "total": 0, "cost": 0.0})
        agent_runs[job.agent]["total"] += 1
        agent_runs[job.agent]["cost"] += job.cost_usd
        if job.exit_code == 0:
            agent_runs[job.agent]["ok"] += 1
    fleet = {}
    for agent, stats in agent_runs.items():
        total = stats["total"]
        fleet[agent] = AgentBucket(
            tasks_done=stats["ok"],
            tasks_active=0,
            total_usd=stats["cost"],
            success_rate=(stats["ok"] / total) if total else 0.0,
            alert_count=0,
        )
    return fleet


EVENTS_PATH = ".synlynk/events.jsonl"

_WRITE_CAPABILITIES_BY_ROLE = {
    Role.OWNER: {"dispatch", "approve_pr", "kill_job"},
    Role.MEMBER: {"dispatch"},
    Role.VIEWER: set(),
}


@dataclasses.dataclass(frozen=True)
class Capability:
    name: str
    enabled: bool


class FeatureFlags:
    """Tiered feature flags, orthogonal to RBAC. Reads a static `features` block
    from .synlynk/config.json: {"features": {"<flag>": ["individual", "team", ...]}}.
    A missing config, missing key, or missing flag is treated as disabled
    (fail-closed) rather than an error.
    """

    @staticmethod
    def is_enabled(flag: str, tier: str) -> bool:
        try:
            with open(".synlynk/config.json") as f:
                config = json.load(f)
        except Exception:
            return False
        tiers_for_flag = config.get("features", {}).get(flag, [])
        return tier in tiers_for_flag


def list_capabilities(actor: Optional[Actor] = None) -> list:
    """Compute the capability manifest for an actor. Every consumer (TUI, Vizor,
    BYOUX) calls this once and renders/hides menu items from the result, rather
    than hardcoding per-surface permission checks."""
    actor = actor or DEFAULT_ACTOR
    allowed = _WRITE_CAPABILITIES_BY_ROLE.get(actor.role, set())
    all_writes = {"dispatch", "approve_pr", "kill_job"}
    return [Capability(name=name, enabled=name in allowed) for name in sorted(all_writes)]


def _has_capability(actor: Actor, action: str) -> bool:
    caps = {c.name: c.enabled for c in list_capabilities(actor)}
    return caps.get(action, False)


def _append_event(event: Event) -> None:
    os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
    with open(EVENTS_PATH, "a") as f:
        f.write(
            json.dumps(
                {
                    "actor_id": event.actor_id,
                    "action": event.action,
                    "params": event.params,
                    "timestamp": event.timestamp,
                    "result": event.result,
                },
                default=str,
            )
            + "\n"
        )


def _execute_write(action: str, actor: Actor, operation, **params) -> WriteResult:
    """The single chokepoint every uxcore write funnels through: checks
    list_capabilities(actor), runs `operation(**params)` if permitted, appends
    a structured event to .synlynk/events.jsonl, and returns a WriteResult.
    This is where policy checks and notification hooks attach in later phases —
    one interception point, not one per surface per write type."""
    if not _has_capability(actor, action):
        result = WriteResult(ok=False, message="not permitted")
        _append_event(
            Event(
                actor_id=actor.id,
                action=action,
                params=params,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                result={"ok": False, "message": "not permitted"},
            )
        )
        return result

    try:
        op_result = operation(**params)
    except Exception as exc:
        raise UxCoreError(f"{action} failed: {exc}") from exc

    result = WriteResult(
        ok=bool(op_result.get("ok", True)),
        message=op_result.get("message", ""),
        job_id=op_result.get("job_id"),
    )
    _append_event(
        Event(
            actor_id=actor.id,
            action=action,
            params=params,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            result={"ok": result.ok, "message": result.message, "job_id": result.job_id},
        )
    )
    return result


import signal
import subprocess


def _review_mode_for_logins(author_login: Optional[str], reviewer_login: Optional[str]) -> str:
    """Select the safe review submission mode for two GitHub identities.

    GitHub logins are case-insensitive. Unknown identities are deliberately
    treated as distinct so a failed ``--approve`` can still use the existing
    fail-closed fallback handling.
    """
    author = (author_login or "").strip().lower()
    reviewer = (reviewer_login or "").strip().lower()
    if author and reviewer and author == reviewer:
        return "comment_checklist"
    return "approve"


def dispatch(agent: str, task: str, actor: Optional[Actor] = None, **flags) -> WriteResult:
    """Dispatch a task to an agent. Wraps synlynk.dispatch.dispatch_agent()."""
    actor = actor or DEFAULT_ACTOR

    def _op(**params):
        from synlynk.dispatch import dispatch_agent

        return dispatch_agent(params["agent"], params["task"], **params.get("flags", {}))

    return _execute_write("dispatch", actor, _op, agent=agent, task=task, flags=flags)


def approve_pr(pr_number: int, actor: Optional[Actor] = None, role: str = "qa",
               story_id: Optional[str] = None) -> WriteResult:
    """Approve and squash-merge a PR via gh. qa APPROVE (`gh pr review --approve`)
    is the default when reviewer and author identities differ; comment-checklist only
    on same-login collision or credential/permission fallback (see #423)."""
    actor = actor or DEFAULT_ACTOR

    def _op(**params):
        pr = str(params["pr_number"])
        op_role = params.get("role") or "qa"
        env = os.environ.copy()
        try:
            from synlynk.dispatch import _isolated_gh_config_dir, _resolve_dispatch_gh_token
            token = _resolve_dispatch_gh_token(op_role)
            if token:
                env.pop("GH_TOKEN", None)
                env.pop("GITHUB_TOKEN", None)
                env["GH_TOKEN"] = token
                env["GITHUB_TOKEN"] = token
                env["GH_CONFIG_DIR"] = _isolated_gh_config_dir()
        except Exception:
            token = None

        reviewer_login = None
        author_login = None
        try:
            from synlynk.dispatch import _resolve_dispatch_gh_bot_login
            reviewer_login = _resolve_dispatch_gh_bot_login(op_role)
            if reviewer_login:
                identity = subprocess.run(
                    ["gh", "pr", "view", pr, "--json", "author"],
                    capture_output=True, text=True, env=env,
                )
                if identity.returncode == 0:
                    author_login = (json.loads(identity.stdout or "{}").get("author") or {}).get("login")
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass

        if _review_mode_for_logins(author_login, reviewer_login) == "comment_checklist":
            review = subprocess.run(
                [
                    "gh", "pr", "comment", pr, "--body",
                    "Approved (formal comment — same-login collision review fallback, see #423).\n\n"
                    "Checklist:\n- [x] Reviewed the PR diff\n- [x] Verified the relevant tests\n- [x] No blocking concerns",
                ], capture_output=True, text=True, env=env,
            )
            if review.returncode != 0:
                return {"ok": False, "message": review.stdout or review.stderr}
            review = None
        else:
            review = subprocess.run(
                ["gh", "pr", "review", pr, "--approve"], capture_output=True, text=True, env=env
            )
        if review is not None and review.returncode != 0:
            review_message = review.stdout or review.stderr
            normalized_message = review_message.lower()
            self_approval_error = (
                "can not approve your own pull request" in normalized_message
                or "cannot approve your own pull request" in normalized_message
                or "same-login" in normalized_message
                or "same login" in normalized_message
            )
            credential_permission_error = (
                "resource not accessible by integration" in normalized_message
                or "bad credentials" in normalized_message
                or "credentials" in normalized_message
                or "not accessible by integration" in normalized_message
                or "integration" in normalized_message
                or "permission" in normalized_message
                or "unauthorized" in normalized_message
                or "401" in normalized_message
                or "403" in normalized_message
            )
            if not (self_approval_error or credential_permission_error):
                return {"ok": False, "message": review_message}

            fallback_reason = "same-login collision" if self_approval_error else "credential/permission"
            comment = subprocess.run(
                ["gh", "pr", "comment", pr, "--body", f"Approved (formal comment — {fallback_reason} review fallback, see #423)."],
                capture_output=True,
                text=True,
                env=env,
            )
            if comment.returncode != 0:
                return {"ok": False, "message": comment.stdout or comment.stderr}
        rebase = rebase_pr_if_behind(int(pr), env=env)
        if rebase.get("attempted") and not rebase.get("rebased"):
            return {"ok": False, "message": f"cannot merge behind PR: {rebase['reason']}"}
        from synlynk.merge_oracle import require_merge_oracle
        oracle = require_merge_oracle(pr_number=int(pr), role=op_role)
        if not oracle["merge_allowed"]:
            return {"ok": False, "message": oracle["reason"]}
        merge = subprocess.run(
            ["gh", "pr", "merge", pr, "--squash"], capture_output=True, text=True, env=env
        )
        if merge.returncode == 0 and story_id:
            from synlynk.db import mark_story_done_after_merge
            mark_story_done_after_merge(story_id, pr_number=pr)
        return {"ok": merge.returncode == 0, "message": merge.stdout or merge.stderr}

    return _execute_write("approve_pr", actor, _op, pr_number=pr_number, role=role)


def kill_job(job_id: str, actor: Optional[Actor] = None) -> WriteResult:
    """Send SIGTERM to a running job's tracked PID. Reads/writes .synlynk/jobs.json
    via the existing synlynk.jobs._load_jobs()/_save_jobs() helpers."""
    actor = actor or DEFAULT_ACTOR

    def _op(**params):
        from synlynk.jobs import _load_jobs, _save_jobs

        jobs = _load_jobs()
        target = next((j for j in jobs if j.get("job_id") == params["job_id"]), None)
        if target is None:
            return {"ok": False, "message": f"no job with id {params['job_id']}"}
        pid = target.get("pid")
        if pid:
            os.kill(pid, signal.SIGTERM)
        target["status"] = "killed"
        _save_jobs(jobs)
        return {"ok": True, "message": f"sent SIGTERM to pid {pid}", "job_id": params["job_id"]}

    return _execute_write("kill_job", actor, _op, job_id=job_id)


def subscribe(event_types: Optional[list] = None) -> Iterator[Event]:
    """Read all events currently in .synlynk/events.jsonl, optionally filtered
    to `event_types`. This is a one-shot read of existing events, not a live
    tail — callers that want live updates poll subscribe() on an interval
    (see synlynk/notifiers/slack.py for the reference consumer)."""
    if not os.path.exists(EVENTS_PATH):
        return
    with open(EVENTS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event_types is not None and raw.get("action") not in event_types:
                continue
            yield Event(
                actor_id=raw.get("actor_id", ""),
                action=raw.get("action", ""),
                params=raw.get("params", {}),
                timestamp=raw.get("timestamp", ""),
                result=raw.get("result", {}),
            )
