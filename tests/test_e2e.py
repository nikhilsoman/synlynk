"""
E2E tests for the synlynk CLI.

These tests invoke `python3 bin/synlynk.py` as a subprocess and treat
it as a black box — no imports from synlynk, no monkeypatching.

Run with:  pytest tests/test_e2e.py -v
Run only:  pytest tests/test_e2e.py -m e2e -v

Extending:
  1. Add your test to the appropriate feature section (or create a new one)
  2. Use the `cli` fixture — it provides a `Cli` helper with a fresh initialized project
  3. For commands that need a clean (uninitialised) dir, use `tmp_path` + `Cli.from_dir(tmp_path)`
  4. Follow the naming convention: test_<feature>_<scenario>
"""
import json
import subprocess
from pathlib import Path

import pytest

SYNLYNK_BIN = Path(__file__).parent.parent / "bin" / "synlynk.py"
PYTHON = "python3"

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

class Cli:
    """Helper wrapping subprocess calls to the synlynk CLI."""

    def __init__(self, project_dir: Path):
        self.dir = project_dir

    @classmethod
    def from_dir(cls, directory: Path) -> "Cli":
        """Return a Cli for an arbitrary directory (no init performed)."""
        return cls(directory)

    def run(self, *args, timeout: int = 30, **kwargs) -> subprocess.CompletedProcess:
        """Run synlynk with the given args in the project directory."""
        return subprocess.run(
            [PYTHON, str(SYNLYNK_BIN)] + list(args),
            cwd=str(self.dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            **kwargs,
        )

    def write_file(self, rel_path: str, content: str) -> None:
        """Write content to a file relative to the project directory."""
        target = self.dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def read_file(self, rel_path: str) -> str:
        """Read a file relative to the project directory."""
        return (self.dir / rel_path).read_text()

    @property
    def sentinel_file(self) -> Path:
        return self.dir / ".synlynk" / "sentinel.md"


@pytest.fixture
def cli(tmp_path) -> Cli:
    """Provides a Cli helper with a fresh initialized synlynk project."""
    instance = Cli(tmp_path)
    result = instance.run("init")
    assert result.returncode == 0, f"init failed:\n{result.stdout}\n{result.stderr}"
    return instance


@pytest.fixture
def uninit_cli(tmp_path) -> Cli:
    """Provides a Cli helper for a bare directory with no synlynk project."""
    return Cli.from_dir(tmp_path)


# ---------------------------------------------------------------------------
# Feature: CLI basics
# ---------------------------------------------------------------------------

def test_version_shows_synlynk(uninit_cli):
    result = uninit_cli.run("--version")
    assert result.returncode == 0
    assert "synlynk" in result.stdout


def test_help_exits_zero_and_lists_commands(uninit_cli):
    result = uninit_cli.run("--help")
    assert result.returncode == 0
    for cmd in ("exec", "status", "init", "sentinel"):
        assert cmd in result.stdout, f"'{cmd}' missing from --help output"


def test_init_creates_project_structure(uninit_cli):
    result = uninit_cli.run("init")
    assert result.returncode == 0
    assert (uninit_cli.dir / "project-docs").is_dir()
    assert (uninit_cli.dir / ".synlynk" / "config.json").exists()


def test_init_force_reruns_without_error(cli):
    result = cli.run("init", "--force")
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Feature: exec
# ---------------------------------------------------------------------------

def test_exec_echo_exits_zero(cli):
    result = cli.run("exec", "echo", "hello")
    assert result.returncode == 0
    assert "Executing:" in result.stdout


def test_exec_propagates_non_zero_exit_code(cli):
    result = cli.run("exec", PYTHON, "-c", "import sys; sys.exit(42)")
    assert result.returncode == 42


def test_exec_missing_command_returns_127(cli):
    result = cli.run("exec", "nonexistentcommand_synlynk_e2e_xyz")
    assert result.returncode == 127


def test_exec_writes_telemetry_event(cli):
    cli.run("exec", "echo", "hello")
    telemetry_path = cli.dir / ".synlynk" / "telemetry.json"
    assert telemetry_path.exists(), "telemetry.json not created after exec"
    data = json.loads(telemetry_path.read_text())
    assert isinstance(data, list)
    assert len(data) >= 1
    last = data[-1]
    assert last.get("type") == "exec"
    assert last.get("command") is not None
    assert "_ts" in last, "telemetry event missing _ts field"


# ---------------------------------------------------------------------------
# Feature: sentinel
# ---------------------------------------------------------------------------

def test_sentinel_list_empty_on_fresh_project(cli):
    result = cli.run("sentinel", "list")
    assert result.returncode == 0
    assert "No active" in result.stdout


def test_sentinel_list_shows_alert_after_write(cli):
    cli.write_file(
        ".synlynk/sentinel.md",
        "# Sentinel Alerts\n"
        "- [CRITICAL] [2026-06-10 14:23] ZOMBIE_DAEMON: daemon dead\n"
    )
    result = cli.run("sentinel", "list")
    assert result.returncode == 0
    assert "ZOMBIE_DAEMON" in result.stdout


def test_sentinel_clear_removes_all_alerts(cli):
    cli.write_file(
        ".synlynk/sentinel.md",
        "# Sentinel Alerts\n"
        "- [CRITICAL] [2026-06-10 14:23] ZOMBIE_DAEMON: daemon dead\n"
        "- [WARN] [2026-06-10 14:24] STALL: stalled\n"
    )
    clear_result = cli.run("sentinel", "clear")
    assert clear_result.returncode == 0
    list_result = cli.run("sentinel", "list")
    assert "No active" in list_result.stdout


def test_sentinel_clear_severity_removes_only_matching(cli):
    cli.write_file(
        ".synlynk/sentinel.md",
        "# Sentinel Alerts\n"
        "- [CRITICAL] [2026-06-10 14:23] ZOMBIE_DAEMON: daemon dead\n"
        "- [WARN] [2026-06-10 14:24] STALL: stalled\n"
    )
    cli.run("sentinel", "clear", "--severity", "WARN")
    result = cli.run("sentinel", "list")
    assert "ZOMBIE_DAEMON" in result.stdout
    assert "STALL" not in result.stdout


def test_sentinel_clear_code_removes_only_matching(cli):
    cli.write_file(
        ".synlynk/sentinel.md",
        "# Sentinel Alerts\n"
        "- [CRITICAL] [2026-06-10 14:23] ZOMBIE_DAEMON: daemon dead\n"
        "- [WARN] [2026-06-10 14:24] STALL: stalled\n"
    )
    cli.run("sentinel", "clear", "--code", "STALL")
    result = cli.run("sentinel", "list")
    assert "ZOMBIE_DAEMON" in result.stdout
    assert "STALL" not in result.stdout


# ---------------------------------------------------------------------------
# Feature: pre-exec gate
# ---------------------------------------------------------------------------

def test_exec_blocked_by_critical_alert(cli):
    cli.write_file(
        ".synlynk/sentinel.md",
        "# Sentinel Alerts\n"
        "- [CRITICAL] [2026-06-10 14:23] ZOMBIE_DAEMON: daemon dead\n"
    )
    result = cli.run("exec", "echo", "hello")
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "blocked" in combined.lower() or "CRITICAL" in combined


def test_exec_force_bypasses_critical_alert(cli):
    cli.write_file(
        ".synlynk/sentinel.md",
        "# Sentinel Alerts\n"
        "- [CRITICAL] [2026-06-10 14:23] ZOMBIE_DAEMON: daemon dead\n"
    )
    result = cli.run("exec", "--force", "echo", "hello")
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Feature: status
# ---------------------------------------------------------------------------

def test_status_exits_zero_on_initialized_project(cli):
    result = cli.run("status")
    assert result.returncode == 0


def test_status_output_contains_expected_sections(cli):
    result = cli.run("status")
    assert result.returncode == 0
    # Human-readable status output always includes BUDGET and SENTINEL sections
    for section in ("BUDGET", "SENTINEL"):
        assert section in result.stdout, f"'{section}' missing from status output"


# ---------------------------------------------------------------------------
# TODO: watch lifecycle tests
#
# synlynk watch start / stop are not covered here because daemon forking
# is unreliable in subprocess-based test environments (PID files, signal
# handling, timing). Add these as a dedicated test module that is opt-in
# and marked @pytest.mark.slow when the daemon API stabilises.
# ---------------------------------------------------------------------------
