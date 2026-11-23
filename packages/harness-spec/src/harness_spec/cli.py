"""CLI for harness-spec."""

import argparse
import json
import os
import sys
from harness_spec.probe import probe_all_known, probe_binary


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .harness-spec.json configuration."""
    cfg_path = ".harness-spec.json"
    if os.path.exists(cfg_path) and not args.force:
        print(f"{cfg_path} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1
    sample_cfg = {
        "$schema": "https://synlynk.dev/schemas/harness-spec.schema.json",
        "custom_harnesses": {},
        "preferred_harness_order": ["claude", "agy", "codex", "grok"]
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(sample_cfg, f, indent=2)
    print(f"Initialized {cfg_path}")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    """Probe installed harnesses and print contract specifications."""
    if args.harness:
        contract = probe_binary(args.harness)
        print(f"Harness: {contract.display_name} ({contract.binary_name})")
        print(f"  Installed: {contract.installed}")
        print(f"  Version:   {contract.version or 'none'}")
        print(f"  Flag:      {contract.headless_prompt_flag}")
        return 0

    results = probe_all_known()
    print("Fleet Harness Probes:")
    for name, c in results.items():
        status = f"INSTALLED ({c.version})" if c.installed else "NOT FOUND"
        print(f" - {c.display_name:<20}: {status}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="harness-spec", description="Universal Agent CLI Discovery & Sandboxing Protocol")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_p = subparsers.add_parser("init", help="Initialize local configuration")
    init_p.add_argument("--force", "-f", action="store_true", help="Overwrite existing configuration")
    init_p.set_defaults(func=cmd_init)

    probe_p = subparsers.add_parser("probe", help="Probe agent CLI binaries")
    probe_p.add_argument("--harness", "-H", type=str, default=None, help="Probe single harness")
    probe_p.set_defaults(func=cmd_probe)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
