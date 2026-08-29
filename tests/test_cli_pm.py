import os
import subprocess
import sys
import textwrap


def test_pm_sweep_dry_run_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.json", "w") as f:
        f.write(textwrap.dedent("""\
            {
              "segments": [{"name": "solo indie devs", "competitors": []}],
              "decide_panel": "claude",
              "research_issue_labels": ["competitive-research"],
              "proposal_issue_labels": ["feature-proposal"]
            }
        """))
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(repo_root, "bin", "synlynk.py"),
            "pm",
            "sweep",
            "--dry-run",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "solo indie devs" in result.stdout
