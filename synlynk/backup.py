"""SQLite-consistent local disaster-recovery snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
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


def _require_gpg() -> str:
    executable = shutil.which("gpg")
    if not executable:
        raise RuntimeError("encrypted DR export requires gpg")
    return executable


def encrypt_snapshot(
    snapshot: str | Path,
    recipient: str,
    output_dir: str | Path | None = None,
) -> dict:
    """Encrypt a verified snapshot for provider-neutral off-machine retention."""
    if not recipient or not recipient.strip():
        raise ValueError("a GPG recipient is required for encrypted DR export")
    source = Path(snapshot).expanduser().resolve()
    source_evidence = verify_snapshot(source)
    destination_dir = (
        Path(output_dir).expanduser().resolve() if output_dir else source.parent
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    encrypted = destination_dir / f"{source.name}.gpg"
    manifest_path = encrypted.with_suffix(".json")
    gpg = _require_gpg()
    temporary = destination_dir / f".{encrypted.name}.tmp"
    try:
        subprocess.run(
            [gpg, "--batch", "--yes", "--trust-model", "always", "--output",
             str(temporary), "--encrypt", "--recipient", recipient, str(source)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("gpg produced no encrypted DR artifact")
        os.replace(temporary, encrypted)
        manifest = {
            "format": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_snapshot": str(source),
            "source_sha256": source_evidence["sha256"],
            "encrypted_snapshot": str(encrypted),
            "encrypted_sha256": _sha256(encrypted),
            "recipient": recipient,
            "integrity_check": "verified-before-encryption",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    finally:
        if temporary.exists():
            temporary.unlink()


def verify_encrypted_snapshot(encrypted: str | Path) -> dict:
    """Decrypt an encrypted artifact into a temporary file and verify SQLite."""
    path = Path(encrypted).expanduser().resolve()
    manifest_path = path.with_suffix(".json")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"encrypted DR manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("encrypted_sha256") != _sha256(path):
        raise sqlite3.DatabaseError("encrypted DR artifact checksum mismatch")
    gpg = _require_gpg()
    with tempfile.TemporaryDirectory(prefix="synlynk-dr-verify-") as temporary_dir:
        plaintext = Path(temporary_dir) / "snapshot.db"
        subprocess.run(
            [gpg, "--batch", "--yes", "--output", str(plaintext), "--decrypt", str(path)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        evidence = verify_snapshot(plaintext)
    if evidence["sha256"] != manifest.get("source_sha256"):
        raise sqlite3.DatabaseError("decrypted DR snapshot checksum mismatch")
    return {
        "encrypted_snapshot": str(path),
        "encrypted_sha256": manifest["encrypted_sha256"],
        "source_sha256": evidence["sha256"],
        "integrity_check": evidence["integrity_check"],
        "row_counts": evidence["row_counts"],
    }


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


def cmd_backup_encrypt(snapshot: str, recipient: str, output_dir=None) -> None:
    manifest = encrypt_snapshot(snapshot, recipient, output_dir=output_dir)
    print(f"  ✓ Encrypted snapshot: {manifest['encrypted_snapshot']}")
    print(f"  ✓ Manifest: {manifest['encrypted_snapshot'][:-4]}.json")
    print(f"  ✓ SHA-256: {manifest['encrypted_sha256']}")


def cmd_backup_verify_encrypted(snapshot: str) -> None:
    evidence = verify_encrypted_snapshot(snapshot)
    print(f"  ✓ Encrypted snapshot verified: {evidence['encrypted_snapshot']}")
    print(f"  ✓ Decrypted SHA-256: {evidence['source_sha256']}")
    print(f"  ✓ Integrity: {evidence['integrity_check']}")
