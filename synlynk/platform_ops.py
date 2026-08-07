"""Cross-repo platform operations report for this machine/environment.

Answers a broader question than fleet hygiene: "Did multi-agent work actually
work across every synlynk-managed project on this box in the last N hours?"

Layers (maps to the nine gaps from the fleet EOD postmortem):
  L0 hygiene     — nested product state.db, dry matrix (known repos under ~/dev)
  L1 jobs        — daemon_jobs + jobs.json outcomes (status mix, unknown rate)
  L2 cost        — cost_entries rollup + orphan costs (no job_id)
  L3 side-effect — GH-write capable agents vs recent job text mentioning gh/pr fail
  L4 signals     — recent (report-window) sentinel CRITICAL lines + open LIVE issues
  L5 worktrees   — local git worktree count / stale
  L6 live smoke  — optional: last live matrix cells (per-repo if recorded)
  L7 attach      — harness attach/completion rates when present
  L8 soft-criteria scoreboard — explicit ops RED vs hygiene GREEN separation
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Sentinel severity tokens that contribute to ops RED when recent.
_SENTINEL_CRIT_KEYS = ("CRITICAL", "FLATLINE", "QUOTA_EXHAUSTED")
# Bracket timestamps as written by _write_sentinel_alert: [YYYY-MM-DD HH:MM]
_SENTINEL_TS_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(?::\d{2})?)\]"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s[:19] if "T" in s or " " in s else s[:10], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _parse_sentinel_line_ts(line: str) -> Optional[datetime]:
    """Parse the first bracket timestamp in a sentinel.md alert line.

    Matches both ``[YYYY-MM-DD HH:MM]`` (canonical write format) and
    ISO-like ``[YYYY-MM-DDTHH:MM:SS]``. Returned datetimes are timezone-aware
    UTC; naive local wall-clock stamps are treated as UTC for windowing
    (acceptable for multi-hour ops windows).
    """
    m = _SENTINEL_TS_RE.search(line or "")
    if not m:
        return None
    date_s, time_s = m.group(1), m.group(2)
    if len(time_s) == 5:
        time_s = time_s + ":00"
    try:
        dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_sentinel_critical_line(line: str) -> bool:
    """True for alert bullets that carry CRITICAL / FLATLINE / QUOTA_EXHAUSTED.

    Requires a ``- [`` prefix so triage notes / markdown headers mentioning
    the word CRITICAL are not counted.
    """
    s = (line or "").strip()
    if not s.startswith("- ["):
        return False
    upper = s.upper()
    return any(k in upper for k in _SENTINEL_CRIT_KEYS)


def count_sentinel_critical_lines(
    text: str,
    *,
    cutoff: datetime,
    now: Optional[datetime] = None,
) -> Tuple[int, int, int]:
    """Count severity-critical sentinel lines with a time window.

    Returns ``(windowed, lifetime, untimestamped)``:
    - **windowed** — critical lines with a parseable timestamp ``>= cutoff``
      and ``<= now`` (if ``now`` given; default no upper bound beyond now)
    - **lifetime** — all critical alert lines regardless of age
    - **untimestamped** — critical lines with no parseable timestamp (excluded
      from windowed so append-only historical noise without stamps cannot
      flip ops RED)

    Lines outside the window still appear in ``lifetime`` for diagnostics.
    """
    if now is None:
        now = _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    windowed = 0
    lifetime = 0
    untimestamped = 0
    for line in (text or "").splitlines():
        if not _is_sentinel_critical_line(line):
            continue
        lifetime += 1
        ts = _parse_sentinel_line_ts(line)
        if ts is None:
            untimestamped += 1
            continue
        if cutoff <= ts <= now + timedelta(minutes=5):
            # +5m slack for clock skew / same-minute writes
            windowed += 1
    return windowed, lifetime, untimestamped


def _dev_roots() -> List[Path]:
    dev = Path.home() / "dev"
    if not dev.is_dir():
        return []
    roots = []
    for p in sorted(dev.iterdir()):
        if not p.is_dir():
            continue
        if (p / ".synlynk").is_dir() or (p / ".git").exists():
            roots.append(p)
    return roots


def _project_dbs(hours: int) -> List[Path]:
    projects = Path.home() / ".synlynk" / "projects"
    if not projects.is_dir():
        return []
    cutoff = _utc_now().timestamp() - (hours + 24) * 3600
    out = []
    for d in projects.iterdir():
        db = d / "state.db"
        if db.is_file() and db.stat().st_mtime >= cutoff:
            out.append(db)
    return out


@dataclass
class PlatformReport:
    hours: int
    generated_at: str
    hygiene: Dict[str, Any] = field(default_factory=dict)
    jobs: Dict[str, Any] = field(default_factory=dict)
    costs: Dict[str, Any] = field(default_factory=dict)
    side_effects: Dict[str, Any] = field(default_factory=dict)
    signals: Dict[str, Any] = field(default_factory=dict)
    worktrees: Dict[str, Any] = field(default_factory=dict)
    live_smoke: Dict[str, Any] = field(default_factory=dict)
    attach: Dict[str, Any] = field(default_factory=dict)
    scoreboard: Dict[str, Any] = field(default_factory=dict)
    job_samples: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def collect_platform_report(hours: int = 24, dev_root: Optional[str] = None) -> PlatformReport:
    """Build a full-environment platform ops report for the last *hours*."""
    now = _utc_now()
    cutoff = now - timedelta(hours=hours)
    cutoff_s = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    report = PlatformReport(hours=hours, generated_at=now.isoformat())

    # --- L0 hygiene: nested DBs under known ~/dev repos ---
    nested_total = 0
    nested_by_repo: Dict[str, int] = {}
    matrix_by_repo: Dict[str, Any] = {}
    try:
        from synlynk.fleet import find_nested_product_state_dbs, run_matrix_dry
    except Exception:
        find_nested_product_state_dbs = None  # type: ignore
        run_matrix_dry = None  # type: ignore

    roots = _dev_roots()
    if dev_root:
        roots = [Path(dev_root)] + [r for r in roots if r.resolve() != Path(dev_root).resolve()]

    for root in roots:
        name = root.name
        if find_nested_product_state_dbs:
            try:
                hits = find_nested_product_state_dbs(str(root))
                nested_by_repo[name] = len(hits)
                nested_total += len(hits)
            except Exception:
                nested_by_repo[name] = -1
        # dry matrix only for repos that look synlynk-initialized
        if run_matrix_dry and (root / "synlynk").is_dir() and (root / "tests").is_dir():
            try:
                cwd = os.getcwd()
                os.chdir(root)
                cells = run_matrix_dry(str(root))
                reds = [c for c in cells if c.status == "red" and c.tier == 1]
                matrix_by_repo[name] = {
                    "cells": len(cells),
                    "green": sum(1 for c in cells if c.status == "green"),
                    "red": len(reds),
                    "exit": 1 if reds else 0,
                }
            except Exception as e:
                matrix_by_repo[name] = {"error": str(e)[:120]}
            finally:
                os.chdir(cwd)

    report.hygiene = {
        "nested_product_state_db_total": nested_total,
        "nested_by_repo": nested_by_repo,
        "dry_matrix_by_repo": matrix_by_repo,
        "pass": nested_total == 0 and all(
            (v.get("red", 0) == 0) for v in matrix_by_repo.values() if isinstance(v, dict) and "red" in v
        ),
    }

    # --- L1 jobs + L2 costs from project DBs ---
    jobs: List[dict] = []
    costs: List[dict] = []
    dbs = _project_dbs(hours)
    for db in dbs:
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT job_id, agent, task, story_id, status, exit_code, "
                    "enqueued_at, started_at, completed_at, log_path "
                    "FROM daemon_jobs WHERE COALESCE(completed_at, started_at, enqueued_at) >= ?",
                    (cutoff_s[:19],),
                ).fetchall()
                for r in rows:
                    for col in ("completed_at", "started_at", "enqueued_at"):
                        dt = _parse_ts(r[col])
                        if dt and dt >= cutoff:
                            jobs.append({
                                "job_id": r["job_id"],
                                "agent": r["agent"],
                                "status": r["status"],
                                "exit_code": r["exit_code"],
                                "completed_at": r["completed_at"],
                                "started_at": r["started_at"],
                                "task": (r["task"] or "")[:100],
                                "db": db.parent.name,
                                "source": "daemon_jobs",
                            })
                            break
            except sqlite3.Error:
                pass
            try:
                rows = conn.execute(
                    "SELECT agent, model, input_tokens, output_tokens, cache_read_tokens, "
                    "total_cost_usd, job_id, story_id, notes, recorded_at, session_date "
                    "FROM cost_entries WHERE COALESCE(recorded_at, session_date) >= ?",
                    (cutoff_s[:10],),
                ).fetchall()
                for r in rows:
                    dt = _parse_ts(r["recorded_at"]) or _parse_ts(
                        (r["session_date"] or "") + "T12:00:00+00:00"
                    )
                    if dt and dt >= cutoff:
                        costs.append({
                            "agent": r["agent"],
                            "model": r["model"],
                            "in_tok": int(r["input_tokens"] or 0),
                            "out_tok": int(r["output_tokens"] or 0),
                            "cache_tok": int(r["cache_read_tokens"] or 0),
                            "cost": float(r["total_cost_usd"] or 0),
                            "job_id": r["job_id"],
                            "recorded_at": r["recorded_at"] or r["session_date"],
                            "notes": (r["notes"] or "")[:80],
                            "db": db.parent.name,
                        })
            except sqlite3.Error:
                pass
            # live matrix cells if table exists
            try:
                rows = conn.execute(
                    "SELECT home, cell, tier, status, detail, cost_usd, ts FROM fleet_matrix_runs "
                    "WHERE tier=2 AND ts >= ? ORDER BY ts DESC LIMIT 50",
                    (cutoff_s[:19],),
                ).fetchall()
                if rows and not report.live_smoke.get("cells"):
                    report.live_smoke["cells"] = [
                        {
                            "home": r[0], "cell": r[1], "status": r[3],
                            "detail": r[4], "cost": r[5], "ts": r[6], "db": db.parent.name,
                        }
                        for r in rows[:20]
                    ]
            except sqlite3.Error:
                pass
            try:
                rows = conn.execute(
                    "SELECT agent_name, attach_rate_24h, completion_rate_24h, compliance_status "
                    "FROM harness_status"
                ).fetchall()
                if rows:
                    report.attach.setdefault("rows", [])
                    for r in rows:
                        report.attach["rows"].append({
                            "agent": r[0], "attach": r[1], "complete": r[2],
                            "compliance": r[3], "db": db.parent.name,
                        })
            except sqlite3.Error:
                pass
            conn.close()
        except Exception:
            continue

    # jobs.json under ~/dev
    for root in roots:
        jp = root / ".synlynk" / "jobs.json"
        if not jp.is_file():
            continue
        try:
            data = json.loads(jp.read_text())
            items = data if isinstance(data, list) else (
                data.get("jobs") or list(data.values()) if isinstance(data, dict) else []
            )
            if isinstance(items, dict):
                items = list(items.values())
            for j in items:
                if not isinstance(j, dict):
                    continue
                for col in ("completed_at", "ended_at", "started_at", "enqueued_at"):
                    dt = _parse_ts(j.get(col))
                    if dt and dt >= cutoff:
                        jobs.append({
                            "job_id": j.get("id") or j.get("job_id"),
                            "agent": j.get("agent"),
                            "status": j.get("status"),
                            "exit_code": j.get("exit_code"),
                            "completed_at": j.get("completed_at") or j.get("ended_at"),
                            "started_at": j.get("started_at"),
                            "task": (j.get("task") or "")[:100],
                            "db": root.name,
                            "source": "jobs.json",
                        })
                        break
        except Exception:
            pass

    # dedupe jobs
    by_id: Dict[str, dict] = {}
    for j in jobs:
        jid = j.get("job_id") or f"{j.get('db')}-{j.get('started_at')}-{j.get('agent')}"
        prev = by_id.get(jid)
        if not prev or (j.get("completed_at") or "") > (prev.get("completed_at") or ""):
            by_id[jid] = j
    jobs = list(by_id.values())

    status_counts = Counter((j.get("status") or "unknown").lower() for j in jobs)
    n_jobs = len(jobs)
    unknownish = sum(
        status_counts[s] for s in status_counts
        if s in ("unknown", "failed_unverified", "") or "unknown" in s
    )
    failed = sum(status_counts[s] for s in status_counts if "fail" in s)
    done = sum(status_counts[s] for s in status_counts if s in ("done", "completed", "ok"))
    unknown_rate = (unknownish / n_jobs) if n_jobs else 0.0
    fail_rate = (failed / n_jobs) if n_jobs else 0.0

    by_agent_jobs = Counter(j.get("agent") or "?" for j in jobs)
    report.jobs = {
        "count": n_jobs,
        "by_status": dict(status_counts),
        "by_agent": dict(by_agent_jobs),
        "unknown_rate": round(unknown_rate, 3),
        "fail_rate": round(fail_rate, 3),
        "done": done,
        "failed": failed,
        "unknownish": unknownish,
        "dbs_scanned": len(dbs),
        "pass": n_jobs == 0 or (unknown_rate < 0.25 and fail_rate < 0.40),
    }
    report.job_samples = sorted(
        jobs,
        key=lambda j: j.get("completed_at") or j.get("started_at") or "",
        reverse=True,
    )[:25]

    # costs
    tot_cost = sum(c["cost"] for c in costs)
    tot_in = sum(c["in_tok"] for c in costs)
    tot_out = sum(c["out_tok"] for c in costs)
    by_agent_cost: Dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "in": 0, "out": 0, "n": 0})
    orphans = 0
    job_ids = set(by_id.keys())
    for c in costs:
        a = c.get("agent") or "?"
        by_agent_cost[a]["cost"] += c["cost"]
        by_agent_cost[a]["in"] += c["in_tok"]
        by_agent_cost[a]["out"] += c["out_tok"]
        by_agent_cost[a]["n"] += 1
        if not c.get("job_id") or c.get("job_id") not in job_ids:
            orphans += 1
    orphan_rate = (orphans / len(costs)) if costs else 0.0
    report.costs = {
        "entries": len(costs),
        "total_usd": round(tot_cost, 4),
        "input_tokens": tot_in,
        "output_tokens": tot_out,
        "by_agent": {k: dict(v) for k, v in sorted(by_agent_cost.items(), key=lambda x: -x[1]["cost"])},
        "orphan_entries": orphans,
        "orphan_rate": round(orphan_rate, 3),
        "pass": orphan_rate < 0.35 or len(costs) == 0,
    }

    # L3 side-effects (lightweight text heuristics on recent tasks)
    gh_fail_hints = 0
    for j in jobs:
        t = (j.get("task") or "").lower()
        st = (j.get("status") or "").lower()
        if any(x in t for x in ("gh pr", "github", "merge", "review")) and (
            "fail" in st or "unknown" in st
        ):
            gh_fail_hints += 1
    try:
        from synlynk._constants import AGENT_CAPABILITY_BASELINES as _BASELINES
        can_gh = [a for a, b in _BASELINES.items() if b.get("can_gh_write")]
    except Exception:
        can_gh = []
    report.side_effects = {
        "note": "Heuristic only — Phase 3 GH-write proof not automated yet",
        "jobs_mentioning_gh_with_bad_status": gh_fail_hints,
        "can_gh_write_agents": can_gh,
        "pass": gh_fail_hints < max(3, n_jobs // 5) if n_jobs else True,
    }

    # L4 signals — sentinels across ~/dev (windowed) + LIVE issues via gh
    # Window matches the report's --hours so STALE historical CRITICAL lines
    # in append-only sentinel.md cannot keep ops RED forever (#751).
    sentinel_hours = hours
    env_hours = os.environ.get("SYNLYNK_OPS_SENTINEL_HOURS", "").strip()
    if env_hours.isdigit():
        sentinel_hours = max(1, int(env_hours))
    sentinel_cutoff = now - timedelta(hours=sentinel_hours)

    sentinel_crit = 0
    sentinel_crit_lifetime = 0
    sentinel_untimestamped = 0
    sentinel_files = 0
    for root in roots:
        sp = root / ".synlynk" / "sentinel.md"
        if not sp.is_file():
            continue
        sentinel_files += 1
        try:
            text = sp.read_text(errors="replace")
            w, life, unts = count_sentinel_critical_lines(
                text, cutoff=sentinel_cutoff, now=now
            )
            sentinel_crit += w
            sentinel_crit_lifetime += life
            sentinel_untimestamped += unts
        except Exception:
            pass

    live_issues = []
    # Scope to this environment's orgs (not entire GitHub search noise).
    owners = os.environ.get("SYNLYNK_OPS_GH_OWNERS", "nikhilsoman,Dialify").split(",")
    for owner in owners:
        owner = owner.strip()
        if not owner:
            continue
        try:
            r = subprocess.run(
                [
                    "gh", "search", "issues",
                    f"label:live-issue is:open user:{owner}",
                    "--limit", "20",
                    "--json", "number,title,repository,url",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                live_issues.extend(json.loads(r.stdout))
        except Exception:
            pass
    # de-dupe by url/number
    seen_urls = set()
    deduped = []
    for i in live_issues:
        u = i.get("url") or f"{i.get('number')}"
        if u in seen_urls:
            continue
        seen_urls.add(u)
        deduped.append(i)
    live_issues = deduped

    report.signals = {
        "sentinel_files_scanned": sentinel_files,
        "sentinel_critical_lines": sentinel_crit,
        "sentinel_critical_lines_lifetime": sentinel_crit_lifetime,
        "sentinel_critical_untimestamped": sentinel_untimestamped,
        "sentinel_window_hours": sentinel_hours,
        "open_live_issues": len(live_issues),
        "live_issue_samples": [
            {"number": i.get("number"), "title": (i.get("title") or "")[:80],
             "repo": (i.get("repository") or {}).get("nameWithOwner") if isinstance(i.get("repository"), dict) else i.get("repository")}
            for i in live_issues[:10]
        ],
        "pass": len(live_issues) == 0 and sentinel_crit < 5,
    }

    # L5 worktrees — directory walk under ~/dev (no unused git porcelain call)
    try:
        wt_dirs = 0
        for root in roots:
            for base in (".worktrees", "worktrees"):
                d = root / base
                if d.is_dir():
                    for child in d.iterdir():
                        if child.is_dir():
                            wt_dirs += 1
        report.worktrees = {
            "tracked_under_dev_worktrees_dirs": wt_dirs,
            "note": "High counts are operational debt; not auto-cleaned",
            "pass": wt_dirs < 80,
        }
    except Exception as e:
        report.worktrees = {"error": str(e)[:100], "pass": True}

    # L6 live smoke summary
    cells = report.live_smoke.get("cells") or []
    live_green = sum(1 for c in cells if c.get("status") == "green")
    live_red = sum(1 for c in cells if c.get("status") == "red")
    report.live_smoke.update({
        "green": live_green,
        "red": live_red,
        "note": "These are CLI smoke cells if recorded — not full dispatch proof",
        "pass": live_red == 0,
    })

    # L7 attach
    rows = report.attach.get("rows") or []
    zero_attach = sum(1 for r in rows if not r.get("attach"))
    report.attach.update({
        "row_count": len(rows),
        "zero_attach_count": zero_attach,
        "pass": True,  # informational; attach often empty
        "note": "Attach rates are informational — empty is common",
    })

    # L8 scoreboard — separate hygiene vs ops reality
    hygiene_ok = bool(report.hygiene.get("pass"))
    jobs_ok = bool(report.jobs.get("pass"))
    costs_ok = bool(report.costs.get("pass"))
    signals_ok = bool(report.signals.get("pass"))
    side_ok = bool(report.side_effects.get("pass"))

    ops_red_reasons = []
    if not jobs_ok:
        ops_red_reasons.append(
            f"job unknown_rate={report.jobs.get('unknown_rate')} fail_rate={report.jobs.get('fail_rate')}"
        )
    if not costs_ok:
        ops_red_reasons.append(f"cost orphan_rate={report.costs.get('orphan_rate')}")
    if not signals_ok:
        ops_red_reasons.append(
            f"open LIVE issues={report.signals.get('open_live_issues')} "
            f"sentinel_crit={report.signals.get('sentinel_critical_lines')}"
        )
    if not side_ok:
        ops_red_reasons.append(
            f"gh-ish jobs bad status={report.side_effects.get('jobs_mentioning_gh_with_bad_status')}"
        )
    if not hygiene_ok:
        ops_red_reasons.append(
            f"nested_state={report.hygiene.get('nested_product_state_db_total')}"
        )

    report.scoreboard = {
        "hygiene": "GREEN" if hygiene_ok else "RED",
        "ops": "GREEN" if not ops_red_reasons else "RED",
        "ops_red_reasons": ops_red_reasons,
        "summary": (
            "hygiene GREEN / ops GREEN — quiet"
            if hygiene_ok and not ops_red_reasons
            else (
                f"hygiene {'GREEN' if hygiene_ok else 'RED'} / "
                f"ops {'GREEN' if not ops_red_reasons else 'RED'}: "
                + "; ".join(ops_red_reasons[:4])
            )
        ),
    }

    # Findings for Support Engineer
    findings = []
    if report.jobs.get("unknown_rate", 0) >= 0.25 and n_jobs >= 5:
        findings.append({
            "type": "platform_ops",
            "severity": "high",
            "summary": f"High job unknown rate {report.jobs['unknown_rate']:.0%} over {hours}h ({unknownish}/{n_jobs})",
            "detail": json.dumps(report.jobs.get("by_status"), indent=0)[:500],
            "signal_hash": f"ops-unknown-{hours}h",
        })
    if report.costs.get("orphan_rate", 0) >= 0.35 and len(costs) >= 5:
        findings.append({
            "type": "platform_ops",
            "severity": "medium",
            "summary": f"Cost orphan rate {report.costs['orphan_rate']:.0%} ({orphans}/{len(costs)} entries lack job_id match)",
            "detail": f"total_usd={tot_cost:.2f}",
            "signal_hash": f"ops-cost-orphan-{hours}h",
        })
    if live_issues:
        findings.append({
            "type": "platform_ops",
            "severity": "high",
            "summary": f"{len(live_issues)} open live-issue labelled GitHub issues",
            "detail": "; ".join(
                f"#{i.get('number')} {(i.get('title') or '')[:40]}" for i in live_issues[:5]
            ),
            "signal_hash": f"ops-live-issues-{len(live_issues)}",
        })
    if nested_total > 0:
        findings.append({
            "type": "platform_ops",
            "severity": "high",
            "summary": f"{nested_total} nested product state.db under ~/dev repos",
            "detail": json.dumps(nested_by_repo)[:400],
            "signal_hash": f"ops-nested-{nested_total}",
        })
    if sentinel_crit >= 5:
        findings.append({
            "type": "platform_ops",
            "severity": "medium",
            "summary": (
                f"{sentinel_crit} CRITICAL/FLATLINE sentinel lines in last "
                f"{sentinel_hours}h across repos"
            ),
            "detail": (
                f"files={sentinel_files} windowed={sentinel_crit} "
                f"lifetime={sentinel_crit_lifetime} "
                f"untimestamped={sentinel_untimestamped}"
            ),
            "signal_hash": f"ops-sentinel-{sentinel_hours}h-{sentinel_crit}",
        })
    report.findings = findings
    return report


def format_platform_report(report: PlatformReport) -> str:
    """Human-readable multi-section report."""
    lines = [
        f"SYNLYNK PLATFORM OPS  last {report.hours}h  @ {report.generated_at}",
        "━" * 56,
        "",
        f"SCOREBOARD  hygiene={report.scoreboard.get('hygiene')}  "
        f"ops={report.scoreboard.get('ops')}",
        f"  {report.scoreboard.get('summary')}",
        "",
        "L0 HYGIENE",
        f"  nested product state.db: {report.hygiene.get('nested_product_state_db_total')}",
        f"  dry matrix (synlynk-like repos): {report.hygiene.get('dry_matrix_by_repo')}",
        "",
        "L1 JOBS",
        f"  count={report.jobs.get('count')}  done={report.jobs.get('done')}  "
        f"failed={report.jobs.get('failed')}  unknownish={report.jobs.get('unknownish')}",
        f"  unknown_rate={report.jobs.get('unknown_rate')}  fail_rate={report.jobs.get('fail_rate')}",
        f"  by_status={report.jobs.get('by_status')}",
        f"  by_agent={report.jobs.get('by_agent')}",
        f"  dbs_scanned={report.jobs.get('dbs_scanned')}",
        "",
        "L2 COSTS",
        f"  entries={report.costs.get('entries')}  total_usd=${report.costs.get('total_usd')}",
        f"  tokens in={report.costs.get('input_tokens'):,}  out={report.costs.get('output_tokens'):,}",
        f"  orphan_entries={report.costs.get('orphan_entries')}  "
        f"orphan_rate={report.costs.get('orphan_rate')}",
        f"  by_agent={report.costs.get('by_agent')}",
        "",
        "L3 SIDE-EFFECTS",
        f"  {report.side_effects}",
        "",
        "L4 SIGNALS",
        f"  sentinel_crit={report.signals.get('sentinel_critical_lines')} "
        f"(last {report.signals.get('sentinel_window_hours')}h; "
        f"lifetime={report.signals.get('sentinel_critical_lines_lifetime')})  "
        f"open_LIVE={report.signals.get('open_live_issues')}",
        f"  live_samples={report.signals.get('live_issue_samples')}",
        "",
        "L5 WORKTREES",
        f"  {report.worktrees}",
        "",
        "L6 LIVE SMOKE (recorded)",
        f"  green={report.live_smoke.get('green')} red={report.live_smoke.get('red')}  "
        f"{report.live_smoke.get('note')}",
        "",
        "L7 ATTACH",
        f"  rows={report.attach.get('row_count')} zero_attach={report.attach.get('zero_attach_count')}",
        "",
        "FINDINGS (for Support Engineer)",
    ]
    if report.findings:
        for f in report.findings:
            lines.append(f"  [{f.get('severity', '?').upper()}] {f.get('summary')}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("RECENT JOBS (sample)")
    for j in report.job_samples[:15]:
        lines.append(
            f"  {j.get('completed_at') or j.get('started_at') or '?':20s} "
            f"{(j.get('agent') or '?'):8s} {(j.get('status') or '?'):12s} "
            f"{j.get('job_id')} {(j.get('task') or '')[:50]!r}"
        )
    lines.append("")
    lines.append(
        "NOTE: This report is machine-local (~/.synlynk/projects + ~/dev). "
        "It is not GitHub org billing. Hygiene GREEN does not imply ops GREEN."
    )
    return "\n".join(lines)


def cmd_ops_report(hours: int = 24, json_output: bool = False) -> int:
    """CLI entry: print platform ops report; exit 1 if ops scoreboard is RED."""
    report = collect_platform_report(hours=hours)
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(format_platform_report(report))
    return 0 if report.scoreboard.get("ops") == "GREEN" else 1
