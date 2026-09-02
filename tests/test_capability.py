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
