"""Taxonomy-driven command selftest helpers."""

from __future__ import annotations

import argparse
import contextlib
import io
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from synlynk.cli import build_parser
from synlynk.taxonomy import COMMAND_TAXONOMY


@dataclass
class ScenarioContext:
    repo_path: str
    live: bool
    budget_cap_usd: float = 2.0
    spent_usd: float = 0.0
    state: dict = field(default_factory=dict)

    def remaining_budget(self) -> float:
        return max(0.0, self.budget_cap_usd - self.spent_usd)


@dataclass
class ScenarioResult:
    command: str
    status: str
    detail: str
    cost_usd: float = 0.0


def _selftest_sort_key(entry: dict) -> tuple[int, int]:
    tier = entry["maturity_tier"]
    tier_rank = 99 if tier == "latent" else int(tier)
    return tier_rank, _TAXONOMY_INDEX[entry["command"]]


def _generic_help_scenario(entry: dict, parser: argparse.ArgumentParser) -> ScenarioResult:
    argv = entry["command"].split() + ["--help"]
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            parser.parse_args(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 0
            if code == 0:
                return ScenarioResult(
                    command=entry["command"],
                    status="pass",
                    detail="generic --help fallback accepted",
                )
            return ScenarioResult(
                command=entry["command"],
                status="fail",
                detail=f"generic --help fallback exited {code}",
            )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="generic --help fallback accepted",
    )


SELFTEST_SCENARIOS: Dict[str, Callable[[dict, ScenarioContext], ScenarioResult]] = {}

_TAXONOMY_INDEX = {entry["command"]: idx for idx, entry in enumerate(COMMAND_TAXONOMY)}


def run_selftest(live: bool = False) -> List[ScenarioResult]:
    """Run the selftest scenarios for every taxonomy command."""
    parser = build_parser()
    ctx = ScenarioContext(repo_path=".", live=live)
    results: List[ScenarioResult] = []
    for entry in sorted(COMMAND_TAXONOMY, key=_selftest_sort_key):
        scenario = SELFTEST_SCENARIOS.get(entry["command"]) if live else None
        if scenario is None:
            result = _generic_help_scenario(entry, parser)
        else:
            result = scenario(entry, ctx)
        ctx.spent_usd += result.cost_usd
        results.append(result)
    return results


def cmd_selftest(live: bool = False) -> int:
    """CLI entry point for the command selftest."""
    results = run_selftest(live=live)
    passes = sum(1 for result in results if result.status == "pass")
    failures = sum(1 for result in results if result.status == "fail")
    skipped = sum(1 for result in results if result.status == "skipped")

    for result in results:
        print(f"{result.status.upper():7s} {result.command:20s} {result.detail}")
    print(f"summary: {passes} passed, {failures} failed, {skipped} skipped")
    return 1 if failures else 0
