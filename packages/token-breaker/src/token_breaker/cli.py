"""CLI for token-breaker."""

import argparse
import json
import os
import subprocess
import sys
from token_breaker.models import BreakerBudget, CircuitBreakerError
from token_breaker.breaker import TokenCircuitBreaker


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .tbreak.json configuration."""
    cfg_path = ".tbreak.json"
    if os.path.exists(cfg_path) and not args.force:
        print(f"{cfg_path} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1
    sample_cfg = {
        "$schema": "https://synlynk.dev/schemas/tbreak.schema.json",
        "default_max_cost_usd": 5.0,
        "default_max_tokens": 1000000,
        "max_consecutive_errors": 5,
        "enforcement_mode": "strict"
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(sample_cfg, f, indent=2)
    print(f"Initialized {cfg_path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run command under supervised circuit breaker."""
    if not args.cmd:
        print("Error: Command arguments required.", file=sys.stderr)
        return 1

    budget = BreakerBudget(
        max_cost_usd=args.max_cost,
        max_tokens=args.max_tokens,
    )
    breaker = TokenCircuitBreaker(budget)

    try:
        proc = subprocess.Popen(args.cmd)
        rc = breaker.supervise_process(proc, timeout_seconds=args.timeout)
        return rc
    except CircuitBreakerError as e:
        print(f"CIRCUIT BREAKER TRIPPED: {e}", file=sys.stderr)
        return 124


def main() -> None:
    parser = argparse.ArgumentParser(prog="tbreak", description="In-Flight Token & Spend Circuit Breaker")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_p = subparsers.add_parser("init", help="Initialize local configuration")
    init_p.add_argument("--force", "-f", action="store_true", help="Overwrite existing configuration")
    init_p.set_defaults(func=cmd_init)

    run_p = subparsers.add_parser("run", help="Run command under circuit breaker")
    run_p.add_argument("--max-cost", type=float, default=None, help="Max cost in USD")
    run_p.add_argument("--max-tokens", type=int, default=None, help="Max tokens")
    run_p.add_argument("--timeout", type=int, default=None, help="Max execution seconds")
    run_p.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run")
    run_p.set_defaults(func=cmd_run)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
