"""Standalone CLI for tokentrail."""

import argparse
import json
import os
import sys
from tokentrail.extractor import extract_ledger


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .tokentrail.json configuration."""
    cfg_path = ".tokentrail.json"
    if os.path.exists(cfg_path) and not args.force:
        print(f"{cfg_path} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1
    sample_cfg = {
        "$schema": "https://synlynk.dev/schemas/tokentrail.schema.json",
        "harnesses": ["claude", "agy", "codex"],
        "watch_paths": [
            "~/.claude/projects",
            ".system_generated/logs",
            "~/.codex/sessions"
        ],
        "collapse_streaming_chunks": True,
        "default_currency": "USD"
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(sample_cfg, f, indent=2)
    print(f"Initialized {cfg_path}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    """Extract and print token summary for a transcript file."""
    if not args.file:
        print("Error: --file argument is required for summary.", file=sys.stderr)
        return 1
    try:
        ledger = extract_ledger(args.file, harness=args.harness)
        total = ledger.total_usage
        print(f"Session: {ledger.session_id} (Harness: {ledger.harness})")
        print(f"Turns: {len(ledger.turns)}")
        print(f"  Input Tokens:       {total.input_tokens:,}")
        print(f"  Output Tokens:      {total.output_tokens:,}")
        print(f"  Cache Write Tokens: {total.cache_write_tokens:,}")
        print(f"  Cache Read Tokens:  {total.cache_read_tokens:,}")
        print(f"  Total Tokens:       {total.total_tokens:,}")
        return 0
    except Exception as e:
        print(f"Error extracting summary: {e}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="tokentrail", description="Universal Session & Gateway Transcript Extractor")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_p = subparsers.add_parser("init", help="Initialize local configuration")
    init_p.add_argument("--force", "-f", action="store_true", help="Overwrite existing configuration")
    init_p.set_defaults(func=cmd_init)

    sum_p = subparsers.add_parser("summary", help="Print session token summary")
    sum_p.add_argument("--file", "-F", type=str, required=True, help="Path to transcript file")
    sum_p.add_argument("--harness", "-H", type=str, default=None, help="Force specific harness parser")
    sum_p.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
