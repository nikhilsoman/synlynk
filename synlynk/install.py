import shutil
import subprocess
import sys
from typing import Dict, Any


def check_install_prerequisites() -> Dict[str, Any]:
    """Check git, python, and environment prerequisites for Synlynk onboarding."""
    results = {
        "git": {"satisfied": False, "version": None, "path": None},
        "python": {"satisfied": False, "version": sys.version.split()[0], "path": sys.executable},
        "can_proceed": False,
    }

    if sys.version_info >= (3, 10):
        results["python"]["satisfied"] = True

    git_path = shutil.which("git")
    if git_path:
        results["git"]["path"] = git_path
        try:
            out = subprocess.run([git_path, "--version"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                results["git"]["version"] = out.stdout.strip()
                results["git"]["satisfied"] = True
        except Exception:
            pass

    results["can_proceed"] = results["git"]["satisfied"] and results["python"]["satisfied"]
    return results


def run_install_preflight() -> bool:
    """Print readable preflight diagnostic to terminal. Returns True if can proceed."""
    res = check_install_prerequisites()
    if not res["can_proceed"]:
        print("❌ Installation preflight failed:")
        if not res["git"]["satisfied"]:
            print("  - Git >= 2.38 is required.")
        if not res["python"]["satisfied"]:
            print("  - Python >= 3.10 is required.")
        return False
    return True
