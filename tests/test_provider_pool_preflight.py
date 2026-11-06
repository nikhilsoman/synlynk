"""Preflight for harness track, reservations, and credit pools (gh:#5012)."""

import pytest

import synlynk as sl
from synlynk.dispatch import _format_job_summary
from synlynk.quota import _open_reservation, provider_pool_preflight


@pytest.fixture
def db_conn(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        yield conn
    finally:
        conn.close()


def test_preflight_uses_the_model_track(db_conn):
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=50_000, used_tokens=0,
        track="gemini", model="gemini-3.8-flash-high", unit="tokens", conn=db_conn,
    )
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=80_000, used_tokens=0,
        track="claude_proxy", model="claude-opus-4-6-thinking", unit="tokens", conn=db_conn,
    )

    gemini = provider_pool_preflight(
        db_conn, "agy", "gemini-3.8-flash-high", estimated_tokens=60_000
    )
    claude = provider_pool_preflight(
        db_conn, "agy", "claude-opus-4-6-thinking", estimated_tokens=60_000
    )

    assert gemini["status"] == "exhausted"
    assert gemini["track"] == "gemini"
    assert claude["status"] == "ok"
    assert claude["track"] == "claude_proxy"


def test_same_track_reservation_blocks_the_next_job(db_conn):
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=50_000, used_tokens=0,
        track="gemini", model="gemini-3.8-flash-high", unit="tokens", conn=db_conn,
    )
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=80_000, used_tokens=0,
        track="claude_proxy", model="claude-opus-4-6-thinking", unit="tokens", conn=db_conn,
    )
    _open_reservation(
        db_conn, "agy", 40_000, scope="session", job_id="job-open", track="gemini"
    )

    gemini = provider_pool_preflight(
        db_conn, "agy", "gemini-3.8-flash-high", estimated_tokens=20_000
    )
    claude = provider_pool_preflight(
        db_conn, "agy", "claude-opus-4-6-thinking", estimated_tokens=20_000
    )

    assert gemini["status"] == "exhausted"
    assert claude["status"] == "ok"


def test_empty_credit_pool_blocks_with_token_headroom(db_conn):
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=db_conn
    )
    db_conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at, expires_at) "
        "VALUES ('codex', 10, 4, '2026-01-01', '2020-01-01')"
    )
    db_conn.commit()

    status = provider_pool_preflight(db_conn, "codex", "gpt-5.6-sol", estimated_tokens=1_000)

    assert status["status"] == "exhausted"
    assert status["reason"] == "credit_pool_exhausted"


def test_unexpired_credit_does_not_block(db_conn):
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=db_conn
    )
    db_conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('codex', 10, 4, '2026-01-01')"
    )
    db_conn.commit()

    status = provider_pool_preflight(db_conn, "codex", "gpt-5.6-sol", estimated_tokens=1_000)

    assert status["status"] == "ok"
    assert status["credit_remaining_usd"] == 4


def test_summary_names_partial_work_after_provider_rejection():
    log = 'AGY_ERROR: RESOURCE_EXHAUSTED (code 429) "Your AI credits balance is too low to continue."'
    partial = _format_job_summary(
        "job-fd10a508", "agy", "story-c4a30135", 1, 12.0, 47554, 6968, 0.25,
        files_touched=["synlynk/context_compaction.py", "tests/test_context_compaction.py"],
        log_text=log,
    )
    empty = _format_job_summary(
        "job-a439c076", "agy", "story-c4a30135", 1, 8.0, 103071, 3892, 0.37,
        files_touched=[],
        log_text=log,
    )

    assert "QUOTA_EXHAUSTED (partial work, 2 files)" in partial
    assert "partial and unusable" in partial
    assert "synlynk/context_compaction.py" in partial
    assert "QUOTA_EXHAUSTED (no files written)" in empty


def test_summary_keeps_a_clean_failure_label():
    summary = _format_job_summary(
        "job-ok", "agy", None, 1, 1.0, 10, 2, 0.01,
        files_touched=["synlynk/quota.py"],
        log_text="traceback: assertion failed",
    )
    assert "FAILED (exit 1)" in summary
    assert "QUOTA_EXHAUSTED" not in summary
