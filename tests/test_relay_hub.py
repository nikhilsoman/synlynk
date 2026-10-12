import subprocess
import sys


def test_core_cli_import_does_not_require_nats():
    """synlynk's core CLI must import cleanly with no nats-py installed --
    hub features are optional, the base CLI is stdlib-only (CLAUDE.md constraint).
    """
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk; import synlynk.cli"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_relay_hub_module_importable_without_nats_installed():
    """Importing synlynk.relay_hub itself must not require nats-py at import time --
    only calling HubAdapter.connect() should need it.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk.relay_hub"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
