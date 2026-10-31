"""Unit tests for cost_entries estimate-vs-actual drift tracking (v0.26.9)."""

import synlynk as sl


def test_cost_entries_has_estimate_columns(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
        assert "estimated_input_tokens" in cols
        assert "estimated_output_tokens" in cols
        assert "estimated_cost_usd" in cols
    finally:
        conn.close()
