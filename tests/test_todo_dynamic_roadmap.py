import os
import sqlite3
import pytest
from synlynk.db import _generate_todo_md, _write_generated_project_doc


def test_todo_dynamic_roadmap_and_goal_derivation(project_dir, monkeypatch):
    """Verify _generate_todo_md dynamically resolves active roadmap arcs and goals

    instead of relying on stale hardcoded tuples like 'v1.0.0-preview' or 'goal-eacab0dc'.
    (Regression test for #5289 / #5288).
    """
    from synlynk import _get_db

    conn = _get_db()

    # Setup Approach C derived views or underlying tables
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY,
            goal_id TEXT UNIQUE,
            outcome TEXT,
            status TEXT DEFAULT 'active',
            kind TEXT DEFAULT 'feature',
            placement_status TEXT DEFAULT 'placed',
            arc_version TEXT,
            phase_title TEXT,
            notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS roadmap_arcs (
            id INTEGER PRIMARY KEY,
            version TEXT UNIQUE,
            title TEXT,
            status TEXT DEFAULT 'in_progress'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS roadmap_phases (
            id INTEGER PRIMARY KEY,
            arc_version TEXT,
            title TEXT,
            story_id TEXT,
            status TEXT DEFAULT 'in_progress'
        )
        """
    )

    # Insert an active arc and phase
    conn.execute("INSERT OR REPLACE INTO roadmap_arcs (version, title, status) VALUES ('v0.36.0', 'Horizon 1 Autonomy', 'in_progress')")
    conn.execute("INSERT OR REPLACE INTO roadmap_phases (arc_version, phase_title, story_id, status) VALUES ('v0.36.0', 'Phase 1 JIT Context', 'story-phase', 'in_progress')")

    # Insert an active placed goal and an unplaced legacy loop goal (like goal-eacab0dc)
    conn.execute("INSERT OR REPLACE INTO goals (goal_id, outcome, criterion, status, kind, placement_status) VALUES ('goal-active-placed', 'Active Placed Goal', 'criterion', 'active', 'feature', 'placed')")
    conn.execute("INSERT OR REPLACE INTO goals (goal_id, outcome, criterion, status, kind, placement_status) VALUES ('goal-eacab0dc', 'Legacy Loop Goal', 'criterion', 'active', 'loop', 'unresolved')")

    # Insert stories with inverted timestamps so timestamp sorting alone cannot pass:
    # 1. story-legacy: attached to legacy unresolved goal goal-eacab0dc, newest timestamp
    # 2. story-placed: attached to active placed goal, older timestamp
    # 3. story-phase: attached to active roadmap phase v0.36.0, oldest timestamp
    conn.execute(
        """
        INSERT INTO stories (story_id, title, status, engg_domain, goal_id, created_at)
        VALUES ('story-legacy', 'Legacy Loop Task', 'open', 'devops', 'goal-eacab0dc', '2026-11-15 12:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO stories (story_id, title, status, engg_domain, goal_id, created_at)
        VALUES ('story-placed', 'Placed Goal Task', 'open', 'backend', 'goal-active-placed', '2026-11-15 11:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO stories (story_id, title, status, engg_domain, goal_id, created_at)
        VALUES ('story-phase', 'Horizon 1 Task', 'in_progress', 'backend', 'goal-active-placed', '2026-11-15 10:00:00')
        """
    )
    conn.commit()
    conn.close()

    # Generate todo.md
    _generate_todo_md()

    todo_file = os.path.join(project_dir, "project-docs", "todo.md")
    assert os.path.exists(todo_file), "todo.md was not created"

    with open(todo_file, "r") as f:
        content = f.read()

    lines = [line.strip() for line in content.splitlines() if line.startswith("- [")]
    assert len(lines) >= 3, f"Expected at least 3 tasks, got: {lines}"

    # story-phase must be first (priority_group 0)
    assert "story-phase" in lines[0], f"Expected story-phase at top, got: {lines[0]}"
    # story-placed must be second (priority_group 1)
    assert "story-placed" in lines[1], f"Expected story-placed second, got: {lines[1]}"
    # story-legacy must be third (priority_group 2)
    assert "story-legacy" in lines[2], f"Expected story-legacy third, got: {lines[2]}"
