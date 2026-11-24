"""Configuration manager and CLI for tokenprice."""

import argparse
import json
import os
import sys
from typing import Dict, Any

_CONFIG_PATH = os.path.expanduser("~/.config/tokenprice/config.json")


def load_config() -> Dict[str, Any]:
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(prog="tokenprice", description="Universal model pricing catalog & valuation engine")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize tokenprice configuration")

    # list
    list_parser = subparsers.add_parser("list", help="List all catalog models and rates")

    # calc
    calc_parser = subparsers.add_parser("calc", help="Calculate cost for given tokens")
    calc_parser.add_argument("--model", "-m", required=True, help="Model identifier")
    calc_parser.add_argument("--input", "-i", type=int, default=0, help="Input prompt tokens")
    calc_parser.add_argument("--output", "-o", type=int, default=0, help="Output completion tokens")
    calc_parser.add_argument("--cache-read", type=int, default=0, help="Cache read tokens")
    calc_parser.add_argument("--cache-write", type=int, default=0, help="Cache write tokens")
    calc_parser.add_argument("--mode", choices=["api", "subscription"], default="api", help="Billing mode")

    args = parser.parse_args()

    from tokenprice.catalog import list_models, get_model_rates, calculate_cost
    from tokenprice.models import BillingMode

    if args.subcommand == "init":
        save_config({"version": "0.1.0", "default_mode": "api", "custom_rates": {}})
        print(f"Initialized tokenprice config at {_CONFIG_PATH}")
    elif args.subcommand == "list":
        print(f"{'Model':<25} {'Input/M':<10} {'Output/M':<10} {'CacheRead/M':<12}")
        print("-" * 60)
        for m in list_models():
            r = get_model_rates(m)
            if r:
                print(f"{r.model_id:<25} ${r.input_per_m:<9.2f} ${r.output_per_m:<9.2f} ${r.cache_read_per_m:<11.4f}")
    elif args.subcommand == "calc":
        res = calculate_cost(
            model=args.model,
            input_tokens=args.input,
            output_tokens=args.output,
            cache_read_tokens=args.cache_read,
            cache_write_tokens=args.cache_write,
            billing_mode=BillingMode(args.mode),
        )
        print(f"Model: {res.model}")
        print(f"Nominal Cost:   ${res.nominal_usd:.6f}")
        print(f"Effective Cost: ${res.effective_usd:.6f} ({res.billing_mode.value})")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
