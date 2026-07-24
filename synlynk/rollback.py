"""Checkpoint-and-restore rollback mechanism for init/migrate/upgrade.

Two independent legs share one manifest format:
Leg 1 (rollback_checkpoint): git-repo checkpoint for init/migrate
Leg 2 (rollback_checkpoint_upgrade): global install snapshot for upgrade,
since upgrade never touches the git repo
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

ROLLBACK_DIR = os.path.join(".synlynk", "rollback")
MANIFEST_PATH = os.path.join(ROLLBACK_DIR, "last.json")
ARCHIVE_DIR = os.path.join(ROLLBACK_DIR, "archive")


def _new_op_id() -> str:
    return uuid.uuid4().hex[:8]


def _dest_for(backup_dir: str, path: str) -> Path:
    """Map a (possibly absolute) source path onto a location inside backup_dir."""
    normalized = str(path)
    if os.path.isabs(normalized):
        normalized = normalized.lstrip(os.sep)
    return Path(backup_dir) / normalized


def _backup_paths(op_id: str, paths: list) -> str:
    backup_dir = os.path.join(ROLLBACK_DIR, op_id, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    for raw_path in paths:
        src = Path(raw_path)
        dest = _dest_for(backup_dir, raw_path)
        if not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)
    return backup_dir


def _restore_paths(backup_dir: str, paths: list) -> None:
    for raw_path in paths:
        src = _dest_for(backup_dir, raw_path)
        dest = Path(raw_path)
        if not src.exists():
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def _write_manifest(manifest: dict) -> None:
    os.makedirs(ROLLBACK_DIR, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def _read_manifest(op_id: Optional[str] = None) -> Optional[dict]:
    path = MANIFEST_PATH if op_id is None else os.path.join(ARCHIVE_DIR, f"{op_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _archive_manifest(manifest: dict) -> None:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    archive_path = os.path.join(ARCHIVE_DIR, f"{manifest['op_id']}.json")
    with open(archive_path, "w") as f:
        json.dump(manifest, f, indent=2)
    if os.path.exists(MANIFEST_PATH):
        os.remove(MANIFEST_PATH)


def _git_head_sha() -> Optional[str]:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_dirty() -> bool:
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if result is None:
        return False
    return bool(result.stdout.strip())


def _pop_stash(stash_ref: str) -> None:
    listing = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
    if listing is None:
        return
    for line in listing.stdout.splitlines():
        if stash_ref in line:
            stash_id = line.split(":", 1)[0]
            popped = subprocess.run(["git", "stash", "pop", stash_id])
            if popped is not None and popped.returncode != 0:
                print(
                    f"  ⚠ git stash pop failed for {stash_id} — resolve conflicts "
                    f"manually, then run: git stash drop {stash_id}"
                )
            break


def restore_leg1(manifest: dict) -> None:
    sha = manifest.get("checkpoint_sha")
    if sha:
        subprocess.run(["git", "reset", "--hard", sha], check=True)
    stash_ref = manifest.get("stash_ref")
    if stash_ref:
        _pop_stash(stash_ref)
    if manifest.get("backup_dir"):
        _restore_paths(manifest["backup_dir"], manifest.get("untracked_paths", []))
    _archive_manifest(manifest)


@contextlib.contextmanager
def rollback_checkpoint(op_type: str, untracked_paths: Optional[list] = None):
    """Leg 1: repo checkpoint wrapping init()/cmd_migrate().

    Records the pre-op HEAD SHA (auto-stashing a dirty tree first) and backs up
    untracked_paths before yielding.
    On any exception raised inside the `with` block, restores the repo and
    untracked paths to their pre-op state, then re-raises.
    On success, pops the auto-stash back (if one was created) so a dirty
    pre-op working tree is left exactly as it was. The manifest is left at
    MANIFEST_PATH (not archived) so `synlynk rollback --last` can still act
    on it.
    """
    untracked_paths = untracked_paths or []
    op_id = _new_op_id()
    backup_dir = _backup_paths(op_id, untracked_paths)
    stash_ref = None
    if _git_dirty():
        stash_ref = f"synlynk-rollback-{op_id}"
        # untracked_paths are the op's own outputs (already covered by the
        # _backup_paths/_restore_paths mechanism above) — exclude them from
        # the auto-stash so popping the stash back on success doesn't clobber
        # what the op just wrote.
        exclude_pathspecs = [f":!{p}" for p in untracked_paths]
        subprocess.run(
            ["git", "stash", "push", "-u", "-m", stash_ref, "--", ".", *exclude_pathspecs],
            check=True,
        )
    checkpoint_sha = _git_head_sha()
    manifest = {
        "op_id": op_id,
        "op_type": op_type,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checkpoint_sha": checkpoint_sha,
        "stash_ref": stash_ref,
        "backup_dir": backup_dir,
        "untracked_paths": untracked_paths,
    }
    _write_manifest(manifest)
    try:
        yield manifest
    except BaseException:
        restore_leg1(manifest)
        raise
    else:
        if stash_ref:
            _pop_stash(stash_ref)


_SCRIPT_INSTALL_PATHS = ("~/.synlynk/bin", "~/.synlynk/lib")


def restore_leg2(manifest: dict) -> None:
    install_type = manifest.get("install_type")
    old_version = manifest.get("previous_version")
    if install_type == "pipx" and old_version:
        subprocess.run(
            [
                "pipx",
                "install",
                f"git+https://github.com/nikhilsoman/synlynk@v{old_version}",
                "--force",
            ]
        )
    elif install_type == "script" and manifest.get("backup_dir"):
        _restore_paths(
            manifest["backup_dir"],
            [os.path.expanduser(p) for p in _SCRIPT_INSTALL_PATHS],
        )
    _archive_manifest(manifest)


@contextlib.contextmanager
def rollback_checkpoint_upgrade(current_version: str, install_type: str):
    """Leg 2: install-location snapshot wrapping _run_upgrade().

    upgrade() never touches the git repo, so this does not use Leg 1 at all.
    pipx installs roll back by reinstalling the recorded old version tag;
    script installs additionally snapshot ~/.synlynk/{bin,lib} since there is
    no version-pinned reinstall path for that install type.
    """
    op_id = _new_op_id()
    backup_dir = None
    if install_type == "script":
        backup_dir = _backup_paths(
            op_id, [os.path.expanduser(p) for p in _SCRIPT_INSTALL_PATHS]
        )
    manifest = {
        "op_id": op_id,
        "op_type": "upgrade",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "previous_version": current_version,
        "install_type": install_type,
        "backup_dir": backup_dir,
    }
    _write_manifest(manifest)
    try:
        yield manifest
    except BaseException:
        restore_leg2(manifest)
        raise


def cmd_rollback(last: bool = False, op_id: Optional[str] = None, clear: bool = False) -> None:
    manifest = _read_manifest(op_id=op_id) if op_id else _read_manifest()
    if manifest is None:
        print("  No rollback checkpoint found for this session.")
        return
    if clear:
        _archive_manifest(manifest)
        print(f"  ✓ Cleared checkpoint {manifest['op_id']} ({manifest['op_type']}) without restoring")
        return
    if manifest["op_type"] in ("init", "migrate"):
        restore_leg1(manifest)
    else:
        restore_leg2(manifest)
    print(f"  ✓ Rolled back {manifest['op_type']} checkpoint {manifest['op_id']}")
