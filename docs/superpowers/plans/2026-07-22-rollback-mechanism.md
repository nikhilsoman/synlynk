# Rollback Mechanism for init/migrate/upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `synlynk init`, `synlynk migrate`, and `synlynk upgrade` a checkpoint-and-restore rollback mechanism so any of them can be undone — automatically on failure, or on request via `synlynk rollback` — within the same session.

**Architecture:** A new `synlynk/rollback.py` module provides two independent context managers sharing one manifest format (`.synlynk/rollback/last.json`, archived to `.synlynk/rollback/archive/<op-id>.json` after use). `rollback_checkpoint(op_type, untracked_paths)` (Leg 1) wraps `init()` and `cmd_migrate()`: it records the pre-op `HEAD` SHA, auto-stashes a dirty tree, and copies untracked files/dirs aside before the operation runs; on any uncaught exception it restores everything via `git reset --hard` + stash pop + file copy-back. `rollback_checkpoint_upgrade(current_version, install_type)` (Leg 2) wraps `_run_upgrade()`: for `pipx` installs it records the old version and rolls back by reinstalling that exact tag; for `script` installs it also snapshots `~/.synlynk/bin` and `~/.synlynk/lib` since there's no version-pinned reinstall path. A new `synlynk rollback [--last|<op-id>|--clear]` CLI command reads the manifest and dispatches to the right leg's restore function. `init --dry-run` and `upgrade --dry-run` are added as a cheap complementary preview (Approach C), matching the existing `migrate --dry-run` pattern.

**Tech Stack:** Python 3 stdlib only (`subprocess`, `shutil`, `json`, `contextlib`), pytest, argparse (existing `synlynk/cli.py` conventions).

---

## File Structure

- Create: `synlynk/rollback.py` — manifest I/O, path backup/restore helpers, both context managers, both restore functions, and the `cmd_rollback()` CLI handler.
- Create: `tests/test_rollback.py` — unit tests for the module in isolation (manifest round-trip, path backup/restore, Leg 1 restore, Leg 2 restore).
- Modify: `synlynk/db.py:1185` (`cmd_migrate`) — wrap the mutating body in `rollback_checkpoint("migrate", ...)`.
- Modify: `synlynk/__init__.py:3543` (`init`) — wrap Step 3 onward in `rollback_checkpoint("init", ...)`; add `dry_run` parameter.
- Modify: `synlynk/upgrade.py` (`_run_upgrade`) — wrap in `rollback_checkpoint_upgrade(...)`; add `dry_run` parameter to `upgrade()`.
- Modify: `synlynk/cli.py` — add `rollback` subparser + dispatch; add `--dry-run` to `init`/`upgrade` subparsers.
- Modify: `tests/test_migrate.py`, `tests/test_upgrade.py` — wiring-level tests (checkpoint recorded, restore fires on injected failure).
- Modify: `synlynk/selftest.py`, `tests/test_selftest.py` — failure-injection variants of the PR #452 live scenarios, plus `rollback --last`/`--clear` coverage.

---

### Task 1: Rollback module — manifest I/O and path backup/restore helpers

**Files:**
- Create: `synlynk/rollback.py`
- Test: `tests/test_rollback.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rollback.py
import json
import os

import pytest

from synlynk import rollback


def test_dest_for_relative_path(tmp_path):
    dest = rollback._dest_for(str(tmp_path / "backup"), "project-docs/roadmap.md")
    assert dest == tmp_path / "backup" / "project-docs" / "roadmap.md"


def test_dest_for_absolute_path(tmp_path):
    dest = rollback._dest_for(str(tmp_path / "backup"), "/home/user/.synlynk/bin")
    assert dest == tmp_path / "backup" / "home" / "user" / ".synlynk" / "bin"
    assert not str(dest).startswith("//")


def test_backup_and_restore_file_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "CLAUDE.md"
    target.write_text("original content\n")
    backup_dir = rollback._backup_paths("op1", ["CLAUDE.md"])
    target.write_text("clobbered content\n")
    rollback._restore_paths(backup_dir, ["CLAUDE.md"])
    assert target.read_text() == "original content\n"


def test_backup_and_restore_dir_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / ".synlynk" / "project-docs"
    docs.mkdir(parents=True)
    (docs / "roadmap.md").write_text("v1\n")
    backup_dir = rollback._backup_paths("op1", [".synlynk/project-docs"])
    (docs / "roadmap.md").write_text("v2\n")
    (docs / "new-file.md").write_text("should be removed\n")
    rollback._restore_paths(backup_dir, [".synlynk/project-docs"])
    assert (docs / "roadmap.md").read_text() == "v1\n"
    assert not (docs / "new-file.md").exists()


def test_restore_removes_path_that_did_not_exist_before(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backup_dir = rollback._backup_paths("op1", ["never-existed.txt"])
    new_file = tmp_path / "never-existed.txt"
    new_file.write_text("created during the operation\n")
    rollback._restore_paths(backup_dir, ["never-existed.txt"])
    assert not new_file.exists()


def test_manifest_write_read_archive_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest = {"op_id": "abc123", "op_type": "init", "checkpoint_sha": "deadbeef"}
    rollback._write_manifest(manifest)
    assert os.path.exists(rollback.MANIFEST_PATH)
    loaded = rollback._read_manifest()
    assert loaded == manifest
    rollback._archive_manifest(manifest)
    assert not os.path.exists(rollback.MANIFEST_PATH)
    archived = rollback._read_manifest(op_id="abc123")
    assert archived == manifest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rollback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.rollback'`

- [ ] **Step 3: Write the module**

```python
# synlynk/rollback.py
"""Checkpoint-and-restore rollback mechanism for init/migrate/upgrade.

Two independent legs share one manifest format:
- Leg 1 (rollback_checkpoint): git-repo checkpoint for init/migrate.
- Leg 2 (rollback_checkpoint_upgrade): global install snapshot for upgrade,
  since upgrade never touches the git repo.
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
            # Nothing was backed up -> path did not exist before the op; remove it.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rollback.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/rollback.py tests/test_rollback.py
git commit -m "feat(rollback): manifest I/O and path backup/restore helpers"
```

---

### Task 2: Leg 1 — git checkpoint context manager for init/migrate

**Files:**
- Modify: `synlynk/rollback.py`
- Test: `tests/test_rollback.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rollback.py`:

```python
import subprocess


def _init_git_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)


def test_rollback_checkpoint_restores_on_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)
    hook = tmp_path / "untracked.txt"
    hook.write_text("original hook content\n")

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint("init", untracked_paths=["untracked.txt"]):
            tracked.write_text("v2 mutated\n")
            subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
            subprocess.run(["git", "commit", "-m", "mutation", "-q"], cwd=tmp_path, check=True)
            hook.write_text("clobbered hook content\n")
            raise RuntimeError("simulated mid-operation failure")

    assert tracked.read_text() == "v1\n"
    assert hook.read_text() == "original hook content\n"
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert "mutation" not in log
    # Manifest archived, not left live.
    assert not os.path.exists(rollback.MANIFEST_PATH)


def test_rollback_checkpoint_restores_dirty_tree_stash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)
    # Dirty the tree before the checkpoint starts.
    tracked.write_text("uncommitted local edit\n")

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint("init", untracked_paths=[]):
            tracked.write_text("mutated during op\n")
            raise RuntimeError("simulated failure")

    assert tracked.read_text() == "uncommitted local edit\n"


def test_rollback_checkpoint_leaves_manifest_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "initial", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("migrate", untracked_paths=[]) as manifest:
        assert manifest["op_type"] == "migrate"

    assert os.path.exists(rollback.MANIFEST_PATH)
    loaded = rollback._read_manifest()
    assert loaded["op_type"] == "migrate"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rollback.py -v -k checkpoint`
Expected: FAIL with `AttributeError: module 'synlynk.rollback' has no attribute 'rollback_checkpoint'`

- [ ] **Step 3: Implement the context manager**

Append to `synlynk/rollback.py`:

```python
def _git_head_sha() -> Optional[str]:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_dirty() -> bool:
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return bool(result.stdout.strip())


def restore_leg1(manifest: dict) -> None:
    sha = manifest.get("checkpoint_sha")
    if sha:
        subprocess.run(["git", "reset", "--hard", sha], check=True)
    stash_ref = manifest.get("stash_ref")
    if stash_ref:
        listing = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
        for line in listing.stdout.splitlines():
            if stash_ref in line:
                stash_id = line.split(":", 1)[0]
                popped = subprocess.run(["git", "stash", "pop", stash_id])
                if popped.returncode != 0:
                    print(
                        f"  ⚠ git stash pop failed for {stash_id} — resolve conflicts "
                        f"manually, then run: git stash drop {stash_id}"
                    )
                break
    if manifest.get("backup_dir"):
        _restore_paths(manifest["backup_dir"], manifest.get("untracked_paths", []))
    _archive_manifest(manifest)


@contextlib.contextmanager
def rollback_checkpoint(op_type: str, untracked_paths: Optional[list] = None):
    """Leg 1: repo checkpoint wrapping init()/cmd_migrate().

    Records the pre-op HEAD SHA (auto-stashing a dirty tree first) and backs up
    untracked_paths before yielding. On any exception raised inside the `with`
    block, restores the repo and untracked paths to their pre-op state, then
    re-raises.
    """
    untracked_paths = untracked_paths or []
    op_id = _new_op_id()
    stash_ref = None
    if _git_dirty():
        stash_ref = f"synlynk-rollback-{op_id}"
        subprocess.run(["git", "stash", "push", "-u", "-m", stash_ref], check=True)
    checkpoint_sha = _git_head_sha()
    backup_dir = _backup_paths(op_id, untracked_paths)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rollback.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/rollback.py tests/test_rollback.py
git commit -m "feat(rollback): Leg 1 git-checkpoint context manager for init/migrate"
```

---

### Task 3: Leg 2 — install-snapshot context manager for upgrade

**Files:**
- Modify: `synlynk/rollback.py`
- Test: `tests/test_rollback.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rollback.py`:

```python
def test_rollback_checkpoint_upgrade_pipx_restore_reinstalls_old_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recorded = []
    monkeypatch.setattr(
        rollback.subprocess, "run",
        lambda args, **kw: recorded.append(list(args)) or subprocess.CompletedProcess(args, 0),
    )

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint_upgrade("0.12.0", "pipx"):
            raise RuntimeError("simulated pipx failure")

    assert any(
        call[:2] == ["pipx", "install"] and "v0.12.0" in call[2]
        for call in recorded
    )
    assert not os.path.exists(rollback.MANIFEST_PATH)


def test_rollback_checkpoint_upgrade_script_restores_bin_and_lib(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    bin_dir = home / ".synlynk" / "bin"
    lib_dir = home / ".synlynk" / "lib"
    bin_dir.mkdir(parents=True)
    lib_dir.mkdir(parents=True)
    (bin_dir / "synlynk").write_text("#!/bin/sh\necho old\n")
    monkeypatch.setattr(rollback.os.path, "expanduser", lambda p: p.replace("~", str(home)))

    with pytest.raises(RuntimeError):
        with rollback.rollback_checkpoint_upgrade("0.12.0", "script"):
            (bin_dir / "synlynk").write_text("#!/bin/sh\necho new\n")
            raise RuntimeError("simulated script install failure")

    assert (bin_dir / "synlynk").read_text() == "#!/bin/sh\necho old\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rollback.py -v -k upgrade`
Expected: FAIL with `AttributeError: module 'synlynk.rollback' has no attribute 'rollback_checkpoint_upgrade'`

- [ ] **Step 3: Implement Leg 2**

Append to `synlynk/rollback.py`:

```python
_SCRIPT_INSTALL_PATHS = ("~/.synlynk/bin", "~/.synlynk/lib")


def restore_leg2(manifest: dict) -> None:
    install_type = manifest.get("install_type")
    old_version = manifest.get("previous_version")
    if install_type == "pipx" and old_version:
        subprocess.run(
            [
                "pipx", "install",
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rollback.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/rollback.py tests/test_rollback.py
git commit -m "feat(rollback): Leg 2 install-snapshot context manager for upgrade"
```

---

### Task 4: Wire Leg 1 into `cmd_migrate()`

**Files:**
- Modify: `synlynk/db.py:1185-1296` (`cmd_migrate`)
- Modify: `tests/test_migrate.py`

The checkpoint must be recorded **before** `_migrate_import()` runs and must wrap through migrate's own final `git commit` — that commit is exactly what `git reset --hard <checkpoint_sha>` needs to undo as a single unit if anything downstream fails.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_migrate.py`:

```python
def test_migrate_rolls_back_on_mid_operation_failure(tmp_path, monkeypatch):
    import subprocess as sp
    from synlynk import db as db_mod

    monkeypatch.chdir(tmp_path)
    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    docs_dir = tmp_path / "project-docs"
    docs_dir.mkdir()
    (docs_dir / "roadmap.md").write_text("# roadmap\n")
    sp.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    sp.run(["git", "commit", "-m", "seed", "-q"], cwd=tmp_path, check=True)
    before_head = sp.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure writing sentinel")

    monkeypatch.setattr(db_mod, "_migrate_dr_mirror", boom)

    with pytest.raises(RuntimeError):
        db_mod.cmd_migrate()

    after_head = sp.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert after_head == before_head
    assert not (tmp_path / ".synlynk" / ".synlynk_migrated").exists()
```

Add `import pytest` at the top of `tests/test_migrate.py` if not already present.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrate.py -v -k rolls_back`
Expected: FAIL — migrate currently swallows the `git commit` `CalledProcessError` and doesn't propagate other failures as a rollback-triggering exception; `_migrate_dr_mirror` raising `RuntimeError` today is either uncaught (crashes without cleanup) or not rolled back. The test should fail because `after_head != before_head` (no rollback happens) or because no exception propagates as expected — confirm the actual failure mode before writing the fix.

- [ ] **Step 3: Wrap `cmd_migrate()` in the Leg 1 checkpoint**

In `synlynk/db.py`, modify the body of `cmd_migrate` starting right after the `dry_run` early return (line 1240) through the end of the function (line 1296). Replace:

```python
    print("  ▶ Importing flat files → state.db ...")
    try:
        _migrate_import(docs_dir)
    except MigrationImportError as exc:
        print(f"  ✗ {exc}")
        raise SystemExit(1)

    backup_dir = _synlynk_project_docs_dir()
    print(f"  ▶ Copying {docs_dir}/ → {backup_dir}/ ...")
    if os.path.exists(backup_dir):
        _shutil.rmtree(backup_dir)
    _shutil.copytree(docs_dir, backup_dir)

    _migrate_dr_mirror(backup_dir)

    try:
        subprocess.run(
            ["git", "rm", "--cached", "-r", "--quiet", docs_dir],
            check=True,
            stderr=subprocess.DEVNULL,
        )
        print(f"  ✓ git rm --cached {docs_dir}/")
    except subprocess.CalledProcessError:
        print("  ⚠ git rm --cached failed (may not be tracked) — continuing")

    gitignore = ".gitignore"
    entry = f"{docs_dir}/\n"
    already = False
    if os.path.exists(gitignore):
        with open(gitignore) as f:
            already = any(docs_dir in line for line in f)
    if not already:
        with open(gitignore, "a") as f:
            f.write(entry)
        print(f"  ✓ Added {docs_dir}/ to .gitignore")

    with open(sentinel, "w") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    print("  ✓ Sentinel written")

    try:
        subprocess.run(["git", "add", ".gitignore", sentinel], check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "chore: synlynk migrate — project-docs moved to .synlynk, "
                "state.db is now source of truth",
            ],
            check=True,
        )
        print("  ✓ Committed")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ Git commit failed (continuing): {e}")
```

with:

```python
    from synlynk.rollback import rollback_checkpoint

    backup_dir = _synlynk_project_docs_dir()
    with rollback_checkpoint("migrate", untracked_paths=[
        os.path.join(".synlynk", "state.db"),
        backup_dir,
        sentinel,
    ]):
        print("  ▶ Importing flat files → state.db ...")
        try:
            _migrate_import(docs_dir)
        except MigrationImportError as exc:
            print(f"  ✗ {exc}")
            raise

        print(f"  ▶ Copying {docs_dir}/ → {backup_dir}/ ...")
        if os.path.exists(backup_dir):
            _shutil.rmtree(backup_dir)
        _shutil.copytree(docs_dir, backup_dir)

        _migrate_dr_mirror(backup_dir)

        subprocess.run(
            ["git", "rm", "--cached", "-r", "--quiet", docs_dir],
            check=True,
            stderr=subprocess.DEVNULL,
        )
        print(f"  ✓ git rm --cached {docs_dir}/")

        gitignore = ".gitignore"
        entry = f"{docs_dir}/\n"
        already = False
        if os.path.exists(gitignore):
            with open(gitignore) as f:
                already = any(docs_dir in line for line in f)
        if not already:
            with open(gitignore, "a") as f:
                f.write(entry)
            print(f"  ✓ Added {docs_dir}/ to .gitignore")

        with open(sentinel, "w") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        print("  ✓ Sentinel written")

        subprocess.run(["git", "add", ".gitignore", sentinel], check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "chore: synlynk migrate — project-docs moved to .synlynk, "
                "state.db is now source of truth",
            ],
            check=True,
        )
        print("  ✓ Committed")
```

Note this is a **behavior change**, called out explicitly: previously `git rm --cached` failing or `git commit` failing only printed a warning and continued, silently leaving a half-migrated repo. Now any failure in this block raises and triggers a full automatic rollback — this is the exact gap identified in the spec's "migrate is not currently atomic" risk item. `MigrationImportError` is re-raised (not converted to `SystemExit`) so it's caught by the checkpoint's `except BaseException` and triggers rollback before the caller sees it; `cli.py`'s dispatch for `migrate` does not currently catch exceptions from `cmd_migrate`, so add a thin translation at the call site in Task 7 if needed — for this task, leave the exception propagating and confirm via the test above.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_migrate.py -v`
Expected: PASS, including `test_migrate_rolls_back_on_mid_operation_failure`

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass (existing migrate tests, e.g. `test_migrate_db_creates_new_tables`, must still pass unchanged since they don't invoke `cmd_migrate` directly)

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_migrate.py
git commit -m "feat(migrate): wrap cmd_migrate in Leg 1 rollback checkpoint"
```

---

### Task 5: Wire Leg 1 into `init()`

**Files:**
- Modify: `synlynk/__init__.py:3543` (`init`)
- Modify: `tests/test_init_business_goals.py` (or create `tests/test_init_rollback.py` if that file is scoped to business-goal seeding only — check its imports/fixtures first before adding here)

- [ ] **Step 1: Write the failing test**

Create `tests/test_init_rollback.py`:

```python
import json
import subprocess

import pytest

import synlynk


def _init_git_repo(path):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)


def test_init_rolls_back_on_mid_operation_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "seed", "-q"], cwd=tmp_path, check=True)
    existing_claude = tmp_path / "CLAUDE.md"
    existing_claude.write_text("pre-existing content\n")

    monkeypatch.setattr(synlynk, "discover_agents", lambda: [])
    monkeypatch.setattr(
        synlynk, "_static_scan",
        lambda path: {
            "project_name": "test", "commit_count": 1, "languages": ["Python"],
            "recent_topics": [], "has_structured_commits": True,
        },
    )

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure installing pre-commit hook")

    monkeypatch.setattr(synlynk, "install_pre_commit_hook", boom)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    with pytest.raises(RuntimeError):
        synlynk.init(force=False, agents=["claude"], mode="solo")

    assert existing_claude.read_text() == "pre-existing content\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_init_rollback.py -v`
Expected: FAIL — today's `init()` has no rollback wrapper, so `CLAUDE.md` gets overwritten by `_write_instruction_file` before `install_pre_commit_hook` raises, and the assertion on `existing_claude.read_text()` fails.

- [ ] **Step 3: Wrap `init()` Step 3 onward in the Leg 1 checkpoint**

In `synlynk/__init__.py`, the mutating work starts at `# ── Step 3: Create directories + write skeleton` (line 3590) and runs through the `install_pre_commit_hook(repo_root=Path.cwd())` call (line 3649) and the `config.json`/`model_rates.json` writes right after it (lines 3651–3666). Wrap that whole span. Replace the block from line 3590 (`dd = _docs_dir()`) through line 3666 (end of the `model_rates.json` write) by indenting it one level inside a new `with` block, and add the import + `untracked_paths` list right before it:

```python
    from synlynk.rollback import rollback_checkpoint

    pre_commit_hook_path = os.path.join(".git", "hooks", "pre-commit")
    config_path = os.path.join(".synlynk", "config.json")
    with rollback_checkpoint("init", untracked_paths=[
        pre_commit_hook_path,
        config_path,
        os.path.join(".synlynk", "model_rates.json"),
        os.path.join(".synlynk", "instruction_manifest.json"),
    ]):
        # ── Step 3: Create directories + write skeleton ─────────────────────
        dd = _docs_dir()
        _print_step(3, f"Bootstrapping {dd}/")
        for d in [dd, os.path.join(dd, "devlogs"), ".synlynk",
                  LOGS_DIR, PROMPTS_DIR]:
            if not os.path.exists(d):
                os.makedirs(d)

        written = _write_informed_skeleton(scan, skip_existing=not force)
        if written:
            for p, label in written:
                print(f"  {_GREEN}✓{_RESET} {p}  {_DIM}({label}){_RESET}")
        else:
            print(f"  {_DIM}All docs already exist — skipped (use --force to overwrite){_RESET}")

        # Write agent instruction files using _write_instruction_file().
        agent_set = set(agents) if agents is not None else {a["name"] for a in functional} or {"claude", "agy", "codex", "grok"}
        templates = _build_templates(org=org, repo=repo, project_id=project_id)

        # Core trio: only write if agent was discovered as functional.
        trio_content = {
            "CLAUDE.md":   (templates.get("CLAUDE.md", ""), "html"),
            "GEMINI.md":   (templates.get("GEMINI.md", ""), "html"),
            "AGENTS.md":   (templates.get("AGENTS.md", ""), "html"),
            "GROK.md":     (templates.get("GROK.md", ""), "html"),
        }
        _agent_guards = {"CLAUDE.md": "claude", "GEMINI.md": "agy", "AGENTS.md": "codex", "GROK.md": "grok"}
        for fname, (content, mstyle) in trio_content.items():
            required = _agent_guards[fname]
            if required not in agent_set:
                continue
            _write_instruction_file(fname, required, content, mstyle)

        # Extended targets: written based on environment detection.
        # Guards are sourced from _INSTRUCTION_TARGETS[i][3] (detection_fn).
        _target_detection = {fpath: fn for fpath, _, _, fn in _INSTRUCTION_TARGETS}
        extended = [
            (".cursor/rules/synlynk.mdc",       "cursor",    "none", _build_cursor_mdc()),
            (".github/copilot-instructions.md",  "copilot",   "html", _build_copilot_instructions()),
            (".windsurfrules",                   "windsurf",  "hash", _build_windsurf_rules()),
            ("AI_INSTRUCTIONS.md",              "universal",  "html", templates.get("AI_INSTRUCTIONS.md", "")),
        ]
        for fpath, tool, mstyle, content in extended:
            if _target_detection[fpath]():
                # marker_style='none' means synlynk owns the whole file — always overwrites
                _write_instruction_file(fpath, tool, content, mstyle)

        # Write manifest of all tracked files with their SHAs.
        manifest_entries = {}
        for fpath, tool, mstyle, _ in _INSTRUCTION_TARGETS:
            if not os.path.exists(fpath):
                continue
            file_content = open(fpath).read()
            section = _extract_synlynk_section(file_content, mstyle)
            if section is not None:
                manifest_entries[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}
        if manifest_entries:
            _write_instruction_manifest(manifest_entries)

        install_pre_commit_hook(repo_root=Path.cwd())

        # Write config.json if needed.
        config_json_content = templates.get("config.json", "")
        if config_json_content:
            if not os.path.exists(config_path) or force:
                with open(config_path, "w") as f:
                    f.write(config_json_content)

        rates_path = os.path.join(".synlynk", "model_rates.json")
        if not os.path.exists(rates_path):
            from synlynk.costs import _HARDCODED_FALLBACK_RATES
            rates_seed = dict(_HARDCODED_FALLBACK_RATES)
            rates_seed["rates_updated_at"] = time.strftime("%Y-%m-%d")
            with open(rates_path, "w") as f:
                json.dump(rates_seed, f, indent=2)
            print(f"  ✓ Created {rates_path}")
```

The rest of `init()` (Step 4 LLM enrichment onward, lines 3668+) stays at the original indentation, outside the `with` block — those steps are interactive/config-only and not part of what this rollback covers (enrichment doesn't overwrite anything the checkpoint needs to protect, and the email/industry prompts have no destructive file writes).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_init_rollback.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass, including existing `tests/test_init_business_goals.py` and the `_scenario_init_existing_files` coverage exercised via `tests/test_selftest.py`

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_init_rollback.py
git commit -m "feat(init): wrap init() write surface in Leg 1 rollback checkpoint"
```

---

### Task 6: Wire Leg 2 into `_run_upgrade()`

**Files:**
- Modify: `synlynk/upgrade.py`
- Modify: `tests/test_upgrade.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_upgrade.py`:

```python
def test_run_upgrade_pipx_records_leg2_manifest(tmp_path, monkeypatch):
    import synlynk.upgrade as upgrade_mod
    from synlynk import rollback

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(upgrade_mod, "VERSION", "0.12.0")
    monkeypatch.setattr(upgrade_mod, "_detect_install_type", lambda: "pipx")
    monkeypatch.setattr(upgrade_mod, "_get_pipx_source", lambda: "")
    monkeypatch.setattr(
        upgrade_mod.subprocess, "run",
        lambda args, **kw: __import__("subprocess").CompletedProcess(args, 0),
    )

    upgrade_mod._run_upgrade("0.13.0")

    manifest = rollback._read_manifest()
    assert manifest["op_type"] == "upgrade"
    assert manifest["previous_version"] == "0.12.0"
    assert manifest["install_type"] == "pipx"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_upgrade.py -v -k leg2`
Expected: FAIL — `rollback._read_manifest()` returns `None` because `_run_upgrade` doesn't write a manifest yet

- [ ] **Step 3: Wrap `_run_upgrade()` in the Leg 2 checkpoint**

In `synlynk/upgrade.py`, modify `_run_upgrade`:

```python
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
```

Note: `_run_upgrade` today never raises on subprocess failure (it prints a warning and returns) — that's unchanged. The Leg 2 checkpoint's automatic-restore-on-exception only fires for genuinely uncaught exceptions (e.g. `subprocess.run` itself raising `FileNotFoundError` if `pipx` isn't on `PATH`); the manifest is still written unconditionally so `synlynk rollback --last` remains available even after a "soft" failure that only printed a warning.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_upgrade.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add synlynk/upgrade.py tests/test_upgrade.py
git commit -m "feat(upgrade): wrap _run_upgrade in Leg 2 rollback checkpoint"
```

---

### Task 7: `synlynk rollback [--last|<op-id>|--clear]` CLI command

**Files:**
- Modify: `synlynk/rollback.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_rollback.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rollback.py`:

```python
def test_cmd_rollback_last_restores_and_archives(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("init", untracked_paths=[]):
        tracked.write_text("v2\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "unwanted change", "-q"], cwd=tmp_path, check=True)

    assert tracked.read_text() == "v2\n"  # succeeded, no auto-rollback

    rollback.cmd_rollback(last=True)

    assert tracked.read_text() == "v1\n"
    assert not os.path.exists(rollback.MANIFEST_PATH)


def test_cmd_rollback_clear_discards_without_restoring(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "initial", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("init", untracked_paths=[]):
        pass

    assert os.path.exists(rollback.MANIFEST_PATH)
    rollback.cmd_rollback(clear=True)
    assert not os.path.exists(rollback.MANIFEST_PATH)
    archived = os.listdir(rollback.ARCHIVE_DIR)
    assert len(archived) == 1


def test_cmd_rollback_no_manifest_prints_message(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rollback.cmd_rollback(last=True)
    captured = capsys.readouterr()
    assert "no rollback checkpoint" in captured.out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rollback.py -v -k cmd_rollback`
Expected: FAIL with `AttributeError: module 'synlynk.rollback' has no attribute 'cmd_rollback'`

- [ ] **Step 3: Implement `cmd_rollback` and dispatch to the right leg**

Append to `synlynk/rollback.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rollback.py -v`
Expected: PASS (all rollback tests, 14+ total)

- [ ] **Step 5: Wire the CLI subcommand**

In `synlynk/cli.py`, add the subparser right after the `migrate_parser` block (after line 296, before `probe_parser = subparsers.add_parser(...)` at line 298):

```python
    rollback_parser = subparsers.add_parser(
        "rollback", help="Undo the last init/migrate/upgrade if something went wrong"
    )
    rollback_group = rollback_parser.add_mutually_exclusive_group()
    rollback_group.add_argument("--last", action="store_true",
                                help="Roll back the most recent checkpoint (default)")
    rollback_group.add_argument("--op-id", default=None, dest="op_id",
                                help="Roll back a specific archived checkpoint by op-id")
    rollback_group.add_argument("--clear", action="store_true",
                                help="Discard the current checkpoint without restoring")
```

Add the dispatch case right after the `migrate` case (after line 1029, before `elif args.command == "probe":` at line 1030):

```python
    elif args.command == "rollback":
        from synlynk.rollback import cmd_rollback
        cmd_rollback(
            last=getattr(args, "last", False) or not (getattr(args, "op_id", None) or getattr(args, "clear", False)),
            op_id=getattr(args, "op_id", None),
            clear=getattr(args, "clear", False),
        )
```

- [ ] **Step 6: Verify the CLI parses**

Run: `python3 -m synlynk rollback --help`
Expected: prints usage showing `--last`, `--op-id`, `--clear`

Run: `python3 -m synlynk rollback` (in a repo with no active checkpoint)
Expected: `  No rollback checkpoint found for this session.`

- [ ] **Step 7: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add synlynk/rollback.py synlynk/cli.py tests/test_rollback.py
git commit -m "feat(rollback): add synlynk rollback CLI command"
```

---

### Task 8: `--dry-run` for `init` and `upgrade` (Approach C)

**Files:**
- Modify: `synlynk/__init__.py` (`init`)
- Modify: `synlynk/upgrade.py` (`upgrade`)
- Modify: `synlynk/cli.py`
- Test: `tests/test_init_rollback.py`, `tests/test_upgrade.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_init_rollback.py`:

```python
def test_init_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "seed", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setattr(synlynk, "discover_agents", lambda: [])
    monkeypatch.setattr(
        synlynk, "_static_scan",
        lambda path: {
            "project_name": "test", "commit_count": 1, "languages": ["Python"],
            "recent_topics": [], "has_structured_commits": True,
        },
    )

    synlynk.init(force=False, agents=["claude"], mode="solo", dry_run=True)

    assert not (tmp_path / ".synlynk").exists()
    assert not (tmp_path / "CLAUDE.md").exists()
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert ".github/copilot-instructions.md" in captured.out or "always overwrite" in captured.out.lower()
```

Append to `tests/test_upgrade.py`:

```python
def test_upgrade_dry_run_makes_no_subprocess_calls(tmp_path, monkeypatch, capsys):
    import synlynk.upgrade as upgrade_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(upgrade_mod, "VERSION", "0.12.0")
    calls = []
    monkeypatch.setattr(
        upgrade_mod.subprocess, "run",
        lambda *a, **kw: calls.append(a) or (_ for _ in ()).throw(AssertionError("should not run")),
    )
    monkeypatch.setattr(upgrade_mod, "_detect_install_type", lambda: "pipx")

    upgrade_mod.upgrade(dry_run=True)

    assert calls == []
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "pipx" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_init_rollback.py tests/test_upgrade.py -v -k dry_run`
Expected: FAIL with `TypeError: init() got an unexpected keyword argument 'dry_run'` and similarly for `upgrade()`

- [ ] **Step 3: Add `dry_run` to `init()`**

In `synlynk/__init__.py`, change the signature (line 3543):

```python
def init(force: bool = False, agents: list = None,
         org: str = None, repo: str = None, project_id: str = None,
         mode: str = "solo", dry_run: bool = False) -> None:
```

Immediately after `_print_step(1, "Scanning repository")` and the `synlynk_exists` check (before `scan = _static_scan(".")` — insert right after line 3558's `print` call, before line 3560), add:

```python
    if dry_run:
        print("  DRY RUN — no files will be written\n")
        dd_preview = _docs_dir()
        for d in [dd_preview, os.path.join(dd_preview, "devlogs"), ".synlynk", LOGS_DIR, PROMPTS_DIR]:
            if not os.path.exists(d):
                print(f"  would create: {d}/")
        print("  would always overwrite (marker_style='none', regardless of --force):")
        for fpath in (".cursor/rules/synlynk.mdc", ".github/copilot-instructions.md",
                      ".windsurfrules", "AI_INSTRUCTIONS.md"):
            if os.path.exists(fpath):
                print(f"    ⚠ {fpath}  (already exists — would be overwritten unconditionally)")
            else:
                print(f"    {fpath}  (would be created)")
        return
```

- [ ] **Step 4: Add `dry_run` to `upgrade()`**

In `synlynk/upgrade.py`, change the `upgrade` signature:

```python
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
```

(the rest of the function body is unchanged, following the existing `try/finally` block).

- [ ] **Step 5: Wire `--dry-run` in the CLI**

In `synlynk/cli.py`, change the `upgrade` subparser (line 231) from:

```python
    subparsers.add_parser("upgrade", help="Check for and apply updates")
```

to:

```python
    upgrade_parser = subparsers.add_parser("upgrade", help="Check for and apply updates")
    upgrade_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                help="Preview what would be upgraded without installing")
```

Add to `init_parser` (right after the `--wizard` argument at line 229):

```python
    init_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                             help="Preview what init would write without writing anything")
```

Update the two dispatch call sites. `init` dispatch (line 781-782):

```python
            init(force=args.force, agents=agents, mode=args.mode,
                 org=args.org, repo=args.repo, project_id=args.project_id,
                 dry_run=getattr(args, "dry_run", False))
```

`upgrade` dispatch (line 787):

```python
    elif args.command == "upgrade":
        upgrade(dry_run=getattr(args, "dry_run", False))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_init_rollback.py tests/test_upgrade.py -v`
Expected: PASS

- [ ] **Step 7: Manual CLI smoke test**

Run: `cd /tmp && rm -rf dryrun-smoke && mkdir dryrun-smoke && cd dryrun-smoke && git init -q && python3 -m synlynk init --dry-run`
Expected: prints `DRY RUN`, lists directories that would be created and the four always-overwrite extended targets; `.synlynk/` is NOT created afterward — confirm with `ls -la`

- [ ] **Step 8: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 9: Commit**

```bash
git add synlynk/__init__.py synlynk/upgrade.py synlynk/cli.py tests/test_init_rollback.py tests/test_upgrade.py
git commit -m "feat(dry-run): add --dry-run to init and upgrade"
```

---

### Task 9: Failure-injection live selftest scenarios + rollback CLI coverage

**Files:**
- Modify: `synlynk/selftest.py` (`_scenario_migrate`, `_scenario_upgrade`, `_scenario_init_existing_files`)
- Modify: `tests/test_selftest.py`

This extends the PR #452 scenario functions with the failure-injection technique the spec requires, reusing `_ensure_workspace_scaffold`/`_chdir`/`_capture_call` exactly as those functions already do — no new fixtures.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_selftest.py`:

```python
def test_scenario_migrate_failure_injection_triggers_rollback():
    from synlynk.selftest import (
        ScenarioContext, _scenario_migrate_failure_injection,
    )

    ctx = ScenarioContext(repo_path="", live=True)
    result = _scenario_migrate_failure_injection({"command": "migrate"}, ctx)
    assert result.status == "pass", result.detail


def test_scenario_upgrade_failure_injection_triggers_rollback():
    from synlynk.selftest import (
        ScenarioContext, _scenario_upgrade_failure_injection,
    )

    ctx = ScenarioContext(repo_path="", live=True)
    result = _scenario_upgrade_failure_injection({"command": "upgrade"}, ctx)
    assert result.status == "pass", result.detail
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_selftest.py -v -k failure_injection`
Expected: FAIL with `ImportError: cannot import name '_scenario_migrate_failure_injection'`

- [ ] **Step 3: Add the failure-injection scenario functions**

In `synlynk/selftest.py`, add these two functions right after `_scenario_migrate` (after line 848, before `def _scenario_upgrade`):

```python
def _scenario_migrate_failure_injection(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    """Injects a failure mid-migrate and asserts the workspace is fully rolled back."""
    import synlynk as synlynk_pkg
    import synlynk.db as db_mod
    from synlynk import rollback

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    before_docs = _seed_migrate_workspace(workspace)
    before_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workspace, capture_output=True, text=True
    ).stdout.strip()

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure: simulated git rm --cached failure")

    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)), patch.object(
        db_mod, "_migrate_dr_mirror", boom
    ):
        result, output, _ = _capture_call(entry["command"], db_mod.cmd_migrate)

    if result.status != "fail":
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail=f"expected injected failure to propagate, got: {result.status}",
        )

    after_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workspace, capture_output=True, text=True
    ).stdout.strip()
    if after_head != before_head:
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="migrate rollback did not reset HEAD to the pre-op checkpoint",
        )
    sentinel = workspace / ".synlynk" / ".synlynk_migrated"
    if sentinel.exists():
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="migrate rollback left the sentinel file behind",
        )
    manifest_live = workspace / ".synlynk" / "rollback" / "last.json"
    if manifest_live.exists():
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="rollback manifest was not archived after auto-rollback",
        )
    return ScenarioResult(
        command=entry["command"], status="pass",
        detail="migrate auto-rolled back to the pre-op checkpoint after an injected failure",
    )
```

Add this one right after `_scenario_upgrade` (after line 932, before `_TRIVIAL_PROMPT = ...`):

```python
def _scenario_upgrade_failure_injection(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    """Injects a failure mid-upgrade for a script install and asserts bin/lib are restored."""
    import importlib
    import synlynk as synlynk_pkg

    upgrade_mod = importlib.import_module("synlynk.upgrade")
    workspace = _ensure_workspace_scaffold(ctx)
    home = workspace / "fake-home"
    bin_dir = home / ".synlynk" / "bin"
    lib_dir = home / ".synlynk" / "lib"
    bin_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "synlynk").write_text("#!/bin/sh\necho old-version\n")
    before = (bin_dir / "synlynk").read_bytes()

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure: simulated install script failure")

    with _chdir(workspace), patch.object(
        synlynk_pkg, "_detect_install_type", return_value="script"
    ), patch.object(upgrade_mod.subprocess, "run", boom), patch.dict(
        upgrade_mod.os.environ, {"HOME": str(home)}
    ), patch.object(
        upgrade_mod.os.path, "expanduser",
        side_effect=lambda p: p.replace("~", str(home)),
    ):
        result, output, _ = _capture_call(
            entry["command"], lambda: upgrade_mod._run_upgrade("9.9.9")
        )

    if result.status != "fail":
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail=f"expected injected failure to propagate, got: {result.status}",
        )
    if (bin_dir / "synlynk").read_bytes() != before:
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="upgrade rollback did not restore ~/.synlynk/bin after an injected failure",
        )
    return ScenarioResult(
        command=entry["command"], status="pass",
        detail="upgrade auto-rolled back the script install after an injected failure",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v -k failure_injection`
Expected: PASS (2 tests)

- [ ] **Step 5: Add dedicated `rollback --last` / `--clear` selftest coverage**

Append to `tests/test_selftest.py`:

```python
def test_synlynk_rollback_last_via_cli(tmp_path, monkeypatch):
    import subprocess as sp
    from synlynk import rollback

    monkeypatch.chdir(tmp_path)
    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    sp.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    sp.run(["git", "commit", "-m", "seed", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("init", untracked_paths=[]):
        tracked.write_text("v2\n")
        sp.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
        sp.run(["git", "commit", "-m", "unwanted", "-q"], cwd=tmp_path, check=True)

    from synlynk.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["rollback", "--last"])
    assert args.command == "rollback"
    assert args.last is True

    rollback.cmd_rollback(last=True)
    assert tracked.read_text() == "v1\n"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_selftest.py -v -k rollback_last_via_cli`
Expected: PASS

- [ ] **Step 7: Register the new scenarios (optional live-mode wiring)**

If `SELFTEST_SCENARIOS` in `synlynk/selftest.py` (around line 1053-1067) is meant to map one scenario per taxonomy command (it currently is — one function per `command` key), do **not** register `_scenario_migrate_failure_injection`/`_scenario_upgrade_failure_injection` there, since they're not a new taxonomy command. They're invoked directly by the new tests added in Steps 1-6 above, not through `run_selftest()`. Confirm this by checking that `tests/test_selftest.py`'s `EXPECTED_LIVE_SCENARIOS` list (line 8) is unchanged by this task — it should still list exactly the commands from PR #452, not the failure-injection function names.

- [ ] **Step 8: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, no regressions

- [ ] **Step 9: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "test(rollback): failure-injection coverage for migrate/upgrade + rollback CLI test"
```

---

## Self-Review Notes

**Spec coverage:**
- Leg 1 (git checkpoint + untracked-state backup for init/migrate, checkpoint before migrate's own commit) → Tasks 1, 2, 4, 5.
- Leg 2 (pipx reinstall-by-tag / script file-backup for upgrade) → Tasks 1, 3, 6.
- Shared `synlynk rollback [--last|<op-id>|--clear]` CLI → Task 7.
- Manifest format + archive-after-use → Task 1, exercised throughout.
- Approach C dry-run extension → Task 8.
- Testing section (failure-injection variants of #451 scenarios, dedicated `rollback --last`/`--clear` tests) → Task 9.
- Error handling within rollback itself (stash-pop conflict message, backup dir preserved on failed restore) → covered in Task 2's `restore_leg1` implementation; the "don't delete backup dir if git reset fails" case is a `subprocess.run(..., check=True)` that will raise rather than silently continue — this surfaces the failure loudly rather than swallowing it, consistent with the spec's intent, though it is not separately unit-tested in this plan (flagging as a known gap rather than silently skipping it).

**Out of scope confirmed unchanged:** no transaction journal, no cross-session rollback, no remediation for `pip`/`unknown` upgrade install types — matches the spec's explicit exclusions.

**Type/naming consistency:** `rollback_checkpoint` (Leg 1) vs `rollback_checkpoint_upgrade` (Leg 2) — deliberately different names since they take different arguments (`op_type: str` vs `current_version, install_type`) and wrap different call sites; `cmd_rollback` is the single CLI-facing entrypoint used consistently across Task 7 and Task 9's CLI test.
