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


def _canonicalize_identity(path: Path, *, product_id: str, canonical_path: Path) -> None:
    """Make a promoted copy identify its new canonical lineage."""
    with sqlite3.connect(str(path), timeout=30.0) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "state_identity" not in tables:
            identity_metadata(
                conn, product_id=product_id, mode="canonical", path=canonical_path
            )
        else:
            rows = conn.execute(
                "SELECT product_id, mode FROM state_identity"
            ).fetchall()
            if any(row[0] != product_id for row in rows):
                raise StateRegistryError(
                    "state DB product identity mismatch during canonical recovery"
                )
            if len(rows) > 1:
                raise StateRegistryError(
                    "state DB contains multiple identity rows; refusing recovery"
                )
            if rows:
                conn.execute(
                    "UPDATE state_identity SET product_id=?, mode='canonical', "
                    "canonical_path=?",
                    (product_id, str(canonical_path.expanduser().resolve())),
                )
            else:
                identity_metadata(
                    conn, product_id=product_id, mode="canonical", path=canonical_path
                )
        conn.commit()


def _recovery_copy(
    source: Path,
    destination_dir: Path,
    *,
    product_id: str,
    canonical_path: Path,
) -> Path:
    """Create a verified copy and rewrite its identity before publication."""
    temporary = _normalized_copy(source, destination_dir)
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "state_identity" in tables:
                rows = conn.execute(
                    "SELECT product_id, mode FROM state_identity"
                ).fetchall()
                if any(row[0] != product_id for row in rows):
                    raise StateRegistryError(
                        "source state DB belongs to a different product"
                    )
                if any(row[1] not in {"canonical", "backup", "restore"} for row in rows):
                    raise StateRegistryError(
                        "source state DB has a non-recoverable identity mode"
                    )
        _canonicalize_identity(
            temporary, product_id=product_id, canonical_path=canonical_path
        )
        return temporary
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def _logical_db_equal(left: Path, right: Path) -> bool:
    """Compare SQLite content while ignoring recovery-owned identity metadata."""
    def dump(path: Path) -> list[str]:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            return [line for line in conn.iterdump() if "state_identity" not in line]

    try:
        return dump(left) == dump(right)
    except sqlite3.Error:
        return False


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
    expected_product_id = product_id or product_identity(slug)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError(f"state DB failed integrity check: {source}")
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "state_identity" in tables:
            rows = conn.execute("SELECT product_id, mode FROM state_identity").fetchall()
            if any(row[0] != expected_product_id for row in rows):
                raise StateRegistryError("state DB belongs to a different product")
            if any(row[1] != "canonical" for row in rows):
                raise StateRegistryError("only canonical state DBs may be registered")
    entry = ensure_registered_product(
        slug,
        source,
        expected_product_id,
        repo_path=Path(repo_path) if repo_path else None,
    )
    _canonicalize_identity(source, product_id=entry["product_id"], canonical_path=source)
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
        expected_product_id = product_id or product_identity(slug)
        temporary = _recovery_copy(
            source_path,
            destination_path.parent,
            product_id=expected_product_id,
            canonical_path=destination_path,
        )
        try:
            digest = _sha256(temporary)
            if destination_path.exists():
                if _sha256(destination_path) != digest:
                    if _logical_db_equal(source_path, destination_path):
                        disposition = "already-complete"
                        temporary.unlink()
                    else:
                        raise StateRegistryError(
                            f"refusing to overwrite different canonical DB: {destination_path}"
                        )
                else:
                    disposition = "already-complete"
                    temporary.unlink()
            else:
                os.replace(temporary, destination_path)
                _fsync_dir(destination_path.parent)
                disposition = "promoted"
            entry = ensure_registered_product(
                slug,
                destination_path,
                expected_product_id,
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
        "disposition": "planned",
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
        expected_product_id = product_id or product_identity(slug)
        temporary = _recovery_copy(
            source,
            destination_path.parent,
            product_id=expected_product_id,
            canonical_path=destination_path,
        )
        try:
            if destination_path.exists():
                if archive_path.exists():
                    suffix = 1
                    while archive_path.with_name(
                        f"{archive_path.stem}-{suffix}{archive_path.suffix}"
                    ).exists():
                        suffix += 1
                    archive_path = archive_path.with_name(
                        f"{archive_path.stem}-{suffix}{archive_path.suffix}"
                    )
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
                expected_product_id,
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
