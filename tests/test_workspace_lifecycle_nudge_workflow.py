import os
import stat
import subprocess
from pathlib import Path

WORKFLOW = Path(".github/workflows/workspace-lifecycle-nudge.yml")
SCRIPT = Path(".github/scripts/workspace-lifecycle-nudge.sh")


def test_nudge_workflow_uses_an_explicit_ledger_and_does_not_allow_fallback():
    """gh:#2649 — a runner home ledger must not fail the push."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "branches: [main]" in workflow
    assert "cron: '0 */6 * * *'" in workflow
    assert "bash .github/scripts/workspace-lifecycle-nudge.sh" in workflow
    assert "SYNLYNK_STATE_DB_PATH: ${{ runner.temp }}/synlynk-nudge/state.db" in workflow
    assert "SYNLYNK_ALLOW_STATE_DB_FALLBACK" not in workflow
    assert "gh:#2649" in workflow
    assert "disk I/O error" in SCRIPT.read_text(encoding="utf-8")


def _stub(tmp_path: Path, body: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python3"
    python.write_text(body, encoding="utf-8")
    python.chmod(python.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _run(tmp_path: Path, bin_dir: Path, **env):
    ledger = tmp_path / "ledger" / "state.db"
    count = tmp_path / "count"
    merged = os.environ.copy()
    merged.pop("SYNLYNK_ALLOW_STATE_DB_FALLBACK", None)
    merged.update(
        {
            "PATH": f"{bin_dir}:{merged['PATH']}",
            "SYNLYNK_STATE_DB_PATH": str(ledger),
            "COUNT": str(count),
            "RUNNER_TEMP": str(tmp_path),
        }
    )
    merged.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT.resolve())],
        cwd=tmp_path,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    ), ledger, count


def test_nudge_script_retries_one_disk_io_error_on_a_fresh_ledger(tmp_path):
    bin_dir = _stub(
        tmp_path,
        """#!/bin/sh
echo call >> "$COUNT"
if [ -f "$SYNLYNK_STATE_DB_PATH" ]; then
  echo existed >> "$COUNT"
fi
touch "$SYNLYNK_STATE_DB_PATH"
touch "${SYNLYNK_STATE_DB_PATH}-journal"
calls=$(grep -c call "$COUNT")
if [ "$calls" -eq 1 ]; then
  echo "sqlite3.OperationalError: disk I/O error" >&2
  exit 1
fi
exit 0
""",
    )
    result, ledger, count = _run(tmp_path, bin_dir)

    assert result.returncode == 0, result.stderr
    assert count.read_text(encoding="utf-8").splitlines() == ["call", "call"]
    assert ledger.is_file()


def test_nudge_script_fails_immediately_on_a_real_nudge_error(tmp_path):
    bin_dir = _stub(
        tmp_path,
        """#!/bin/sh
echo call >> "$COUNT"
echo "RuntimeError: nudge failed" >&2
exit 1
""",
    )
    result, _ledger, count = _run(tmp_path, bin_dir)

    assert result.returncode == 1
    assert "nudge failed" in result.stderr
    assert count.read_text(encoding="utf-8").splitlines() == ["call"]


def test_nudge_script_fails_when_disk_io_persists(tmp_path):
    bin_dir = _stub(
        tmp_path,
        """#!/bin/sh
echo call >> "$COUNT"
echo "sqlite3.OperationalError: disk I/O error" >&2
exit 1
""",
    )
    result, _ledger, count = _run(tmp_path, bin_dir)

    assert result.returncode == 1
    assert count.read_text(encoding="utf-8").splitlines() == ["call", "call"]


def test_nudge_script_refuses_the_fallback_flag(tmp_path):
    bin_dir = _stub(tmp_path, "#!/bin/sh\necho call >> \"$COUNT\"\nexit 0\n")
    result, _ledger, count = _run(
        tmp_path, bin_dir, SYNLYNK_ALLOW_STATE_DB_FALLBACK="1"
    )

    assert result.returncode == 1
    assert "SYNLYNK_ALLOW_STATE_DB_FALLBACK" in result.stderr
    assert not count.exists()
