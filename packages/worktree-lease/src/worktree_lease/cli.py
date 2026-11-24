"""CLI for worktree-lease."""

import argparse
import json
import os
import sys
from worktree_lease.manager import WorktreeLeaseManager


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .wtlease.json configuration."""
    cfg_path = ".wtlease.json"
    if os.path.exists(cfg_path) and not args.force:
        print(f"{cfg_path} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1
    sample_cfg = {
        "$schema": "https://synlynk.dev/schemas/wtlease.schema.json",
        "base_dir": ".worktrees",
        "default_ttl_seconds": 3600,
        "auto_prune_stale": True
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(sample_cfg, f, indent=2)
    print(f"Initialized {cfg_path}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List active worktree leases."""
    mgr = WorktreeLeaseManager(repo_root=args.repo_root or ".")
    leases = mgr.list_leases()
    if not leases:
        print("No active worktree leases.")
        return 0
    print(f"Active Leases ({len(leases)}):")
    for l in leases:
        print(f" - {os.path.basename(l.worktree_path)}: branch={l.branch} pid={l.pid} holder={l.lease_holder}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Prune stale leases."""
    mgr = WorktreeLeaseManager(repo_root=args.repo_root or ".")
    pruned = mgr.prune(dry_run=args.dry_run)
    mode = "(dry-run)" if args.dry_run else "(pruned)"
    print(f"{mode} Stale leases: {', '.join(pruned) if pruned else 'None'}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="wtlease", description="Atomic Git Worktree Concurrency & Lease Manager")
    parser.add_argument("--repo-root", type=str, default=".", help="Root of git repository")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_p = subparsers.add_parser("init", help="Initialize local configuration")
    init_p.add_argument("--force", "-f", action="store_true", help="Overwrite existing configuration")
    init_p.set_defaults(func=cmd_init)

    list_p = subparsers.add_parser("list", help="List active leases")
    list_p.set_defaults(func=cmd_list)

    prune_p = subparsers.add_parser("prune", help="Prune dead leases")
    prune_p.add_argument("--dry-run", action="store_true", help="Report without deleting")
    prune_p.set_defaults(func=cmd_prune)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
