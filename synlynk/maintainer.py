"""Autonomous maintainer issue burndown classifier and sentinel maintenance loop."""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from typing import List, Optional

from synlynk.sentinel import _iter_sentinel_alerts, _normalize_sentinel_severity

_REMEDIATION_TOPICS = (
    "invariant 1",
    "circuit breaker",
    "daemon supervision",
)

SEVERITY_RANKS = {
    "CRITICAL": 4,
    "ERROR": 3,
    "WARN": 2,
    "INFO": 1,
}


def is_issue_remediated(issue_text: str, commit_messages: List[str]) -> bool:
    """Return True if a commit message remediates the same topic as the issue."""
    issue_lower = issue_text.lower()
    for msg in commit_messages:
        msg_lower = msg.lower()
        for topic in _REMEDIATION_TOPICS:
            if topic in issue_lower and topic in msg_lower:
                return True
        if "circuit breaker" in issue_lower and "live-19" in msg_lower:
            return True
    return False


def triage_sentinel_alerts(path: Optional[str] = None, max_age_days: int = 7) -> list[dict]:
    """Parse, deduplicate, and rank recurring sentinel alerts by severity and frequency."""
    alerts = _iter_sentinel_alerts(path=path, active_only=True)
    if not alerts:
        return []

    now = datetime.now(timezone.utc)
    groups: dict[str, dict] = {}

    for alert in alerts:
        last_seen = alert.get("last_seen_dt") or alert.get("timestamp_dt")
        if last_seen is not None and (now - last_seen).total_seconds() > (max_age_days * 86400):
            continue

        sev = _normalize_sentinel_severity(alert.get("severity") or "INFO")
        code = (alert.get("code") or "GENERAL").strip().upper()
        fingerprint = f"{sev}:{code}"

        occurrences = int(alert.get("occurrences") or 1)
        first_seen_str = str(alert.get("first_seen") or alert.get("timestamp") or "unknown")
        last_seen_str = str(alert.get("last_seen") or alert.get("timestamp") or "unknown")
        message = str(alert.get("message") or alert.get("raw_line") or "").strip()

        if fingerprint not in groups:
            groups[fingerprint] = {
                "fingerprint": fingerprint,
                "severity": sev,
                "code": code,
                "total_occurrences": occurrences,
                "first_seen": first_seen_str,
                "last_seen": last_seen_str,
                "sample_messages": [message] if message else [],
                "alerts": [alert],
            }
        else:
            g = groups[fingerprint]
            g["total_occurrences"] += occurrences
            g["last_seen"] = last_seen_str
            if message and message not in g["sample_messages"]:
                g["sample_messages"].append(message)
            g["alerts"].append(alert)

    ranked = list(groups.values())
    ranked.sort(
        key=lambda g: (SEVERITY_RANKS.get(g["severity"], 0), g["total_occurrences"]),
        reverse=True,
    )
    return ranked


def format_triage_issue(group: dict) -> str:
    """Format structured GitHub issue body for a recurring sentinel fault group."""
    code = group.get("code", "GENERAL")
    sev = group.get("severity", "INFO")
    fingerprint = group.get("fingerprint", f"{sev}:{code}")
    occurrences = group.get("total_occurrences", 1)
    first_seen = group.get("first_seen", "unknown")
    last_seen = group.get("last_seen", "unknown")
    samples = "\n".join(f"- {msg}" for msg in group.get("sample_messages", [])[:5]) or "- No detailed messages."

    return f"""# [Maintainer Triage] {code}: recurring {sev.lower()} sentinel fault

## Intent
Automated triage by workspace Maintainer agent for recurring sentinel fault `{code}`.

## Context
- **Severity:** `{sev}`
- **Fingerprint:** `{fingerprint}`
- **Total Occurrences:** {occurrences}
- **First Seen:** `{first_seen}`
- **Last Seen:** `{last_seen}`

## Diagnostic Evidence
```
{samples}
```

## Reproduction Recipe
1. Verify sentinel alert state: `synlynk sentinel list`
2. Run focused reproduction test: `pytest -k "{code.lower()}"`
3. Check recent daemon logs: `tail -n 100 .synlynk/daemon.log`

## Acceptance Criteria
- [ ] Root cause identified and reproduction test committed.
- [ ] Minimal fix implemented without architectural scope creep.
- [ ] Sentinel alert cleared via `synlynk sentinel clear --code {code}`.
"""


def probe_reproduction(group: dict, workspace_root: Optional[str] = None) -> dict:
    """Execute reproduction probe in a scratch or local workspace."""
    code = str(group.get("code") or "").lower()
    root = workspace_root or os.getcwd()

    cmd = ["pytest", "-k", code]
    try:
        res = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        reproduced = res.returncode != 0
        return {
            "reproduced": reproduced,
            "exit_code": res.returncode,
            "output": (res.stdout + res.stderr)[:2000],
        }
    except Exception as exc:
        return {
            "reproduced": False,
            "exit_code": 1,
            "output": f"Probe error: {exc}",
        }
