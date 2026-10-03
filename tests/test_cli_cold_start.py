"""Cold-start budgets for the most frequently inspected CLI commands."""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest


# GitHub's shared Linux runners show materially higher process-start variance
# than local development machines (especially on Python 3.10).  Keep enough
# headroom for that loaded-runner variance while still catching regressions in
# the lazy CLI path; this is a CI-calibrated budget, not a local-dev target.
COLD_START_BUDGET_SECONDS = 0.400
_COMMANDS = (("jobs", "--all"), ("status", "--json"))


def _initialize_ledger(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from synlynk import _get_db

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(path))
    conn = _get_db(db_path=str(path), migrate=True)
    conn.close()


@pytest.mark.performance
@pytest.mark.parametrize("command", _COMMANDS, ids=("jobs", "status"))
def test_cli_cold_start_stays_under_budget(tmp_path, monkeypatch, command):
    """A fresh process must keep the command startup path below 400 ms."""
    ledger = tmp_path / "state.db"
    _initialize_ledger(ledger, monkeypatch)

    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(repo_root),
            "SYNLYNK_CLI_ENTRYPOINT": "1",
            "SYNLYNK_STATE_DB_PATH": str(ledger),
        }
    )
    invocation = [
        sys.executable,
        "-c",
        "from synlynk import main; main()",
        *command,
    ]

    samples = []
    for _ in range(5):
        started = time.perf_counter()
        result = subprocess.run(
            invocation,
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        samples.append(time.perf_counter() - started)
        assert result.returncode == 0, result.stderr

    median = statistics.median(samples)
    assert median < COLD_START_BUDGET_SECONDS, (
        f"synlynk {' '.join(command)} cold start median was "
        f"{median * 1000:.1f} ms; budget is "
        f"{COLD_START_BUDGET_SECONDS * 1000:.0f} ms "
        f"(samples={[round(sample * 1000, 1) for sample in samples]})"
    )
