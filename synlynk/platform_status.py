"""Terminal platform-health rendering used by ``synlynk status --platform``.

The package-level compatibility exports are kept in :mod:`synlynk`; these
helpers use late package lookups because status also owns the package DB and
configuration helpers.
"""

import datetime as _dt
import json
import os
import shutil
import subprocess
import sys


def _pkg(name):
    import synlynk
    return getattr(synlynk, name)


def _load_telemetry_events() -> list:
    path = ".synlynk/telemetry.json"
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            events = json.load(f)
        return events if isinstance(events, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _parse_status_timestamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _dt.datetime.fromtimestamp(float(value), tz=_dt.timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def _humanize_ago(value) -> str:
    parsed = _parse_status_timestamp(value)
    if parsed is None:
        return "not probed"
    age = max(0, int((_dt.datetime.now(_dt.timezone.utc) - parsed).total_seconds()))
    if age < 60:
        return f"{age}s ago"
    if age < 3600:
        return f"{age // 60}m ago"
    if age < 86400:
        return f"{age // 3600}h ago"
    return f"{age // 86400}d ago"


def _load_platform_harness_rows() -> tuple:
    known = ["claude", "agy", "codex", "grok", "gemini"]
    try:
        conn = _pkg("_get_db")()
    except Exception:
        conn = None
    db_rows = []
    if conn is not None:
        try:
            db_rows = conn.execute(
                "SELECT harness_name, installed_version, last_probe_at, "
                "compliance_status AS probe_status, capability_hash "
                "FROM harness_records ORDER BY harness_name"
            ).fetchall()
        except Exception:
            pass
        finally:
            conn.close()
    if db_rows:
        return ([{
            "harness_name": name, "installed_version": version or "—",
            "last_probe_at": probed, "probe_status": status or "unknown",
            "capability_hash": digest or "", "installed": True,
        } for name, version, probed, status, digest in db_rows], "db")
    rows = []
    for name in known:
        path = shutil.which(name)
        version = "—"
        if path:
            try:
                result = subprocess.run([name, "--version"], capture_output=True,
                                        text=True, timeout=5)
                raw = (result.stdout or result.stderr or "").strip()
                if raw:
                    version = raw.split()[-1]
            except Exception:
                version = os.path.basename(path)
        rows.append({"harness_name": name, "installed_version": version,
                     "last_probe_at": None, "probe_status": "unknown",
                     "capability_hash": "", "installed": bool(path)})
    return rows, "which"


def _load_platform_drift_agents() -> tuple:
    path = ".synlynk/sentinel.md"
    if not os.path.exists(path):
        return set(), []
    try:
        with open(path) as f:
            lines = [line.strip() for line in f if "DRIFT" in line]
    except IOError:
        return set(), []
    agents = set()
    for line in lines:
        lower = line.lower()
        agents.update(name for name in ("claude", "agy", "codex", "grok", "gemini")
                      if name in lower)
    return agents, lines


def _load_platform_budget_pulse(events: list, limit_usd: float) -> tuple:
    now = _dt.datetime.now(_dt.timezone.utc)
    daily_cutoff, weekly_cutoff = now - _dt.timedelta(days=1), now - _dt.timedelta(days=7)
    daily = weekly = 0.0
    for event in events:
        cost = event.get("cost_usd")
        timestamp = _parse_status_timestamp(event.get("timestamp") or event.get("ts")
                                            or event.get("created_at"))
        if cost is None or timestamp is None:
            continue
        try:
            value = float(cost)
        except (TypeError, ValueError):
            continue
        if timestamp >= weekly_cutoff:
            weekly += value
        if timestamp >= daily_cutoff:
            daily += value
    remaining = max(0.0, limit_usd - weekly) if limit_usd else 0.0
    pct = weekly / limit_usd * 100.0 if limit_usd else 0.0
    return daily, weekly, remaining, pct


def _print_platform_table(title: str, headers: list, rows: list) -> None:
    print()
    print(f" {title}")
    if not rows:
        print("   (none active)")
        return
    widths = [len(header) for header in headers]
    rendered = [[str(value) for value in row] for row in rows]
    for row in rendered:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  " + "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    for row in rendered:
        print("  " + "  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def _print_platform_health() -> bool:
    events = _load_telemetry_events()
    config = _pkg("load_config")()
    limit = float(config.get("budget", {}).get("limit_usd", 0.0) or 0.0)
    daily, weekly, remaining, pct = _load_platform_budget_pulse(events, limit)
    drift_agents, drift_lines = _load_platform_drift_agents()
    rows, _source = _load_platform_harness_rows()
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"◆ synlynk platform health  {now}")
    compliance, availability = [], []
    for row in rows:
        name = row["harness_name"]
        status = "DRIFT" if name in drift_agents else "OK"
        icon = "⚠" if status == "DRIFT" else "✓"
        age = _humanize_ago(row.get("last_probe_at"))
        compliance.append([name, row.get("installed_version") or "—",
                           f"probed {age}" if age != "not probed" else age,
                           f"{icon} {status}"])
        if row.get("installed", False):
            known = "known" if row.get("capability_hash") else "unknown"
            availability.append([name, row.get("installed_version") or "—",
                                 f"✓ {known}" if known == "known" else "⚠ unknown"])
    _print_platform_table("HARNESSES", ["agent", "version", "probe", "compliance"], compliance)
    _print_platform_table("AGENT AVAILABILITY", ["agent", "version", "TC"], availability)
    print(); print(" BUDGET")
    print(f"   today: ${daily:.2f}  ·  week: ${weekly:.2f}  ·  remaining: ${remaining:.2f} / ${limit:.2f}  ·  {pct:.0f}% used")
    print(); print(" SENTINELS")
    if drift_lines:
        for line in drift_lines:
            print(f"   {line}")
    else:
        print("   (none active)")
    return bool(drift_lines) or (limit > 0 and weekly >= limit)
