import re
from datetime import datetime, timezone
import pytest
from synlynk.sentinel import _format_sentinel_alert, _parse_sentinel_alert


def test_sentinel_alert_format_and_parse_with_constitution_law():
    """Verify sentinel alerts format and parse constitution_law field correctly."""
    now = datetime.now(timezone.utc)
    # Format with explicit constitution_law
    line = _format_sentinel_alert(
        severity="CRITICAL",
        code="UNAUTHORIZED_TOKEN",
        message="Personal GitHub token used in dispatched session",
        occurrences=1,
        first_seen=now,
        last_seen=now,
        constitution_law="law-1",
    )
    assert "constitution_law: law-1" in line

    parsed = _parse_sentinel_alert(line)
    assert parsed is not None
    assert parsed["code"] == "UNAUTHORIZED_TOKEN"
    assert parsed["constitution_law"] == "law-1"


def test_sentinel_alert_automatic_law_inference():
    """Verify default sentinel alert codes automatically infer constitutional law if omitted."""
    now = datetime.now(timezone.utc)
    # Token bloat maps to law-3
    line3 = _format_sentinel_alert("WARN", "TOKEN_BLOAT", "Prompt tokens exceeded threshold", 1, now, now)
    parsed3 = _parse_sentinel_alert(line3)
    assert parsed3["constitution_law"] == "law-3"

    # Circuit breaker maps to law-3
    line_cb = _format_sentinel_alert("CRITICAL", "CIRCUIT_BREAKER", "Execution halted", 1, now, now)
    parsed_cb = _parse_sentinel_alert(line_cb)
    assert parsed_cb["constitution_law"] == "law-3"

    # Verify skip maps to law-2
    line2 = _format_sentinel_alert("WARN", "VERIFY_SKIP", "No test evidence found", 1, now, now)
    parsed2 = _parse_sentinel_alert(line2)
    assert parsed2["constitution_law"] == "law-2"


def test_rca_constitution_law_tagging():
    """Verify that Sev1 RCA docs can be parsed and validated for constitution_law header."""
    from synlynk.constitution import get_law

    rca_text = """# RCA: LIVE-31 — Dispatched jobs raw gh

**Date:** 2026-11-14
**Severity:** Sev1
**Status:** Confirmed
**Constitution Law:** law-1

## Root Cause
Attribution failed.
"""
    m = re.search(r"\*\*Constitution Law:\*\*\s*([a-zA-Z0-9_\-]+)", rca_text, re.IGNORECASE)
    assert m is not None
    law_id = m.group(1).lower()
    assert get_law(law_id) is not None
    assert get_law(law_id).id == "law-1"
