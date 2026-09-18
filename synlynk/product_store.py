"""Product-scoped paths for workspace identity material (W1/W5)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import hashlib
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]

REGISTRY_FORMAT = 1


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"


def identity_slug_from_config(repo_path: PathLike = ".") -> str:
    repo = Path(repo_path).resolve()
    candidates = [repo / ".synlynk" / "config.json"]
    try:
        if not (repo / ".git").exists():
            raise OSError("not a git worktree")
        result = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo,
                                capture_output=True, text=True, check=False)
        if result.returncode == 0:
            common = Path(result.stdout.strip()).resolve()
            root = common.parent if common.name == ".git" else common.parent
            candidates.append(root / ".synlynk" / "config.json")
    except (OSError, ValueError):
        pass
    for cfg_path in candidates:
        try:
            data = json.loads(cfg_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        raw = data.get("identity_slug")
        if isinstance(raw, str) and raw.strip():
            return _slugify(raw.strip())
    return _slugify(repo.name)


def configured_identity_slug(repo_path: PathLike = ".") -> Optional[str]:
    """Return the explicitly configured product identity, or ``None``."""
    repo = Path(repo_path).resolve()
    try:
        data = json.loads((repo / ".synlynk" / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    raw = data.get("identity_slug")
    return _slugify(raw.strip()) if isinstance(raw, str) and raw.strip() else None


def product_root(slug: str) -> Path:
    return Path(os.path.expanduser("~")) / ".synlynk" / "workspaces" / _slugify(slug)


def product_registry_path() -> Path:
    """Return the single non-worktree-relative product registry path."""
    return Path(os.path.expanduser("~")) / ".synlynk" / "workspaces" / "registry.json"


def _read_product_registry() -> dict:
    path = product_registry_path()
    if not path.exists():
        return {"format": REGISTRY_FORMAT, "products": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"state DB product registry is unreadable: {path}") from exc
    if not isinstance(payload, dict) or payload.get("format") != REGISTRY_FORMAT:
        raise RuntimeError(f"state DB product registry has unsupported format: {path}")
    products = payload.get("products")
    if not isinstance(products, dict):
        raise RuntimeError(f"state DB product registry has invalid products map: {path}")
    return payload


def register_product(product_id: str, canonical_path: PathLike | None = None) -> Path:
    """Register one canonical product ledger idempotently and atomically."""
    product_id = _slugify(product_id)
    path = Path(canonical_path or state_db_path(product_id)).expanduser().resolve()
    registry_path = product_registry_path()
    payload = _read_product_registry()
    products = payload["products"]
    current = products.get(product_id)
    if current is not None:
        if not isinstance(current, dict) or current.get("mode") != "canonical":
            raise RuntimeError(f"product registry entry is not canonical: {product_id}")
        registered = Path(str(current.get("canonical_path", ""))).expanduser().resolve()
        if registered != path:
            raise RuntimeError(
                f"product registry path mismatch for {product_id}: {registered} != {path}"
            )
        return registered
    products[product_id] = {
        "product_id": product_id,
        "canonical_path": str(path),
        "mode": "canonical",
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".registry.", suffix=".tmp", dir=registry_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, registry_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def registered_product_path(product_id: str) -> Path:
    """Return the registered canonical path, failing closed on ambiguity."""
    product_id = _slugify(product_id)
    payload = _read_product_registry()
    entry = payload["products"].get(product_id)
    if not isinstance(entry, dict) or entry.get("mode") != "canonical":
        raise RuntimeError(f"no canonical state DB registered for product: {product_id}")
    registered = Path(str(entry.get("canonical_path", ""))).expanduser().resolve()
    expected = state_db_path(product_id).resolve()
    if registered != expected:
        raise RuntimeError(f"canonical state DB path mismatch for product: {product_id}")
    return registered


def ensure_product_registered(product_id: str) -> Path:
    """Bootstrap a missing registry entry, then resolve it fail-closed."""
    registry_path = product_registry_path()
    if not registry_path.exists():
        if state_db_path(product_id).exists():
            raise RuntimeError(
                f"state DB product registry is missing for existing ledger: {registry_path}"
            )
        return register_product(product_id)
    return registered_product_path(product_id)


def github_apps_dir(slug: str) -> Path:
    return product_root(slug) / "github_apps"


def repos_path(slug: str) -> Path:
    return product_root(slug) / "repos.json"


def types_yaml_path(slug: str) -> Path:
    return product_root(slug) / "types.yaml"


def types_dir(slug: str) -> Path:
    return product_root(slug) / "types"


def state_db_path(slug: str) -> Path:
    """Return the single product-scoped graph database path."""
    return product_root(slug) / "state.db"


def migrate_state_db_if_needed(repo_path: PathLike = ".") -> Path:
    """Copy a legacy graph into the product store without overwriting it.

    Use SQLite's online backup API instead of copying the main file directly.
    A raw copy can produce a structurally invalid destination when the source
    is in WAL mode and has committed pages in its sidecar files.
    """
    repo = Path(repo_path).resolve()
    slug = identity_slug_from_config(repo)
    destination = state_db_path(slug)
    if destination.exists():
        return destination

    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=repo,
            capture_output=True, text=True, check=False,
        )
        root = Path(common.stdout.strip()).resolve().parent if common.returncode == 0 else repo
    except (OSError, ValueError):
        root = repo
    old_key = hashlib.md5(str(root).encode()).hexdigest()[:8]
    candidates = [
        Path(os.path.expanduser("~")) / ".synlynk" / "projects" / old_key / "state.db",
        repo / ".synlynk" / "state.db",
    ]
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent,
            ) as temp_file:
                temporary = Path(temp_file.name)
            source_conn = sqlite3.connect(
                f"file:{source.resolve()}?mode=ro", uri=True,
            )
            destination_conn = sqlite3.connect(str(temporary))
            try:
                source_conn.backup(destination_conn)
                destination_conn.commit()
                integrity = destination_conn.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise sqlite3.DatabaseError(
                        f"legacy state database failed integrity_check: {integrity}"
                    )
            finally:
                destination_conn.close()
                source_conn.close()
            os.replace(temporary, destination)
            temporary = None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
    return destination


def ensure_product_dirs(slug: str) -> Path:
    root = product_root(slug)
    github_apps_dir(slug).mkdir(parents=True, exist_ok=True)
    types_dir(slug).mkdir(parents=True, exist_ok=True)
    return root


def resolve_github_apps_dir(repo_path: PathLike = ".") -> Path:
    """Prefer populated product App material, with a legacy repo read fallback."""
    slug = identity_slug_from_config(repo_path)
    product_apps = github_apps_dir(slug)
    if any(product_apps.glob("*.json")) or any(product_apps.glob("*.pem")):
        return product_apps
    repo = Path(repo_path).resolve()
    repo_candidates = [repo / ".synlynk" / "github_apps"]
    try:
        if (repo / ".git").exists():
            result = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"], cwd=repo,
                capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                common = Path(result.stdout.strip()).resolve()
                main_repo = common.parent if common.name == ".git" else common.parent
                main_apps = main_repo / ".synlynk" / "github_apps"
                if main_apps not in repo_candidates:
                    repo_candidates.append(main_apps)
    except (OSError, ValueError):
        pass
    for repo_apps in repo_candidates:
        if repo_apps.is_dir() and any(repo_apps.iterdir()):
            return repo_apps
    for repo_apps in repo_candidates:
        if repo_apps.is_dir():
            return repo_apps
    return product_apps


def write_apps_dir_for_init(repo_path: PathLike = ".") -> Path:
    slug = identity_slug_from_config(repo_path)
    ensure_product_dirs(slug)
    return github_apps_dir(slug)


def migrate_repo_apps_if_needed(repo_path: PathLike = ".") -> Path:
    """Copy legacy App json/PEM files once, never overwriting product material."""
    repo = Path(repo_path).resolve()
    source = repo / ".synlynk" / "github_apps"
    # Repositories predating identity_slug keep their legacy behavior until
    # the operator opts into product identity via config.json.
    if not (repo / ".synlynk" / "config.json").is_file():
        return source
    dest = write_apps_dir_for_init(repo_path)
    if source.is_dir() and source != dest:
        for path in source.iterdir():
            if path.suffix not in {".json", ".pem"}:
                continue
            target = dest / path.name
            if not target.exists():
                shutil.copy2(path, target)
                try:
                    os.chmod(target, 0o600)
                except OSError:
                    pass
    return dest
