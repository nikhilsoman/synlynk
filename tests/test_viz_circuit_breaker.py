"""Unit tests for Vizor circuit breaker badge and styling (Invariant 2)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.viz import generate_overview_html
from synlynk.jobs import STATUS_CIRCUIT_BREAKER_TRIPPED


def test_viz_renders_circuit_breaker_badge():
    data = {
        "workspace": {"name": "test-ws", "updated_at": "2026-09-27"},
        "jobs": [
            {
                "id": "job-cb-viz-test",
                "agent": "codex",
                "task": "Runaway worker test",
                "status": STATUS_CIRCUIT_BREAKER_TRIPPED,
                "circuit_breaker_reason": "Token limit breached: 350000 > 300000",
            }
        ],
        "telemetry": {},
    }

    html = generate_overview_html(data, port=7331)

    assert "status-chip circuit-breaker" in html
    assert "⚡ BREAKER" in html
    assert ".status-chip.circuit-breaker" in html
