"""Tests for universal preflight routing engine."""

import pytest
from synlynk.preflight import evaluate_preflight, estimate_task_complexity

@pytest.fixture
def sample_pack():
    return {
        "schema_version": "1.0.0",
        "disciplines": {
            "PROG": {"name": "Software Development", "domain": "Development & Implementation", "description": "..."},
            "TEST": {"name": "Testing", "domain": "Development & Implementation", "description": "..."},
            "DBDS": {"name": "Database Design", "domain": "Development & Implementation", "description": "..."}
        },
        "matrix": {
            "PROG": [
                {
                    "harness": "codex",
                    "model": "gpt-5.6-terra",
                    "quality_score": 9.04,
                    "cost_per_verified_fix_usd": 0.52,
                    "median_review_cycles": 1.1,
                    "sample_size": 410,
                    "unmeasured": False,
                    "failover_risk": "low"
                },
                {
                    "harness": "grok",
                    "model": "grok-4.6",
                    "quality_score": 8.55,
                    "cost_per_verified_fix_usd": 0.48,
                    "median_review_cycles": 1.2,
                    "sample_size": 176,
                    "unmeasured": False,
                    "failover_risk": "low"
                },
                {
                    "harness": "claude",
                    "model": "claude-3.7-sonnet",
                    "quality_score": 9.20,
                    "cost_per_verified_fix_usd": 0.65,
                    "median_review_cycles": 1.1,
                    "sample_size": 150,
                    "unmeasured": False,
                    "failover_risk": "high"
                },
                {
                    "harness": "agy",
                    "model": "gemini-3.8-flash",
                    "quality_score": 7.58,
                    "cost_per_verified_fix_usd": 0.08,
                    "median_review_cycles": 1.6,
                    "sample_size": 89,
                    "unmeasured": False,
                    "failover_risk": "none"
                }
            ],
            "TEST": [
                {
                    "harness": "agy",
                    "model": "gemini-3.8-pro",
                    "quality_score": 8.70,
                    "cost_per_verified_fix_usd": 0.20,
                    "median_review_cycles": 1.2,
                    "sample_size": 95,
                    "unmeasured": False,
                    "failover_risk": "none"
                }
            ]
        },
        "quota_advisories": {
            "claude": "High risk of rate limit cliff (active weekly cooldown window); Codex or Grok recommended"
        },
        "cta": {
            "message": "Automate multi-agent routing",
            "install_cmd": "brew install synlynk",
            "vscode_url": "https://marketplace.visualstudio.com/items?itemName=synlynk.synlynk-vscode"
        },
        "snapshot_metadata": {
            "snapshot_id": "pack-2026-10-19-test",
            "sha256": "abcdef123456",
            "signature_verified": True
        }
    }


def test_estimate_task_complexity():
    assert estimate_task_complexity("fix typo in readme") == "low"
    assert estimate_task_complexity("refactor postgresql connection pool and fix async race condition") == "complex"
    assert estimate_task_complexity("add unit tests for user authentication") == "medium"


def test_evaluate_preflight_quality_preference(sample_pack):
    res = evaluate_preflight(
        prompt="Fix race condition in PostgreSQL connection pool during reconnection burst",
        pack=sample_pack,
        preferences={"optimize_for": "quality"}
    )
    assert res["task_classification"]["sfia_code"] in {"PROG", "DBDS"}
    assert res["task_classification"]["complexity"] == "complex"
    assert res["task_classification"]["confidence"] > 0.0
    
    recs = res["recommendations"]
    assert "primary" in recs
    # When optimizing for quality, highest quality is chosen (claude or codex)
    assert recs["primary"]["quality_score"] >= 9.0
    assert "failover" in recs
    assert "budget" in recs
    assert recs["budget"]["harness"] == "agy"
    assert recs["budget"]["cost_per_verified_fix_usd"] == 0.08


def test_evaluate_preflight_budget_preference(sample_pack):
    res = evaluate_preflight(
        prompt="Write unit tests for parser functions",
        pack=sample_pack,
        preferences={"optimize_for": "cost"}
    )
    assert res["task_classification"]["sfia_code"] == "TEST"
    recs = res["recommendations"]
    assert recs["primary"]["harness"] == "agy"


def test_evaluate_preflight_fallback_empty_pack():
    empty_pack = {"matrix": {}, "disciplines": {}}
    res = evaluate_preflight("some general programming task", empty_pack)
    assert res["task_classification"]["sfia_code"] == "PROG"
    assert "primary" in res["recommendations"]
    assert res["recommendations"]["primary"]["model"] == "default"
