import sqlite3
from unittest.mock import patch

from synlynk.db import _migrate_onboarding_sessions
from synlynk.onboarding_state import STAGE_S1_ORIENTATION
from synlynk.wizard import cmd_wizard_init


def test_wizard_init_advances_headless_state(tmp_path):
    state_db = tmp_path / ".synlynk" / "state.db"
    state_db.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(state_db))
    _migrate_onboarding_sessions(conn)
    conn.close()

    with patch("sys.stdin.isatty", return_value=False), \
         patch("synlynk.wizard._run_scan_tui", return_value={"status": "ok"}):
        # Non-interactive / headless run should execute without hanging
        res = cmd_wizard_init(repo_dir=str(tmp_path), non_interactive=True)
        assert res == 0

    conn = sqlite3.connect(str(state_db))
    row = conn.execute(
        "SELECT current_stage FROM onboarding_sessions ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] != STAGE_S1_ORIENTATION
    assert row[0]
