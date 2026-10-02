"""End-to-End integration tests for LIVE-19 and LIVE-20."""

import json
import os
import pytest
import synlynk as sl
from synlynk.circuit_breaker import evaluate_job_circuit_breaker, CircuitBreakerResult
from synlynk.costs import cmd_cost_true_up, cmd_cost_billing
import synlynk.jobs as jobs_mod


def test_e2e_dispatched_worker_clean_exit_under_token_pressure(tmp_path, monkeypatch):
    """LIVE-19 E2E: Worker with large tokens (>5M) exits 0 cleanly without tripping breaker."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db_file = os.path.join(tmp_path, ".synlynk", "state.db")
    monkeypatch.setattr(sl, "DB_PATH", db_file)
    monkeypatch.setattr(sl, "_is_migrated", lambda: True)

    conn = sl._get_db()
    sl._migrate_db(conn)
    conn.close()

    # Configure quad-harness subscription billing
    with open(".synlynk/config.json", "w") as f:
        json.dump(
            {
                "budget": {"limit_usd": 100.0, "limit_requests": 1000},
                "harness_billing": {
                    "claude": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "codex": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "agy": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "grok": {"payment_mode": "subscription", "monthly_base_fee_usd": 30.0},
                },
            },
            f,
        )

    # Worker job specification with 6M tokens (exceeds default 5M ceiling)
    in_tokens = 4_500_000
    out_tokens = 1_500_000
    pid = 99999
    log_file = os.path.join(tmp_path, "job.log")
    with open(log_file, "w") as f:
        f.write("Completed cleanly with prompt tokens 4500000 and completion tokens 1500000")

    job = {
        "id": "job-live19-e2e-001",
        "agent": "claude",
        "status": "running",
        "pid": pid,
        "started_at": "2026-10-02T00:00:00",
        "story_id": None,
        "log_file": log_file,
    }

    monkeypatch.setattr(sl, "extract_tokens", lambda *args, **kwargs: (in_tokens, out_tokens))

    # When circuit breaker evaluates this job:
    # Since process has terminated cleanly (pid 99999 is dead), _kill_process_tree returns killed=False
    cb_result = evaluate_job_circuit_breaker(
        job,
        skip_identity_check_for_test=True,
    )
    # Crucial assertion for LIVE-19:
    # Process is already dead, so process_killed is False and tripped is False (preserves clean exit)
    assert not cb_result.process_killed
    assert not cb_result.tripped

    sentinel_alerts = []
    saved_jobs = []

    monkeypatch.setattr(jobs_mod, "_load_jobs", lambda: [job])
    monkeypatch.setattr(jobs_mod, "_save_jobs", lambda jobs: saved_jobs.append(jobs))
    monkeypatch.setattr(jobs_mod, "_write_sentinel_alert", lambda *args, **kwargs: sentinel_alerts.append(args))
    monkeypatch.setattr(sl, "_check_job_stall", lambda *args: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda *args, **kwargs: (in_tokens, out_tokens))
    monkeypatch.setattr(sl, "_write_job_summary", lambda *args, **kwargs: "")
    monkeypatch.setattr(sl, "_worktree_files_touched", lambda *args: [])
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *args: None, raising=False)
    monkeypatch.setattr(os, "waitpid", lambda p, opts: (p, 0))

    jobs_mod._reconcile_jobs_unlocked()

    # Verify job record preserved clean exit
    assert job["status"] == "completed"
    assert job["exit_code"] == 0
    assert len(sentinel_alerts) == 0

    # Record cost update
    sl.update_costs(
        command="claude exec",
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        duration=15.0,
        agent="claude",
        story_id=None,
    )

    # Verify cost entry written to state.db with mode='subscription'
    conn = sl._get_db()
    row = conn.execute(
        "SELECT payment_mode, api_equivalent_usd, actual_usd FROM cost_entries WHERE agent='claude'"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "subscription"
    assert row[1] > 0.0  # API equivalent calculated


def test_e2e_cost_true_up_reconciles_against_quad_harness_base(tmp_path, monkeypatch):
    """LIVE-20 E2E: true-up reconciles against $90.00 quad-harness baseline."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db_file = os.path.join(tmp_path, ".synlynk", "state.db")
    monkeypatch.setattr(sl, "DB_PATH", db_file)
    monkeypatch.setattr(sl, "_is_migrated", lambda: True)

    conn = sl._get_db()
    sl._migrate_db(conn)
    conn.close()

    with open(".synlynk/config.json", "w") as f:
        json.dump(
            {
                "budget": {"limit_usd": 100.0, "limit_requests": 1000},
                "harness_billing": {
                    "claude": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "codex": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "agy": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "grok": {"payment_mode": "subscription", "monthly_base_fee_usd": 30.0},
                },
            },
            f,
        )

    # Pre-seed some actual spend during 2026-10
    from synlynk.db import _insert_cost_row
    _insert_cost_row(
        session_date="2026-10-01 10:00",
        agent="claude",
        model="claude-3-7-sonnet",
        input_tokens=100_000,
        output_tokens=20_000,
        total_cost_usd=10.0,
        cost_source="estimated_manual",
        story_id=None,
        api_equivalent_usd=25.0,
        actual_usd=10.0,
        payment_mode="subscription",
    )
    _insert_cost_row(
        session_date="2026-10-02 12:00",
        agent="grok",
        model="grok-3",
        input_tokens=50_000,
        output_tokens=10_000,
        total_cost_usd=5.0,
        cost_source="estimated_manual",
        story_id=None,
        api_equivalent_usd=15.0,
        actual_usd=5.0,
        payment_mode="subscription",
    )

    result = cmd_cost_true_up(month="2026-10")
    # Total billed base = 20 + 20 + 20 + 30 = 90.00
    # Total recorded actual = 10.0 + 5.0 = 15.00
    # Variance = 90.00 - 15.00 = 75.00
    assert result["month"] == "2026-10"
    assert result["billed_usd"] == pytest.approx(90.0)
    assert result["recorded_usd"] == pytest.approx(15.0)
    assert result["variance_usd"] == pytest.approx(75.0)

    # Verify reconciliation row inserted
    conn = sl._get_db()
    c = conn.execute("SELECT SUM(actual_usd) FROM cost_entries WHERE session_date LIKE '2026-10%'")
    total_spend = c.fetchone()[0]
    conn.close()
    assert total_spend == pytest.approx(90.0)


def test_e2e_cost_billing_terminal_output(tmp_path, monkeypatch, capsys):
    """LIVE-20 E2E: cost billing renders the $90.00 quad-harness subscription table."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump(
            {
                "harness_billing": {
                    "claude": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "codex": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "agy": {"payment_mode": "subscription", "monthly_base_fee_usd": 20.0},
                    "grok": {"payment_mode": "subscription", "monthly_base_fee_usd": 30.0},
                }
            },
            f,
        )

    cmd_cost_billing()
    out = capsys.readouterr().out

    assert "Harness Billing & Subscription Status" in out
    assert "- claude: subscription ($20.00/mo)" in out
    assert "- codex: subscription ($20.00/mo)" in out
    assert "- agy: subscription ($20.00/mo)" in out
    assert "- grok: subscription ($30.00/mo)" in out
    assert "Total Monthly Subscription Fees: $90.00" in out
