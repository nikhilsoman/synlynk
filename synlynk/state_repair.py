"""Crash-safe, idempotent state promotion and explicit quarantine tools."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from synlynk.state_registry import (
    StateRegistryError,
    ensure_registered_product,
    identity_metadata,
    product_identity,
    registered_canonical_path,
    registry_lock,
    update_registered_product,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _normalized_copy(source: Path, destination_dir: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix=".state-promote-", suffix=".db", dir=destination_dir)
    os.close(fd)
    temporary = Path(name)
    source_conn = sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True, timeout=30.0)
    destination_conn = sqlite3.connect(str(temporary), timeout=30.0)
    try:
        source_conn.backup(destination_conn)
        destination_conn.commit()
        if destination_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError(f"source state DB failed integrity check: {source}")
        destination_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        destination_conn.execute("PRAGMA journal_mode=DELETE")
        destination_conn.commit()
    finally:
        destination_conn.close()
        source_conn.close()
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{temporary}{suffix}")
        if sidecar.exists():
            sidecar.unlink()
    _fsync_file(temporary)
    return temporary


def register_existing_state(
    path: str | Path,
    *,
    slug: str,
    product_id: str | None = None,
    repo_path: str | Path | None = None,
) -> dict:
    """Register an existing canonical DB after a read-only integrity check."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError(f"state DB failed integrity check: {source}")
    entry = ensure_registered_product(
        slug,
        source,
        product_id or product_identity(slug),
        repo_path=Path(repo_path) if repo_path else None,
    )
    with sqlite3.connect(str(source), timeout=30.0) as conn:
        identity_metadata(conn, product_id=entry["product_id"], mode="canonical", path=source)
        conn.commit()
    return {"disposition": "registered", "path": str(source), "product_id": entry["product_id"]}


def promote_state_db(
    source: str | Path,
    destination: str | Path,
    *,
    slug: str,
    product_id: str | None = None,
    repo_path: str | Path | None = None,
) -> dict:
    """Promote a verified source without overwriting a different destination."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination_path.with_name(f".{destination_path.name}.promote.lock")
    with registry_lock(lock_path):
        if source_path == destination_path:
            with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as conn:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError(f"source state DB failed integrity check: {source_path}")
            entry = ensure_registered_product(
                slug,
                destination_path,
                product_id or product_identity(slug),
                repo_path=Path(repo_path) if repo_path else None,
            )
            return {
                "disposition": "already-complete",
                "source": str(source_path),
                "destination": str(destination_path),
                "sha256": _sha256(destination_path),
                "product_id": entry["product_id"],
            }
        temporary = _normalized_copy(source_path, destination_path.parent)
        try:
            digest = _sha256(temporary)
            if destination_path.exists():
                if _sha256(destination_path) != digest:
                    raise StateRegistryError(
                        f"refusing to overwrite different canonical DB: {destination_path}"
                    )
                disposition = "already-complete"
                temporary.unlink()
            else:
                os.replace(temporary, destination_path)
                _fsync_dir(destination_path.parent)
                disposition = "promoted"
            entry = ensure_registered_product(
                slug,
                destination_path,
                product_id or product_identity(slug),
                repo_path=Path(repo_path) if repo_path else None,
            )
            return {
                "disposition": disposition,
                "source": str(source_path),
                "destination": str(destination_path),
                "sha256": digest,
                "product_id": entry["product_id"],
            }
        finally:
            if temporary.exists():
                temporary.unlink()


def quarantine_state_db(
    path: str | Path,
    *,
    slug: str,
    quarantine_root: str | Path | None = None,
    apply: bool = False,
) -> dict:
    """Classify a non-canonical DB; move it read-only only with --apply."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    canonical = registered_canonical_path(slug)
    if canonical is not None and canonical == source:
        raise StateRegistryError("refusing to quarantine the registry-selected canonical DB")
    root = Path(quarantine_root or Path.home() / ".synlynk" / "quarantine").expanduser().resolve()
    target = root / f"{source.stem}-{int(time.time())}-{_sha256(source)[:12]}"
    result = {"disposition": "planned", "source": str(source), "destination": str(target)}
    if not apply:
        return result
    target.mkdir(parents=True, exist_ok=False)
    moved = []
    try:
        for candidate in (source, Path(f"{source}-wal"), Path(f"{source}-shm"), Path(f"{source}-journal")):
            if candidate.exists():
                destination = target / candidate.name
                os.replace(candidate, destination)
                destination.chmod(0o400)
                moved.append(str(destination))
        manifest = target / "manifest.json"
        manifest.write_text(json.dumps({"source": str(source), "files": moved}, indent=2) + "\n")
        manifest.chmod(0o400)
        _fsync_dir(target)
        result.update({"disposition": "quarantined", "files": moved})
    except Exception:
        for moved_path in reversed(moved):
            os.replace(moved_path, source.parent / Path(moved_path).name)
        shutil.rmtree(target, ignore_errors=True)
        raise
    return result


def restore_state_db(
    snapshot: str | Path,
    destination: str | Path,
    *,
    slug: str,
    product_id: str | None = None,
    repo_path: str | Path | None = None,
    archive_root: str | Path | None = None,
    apply: bool = False,
) -> dict:
    """Validate a snapshot and plan/apply an explicit canonical restore."""
    source = Path(snapshot).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError(f"restore snapshot failed integrity check: {source}")
    archive_dir = Path(archive_root or Path.home() / ".synlynk" / "backups").expanduser().resolve()
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    archive_path = archive_dir / f"restore-{slug}-{stamp}" / destination_path.name
    result = {
        "disposition": "plan-only",
        "snapshot": str(source),
        "destination": str(destination_path),
        "archive": str(archive_path),
        "sha256": _sha256(source),
    }
    if not apply:
        return result
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination_path.with_name(f".{destination_path.name}.restore.lock")
    with registry_lock(lock_path):
        temporary = _normalized_copy(source, destination_path.parent)
        try:
            if destination_path.exists():
                os.replace(destination_path, archive_path)
                for suffix in ("-wal", "-shm", "-journal"):
                    sidecar = Path(f"{destination_path}{suffix}")
                    if sidecar.exists():
                        os.replace(sidecar, archive_path.parent / sidecar.name)
            os.replace(temporary, destination_path)
            _fsync_dir(destination_path.parent)
            entry = ensure_registered_product(
                slug,
                destination_path,
                product_id or product_identity(slug),
                repo_path=Path(repo_path) if repo_path else None,
            )
            generation = int(entry.get("lineage_generation", 1)) + 1
            update_registered_product(
                slug,
                lineage_generation=generation,
                state="active",
                last_restore_snapshot=str(source),
            )
            result.update({"disposition": "restored", "lineage_generation": generation})
        finally:
            if temporary.exists():
                temporary.unlink()
    return result
