import sqlite3
import subprocess

from synlynk.db import _migrate_onboarding_sessions
from synlynk.first_win_loop import execute_first_win_cycle, verify_first_win_effect
from synlynk.onboarding_state import STAGE_S10_BUILD_EXPERIENCE


def test_verify_first_win_effect_rejects_empty(tmp_path):
    # Single-commit repo with no diff should fail effect verification
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# Initial\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=tmp_path, check=True, capture_output=True)

    assert verify_first_win_effect(str(tmp_path), "HEAD") is False


def test_verify_first_win_effect_accepts_valid_diff(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# Initial\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Init"], cwd=tmp_path, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "-b", "feat/first-win"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing Guide\n")
    subprocess.run(["git", "add", "CONTRIBUTING.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: add contributing guide"], cwd=tmp_path, check=True, capture_output=True)

    assert verify_first_win_effect(str(tmp_path), "feat/first-win", base_branch="HEAD~1") is True


def test_execute_first_win_cycle(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_file))
    _migrate_onboarding_sessions(conn)
    conn.close()

    result = execute_first_win_cycle(str(db_file), "prod_123", "add guide")

    assert result["status"] == "completed"
    assert result["product_id"] == "prod_123"
    assert result["current_stage"] == STAGE_S10_BUILD_EXPERIENCE

    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT current_stage FROM onboarding_sessions WHERE session_id = ?",
        (result["session_id"],),
    ).fetchone()
    conn.close()
    assert row["current_stage"] == STAGE_S10_BUILD_EXPERIENCE
