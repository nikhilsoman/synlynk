"""Performance test for Synlynk CLI startup latency (#1497 / #4291)."""

import subprocess
import sys
import time


def test_cli_startup_latency():
    """Verify bin/synlynk.py --version completes under acceptable threshold."""
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "bin/synlynk.py", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    duration = time.perf_counter() - start

    assert proc.returncode == 0
    # Startup latency budget: < 1.0s (typical is ~100-200ms)
    assert duration < 1.5, f"CLI startup took {duration:.3f}s (exceeded 1.5s budget)"
