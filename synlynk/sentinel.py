"""synlynk sentinel: alert writing, pattern detection, telemetry events."""

import json
import os
import re
import time
from typing import Optional

from synlynk._constants import QUOTA_PATTERNS


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


def _extract_auto_signals(log_text: str, started_at: str = None,
                           ended_at: str = None, exit_code: int = None) -> dict:
    """Extracts objective quality signals from a completed job's log text."""
    signals = {
        "test_pass_rate": None,
        "build_success": None,
        "duration_seconds": None,
        "test_count": None,
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


def check_sentinel_patterns(output_text: str = "", exit_code: int = 0,
                             cmd: str = "") -> None:
    """Detects flatline, success loop, and quota-exhausted; writes sentinel alerts."""
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


def sentinel_clear(severity: Optional[str] = None, code: Optional[str] = None) -> None:
    """Removes matching alerts from sentinel.md. No args = clear all structured alerts."""
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        print("  No sentinel file found.")
        return
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
        removed += 1

    with open(sentinel_file, "w") as f:
        f.writelines(kept)
    print(f"  Cleared {removed} alert(s).")
