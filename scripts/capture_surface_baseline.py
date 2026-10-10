#!/usr/bin/env python3
"""Capture or report the CLI surface baseline for gh:#1973."""

import argparse
import json
import shlex
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from synlynk.baseline import load_telemetry, render_markdown, run_onboarding, summarize_telemetry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telemetry", default=".synlynk/telemetry.json")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--onboarding-repo", help="Run a clean-install simulation in this repo")
    parser.add_argument("--init-command", help="Shell command for init, when recording a run")
    parser.add_argument("--dispatch-command", help="Shell command for dispatch, when recording a run")
    args = parser.parse_args()

    summary = summarize_telemetry(load_telemetry(args.telemetry))
    runs = []
    if args.onboarding_repo:
        if not args.dispatch_command:
            parser.error("--dispatch-command is required with --onboarding-repo")
        runs.append(run_onboarding(
            args.onboarding_repo,
            init_command=shlex.split(args.init_command) if args.init_command else None,
            dispatch_command=shlex.split(args.dispatch_command),
        ))
    if args.json_output:
        print(json.dumps({"summary": summary, "onboarding_runs": runs}, indent=2))
    else:
        print(render_markdown(summary, runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
