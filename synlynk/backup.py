"""SQLite-consistent local disaster-recovery snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_source() -> Path:
    override = os.environ.get("SYNLYNK_STATE_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    from synlynk import get_state_db_path

    return Path(get_state_db_path()).expanduser().resolve()


def _default_output_dir(source: Path) -> Path:
    return source.parent.parent / "backups"


def _row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ):
        counts[name] = int(conn.execute(f' SELECT COUNT(*) FROM "{name}"').fetchone()[0])
    return counts


def create_snapshot(
    source: str | Path | None = None,
    output_dir: str | Path | None = None,
    label: str = "state",
) -> dict:
    """Create an integrity-checked SQLite online-backup snapshot."""
    source_path = Path(source).expanduser().resolve() if source else _default_source()
    if not source_path.is_file():
        raise FileNotFoundError(f"state database not found: {source_path}")
    destination_dir = (
        Path(output_dir).expanduser().resolve()
        if output_dir
        else _default_output_dir(source_path)
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{label}-{stamp}"
    snapshot = destination_dir / f"{base}.db"
    manifest_path = destination_dir / f"{base}.json"
    with tempfile.NamedTemporaryFile(
        prefix=f".{base}.", suffix=".tmp", dir=destination_dir, delete=False
    ) as temporary_file:
        temporary = Path(temporary_file.name)

    source_conn = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True, timeout=30.0)
    destination_conn = sqlite3.connect(str(temporary), timeout=30.0)
    try:
        source_conn.backup(destination_conn)
        destination_conn.commit()
        integrity = destination_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError(f"snapshot failed integrity_check: {integrity}")
        # A source in WAL mode can carry that mode into the backup header.
        # Finalize the standalone artifact without sidecars so it can be
        # copied, encrypted, or uploaded as one self-contained file.
        destination_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        destination_conn.execute("PRAGMA journal_mode=DELETE")
        destination_conn.commit()
        manifest = {
            "format": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": str(source_path),
            "snapshot": str(snapshot),
            "sha256": None,
            "size_bytes": None,
            "user_version": destination_conn.execute("PRAGMA user_version").fetchone()[0],
            "page_count": destination_conn.execute("PRAGMA page_count").fetchone()[0],
            "integrity_check": integrity,
            "row_counts": _row_counts(destination_conn),
        }
    finally:
        destination_conn.close()
        source_conn.close()
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{temporary}{suffix}")
        if sidecar.exists():
            sidecar.unlink()
    os.replace(temporary, snapshot)
    manifest["sha256"] = _sha256(snapshot)
    manifest["size_bytes"] = snapshot.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_snapshot(snapshot: str | Path) -> dict:
    """Verify a snapshot and return its manifest-style evidence."""
    path = Path(snapshot).expanduser().resolve()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        evidence = {
            "snapshot": str(path),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
            "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
            "page_count": conn.execute("PRAGMA page_count").fetchone()[0],
            "integrity_check": integrity,
            "row_counts": _row_counts(conn),
        }
    finally:
        conn.close()
    if integrity != "ok":
        raise sqlite3.DatabaseError(f"snapshot failed integrity_check: {integrity}")
    return evidence


def cmd_backup_create(source=None, output_dir=None, label="state") -> None:
    manifest = create_snapshot(source=source, output_dir=output_dir, label=label)
    print(f"  ✓ Snapshot created: {manifest['snapshot']}")
    print(f"  ✓ Manifest: {manifest['snapshot'][:-3]}.json")
    print(f"  ✓ SHA-256: {manifest['sha256']}")
    print(f"  ✓ Integrity: {manifest['integrity_check']}")


def cmd_backup_verify(snapshot: str) -> None:
    evidence = verify_snapshot(snapshot)
    print(f"  ✓ Snapshot verified: {evidence['snapshot']}")
    print(f"  ✓ SHA-256: {evidence['sha256']}")
    print(f"  ✓ Integrity: {evidence['integrity_check']}")
