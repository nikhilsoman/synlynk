"""Live job observability snapshot builder."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

OBSERVATORY_SNAPSHOT_PATH = os.path.join(".synlynk", "observatory-snapshot.json")
OBSERVATORY_CACHE_PATH = os.path.join(".synlynk", "viz-cache", "observatory-snapshot.json")
JOBS_FILE = os.path.join(".synlynk", "jobs.json")
TELEMETRY_FILE = os.path.join(".synlynk", "telemetry.json")


def _load_json(path: str, default):
    try:
        with open(path) as f:
            data = json.load(f)
        return data
    except Exception:
        return default


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _age_seconds(job: dict) -> Optional[int]:
    started_at = job.get("started_at") or job.get("started") or job.get("created_at")
    dt = _parse_dt(started_at)
    if dt is None:
        return None
    return max(0, int(time.time() - dt.timestamp()))


def _humanize_age(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    minutes, secs = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _job_repo_fallback() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    url = (result.stdout or "").strip().rstrip("/")
    if not url:
        return None
    if url.endswith(".git"):
        url = url[:-4]
    if "github.com/" in url:
        path = url.split("github.com/", 1)[1]
    elif "github.com:" in url:
        path = url.split("github.com:", 1)[1]
    else:
        return None
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def _normalize_stage(status: Any, stage: Any = None) -> Optional[str]:
    status_key = str(status or "").strip().lower()
    stage_key = str(stage or "").strip().lower()
    mapping = {
        "running": "running",
        "queued": "queued",
        "failed": "failed",
        "permission_denied": "failed",
        "error": "failed",
        "done": "done",
        "completed": "done",
        "success": "done",
    }
    if status_key in mapping:
        return mapping[status_key]
    if stage_key in mapping:
        return mapping[stage_key]
    if stage_key:
        return stage_key
    if status_key:
        return status_key
    return None


def _format_repo(job: dict) -> Optional[str]:
    repo = job.get("repo")
    if repo:
        return str(repo)
    return _job_repo_fallback()


def _coalesce_number(*values: Any) -> Optional[float]:
    for value in values:
        parsed = _safe_float(value)
        if parsed is not None:
            return parsed
    return None


def _coalesce_int(*values: Any) -> Optional[int]:
    for value in values:
        parsed = _safe_int(value)
        if parsed is not None:
            return parsed
    return None


def _merge_telemetry(telemetry_rows: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for row in telemetry_rows:
        job_id = row.get("job_id") or row.get("id")
        if not job_id:
            continue
        bucket = merged.setdefault(str(job_id), {})
        for key in ("cost_usd", "input_tokens", "output_tokens", "requests", "input_context_tokens"):
            value = row.get(key)
            if value is None:
                continue
            parsed = _safe_float(value) if key == "cost_usd" else _safe_int(value)
            if parsed is None:
                continue
            if key in bucket:
                bucket[key] = (bucket[key] or 0) + parsed
            else:
                bucket[key] = parsed
        for key in (
            "agent",
            "originating_agent",
            "executing_agent",
            "repo",
            "stage",
            "status",
            "log_path",
            "context_path",
            "input_context_tokens",
        ):
            if bucket.get(key) in (None, "") and row.get(key) not in (None, ""):
                bucket[key] = row.get(key)
    return merged


def _summarize_jobs(jobs: list[dict]) -> dict:
    rollups = {
        "total_cost": 0.0,
        "total_tokens": 0,
        "total_requests": 0,
        "active_count": 0,
    }
    for job in jobs:
        rollups["total_cost"] += float(job.get("cost_usd") or 0.0)
        rollups["total_tokens"] += int(job.get("input_tokens") or 0) + int(job.get("output_tokens") or 0)
        rollups["total_requests"] += int(job.get("requests") or 0)
        if job.get("status") in {"running", "queued"} or job.get("stage") in {"running", "queued"}:
            rollups["active_count"] += 1
    return rollups


def write_observatory_snapshot(snapshot: dict) -> None:
    try:
        os.makedirs(os.path.dirname(OBSERVATORY_SNAPSHOT_PATH), exist_ok=True)
        with open(OBSERVATORY_SNAPSHOT_PATH, "w") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        pass

    try:
        os.makedirs(os.path.dirname(OBSERVATORY_CACHE_PATH), exist_ok=True)
        with open(OBSERVATORY_CACHE_PATH, "w") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        pass


def build_job_observatory_snapshot(db_conn=None) -> dict:
    jobs_rows = _load_json(JOBS_FILE, default=[])
    telemetry_rows = _load_json(TELEMETRY_FILE, default=[])
    if not isinstance(jobs_rows, list):
        jobs_rows = []
    if not isinstance(telemetry_rows, list):
        telemetry_rows = []

    telemetry_by_job = _merge_telemetry([row for row in telemetry_rows if isinstance(row, dict)])
    fallback_repo = _job_repo_fallback()
    jobs: list[dict] = []

    for row in jobs_rows:
        if not isinstance(row, dict):
            continue
        job_id = row.get("id") or row.get("job_id")
        if not job_id:
            continue
        job_id = str(job_id)
        telemetry = telemetry_by_job.get(job_id, {})
        input_tokens = _coalesce_int(row.get("input_tokens"), telemetry.get("input_tokens"))
        output_tokens = _coalesce_int(row.get("output_tokens"), telemetry.get("output_tokens"))
        requests = _coalesce_int(row.get("requests"), telemetry.get("requests"))
        input_context_tokens = _coalesce_int(
            row.get("input_context_tokens"),
            row.get("context_tokens"),
            telemetry.get("input_context_tokens"),
        )
        cost_usd = _coalesce_number(row.get("cost_usd"), telemetry.get("cost_usd"))
        stage = _normalize_stage(row.get("status"), row.get("stage"))
        started_at = row.get("started_at") or row.get("started") or row.get("created_at")
        repo = _format_repo(row) or telemetry.get("repo") or fallback_repo
        agent = row.get("agent") or telemetry.get("executing_agent") or telemetry.get("agent")
        originating_agent = (
            row.get("originating_agent")
            or telemetry.get("originating_agent")
            or row.get("agent")
            or telemetry.get("agent")
        )
        job = {
            "id": job_id,
            "repo": repo,
            "agent": agent,
            "originating_agent": originating_agent,
            "stage": stage,
            "status": row.get("status"),
            "runtime_seconds": _age_seconds(row),
            "cost_usd": cost_usd,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "requests": requests,
            "input_context_tokens": input_context_tokens,
            "log_path": row.get("log_path") or row.get("log_file") or telemetry.get("log_path"),
            "context_path": row.get("context_path") or row.get("context_file") or telemetry.get("context_path"),
            "started_at": started_at,
        }
        jobs.append(job)

    jobs.sort(key=lambda job: ((job.get("repo") or "~"), (job.get("stage") or "~"), -(job.get("runtime_seconds") or 0)))

    repos_map: dict[str, list[dict]] = defaultdict(list)
    stage_map: dict[str, list[dict]] = defaultdict(list)
    for job in jobs:
        repos_map[str(job.get("repo") or "unknown")].append(job)
        stage_map[str(job.get("stage") or "unknown")].append(job)

    repos = []
    for repo_name, repo_jobs in sorted(repos_map.items(), key=lambda item: item[0]):
        repos.append({
            "repo": repo_name,
            "jobs": repo_jobs,
            "rollups": _summarize_jobs(repo_jobs),
            "stages": {
                stage: {
                    "jobs": stage_jobs,
                    "rollups": _summarize_jobs(stage_jobs),
                }
                for stage, stage_jobs in sorted(
                    defaultdict(list, {
                        stage: [job for job in repo_jobs if str(job.get("stage") or "unknown") == stage]
                        for stage in {str(job.get("stage") or "unknown") for job in repo_jobs}
                    }).items(),
                    key=lambda item: item[0],
                )
            },
        })

    stages = {
        stage: {
            "jobs": stage_jobs,
            "rollups": _summarize_jobs(stage_jobs),
        }
        for stage, stage_jobs in sorted(stage_map.items(), key=lambda item: item[0])
    }

    snapshot = {
        "jobs": jobs,
        "rollups": _summarize_jobs(jobs),
        "repos": repos,
        "stages": stages,
    }

    try:
        if db_conn is not None:
            db_conn.execute("SELECT 1")
    except Exception:
        pass

    return snapshot
