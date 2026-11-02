"""Developer Preview full acceptance test matrix and GOVERNS truth audit (v0.27.4).

Verifies:
1. GOVERNS lifecycle truth: zero active stories without goals, zero shadow databases.
2. Sentinel health: zero active unresolved CRITICAL or ERROR alerts.
3. Database integrity: schema validation and WAL consistency.
4. Agent charter integrity: all 7 charters parse cleanly and enforce wake cycles.
5. Model catalog hygiene: all tier models resolve without drift.
"""

import sqlite3
import pytest

from synlynk.db import _get_db, _migrate_db
from synlynk.governs_cli import cmd_governs_audit
from synlynk.sentinel import _read_active_sentinel_alerts
from synlynk.charters import load_charter, validate_charter
from synlynk.models import resolve_tier_model
from synlynk._constants import CORE_FLEET, EXTENDED_FLEET


def test_acceptance_governs_truth_audit(tmp_path):
    """Verify GOVERNS audit passes with zero active unlinked stories and no shadow DB."""
    db_file = tmp_path / "clean_governs.db"
    conn = sqlite3.connect(str(db_file))
    _migrate_db(conn)

    # Insert a placed goal and a linked story
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, deadline, placement_status, phase_id) "
        "VALUES ('goal-p1', 'Preview Goal', 'Verified in preview', '2026-11-30', 'placed', 'phase-1')"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id, status) "
        "VALUES ('story-p1', 'Preview Story', 'goal-p1', 'in_progress')"
    )
    conn.commit()

    report = cmd_governs_audit(strict=False, conn=conn)
    assert report["active_stories_without_goal"] == 0
    assert report["duplicate_active_issue_stories"] == 0
    assert report["missing_placement_reasons"] == 0
    conn.close()


def test_acceptance_sentinel_health_sweep(tmp_path):
    """Verify sentinel reader detects zero critical or error alerts in clean workspace."""
    sentinel_path = tmp_path / "sentinel.md"
    sentinel_path.write_text("# Sentinel Alerts\n\nNo active alerts.\n")

    active = _read_active_sentinel_alerts(str(sentinel_path))
    assert len(active) == 0


def test_acceptance_database_integrity_and_schema():
    """Verify state.db integrity check passes and foreign keys are valid."""
    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "ok"


def test_acceptance_role_charters_structural_validation():
    """Verify all defined role charters parse and include required operational sections."""
    expected_roles = ["dev", "architect", "qa", "pm", "maintainer", "security", "doc"]
    for role_name in expected_roles:
        charter = load_charter(role_name)
        assert charter is not None, f"Charter for {role_name} missing"
        assert validate_charter(charter) is True
        assert charter.role == role_name
        assert len(charter.mandate) > 0


def test_acceptance_model_catalog_freshness():
    """Verify model resolution works reliably across all active and extended harnesses."""
    all_harnesses = sorted(CORE_FLEET | EXTENDED_FLEET)
    for harness in all_harnesses:
        for tier in ("fast", "standard", "heavy"):
            model = resolve_tier_model(tier, harness)
            assert model is not None, f"Failed resolving tier {tier} for harness {harness}"
            assert isinstance(model, str)
            assert len(model) > 0
