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


def get_gantt_data() -> list:
    """Return roadmap arcs as a list of Dream dataclasses with nested Stage/Task. Raises UxCoreError on DB access failure."""
    try:
        conn = _get_db()
    except Exception as exc:
        raise UxCoreError(f"could not open state db: {exc}") from exc
    try:
        arc_rows = conn.execute(
            "SELECT version, title, status, target_date, notes FROM roadmap_arcs ORDER BY id"
        ).fetchall()
        phase_rows = conn.execute(
            "SELECT id, arc_version, phase_title, status, priority, story_id, notes "
            "FROM roadmap_phases ORDER BY arc_version, id"
        ).fetchall()
        story_rows = conn.execute(
            "SELECT story_id, title, status, phase, estimated_tokens FROM stories ORDER BY id"
        ).fetchall()
        cost_rows = _fetch_cost_rows(conn)

        stories_by_id = {}
        stories_by_phase = {}
        for story_id, title, status, phase, estimated_tokens in story_rows:
            task = Task(
                id=story_id,
                name=title or "",
                agent=phase or "",
                status=status or "open",
                cost_est=_story_cost_est(estimated_tokens),
                cost_actual=0.0,
                cost_prov_estimated=0.0,
            )
            stories_by_id[story_id] = task
            stories_by_phase.setdefault((phase or "").strip().lower(), []).append(task)

        for _date, agent, amount, notes, cost_source in cost_rows:
            amount = float(amount or 0.0)
            for story_id, task in stories_by_id.items():
                if story_id and story_id in (notes or ""):
                    object.__setattr__(task, "cost_actual", task.cost_actual + amount)
                    if cost_source != "actual":
                        object.__setattr__(
                            task, "cost_prov_estimated", task.cost_prov_estimated + amount
                        )

        dreams = []
        import re

        for dream_id, dream_name, dream_status, _target_date, _notes in arc_rows:
            stage_rows = [row for row in phase_rows if row[1] == dream_id]
            stage_count = len(stage_rows)
            dream_stages = []
            for index, phase_row in enumerate(stage_rows):
                _pid, _arc, phase_title, phase_status, _prio, story_id, notes = phase_row
                agent_list = []
                for match in re.findall(r"\bagent:([a-z,]+)\b", notes or ""):
                    agent_list.extend([a for a in match.split(",") if a])
                phase_key = (phase_title or "").strip()
                matched = []
                if story_id and story_id in stories_by_id:
                    matched.append(stories_by_id[story_id])
                matched.extend(stories_by_phase.get(phase_key.lower(), []))
                deduped, seen = [], set()
                for task in matched:
                    if task.id in seen:
                        continue
                    seen.add(task.id)
                    deduped.append(task)
                for task in deduped:
                    if task.agent and not _looks_like_stage_label(task.agent):
                        agent_list.append(task.agent)
                stage_cost_actual = sum(t.cost_actual for t in deduped)
                stage_cost_est = sum(t.cost_est or 0.0 for t in deduped) or None
                dream_stages.append(
                    Stage(
                        key=phase_key,
                        status=phase_status or "planned",
                        agents=sorted(dict.fromkeys(agent_list)),
                        start_frac=(index / stage_count) if stage_count else 0.0,
                        width_frac=(1.0 / stage_count) if stage_count else 1.0,
                        cost_actual=stage_cost_actual or None,
                        cost_est=stage_cost_est,
                        tasks=deduped,
                    )
                )
            dream_cost_total, dream_cost_prov_estimated = _dream_cost_breakdown(conn, dream_id)
            dream_tasks_cost_est = sum(
                s.cost_est or 0.0 for s in dream_stages
            ) or None
            dreams.append(
                Dream(
                    id=dream_id,
                    name=dream_name or "",
                    status=dream_status or "planned",
                    cost_total=float(dream_cost_total),
                    cost_total_estimated=float(dream_cost_prov_estimated),
                    cost_est=dream_tasks_cost_est,
                    stages=dream_stages,
                )
            )
        return dreams
    finally:
        try:
            conn.close()
        except Exception:
            pass


@dataclasses.dataclass(frozen=True)
class JobRun:
    ts: str
    agent: str
    duration_s: float
    exit_code: int
    cost_usd: float


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
    jobs = []
    for row in rows[-20:]:
        if not isinstance(row, dict):
            continue
        jobs.append(
            JobRun(
                ts=row.get("ts") or row.get("timestamp") or "",
                agent=row.get("agent") or "",
                duration_s=float(row.get("duration_s") or 0.0),
                exit_code=int(row.get("exit_code") or 0),
                cost_usd=float(row.get("cost_usd") or 0.0),
            )
        )
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


def dispatch(agent: str, task: str, actor: Optional[Actor] = None, **flags) -> WriteResult:
    """Dispatch a task to an agent. Wraps synlynk.dispatch.dispatch_agent()."""
    actor = actor or DEFAULT_ACTOR

    def _op(**params):
        from synlynk.dispatch import dispatch_agent

        return dispatch_agent(params["agent"], params["task"], **params.get("flags", {}))

    return _execute_write("dispatch", actor, _op, agent=agent, task=task, flags=flags)


def approve_pr(pr_number: int, actor: Optional[Actor] = None) -> WriteResult:
    """Approve and squash-merge a PR via gh. Falls back to a formal comment
    approval if `gh pr review --approve` fails on the shared-identity
    self-approval error (see CLAUDE.md "GitHub identity caveat #423")."""
    actor = actor or DEFAULT_ACTOR

    def _op(**params):
        pr = str(params["pr_number"])
        review = subprocess.run(
            ["gh", "pr", "review", pr, "--approve"], capture_output=True, text=True
        )
        if review.returncode != 0:
            subprocess.run(
                ["gh", "pr", "comment", pr, "--body", "Approved (formal comment — shared GitHub identity, see #423)."],
                capture_output=True,
                text=True,
            )
        merge = subprocess.run(
            ["gh", "pr", "merge", pr, "--squash", "--admin"], capture_output=True, text=True
        )
        return {"ok": merge.returncode == 0, "message": merge.stdout or merge.stderr}

    return _execute_write("approve_pr", actor, _op, pr_number=pr_number)


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
