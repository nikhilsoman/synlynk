"""Product-scoped paths for workspace identity material (W1/W5)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import hashlib
import sqlite3
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"


def identity_slug_from_config(repo_path: PathLike = ".") -> str:
    repo = Path(repo_path).resolve()
    candidates = [repo / ".synlynk" / "config.json"]
    root_repo = repo
    try:
        if (repo / ".git").exists() or (repo.parent / ".git").exists():
            result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                raw_common = result.stdout.strip()
                if raw_common:
                    common = Path(raw_common)
                    if not common.is_absolute():
                        common = (repo / common).resolve()
                    else:
                        common = common.resolve()
                    root = common.parent if common.name == ".git" else common.parent
                    root_repo = root
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
    return _slugify(root_repo.name)


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


def github_apps_dir(slug: str) -> Path:
    return product_root(slug) / "github_apps"


def repos_path(slug: str) -> Path:
    return product_root(slug) / "repos.json"


def types_yaml_path(slug: str) -> Path:
    return product_root(slug) / "types.yaml"


def types_dir(slug: str) -> Path:
    return product_root(slug) / "types"


def connectors_dir(slug: str) -> Path:
    """Return the product-scoped connector credential directory."""
    return product_root(slug) / "connectors"


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
        common_run = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo,
            capture_output=True, text=True, check=False,
        )
        if common_run.returncode == 0 and common_run.stdout.strip():
            raw_c = Path(common_run.stdout.strip())
            c = (repo / raw_c).resolve() if not raw_c.is_absolute() else raw_c.resolve()
            root = c.parent if c.name == ".git" else c.parent
        else:
            root = repo
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
    lock_path = destination.with_name(f".{destination.name}.migration.lock")
    with lock_path.open("a+") as lock_handle:
        try:
            import fcntl
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError) as exc:
            raise RuntimeError(f"cannot lock state migration {lock_path}: {exc}") from exc
        try:
            if destination.exists():
                return destination
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
                    destination_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    destination_conn.execute("PRAGMA journal_mode=DELETE")
                    destination_conn.commit()
                finally:
                    destination_conn.close()
                    source_conn.close()
                with temporary.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(temporary, destination)
                temporary = None
                try:
                    dir_fd = os.open(str(destination.parent), os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    pass
            finally:
                if temporary is not None:
                    try:
                        temporary.unlink()
                    except FileNotFoundError:
                        pass
        finally:
            try:
                import fcntl
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
    return destination


def ensure_product_dirs(slug: str) -> Path:
    root = product_root(slug)
    github_apps_dir(slug).mkdir(parents=True, exist_ok=True)
    types_dir(slug).mkdir(parents=True, exist_ok=True)
    connectors_dir(slug).mkdir(parents=True, exist_ok=True)
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
        if (repo / ".git").exists() or (repo.parent / ".git").exists():
            result = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo,
                capture_output=True, text=True, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                raw_common = Path(result.stdout.strip())
                common = (repo / raw_common).resolve() if not raw_common.is_absolute() else raw_common.resolve()
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
