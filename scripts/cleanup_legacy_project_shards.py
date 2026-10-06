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


@dataclass
class CleanupResult:
    deletable_count: int
    deletable_bytes: int
    skipped_count: int
    deleted_count: int
    deleted_bytes: int


def run_cleanup(
    projects_root: Path,
    cutoff: date,
    execute: bool,
    report_path: Path,
) -> CleanupResult:
    shards = scan_shards(projects_root)
    deletable = [s for s in shards if is_safe_to_delete(s.path, cutoff)]
    skipped = [s for s in shards if not is_safe_to_delete(s.path, cutoff)]

    deleted_count = 0
    deleted_bytes = 0
    if execute:
        for shard in deletable:
            shard.path.unlink()
            deleted_count += 1
            deleted_bytes += shard.size_bytes

    lines = [
        f"Legacy shard cleanup report ({'EXECUTED' if execute else 'DRY RUN'})",
        f"Cutoff date: {cutoff.isoformat()}",
        f"Scanned: {len(shards)} shard(s)",
        "",
        f"Deletable ({'deleted' if execute else 'would delete'}): "
        f"{len(deletable)} shard(s), {sum(s.size_bytes for s in deletable)} bytes",
    ]
    for shard in deletable:
        lines.append(f"  {shard.path} (mtime={shard.mtime.isoformat()}, {shard.size_bytes} bytes)")
    lines.append("")
    lines.append(f"Skipped (newer than cutoff, never deleted by this script): {len(skipped)} shard(s)")
    for shard in skipped:
        lines.append(f"  {shard.path} (mtime={shard.mtime.isoformat()}, {shard.size_bytes} bytes)")

    report_path.write_text("\n".join(lines) + "\n")

    return CleanupResult(
        deletable_count=len(deletable),
        deletable_bytes=sum(s.size_bytes for s in deletable),
        skipped_count=len(skipped),
        deleted_count=deleted_count,
        deleted_bytes=deleted_bytes,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually delete shards that pass the safety check. Default is dry-run.",
    )
    parser.add_argument(
        "--cutoff-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=DEFAULT_CUTOFF_DATE,
        help="Shards with mtime at or after this date are never deleted. Default: 2026-09-16.",
    )
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=DEFAULT_PROJECTS_ROOT,
        help="Root directory to scan for */state.db shards.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("legacy_shard_cleanup_report.txt"),
        help="Where to write the summary report.",
    )
    args = parser.parse_args(argv)
    args.projects_root = args.projects_root.expanduser()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run_cleanup(
        projects_root=args.projects_root,
        cutoff=args.cutoff_date,
        execute=args.execute,
        report_path=args.report_path,
    )
    mode = "EXECUTED" if args.execute else "DRY RUN"
    print(f"[{mode}] scanned shards under {args.projects_root}")
    print(f"  deletable: {result.deletable_count} shard(s), {result.deletable_bytes} bytes")
    print(f"  skipped (newer than cutoff): {result.skipped_count} shard(s)")
    if args.execute:
        print(f"  deleted: {result.deleted_count} shard(s), {result.deleted_bytes} bytes")
    print(f"  full report: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
