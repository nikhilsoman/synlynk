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


from synlynk.quota import resolve_burn_rate_multiplier


def _seed_cost_entries(conn, rows):
    """rows: list of (harness, model, input_tokens, output_tokens)."""
    for i, (harness, model, in_tok, out_tok) in enumerate(rows):
        conn.execute(
            "INSERT INTO cost_entries "
            "(session_date, agent, harness, model, input_tokens, output_tokens, "
            " cache_read_tokens, cost_source, job_id) "
            "VALUES ('2026-10-31', ?, ?, ?, ?, ?, 0, 'actual', ?)",
            (harness, harness, model, in_tok, out_tok, f"job-{harness}-{model}-{i}"),
        )
    conn.commit()


def test_resolve_burn_rate_multiplier_below_threshold_is_neutral(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed_cost_entries(conn, [("claude", "claude-opus-4-7", 10_000, 2_000)] * 4)
        assert resolve_burn_rate_multiplier("claude", "claude-opus-4-7", conn=conn) == 1.0
    finally:
        conn.close()


def test_resolve_burn_rate_multiplier_unknown_pair_is_neutral(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        assert resolve_burn_rate_multiplier("codex", "gpt-5-codex", conn=conn) == 1.0
    finally:
        conn.close()


def test_resolve_burn_rate_multiplier_computes_ratio_at_threshold(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        # Heavy model: 20,000 tokens/job avg, 5 samples (meets >=5 threshold).
        _seed_cost_entries(
            conn, [("claude", "claude-opus-4-7", 16_000, 4_000)] * 5
        )
        # Light model: 4,000 tokens/job avg, 5 samples.
        _seed_cost_entries(
            conn, [("claude", "claude-haiku-5-5", 3_200, 800)] * 5
        )
        # Harness-wide average across both models: (20000*5 + 4000*5) / 10 = 12,000
        multiplier = resolve_burn_rate_multiplier("claude", "claude-opus-4-7", conn=conn)
        assert multiplier == 20_000 / 12_000
    finally:
        conn.close()



from synlynk.quota import refresh_burn_rate_weights


def test_refresh_burn_rate_weights_writes_cache_row(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        _seed_cost_entries(conn, [("codex", "gpt-5-codex", 8_000, 2_000)] * 6)
        _seed_cost_entries(conn, [("codex", "gpt-5-codex-mini", 2_000, 500)] * 6)
        refresh_burn_rate_weights(conn=conn)
        row = conn.execute(
            "SELECT multiplier, sample_count FROM quota_burn_rate_weights "
            "WHERE harness='codex' AND model='gpt-5-codex'"
        ).fetchone()
        assert row is not None
        assert row[1] == 6
        assert row[0] == 10_000 / 6_250  # (10000*6 + 2500*6) / 12 = 6250
    finally:
        conn.close()
