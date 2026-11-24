import json
import sqlite3

import pytest

from synlynk.capability_regen import regenerate_capability_policy


def _db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE capability_ratings (
            agent TEXT NOT NULL, discipline TEXT NOT NULL, correct INTEGER
        );
        CREATE TABLE daemon_jobs (
            agent TEXT, harness TEXT, actual_harness TEXT,
            requires_gh_write INTEGER, gh_write_verified TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO capability_ratings(agent, discipline, correct) VALUES (?, ?, ?)",
        [("codex", "implement", 1)] * 5 + [("claude", "implement", 1)] * 5,
    )
    conn.executemany(
        "INSERT INTO daemon_jobs(agent, harness, actual_harness, requires_gh_write, gh_write_verified) VALUES (?, ?, ?, ?, ?)",
        [
            ("codex", None, None, 1, "true"),
            ("claude", "claude", None, 1, "false"),
            ("muse", "muse", None, 1, None),
        ],
    )
    conn.commit()
    conn.close()


def test_regen_rewrites_only_derived_policy_fields(tmp_path):
    db_path = tmp_path / "state.db"
    _db(db_path)
    policy_path = tmp_path / "policy.json"
    original = {
        "capability_policy": {
            "eligibility": {
                "codex": {"can_gh_write": False},
                "claude": {"can_gh_write": True},
                "muse": {"can_gh_write": False},
            },
            "not_yet_calibrated": ["stale"],
            "note": "stale",
            "custom": {"preserve": [1, 2]},
        },
        "overrides": {"dev_authority": {"task_allocation": {"implement": {"harness": "codex"}}}},
        "other": {"untouched": True},
    }
    policy_path.write_text(json.dumps(original), encoding="utf-8")

    result = regenerate_capability_policy(
        db_path=db_path,
        policy_path=policy_path,
        harnesses=["codex", "claude", "muse"],
        task_types=["implement", "review"],
    )

    assert result["capability_policy"]["calibration_detail"] == {
        "codex": {"implement": True, "review": False},
        "claude": {"implement": True, "review": False},
        "muse": {"implement": False, "review": False},
    }
    assert result["capability_policy"]["not_yet_calibrated"] == ["muse"]
    assert result["capability_policy"]["eligibility"]["codex"]["can_gh_write"] is True
    assert result["capability_policy"]["eligibility"]["claude"]["can_gh_write"] is False
    assert result["capability_policy"]["eligibility"]["muse"]["can_gh_write"] == "unproven"
    assert result["capability_policy"]["custom"] == original["capability_policy"]["custom"]
    assert result["overrides"] == original["overrides"]
    assert result["other"] == original["other"]


def test_regen_dry_run_does_not_write(tmp_path, capsys):
    db_path = tmp_path / "state.db"
    _db(db_path)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({"capability_policy": {}}), encoding="utf-8")
    before = policy_path.read_bytes()

    regenerate_capability_policy(
        db_path=db_path,
        policy_path=policy_path,
        harnesses=["codex"],
        task_types=["implement"],
        dry_run=True,
    )

    assert policy_path.read_bytes() == before
    assert "calibration_detail" in capsys.readouterr().out


def test_regen_rejects_missing_canonical_database(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="canonical state.db"):
        regenerate_capability_policy(
            db_path=tmp_path / "missing.db", policy_path=policy_path,
            harnesses=["codex"], task_types=["implement"],
        )
