"""Subscription-quota capture. Dollars stay in cost_entries."""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("synlynk.quota_capture")

DEFAULT_POLL_INTERVAL_SECONDS = 900
STALENESS_MULTIPLIER = 2
GROK_REFRESH_WAIT_SECONDS = 2.0

DEFAULT_REGISTRY: dict[str, dict] = {
    "claude": {
        "cli_usage_cmd": 'claude -p "/usage" --output-format text',
        "log_scrape": None,
        "has_5h_window": True,
        "interactive_pane_id": None,
    },
    "agy": {
        "cli_usage_cmd": 'agy -p "/usage" --output-format text',
        "log_scrape": None,
        "has_5h_window": True,
        "interactive_pane_id": None,
    },
    "codex": {
        "cli_usage_cmd": None,
        "log_scrape": {
            "path": "~/.codex/sessions/**/*.jsonl",
            "jq_filter": ".payload.rate_limits",
        },
        "has_5h_window": "unknown",
        "interactive_pane_id": None,
    },
    "grok": {
        "cli_usage_cmd": None,
        "log_scrape": {
            "path": "~/.grok/logs/unified.jsonl",
            "jq_filter": 'select(.msg == "billing: fetched credits config")',
        },
        "has_5h_window": False,
        "interactive_pane_id": None,
    },
}

_PERCENT_USED = re.compile(r"^\s*(\d+(?:\.\d+)?)%\s*used\s*$", re.IGNORECASE)
_ISO_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")


def load_registry(repo_path: str | None = None) -> dict[str, dict]:
    """Return the spec default, with a per-harness replace from quota_capture.json."""
    registry = json.loads(json.dumps(DEFAULT_REGISTRY))
    root = Path(repo_path) if repo_path is not None else Path.cwd()
    overlay_path = root / ".synlynk" / "quota_capture.json"
    if not overlay_path.is_file():
        return registry
    try:
        overlay = json.loads(overlay_path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.exception("ignoring unreadable quota capture overlay %s", overlay_path)
        return registry
    if not isinstance(overlay, dict):
        return registry
    for harness, entry in overlay.items():
        if harness == "poll_interval_seconds" or not isinstance(entry, dict):
            continue
        registry[harness] = entry
    return registry


@dataclass(frozen=True)
class WindowReading:
    window: str
    used_percent: float
    resets_at: str | None
    observed_at: str


def _resets_from_line(line: str) -> str | None:
    match = _ISO_STAMP.search(line)
    return match.group(0) if match else None


def _parse_headed_usage(text: str, *, collapse_max: bool, weekly_requires_all_models: bool) -> list[WindowReading]:
    current: str | None = None
    found: dict[str, WindowReading] = {}
    for raw in text.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered.startswith("current session"):
            current = "5h"
            continue
        if lowered.startswith("current week"):
            if weekly_requires_all_models and "all models" not in lowered:
                current = None
            else:
                current = "weekly"
            continue
        if current is None:
            continue
        percent = _PERCENT_USED.match(line)
        if percent:
            used = float(percent.group(1))
            previous = found.get(current)
            if previous is None or (collapse_max and used >= previous.used_percent) or not collapse_max:
                found[current] = WindowReading(current, used, previous.resets_at if previous else None, "")
            continue
        if lowered.startswith("resets"):
            stamp = _resets_from_line(line)
            if current in found and stamp:
                prev = found[current]
                found[current] = WindowReading(prev.window, prev.used_percent, stamp, prev.observed_at)
    return list(found.values())


def parse_claude_usage_text(text: str) -> list[WindowReading]:
    return _parse_headed_usage(text, collapse_max=False, weekly_requires_all_models=True)


def parse_agy_usage_text(text: str) -> list[WindowReading]:
    return _parse_headed_usage(text, collapse_max=True, weekly_requires_all_models=False)


def _unix_to_iso(value: object) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_codex_rate_limits(rate_limits: dict, observed_at: str) -> list[WindowReading]:
    readings: list[WindowReading] = []
    if not isinstance(rate_limits, dict):
        return readings
    for bucket_name in ("primary", "secondary"):
        bucket = rate_limits.get(bucket_name)
        if not isinstance(bucket, dict):
            continue
        minutes = bucket.get("window_minutes")
        if minutes == 10080:
            window = "weekly"
        elif minutes == 300:
            window = "5h"
        else:
            continue
        used = bucket.get("used_percent")
        if used is None:
            continue
        readings.append(
            WindowReading(window, float(used), _unix_to_iso(bucket.get("resets_at")), observed_at)
        )
    return readings


def parse_grok_billing_line(obj: dict) -> list[WindowReading]:
    if not isinstance(obj, dict) or obj.get("msg") != "billing: fetched credits config":
        return []
    config = (obj.get("ctx") or {}).get("config") or {}
    period = config.get("currentPeriod") or {}
    if period.get("type") != "USAGE_PERIOD_TYPE_WEEKLY":
        return []
    used = config.get("creditUsagePercent")
    observed = obj.get("ts")
    if used is None or not isinstance(observed, str):
        return []
    end = period.get("end")
    resets = end if isinstance(end, str) else None
    return [WindowReading("weekly", float(used), resets, observed)]


def insert_snapshots(
    conn,
    harness: str,
    readings: list[WindowReading],
    *,
    source: str,
    job_id: str | None,
    captured_at: str,
    staleness_by_window: dict[str, int],
) -> int:
    by_window: dict[str, WindowReading] = {}
    for reading in readings:
        if reading.window not in {"5h", "weekly"}:
            continue
        by_window[reading.window] = reading
    for window, reading in by_window.items():
        staleness = None if source == "task_boundary" else int(staleness_by_window.get(window, 0))
        conn.execute(
            """INSERT INTO quota_snapshots
               (harness, window, used_percent, resets_at, captured_at, source, staleness_seconds, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (harness, window, reading.used_percent, reading.resets_at, captured_at, source, staleness, job_id),
        )
    return len(by_window)


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def effective_age_seconds(row, now: datetime) -> float:
    captured = _parse_iso(row["captured_at"])
    age = (now - captured).total_seconds()
    extra = row["staleness_seconds"]
    if extra is None:
        return max(0.0, age)
    return max(0.0, age, float(extra))


def _latest_snapshot(conn, harness: str, window: str):
    try:
        return conn.execute(
            """SELECT harness, window, used_percent, resets_at, captured_at, source, staleness_seconds, job_id
                 FROM quota_snapshots
                WHERE lower(harness) = lower(?) AND window = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1""",
            (harness, window),
        ).fetchone()
    except Exception:
        return None


def _calibrate_percent(conn, harness: str, window: str) -> float | None:
    try:
        row = conn.execute(
            """SELECT used_tokens, limit_tokens FROM harness_quotas
                WHERE lower(harness) = lower(?) AND quota_type = ? AND unit = 'tokens'
                  AND limit_tokens > 0
                ORDER BY updated_at DESC
                LIMIT 1""",
            (harness, window),
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return (float(row["used_tokens"]) / float(row["limit_tokens"])) * 100.0


def window_status(conn, harness: str, window: str, *, now: datetime, registry: dict | None = None) -> dict:
    del registry
    threshold = DEFAULT_POLL_INTERVAL_SECONDS * STALENESS_MULTIPLIER
    row = _latest_snapshot(conn, harness, window)
    if row is not None and effective_age_seconds(row, now) <= threshold:
        return {
            "state": "known",
            "used_percent": float(row["used_percent"]),
            "reason": None,
            "source": row["source"],
            "resets_at": row["resets_at"],
            "captured_at": row["captured_at"],
        }
    calibrated = _calibrate_percent(conn, harness, window)
    if calibrated is not None:
        return {
            "state": "known",
            "used_percent": calibrated,
            "reason": None,
            "source": "calibrate",
            "resets_at": None,
            "captured_at": None,
        }
    reason = "stale" if row is not None else "missing"
    return {
        "state": "unknown",
        "used_percent": None,
        "reason": reason,
        "source": None,
        "resets_at": None,
        "captured_at": None,
    }


def weekly_cost_usd(conn, harness: str, *, now: datetime) -> float:
    cutoff = (now.date() - timedelta(days=6)).isoformat()
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_cost_usd), 0)
                 FROM cost_entries
                WHERE session_date >= ?
                  AND (lower(COALESCE(harness, agent)) = lower(?))""",
            (cutoff, harness),
        ).fetchone()
    except Exception:
        return 0.0
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])


def federated_rows(conn, *, now: datetime | None = None, registry: dict | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    registry = registry if registry is not None else load_registry()
    rows = []
    for harness in registry:
        cost = weekly_cost_usd(conn, harness, now=now)
        for window in ("weekly", "5h"):
            status = window_status(conn, harness, window, now=now, registry=registry)
            rows.append({
                "harness": harness,
                "window": window,
                "state": status["state"],
                "used_percent": status["used_percent"],
                "source": status["source"],
                "resets_at": status["resets_at"],
                "captured_at": status["captured_at"],
                "cost_7d_usd": cost,
                "reason": status["reason"],
            })
    return rows


def format_federated_text(rows: list[dict]) -> str:
    lines = ["harness  window  status   used_percent  source  cost_7d_usd  captured_at"]
    for row in rows:
        used = "—" if row["used_percent"] is None else f"{row['used_percent']:.1f}"
        source = row["source"] or "—"
        captured = row["captured_at"] or "—"
        lines.append(
            f"{row['harness']:<8} {row['window']:<7} {row['state']:<8} {used:<13} {source:<7} "
            f"{row['cost_7d_usd']:<11.2f} {captured}"
        )
    return "\n".join(lines)


def _open_db():
    from synlynk.db import _get_db
    return _get_db()


def _default_runner(argv: list[str], timeout: float) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"exit {proc.returncode}")
    return proc.stdout


def _now_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _reading_age_seconds(observed_at: str, now: datetime) -> int:
    try:
        observed = _parse_iso(observed_at)
    except ValueError:
        return 0
    return max(0, int((now - observed).total_seconds()))


def capture_cli_text(command: str, *, runner=None, timeout: float = 20) -> str:
    run = runner or _default_runner
    return run(shlex.split(command), timeout)


def _newest_codex_rate_limits(sessions_root: Path) -> tuple[dict, str] | None:
    if not sessions_root.is_dir():
        return None
    files = sorted(sessions_root.rglob("rollout-*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        last_payload = None
        last_ts = None
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            logger.exception("codex quota log unreadable: %s", path)
            continue
        for line in lines:
            line = line.strip()
            if not line or "rate_limits" not in line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = obj.get("payload") if isinstance(obj, dict) else None
            rate_limits = payload.get("rate_limits") if isinstance(payload, dict) else None
            if isinstance(rate_limits, dict):
                last_payload = rate_limits
                last_ts = obj.get("timestamp")
        if last_payload is not None:
            observed = last_ts if isinstance(last_ts, str) else _now_iso()
            return last_payload, observed
    return None


def _newest_grok_billing(log_path: Path) -> dict | None:
    if not log_path.is_file():
        return None
    last = None
    try:
        lines = log_path.read_text(errors="replace").splitlines()
    except OSError:
        logger.exception("grok quota log unreadable: %s", log_path)
        return None
    for line in lines:
        if "billing: fetched credits config" not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("msg") == "billing: fetched credits config":
            last = obj
    return last


def _codex_sessions_root(entry: dict) -> Path:
    scrape = entry.get("log_scrape") or {}
    configured = os.path.expanduser(scrape.get("path") or "")
    if "**" in configured:
        return Path(configured.split("**")[0]).expanduser()
    if configured:
        return Path(configured).expanduser()
    return Path(os.path.expanduser("~/.codex/sessions"))


def capture_harness(
    harness: str,
    *,
    source: str,
    job_id: str | None,
    conn,
    registry: dict | None = None,
    now: datetime | None = None,
    runner=None,
) -> int:
    registry = registry if registry is not None else load_registry()
    name = (harness or "").strip().lower()
    if name == "gemini":
        name = "agy"
    entry = registry.get(name)
    if entry is None or conn is None:
        return 0
    current = now or datetime.now(timezone.utc)
    readings: list[WindowReading] = []
    staleness: dict[str, int] = {}
    try:
        if entry.get("cli_usage_cmd"):
            text = capture_cli_text(entry["cli_usage_cmd"], runner=runner)
            if name == "agy":
                readings = parse_agy_usage_text(text)
            else:
                readings = parse_claude_usage_text(text)
            staleness = {item.window: 0 for item in readings}
        elif name == "codex":
            found = _newest_codex_rate_limits(_codex_sessions_root(entry))
            if found is None:
                return 0
            payload, observed = found
            readings = parse_codex_rate_limits(payload, observed)
            age = _reading_age_seconds(observed, current)
            staleness = {item.window: age for item in readings}
        elif name == "grok":
            scrape = entry.get("log_scrape") or {}
            log_path = Path(os.path.expanduser(scrape.get("path") or "~/.grok/logs/unified.jsonl"))
            obj = _newest_grok_billing(log_path)
            if obj is None:
                return 0
            readings = parse_grok_billing_line(obj)
            if readings:
                age = _reading_age_seconds(readings[0].observed_at, current)
                staleness = {item.window: age for item in readings}
        else:
            return 0
    except Exception:
        logger.exception("quota capture failed for %s", name)
        return 0
    if entry.get("has_5h_window") is False:
        readings = [item for item in readings if item.window != "5h"]
    if not readings:
        return 0
    return insert_snapshots(
        conn,
        name,
        readings,
        source=source,
        job_id=job_id,
        captured_at=_now_iso(current),
        staleness_by_window=staleness,
    )


def schedule_boundary_capture(harness: str, job_id: str | None) -> threading.Thread:
    def _run() -> None:
        conn = None
        try:
            conn = _open_db()
            capture_harness(harness, source="task_boundary", job_id=job_id, conn=conn)
            if conn is not None:
                conn.commit()
        except Exception:
            logger.exception("boundary quota capture failed for %s", harness)
        finally:
            if conn is not None:
                conn.close()

    thread = threading.Thread(target=_run, name=f"quota-boundary-{harness}", daemon=True)
    thread.start()
    return thread


def _normalize_harness_name(harness: str) -> str:
    name = os.path.basename(str(harness or "")).strip().lower()
    if name == "gemini":
        return "agy"
    return name


def on_exec_finished(cmd_args: list) -> None:
    if not cmd_args:
        return
    name = _normalize_harness_name(cmd_args[0])
    if name not in load_registry():
        return
    schedule_boundary_capture(name, None)


def on_job_terminal(harness: str, job_id: str, status: str) -> None:
    if status != "done":
        return
    name = _normalize_harness_name(harness)
    if name not in load_registry():
        return
    schedule_boundary_capture(name, job_id)


def note_exec_return(cmd_args: list, exit_code: int) -> int:
    try:
        on_exec_finished(cmd_args)
    except Exception:
        logger.exception("quota boundary schedule failed")
    return exit_code


def note_job_settled(*, settled: bool, harness: str | None, job_id: str, status: str) -> None:
    if not settled or not harness or status != "done":
        return
    try:
        on_job_terminal(harness, job_id, status)
    except Exception:
        logger.exception("quota boundary schedule failed for job %s", job_id)


def refresh_grok_pane(pane_id: str, *, runner=None, sleeper=None) -> None:
    run = runner or _default_runner
    pause = sleeper or time.sleep
    run(["herdr", "pane", "send-text", pane_id, "/usage"], 10)
    run(["herdr", "pane", "send-keys", pane_id, "Enter"], 10)
    pause(GROK_REFRESH_WAIT_SECONDS)


def _grok_line_age(obj: dict | None, now: datetime) -> float | None:
    if obj is None:
        return None
    readings = parse_grok_billing_line(obj)
    if not readings:
        return None
    return float(_reading_age_seconds(readings[0].observed_at, now))


def poll_once(
    *,
    conn=None,
    registry: dict | None = None,
    now: datetime | None = None,
    runner=None,
    sleeper=None,
) -> int:
    owns_conn = conn is None
    if owns_conn:
        conn = _open_db()
    current = now or datetime.now(timezone.utc)
    registry = registry if registry is not None else load_registry()
    written = 0
    try:
        for harness, entry in registry.items():
            try:
                if harness == "grok":
                    scrape = entry.get("log_scrape") or {}
                    log_path = Path(os.path.expanduser(scrape.get("path") or "~/.grok/logs/unified.jsonl"))
                    existing = _newest_grok_billing(log_path)
                    age = _grok_line_age(existing, current)
                    pane_id = entry.get("interactive_pane_id")
                    if pane_id and (age is None or age > DEFAULT_POLL_INTERVAL_SECONDS):
                        try:
                            refresh_grok_pane(pane_id, runner=runner, sleeper=sleeper)
                        except Exception:
                            logger.exception("grok pane refresh failed for %s", pane_id)
                written += capture_harness(
                    harness, source="poller", job_id=None, conn=conn,
                    registry=registry, now=current, runner=runner,
                )
            except Exception:
                logger.exception("quota poll failed for %s", harness)
        if conn is not None:
            conn.commit()
    finally:
        if owns_conn and conn is not None:
            conn.close()
    return written


def cmd_quota_federated(json_output: bool = False) -> None:
    conn = _open_db()
    try:
        rows = federated_rows(conn)
    finally:
        if conn is not None:
            conn.close()
    if json_output:
        print(json.dumps(rows, indent=2))
    else:
        print(format_federated_text(rows))


def prefer_harness_by_weekly_headroom(
    incumbent: str,
    fallbacks: list[str],
    conn,
    now: datetime | None = None,
    registry: dict | None = None,
) -> str:
    current = now or datetime.now(timezone.utc)
    registry = registry if registry is not None else load_registry()
    order = [incumbent]
    for name in fallbacks:
        if name and name not in order:
            order.append(name)
    eligible: list[tuple[float, int, str]] = []
    for harness in order:
        try:
            five = window_status(conn, harness, "5h", now=current, registry=registry)
            weekly = window_status(conn, harness, "weekly", now=current, registry=registry)
        except Exception:
            logger.exception("quota routing skipped %s", harness)
            continue
        if five["state"] == "known" and five["used_percent"] is not None and five["used_percent"] >= 100:
            continue
        if weekly["state"] != "known" or weekly["used_percent"] is None:
            continue
        tie = 0 if harness == incumbent else 1
        eligible.append((float(weekly["used_percent"]), tie, harness))
    if not eligible:
        return incumbent
    eligible.sort()
    return eligible[0][2]
