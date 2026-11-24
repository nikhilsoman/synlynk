import sqlite3

import pytest

from synlynk.routing import SAMPLE_SIZE_FLOOR, LiveQueryRouter, is_calibrated


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT, signal_source TEXT,
            pr_review_cycles REAL, dispatch_rework INTEGER, micro_rework INTEGER,
            duration_vs_estimate REAL, correct INTEGER
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
            updated_at TEXT, exploration_spend_usd REAL NOT NULL DEFAULT 0
        )
    """)
    return conn


def test_composite_score_uses_normalized_components_and_neutral_imputation():
    conn = _make_db()
    for harness, correct_values, cycles, rework, duration, cost in (
        ("codex", [1, 1, 1, 0, 0], 1.0, (0, 0), 1.0, 10.0),
        ("grok", [1, 1, 1, 1, 1], 3.0, (1, 0), 3.0, 30.0),
        ("agy", [None] * 5, None, (0, 0), 1.0, 20.0),
    ):
        for i, correct in enumerate(correct_values):
            conn.execute(
                "INSERT INTO capability_ratings "
                "(story_id, agent, discipline, pr_review_cycles, dispatch_rework, "
                "micro_rework, duration_vs_estimate, correct) VALUES (?, ?, 'implement', ?, ?, ?, ?, ?)",
                (f"{harness}-{i}", harness, cycles, rework[0], rework[1], duration, correct),
            )
        conn.execute(
            "INSERT INTO cost_entries (agent, type_id, total_cost_usd) VALUES (?, 'implement', ?)",
            (harness, cost),
        )
    conn.commit()

    score = LiveQueryRouter()._score(
        conn, "agy", "implement", ["codex", "grok", "agy"]
    )

    # agy receives the median success ratio (.8) and median review cycles (2.0),
    # rather than a rewarding zero for either missing signal.
    assert score == pytest.approx(17 / 12)


def test_composite_score_drops_degenerate_success_term():
    conn = _make_db()
    for harness in ("codex", "grok"):
        for i in range(SAMPLE_SIZE_FLOOR):
            conn.execute(
                "INSERT INTO capability_ratings "
                "(story_id, agent, discipline, correct) VALUES (?, ?, 'implement', NULL)",
                (f"{harness}-{i}", harness),
            )
    conn.commit()

    components = LiveQueryRouter()._score_components(
        conn, "implement", ["codex", "grok"]
    )

    assert components["success_ratio"] == {"codex": 1.0, "grok": 1.0}
    assert components["normalized"]["success_deficit"] == {"codex": 0.0, "grok": 0.0}


def test_composite_score_is_scale_invariant_for_cost_and_duration():
    def seeded(scale):
        conn = _make_db()
        for harness, cost, duration in (("codex", 10.0, 1.0), ("grok", 30.0, 3.0)):
            for i in range(SAMPLE_SIZE_FLOOR):
                conn.execute(
                    "INSERT INTO capability_ratings "
                    "(story_id, agent, discipline, correct, duration_vs_estimate) "
                    "VALUES (?, ?, 'implement', 1, ?)",
                    (f"{harness}-{i}", harness, duration * scale),
                )
            conn.execute(
                "INSERT INTO cost_entries (agent, type_id, total_cost_usd) VALUES (?, 'implement', ?)",
                (harness, cost * scale),
            )
        conn.commit()
        return conn

    router = LiveQueryRouter()
    base = [router._score(seeded(1), h, "implement", ["codex", "grok"]) for h in ("codex", "grok")]
    scaled = [router._score(seeded(1000), h, "implement", ["codex", "grok"]) for h in ("codex", "grok")]
    assert base[0] < base[1]
    assert scaled[0] < scaled[1]


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


def test_round_robin_skips_a_sub_floor_harness_at_the_exploration_spend_cap():
    conn = _make_db()
    conn.execute(
        "INSERT INTO cost_entries (agent, type_id, total_cost_usd) VALUES (?, ?, ?)",
        ("codex", "implement", 10.0),
    )
    conn.commit()

    router = LiveQueryRouter()

    assert router.select(["codex", "grok"], "implement", conn) == "grok"


def test_round_robin_updates_cached_exploration_spend_from_cost_ledger():
    conn = _make_db()
    conn.execute(
        "INSERT INTO cost_entries (agent, type_id, total_cost_usd) VALUES (?, ?, ?)",
        ("codex", "implement", 1.25),
    )
    conn.commit()

    router = LiveQueryRouter()
    assert router.select(["codex", "grok"], "implement", conn) == "codex"

    row = conn.execute(
        "SELECT exploration_spend_usd FROM routing_rotation_state WHERE task_type=?",
        ("implement",),
    ).fetchone()
    assert row[0] == 1.25


def test_calibration_ignores_baseline_seed_rows_per_harness_and_task_type():
    conn = _make_db()
    for i in range(SAMPLE_SIZE_FLOOR):
        conn.execute(
            "INSERT INTO capability_ratings "
            "(story_id, agent, discipline, signal_source, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 'baseline_seed', ?)",
            (f"seed-{i}", 1.0),
        )
    for i in range(SAMPLE_SIZE_FLOOR - 1):
        conn.execute(
            "INSERT INTO capability_ratings "
            "(story_id, agent, discipline, signal_source, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 'auto', ?)",
            (f"real-{i}", 1.0),
        )
    conn.commit()

    assert is_calibrated("codex", "implement", conn) is False
    assert LiveQueryRouter().select(["codex", "grok"], "implement", conn) == "codex"

    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, discipline, signal_source, pr_review_cycles) "
        "VALUES ('real-5', 'codex', 'implement', 'verifier', 1.0)"
    )
    conn.commit()

    assert is_calibrated("codex", "implement", conn) is True
