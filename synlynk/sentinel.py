"""synlynk sentinel: alert writing, pattern detection, telemetry events."""

import json
import os
import re
import subprocess
import time
from typing import Optional

from synlynk._constants import QUOTA_PATTERNS

_SENTINEL_ALERT_RE = re.compile(
    r"^- \[(?P<severity>[A-Z]+)\] \[(?P<timestamp>[^\]]+)\] "
    r"(?P<code>[A-Z0-9_]+): (?P<message>.*)$"
)
_SENTINEL_ALERT_LEGACY_RE = re.compile(
    r"^- \[(?P<timestamp>[^\]]+)\] (?P<code>[A-Z0-9_]+): (?P<message>.*)$"
)
_SENTINEL_VERSION_DRIFT_AGENT_RE = re.compile(
    r"^Agent ['\"](?P<agent>[^'\"]+)['\"] version changed:"
)


def _docs_dir() -> str:
    """Returns the configured project docs directory (defaults to 'project-docs')."""
    config_file = ".synlynk/config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                return json.load(f).get("project_docs_dir", "project-docs")
        except (json.JSONDecodeError, IOError):
            pass
    return "project-docs"


def log_telemetry_event(event: dict) -> None:
    """Appends a structured event to .synlynk/telemetry.json (capped at 100)."""
    telemetry_file = ".synlynk/telemetry.json"
    if not os.path.exists(".synlynk"):
        return
    data = []
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    data.append(event)
    data = data[-100:]
    with open(telemetry_file, "w") as f:
        json.dump(data, f, indent=2)


def _check_costs_freshness() -> None:
    """Warns if costs.md hasn't been updated in the current session (>1 hour)."""
    costs_file = os.path.join(_docs_dir(), "costs.md")
    if not os.path.exists(costs_file):
        return
    if time.time() - os.path.getmtime(costs_file) > 3600:
        print("  ⚠ costs.md not updated this session — AI may have missed logging")


def _write_sentinel_alert(severity: str, code: str, message: str, sentinel_path: Optional[str] = None) -> None:
    """Appends a structured alert line to .synlynk/sentinel.md."""
    sentinel_file = sentinel_path or ".synlynk/sentinel.md"
    if not sentinel_path and not os.path.exists(".synlynk"):
        return
    existing = ""
    if os.path.exists(sentinel_file):
        with open(sentinel_file) as f:
            existing = f.read()
    if "# Sentinel Alerts" not in existing:
        existing = "# Sentinel Alerts\n"
    ts = time.strftime('%Y-%m-%d %H:%M')
    line = f"- [{severity}] [{ts}] {code}: {message}\n"
    if sentinel_path:
        parent = os.path.dirname(sentinel_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
    with open(sentinel_file, "w") as f:
        f.write(existing + line)
    # #753: STALL / internal-timeout alerts must flip daemon_jobs off "running"
    # immediately — do not wait for the next manual `jobs reap` pass.
    if code in ("STALL_NO_OUTPUT", "HARNESS_INTERNAL_TIMEOUT"):
        try:
            from synlynk.jobs import auto_reap_job_from_sentinel
            auto_reap_job_from_sentinel(code, message)
        except Exception:
            pass


def _read_sentinel_alerts(severity: Optional[str] = None) -> list:
    """Returns alert lines from sentinel.md, optionally filtered by severity."""
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        return []
    alerts = []
    with open(sentinel_file) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("- ["):
                continue
            if severity is None:
                alerts.append(line)
            else:
                m = re.match(r'^- \[([A-Z]+)\]', line)
                if m and m.group(1) == severity:
                    alerts.append(line)
    return alerts


def _summarize_sentinel_alerts(alert_lines: list, max_alert_types: int = 20) -> list:
    """Collapses repeated alerts by message content and keeps the latest alert per group."""
    grouped = {}
    passthrough = []

    for raw_line in alert_lines:
        line = (raw_line or "").strip()
        if not line:
            continue
        match = _SENTINEL_ALERT_RE.match(line)
        legacy = False
        if not match:
            match = _SENTINEL_ALERT_LEGACY_RE.match(line)
            legacy = bool(match)
        if not match:
            passthrough.append(line)
            continue

        code = match.group("code")
        message = match.group("message")
        timestamp = match.group("timestamp")
        severity = match.groupdict().get("severity") or "INFO"
        key = (code, message)

        bucket = grouped.get(key)
        if bucket is None:
            grouped[key] = {
                "line": line,
                "count": 1,
                "timestamp": timestamp,
                "severity": severity,
                "legacy": legacy,
            }
            continue

        bucket["count"] += 1
        if timestamp >= bucket["timestamp"]:
            bucket.update({
                "line": line,
                "timestamp": timestamp,
                "severity": severity,
                "legacy": legacy,
            })

    summarized = []
    for bucket in grouped.values():
        line = bucket["line"]
        count = bucket["count"]
        if count > 1:
            line = f"{line} ({count} occurrences, most recent {bucket['timestamp']})"
        summarized.append((bucket["timestamp"], line))

    summarized.sort(key=lambda item: item[0], reverse=True)
    deduped = [line for _, line in summarized[:max_alert_types]]
    deduped.extend(passthrough)
    return deduped


def _extract_sentinel_agent(line: str) -> Optional[str]:
    """Returns the agent name embedded in a structured alert message, when present."""
    match = _SENTINEL_ALERT_RE.match(line) or _SENTINEL_ALERT_LEGACY_RE.match(line)
    if not match:
        return None
    message = match.group("message")
    drift = _SENTINEL_VERSION_DRIFT_AGENT_RE.match(message)
    if drift:
        return drift.group("agent")
    return None


def _worktree_branch_name(worktree_path):
    """Returns the current git branch for a worktree, or None when unavailable."""
    root = worktree_path or os.getcwd()
    if not os.path.isdir(root):
        return None
    try:
        result = subprocess.run(
            ["git", "-C", root, "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    branch = (result.stdout or "").strip()
    return branch or None


def _gh_pr_view_payload(worktree_path, worktree_branch):
    """Returns gh pr view JSON payload for the active branch, or None."""
    branch = worktree_branch or _worktree_branch_name(worktree_path)
    if not branch:
        return None
    root = worktree_path or os.getcwd()
    try:
        result = subprocess.run(
            ["gh", "pr", "view", branch, "--json", "reviews"],
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
        )
    except Exception:
        return None

    payload_text = (result.stdout or "").strip()
    if not payload_text:
        return None
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_pr_review_cycles(worktree_path=None, worktree_branch=None):
    """Counts review-request -> approval round trips from GH PR review data."""
    payload = _gh_pr_view_payload(worktree_path, worktree_branch)
    if not payload:
        return None
    reviews = payload.get("reviews")
    if not isinstance(reviews, list):
        return None

    events = []
    for review in reviews:
        if not isinstance(review, dict):
            continue
        state = (review.get("state") or review.get("reviewState") or "").strip().upper()
        if not state:
            continue
        ts = review.get("submittedAt") or review.get("createdAt") or ""
        events.append((ts, state))

    events.sort(key=lambda item: item[0] or "")
    cycles = 0
    awaiting_approval = False
    for _, state in events:
        if state == "CHANGES_REQUESTED":
            awaiting_approval = True
        elif state == "APPROVED" and awaiting_approval:
            cycles += 1
            awaiting_approval = False
    return cycles


def _extract_verified_by_ci(worktree_path=None, worktree_branch=None):
    """Returns CI outcome for the active branch when GH status data is available."""
    branch = worktree_branch or _worktree_branch_name(worktree_path)
    if not branch:
        return None
    root = worktree_path or os.getcwd()

    try:
        result = subprocess.run(
            ["gh", "pr", "checks", branch],
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
        )
    except Exception:
        result = None

    if result is not None:
        output = "\n".join(part for part in [result.stdout or "", result.stderr or ""] if part).lower()
        if any(phrase in output for phrase in ("no pull request", "no pull requests", "no checks", "not found")):
            return None
        if any(phrase in output for phrase in ("fail", "failure", "errored")):
            return False
        if result.returncode == 0 and any(phrase in output for phrase in ("pass", "success", "succeeded")):
            return True
        if result.returncode == 0 and not output.strip():
            return True

    try:
        result = subprocess.run(
            ["gh", "run", "list", "--branch", branch, "--limit", "1", "--json", "status,conclusion"],
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
        )
    except Exception:
        return None

    payload_text = (result.stdout or "").strip()
    if not payload_text:
        return None
    try:
        runs = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(runs, list) or not runs:
        return None
    run = runs[0]
    if not isinstance(run, dict):
        return None

    status = str(run.get("status") or "").lower()
    conclusion = str(run.get("conclusion") or "").lower()
    if status and status != "completed":
        return None
    if conclusion in ("success", "neutral", "skipped"):
        return True
    if conclusion in ("failure", "cancelled", "timed_out", "action_required"):
        return False
    return None


def _extract_auto_signals(log_text: str, started_at: str = None,
                           ended_at: str = None, exit_code: int = None,
                           worktree_path=None, worktree_branch=None) -> dict:
    """Extracts objective quality signals from a completed job's log text."""
    signals = {
        "test_pass_rate": None,
        "build_success": None,
        "duration_seconds": None,
        "test_count": None,
        "pr_review_cycles": None,
        "verified_by_ci": None,
    }

    patterns = [
        r"(\d+)\s+passed.*?(\d+)\s+(?:failed|error)",
        r"Tests:\s+(\d+)\s+passed.*?(\d+)\s+failed",
        r"(\d+)/(\d+)\s+tests?\s+passed",
    ]
    for pat in patterns:
        m = re.search(pat, log_text, re.IGNORECASE)
        if m:
            passed = int(m.group(1))
            second = int(m.group(2))
            if "passed" in pat and "failed" in pat:
                total = passed + second
            else:
                total = second
            signals["test_pass_rate"] = passed / total if total else None
            signals["test_count"] = passed
            break

    if signals["test_pass_rate"] is None:
        m = re.search(r"(\d+)\s+passed", log_text, re.IGNORECASE)
        if m and "failed" not in log_text.lower() and "error" not in log_text.lower():
            signals["test_pass_rate"] = 1.0
            signals["test_count"] = int(m.group(1))

    if exit_code is not None:
        signals["build_success"] = (exit_code == 0)

    if started_at and ended_at:
        try:
            fmt = "%Y-%m-%dT%H:%M:%S"
            import datetime as _dt
            delta = _dt.datetime.strptime(ended_at, fmt) - _dt.datetime.strptime(started_at, fmt)
            signals["duration_seconds"] = delta.total_seconds()
        except Exception:
            pass

    signals["pr_review_cycles"] = _extract_pr_review_cycles(worktree_path, worktree_branch)
    signals["verified_by_ci"] = _extract_verified_by_ci(worktree_path, worktree_branch)

    return signals


def _extract_compliance_tags(output_text: str) -> dict:
    """Scans agent output for compliance evidence. Returns a dict of bool flags."""
    lower = output_text.lower()
    import re as _re

    ran_tests_patterns = [
        r"\btests\s+pass",
        r"\bpassed\b",
        r"\bpytest\b",
        r"\btest\s+suite\b",
        r"\brunning\s+tests\b",
    ]
    verify_patterns = [
        r"\bverif",
        r"\blgtm\b",
        r"\breviewed\b",
        r"\bchecked\b",
    ]
    ran_tests = any(_re.search(pat, lower) for pat in ran_tests_patterns)
    verify_before_commit = any(_re.search(pat, lower) for pat in verify_patterns)
    return {
        "ran_tests": ran_tests,
        "verify_before_commit": verify_before_commit,
    }


def check_model_rates_freshness() -> None:
    """Sentinel check for model rate table staleness.
    Writes a STALE_MODEL_RATES alert if rates are None or older than 90 days.
    """
    from synlynk.costs import _RATES_PATH, _load_model_rates
    if not os.path.exists(_RATES_PATH):
        return
    rates = _load_model_rates()
    rates_updated_at = rates.get("rates_updated_at")
    if not rates_updated_at:
        _write_sentinel_alert(
            "WARN", "STALE_MODEL_RATES",
            "Model rates have never been updated (using hardcoded defaults)."
        )
        return
    try:
        t_parsed = time.mktime(time.strptime(rates_updated_at, "%Y-%m-%d"))
        age_days = (time.time() - t_parsed) / 86400
    except (ValueError, TypeError):
        _write_sentinel_alert(
            "WARN", "STALE_MODEL_RATES",
            f"Model rates have invalid timestamp: {rates_updated_at}."
        )
        return
    if age_days > 90:
        _write_sentinel_alert(
            "WARN", "STALE_MODEL_RATES",
            f"Model rates are stale (updated {rates_updated_at}, {int(age_days)} days ago)."
        )


def check_sentinel_patterns(output_text: str = "", exit_code: int = 0,
                             cmd: str = "") -> None:
    """Detects flatline, success loop, and quota-exhausted; writes sentinel alerts."""
    check_model_rates_freshness()
    telemetry_file = ".synlynk/telemetry.json"
    data = []
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    execs = [e for e in data if e.get("type") == "exec"]

    if len(execs) >= 3:
        last3 = execs[-3:]
        if (all(e.get("exit_code", 0) != 0 for e in last3) and
                all(e.get("command") == last3[0].get("command") for e in last3)):
            fail_cmd = last3[0].get("command", "unknown")
            _write_sentinel_alert(
                "CRITICAL", "FLATLINE",
                f"`{fail_cmd}` failed 3 times in a row — possible hallucination loop."
            )
            print(f"\n  \U0001f6a8 [FLATLINE] `{fail_cmd}` failed 3x — consider manual intervention.")

    if len(execs) >= 5:
        last5 = execs[-5:]
        if (all(e.get("exit_code", 1) == 0 for e in last5) and
                all(e.get("command") == last5[0].get("command") for e in last5)):
            ts_first = last5[0].get("_ts", 0)
            ts_last = last5[-1].get("_ts", 0)
            window_min = (ts_last - ts_first) / 60 if ts_first else 999
            if window_min < 10:
                _write_sentinel_alert(
                    "WARN", "SUCCESS_LOOP",
                    f"Same command succeeded 5x in {window_min:.1f} min — "
                    "possible automated loop burning tokens."
                )
                print(f"\n  ⚠ [SUCCESS_LOOP] Same command 5x in {window_min:.1f} min.")

    if output_text:
        lower = output_text.lower()
        for phrase in QUOTA_PATTERNS:
            if phrase.lower() in lower:
                cli = cmd.split()[0] if cmd else "agent"
                _write_sentinel_alert(
                    "CRITICAL", "QUOTA_EXHAUSTED",
                    f"`{cli}` — matched \"{phrase}\". "
                    "Check plan limits or switch agent CLI."
                )
                print(f"\n  \U0001f6a8 [QUOTA_EXHAUSTED] Matched \"{phrase}\" in output.")
                try:
                    from synlynk import _get_db, _force_exhaust_quota
                    _quota_conn = _get_db()
                    try:
                        _force_exhaust_quota(_quota_conn, cli, "5h")
                    finally:
                        _quota_conn.close()
                except Exception:
                    pass
                break

    if output_text and exit_code == 0:
        tags = _extract_compliance_tags(output_text)
        if not tags["ran_tests"] and not tags["verify_before_commit"]:
            _write_sentinel_alert(
                "INFO", "VERIFY_SKIP",
                "Job exited 0 but no test or verify evidence found in output. "
                "Review before commit and capture verification signals next time."
            )
            print("  ℹ [VERIFY_SKIP] No test/verify evidence (informational — see sentinel.md)")


def sentinel_list() -> None:
    """Prints all active sentinel alerts."""
    alerts = _read_sentinel_alerts()
    if not alerts:
        print("  No active sentinel alerts.")
        return
    print(f"  {len(alerts)} active alert(s):")
    for a in alerts:
        print(f"    {a}")


def _clear_sentinel_alerts(severity: Optional[str] = None, code: Optional[str] = None,
                           agent: Optional[str] = None, sentinel_file: str = ".synlynk/sentinel.md") -> int:
    """Removes matching alerts from sentinel.md and returns the number removed."""
    if not os.path.exists(sentinel_file):
        return 0
    with open(sentinel_file) as f:
        lines = f.readlines()

    kept = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- ["):
            kept.append(line)
            continue
        m = re.match(r'^- \[([A-Z]+)\]', stripped)
        if not m:
            kept.append(line)
            continue
        line_sev = m.group(1)
        if severity and line_sev != severity:
            kept.append(line)
            continue
        if code and code not in stripped:
            kept.append(line)
            continue
        if agent and _extract_sentinel_agent(stripped) != agent:
            kept.append(line)
            continue
        removed += 1

    if removed > 0:
        with open(sentinel_file, "w") as f:
            f.writelines(kept)
    return removed


def sentinel_clear(severity: Optional[str] = None, code: Optional[str] = None,
                   agent: Optional[str] = None) -> None:
    """Removes matching alerts from sentinel.md. No args = clear all structured alerts."""
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        print("  No sentinel file found.")
        return
    removed = _clear_sentinel_alerts(severity=severity, code=code, agent=agent, sentinel_file=sentinel_file)
    print(f"  Cleared {removed} alert(s).")
