"""Canonical product state registry and identity helpers.

The registry is deliberately separate from SQLite so a database copy cannot
declare itself canonical merely by carrying copied metadata.  Canonical status
requires both the DB identity and the registry-selected real path.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Iterator, Optional


REGISTRY_VERSION = 1
_PRODUCT_NAMESPACE = uuid.UUID("7e4d3f42-7a57-4d16-a8a0-2f4a0f8757c4")


class StateRegistryError(RuntimeError):
    """Raised when canonical product identity cannot be established safely."""


def registry_path() -> Path:
    override = os.environ.get("SYNLYNK_REGISTRY_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return Path(os.path.expanduser("~/.synlynk/registry.json"))


def _lock_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.lock")


@contextlib.contextmanager
def registry_lock(path: Optional[Path] = None) -> Iterator[None]:
    """Serialize registry reads/writes across processes."""
    target = path or registry_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = _lock_path(target).open("a+")
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError) as exc:
            raise StateRegistryError(f"cannot lock state registry {target}: {exc}") from exc
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        handle.close()


def _read_unlocked(path: Path) -> dict:
    if not path.exists():
        return {"version": REGISTRY_VERSION, "products": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateRegistryError(f"state registry is unreadable: {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != REGISTRY_VERSION:
        raise StateRegistryError(f"state registry has unsupported format: {path}")
    products = payload.get("products")
    if not isinstance(products, dict):
        raise StateRegistryError(f"state registry products map is invalid: {path}")
    return payload


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_unlocked(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        _fsync_directory(path.parent)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _legacy_product_id(slug: str) -> str:
    """Stable bootstrap ID for pre-registry installs; persisted on first write."""
    return str(uuid.uuid5(_PRODUCT_NAMESPACE, f"legacy:{slug}"))


def product_identity(slug: str, repo_path: str = ".") -> str:
    """Return configured or registered product identity without mutating state."""
    try:
        config = json.loads((Path(repo_path) / ".synlynk" / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        config = {}
    configured = config.get("product_id")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    path = registry_path()
    with registry_lock(path):
        payload = _read_unlocked(path)
        entry = payload["products"].get(slug)
        if isinstance(entry, dict) and entry.get("product_id"):
            return str(entry["product_id"])
    return _legacy_product_id(slug)


def canonical_path(
    slug: str,
    fallback: Path,
    *,
    allow_unregistered_existing: bool = False,
) -> Path:
    """Resolve the registry path, rejecting an unexpected canonical move."""
    path = registry_path()
    try:
        os.stat(path)
    except FileNotFoundError:
        # Pre-registry installs bootstrap only after a successful canonical
        # open. This is a one-time compatibility state, not a runtime choice
        # between multiple existing ledgers.
        return fallback
    except OSError as exc:
        raise StateRegistryError(f"state registry cannot be inspected: {path}: {exc}") from exc
    # Once a registry exists, every product lookup is authoritative. Any
    # unreadable, corrupt, missing, or ambiguous entry fails closed.
    payload = _read_unlocked(path)
    entry = payload["products"].get(slug)
    if not isinstance(entry, dict) or not entry.get("canonical_path"):
        # A shared registry may already contain other products.  A brand-new
        # product has no DB to copy or masquerade as, so it may bootstrap at
        # its deterministic product path.  Existing unregistered files remain
        # fail-closed and must be explicitly inventoried/reconciled.
        if allow_unregistered_existing and fallback.expanduser().resolve().exists():
            return fallback.expanduser().resolve()
        if not fallback.expanduser().resolve().exists():
            return fallback
        raise StateRegistryError(f"no canonical registry entry for product {slug!r}")
    registered = Path(str(entry["canonical_path"])).expanduser().resolve()
    return registered


def registered_canonical_path(slug: str) -> Optional[Path]:
    """Return a registered path, or None when a product has not bootstrapped."""
    path = registry_path()
    try:
        os.stat(path)
    except FileNotFoundError:
        return None
    with registry_lock(path):
        payload = _read_unlocked(path)
        entry = payload["products"].get(slug)
        if not isinstance(entry, dict) or not entry.get("canonical_path"):
            return None
        return Path(str(entry["canonical_path"])).expanduser().resolve()


def ensure_registered_product(slug: str, path: Path, product_id: Optional[str] = None) -> dict:
    """Idempotently register a canonical product path and return its entry."""
    registry = registry_path()
    path = path.expanduser().resolve()
    with registry_lock(registry):
        payload = _read_unlocked(registry)
        products = payload["products"]
        entry = products.get(slug)
        if entry is not None:
            if not isinstance(entry, dict):
                raise StateRegistryError(f"registry entry for {slug!r} is invalid")
            registered_path = Path(str(entry.get("canonical_path", ""))).expanduser().resolve()
            if registered_path != path:
                raise StateRegistryError(
                    f"canonical path mismatch for {slug!r}: registry={registered_path} requested={path}"
                )
            return entry
        entry = {
            "product_id": product_id or _legacy_product_id(slug),
            "slug": slug,
            "canonical_path": str(path),
            "mode": "canonical",
            "lineage_generation": 1,
            "state": "active",
        }
        products[slug] = entry
        _write_unlocked(registry, payload)
        return entry


def update_registered_product(slug: str, **updates: object) -> dict:
    """Atomically update an existing product registry entry."""
    registry = registry_path()
    with registry_lock(registry):
        payload = _read_unlocked(registry)
        entry = payload["products"].get(slug)
        if not isinstance(entry, dict):
            raise StateRegistryError(f"no registered product for {slug!r}")
        entry.update(updates)
        payload["products"][slug] = entry
        _write_unlocked(registry, payload)
        return entry


def identity_metadata(conn, *, product_id: str, mode: str, path: Path) -> None:
    """Bootstrap/read identity metadata on an already-open writable ledger."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS state_identity (
            product_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            canonical_path TEXT NOT NULL,
            lineage_generation INTEGER NOT NULL DEFAULT 1,
            source_sha256 TEXT,
            bootstrapped_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    row = conn.execute(
        "SELECT product_id, mode, canonical_path FROM state_identity LIMIT 1"
    ).fetchone()
    real_path = str(path.expanduser().resolve())
    if row and (row[0] != product_id or row[1] != mode or row[2] != real_path):
        raise StateRegistryError(
            "state DB identity mismatch: "
            f"found product={row[0]!r} mode={row[1]!r} path={row[2]!r}, "
            f"expected product={product_id!r} mode={mode!r} path={real_path!r}"
        )
    if not row:
        digest = None
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        conn.execute(
            "INSERT INTO state_identity(product_id, mode, canonical_path, source_sha256) VALUES (?, ?, ?, ?)",
            (product_id, mode, real_path, digest),
        )
