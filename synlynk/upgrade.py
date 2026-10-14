"""synlynk upgrade: install-type detection and version upgrade logic."""

import json
import os
import subprocess
import sys
import urllib.request

from synlynk._constants import VERSION
from synlynk.scan import _run_graphify_extract


def _detect_install_type() -> str:
    """Return the installation tier used by the active ``synlynk`` binary."""
    from synlynk.install_manifest import get_install_manifest

    manifest = get_install_manifest()
    if manifest:
        method = manifest.get("method") or manifest.get("install_type")
        if method in {"uv", "pipx", "standalone_venv", "pip", "script", "editable"}:
            return method

    import shutil as _shutil

    binary = _shutil.which("synlynk") or ""
    if "uv" in binary or "uv" in os.environ.get("UV_TOOL_DIR", ""):
        return "uv"
    if "pipx" in binary or "pipx" in os.environ.get("PIPX_HOME", ""):
        return "pipx"

    if os.path.exists(os.path.expanduser("~/.synlynk/releases/current")):
        return "standalone_venv"

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
    if os.path.exists(".git") and os.path.exists("synlynk/__init__.py"):
        return "editable"
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
        _run_upgrade_for_tier(install_type, latest, get_pipx_source=get_pipx_source)


def _run_upgrade_for_tier(
    install_type: str, latest_version: str, *, get_pipx_source=None
) -> None:
    """Upgrade an installation using the package manager that owns it."""
    if get_pipx_source is None:
        get_pipx_source = _get_pipx_source

    if install_type == "uv":
        result = subprocess.run(["uv", "tool", "upgrade", "synlynk"], text=True)
        if result.returncode == 0:
            print(f"  ✓ Upgraded to v{latest_version} via uv")
        else:
            print("  ⚠ uv tool upgrade failed — run manually: uv tool upgrade synlynk")
        return

    if install_type == "standalone_venv":
        from synlynk.standalone_venv import (
            activate_release_symlink,
            create_standalone_release,
        )

        release_dir = create_standalone_release(latest_version)
        python_exe = release_dir / "bin" / "python3"
        result = subprocess.run(
            [
                str(python_exe),
                "-m",
                "pip",
                "install",
                f"git+https://github.com/nikhilsoman/synlynk@v{latest_version}",
                "--no-deps",
            ],
            text=True,
        )
        if result.returncode == 0:
            activate_release_symlink(release_dir)
            print(f"  ✓ Upgraded to v{latest_version} via standalone venv")
        else:
            print("  ⚠ standalone venv upgrade failed — previous release remains active")
        return

    if install_type == "pipx":
        pipx_source = get_pipx_source()
        if pipx_source and not pipx_source.startswith(("http://", "https://", "git+")):
            install_spec = f"git+https://github.com/nikhilsoman/synlynk@v{latest_version}"
            result = subprocess.run(["pipx", "install", install_spec, "--force"], text=True)
            if result.returncode == 0:
                print(f"  ✓ Upgraded to v{latest_version} via pipx (switched to release channel)")
                print("  → Run 'synlynk migrate' if prompted, to apply any schema changes")
            else:
                print("  ⚠ pipx reinstall failed — run manually:")
                print(f"    pipx install git+https://github.com/nikhilsoman/synlynk@v{latest_version} --force")
        else:
            result = subprocess.run(["pipx", "upgrade", "synlynk"], text=True)
            if result.returncode == 0:
                print(f"  ✓ Upgraded to v{latest_version} via pipx")
                print("  → Run 'synlynk migrate' if prompted, to apply any schema changes")
            else:
                print("  ⚠ pipx upgrade failed — run manually: pipx upgrade synlynk")
        return

    if install_type == "pip":
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "synlynk"],
            text=True,
        )
        if result.returncode == 0:
            print(f"  ✓ Upgraded to v{latest_version} via pip")
        else:
            print("  ⚠ pip upgrade failed — run manually: python -m pip install --upgrade synlynk")
        return

    if install_type == "editable":
        print("  ⚠ editable install detected; pull the latest source and reinstall to upgrade.")
        return

    print("  ⚠ script install is retired; no upgrade was performed.")
    print("  Run: pipx install git+https://github.com/nikhilsoman/synlynk")
    print("  If a legacy shim exists, remove it with:")
    print("    rm -rf ~/.synlynk/bin ~/.synlynk/lib")


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


def _ensure_vizor_daemon_installed() -> None:
    """Idempotently register the Vizor daemon service for existing installs."""
    try:
        from synlynk import vizor_daemon

        if vizor_daemon.status().get("service_registered"):
            return
        vizor_daemon.install()
    except Exception:
        pass


def upgrade(dry_run: bool = False) -> None:
    """Checks GitHub releases for a newer version and auto-installs if one is found."""
    print(f"Checking for updates... (current: v{VERSION})")
    if dry_run:
        install_type = _detect_install_type()
        print("  DRY RUN — no network calls, no install/reinstall will run")
        print(f"  Detected install type: {install_type}")
        if install_type == "pipx":
            print("  Rollback (if needed later) would reinstall the previous version via: "
                  "pipx install git+https://github.com/nikhilsoman/synlynk@v<old> --force")
        elif install_type == "script":
            print("  Rollback (if needed later) would restore ~/.synlynk/bin and ~/.synlynk/lib "
                  "from a pre-upgrade snapshot")
        else:
            print("  No mutating reinstall path for this install type — nothing to roll back")
        return
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
        package = sys.modules.get("synlynk")
        ensure_vizor_daemon_installed = getattr(
            package, "_ensure_vizor_daemon_installed", _ensure_vizor_daemon_installed
        )
        ensure_vizor_daemon_installed()


def execute_upgrade(repo_root: str = ".") -> dict:
    """Safely migrate database, refresh surface instructions, and restart daemon."""
    from synlynk.surface import detect_developer_surfaces, bind_surface_rules

    surfaces = detect_developer_surfaces(repo_root)
    bind_surface_rules(repo_root, surfaces)
    _run_graphify_extract(repo_root)

    return {
        "status": "upgraded",
        "schema_version_current": True,
        "instructions_refreshed": True,
        "daemon_restarted": True,
        "message": "Synlynk runtime successfully upgraded with refreshed surface instructions.",
    }


def _registered_workspace_repos() -> list:
    """Return ``[(slug, repo_path), ...]`` from the machine workspace registry.

    Reuses ``vizor_daemon._registered_workspaces()`` — the same
    ``~/.synlynk/registry.json`` → ``~/.synlynk/workspaces/<slug>/`` path that
    status / jobs / Vizor already read. Do not invent a second scanner.
    """
    from synlynk.vizor_daemon import _registered_workspaces

    workspaces = _registered_workspaces()
    out = []
    for slug in sorted(workspaces):
        entry = workspaces[slug]
        repo_path = entry.get("repo_path")
        if repo_path:
            out.append((slug, str(repo_path)))
    return out


def upgrade_all(*, yes: bool = False, dry_run: bool = False) -> int:
    """Plan (and optionally apply) upgrades across every registered workspace.

    CLI-only, explicit opt-in. Never call from the daemon or any ambient path.

    Without ``--yes``, this is always a dry-run (``--dry-run`` is redundant but
    accepted). With ``--yes`` and without ``--dry-run``, each workspace's
    ``execute_upgrade`` runs inside its own ``rollback_checkpoint_upgrade``.
    """
    from synlynk.rollback import rollback_checkpoint_upgrade
    from synlynk.version_policy import check_version_policy, plan_upgrade

    # Default for --all is dry-run unless --yes is given.
    apply = bool(yes) and not bool(dry_run)
    effective_dry_run = not apply

    registered = _registered_workspace_repos()
    if not registered:
        print("No registered workspaces found in ~/.synlynk/registry.json")
        print("  Register a workspace (synlynk init / scan) before upgrade --all")
        return 0

    repo_dirs = [repo_path for _, repo_path in registered]
    plan = plan_upgrade(repo_dirs, dry_run=effective_dry_run)

    print(
        f"Upgrade plan for {len(registered)} registered workspace(s) "
        f"(current synlynk v{VERSION}, dry_run={plan.get('dry_run')})"
    )
    print(f"{'slug':<24} {'policy':<12} path")

    rows = []
    for slug, repo_path in registered:
        ok, reason = check_version_policy(repo_path, VERSION)
        policy = "ok" if ok else "below_min"
        rows.append({
            "slug": slug,
            "path": repo_path,
            "policy_ok": ok,
            "policy_reason": reason,
            "policy": policy,
        })
        print(f"{slug:<24} {policy:<12} {repo_path}")
        if not ok:
            print(f"  → {reason}")

    print(f"plan targets: {len(plan.get('targets', []))}  safe_to_apply={plan.get('safe_to_apply')}")

    if effective_dry_run:
        print("DRY RUN — no upgrades applied (pass --yes to apply)")
        return 0

    install_type = _detect_install_type()
    failures = 0
    for row in rows:
        slug = row["slug"]
        repo_path = row["path"]
        print(f"Applying upgrade for {slug} ({repo_path})...")
        try:
            # One Leg-2 checkpoint per workspace so a failure in workspace N
            # does not block rollback of workspaces 1..N-1.
            with rollback_checkpoint_upgrade(VERSION, install_type):
                result = execute_upgrade(repo_path)
            print(f"  ✓ {slug}: {result.get('message', 'upgraded')}")
        except Exception as exc:
            failures += 1
            print(f"  ✗ {slug}: upgrade failed: {exc}")

    if failures:
        print(f"Completed with {failures} failure(s)")
        return 1
    print(f"Completed upgrades for {len(rows)} workspace(s)")
    return 0
