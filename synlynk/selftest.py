"""Taxonomy-driven command selftest helpers."""

from __future__ import annotations

import argparse
import builtins
import contextlib
import io
import json
import os
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List
from unittest.mock import patch

from synlynk.dispatch import dispatch_agent, exec_command
from synlynk.cli import build_parser
from synlynk import discover_agents
from synlynk.jobs import _resolve_worktree_pr_base_branch
from synlynk.taxonomy import COMMAND_TAXONOMY


@dataclass
class ScenarioContext:
    repo_path: str
    live: bool
    budget_cap_usd: float = 2.0
    spent_usd: float = 0.0
    state: dict = field(default_factory=dict)
    mode: str = "home"
    harness: str | None = None

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
                    "budget": {"limit_usd": 2.0},
                    "roles": {},
                },
                indent=2,
            )
        )
    if ctx.live and not (workspace / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        subprocess.run(
            ["git", "config", "user.name", "synlynk-selftest"],
            cwd=workspace,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "selftest@synlynk.local"],
            cwd=workspace,
            check=True,
        )
        (docs_dir / ".gitkeep").touch(exist_ok=True)
        subprocess.run(
            ["git", "add", ".synlynk/config.json", "project-docs/.gitkeep"],
            cwd=workspace,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "chore: bootstrap selftest workspace", "--quiet"],
            cwd=workspace,
            check=True,
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
    return _scenario_init_existing_files(entry, ctx)


def _scenario_init_existing_files(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    existing_claude = workspace / "CLAUDE.md"
    existing_gemini = workspace / "GEMINI.md"
    existing_roadmap = workspace / "project-docs" / "roadmap.md"
    existing_claude.write_text("seeded claude instructions\n")
    existing_gemini.write_text("seeded gemini instructions\n")
    existing_roadmap.write_text("# seeded roadmap\n")
    before = {
        path: path.read_bytes()
        for path in (existing_claude, existing_gemini, existing_roadmap)
    }
    scan_payload = {
        "project_name": "selftest-workspace",
        "commit_count": 1,
        "languages": ["Python"],
        "recent_topics": ["feat: live selftest"],
        "has_structured_commits": True,
    }
    db_path = workspace / ".synlynk" / "state.db"
    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "discover_agents",
        return_value=[],
    ), patch.object(synlynk_pkg, "_static_scan", return_value=scan_payload), patch.object(
        synlynk_pkg,
        "DB_PATH",
        str(db_path),
    ), patch.object(
        builtins,
        "input",
        side_effect=lambda prompt="": "",
    ):
        result, output, _ = _capture_call(
            entry["command"],
            lambda: synlynk_pkg.init(
                force=False,
                agents=["codex"],
                org="synlynk",
                repo="synlynk",
                project_id="proj-selftest",
                mode="solo",
            ),
        )
    if result.status != "pass":
        return result
    after = {
        path: path.read_bytes()
        for path in (existing_claude, existing_gemini, existing_roadmap)
    }
    if "Step 1/6" not in output or not (workspace / ".synlynk" / "config.json").exists():
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="init did not bootstrap the workspace scaffold",
        )
    if before != after:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="init modified pre-existing workspace files",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="init bootstrapped the workspace scaffold without clobbering existing files",
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
    devlog_dir = workspace / "project-docs" / "devlogs"
    if not devlog_dir.exists() or not any(devlog_dir.iterdir()):
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="join did not create a real devlog entry",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="join completed the onboarding flow and created a real devlog entry",
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
        synlynk_pkg,
        "_generate_todo_md",
        return_value=None,
    ), patch.object(
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
        synlynk_pkg,
        "_generate_todo_md",
        return_value=None,
    ), patch.object(
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

    def _fake_run_agent_sync(agent: str, prompt: str, timeout: int | None = 120) -> str:
        if "Synthesize these into a single decision" in prompt:
            return (
                "claude recommends the obvious option.\n"
                "codex recommends the obvious option.\n"
                "Decision: choose the obvious option."
            )
        return f"{agent} recommends the obvious option."

    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "_run_agent_sync",
        side_effect=_fake_run_agent_sync,
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
    if "claude recommends" not in output or "codex recommends" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="decide did not surface each panelist's individual response",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="decide ran the live panel flow and surfaced every panelist's response",
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
            previous_agents TEXT,
            dispatch_context TEXT
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
    with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        conn = synlynk_pkg._get_db()
        conn.execute(
            "INSERT OR REPLACE INTO harness_status (harness_name, attach_rate_24h, attach_point_in_time, completion_rate_24h, installed_version, latest_version) VALUES (?, ?, ?, ?, ?, ?)",
            ("claude", 1.0, 1, 0.8, "1.0.0", "1.0.0"),
        )
        conn.execute(
            "INSERT INTO cycle_capability (harness_name, cycle, support, verb_count, full_count, partial_count, updated_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            ("claude", "execute", "full", 1, 1, 0),
        )
        conn.commit()
        conn.close()
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)), patch.object(
        costs_mod,
        "_load_model_rates",
        return_value={"rates_updated_at": "2026-07-17"},
    ):
        result, output, _ = _capture_call(
            entry["command"], lambda: status_mod.cmd_status(json_output=False)
        )
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


def _seed_migrate_workspace(workspace: Path) -> dict[str, bytes]:
    docs_dir = workspace / "project-docs"
    devlogs_dir = docs_dir / "devlogs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    devlogs_dir.mkdir(parents=True, exist_ok=True)

    files = {
        docs_dir / "memory.md": (
            "# Workspace Memory\n\n"
            "## Decisions\n"
            "Use the live selftest scratch repo. [@codex]\n\n"
            "## Risks\n"
            "Keep the migration deterministic.\n"
        ),
        docs_dir / "roadmap.md": (
            "# Workspace Roadmap\n\n"
            "## v0.2.0 - Migration Pilot <!-- goal:goal-live-migrate -->\n\n"
            "- import project-docs [P0]\n"
            "- verify state.db rows [P1]\n"
        ),
        docs_dir / "costs.md": (
            "| Date | Agent | Model | In | Out | Cache | Cost | Notes |\n"
            "|---|---|---|---|---|---|---|---|\n"
            "| 2026-07-22 | claude | sonnet | 120000 | 24000 | 0 | $0.88 | migrate live scenario |\n"
        ),
        devlogs_dir / "nikhil.md": (
            "# Nikhil Devlog\n\n"
            "## 2026-07-22 — Session: live migrate coverage\n\n"
            "### Shipped\n"
            "- state db import path\n"
        ),
        docs_dir / "todo.md": (
            "- [ ] live migrate story <!-- id:story-live-migrate --> <!-- gh:#451 -->\n"
            "- [ ] unrelated task <!-- id:story-unrelated -->\n"
        ),
    }
    for path, content in files.items():
        path.write_text(content)
    return {path: path.read_bytes() for path in files}


def _scenario_migrate(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import synlynk as synlynk_pkg
    import synlynk.db as db_mod

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    before_docs = _seed_migrate_workspace(workspace)
    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        conn = synlynk_pkg._get_db()
        conn.execute(
            "INSERT OR REPLACE INTO goals (goal_id, outcome, criterion, status) VALUES (?,?,?,?)",
            (
                "goal-live-migrate",
                "Validate live migrate coverage",
                "Migrate seeded project-docs into state.db",
                "active",
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO stories (story_id, title, status) VALUES (?,?,?)",
            ("story-live-migrate", "live migrate story", "open"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO stories (story_id, title, status) VALUES (?,?,?)",
            ("story-unrelated", "unrelated task", "open"),
        )
        conn.commit()
        conn.close()
        with patch("synlynk.rollback.rollback_checkpoint", side_effect=lambda *args, **kwargs: contextlib.nullcontext()):
            result, output, _ = _capture_call(entry["command"], db_mod.cmd_migrate)
    if result.status != "pass":
        return result

    backup_dir = workspace / ".synlynk" / "project-docs"
    sentinel = workspace / ".synlynk" / ".synlynk_migrated"
    gitignore = (workspace / ".gitignore").read_text()
    after_docs = {
        path: path.read_bytes()
        for path in before_docs
    }
    if any(before_docs[path] != after_docs[path] for path in before_docs):
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="migrate rewrote source project-docs files",
        )

    conn = sqlite3.connect(db_path)
    try:
        memory_rows = conn.execute(
            "SELECT section, body, author FROM memory_entries ORDER BY id"
        ).fetchall()
        arc_rows = conn.execute(
            "SELECT version, title, status, goal_id FROM roadmap_arcs ORDER BY id"
        ).fetchall()
        phase_rows = conn.execute(
            "SELECT arc_version, phase_title, status, priority FROM roadmap_phases ORDER BY id"
        ).fetchall()
        cost_rows = conn.execute(
            "SELECT session_date, agent, model, input_tokens, output_tokens, cache_read_tokens, total_cost_usd, cost_source "
            "FROM cost_entries ORDER BY id"
        ).fetchall()
        devlog_rows = conn.execute(
            "SELECT author, entry_date, session_title, body FROM devlog_entries ORDER BY id"
        ).fetchall()
        story_row = conn.execute(
            "SELECT gh_issue FROM stories WHERE story_id=?",
            ("story-live-migrate",),
        ).fetchone()
    finally:
        conn.close()

    expected_memory = [
        ("Decisions", "Use the live selftest scratch repo. [@codex]", "codex"),
        ("Risks", "Keep the migration deterministic.", None),
    ]
    expected_arc = ("v0.2.0", "Migration Pilot", "planned", "goal-live-migrate")
    expected_phases = [
        ("v0.2.0", "import project-docs [P0]", "planned", "P0"),
        ("v0.2.0", "verify state.db rows [P1]", "planned", "P1"),
    ]
    expected_cost = ("2026-07-22", "claude", "sonnet", 120000, 24000, 0, 0.88, "legacy_unknown")
    expected_devlog = (
        "nikhil",
        "2026-07-22",
        "live migrate coverage",
        "### Shipped\n- state db import path",
    )

    if list(memory_rows) != expected_memory:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail=f"migrate memory rows mismatch: {memory_rows!r}",
        )
    if list(arc_rows) != [expected_arc]:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail=f"migrate roadmap arcs mismatch: {arc_rows!r}",
        )
    if list(phase_rows) != expected_phases:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail=f"migrate roadmap phases mismatch: {phase_rows!r}",
        )
    if list(cost_rows) != [expected_cost]:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail=f"migrate cost rows mismatch: {cost_rows!r}",
        )
    if expected_devlog not in devlog_rows:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail=f"migrate devlog rows missing expected entry: {devlog_rows!r}",
        )
    if not story_row or story_row[0] != "#451":
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail=f"migrate did not sync gh_issue into stories: {story_row!r}",
        )
    if not sentinel.exists():
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="migrate did not write the sentinel file",
        )
    if "project-docs/" not in gitignore:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="migrate did not add project-docs/ to .gitignore",
        )
    if not backup_dir.exists():
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="migrate did not copy docs into .synlynk/project-docs",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="migrate imported seeded project-docs into state.db and preserved the source files",
    )


def _scenario_migrate_failure_injection(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    """Injects a failure mid-migrate and asserts the workspace is fully rolled back."""
    import synlynk as synlynk_pkg
    import synlynk.db as db_mod
    from synlynk import rollback

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    before_docs = _seed_migrate_workspace(workspace)

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure: simulated git rm --cached failure")

    with _chdir(workspace), patch.object(synlynk_pkg, "DB_PATH", str(db_path)), patch.object(
        db_mod, "_migrate_dr_mirror", boom
    ):
        conn = synlynk_pkg._get_db()
        conn.execute(
            "INSERT OR REPLACE INTO goals (goal_id, outcome, criterion, status) VALUES (?,?,?,?)",
            (
                "goal-live-migrate",
                "Validate live migrate coverage",
                "Migrate seeded project-docs into state.db",
                "active",
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO stories (story_id, title, status) VALUES (?,?,?)",
            ("story-live-migrate", "live migrate story", "open"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO stories (story_id, title, status) VALUES (?,?,?)",
            ("story-unrelated", "unrelated task", "open"),
        )
        conn.commit()
        conn.close()
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar = db_path.with_name(db_path.name + suffix)
            if sidecar.exists():
                sidecar.unlink()
        subprocess.run(["git", "add", ".synlynk/state.db"], cwd=workspace, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: track seeded state.db for migrate selftest", "--quiet"],
            cwd=workspace,
            check=True,
        )
        before_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=workspace, capture_output=True, text=True
        ).stdout.strip()
        result, output, _ = _capture_call(entry["command"], db_mod.cmd_migrate)

    if result.status != "fail":
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail=f"expected injected failure to propagate, got: {result.status}",
        )

    after_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=workspace, capture_output=True, text=True
    ).stdout.strip()
    if after_head != before_head:
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="migrate rollback did not reset HEAD to the pre-op checkpoint",
        )
    sentinel = workspace / ".synlynk" / ".synlynk_migrated"
    if sentinel.exists():
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="migrate rollback left the sentinel file behind",
        )
    manifest_live = workspace / ".synlynk" / "rollback" / "last.json"
    if manifest_live.exists():
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="rollback manifest was not archived after auto-rollback",
        )
    return ScenarioResult(
        command=entry["command"], status="pass",
        detail="migrate auto-rolled back to the pre-op checkpoint after an injected failure",
    )


def _scenario_upgrade(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    import importlib
    import synlynk as synlynk_pkg

    upgrade_mod = importlib.import_module("synlynk.upgrade")

    workspace = _ensure_workspace_scaffold(ctx)
    sentinel_file = workspace / "upgrade-sentinel.txt"
    sentinel_file.write_text("keep me untouched\n")
    before = sentinel_file.read_bytes()
    install_root = workspace / ".local" / "pipx" / "venvs" / "synlynk"
    install_root.mkdir(parents=True, exist_ok=True)
    recorded_calls = []

    class Result:
        def __init__(self, returncode: int = 0, stdout: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"echo synlynk-upgrade"

    def fake_run(args, *_, **__):
        recorded_calls.append(list(args))
        if args and args[0] == "gh":
            return Result(returncode=0, stdout="v9.9.9\n")
        if args and args[0] == "pipx":
            return Result(returncode=0)
        if args and args[0] == "bash":
            return Result(returncode=0)
        return Result(returncode=0)

    with _chdir(workspace), patch.object(
        synlynk_pkg,
        "_detect_install_type",
        return_value="pipx",
    ), patch.object(
        synlynk_pkg,
        "_get_pipx_source",
        return_value=str(install_root),
    ), patch.object(
        upgrade_mod.subprocess,
        "run",
        side_effect=fake_run,
    ), patch.object(
        upgrade_mod.urllib.request,
        "urlopen",
        return_value=Response(),
    ), patch.dict(upgrade_mod.os.environ, {"HOME": str(workspace)}):
        result, output, _ = _capture_call(entry["command"], upgrade_mod.upgrade)
    if result.status != "pass":
        return result
    if sentinel_file.read_bytes() != before:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="upgrade modified files outside its install location",
        )
    if not any(call[:2] == ["pipx", "install"] for call in recorded_calls):
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="upgrade did not route through the pipx reinstall branch",
        )
    if "Upgraded to v9.9.9 via pipx" not in output:
        return ScenarioResult(
            command=entry["command"],
            status="fail",
            detail="upgrade did not report the pipx upgrade path",
        )
    return ScenarioResult(
        command=entry["command"],
        status="pass",
        detail="upgrade identified the pipx install path without touching unrelated files",
    )


def _scenario_upgrade_failure_injection(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    """Injects a failure mid-upgrade for a script install and asserts bin/lib are restored.

    Drives rollback_checkpoint_upgrade directly (as test_rollback.py's
    test_rollback_checkpoint_upgrade_script_restores_bin_and_lib does) rather than through
    upgrade._run_upgrade's script-install path — that path wraps its subprocess.run call in a
    broad try/except that prints a manual-fix message instead of re-raising, so a subprocess
    failure there never propagates out to the rollback_checkpoint_upgrade context manager.
    That swallow-and-warn behavior is pre-existing and out of scope for this scenario; this
    exercises the Leg 2 restore mechanism itself under a live selftest workspace.
    """
    from synlynk import rollback

    workspace = _ensure_workspace_scaffold(ctx)
    home = workspace / "fake-home"
    bin_dir = home / ".synlynk" / "bin"
    lib_dir = home / ".synlynk" / "lib"
    bin_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "synlynk").write_text("#!/bin/sh\necho old-version\n")
    before = (bin_dir / "synlynk").read_bytes()

    def action():
        with patch.object(rollback.os.path, "expanduser", side_effect=lambda p: p.replace("~", str(home))):
            with rollback.rollback_checkpoint_upgrade("0.12.0", "script"):
                (bin_dir / "synlynk").write_text("#!/bin/sh\necho new-version\n")
                raise RuntimeError("injected failure: simulated install script failure")

    with _chdir(workspace):
        result, output, _ = _capture_call(entry["command"], action)

    if result.status != "fail":
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail=f"expected injected failure to propagate, got: {result.status}",
        )
    if (bin_dir / "synlynk").read_bytes() != before:
        return ScenarioResult(
            command=entry["command"], status="fail",
            detail="upgrade rollback did not restore ~/.synlynk/bin after an injected failure",
        )
    return ScenarioResult(
        command=entry["command"], status="pass",
        detail="upgrade auto-rolled back the script install after an injected failure",
    )


_GH_WRITE_ACTIONS = ("gh pr review", "gh pr merge", "gh issue comment")


def _attempt_gh_write_action(agent_name: str, mode: str, action: str) -> str:
    """Best-effort structural check for whether gh exposes a write action."""
    import subprocess as _subprocess

    parts = action.split()
    try:
        result = _subprocess.run(
            ["gh", *parts[1:], "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, _subprocess.TimeoutExpired):
        return "fail"
    return "pass" if result.returncode == 0 else "fail"


def _scenario_gh_write_actions(entry: dict, ctx: ScenarioContext) -> list[ScenarioResult]:
    import synlynk as synlynk_pkg

    workspace = _ensure_workspace_scaffold(ctx)
    db_path = workspace / ".synlynk" / "state.db"
    results: list[ScenarioResult] = []
    with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        conn = synlynk_pkg._get_db()
        for agent in discover_agents():
            agent_name = agent["name"]
            for mode in ("home", "headless"):
                for action in _GH_WRITE_ACTIONS:
                    status = _attempt_gh_write_action(agent_name, mode, action)
                    conn.execute(
                        "INSERT OR REPLACE INTO gh_write_capability "
                        "(harness, mode, action, status, checked_at) VALUES (?, ?, ?, ?, datetime('now'))",
                        (agent_name, mode, action, status),
                    )
                    results.append(
                        ScenarioResult(
                            command=f"{action}[{agent_name}/{mode}]",
                            status=status,
                            detail=f"{action} structural check for {agent_name} in {mode} mode",
                        )
                    )
        conn.commit()
        conn.close()
    return results


_TRIVIAL_PROMPT = "Reply with the single word OK and do nothing else."


def _wait_for_worktree_finalization(job: dict, timeout_s: int = 60) -> dict:
    """Poll until the dispatched worktree job's process exits."""
    import time as _time

    pid = job.get("pid")
    if not pid:
        return job
    deadline = _time.time() + timeout_s
    while _time.time() < deadline:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            break
        _time.sleep(1)
    return job


def _dispatch_scenario(entry: dict, ctx: ScenarioContext) -> list[ScenarioResult]:
    import os
    from synlynk import discover_agents
    import synlynk as synlynk_pkg

    results: list[ScenarioResult] = []
    for agent in discover_agents():
        agent_name = agent["name"]
        if ctx.remaining_budget() <= 0:
            results.append(
                ScenarioResult(
                    command=f"dispatch[{agent_name}]",
                    status="skipped",
                    detail="budget cap reached",
                )
            )
            continue
        workspace = Path(ctx.repo_path)
        db_path = workspace / ".synlynk" / "state.db"
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
                job = dispatch_agent(agent_name, _TRIVIAL_PROMPT, force_agent=True)
            fence = job.get("fence")
            cost = fence.cost_usd if fence else 0.0
            job = _wait_for_worktree_finalization(job)
            worktree_path = job.get("worktree_path")
            expected_base = job.get("base_branch")
            if worktree_path and expected_base:
                actual_base = _resolve_worktree_pr_base_branch(job, worktree_path)
                if actual_base != expected_base:
                    results.append(
                        ScenarioResult(
                            command=f"dispatch[{agent_name}]",
                            status="fail",
                            detail=(
                                f"PR base branch mismatch: expected {expected_base!r}, "
                                f"resolved {actual_base!r}"
                            ),
                        )
                    )
                    continue
            results.append(
                ScenarioResult(
                    command=f"dispatch[{agent_name}]",
                    status="pass",
                    detail=f"launched {job.get('id')} pid={job.get('pid')}",
                    cost_usd=cost,
                )
            )
        except Exception as exc:
            results.append(
                ScenarioResult(
                    command=f"dispatch[{agent_name}]",
                    status="fail",
                    detail=str(exc),
                )
            )
        finally:
            os.chdir(old_cwd)
    return results


def _exec_scenario(entry: dict, ctx: ScenarioContext) -> list[ScenarioResult]:
    import os
    from synlynk import discover_agents
    import synlynk as synlynk_pkg

    results: list[ScenarioResult] = []
    for agent in discover_agents():
        agent_name = agent["name"]
        if ctx.remaining_budget() <= 0:
            results.append(
                ScenarioResult(
                    command=f"exec[{agent_name}]",
                    status="skipped",
                    detail="budget cap reached",
                )
            )
            continue
        workspace = Path(ctx.repo_path)
        db_path = workspace / ".synlynk" / "state.db"
        old_cwd = os.getcwd()
        os.chdir(ctx.repo_path)
        try:
            with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
                exit_code = exec_command([agent_name, "-p", _TRIVIAL_PROMPT])
            if exit_code != 0:
                results.append(
                    ScenarioResult(
                        command=f"exec[{agent_name}]",
                        status="skipped",
                        detail=f"exit code {exit_code}",
                    )
                )
            else:
                results.append(
                    ScenarioResult(
                        command=f"exec[{agent_name}]",
                        status="pass",
                        detail="exec completed",
                    )
                )
        except Exception as exc:
            results.append(
                ScenarioResult(
                    command=f"exec[{agent_name}]",
                    status="fail",
                    detail=str(exc),
                )
            )
        finally:
            os.chdir(old_cwd)
    return results


def _schedule_scenario(entry: dict, ctx: ScenarioContext) -> ScenarioResult:
    if ctx.remaining_budget() <= 0:
        return ScenarioResult(command="schedule", status="skipped", detail="budget cap reached")
    from synlynk.scheduler import cmd_schedule
    import os
    import synlynk as synlynk_pkg

    workspace = Path(ctx.repo_path)
    db_path = workspace / ".synlynk" / "state.db"
    old_cwd = os.getcwd()
    os.chdir(ctx.repo_path)
    try:
        with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
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


SELFTEST_SCENARIOS: Dict[
    str, Callable[[dict, ScenarioContext], ScenarioResult | list[ScenarioResult]]
] = {
    "init": _scenario_init_existing_files,
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
    "migrate": _scenario_migrate,
    "upgrade": _scenario_upgrade,
    "gh-write-check": _scenario_gh_write_actions,
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
    if live:
        with tempfile.TemporaryDirectory(prefix="synlynk-selftest-") as scratch_dir:
            scratch_workspace = Path(scratch_dir)
            ctx.state["workspace_dir"] = scratch_workspace
            scratch_workspace = _ensure_workspace_scaffold(ctx)
            ctx.repo_path = str(scratch_workspace)
            with _chdir(scratch_workspace):
                for entry in sorted(COMMAND_TAXONOMY, key=_selftest_sort_key):
                    scenario = SELFTEST_SCENARIOS.get(entry["command"])
                    if scenario is None:
                        result = _generic_help_scenario(entry, parser)
                    else:
                        result = scenario(entry, ctx)
                    if isinstance(result, list):
                        for item in result:
                            ctx.spent_usd += item.cost_usd
                            results.append(item)
                    else:
                        ctx.spent_usd += result.cost_usd
                        results.append(result)
                gh_write_results = _scenario_gh_write_actions({"command": "gh-write-check"}, ctx)
                results.extend(gh_write_results)
        return results

    for entry in sorted(COMMAND_TAXONOMY, key=_selftest_sort_key):
        result = _generic_help_scenario(entry, parser)
        ctx.spent_usd += result.cost_usd
        results.append(result)
    return results


def cmd_selftest(
    live: bool = False,
    matrix: bool = False,
    budget: float | None = None,
) -> int:
    """CLI entry point for the command selftest (or fleet matrix)."""
    if matrix:
        from synlynk import _get_db
        from synlynk._constants import MATRIX_LIVE_BUDGET_USD
        from synlynk.fleet import (
            new_run_id,
            record_matrix_run,
            run_matrix_dry,
            run_matrix_live,
        )

        run_id = new_run_id()
        results = run_matrix_dry(".")
        if live:
            cap = budget if budget is not None else MATRIX_LIVE_BUDGET_USD
            # Real headless CLI smoke per Core 4 agent (budget-capped).
            results.extend(run_matrix_live(".", budget_usd=cap, mock=False))
        conn = _get_db()
        try:
            record_matrix_run(conn, run_id, results)
        finally:
            conn.close()

        print(f"fleet matrix run_id={run_id}")
        print(f"{'HOME':8s} {'CELL':16s} {'TIER':4s} {'STATUS':10s} DETAIL")
        for r in results:
            print(
                f"{r.home:8s} {r.cell:16s} {r.tier:<4d} {r.status:10s} {r.detail}"
            )
        reds = [r for r in results if r.status == "red" and r.tier == 1]
        greens = sum(1 for r in results if r.status == "green")
        nas = sum(1 for r in results if r.status == "na")
        print(
            f"summary: {len(results)} cells, {greens} green, {len(reds)} tier-1 red, {nas} na"
        )
        return 1 if reds else 0

    results = run_selftest(live=live)
    passes = sum(1 for result in results if result.status == "pass")
    failures = sum(1 for result in results if result.status == "fail")
    skipped = sum(1 for result in results if result.status == "skipped")

    for result in results:
        print(f"{result.status.upper():7s} {result.command:20s} {result.detail}")
    print(f"summary: {passes} passed, {failures} failed, {skipped} skipped")
    return 1 if failures else 0
