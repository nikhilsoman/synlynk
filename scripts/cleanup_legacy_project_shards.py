# scripts/cleanup_legacy_project_shards.py
"""One-off remediation for gh:#1831: delete dead legacy per-project state.db
shards under ~/.synlynk/projects/*/state.db. These predate product_store.py's
slug-keyed canonical DB path and have had no active writes since 2026-09-15
(confirmed in gh:#1831). Not installed as a synlynk subcommand — single-use.

Usage:
    python3 scripts/cleanup_legacy_project_shards.py                 # dry run
    python3 scripts/cleanup_legacy_project_shards.py --execute        # delete
    python3 scripts/cleanup_legacy_project_shards.py --cutoff-date 2026-09-20
"""
import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DEFAULT_CUTOFF_DATE = date(2026, 9, 16)
DEFAULT_PROJECTS_ROOT = Path.home() / ".synlynk" / "projects"


@dataclass
class Shard:
    path: Path
    size_bytes: int
    mtime: datetime


def scan_shards(projects_root: Path) -> list[Shard]:
    shards = []
    for db_path in projects_root.glob("*/state.db"):
        stat = db_path.stat()
        shards.append(
            Shard(
                path=db_path,
                size_bytes=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime),
            )
        )
    return shards


def is_safe_to_delete(path: Path, cutoff: date) -> bool:
    mtime = datetime.fromtimestamp(path.stat().st_mtime).date()
    return mtime < cutoff
