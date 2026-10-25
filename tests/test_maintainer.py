from datetime import datetime, timezone
import pytest

from synlynk.maintainer import (
    triage_sentinel_alerts,
    format_triage_issue,
    probe_reproduction,
)


def test_triage_sentinel_alerts_groups_and_ranks_by_severity_and_frequency(tmp_path):
    path = tmp_path / "sentinel.md"
    path.write_text(
        "# Sentinel Alerts\n"
        "- [CRITICAL] [2026-10-25 10:00:00 UTC] SEV1_FAULT: Crash during fork [occurrences: 2; first seen: 2026-10-25 10:00:00 UTC; last seen: 2026-10-25 10:00:00 UTC]\n"
        "- [WARN] [2026-10-25 12:00:00 UTC] TOKEN_BLOAT: High tokens [occurrences: 5; first seen: 2026-10-25 12:00:00 UTC; last seen: 2026-10-25 12:00:00 UTC]\n"
        "- [INFO] [2026-10-25 14:00:00 UTC] NOTICE: Routine pulse [occurrences: 1; first seen: 2026-10-25 14:00:00 UTC; last seen: 2026-10-25 14:00:00 UTC]\n"
    )

    groups = triage_sentinel_alerts(path=str(path), max_age_days=7)
    assert len(groups) == 3

    # CRITICAL should rank first despite lower count
    assert groups[0]["code"] == "SEV1_FAULT"
    assert groups[0]["severity"] == "CRITICAL"
    assert groups[0]["total_occurrences"] == 2

    # WARN should rank second with 5 occurrences
    assert groups[1]["code"] == "TOKEN_BLOAT"
    assert groups[1]["severity"] == "WARN"
    assert groups[1]["total_occurrences"] == 5


def test_format_triage_issue_contains_standard_sections():
    group = {
        "fingerprint": "CRITICAL:SEV1_FAULT",
        "severity": "CRITICAL",
        "code": "SEV1_FAULT",
        "total_occurrences": 3,
        "first_seen": "2026-10-25 10:00:00 UTC",
        "last_seen": "2026-10-25 12:00:00 UTC",
        "sample_messages": ["Crash during fork in JWT minting"],
    }
    body = format_triage_issue(group)
    assert "[Maintainer Triage] SEV1_FAULT" in body
    assert "## Intent" in body
    assert "## Context" in body
    assert "## Reproduction Recipe" in body
    assert "## Acceptance Criteria" in body
    assert "CRITICAL:SEV1_FAULT" in body
    assert "Crash during fork in JWT minting" in body


def test_probe_reproduction_executes_check(tmp_path):
    group = {
        "code": "SEV1_FAULT",
        "severity": "CRITICAL",
        "fingerprint": "CRITICAL:SEV1_FAULT",
    }
    res = probe_reproduction(group, workspace_root=str(tmp_path))
    assert isinstance(res, dict)
    assert "reproduced" in res
    assert "output" in res
