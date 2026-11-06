"""Unit tests for Greenfield Genesis Orchestrator (v0.28.5)."""
from __future__ import annotations

import os
import sqlite3
import pytest

from synlynk.greenfield import (
    STAGE_S0_FLEET,
    STAGE_S1_PM,
    STAGE_S2_ARCH,
    STAGE_S3_DECIDE,
    STAGE_S4_TPM,
    STAGE_S5_DEV_QA,
    STAGE_COMPLETED,
    STAGES,
    GreenfieldOrchestrator,
    create_or_resume_session,
    advance_stage,
    get_session,
)


def test_greenfield_session_lifecycle(tmp_path):
    """Verify session creation and sequential stage progression in SQLite."""
    db_file = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_file))
    from synlynk.db_schema import GREENFIELD_SESSIONS_SCHEMA
    conn.executescript(GREENFIELD_SESSIONS_SCHEMA)

    session = create_or_resume_session(
        conn,
        project_name="podcast-cli",
        raw_intent="Build an AI podcast digest CLI",
        fast_forward=False,
    )
    assert session["session_id"].startswith("gen-")
    assert session["current_stage"] == STAGE_S0_FLEET
    assert session["project_name"] == "podcast-cli"
    assert session["fast_forwarded"] == 0

    # Advance stage
    updated = advance_stage(conn, session["session_id"], STAGE_S1_PM)
    assert updated["current_stage"] == STAGE_S1_PM

    # Final stage completion
    completed = advance_stage(conn, session["session_id"], STAGE_COMPLETED)
    assert completed["current_stage"] == STAGE_COMPLETED
    assert completed["completed_at"] is not None

    fetched = get_session(conn, session["session_id"])
    assert fetched["current_stage"] == STAGE_COMPLETED
    conn.close()


def test_greenfield_orchestrator_end_to_end(tmp_path):
    """Verify full 6-stage genesis cycle generates governance artifacts and code scaffold."""
    logs = []
    orchestrator = GreenfieldOrchestrator(
        str(tmp_path),
        printer=lambda msg: logs.append(msg),
    )

    result = orchestrator.run(
        "Build an AI podcast digest CLI using Whisper and SQLite",
        project_name="podcast-digest",
        fast_forward=True,
    )

    assert result["status"] == "success"
    assert result["current_stage"] == STAGE_COMPLETED
    assert result["project_name"] == "podcast-digest"

    # Verify generated governance artifacts
    brief_file = tmp_path / "project-docs" / "brief.md"
    roadmap_file = tmp_path / "project-docs" / "roadmap.md"
    todo_file = tmp_path / "project-docs" / "todo.md"
    assert brief_file.exists()
    assert roadmap_file.exists()
    assert todo_file.exists()

    brief_text = brief_file.read_text(encoding="utf-8")
    assert "AI podcast digest CLI" in brief_text

    # Verify specs and decisions
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    assert specs_dir.exists()
    specs = list(specs_dir.glob("*-podcast-digest-design.md"))
    assert len(specs) == 1

    decisions_dir = tmp_path / "project-docs" / "decisions"
    assert decisions_dir.exists()
    decisions = list(decisions_dir.glob("*.md"))
    assert len(decisions) >= 1

    # Verify code scaffolding and initial test
    pkg_dir = tmp_path / "podcast_digest"
    tests_dir = tmp_path / "tests"
    assert (pkg_dir / "__init__.py").exists()
    assert (pkg_dir / "main.py").exists()
    assert (tests_dir / "test_podcast_digest.py").exists()

    # Verify rollup card printed
    assert any("PROJECT GENESIS COMPLETE" in log for log in logs)
