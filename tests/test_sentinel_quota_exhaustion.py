"""Tests that sentinel's QUOTA_EXHAUSTED detection actually corrects harness_quotas."""


def test_quota_exhausted_detection_calls_force_exhaust(project_dir):
    import synlynk as sl
    from synlynk.sentinel import check_sentinel_patterns

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "claude", "5h", limit_tokens=200_000, used_tokens=1_000, unit="tokens", conn=conn
    )

    check_sentinel_patterns(
        output_text="Error: rate limit exceeded for this billing period",
        exit_code=1,
        cmd="claude --print",
    )

    row = conn.execute(
        "SELECT limit_tokens, used_tokens FROM harness_quotas WHERE harness='claude' AND quota_type='5h'"
    ).fetchone()
    assert row[1] == row[0]


def test_quota_exhausted_detection_noop_when_no_match(project_dir):
    import synlynk as sl
    from synlynk.sentinel import check_sentinel_patterns

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "claude", "5h", limit_tokens=200_000, used_tokens=1_000, unit="tokens", conn=conn
    )

    check_sentinel_patterns(
        output_text="All good, task complete.", exit_code=0, cmd="claude --print"
    )

    row = conn.execute(
        "SELECT used_tokens FROM harness_quotas WHERE harness='claude' AND quota_type='5h'"
    ).fetchone()
    assert row[0] == 1_000
