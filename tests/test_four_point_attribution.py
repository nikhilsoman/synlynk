"""Tests for universal 4-point attribution mandate (Goal, Epic, Milestone, Arc)."""

from __future__ import annotations

import re
from pathlib import Path
import pytest


def test_recent_specs_and_plans_carry_four_point_attribution():
    """Verify that recent specs and plans carry goal, epic, milestone, and arc in frontmatter."""
    root = Path(__file__).resolve().parent.parent

    for doc_type in ("specs", "plans"):
        doc_dir = root / "docs" / "superpowers" / doc_type
        if not doc_dir.exists():
            continue

        # Check all markdown files authored for v0.25.x
        v025_files = [f for f in doc_dir.glob("*2026-10-2[4-9]*.md") if f.is_file()]
        for f in v025_files:
            content = f.read_text(encoding="utf-8")
            # Frontmatter check
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not match:
                # Check inline headers if YAML frontmatter omitted
                assert "Goal" in content or "goal:" in content or "Goals:" in content, f"{f.name} missing Goal"
                assert "Epic" in content or "epic:" in content, f"{f.name} missing Epic"
                assert "Release" in content or "milestone:" in content or "Release target:" in content, f"{f.name} missing Release/Milestone"
                continue

            fm = match.group(1)
            keys = {line.split(":")[0].strip().lower() for line in fm.splitlines() if ":" in line}
            assert "goal" in keys, f"{f.name} frontmatter missing 'goal'"
            assert "epic" in keys, f"{f.name} frontmatter missing 'epic'"
            assert "milestone" in keys or "release" in keys, f"{f.name} frontmatter missing 'milestone'"
            assert "arc" in keys, f"{f.name} frontmatter missing 'arc'"


def test_story_attribution_verification_helper(tmp_path, monkeypatch):
    """Verify that story validation verifies goal, epic, milestone, and arc coordinates."""
    import synlynk
    from synlynk.story_governance import verify_story_four_point_attribution

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO goals (goal_id, outcome, criterion) VALUES ('goal-test', 'Test Outcome', 'Criterion')")
        conn.execute(
            """INSERT INTO stories (story_id, title, goal_id, phase, engg_domain)
               VALUES ('story-valid', 'Valid work (#2458) [milestone:v0.25.6]', 'goal-test', 'build', 'governance')"""
        )
        conn.execute(
            """INSERT INTO stories (story_id, title, goal_id, phase)
               VALUES ('story-missing-goal', 'Missing goal', NULL, 'build')"""
        )
        conn.commit()
    finally:
        conn.close()

    conn = synlynk._get_db()
    try:
        valid_res = verify_story_four_point_attribution(conn, "story-valid")
        assert valid_res["valid"] is True
        assert valid_res["goal_id"] == "goal-test"

        invalid_res = verify_story_four_point_attribution(conn, "story-missing-goal")
        assert invalid_res["valid"] is False
        assert "missing_goal" in invalid_res["deficiencies"]
    finally:
        conn.close()
