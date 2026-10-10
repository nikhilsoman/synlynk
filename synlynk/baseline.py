"""Baseline measurements for the CLI surface simplification rollout."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence


def explicit_flags(argv: Sequence[str]) -> list[str]:
    """Return option names explicitly present in a dispatch argv list.

    Values are deliberately not counted.  Repeated options (for example
    ``--requires``) remain repeated because the metric is flags per call.
    """
    flags = []
    for token in argv:
        if token == "--":
            break
        if token.startswith("--"):
            flags.append(token.split("=", 1)[0])
        elif token.startswith("-") and token != "-":
            flags.append(token)
    return flags


def dispatch_invocation_event(
    argv: Sequence[str], agent: str, job_id: str | None, timestamp: str | None = None
) -> dict:
    """Build the telemetry row for one successful CLI dispatch invocation."""
    flags = explicit_flags(argv)
    return {
        "type": "dispatch_invocation",
        "schema_version": 1,
        "timestamp": timestamp or time.strftime("%Y-%m-%d %H:%M:%S"),
        "agent": agent,
        "job_id": job_id,
        "explicit_flags": flags,
        "explicit_flag_count": len(flags),
    }


def load_telemetry(path: str | Path) -> list[dict]:
    """Load a telemetry array, tolerating a missing or malformed file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def dispatch_flag_samples(events: Iterable[dict]) -> tuple[list[int], int]:
    """Return measured flag counts and legacy dispatch rows without counts."""
    samples = []
    unavailable = 0
    for event in events:
        if event.get("type") not in {"dispatch", "dispatch_invocation"}:
            continue
        count = event.get("explicit_flag_count")
        if isinstance(count, int) and count >= 0:
            samples.append(count)
        else:
            unavailable += 1
    return samples, unavailable


def summarize_telemetry(events: Iterable[dict]) -> dict:
    """Build the machine-readable baseline summary from telemetry events."""
    rows = list(events)
    dispatch_rows = [
        event for event in rows
        if event.get("type") in {"dispatch", "dispatch_invocation"}
    ]
    # A live CLI dispatch emits both the historical lifecycle row and the new
    # invocation row. Count that job once, preferring the measured row.
    by_job = {}
    without_job = []
    for event in dispatch_rows:
        job_id = event.get("job_id")
        if job_id:
            by_job[job_id] = event if event.get("explicit_flag_count") is not None else by_job.get(job_id, event)
        else:
            without_job.append(event)
    canonical_rows = list(by_job.values()) + without_job
    samples, unavailable = dispatch_flag_samples(canonical_rows)
    return {
        "dispatch_events": len(canonical_rows),
        "dispatch_samples_with_explicit_flags": len(samples),
        "dispatch_samples_without_explicit_flags": unavailable,
        "explicit_flags_per_dispatch": {
            "median": statistics.median(samples) if samples else None,
            "samples": samples,
        },
    }


def run_onboarding(
    repo: str | Path,
    init_command: Sequence[str] | None = None,
    dispatch_command: Sequence[str] | None = None,
) -> dict:
    """Run a timestamped clean-install simulation and record its outcome.

    The dispatch command is caller-supplied so dogfood runs can use the
    harness and task appropriate to the local environment. A run is verified
    only when the dispatch process succeeds and emits the normal dispatch
    confirmation; previews are therefore not mislabeled as verified runs.
    """
    root = Path(repo).resolve()
    init_command = list(init_command or [sys.executable, "bin/synlynk.py", "init", "--yes"])
    dispatch_command = list(dispatch_command or [])
    started = time.time()
    env = os.environ.copy()
    env["SYNLYNK_STATE_DB_PATH"] = str(root / ".synlynk" / "state.db")
    init = subprocess.run(
        init_command, cwd=root, env=env, text=True, capture_output=True, check=False
    )
    dispatch = None
    if init.returncode == 0 and dispatch_command:
        dispatch = subprocess.run(
            dispatch_command, cwd=root, env=env, text=True, capture_output=True, check=False
        )
    finished = time.time()
    output = (dispatch.stdout + dispatch.stderr) if dispatch else ""
    verified = bool(
        dispatch
        and dispatch.returncode == 0
        and "dispatched" in output.lower()
        and "pid" in output.lower()
    )
    return {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "duration_seconds": round(finished - started, 3),
        "init_command": init_command,
        "init_exit_code": init.returncode,
        "dispatch_command": dispatch_command,
        "dispatch_exit_code": dispatch.returncode if dispatch else None,
        "verified_dispatch": verified,
    }


def render_markdown(summary: dict, onboarding_runs: Iterable[dict] = ()) -> str:
    """Render a compact report suitable for committing under docs/strategy."""
    metric = summary["explicit_flags_per_dispatch"]
    median = metric["median"] if metric["median"] is not None else "Unavailable"
    lines = [
        "# CLI Surface Baseline Metrics",
        "",
        f"Captured: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "",
        "## Dispatch flags",
        "",
        f"- Dispatch events in rolling telemetry: {summary['dispatch_events']}",
        f"- Events with explicit-flag telemetry: {summary['dispatch_samples_with_explicit_flags']}",
        f"- Legacy events without explicit-flag telemetry: {summary['dispatch_samples_without_explicit_flags']}",
        f"- Median explicit flags per dispatch: **{median}**",
        "",
        "Legacy rows are reported as unavailable rather than treated as zero; the "
        "instrumentation added for this baseline makes future runs measurable.",
        "",
        "## Dogfood onboarding runs",
        "",
    ]
    runs = list(onboarding_runs)
    if not runs:
        lines.append("No run recorded in this report.")
    else:
        lines.extend(
            f"- {run['started_at']}: {run['duration_seconds']}s; "
            f"verified dispatch: {'yes' if run['verified_dispatch'] else 'no'}"
            for run in runs
        )
    lines.append("")
    return "\n".join(lines)
