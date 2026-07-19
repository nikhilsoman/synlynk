"""Taxonomy-driven command selftest helpers."""

from __future__ import annotations

import argparse
import builtins
import contextlib
import io
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List
from unittest.mock import patch

from synlynk.dispatch import dispatch_agent, exec_command
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


@contextlib.contextmanager
def _chdir(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _workspace_dir(ctx: ScenarioContext) -> Path:
    path = ctx.state.get("workspace_dir")
    if path is None:
        path = Path(tempfile.mkdtemp(prefix="synlynk-selftest-"))
        ctx.state["workspace_dir"] = path
    return Path(path)


def _ensure_workspace_scaffold(ctx: ScenarioContext) -> Path:
    workspace = _workspace_dir(ctx)
    docs_dir = workspace / "project-docs"
    synlynk_dir = workspace / ".synlynk"
    docs_dir.mkdir(parents=True, exist_ok=True)
    synlynk_dir.mkdir(parents=True, exist_ok=True)
    config_path = synlynk_dir / "config.json"
    if not config_path.exists():
        config_path.write_text(
            json.dumps(
                {
                    "project_docs_dir": "project-docs",
                    "dispatch_mode": "daily-grind",
                    "roles": {},
                },
                indent=2,
            )
        )
    return workspace


def _capture_call(command: str, action: Callable[[], object]) -> tuple[ScenarioResult, str, object | None]:
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
            value = action()
    except Exception as exc:  # pragma: no cover - exercised by failure paths
        return (
            ScenarioResult(command=command, status="fail", detail=f"{type(exc).__name__}: {exc}"),
            stdout.getvalue(),
            None,
        )
    return (
        ScenarioResult(command=command, status="pass", detail="live scenario executed"),
        stdout.getvalue(),
        value,
    )


def _scenario_init(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    config_payload = {
        "project_docs_dir": "project-docs",
        "dispatch_mode": "daily-grind",
    }
    scan_payload = {
        "project_name": "selftest-workspace",
        "commit_count": 1,
        "languages": ["Python"],
        "recent_topics": ["feat: live selftest"],
        "has_structured_commits": True,
    }
    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "discover_agents",
        return_value=[
            {"name": "claude", "functional": True, "version": "test", "roles": ["pm"]},
            {"name": "codex", "functional": False, "version": "broken", "roles": ["build"]},
        ],
    ), patch.object(synlynk_pkg, "_static_scan", return_value=scan_payload), patch.object(
        synlynk_pkg,
        "_write_informed_skeleton",
        return_value=[],
    ), patch.object(
        synlynk_pkg,
        "_build_templates",
        return_value={"config.json": json.dumps(config_payload)},
    ), patch.object(
        synlynk_pkg,
        "_write_instruction_file",
        return_value=None,
    ), patch.object(
        synlynk_pkg,
        "_write_instruction_manifest",
        return_value=None,
    ), patch.object(
        synlynk_pkg,
        "install_pre_commit_hook",
        return_value=None,
    ), patch.object(builtins, "input", side_effect=lambda prompt="": ""):
        result, output, _ = _capture_call(
            entry["command"],
            lambda: synlynk_pkg.init(
                force=True,
                agents=["claude"],
                org="synlynk",
                repo="synlynk",
                project_id="proj-selftest",
                mode="solo",
            ),
        )
    if result.status != "pass":
        return result
    if "Step 1/6" not in output or not (workspace / ".synlynk" / "config.json").exists():
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="init did not bootstrap the workspace scaffold",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="init bootstrapped the workspace scaffold",
    )


def _scenario_scan(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    scan_payload = {
        "workspace_name": "selftest-workspace",
        "repos": [
            {
                "name": workspace.name,
                "path": str(workspace),
                "stack_labels": ["python"],
            }
        ],
        "skills": [],
        "topology": "mono",
        "stack": "python",
        "source": [],
        "complexity": {"hotspots": [], "todo_counts": {"TODO": 0, "FIXME": 0, "HACK": 0, "XXX": 0}},
        "tests": {"gap_count": 0},
        "git": {"churn": [], "total_commits_scanned": 0},
        "arch": {"pattern": "library"},
    }
    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "run_workspace_scan",
        return_value=scan_payload,
    ), patch.object(
        synlynk_pkg,
        "_card_summary",
        side_effect=lambda key, data: (f"{key} ok", ""),
    ), patch.object(
        synlynk_pkg,
        "_write_scan_fences",
        return_value=[str(workspace / ".synlynk" / "context.md")],
    ):
        result, output, _ = _capture_call(
            entry["command"],
            lambda: synlynk_pkg.cmd_scan(no_tui=True),
        )
    if result.status != "pass":
        return result
    if "synlynk scan" not in output or "workspace: selftest-workspace" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="scan did not render the workspace summary",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="scan rendered the workspace summary",
    )


def _scenario_join(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "get_username",
        return_value="tester",
    ), patch.object(
        synlynk_pkg,
        "cmd_scan",
        return_value=None,
    ), patch.object(
        synlynk_pkg,
        "_generate_ai_context_files",
        return_value=None,
    ), patch.object(
        synlynk_pkg,
        "_seed_devlog",
        return_value=None,
    ):
        result, output, _ = _capture_call(entry["command"], synlynk_pkg.cmd_join)
    if result.status != "pass":
        return result
    if "Joining project as @tester" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="join did not announce the current user",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="join completed the onboarding flow",
    )


def _scenario_goal_create(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk.db as db_mod
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        result, output, goal_id = _capture_call(
            entry["command"],
            lambda: db_mod.cmd_goal_create("Live selftest goal", "goal passes the smoke test"),
        )
    if result.status != "pass":
        return result
    if not isinstance(goal_id, str) or not goal_id.startswith("goal-"):
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="goal create did not return a goal id",
        )
    ctx.state["goal_id"] = goal_id
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail=f"created {goal_id}",
    )


def _scenario_goal_list(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk.db as db_mod
    import synlynk as synlynk_pkg

    goal_id = ctx.state.get("goal_id")
    if not goal_id:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="goal create must run before goal list",
        )
    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        result, output, _ = _capture_call(entry["command"], db_mod.cmd_goal_list)
    if result.status != "pass":
        return result
    if goal_id not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="goal list did not include the live goal",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="goal list included the live goal",
    )


def _scenario_goal_link(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk.db as db_mod
    import synlynk as synlynk_pkg

    goal_id = ctx.state.get("goal_id")
    if not goal_id:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="goal create must run before goal link",
        )
    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)), patch.object(
        db_mod,
        "_generate_todo_md",
        return_value=None,
    ):
        result, _, story_id = _capture_call(
            entry["command"],
            lambda: db_mod.cmd_story_create("Live selftest story", discipline="backend"),
        )
        if result.status != "pass":
            return result
        if not isinstance(story_id, str) or not story_id.startswith("story-"):
            return ScenarioResult(
                command=entry["command"],
                status="fail",
                detail="story create did not return a story id",
            )
        ctx.state["story_id"] = story_id
        result, output, _ = _capture_call(
            entry["command"],
            lambda: db_mod.cmd_goal_link(story_id, goal_id),
        )
    if result.status != "pass":
        return result
    if "linked to" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="goal link did not confirm the link",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail=f"linked {story_id} to {goal_id}",
    )


def _scenario_goal_status(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk.db as db_mod
    import synlynk as synlynk_pkg

    goal_id = ctx.state.get("goal_id")
    story_id = ctx.state.get("story_id")
    if not goal_id or not story_id:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="goal link must run before goal status",
        )
    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        result, output, _ = _capture_call(entry["command"], db_mod.cmd_goal_status)
    if result.status != "pass":
        return result
    if goal_id not in output or "Stories: 0/1 done" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="goal status did not report the expected rollup",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="goal status reported the live rollup",
    )


def _scenario_story_create(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk.db as db_mod
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)), patch.object(
        db_mod,
        "_generate_todo_md",
        return_value=None,
    ):
        result, output, story_id = _capture_call(
            entry["command"],
            lambda: db_mod.cmd_story_create("Second live selftest story", discipline="backend"),
        )
    if result.status != "pass":
        return result
    if not isinstance(story_id, str) or not story_id.startswith("story-"):
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="story create did not return a story id",
        )
    ctx.state["latest_story_id"] = story_id
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail=f"created {story_id}",
    )


def _scenario_story_list(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk.db as db_mod
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        result, output, _ = _capture_call(entry["command"], db_mod.cmd_story_list)
    if result.status != "pass":
        return result
    if "Live selftest story" not in output and "Second live selftest story" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="story list did not include the live stories",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="story list included the live stories",
    )


def _scenario_decide(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "_run_agent_sync",
        side_effect=lambda agent, prompt, timeout=120: f"{agent} recommends the obvious option.",
    ), patch.object(
        synlynk_pkg,
        "_check_upstream_divergence",
        return_value=None,
    ):
        result, output, _ = _capture_call(
            entry["command"],
            lambda: synlynk_pkg.cmd_decide("Choose the best path", ["claude", "codex"], record=False),
        )
    if result.status != "pass":
        return result
    if "Convening panel" not in output or "Synthesizing" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="decide did not run the panel flow",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="decide ran the live panel flow",
    )


def _scenario_jobs(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daemon_jobs (
            job_id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            task TEXT NOT NULL,
            story_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            priority INTEGER NOT NULL DEFAULT 5,
            depends_on TEXT NOT NULL DEFAULT '[]',
            pid INTEGER,
            enqueued_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            exit_code INTEGER,
            log_path TEXT,
            handoff_count INTEGER NOT NULL DEFAULT 0,
            previous_agents TEXT
        )
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO daemon_jobs (job_id, agent, task, story_id, status, enqueued_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("job-selftest", "codex", "live selftest task", None, "running", "2026-07-17T00:00:00"),
    )
    conn.commit()
    conn.close()
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)), patch.object(
        synlynk_pkg,
        "_reconcile_daemon_jobs",
        return_value=None,
    ), patch.object(
        synlynk_pkg,
        "_reconcile_jobs",
        return_value=None,
    ):
        result, output, _ = _capture_call(entry["command"], synlynk_pkg.cmd_jobs)
    if result.status != "pass":
        return result
    if "job-selftest" not in output or "codex" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="jobs did not show the seeded daemon job",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="jobs showed the seeded daemon job",
    )


def _scenario_status(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg
    import synlynk.costs as costs_mod
    import synlynk.status as status_mod

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS harness_status (
            agent_name TEXT PRIMARY KEY,
            attach_rate_24h REAL,
            attach_point_in_time INTEGER,
            completion_rate_24h REAL,
            installed_version TEXT,
            latest_version TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cycle_capability (
            agent_name TEXT,
            cycle TEXT,
            support TEXT
        )
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO harness_status (agent_name, attach_rate_24h, attach_point_in_time, completion_rate_24h, installed_version, latest_version) VALUES (?, ?, ?, ?, ?, ?)",
        ("claude", 1.0, 1, 0.8, "1.0.0", "1.0.0"),
    )
    conn.execute(
        "INSERT INTO cycle_capability (agent_name, cycle, support, verb_count, full_count, partial_count, updated_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        ("claude", "execute", "full", 1, 1, 0),
    )
    conn.commit()
    conn.close()
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)), patch.object(
        costs_mod,
        "_load_model_rates",
        return_value={"rates_updated_at": "2026-07-17"},
    ):
        result, output, _ = _capture_call(entry["command"], lambda: status_mod.cmd_status(json_output=False))
    if result.status != "pass":
        return result
    if "SYNLYNK ECOSYSTEM STATUS" not in output or "claude" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="status did not include the seeded harness row",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="status rendered the seeded harness row",
    )


def _scenario_instructions_status(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk.instructions as instructions_mod

    workspace = _ensure_workspace_scaffold(ctx)
    tracked_file = workspace / "AGENTS.md"
    tracked_file.write_text(
        "<!-- synlynk:start version=\"1\" tool=\"codex\" -->\n"
        "## live selftest\n"
        "<!-- synlynk:end -->\n"
    )
    manifest = {
        str(tracked_file): {
            "tool": "codex",
            "sha": instructions_mod._compute_section_sha("## live selftest\n"),
            "last_checked": "2026-07-17T00:00:00Z",
        }
    }
    with _chdir(workspace), patch.object(
        instructions_mod,
        "_load_instruction_manifest",
        return_value=manifest,
    ):
        result, output, _ = _capture_call(entry["command"], instructions_mod.cmd_instructions_status)
    if result.status != "pass":
        return result
    if "AGENTS.md" not in output or "codex" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="instructions status did not report the seeded manifest",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="instructions status reported the seeded manifest",
    )


_TRIVIAL_PROMPT = "Reply with the single word OK and do nothing else."


def _dispatch_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    if ctx.remaining_budget() <= 0:
        return ScenarioResult(command="dispatch", status="skipped", detail="budget cap reached")
    import os

    old_cwd = os.getcwd()
    os.chdir(ctx.repo_path)
    try:
        job = dispatch_agent("codex", _TRIVIAL_PROMPT, force_agent=True)
    except Exception as exc:
        return ScenarioResult(command="dispatch", status="fail", detail=str(exc))
    finally:
        os.chdir(old_cwd)
    fence = job.get("fence")
    cost = fence.cost_usd if fence else 0.0
    return ScenarioResult(
        command="dispatch",
        status="pass",
        detail=f"launched {job.get('id')} pid={job.get('pid')}",
        cost_usd=cost,
    )


def _exec_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    if ctx.remaining_budget() <= 0:
        return ScenarioResult(command="exec", status="skipped", detail="budget cap reached")
    import os

    old_cwd = os.getcwd()
    os.chdir(ctx.repo_path)
    try:
        exit_code = exec_command(["claude", "-p", _TRIVIAL_PROMPT])
    except Exception as exc:
        return ScenarioResult(command="exec", status="fail", detail=str(exc))
    finally:
        os.chdir(old_cwd)
    if exit_code != 0:
        return ScenarioResult(command="exec", status="fail", detail=f"exit code {exit_code}")
    return ScenarioResult(command="exec", status="pass", detail="exec completed")


def _schedule_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    if ctx.remaining_budget() <= 0:
        return ScenarioResult(command="schedule", status="skipped", detail="budget cap reached")
    from synlynk.scheduler import cmd_schedule
    import os

    old_cwd = os.getcwd()
    os.chdir(ctx.repo_path)
    try:
        cmd_schedule(execute=True, max_stories=1)
    except Exception as exc:
        return ScenarioResult(command="schedule", status="fail", detail=str(exc))
    finally:
        os.chdir(old_cwd)
    return ScenarioResult(command="schedule", status="pass", detail="schedule --execute ran")


def _release_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    return ScenarioResult(
        command="release",
        status="skipped",
        detail=(
            "release is a real-world publish action (git tag/push, GitHub release) - "
            "not safe to run against a scratch repo; verified structurally via --help only"
        ),
    )


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


SELFTEST_SCENARIOS: Dict[str, Callable[[dict, ScenarioContext], ScenarioResult]] = {
    "init": _scenario_init,
    "scan": _scenario_scan,
    "join": _scenario_join,
    "goal create": _scenario_goal_create,
    "goal list": _scenario_goal_list,
    "goal link": _scenario_goal_link,
    "goal status": _scenario_goal_status,
    "story create": _scenario_story_create,
    "story list": _scenario_story_list,
    "decide": _scenario_decide,
    "jobs": _scenario_jobs,
    "status": _scenario_status,
    "instructions status": _scenario_instructions_status,
    "dispatch": _dispatch_scenario,
    "exec": _exec_scenario,
    "schedule": _schedule_scenario,
    "release": _release_scenario,
}

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
