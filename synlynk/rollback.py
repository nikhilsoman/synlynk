"""Checkpoint-and-restore rollback mechanism for init/migrate/upgrade.

Two independent legs share one manifest format:
- Leg 1 (rollback_checkpoint): git-repo checkpoint for init/migrate
- Leg 2 (rollback_checkpoint_upgrade): global install snapshot for upgrade,
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

ROLLBACK_DIR = os.path.join("synlynk", "rollback")
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
