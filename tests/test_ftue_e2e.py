import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.coldstart import run_ftue_journey


def test_run_ftue_journey_e2e(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n")
    result = run_ftue_journey(str(tmp_path), interactive=False, dry_run=True)
    assert result["success"] is True
    assert result["first_win_task"] is not None
    assert "feat/first-win" in result["first_win_task"]["branch"]
    assert result["governs_goal"] is not None
