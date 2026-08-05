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
