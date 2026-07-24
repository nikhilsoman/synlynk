"""synlynk upgrade: install-type detection and version upgrade logic."""

import json
import os
import subprocess
import sys
import urllib.request

from synlynk._constants import VERSION, _INSTALL_SCRIPT_URL


def _detect_install_type() -> str:
    """Returns 'pipx', 'pip', 'script', or 'unknown'."""
    import shutil as _shutil

    binary = _shutil.which("synlynk") or ""
    if "pipx" in binary or "pipx" in os.environ.get("PIPX_HOME", ""):
        return "pipx"
    try:
        import importlib.metadata as _meta

        loc = str(_meta.distribution("synlynk").locate_file(""))
        if "pipx" in loc:
            return "pipx"
        if loc != "":
            return "pip"
    except Exception:
        pass
    if os.path.exists(os.path.expanduser("~/.synlynk/bin/synlynk")):
        return "script"
    return "unknown"


def _ver_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


def _run_upgrade(latest: str) -> None:
    from synlynk.rollback import rollback_checkpoint_upgrade

    print(f"  ✦ New version available: v{latest} — upgrading from v{VERSION}")
    package = sys.modules.get("synlynk")
    detect_install_type = getattr(package, "_detect_install_type", _detect_install_type)
    get_pipx_source = getattr(package, "_get_pipx_source", _get_pipx_source)
    install_type = detect_install_type()
    with rollback_checkpoint_upgrade(VERSION, install_type):
        if install_type == "pipx":
            pipx_source = get_pipx_source()
            if pipx_source and not pipx_source.startswith(("http://", "https://", "git+")):
                install_spec = f"git+https://github.com/nikhilsoman/synlynk@v{latest}"
                result = subprocess.run(["pipx", "install", install_spec, "--force"], text=True)
                if result.returncode == 0:
                    print(f"  ✓ Upgraded to v{latest} via pipx (switched to release channel)")
                    print("  → Run 'synlynk migrate' if prompted, to apply any schema changes")
                else:
                    print("  ⚠ pipx reinstall failed — run manually:")
                    print(f"    pipx install git+https://github.com/nikhilsoman/synlynk@v{latest} --force")
            else:
                result = subprocess.run(["pipx", "upgrade", "synlynk"], text=True)
                if result.returncode == 0:
                    print(f"  ✓ Upgraded to v{latest} via pipx")
                    print("  → Run 'synlynk migrate' if prompted, to apply any schema changes")
                else:
                    print("  ⚠ pipx upgrade failed — run manually: pipx upgrade synlynk")
            return
        try:
            req = urllib.request.Request(
                _INSTALL_SCRIPT_URL, headers={"User-Agent": f"synlynk/{VERSION}"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                script = resp.read().decode()
            result = subprocess.run(["bash", "-c", script], text=True)
            if result.returncode == 0:
                print(f"  ✓ Upgraded to v{latest}")
                print("  Restart your shell or run: source ~/.zshrc")
                print("  → Run 'synlynk migrate' if prompted, to apply any schema changes")
            else:
                print(f"  ⚠ Install script exited {result.returncode} — run manually:")
                print(f"  curl -sSL {_INSTALL_SCRIPT_URL} | bash")
        except Exception as e:
            print(f"  ⚠ Auto-install failed ({e}) — run manually:")
            print(f"  curl -sSL {_INSTALL_SCRIPT_URL} | bash")


def _get_pipx_source() -> str:
    """Return the pipx package_or_url for synlynk, or '' if not detectable."""
    try:
        pipx_home = os.environ.get("PIPX_HOME", os.path.expanduser("~/.local/pipx"))
        metadata_path = os.path.join(pipx_home, "venvs", "synlynk", "pipx_metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path) as f:
                data = json.load(f)
            return data.get("main_package", {}).get("package_or_url", "")
    except Exception:
        pass
    return ""


def _warn_stale_script_install() -> None:
    """Warn if a stale ~/.synlynk/bin/synlynk script-install shim exists alongside a pipx install."""
    script_shim = os.path.expanduser("~/.synlynk/bin/synlynk")
    if not os.path.exists(script_shim):
        return
    install_type = _detect_install_type()
    if install_type != "pipx":
        return
    # Running from pipx but a legacy script shim also exists — warn.
    print("  ⚠ Legacy script install detected at ~/.synlynk/bin/synlynk")
    print("    This shim may be stale and shadow your pipx install on some PATH configs")
    print("    To remove it:")
    print("      rm -rf ~/.synlynk/bin ~/.synlynk/lib")
    print("    Your pipx install at ~/.local/bin/synlynk is the active version")


def upgrade() -> None:
    """Checks GitHub releases for a newer version and auto-installs if one is found."""
    print(f"Checking for updates... (current: v{VERSION})")
    package = sys.modules.get("synlynk")
    run_upgrade = getattr(package, "_run_upgrade", _run_upgrade)
    warn_stale_script_install = getattr(
        package, "_warn_stale_script_install", _warn_stale_script_install
    )
    try:
        # Try gh CLI first — works for private repos and avoids unauthenticated rate limits.
        try:
            result = subprocess.run(
                ["gh", "api", "repos/nikhilsoman/synlynk/releases/latest", "--jq", ".tag_name"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                latest = result.stdout.strip().lstrip("v")
                if latest and _ver_tuple(latest) > _ver_tuple(VERSION):
                    run_upgrade(latest)
                else:
                    print(f"  ✓ You are on the latest version (v{VERSION}).")
                return
        except Exception:
            pass
        # Fall back to unauthenticated GitHub API (works for public repos).
        url = "https://api.github.com/repos/nikhilsoman/synlynk/releases/latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"synlynk/{VERSION}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            latest = data.get("tag_name", "").lstrip("v")
            if latest and _ver_tuple(latest) > _ver_tuple(VERSION):
                run_upgrade(latest)
            else:
                print(f"  ✓ You are on the latest version (v{VERSION}).")
        except Exception as e:
            print(f"  ⚠ Could not check for updates: {e}")
            print("  Check manually: https://github.com/nikhilsoman/synlynk/releases")
    finally:
        warn_stale_script_install()
