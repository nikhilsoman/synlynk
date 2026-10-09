"""Read-only inventory of state DB artifacts."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import time
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


def _row_count(path: Path) -> int | None:
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "stories" not in tables:
                return None
            return conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None


def _identity_product_id(path: Path) -> str | None:
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "state_identity" not in tables:
                return None
            row = conn.execute("SELECT product_id FROM state_identity LIMIT 1").fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _recent_story_fingerprints(path: Path, limit: int = 20) -> set[str]:
    """Return a set of normalized (title, gh_issue) tokens for recent stories."""
    tokens: set[str] = set()
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "stories" not in tables:
                return tokens
            cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
            select_cols = ["title"]
            if "gh_issue" in cols:
                select_cols.append("gh_issue")
            order_col = "created_at" if "created_at" in cols else "id"
            query = f"SELECT {', '.join(select_cols)} FROM stories ORDER BY {order_col} DESC LIMIT ?"
            for row in conn.execute(query, (limit,)):
                for value in row:
                    if value:
                        tokens.add(str(value).strip().lower())
        finally:
            conn.close()
    except Exception:
        pass
    return tokens


def _match_project(shard_path: Path, workspaces_root: Path) -> dict:
    """Best-effort match of a legacy shard to a known canonical workspace DB."""
    if not workspaces_root.is_dir():
        return {"slug": None, "method": "none", "confidence": None}

    candidates = sorted(workspaces_root.glob("*/state.db"))

    shard_product_id = _identity_product_id(shard_path)
    if shard_product_id is not None:
        for candidate in candidates:
            if _identity_product_id(candidate) == shard_product_id:
                return {
                    "slug": candidate.parent.name,
                    "method": "fingerprint",
                    "confidence": "exact",
                }

    shard_tokens = _recent_story_fingerprints(shard_path)
    if shard_tokens:
        best_slug = None
        best_overlap = 0
        for candidate in candidates:
            candidate_tokens = _recent_story_fingerprints(candidate)
            overlap = len(shard_tokens & candidate_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_slug = candidate.parent.name
        if best_slug is not None and best_overlap >= 1:
            return {"slug": best_slug, "method": "heuristic", "confidence": "heuristic"}

    return {"slug": None, "method": "none", "confidence": None}


def _read_stories(path: Path) -> dict[str, dict]:
    """Read all stories from a DB keyed by story_id. Returns {} if no stories table."""
    result: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "stories" not in tables:
                return result
            cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
            if "story_id" not in cols:
                return result
            select_cols = ["story_id", "title"]
            if "gh_issue" in cols:
                select_cols.append("gh_issue")
            if "created_at" in cols:
                select_cols.append("created_at")
            for row in conn.execute(f"SELECT {', '.join(select_cols)} FROM stories"):
                record = dict(zip(select_cols, row))
                result[record["story_id"]] = record
        finally:
            conn.close()
    except Exception:
        pass
    return result


def _reconcile_plan(shard_path: Path, canonical_path: Path) -> dict:
    """Compute a union-merge plan for shard_path's stories into canonical_path's."""
    shard_stories = _read_stories(shard_path)
    canonical_stories = _read_stories(canonical_path)

    to_add = []
    already_present = []
    conflicts = []

    for story_id, shard_row in shard_stories.items():
        canonical_row = canonical_stories.get(story_id)
        if canonical_row is None:
            to_add.append(shard_row)
        elif canonical_row.get("title") == shard_row.get("title"):
            already_present.append(shard_row)
        else:
            conflicts.append(shard_row)

    return {"to_add": to_add, "already_present": already_present, "conflicts": conflicts}


def apply_reconcile(shard_path: Path, canonical_path: Path, *, ignore_conflicts: bool = True) -> dict:
    """Merge shard_path's stories into canonical_path, backing up canonical first.

    Conflicting story_ids (same id, different title) are never overwritten.
    With ignore_conflicts=True (the default for this function; the CLI
    defaults to requiring an explicit flag — see Task 6) they are counted
    and skipped. With ignore_conflicts=False, a ValueError is raised instead
    and nothing is written.
    """
    plan = _reconcile_plan(shard_path, canonical_path)
    if plan["conflicts"] and not ignore_conflicts:
        raise ValueError(
            f"{len(plan['conflicts'])} conflict(s) found; re-run with ignore_conflicts=True "
            "to skip them, or resolve manually first"
        )

    backup_path = canonical_path.parent / f"{canonical_path.name}.pre-reconcile-{int(time.time())}.bak"
    shutil.copy2(canonical_path, backup_path)

    conn = sqlite3.connect(canonical_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
        insert_cols = ["story_id", "title"]
        if "gh_issue" in cols:
            insert_cols.append("gh_issue")
        if "created_at" in cols:
            insert_cols.append("created_at")
        placeholders = ", ".join("?" for _ in insert_cols)
        with conn:
            for row in plan["to_add"]:
                values = [row.get(c) for c in insert_cols]
                conn.execute(
                    f"INSERT INTO stories ({', '.join(insert_cols)}) VALUES ({placeholders})",
                    values,
                )
    except Exception:
        conn.close()
        raise
    conn.close()

    return {
        "added": len(plan["to_add"]),
        "already_present": len(plan["already_present"]),
        "skipped_conflicts": len(plan["conflicts"]),
        "backup_path": str(backup_path),
    }


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
    workspaces_root = home / "workspaces"
    for path in sorted(p for p in paths if p.is_file()):
        mtime = path.stat().st_mtime
        mtime_dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        staleness_days = (datetime.datetime.now(tz=datetime.timezone.utc) - mtime_dt).days
        item = {
            "path": str(path),
            "class": _classify(path, repo),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "sidecars": {suffix: Path(f"{path}{suffix}").is_file() for suffix in ("-wal", "-shm", "-journal")},
            "row_count": _row_count(path),
            "mtime_iso": mtime_dt.isoformat(),
            "staleness_days": staleness_days,
        }
        item.update(_metadata(path))
        if item["class"] == "legacy-project":
            item["project_match"] = _match_project(path, workspaces_root)
        rows.append(item)
    return rows


def cmd_state_inventory(
    *,
    repo_root: str = ".",
    json_output: bool = False,
    all_artifacts: bool = False,
    reconcile_slug: str | None = None,
    apply: bool = False,
    ignore_conflicts: bool = False,
    cutoff_days: int | None = None,
) -> int:
    if reconcile_slug is not None:
        return _cmd_reconcile(
            repo_root,
            reconcile_slug,
            apply=apply,
            ignore_conflicts=ignore_conflicts,
            cutoff_days=cutoff_days,
        )

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


def _cmd_reconcile(
    repo_root: str,
    slug: str,
    *,
    apply: bool,
    ignore_conflicts: bool,
    cutoff_days: int | None = None,
) -> int:
    home = Path(os.path.expanduser("~/.synlynk"))
    canonical_path = home / "workspaces" / slug / "state.db"
    if not canonical_path.is_file():
        print(f"error: no canonical state.db found for slug {slug!r} at {canonical_path}")
        return 1

    rows = inventory(repo_root, all_artifacts=True)
    matched_shards = [
        r
        for r in rows
        if r["class"] == "legacy-project" and r.get("project_match", {}).get("slug") == slug
    ]
    if cutoff_days is not None:
        skipped = [r for r in matched_shards if r["staleness_days"] > cutoff_days]
        matched_shards = [r for r in matched_shards if r["staleness_days"] <= cutoff_days]
        for shard in skipped:
            print(
                f"skipping {shard['path']}: staleness {shard['staleness_days']}d "
                f"exceeds --cutoff-days {cutoff_days}"
            )
    if not matched_shards:
        print(f"no legacy shards matched to slug {slug!r}")
        return 0

    exit_code = 0
    for shard in matched_shards:
        shard_path = Path(shard["path"])
        plan = _reconcile_plan(shard_path, canonical_path)
        print(f"=== {shard_path} -> {canonical_path} ===")
        print(json.dumps(plan, indent=2, sort_keys=True, default=str))
        if apply:
            if plan["conflicts"] and not ignore_conflicts:
                print(
                    f"refusing to apply: {len(plan['conflicts'])} conflict(s). "
                    "Re-run with --ignore-conflicts to skip them."
                )
                exit_code = 1
                continue
            result = apply_reconcile(shard_path, canonical_path, ignore_conflicts=True)
            print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code
