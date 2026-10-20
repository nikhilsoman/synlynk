"""One-off remediation for gh:#1831 legacy project state shards.

The command is dry-run by default.  Only shards whose modification date is
strictly before the cutoff may be deleted with ``--execute``.
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
    return [
        Shard(path=path, size_bytes=path.stat().st_size, mtime=datetime.fromtimestamp(path.stat().st_mtime))
        for path in projects_root.glob("*/state.db")
    ]


def is_safe_to_delete(path: Path, cutoff: date) -> bool:
    return datetime.fromtimestamp(path.stat().st_mtime).date() < cutoff


@dataclass
class CleanupResult:
    deletable_count: int
    deletable_bytes: int
    skipped_count: int
    deleted_count: int
    deleted_bytes: int


def run_cleanup(projects_root: Path, cutoff: date, execute: bool, report_path: Path) -> CleanupResult:
    shards = scan_shards(projects_root)
    deletable = [shard for shard in shards if is_safe_to_delete(shard.path, cutoff)]
    skipped = [shard for shard in shards if not is_safe_to_delete(shard.path, cutoff)]
    deleted_count = deleted_bytes = 0
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
        f"Deletable ({'deleted' if execute else 'would delete'}): {len(deletable)} shard(s), "
        f"{sum(shard.size_bytes for shard in deletable)} bytes",
    ]
    lines.extend(f"  {shard.path} (mtime={shard.mtime.isoformat()}, {shard.size_bytes} bytes)" for shard in deletable)
    lines.append("")
    lines.append(f"Skipped (newer than cutoff, never deleted by this script): {len(skipped)} shard(s)")
    lines.extend(f"  {shard.path} (mtime={shard.mtime.isoformat()}, {shard.size_bytes} bytes)" for shard in skipped)
    report_path.write_text("\n".join(lines) + "\n")
    return CleanupResult(
        deletable_count=len(deletable),
        deletable_bytes=sum(shard.size_bytes for shard in deletable),
        skipped_count=len(skipped),
        deleted_count=deleted_count,
        deleted_bytes=deleted_bytes,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually delete safe shards; default is dry-run.")
    parser.add_argument(
        "--cutoff-date",
        type=lambda value: datetime.strptime(value, "%Y-%m-%d").date(),
        default=DEFAULT_CUTOFF_DATE,
        help="Never delete shards modified on or after this date.",
    )
    parser.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS_ROOT)
    parser.add_argument("--report-path", type=Path, default=Path("legacy_shard_cleanup_report.txt"))
    args = parser.parse_args(argv)
    args.projects_root = args.projects_root.expanduser()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run_cleanup(args.projects_root, args.cutoff_date, args.execute, args.report_path)
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
