"""Self-tests for live command surfaces."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from synlynk.dispatch import dispatch_agent, exec_command
from synlynk import cmd_status, init
from synlynk.db import cmd_goal_create, cmd_goal_link, cmd_goal_list, cmd_goal_status, cmd_story_create, cmd_story_list
from synlynk.instructions import cmd_instructions_status
from synlynk.jobs import cmd_jobs
from synlynk.scan import cmd_scan
from synlynk.team import cmd_decide, cmd_join
from synlynk.scheduler import cmd_schedule


@dataclass(frozen=True)
class ScenarioContext:
    name: str
    workspace: Path


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    status: str
    detail: str = ""


def _passed(name: str, detail: str = "") -> ScenarioResult:
    return ScenarioResult(name=name, status="passed", detail=detail)


def _failed(name: str, detail: str) -> ScenarioResult:
    return ScenarioResult(name=name, status="failed", detail=detail)


def _skipped(name: str, detail: str) -> ScenarioResult:
    return ScenarioResult(name=name, status="skipped", detail=detail)


@contextlib.contextmanager
def _workspace(name: str, root: Path):
    previous = os.getcwd()
    workspace = root / name
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / ".synlynk").mkdir(exist_ok=True)
    (workspace / ".agents").mkdir(exist_ok=True)
    config_path = workspace / ".synlynk" / "config.json"
    if not config_path.exists():
        config_path.write_text(
            json.dumps(
                {
                    "budget": {"limit_usd": 0},
                    "fenced_commands": [],
                    "roles": {},
                    "workgroup_agents": ["claude"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    try:
        os.chdir(workspace)
        yield ScenarioContext(name=name, workspace=workspace)
    finally:
        os.chdir(previous)


def _run(name: str, root: Path, func: Callable[[ScenarioContext], None]) -> ScenarioResult:
    try:
        with _workspace(name, root) as ctx:
            func(ctx)
        return _passed(name)
    except Exception as exc:  # pragma: no cover - exercised through scenario tests
        return _failed(name, f"{type(exc).__name__}: {exc}")


def _scenario_init(ctx: ScenarioContext) -> None:
    init(force=True, agents=["claude"], org="selftest", repo="selftest/repo", mode="solo")


def _scenario_scan(ctx: ScenarioContext) -> None:
    cmd_scan(dry_run=True, no_tui=True)


def _scenario_join(ctx: ScenarioContext) -> None:
    cmd_join()


def _scenario_goal_create(ctx: ScenarioContext) -> None:
    cmd_goal_create("selftest outcome", "selftest criterion")


def _scenario_goal_list(ctx: ScenarioContext) -> None:
    cmd_goal_list()


def _scenario_goal_link(ctx: ScenarioContext) -> None:
    goal_id = cmd_goal_create("selftest link outcome", "selftest link criterion")
    story_id = cmd_story_create("selftest linked story")
    cmd_goal_link(story_id, goal_id)


def _scenario_goal_status(ctx: ScenarioContext) -> None:
    cmd_goal_status()


def _scenario_story_create(ctx: ScenarioContext) -> None:
    cmd_story_create("selftest story")


def _scenario_story_list(ctx: ScenarioContext) -> None:
    cmd_story_list()


def _scenario_decide(ctx: ScenarioContext) -> None:
    cmd_decide("selftest decision", panel=["claude"], record=False)


def _scenario_jobs(ctx: ScenarioContext) -> None:
    cmd_jobs()


def _scenario_status(ctx: ScenarioContext) -> None:
    cmd_status()


def _scenario_instructions_status(ctx: ScenarioContext) -> None:
    cmd_instructions_status(pre_commit=False)


def _scenario_dispatch(ctx: ScenarioContext) -> None:
    dispatch_agent(
        "claude",
        "selftest dispatch smoke",
        story_id=None,
        skip_preflight=True,
        job_id="selftest-dispatch",
    )


def _scenario_exec(ctx: ScenarioContext) -> None:
    exec_command(["echo", "synlynk selftest"])


def _scenario_schedule(ctx: ScenarioContext) -> None:
    cmd_schedule(execute=False, max_stories=1)


def _scenario_release(ctx: ScenarioContext) -> ScenarioResult:
    return _skipped(
        ctx.name,
        "release performs irreversible real-world actions; not safe to selftest",
    )


SELFTEST_SCENARIOS: dict[str, Callable[[ScenarioContext], ScenarioResult]] = {
    "init": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_init),
    "scan": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_scan),
    "join": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_join),
    "goal create": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_goal_create),
    "goal list": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_goal_list),
    "goal link": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_goal_link),
    "goal status": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_goal_status),
    "story create": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_story_create),
    "story list": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_story_list),
    "decide": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_decide),
    "jobs": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_jobs),
    "status": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_status),
    "instructions status": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_instructions_status),
    "dispatch": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_dispatch),
    "exec": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_exec),
    "schedule": lambda ctx: _run(ctx.name, ctx.workspace, _scenario_schedule),
    "release": _scenario_release,
}


def run_selftest(
    scenarios: Mapping[str, Callable[[ScenarioContext], ScenarioResult]] | None = None,
) -> list[ScenarioResult]:
    active = scenarios or SELFTEST_SCENARIOS
    results: list[ScenarioResult] = []
    with tempfile.TemporaryDirectory(prefix="synlynk-selftest-") as tmp:
        root = Path(tmp)
        for name, scenario in active.items():
            try:
                ctx = ScenarioContext(name=name, workspace=root)
                result = scenario(ctx)
            except Exception as exc:  # pragma: no cover - guarded by tests
                result = _failed(name, f"{type(exc).__name__}: {exc}")
            results.append(result)
    return results


def cmd_selftest() -> int:
    results = run_selftest()
    failed = 0
    skipped = 0
    for result in results:
        detail = f" - {result.detail}" if result.detail else ""
        print(f"{result.name}: {result.status}{detail}")
        if result.status == "failed":
            failed += 1
        elif result.status == "skipped":
            skipped += 1
    total = len(results)
    passed = total - failed - skipped
    print(f"selftest: {passed} passed, {skipped} skipped, {failed} failed")
    return 1 if failed else 0
