"""Unit tests for per-harness/model burn-rate weighting (v0.26.9)."""

import synlynk as sl


def test_quota_burn_rate_weights_table_exists(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        conn.execute(
            "INSERT INTO quota_burn_rate_weights (harness, model, multiplier, sample_count) "
            "VALUES ('claude', 'claude-opus-4-7', 1.8, 12)"
        )
        conn.commit()
        row = conn.execute(
            "SELECT harness, model, multiplier, sample_count FROM quota_burn_rate_weights "
            "WHERE harness='claude' AND model='claude-opus-4-7'"
        ).fetchone()
        assert row == ("claude", "claude-opus-4-7", 1.8, 12)
    finally:
        conn.close()
