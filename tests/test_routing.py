import sqlite3

import pytest

from synlynk.routing import SAMPLE_SIZE_FLOOR, LiveQueryRouter


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT, pr_review_cycles REAL
        )
    """)
    conn.execute("""
        CREATE TABLE cost_entries (
            agent TEXT, type_id TEXT, total_cost_usd REAL
        )
    """)
    conn.execute("""
        CREATE TABLE routing_rotation_state (
            task_type TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT
        )
    """)
    return conn


def test_round_robins_below_sample_floor():
    conn = _make_db()
    router = LiveQueryRouter()
    picks = [router.select(["codex", "grok", "agy"], "implement", conn) for _ in range(6)]
    assert picks == ["codex", "grok", "agy", "codex", "grok", "agy"]


def test_ranks_by_score_at_or_above_floor():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', ?)", (f"s{i}", 1.0)
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', ?)", (f"g{i}", 3.0)
        )
    conn.commit()
    router = LiveQueryRouter()
    # codex has the lower (better) median pr_review_cycles, should win.
    assert router.select(["codex", "grok"], "implement", conn) == "codex"


def test_deterministic_tie_break_prefers_higher_sample_count_then_alphabetical():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'agy', 'implement', ?)", (f"a{i}", 2.0)
        )
    for i in range(SAMPLE_SIZE_FLOOR + 2):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', ?)", (f"c{i}", 2.0)
        )
    conn.commit()
    router = LiveQueryRouter()
    # Tied score (2.0 both); codex has more samples (7 vs 5) so it wins the tie.
    assert router.select(["agy", "codex"], "implement", conn) == "codex"


def test_round_robin_rotates_only_sub_floor_harnesses_in_a_mixed_set():
    """A harness that has already cleared SAMPLE_SIZE_FLOOR must not be
    rotated into by round-robin just because another harness in the same
    eligible set is still below the floor — round-robin is scoped to
    below_floor, not the full eligible_harnesses list (dec-8ed62afa)."""
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', ?)", (f"s{i}", 1.0)
        )
    conn.commit()
    router = LiveQueryRouter()
    # codex is at the floor already; grok and agy are below it. Only grok/agy
    # should ever be picked here — codex must never appear in these picks.
    picks = [router.select(["codex", "grok", "agy"], "implement", conn) for _ in range(4)]
    assert "codex" not in picks
    assert picks == ["grok", "agy", "grok", "agy"]


def test_single_eligible_harness_short_circuits():
    conn = _make_db()
    router = LiveQueryRouter()
    assert router.select(["codex"], "implement", conn) == "codex"


def test_empty_eligible_list_raises():
    conn = _make_db()
    router = LiveQueryRouter()
    with pytest.raises(ValueError):
        router.select([], "implement", conn)
