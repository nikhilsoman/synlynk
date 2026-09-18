"""Read-only inventory of state DB artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _classify(path: Path, repo_root: Path) -> str:
    text = str(path)
    if "/quarantine/" in text:
        return "quarantine"
    if "/backups/" in text or path.suffix in {".bak", ".snapshot"}:
        return "backup"
    if "/projects/" in text:
        return "legacy-project"
    if path == repo_root / ".synlynk" / "state.db" or path == repo_root / "state.db":
        return "repo-local"
    if "/workspaces/" in text:
        return "product-workspace"
    return "unknown"


def _metadata(path: Path) -> dict:
    result = {}
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            quick = conn.execute("PRAGMA quick_check").fetchone()[0]
            result["integrity"] = quick
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "state_identity" in tables:
                row = conn.execute(
                    "SELECT product_id, mode, canonical_path, lineage_generation FROM state_identity LIMIT 1"
                ).fetchone()
                if row:
                    result["identity"] = {
                        "product_id": row[0],
                        "mode": row[1],
                        "canonical_path": row[2],
                        "lineage_generation": row[3],
                    }
        finally:
            conn.close()
    except Exception as exc:
        result["integrity"] = f"unreadable: {exc}"
    return result


def inventory(repo_root: str | Path = ".", *, all_artifacts: bool = False) -> list[dict]:
    repo = Path(repo_root).resolve()
    home = Path(os.path.expanduser("~/.synlynk"))
    # Keep the default command bounded to the current product.  The legacy
    # projects tree can contain thousands of historical ledgers; operators
    # opt into that potentially expensive sweep explicitly with --all.
    roots = [repo]
    if all_artifacts:
        roots.extend([home / "workspaces", home / "projects", home / "quarantine", home / "backups"])
    paths: set[Path] = set()
    for root in roots:
        if root.is_file() and root.name == "state.db":
            paths.add(root)
        elif root.is_dir():
            paths.update(root.rglob("state.db"))
    rows = []
    for path in sorted(p for p in paths if p.is_file()):
        item = {
            "path": str(path),
            "class": _classify(path, repo),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "sidecars": {suffix: Path(f"{path}{suffix}").is_file() for suffix in ("-wal", "-shm", "-journal")},
        }
        item.update(_metadata(path))
        rows.append(item)
    return rows


def cmd_state_inventory(*, repo_root: str = ".", json_output: bool = False, all_artifacts: bool = False) -> int:
    rows = inventory(repo_root, all_artifacts=all_artifacts)
    if json_output:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print("PATH\tCLASS\tSIZE\tSHA256\tINTEGRITY")
        for row in rows:
            print(
                f"{row['path']}\t{row['class']}\t{row['size_bytes']}\t"
                f"{row['sha256']}\t{row.get('integrity', 'unknown')}"
            )
    return 0
