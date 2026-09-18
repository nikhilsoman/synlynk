"""Product workspace runtime surfaces."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from synlynk.product_store import configured_identity_slug, github_apps_dir, repos_path
from synlynk.types_registry import load_types


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def add_repo(nwo: Optional[str] = None, repo_path: str = ".") -> dict:
    """Register a clone without creating an App or calling GitHub."""
    repo = Path(repo_path).resolve()
    slug = configured_identity_slug(repo)
    if not slug:
        raise RuntimeError(
            "workspace add-repo requires .synlynk/config.json with identity_slug; refusing to guess the product"
        )
    config_path = repo / ".synlynk" / "config.json"
    config = _read_json(config_path)
    nwo = (nwo or "").strip() or repo.name
    repo_id = config.get("repo_id") or nwo or repo.name
    config["repo_id"] = repo_id
    _write_json(config_path, config)

    types = load_types(slug)
    changed_apps = []
    apps = github_apps_dir(slug)
    if apps.is_dir():
        for app_path in sorted(apps.glob("*.json")):
            if not (types.get(app_path.stem) or {}).get("canonical"):
                continue
            app = _read_json(app_path)
            repos = app.get("repos") if isinstance(app.get("repos"), list) else []
            if nwo and nwo not in repos:
                repos.append(nwo)
                app["repos"] = repos
                _write_json(app_path, app)
                changed_apps.append(app_path.stem)

    ledger_path = repos_path(slug)
    ledger = _read_json(ledger_path)
    entries = ledger.get("repos") if isinstance(ledger.get("repos"), list) else []
    entry = {"repo_id": repo_id, "nwo": nwo}
    for index, existing in enumerate(entries):
        if isinstance(existing, dict) and (existing.get("repo_id") == repo_id or
                                           (nwo and existing.get("nwo") == nwo)):
            entries[index] = entry
            break
    else:
        entries.append(entry)
    _write_json(ledger_path, {"schema_version": 1, "repos": entries})
    return {"identity_slug": slug, "repo_id": repo_id, "nwo": entry["nwo"], "apps": changed_apps}


def cmd_workspace_add_repo(args) -> int:
    try:
        result = add_repo(getattr(args, "nwo", None))
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1
    print(f"  added {result['repo_id']} to product {result['identity_slug']}")
    if result["apps"]:
        print(f"  updated canonical Apps: {', '.join(result['apps'])}")
    print("  GitHub install repository selection is unchanged; add this repo in the GitHub install UI.")
    return 0
