"""Product-scoped paths for workspace identity material (W1/W5)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


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


def product_root(slug: str) -> Path:
    return Path(os.path.expanduser("~")) / ".synlynk" / "workspaces" / _slugify(slug)


def github_apps_dir(slug: str) -> Path:
    return product_root(slug) / "github_apps"


def types_yaml_path(slug: str) -> Path:
    return product_root(slug) / "types.yaml"


def types_dir(slug: str) -> Path:
    return product_root(slug) / "types"


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
