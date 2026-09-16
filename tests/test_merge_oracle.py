from synlynk.merge_oracle import require_merge_oracle

def test_green_checks_allow_merge():
    result = require_merge_oracle(
        1592,
        pr_check=lambda _: (True, "ok"),
        qa_gate=lambda _: {"verdict": "green", "reason": "CI green"},
        hud={"status": "running"},
    )
    assert result["merge_allowed"] is True
    assert result["qa_gate"]["verdict"] == "green"


def test_failed_unverified_hud_does_not_block_green_ci():
    result = require_merge_oracle(
        1592,
        pr_check=lambda _: (True, "ok"),
        qa_gate=lambda _: {"verdict": "green", "reason": "CI green"},
        hud={"status": "failed_unverified"},
    )
    assert result["merge_allowed"] is True
    assert result["hud"]["status"] == "failed_unverified"


def test_red_qa_gate_blocks_merge():
    result = require_merge_oracle(
        1592,
        pr_check=lambda _: (True, "ok"),
        qa_gate=lambda _: {"verdict": "red", "reason": "CI matrix is red"},
    )
    assert result["merge_allowed"] is False
    assert "CI matrix is red" in result["reason"]


def test_pr_check_failure_blocks_merge():
    result = require_merge_oracle(
        1592,
        pr_check=lambda _: (False, "synlynk pr check exited 1"),
        qa_gate=lambda _: {"verdict": "green", "reason": "CI green"},
    )
    assert result["merge_allowed"] is False
