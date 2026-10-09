import sqlite3
import pytest

from synlynk.capability import (
    capability_score,
    expected_value,
    route_expected_value,
    update_capability_score,
)


def test_beta_update_records_success_and_failure():
    conn = sqlite3.connect(":memory:")
    update_capability_score("model-a", "codex", "cli", True, conn=conn)
    result = update_capability_score("model-a", "codex", "cli", False, conn=conn)
    assert result["alpha"] == pytest.approx(2)
    assert result["beta"] == pytest.approx(2)
    assert result["success_probability"] == pytest.approx(0.5)


def test_beta_evidence_decays_toward_prior():
    conn = sqlite3.connect(":memory:")
    update_capability_score("model-a", "codex", "cli", True,
                            conn=conn, observed_at="2026-01-01T00:00:00+00:00")
    result = update_capability_score("model-a", "codex", "cli", False,
                                     conn=conn, observed_at="2026-01-31T00:00:00+00:00")
    # One half-life has elapsed: old alpha=2/beta=1 shrinks to 1.5/1.0,
    # then the failure increments beta.
    assert result["alpha"] == pytest.approx(1.5)
    assert result["beta"] == pytest.approx(2.0)


def test_expected_value_and_router_choose_evidence_based_candidate():
    conn = sqlite3.connect(":memory:")
    for _ in range(4):
        update_capability_score("codex", "codex", "cli", True, conn=conn)
    update_capability_score("agy", "agy", "cli", False, conn=conn)
    assert expected_value(.8, 2, 1, 1, .5) == pytest.approx(1.0666667)
    result = route_expected_value(["codex", "agy"], "cli", conn=conn)
    assert result["harness"] == "codex"


def _ensure_cost_entries(conn):
    """cost_entries is created by the db.py migration, not ``_DB_SCHEMA``."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            harness TEXT,
            story_id TEXT,
            total_cost_usd REAL,
            cost_source TEXT NOT NULL,
            pr_number INTEGER
        )"""
    )


def test_ranked_harness_for_task_promotes_candidate_with_better_metrics():
    from synlynk.db_schema import _DB_SCHEMA, _DB_SCORES_VIEW
    from synlynk.capability import ranked_harness_for_task

    conn = sqlite3.connect(":memory:")
    conn.executescript(_DB_SCHEMA)
    conn.executescript(_DB_SCORES_VIEW)
    _ensure_cost_entries(conn)

    # Incumbent "codex": 5 samples, pr_review_cycles=3 each, cost=$10 each.
    for i in range(5):
        story_id = f"story-codex-{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'codex', 'implement', 3)",
            (story_id,),
        )
        conn.execute(
            "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd) "
            "VALUES ('2026-10-01', 'codex', ?, 'test', 10.0)",
            (story_id,),
        )
    # Challenger "grok": 5 samples, pr_review_cycles=1 each (better), cost=$4 each (better).
    for i in range(5):
        story_id = f"story-grok-{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1)",
            (story_id,),
        )
        conn.execute(
            "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd) "
            "VALUES ('2026-10-01', 'grok', ?, 'test', 4.0)",
            (story_id,),
        )
    conn.commit()

    result = ranked_harness_for_task("implement", ["codex", "grok"], conn=conn)
    assert result == "grok"


def test_ranked_harness_for_task_falls_back_below_sample_size():
    from synlynk.db_schema import _DB_SCHEMA, _DB_SCORES_VIEW
    from synlynk.capability import ranked_harness_for_task

    conn = sqlite3.connect(":memory:")
    conn.executescript(_DB_SCHEMA)
    conn.executescript(_DB_SCORES_VIEW)
    _ensure_cost_entries(conn)

    # Challenger "grok" only has 2 samples (below min_sample_size=5), even
    # though its metrics would otherwise win.
    for i in range(2):
        story_id = f"story-grok-{i}"
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, discipline, pr_review_cycles) "
            "VALUES (?, 'grok', 'implement', 1)",
            (story_id,),
        )
        conn.execute(
            "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd) "
            "VALUES ('2026-10-01', 'grok', ?, 'test', 4.0)",
            (story_id,),
        )
    conn.commit()

    result = ranked_harness_for_task("implement", ["codex", "grok"], conn=conn)
    assert result is None


def test_discipline_for_task_type_known_mapping():
    from synlynk.capability import _discipline_for_task_type

    assert _discipline_for_task_type("implement") == "backend"
    assert _discipline_for_task_type("test") == "testing"
    assert _discipline_for_task_type("review") == "architecture"


def test_discipline_for_task_type_unknown_returns_none():
    from synlynk.capability import _discipline_for_task_type

    assert _discipline_for_task_type("not-a-real-task-type") is None


def test_median_cost_per_pr_sums_rows_sharing_a_pr_before_median():
    from synlynk.capability import _median_cost_per_pr

    conn = sqlite3.connect(":memory:")
    _ensure_cost_entries(conn)
    conn.execute(
        "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd, pr_number) "
        "VALUES ('2026-10-01', 'codex', 's1', 'test', 6.0, 100)"
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd, pr_number) "
        "VALUES ('2026-10-01', 'codex', 's1', 'test', 3.0, 100)"
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd, pr_number) "
        "VALUES ('2026-10-02', 'codex', 's2', 'test', 5.0, 101)"
    )
    conn.commit()

    assert _median_cost_per_pr(conn, "codex") == pytest.approx(7.0)


def test_median_cost_per_pr_ignores_null_pr_number():
    from synlynk.capability import _median_cost_per_pr

    conn = sqlite3.connect(":memory:")
    _ensure_cost_entries(conn)
    conn.execute(
        "INSERT INTO cost_entries (session_date, harness, story_id, cost_source, total_cost_usd, pr_number) "
        "VALUES ('2026-10-01', 'codex', 's1', 'test', 999.0, NULL)"
    )
    conn.commit()

    assert _median_cost_per_pr(conn, "codex") is None
