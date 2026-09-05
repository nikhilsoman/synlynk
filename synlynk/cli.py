import argparse
import os
import sys
from pathlib import Path
import re

_SYNLYNK_DIR = ".synlynk"


def _synlynk_repo_root(start=None):
    """Return the enclosing synlynk checkout, if ``start`` is inside one."""
    path = Path.cwd() if start is None else Path(start)
    if not path.is_dir():
        path = path.parent
    for candidate in (path, *path.parents):
        pyproject = candidate / "pyproject.toml"
        version_file = candidate / "VERSION"
        if not (pyproject.is_file() and version_file.is_file()):
            continue
        try:
            project_metadata = pyproject.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"(?m)^\s*name\s*=\s*[\"']synlynk[\"']\s*$", project_metadata):
            return candidate
    return None


def _warn_stale_repo_version(installed_version, cwd=None):
    """Warn when an installed CLI predates the checkout it is being used in."""
    repo_root = _synlynk_repo_root(cwd)
    if repo_root is None:
        return

    try:
        repo_version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
        installed_parts = tuple(int(part) for part in str(installed_version).split("."))
        repo_parts = tuple(int(part) for part in repo_version.split("."))
    except (OSError, ValueError):
        return

    if installed_parts >= repo_parts:
        return

    print(
        "warning: installed synlynk "
        f"{installed_version} is behind this repository's VERSION {repo_version}. "
        "Your pipx-installed CLI may be stale; refresh it with "
        "`pipx install --force git+https://github.com/nikhilsoman/synlynk.git`.",
        file=sys.stderr,
    )

def cmd_watch(args) -> None:
    """Terminal HUD for live workspace state."""
    import select
    import termios
    import time
    import tty

    from synlynk import _resolve_db_path
    from synlynk.hud import CYCLES, FrameBuffer, HUDRenderer, HarnessSnapshot, JobSnapshot, _get_terminal_size, render_observatory_panel
    from synlynk.observatory import build_job_observatory_snapshot

    jobs_file = os.path.join(_SYNLYNK_DIR, "jobs.json")
    if not os.path.exists(jobs_file):
        print(f"\033[38;5;196m✗ {jobs_file} not found -- run synlynk scan first\033[0m", file=sys.stderr)
        raise SystemExit(1)

    live_mode = getattr(args, "live", False)
    refresh_seconds = 3 if live_mode else 10
    snapshot = JobSnapshot(jobs_file)
    harness_snapshot = HarnessSnapshot(_resolve_db_path())
    selected_cycle_idx = CYCLES.index("execute")
    platform_expanded = False
    show_all = False
    last_refresh = 0.0
    interactive = sys.stdin.isatty()
    fd = None
    old_settings = None

    try:
        if interactive:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)

        sys.stdout.write("\033[?1049h")
        sys.stdout.write("\033[2J")
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        rows, cols = _get_terminal_size()
        buf = FrameBuffer(rows, cols)
        renderer = HUDRenderer(buf)
        rendered_once = False

        while True:
            now = time.time()
            need_refresh = not rendered_once or (now - last_refresh) >= refresh_seconds

            if need_refresh:
                rows, cols = _get_terminal_size()
                buf.rows = rows
                buf.cols = cols
                buf.clear()

                if cols < 60:
                    renderer.render_narrow_warning(cols)
                elif live_mode:
                    observatory = build_job_observatory_snapshot()
                    summary = snapshot.cycle_summary()
                    harness_data = harness_snapshot.load()
                    row = 0
                    row += renderer.render_header(summary, platform_expanded, row, harness_data=harness_data)
                    row += render_observatory_panel(buf, observatory["jobs"], observatory["rollups"], cols, start_row=row)
                    if rows - 2 > row:
                        buf.set_line(rows - 2, "  q to quit  ·  r to refresh")
                else:
                    selected_cycle = CYCLES[selected_cycle_idx]
                    summary = snapshot.cycle_summary()
                    harness_data = harness_snapshot.load()
                    row = 0
                    row += renderer.render_header(summary, platform_expanded, row, harness_data=harness_data)
                    renderer.render_sidebar(summary, selected_cycle, row, 0)
                    renderer.render_right_panel(
                        selected_cycle,
                        snapshot.active_jobs(cycle=selected_cycle),
                        snapshot.recent_jobs(n=5, cycle=selected_cycle),
                        20,
                        row,
                    )

                sys.stdout.write(buf.flush())
                sys.stdout.flush()
                rendered_once = True
                last_refresh = now

            if not interactive:
                ready, _, _ = select.select([sys.stdin], [], [], 0)
                if ready:
                    ch = sys.stdin.read(1)
                    if ch in ("q", "Q", ""):
                        break
                    if ch == "r":
                        last_refresh = 0.0
                        continue
                break

            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not ready:
                continue
            ch = sys.stdin.read(1)
            if ch in ("q", "Q", ""):
                break
            if ch == "r":
                last_refresh = 0.0
                continue
            if ch == "p" and not live_mode:
                platform_expanded = not platform_expanded
                last_refresh = 0.0
                continue
            if ch == "a" and live_mode:
                show_all = not show_all
                last_refresh = 0.0
                continue
            if ch == "\x1b" and not live_mode:
                rest = sys.stdin.read(2)
                if rest == "[A":
                    selected_cycle_idx = max(0, selected_cycle_idx - 1)
                    last_refresh = 0.0
                elif rest == "[B":
                    selected_cycle_idx = min(len(CYCLES) - 1, selected_cycle_idx + 1)
                    last_refresh = 0.0
    except KeyboardInterrupt:
        pass
    finally:
        if interactive and old_settings is not None and fd is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()

def build_parser() -> argparse.ArgumentParser:
    from synlynk._constants import CORE_FLEET
    from synlynk import (
        HARNESS_CAPABILITY_BASELINES,
        VERSION,
        SynlynkDaemon,
        SynlynkRelay,
        _CYAN,
        _GREEN,
        _RESET,
        _daemon_install_service,
        _daemon_uninstall_service,
        _update_config,
        checkpoint,
        cmd_agent_add,
        cmd_agent_configure,
        cmd_agent_list,
        cmd_agent_run,
        cmd_harness_add,
        cmd_harness_configure,
        cmd_harness_list,
        cmd_harness_run,
        cmd_audit_docs,
        cmd_decide,
        cmd_heal,
        cmd_doctor,
        cmd_exit,
        cmd_identity_init,
        cmd_instructions_ack,
        cmd_instructions_diff,
        cmd_instructions_register,
        cmd_instructions_status,
        cmd_instructions_update,
        cmd_jobs,
        cmd_jobs_handoff,
        cmd_jobs_reap,
        cmd_backfill_capability_ratings,
        cmd_join,
        cmd_launch,
        cmd_launch_ftue,
        cmd_logs,
        cmd_migrate,
        cmd_pr_check,
        cmd_probe,
        cmd_relay_broadcast,
        cmd_relay_start,
        cmd_release,
        cmd_repair,
        cmd_roles,
        cmd_run_trio,
        cmd_scan,
        cmd_cost_log,
        cmd_quota,
        cmd_quota_tpm_view,
        cmd_roadmap_add,
        cmd_score_add,
        cmd_score_attest,
        cmd_score_list,
        cmd_shell,
        cmd_status as cmd_project_status,
        cmd_story_create,
        cmd_story_draft,
        cmd_story_list,
        cmd_story_ready,
        cmd_sync,
        cmd_configure_agent,
        cmd_team_status,
        cmd_identity_init_role,
        cmd_identity_list,
        cmd_watch,
        dispatch_agent,
        exec_command,
        init,
        sentinel_clear,
        sentinel_list,
        upgrade,
        wizard_init,
    )
    from synlynk.events import cmd_events_tail
    from synlynk.status import cmd_status as cmd_ecosystem_status
    from synlynk.viz import cmd_viz
    from synlynk.scheduler import cmd_schedule

    parser = argparse.ArgumentParser(
        description="synlynk: The Universal Context Switchboard for AI Devs"
    )
    parser.add_argument("--version", action="version", version=f"synlynk {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize synlynk in a repository")
    init_parser.add_argument("--force", action="store_true",
                             help="Overwrite existing template files")
    init_parser.add_argument("--agents", default="claude,agy,codex,grok",
                             help="Comma-separated harness set to generate files for (claude,agy,codex,grok)")
    init_parser.add_argument("--mode", choices=["solo", "team"], default="solo",
                             help="Project mode written to project-docs/.synlynk_config.json")
    init_parser.add_argument("--org", default=None,
                             help="GitHub organization name (stored in .synlynk/config.json)")
    init_parser.add_argument("--repo", default=None,
                             help="GitHub repository name (stored in .synlynk/config.json)")
    init_parser.add_argument("--project-id", default=None, dest="project_id",
                             help="GitHub Projects v2 node ID (fills TODO: PROJECT_ID in harness files)")
    init_parser.add_argument("--docs-dir", default=None, dest="docs_dir",
                             help="Directory for project docs (default: project-docs). "
                                  "Use '.' for repos that keep docs at the repo root.")
    init_parser.add_argument("--wizard", action="store_true",
                             help="Run the FTUE guided setup wizard")
    init_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                             help="Preview what init would write without writing anything")

    upgrade_parser = subparsers.add_parser("upgrade", help="Check for and apply updates")
    upgrade_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                help="Preview what would be upgraded without installing")

    subparsers.add_parser("join", help="Onboard as a new member to an existing project")
    subparsers.add_parser(
        "start", help="Cold-start entry point: detect new vs existing project and guide setup"
    )
    home_parser = subparsers.add_parser("home", help="Display or switch the active home harness")
    home_parser.add_argument("harness", nargs="?", choices=["claude", "agy", "codex", "grok", "local"], help="Harness to set as home")

    team_parser = subparsers.add_parser("team", help="Team status and management")
    team_sub = team_parser.add_subparsers(dest="team_action")
    team_sub.add_parser("status", help="Show team digest: members, stories, budget")

    decide_parser = subparsers.add_parser(
        "decide", help="Convene a multi-agent panel and optionally record a Decision"
    )
    decide_parser.add_argument("topic", nargs="?", default="Executive architecture audit", help="Decision topic (quoted string)")
    decide_parser.add_argument(
        "--panel", required=False, default="claude,agy,codex,grok",
        help="Comma-separated harness names, e.g. claude,agy,codex"
    )
    decide_parser.add_argument(
        "--record", action="store_true",
        help="Write the Decision record to project-docs/decisions/"
    )
    decide_parser.add_argument("--audit", action="store_true", help="Write an executive architecture audit brief")

    heal_parser = subparsers.add_parser("heal", help="Scan, remediate, verify, and optionally merge fixes")
    heal_parser.add_argument("--auto-merge", action="store_true", help="Merge verified pull requests")
    heal_parser.add_argument("--batch-size", type=int, default=1, help="Maximum findings to remediate")

    audit_docs_parser = subparsers.add_parser(
        "audit-docs", help="Detect (and optionally fix) devlog author-identity drift"
    )
    audit_docs_parser.add_argument(
        "--json", action="store_true", help="Emit findings as JSON"
    )
    audit_docs_parser.add_argument(
        "--fix", action="store_true",
        help="Merge fork findings into their canonical member devlog (unregistered findings are never auto-fixed)"
    )

    goal_parser = subparsers.add_parser("goal", help="Manage Business Goals")
    goal_sub = goal_parser.add_subparsers(dest="goal_action")
    goal_create_parser = goal_sub.add_parser("create", help="Create a Business Goal")
    goal_create_parser.add_argument("--outcome", required=True)
    goal_create_parser.add_argument("--criterion", required=True)
    goal_create_parser.add_argument("--deadline", default=None)
    goal_create_parser.add_argument("--role", default="pm")
    goal_sub.add_parser("list", help="List active goals")
    goal_link_parser = goal_sub.add_parser("link", help="Link a story to a goal")
    goal_link_parser.add_argument("story_id")
    goal_link_parser.add_argument("--goal", required=True, dest="goal_id")
    goal_link_parser.add_argument("--secondary", action="store_true")
    goal_sub.add_parser("status", help="Show goal completion rollup")

    local_parser = subparsers.add_parser("local", help="Manage the local (oMLX) harness")
    local_sub = local_parser.add_subparsers(dest="local_action")
    local_sub.add_parser("doctor", help="Check oMLX endpoint reachability and model roster")

    models_parser = subparsers.add_parser("models", help="Inspect and discover the model registry")
    models_sub = models_parser.add_subparsers(dest="models_action")
    models_list_parser = models_sub.add_parser("list", help="List registered models")
    models_list_parser.add_argument("--json", action="store_true", dest="json_output")
    models_show_parser = models_sub.add_parser("show", help="Show one registered model")
    models_show_parser.add_argument("model_id")
    models_show_parser.add_argument("--json", action="store_true", dest="json_output")
    models_discover_parser = models_sub.add_parser("discover", help="Probe installed harnesses and local runtimes")
    models_discover_parser.add_argument("--json", action="store_true", dest="json_output")

    media_parser = subparsers.add_parser("media", help="Manage and generate media assets")
    media_sub = media_parser.add_subparsers(dest="media_action")
    media_generate_parser = media_sub.add_parser("generate", help="Generate SVG diagrams and OpenGraph preview cards")
    media_generate_parser.add_argument("--type", choices=["all", "diagram", "og-card", "svg", "og"], default="all", help="Media type to generate")
    media_generate_parser.add_argument("--title", default="Autonomous Growth & Marketing Engine", help="Title for media asset")
    media_generate_parser.add_argument("--output", "-o", default=None, help="Output file or directory path")

    scan_parser = subparsers.add_parser(
        "scan", help="Scan workspace environment (repos, harnesses, agents, skills)")
    scan_parser.add_argument("--deep", action="store_true",
                             help="Full source-tree walk: populate state.db + source-map.md")
    scan_parser.add_argument("--status", action="store_true",
                             help="Show source-skeleton cache status")
    scan_parser.add_argument("--refresh", action="store_true",
                             help="Re-run workspace scan on existing workspace")
    scan_parser.add_argument("--add", default=None, dest="add_path", metavar="PATH",
                             help="Add a repo path to the current workspace")
    scan_parser.add_argument("--remove", default=None, dest="remove_path", metavar="PATH",
                             help="Remove a repo path from the current workspace")
    scan_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                             help="Preview changes without writing")
    scan_parser.add_argument("--workspace", default=None, dest="workspace_name",
                             help="Workspace name (default: inferred from parent dir)")
    scan_parser.add_argument("--no-tui", action="store_true",
                             help="Print a text summary instead of the interactive TUI")

    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate project-docs markdown into state.db and .synlynk/project-docs"
    )
    migrate_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                help="Preview migration without writing")
    migrate_parser.add_argument("--recover", action="store_true",
                                help="Re-import from .synlynk/project-docs")
    migrate_parser.add_argument("--setup-dr", action="store_true", dest="setup_dr",
                                help="Configure a DR sync path for mirroring")

    rollback_parser = subparsers.add_parser(
        "rollback", help="Undo the last init/migrate/upgrade if something went wrong"
    )
    rollback_group = rollback_parser.add_mutually_exclusive_group()
    rollback_group.add_argument("--last", action="store_true",
                                help="Roll back the most recent checkpoint (default)")
    rollback_group.add_argument("--op-id", default=None, dest="op_id",
                                help="Roll back a specific archived checkpoint by op-id")
    rollback_group.add_argument("--clear", action="store_true",
                                help="Discard the current checkpoint without restoring")

    probe_parser = subparsers.add_parser(
        "probe", help="Probe harness capability and record compatibility"
    )
    probe_parser.add_argument(
        "--harness", "--agent", default=None, dest="harness",
        help="Probe a single harness instead of all known harnesses (--agent is deprecated, use --harness)",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Run health checks on your synlynk installation")
    doctor_parser.add_argument("--fix", default=None,
                               help="Apply a targeted remediation for the named harness (agy only)")
    doctor_parser.add_argument("--yes", action="store_true",
                               help="Write the proposed remediation without prompting")
    doctor_parser.add_argument("--live-probe", action="store_true",
                               help="Execute live in-sandbox gh-write probe during health checks")

    worktree_parser = subparsers.add_parser(
        "worktree", help="Audit and clean up stale git worktrees/branches"
    )
    worktree_sub = worktree_parser.add_subparsers(dest="worktree_action")
    worktree_audit_parser = worktree_sub.add_parser(
        "audit", help="Report worktree safety classification (read-only)"
    )
    worktree_audit_parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output machine-readable JSON"
    )
    worktree_clean_parser = worktree_sub.add_parser(
        "clean", help="Remove SAFE worktrees/branches (dry-run unless --apply)"
    )
    worktree_clean_parser.add_argument(
        "--apply", action="store_true",
        help="Actually remove SAFE items (default is dry-run)"
    )
    worktree_clean_parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output machine-readable JSON"
    )

    tui_parser = subparsers.add_parser("tui", help="Launch the curses terminal UI")
    tui_parser.set_defaults(
        func=lambda args: __import__("synlynk.tui", fromlist=["main"]).main()
    )

    notify_parser = subparsers.add_parser("notify", help="Run a BYOUX notifier")
    notify_sub = notify_parser.add_subparsers(dest="notify_command")
    slack_parser = notify_sub.add_parser("slack", help="Post uxcore events to a Slack Incoming Webhook")
    slack_parser._synlynk_skip_taxonomy = True
    slack_parser.add_argument("--webhook-url", required=True, help="Slack Incoming Webhook URL")
    slack_parser.set_defaults(
        func=lambda args: __import__(
            "synlynk.notifiers.slack", fromlist=["main"]
        ).main(args.webhook_url)
    )

    exit_parser = subparsers.add_parser(
        "exit", help="Remove synlynk from this repository (reversible via repair)")
    exit_parser.add_argument(
        "--confirm", action="store_true",
        help="Execute removal (default is dry-run)")
    exit_parser.add_argument(
        "--remove-docs", action="store_true", dest="remove_docs",
        help="Also remove project-docs/ directory (destructive)")

    repair_parser = subparsers.add_parser(
        "repair", help="Remove and re-initialize synlynk using current configuration")
    repair_parser.add_argument(
        "--confirm", action="store_true",
        help="Execute repair (default is dry-run)")

    sync_parser = subparsers.add_parser(
        "sync", help="Propagate updated synlynk artifacts without full re-init")
    sync_parser.add_argument(
        "--confirm", action="store_true",
        help="Execute sync (default is dry-run)")
    sync_parser.add_argument(
        "--repair-sops", action="store_true", dest="repair_sops",
        help="Re-inject missing SOP sections into directive files")

    configure_parser = subparsers.add_parser(
        "configure", help="Configure synlynk components")
    configure_sub = configure_parser.add_subparsers(dest="configure_target")
    agent_configure_parser = configure_sub.add_parser(
        "agent", help="Configure a specific agent's harness")
    agent_configure_parser.add_argument("name", help="Agent name (claude, agy, codex, grok)")
    agent_configure_parser.add_argument(
        "--flag", action="append", default=[], metavar="KEY=VAL",
        help="Set a dispatch flag override (repeatable)")
    agent_configure_parser.add_argument(
        "--env", action="append", default=[], metavar="KEY=VAL",
        help="Set an env var override (repeatable)")
    agent_configure_parser.add_argument(
        "--network-dep", action="append", default=[], metavar="HOST:PORT",
        help="Add a required network endpoint (repeatable)")

    identity_parser = subparsers.add_parser("identity", help="Manage synlynk agent identity")
    identity_sub = identity_parser.add_subparsers(dest="identity_action")
    identity_init_parser = identity_sub.add_parser("init", help="Create local Ed25519 identity key")
    identity_init_parser.add_argument(
        "--role",
        default=None,
        help="Provision a GitHub App for a specific role",
    )
    identity_sub.add_parser("list", help="List provisioned role identities")

    events_parser = subparsers.add_parser("events", help="Inspect the GOVERNS event bus")
    events_sub = events_parser.add_subparsers(dest="events_action")
    events_tail_parser = events_sub.add_parser("tail", help="Print recent GOVERNS events, newest first")
    events_tail_parser.add_argument(
        "--type",
        dest="event_type",
        default=None,
        help="Filter to one event type (e.g. job_terminal, review_submitted, pr_merged)",
    )
    events_tail_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of events to show (default 20)",
    )

    session_parser = subparsers.add_parser("session", help="Manage work-envelope sessions")
    session_sub = session_parser.add_subparsers(dest="session_action")
    session_open_parser = session_sub.add_parser("open", help="Open a new session")
    session_open_parser.add_argument("--title", required=True, help="Short description of this session's work")
    session_open_parser.add_argument("--goal", dest="goal_id", default=None, help="Link to an existing goal_id")
    session_sub.add_parser("status", help="Show the active session and its evidence")
    session_sub.add_parser("checkpoint", help="Reconcile jobs/devlog entries since the last checkpoint")
    session_close_parser = session_sub.add_parser("close", help="Close the active session")
    session_close_parser.add_argument(
        "--disposition", required=True,
        choices=["goal_progress", "maintenance", "exploration", "parked", "needs_attribution"],
        help="What this session's work amounted to",
    )
    session_close_parser.add_argument("--summary", default=None, help="One-line closing summary")

    harness_parser = subparsers.add_parser("harness", help="Manage and run autopilot harnesses")
    harness_sub = harness_parser.add_subparsers(dest="harness_action")
    harness_add_parser = harness_sub.add_parser("add", help="Retrofit an on-PATH harness into this project")
    harness_add_parser.add_argument("name", help="Harness binary name on PATH")
    harness_configure_parser = harness_sub.add_parser(
        "configure", help="Interactively write .agents/<name>.json context profile"
    )
    harness_configure_parser.add_argument("name", help="Harness name: claude, agy, codex, grok")
    harness_run_parser = harness_sub.add_parser("run", help="Run a named harness once")
    harness_run_parser.add_argument("name", help="Harness name (matches .agents/<name>.json)")
    harness_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                  help="Collect signals and print findings; no dispatch/issue/PR")
    harness_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron",
                                  help="Install local crontab entry for this harness")
    harness_sub.add_parser("list", help="List .agents/ configs and last run status")

    agent_parser = subparsers.add_parser("agent", help="Manage workspace agents (roles/charters)")
    agent_parser._synlynk_skip_taxonomy = True
    agent_sub = agent_parser.add_subparsers(dest="agent_action")

    agent_init_parser = agent_sub.add_parser("init", help="Create a new workspace agent for a role")
    agent_init_parser.add_argument("role", choices=[
        "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot",
    ], help="Org-chart role for this agent")

    agent_sub.add_parser("list", help="List all registered workspace agents")

    agent_show_parser = agent_sub.add_parser("show", help="Show one agent's details and charter")
    agent_show_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")

    agent_edit_parser = agent_sub.add_parser("edit", help="Propose a new charter revision")
    agent_edit_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")
    agent_edit_parser.add_argument("--charter", required=True,
        help="Path to new charter content, or '-' to read from stdin")

    agent_sync_routing_parser = agent_sub.add_parser(
        "sync-routing", help="Regenerate an agent's dispatch_routing frontmatter from policy.json"
    )
    agent_sync_routing_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")

    agent_disable_parser = agent_sub.add_parser("disable", help="Disable a workspace agent")
    agent_disable_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")

    exec_parser = subparsers.add_parser("exec", help="Execute an AI CLI with synlynk context")
    exec_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute")
    exec_parser.add_argument("--force", action="store_true",
                             help="Bypass CRITICAL sentinel gate")

    watch_parser = subparsers.add_parser("watch", help="Live workspace HUD (synlynk watch)")
    watch_parser.add_argument("--live", action="store_true",
                              help="Active-job stream mode (3s refresh, no sidebar)")

    swarm_parser = subparsers.add_parser("swarm", help="Manage ephemeral swarm runners")
    swarm_sub = swarm_parser.add_subparsers(dest="swarm_action")
    swarm_dispatch = swarm_sub.add_parser("dispatch", help="Provision an ephemeral runner batch")
    swarm_dispatch.add_argument("--driver", choices=("local", "fly"), default="local")
    swarm_dispatch.add_argument("--batch-size", type=int, default=1)
    swarm_dispatch.add_argument("--task", default="true")
    swarm_status = swarm_sub.add_parser("status", help="Show swarm runner status")
    swarm_status.add_argument("--all", action="store_true")
    swarm_destroy = swarm_sub.add_parser("destroy", help="Destroy swarm runners")
    swarm_destroy.add_argument("runner_id", nargs="?")
    swarm_destroy.add_argument("--all", action="store_true")

    daemon_parser = subparsers.add_parser("daemon", help="Manage the always-on context daemon")
    daemon_parser.add_argument(
        "action", nargs="?", choices=["start", "stop", "status", "restart"],
        help="Daemon action"
    )
    daemon_parser.add_argument(
        "--install-service", action="store_true", dest="install_service",
        help="Register daemon with launchd (macOS) / systemd (Linux) / crontab (fallback)"
    )
    daemon_parser.add_argument(
        "--uninstall-service", action="store_true", dest="uninstall_service",
        help="Deregister daemon service"
    )
    daemon_parser.add_argument(
        "--autonomous", action="store_true",
        help="Enable the continuous heal and TPM sweep loop"
    )

    subparsers.add_parser("checkpoint",
                          help="Archive done tasks, refresh context, emit telemetry")

    status_parser = subparsers.add_parser("status", help="Show project state dashboard")
    status_parser.add_argument("--json", action="store_true", dest="json_output",
                               help="Output machine-readable JSON")
    status_parser.add_argument("--platform", action="store_true", dest="platform",
                               help="Show legacy project dashboard instead of ecosystem status")

    ops_parser = subparsers.add_parser(
        "ops",
        help="Cross-repo platform operations report (jobs, costs, LIVE, hygiene)",
    )
    ops_sub = ops_parser.add_subparsers(dest="ops_action")
    ops_report = ops_sub.add_parser(
        "report",
        help="Full-environment ops report for this machine (not single-repo fleet hygiene)",
    )
    ops_report.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Lookback window in hours (default 24)",
    )
    ops_report.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Machine-readable JSON",
    )

    selftest_parser = subparsers.add_parser(
        "selftest",
        help="Exercise every synlynk command (dry by default; --live runs against a real scratch repo)",
    )
    selftest_parser.add_argument(
        "--live", action="store_true",
        help="Run against a real throwaway git repo, including real paid-harness-CLI invocations, capped at $2 total spend",
    )
    selftest_parser.add_argument(
        "--matrix", action="store_true",
        help="Run fleet operability matrix (dry by default; combine with --live for paid cells)",
    )
    selftest_parser.add_argument(
        "--budget", type=float, default=None,
        help="Live matrix budget USD (default 10 when --matrix --live)",
    )
    selftest_parser._synlynk_skip_taxonomy = True

    config_parser = subparsers.add_parser("config", help="Manage synlynk config")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_set_parser = config_sub.add_parser("set", help="Set a config key")
    config_set_parser.add_argument("key")
    config_set_parser.add_argument("value")
    nudges_parser = config_sub.add_parser(
        "nudges", help="Control workspace-agent nudges"
    )
    nudges_parser.add_argument("state", choices=["on", "off", "reset"])

    sentinel_parser = subparsers.add_parser("sentinel",
                                             help="View and manage sentinel alerts")
    sentinel_sub = sentinel_parser.add_subparsers(dest="sentinel_action")
    sentinel_sub.add_parser("list", help="List all active sentinel alerts")
    sentinel_clear_parser = sentinel_sub.add_parser("clear", help="Clear sentinel alerts")
    sentinel_clear_parser.add_argument("--severity",
                                       choices=["CRITICAL", "WARN", "INFO"],
                                       help="Clear only alerts of this severity")
    sentinel_clear_parser.add_argument("--code",
                                       help="Clear only alerts with this code")

    dispatch_parser = subparsers.add_parser(
        "dispatch", help="Dispatch a harness to run a task in the background")
    known_agents = sorted(HARNESS_CAPABILITY_BASELINES)
    dispatch_parser.add_argument("agent",
        nargs="?", default=None,
        choices=known_agents,
        help=f"Harness name: {', '.join(known_agents)}. Optional when --as-agent triggers auto-selection.")
    dispatch_parser.add_argument("--task", required=True,
        help="Task description for the harness")
    dispatch_parser.add_argument("--story", default=None, dest="story_id",
        help="Story/task ID for context labelling")
    dispatch_parser.add_argument("--issue", type=int, default=None,
        help="GitHub issue number to associate this dispatch with (auto-detected from #N in --task if omitted)")
    dispatch_parser.add_argument(
        "--force-harness", "--force-agent", action="store_true", dest="force_agent",
        help="Bypass capability routing — dispatch to the exact harness specified",
    )
    dispatch_parser.add_argument("--static-baseline", action="store_true", dest="static_baseline",
        help="Bypass learned capability-score routing for this dispatch — use the "
             "deterministic static baseline pick instead (Phase 2, #914-adjacent)")
    dispatch_parser.add_argument("--requires-gh-write", action="store_true", dest="requires_gh_write",
        help="Task needs gh write (PR review/merge/comment). Requires a role GitHub App token "
             "(synlynk identity init --role); fails closed if none (#569). "
             "Also hints routing to a GH-capable agent unless --force-agent (#426).")
    dispatch_parser.add_argument("--task-type", default=None, dest="task_type",
                                 help="Classify the dispatch task (for example, review) for task-specific handling")
    dispatch_parser.add_argument("--task-domain", default=None, dest="task_domain",
                                 help="Capability domain used by adaptive EV routing")
    dispatch_parser.add_argument("--criticality", type=float, default=1.0,
                                 help="Task criticality multiplier for adaptive routing")
    dispatch_parser.add_argument(
        "--gh-write-target-kind",
        choices=["issue", "pr"],
        default=None,
        dest="gh_write_target_kind",
        help="Explicitly set the gh-write verification target kind (issue or pr). "
             "If omitted, defaults to 'pr' when --task-type review is set, else 'issue'.",
    )
    dispatch_parser.add_argument(
        "--requires",
        action="append",
        default=[],
        help="Declare a required capability for this dispatch (repeatable, e.g. docker, mcp, gh-write)",
    )
    dispatch_parser.add_argument(
        "--context-mode", choices=["none", "task", "full"], default="task",
        dest="context_mode", help="Context injection mode"
    )
    dispatch_parser.add_argument(
        "--skip-preflight", action="store_true", dest="skip_preflight",
        help="Bypass harness preflight checks"
    )
    dispatch_parser.add_argument(
        "--base", default=None,
        help="Explicit base branch/ref to anchor the job worktree to (overrides auto-stacking)"
    )
    dispatch_parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Print what would be dispatched (task digest, context digest) without creating a job, worktree, or cost entry (see #720)"
    )
    dispatch_parser.add_argument(
        "--grant", action="append", default=[],
        help="Add a permission for this dispatch (repeatable)"
    )
    dispatch_parser.add_argument(
        "--revoke", action="append", default=[],
        help="Remove a permission for this dispatch (repeatable)"
    )
    dispatch_parser.add_argument(
        "--scope-paths", action="append", default=[],
        dest="scope_paths",
        help="Restrict this dispatch to only touching files matching this glob (repeatable, "
             "e.g. --scope-paths 'docs/superpowers/specs/**'). Declaring this denies automatic "
             "PR creation by default unless --requires-gh-write is also set. See #769.",
    )
    dispatch_parser.add_argument(
        "--session",
        dest="session_id",
        default=None,
        help="Override the active session_id for this dispatch (defaults to .synlynk/active_session.json)",
    )
    dispatch_parser.add_argument(
        "--as-agent",
        dest="as_agent",
        default=None,
        help="Dispatch as this workspace agent (ID or role alias). Resolves GitHub identity "
             "and, if the harness positional is omitted, auto-selects a harness by role fit.",
    )
    dispatch_parser.add_argument(
        "--role",
        dest="role",
        default=None,
        help="Explicit role identity for this dispatch (e.g. qa, dev, architect). Required "
             "for --requires-gh-write dispatches that have no --as-agent or role-tagged "
             "--story to resolve a role from (#423, #569).",
    )

    jobs_parser = subparsers.add_parser("jobs", help="List dispatched background jobs")
    jobs_parser.add_argument("--all", action="store_true", dest="all_jobs",
        help="Include completed and failed jobs")
    jobs_parser.add_argument("--summary", metavar="JOB_ID")
    jobs_parser.add_argument("--watch", action="store_true",
        help="Refresh table every 2 seconds until Ctrl-C")
    jobs_parser.add_argument("--stalled", action="store_true",
        help="List jobs awaiting handoff")
    jobs_sub = jobs_parser.add_subparsers(dest="jobs_cmd")
    handoff_p = jobs_sub.add_parser("handoff", help="Transfer a stalled job to another harness")
    handoff_p.add_argument("job_id")
    handoff_p.add_argument("--to-harness", "--to-agent", "--to", dest="to_agent", default=None,
        help="Harness to hand off the stalled job to")
    reap_p = jobs_sub.add_parser(
        "reap",
        help="Reap dead-PID daemon_jobs stuck in status=running (dry-run default; --apply writes)",
    )
    reap_p.add_argument(
        "--apply",
        action="store_true",
        help="Actually mark zombies timed_out (default is dry-run)",
    )
    reap_p.add_argument(
        "--all-projects",
        action="store_true",
        dest="all_projects",
        help="Scan every ~/.synlynk/projects/*/state.db (default: current project only)",
    )

    relay_parser = subparsers.add_parser("relay", help="Relay event broker commands")
    relay_sub = relay_parser.add_subparsers(dest="relay_action")

    relay_start_p = relay_sub.add_parser("start", help="Start relay broker (foreground)")
    relay_start_p.add_argument("--port", type=int, default=7432,
        help="Port to listen on (default: 7432)")
    relay_start_p.add_argument("--daemon", action="store_true", help="Start in the background")

    relay_status_p = relay_sub.add_parser("status", help="Show relay health")
    relay_status_p.add_argument("--relay-url", default=None, dest="relay_url")

    relay_send_p = relay_sub.add_parser("send", help="Send a message to an agent")
    relay_send_p.add_argument("--to-agent", required=True, dest="to_agent")
    relay_send_p.add_argument("--message", required=True)
    relay_send_p.add_argument("--relay-url", default=None, dest="relay_url")

    relay_tail_p = relay_sub.add_parser("tail", help="Stream relay events")
    relay_tail_p.add_argument("--relay-url", default=None, dest="relay_url")

    relay_broadcast_p = relay_sub.add_parser("broadcast", help="Send a broadcast event to the relay")
    relay_broadcast_p.add_argument("body", help="Message body")
    relay_broadcast_p.add_argument("--kind", default="message",
        choices=["motd", "wellness", "message", "joke", "custom"],
        help="Broadcast kind (default: message)")
    relay_broadcast_p.add_argument("--relay-url", default=None, dest="relay_url",
        help="Relay URL (default: http://localhost:27472)")

    logs_parser = subparsers.add_parser("logs", help="Tail the output log of a job")
    logs_parser.add_argument("--job", required=True, dest="job_id",
        help="Job ID (from `synlynk jobs`)")
    logs_parser.add_argument("--tail", type=int, default=50,
        help="Number of lines to show (default: 50)")

    subparsers.add_parser(
        "backfill-capability-ratings",
        help="Resolve/create story_ids for completed jobs missing one and write their capability ratings",
    )

    shell_parser = subparsers.add_parser(
        "shell", help="Spawn a subshell with synlynk context injected")
    shell_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID to label the shell session")

    open_parser = subparsers.add_parser(
        "open", help="Open a harness CLI interactively with pre-loaded context")
    open_parser.add_argument(
        "agent",
        choices=sorted(CORE_FLEET),
        help=(
            f"Agent name: {', '.join(sorted(CORE_FLEET))} "
            "(local is experimental — use dispatch, not open)"
        ),
    )
    open_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")

    launch_parser = subparsers.add_parser(
        "launch", help="Pick your first task and dispatch it (FTUE task picker)")
    launch_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
        help="Print selected tasks without TUI or dispatching")
    launch_parser.add_argument("--list", action="store_true", dest="list_mode",
        help="Print full template pool with trigger conditions")

    run_parser = subparsers.add_parser(
        "run", help="Convenience wrappers for common dispatch patterns")
    run_sub = run_parser.add_subparsers(dest="run_action")
    trio_parser = run_sub.add_parser("--trio",
        help="Dispatch all functional agents in parallel (not the sequential Trio pipeline)")
    trio_parser.add_argument("--task", required=True,
        help="Task description sent to all agents")
    trio_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID for context labelling")

    story_parser = subparsers.add_parser("story", help="Manage stories")
    story_sub = story_parser.add_subparsers(dest="story_action")
    story_create_parser = story_sub.add_parser("create", help="Create a story")
    story_create_parser.add_argument("--title", required=True)
    story_create_parser.add_argument("--engg", default=None, dest="engg_domain")
    story_create_parser.add_argument("--discipline", default=None)
    story_create_parser.add_argument("--org", default=None, dest="org_domain")
    story_create_parser.add_argument("--role", default=None)
    story_create_parser.add_argument("--stage", default=None)
    story_create_parser.add_argument("--phase", default="build")
    story_create_parser.add_argument("--org-tags", nargs="*", default=[],
                                      dest="org_domain_tags",
                                      help="Secondary org domain tags (Tokq discoverability only)")
    story_create_parser.add_argument(
        "--tokens", type=int, default=None, dest="estimated_tokens",
        help="Estimated token budget (set by AI planner)"
    )
    story_create_parser.add_argument(
        "--stack-tags", nargs="*", default=None, dest="stack_tags",
        help="Workspace stack tags; auto-detected when omitted"
    )
    story_sub.add_parser("list", help="List all stories")
    story_ready_parser = story_sub.add_parser("ready", help="Mark a story ready for scheduling")
    story_ready_parser.add_argument("story_id", nargs="?", default=None)
    story_ready_parser.add_argument("--all", action="store_true", dest="all_stories",
                                     help="Mark every draft story ready")
    story_draft_parser = story_sub.add_parser("draft", help="Revert a story to draft")
    story_draft_parser.add_argument("story_id")
    story_done_parser = story_sub.add_parser("done", help="Mark a story done")
    story_done_parser.add_argument("story_id")

    pm_parser = subparsers.add_parser("pm", help="PM agent commands")
    pm_subparsers = pm_parser.add_subparsers(dest="pm_command")
    pm_sweep_parser = pm_subparsers.add_parser(
        "sweep", help="Run one competitive-intelligence sweep pass"
    )
    pm_sweep_parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the composed research prompt without invoking Claude"
    )

    tpm_parser = subparsers.add_parser("tpm", help="TPM sweep commands")
    tpm_subparsers = tpm_parser.add_subparsers(dest="tpm_command")
    sweep_parser = tpm_subparsers.add_parser(
        "sweep", help="Run one autonomous sweep pass over ready stories"
    )
    sweep_parser.add_argument("--assignee", default="nikhilsoman")

    score_parser = subparsers.add_parser("score", help="Manage capability scores")
    score_sub = score_parser.add_subparsers(dest="score_action")
    score_add_parser = score_sub.add_parser("add", help="Add a human quality rating")
    score_add_parser.add_argument("story_id")
    score_add_parser.add_argument("rating", type=float)
    score_add_parser.add_argument("--note", default=None)
    score_add_parser.add_argument("--rework", action="store_true")
    score_list_parser = score_sub.add_parser("list", help="Show capability scores")
    score_list_parser.add_argument("--engg", default=None)
    score_list_parser.add_argument("--org", default=None)
    score_list_parser.add_argument("--industry", default=None)
    charters_parser = subparsers.add_parser("charters", help="Manage living role charters")
    charters_sub = charters_parser.add_subparsers(dest="charters_action")
    charters_adapt_parser = charters_sub.add_parser("adapt", help="Detect empirical charter drift")
    charters_adapt_parser.add_argument("--threshold", type=float, default=0.25)
    charters_adapt_parser.add_argument("--write-proposals", action="store_true",
                                       help="Write reviewable proposal files")
    attest_parser = score_sub.add_parser("attest", help="Retroactively attest model version")
    attest_parser.add_argument("story_id")
    attest_parser.add_argument("--model", required=True)

    cost_parser = subparsers.add_parser("cost", help="Manage the cost ledger")
    cost_sub = cost_parser.add_subparsers(dest="cost_action")
    cost_log_parser = cost_sub.add_parser("log", help="Log a manual cost entry for native/unwrapped sessions")
    cost_log_parser.add_argument("--harness", "--agent", required=True, dest="harness")
    cost_log_parser.add_argument("--tokens-in", type=int, required=True, dest="tokens_in")
    cost_log_parser.add_argument("--tokens-out", type=int, required=True, dest="tokens_out")
    cost_log_parser.add_argument("--story-id", default=None, dest="story_id")
    cost_log_parser.add_argument("--note", default=None)
    cost_true_up_parser = cost_sub.add_parser("true-up", help="Reconcile subscription costs for a month")
    cost_true_up_parser.add_argument("--month", default=None, help="Billing month in YYYY-MM format")
    cost_true_up_parser.add_argument("--harness", default=None)

    roadmap_parser = subparsers.add_parser("roadmap", help="Manage the roadmap")
    roadmap_sub = roadmap_parser.add_subparsers(dest="roadmap_action")
    roadmap_add_parser = roadmap_sub.add_parser("add", help="Add or update a roadmap arc or phase")
    roadmap_add_parser.add_argument("--version", required=True)
    roadmap_add_parser.add_argument("--title", default=None)
    roadmap_add_parser.add_argument("--status", default="planned")
    roadmap_add_parser.add_argument("--target-date", default=None, dest="target_date")
    roadmap_add_parser.add_argument("--notes", default=None)
    roadmap_add_parser.add_argument("--phase-title", default=None, dest="phase_title")
    roadmap_add_parser.add_argument("--priority", default=None)
    roadmap_add_parser.add_argument("--story-id", default=None, dest="story_id")
    roadmap_add_parser.add_argument("--role", default="pm")

    policy_parser = subparsers.add_parser("policy", help="Check policy authority")
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command")
    policy_subparsers.add_parser("show", help="Show the resolved policy")
    policy_check_merge_parser = policy_subparsers.add_parser(
        "check-merge", help="Check merge authority for a role per policy.json"
    )
    policy_check_merge_parser.add_argument(
        "--role", required=True, help="Role identity attempting to merge"
    )
    policy_sync_bp_parser = policy_subparsers.add_parser("sync-branch-protection", help="Configure GitHub branch protection from policy.json")
    policy_sync_bp_parser.add_argument("--dry-run", action="store_true")

    credit_parser = subparsers.add_parser("credit", help="Credit grant ledger commands")
    credit_sub = credit_parser.add_subparsers(dest="credit_action")
    grant_parser = credit_sub.add_parser("grant", help="Record a credit grant for a harness")
    grant_parser.add_argument(
        "--harness", "--agent", required=True, dest="harness",
        help="Harness name (e.g. agy, codex) (--agent is deprecated, use --harness)",
    )
    grant_parser.add_argument("--amount", type=float, required=True, help="Face-value USD amount granted")
    grant_parser.add_argument("--expires", default=None, help="ISO8601 expiry date, optional")
    grant_parser.add_argument("--note", default=None, help="Free-text note")

    backlog_parser = subparsers.add_parser("backlog", help="GOVERNS backlog automation commands")
    backlog_sub = backlog_parser.add_subparsers(dest="backlog_action")
    backlog_capture_parser = backlog_sub.add_parser("capture", help="Stage newly discovered work into backlog")
    backlog_capture_parser.add_argument("--title", required=True, help="Title of discovered work")
    backlog_capture_parser.add_argument("--description", default="", help="Detailed description")
    backlog_capture_parser.add_argument("--role", default="dev", help="Assigned role (dev, qa, pm, etc.)")
    backlog_capture_parser.add_argument("--stage", default="open", help="GOVERNS stage (open, sustain, etc.)")
    backlog_capture_parser.add_argument("--source-type", default="manual", dest="source_type")
    backlog_capture_parser.add_argument("--source-ref", default="", dest="source_ref")
    backlog_capture_parser.add_argument("--priority", type=int, default=5)
    backlog_capture_parser.add_argument("--sync-gh", action="store_true", dest="sync_gh")
    backlog_capture_parser.add_argument("--parent", type=int, default=None, dest="parent_issue")

    backlog_list_parser = backlog_sub.add_parser("list", help="List staged and discovered backlog items")
    backlog_list_parser.add_argument("--stage", default=None, help="Filter by GOVERNS stage")
    backlog_list_parser.add_argument("--unfiled", action="store_true", help="Only show unfiled items (no gh_issue)")

    backlog_sync_parser = backlog_sub.add_parser("sync", help="Synchronize staged backlog items to GitHub issues")
    backlog_sync_parser.add_argument("--dry-run", action="store_true", help="Dry run without creating real issues")
    backlog_sync_parser.add_argument("--parent", type=int, default=None, dest="parent_issue")
    backlog_sync_parser.add_argument("--stage", default=None, help="Filter by GOVERNS stage")

    backlog_ingest_parser = backlog_sub.add_parser("ingest", help="Ingest open GitHub issues into backlog")
    backlog_ingest_parser.add_argument("--sync-github", "--sync-gh", action="store_true", dest="sync_github", help="Sync/link GitHub issues during ingest")
    backlog_ingest_parser.add_argument("--limit", type=int, default=100, help="Maximum issues to fetch")

    backlog_triage_parser = backlog_sub.add_parser("triage", help="Triage staged backlog items into structured stories")
    backlog_triage_parser.add_argument("--auto-promote", action="store_true", dest="auto_promote", help="Auto-promote triaged items to ready stories")

    backlog_autopromote_parser = backlog_sub.add_parser("auto-promote", help="Promote triaged backlog items to ready state.db stories")
    backlog_autopromote_parser.add_argument("--min-tier", type=int, default=1, dest="min_tier", help="Minimum complexity tier to promote")

    quota_parser = subparsers.add_parser(
        "quota",
        help="Show per-harness quota headroom / reset windows (5h, hourly, daily, weekly, monthly)",
    )
    quota_parser.add_argument(
        "--harness", "--agent",
        default=None,
        dest="harness",
        help="Filter to a single harness (claude, agy, codex, grok, local) (--agent is deprecated, use --harness)",
    )
    quota_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON",
    )
    quota_parser.add_argument(
        "--tpm-view",
        action="store_true",
        dest="tpm_view",
        help="Show open reservations across all harnesses (read-only TPM hook view)",
    )

    schedule_parser = subparsers.add_parser(
        "schedule", help="Batch-assign ready stories to agents (dry-run by default)"
    )
    schedule_parser.add_argument("--execute", action="store_true",
                                  help="Enqueue and dispatch the plan instead of a dry run")
    schedule_parser.add_argument("--max-stories", type=int, default=None, dest="max_stories",
                                  help="Cap how many stories to schedule this run")

    pr_parser = subparsers.add_parser("pr", help="PR workflow commands")
    pr_sub = pr_parser.add_subparsers(dest="pr_action")
    pr_sub.add_parser("check", help="Block PR if model versions are unattested")
    pr_sub.add_parser("gate-status", help="qa block-only merge gate (CI matrix + sentinel health)")

    capability_parser = subparsers.add_parser("capability", help="Capability ledger commands")
    capability_sub = capability_parser.add_subparsers(dest="capability_action")
    sweep_parser = capability_sub.add_parser(
        "sweep",
        help="Run a calibration sweep across agents/models to seed the capability baseline",
    )
    sweep_parser.add_argument(
        "--cost-cap",
        type=float,
        default=None,
        dest="cost_cap",
        help="Override the configured cost cap (USD) for this sweep run",
    )

    instructions_parser = subparsers.add_parser(
        "instructions", help="Manage synlynk instruction files across AI tools"
    )
    instructions_sub = instructions_parser.add_subparsers(dest="instructions_action")
    instr_status_parser = instructions_sub.add_parser(
        "status", help="Show status of all tracked instruction files"
    )
    instr_status_parser.add_argument(
        "--pre-commit",
        action="store_true",
        dest="pre_commit",
        help="Fail with exit 1 if drift is detected (for git hooks)",
    )
    instr_diff_parser = instructions_sub.add_parser(
        "diff", help="Show user/tool content outside synlynk sections"
    )
    instr_diff_parser.add_argument("file", nargs="?", default=None,
                                   help="Specific file to diff (default: all)")
    instr_update_parser = instructions_sub.add_parser(
        "update", help="Re-generate synlynk sections and refresh manifest"
    )
    instr_update_parser.add_argument("file", nargs="?", default=None,
                                     help="Specific file to update (default: all)")
    instr_register_parser = instructions_sub.add_parser(
        "register", help="Backfill the manifest from existing synlynk sections"
    )
    instr_register_parser.add_argument("file", nargs="?", default=None,
                                       help="Specific file to register (default: all)")
    instr_ack_parser = instructions_sub.add_parser(
        "ack", help="Acknowledge an INSTRUCTION_DRIFT sentinel event"
    )
    instr_ack_parser.add_argument("file", help="File to acknowledge drift for")

    parser._synlynk_help_parsers = {
        "harness": harness_parser,
        "agent": agent_parser,
        "configure": configure_parser,
        "config": config_parser,
        "daemon": daemon_parser,
        "goal": goal_parser,
        "identity": identity_parser,
        "events": events_parser,
        "session": session_parser,
        "instructions": instructions_parser,
        "local": local_parser,
        "media": media_parser,
        "models": models_parser,
        "relay": relay_parser,
        "run": run_parser,
        "team": team_parser,
        "worktree": worktree_parser,
        "swarm": swarm_parser,
    }

    roles_parser = subparsers.add_parser(
        "roles", help="Show agent role table and directive file fence status")
    roles_parser.add_argument(
        "--fix", action="store_true",
        help="Write missing role fences and repair stale/missing SOP sections in directive files")

    release_parser = subparsers.add_parser('release', help='Cut a named release')
    release_parser.add_argument('--dry-run', action='store_true')
    release_parser.add_argument('--version', help='Explicit version string e.g. 0.11.0')
    release_parser.add_argument('--minor', action='store_true', help='Bump minor instead of patch')
    release_parser.add_argument('--role', default='dev')
    release_parser.add_argument(
        '--check-docs', action='store_true',
        help='Validate README against release metadata without cutting a release')
    release_parser.add_argument(
        '--waive', action='append', default=[],
        help='Skip a waivable README check: check=reason (repeatable)')

    viz_parser = subparsers.add_parser("viz", help="Open local browser workspace dashboard")
    viz_parser.add_argument("--serve", action="store_true",
                            help="Start background server (stable port)")
    viz_parser.add_argument("--generate", action="store_true",
                            help="Generate views without opening browser")
    viz_parser.add_argument("--open", action="store_true",
                            help="Open existing cache in browser")
    viz_parser.add_argument("--stop", action="store_true",
                            help="Stop background server")
    viz_parser.add_argument("--port", type=int, default=None,
                            help="Override port (default: 8721)")

    return parser


def cmd_home(args) -> None:
    """Display or switch the active home harness."""
    from synlynk import _update_config, load_config
    from synlynk.context import detect_active_home_harness, generate_context

    cfg = load_config() if callable(load_config) else {}
    target = getattr(args, "harness", None)

    if target:
        _update_config({"home_harness": target})
        generate_context()
        print(f"  ✓ Home harness switched to: {target}")
        print(f"  ✓ .synlynk/context.md refreshed with {target} as Active Home Conductor")
    else:
        current_cfg = cfg.get("home_harness", "not configured")
        detected = detect_active_home_harness(cfg)
        print("Home Harness Status:")
        print(f"  Configured in .synlynk/config.json : {current_cfg}")
        print(f"  Detected in current session       : {detected}")
        print("  To switch: synlynk home <claude|agy|codex|grok>")


def _warn_deprecated_harness_flag(argv) -> None:
    if "--agent" in argv and "--harness" not in argv:
        print("  warning: --agent is deprecated, use --harness instead", file=sys.stderr)
    if "--force-agent" in argv and "--force-harness" not in argv:
        print("  warning: --force-agent is deprecated, use --force-harness instead", file=sys.stderr)
    if "--to-agent" in argv and "--to-harness" not in argv:
        print("  warning: --to-agent is deprecated, use --to-harness instead", file=sys.stderr)


def main(argv=None) -> None:
    from synlynk.capability_sweep import cmd_capability_sweep
    from synlynk.db import cmd_story_done
    from synlynk.policy_cli import cmd_policy_check_merge, cmd_policy_show, cmd_policy_sync_branch_protection
    from synlynk.charters import cmd_charters_adapt

    from synlynk import (
        HARNESS_CAPABILITY_BASELINES,
        VERSION,
        SynlynkDaemon,
        SynlynkRelay,
        _CYAN,
        _GREEN,
        _RESET,
        _daemon_install_service,
        _daemon_uninstall_service,
        _reconcile_jobs,
        _update_config,
        checkpoint,
        cmd_agent_add,
        cmd_agent_configure,
        cmd_agent_list,
        cmd_agent_run,
        cmd_harness_add,
        cmd_harness_configure,
        cmd_harness_list,
        cmd_harness_run,
        cmd_audit_docs,
        cmd_decide,
        cmd_heal,
        cmd_doctor,
        cmd_exit,
        cmd_identity_init,
        cmd_identity_init_role,
        cmd_identity_list,
        cmd_instructions_ack,
        cmd_instructions_diff,
        cmd_instructions_status,
        cmd_instructions_update,
        cmd_jobs,
        cmd_jobs_handoff,
        cmd_jobs_reap,
        cmd_backfill_capability_ratings,
        cmd_join,
        cmd_launch,
        cmd_launch_ftue,
        cmd_logs,
        cmd_migrate,
        cmd_pr_check,
        cmd_probe,
        cmd_relay_broadcast,
        cmd_relay_start,
        cmd_release,
        cmd_repair,
        cmd_roadmap_add,
        cmd_roles,
        cmd_run_trio,
        cmd_scan,
        cmd_cost_log,
        cmd_quota_tpm_view,
        cmd_score_add,
        cmd_score_attest,
        cmd_score_list,
        cmd_shell,
        cmd_status as cmd_project_status,
        cmd_story_create,
        cmd_story_draft,
        cmd_story_list,
        cmd_story_ready,
        cmd_sync,
        cmd_configure_agent,
        cmd_team_status,
        cmd_watch,
        dispatch_agent,
        exec_command,
        init,
        sentinel_clear,
        sentinel_list,
        upgrade,
        wizard_init,
    )
    from synlynk.events import cmd_events_tail
    from synlynk.status import cmd_status as cmd_ecosystem_status
    from synlynk.viz import cmd_viz
    from synlynk.scheduler import cmd_schedule
    from synlynk.db import cmd_credit_grant
    _reconcile_jobs()
    try:
        from synlynk.capability_watch import spawn_staleness_check_thread
        from synlynk import _get_db, load_config

        _watch_conn = _get_db()
        spawn_staleness_check_thread(_watch_conn, load_config())
    except Exception:
        pass  # staleness checks are best-effort; never block a real command on this
    parser = build_parser()
    args = parser.parse_args(argv)
    cli_tokens = argv if argv is not None else sys.argv[1:]
    help_parsers = getattr(parser, "_synlynk_help_parsers", {})
    _warn_stale_repo_version(VERSION)

    if args.command == "init":
        if getattr(args, "wizard", False):
            wizard_init()
        else:
            agents = [a.strip() for a in args.agents.split(",") if a.strip()]
            if getattr(args, "docs_dir", None):
                # Write docs_dir to config before init() runs so _docs_dir() picks it up
                os.makedirs(".synlynk", exist_ok=True)
                _update_config({"project_docs_dir": args.docs_dir})
            init(force=args.force, agents=agents, mode=args.mode,
                 org=args.org, repo=args.repo, project_id=args.project_id,
                 dry_run=getattr(args, "dry_run", False))
    elif args.command == "exec":
        force = getattr(args, 'force', False)
        sys.exit(exec_command(args.cmd, force=force))
    elif args.command == "upgrade":
        upgrade(dry_run=getattr(args, "dry_run", False))
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "swarm":
        from synlynk.swarm import cmd_swarm_destroy, cmd_swarm_dispatch, cmd_swarm_status
        if args.swarm_action == "dispatch":
            cmd_swarm_dispatch(args)
        elif args.swarm_action == "status":
            cmd_swarm_status(args)
        elif args.swarm_action == "destroy":
            cmd_swarm_destroy(args)
        else:
            swarm_parser.print_help()
    elif args.command == "daemon":
        d = (SynlynkDaemon(autonomous=True) if getattr(args, "autonomous", False)
             else SynlynkDaemon())
        if getattr(args, "install_service", False):
            _daemon_install_service(d)
        elif getattr(args, "uninstall_service", False):
            _daemon_uninstall_service()
        else:
            action = getattr(args, "action", None) or "status"
            if action == "start":
                d.start()
            elif action == "stop":
                d.stop()
            elif action == "status":
                d.status()
            elif action == "restart":
                d.stop()
                d.start()
            else:
                daemon_parser.print_help()
    elif args.command == "checkpoint":
        checkpoint()
    elif args.command == "status":
        if getattr(args, "platform", False):
            cmd_project_status(json_output=args.json_output, platform=True)
        else:
            from synlynk import _get_db
            cmd_ecosystem_status(db_conn=_get_db(), json_output=args.json_output)
    elif args.command == "home":
        cmd_home(args)
    elif args.command == "selftest":
        from synlynk.selftest import cmd_selftest

        sys.exit(
            cmd_selftest(
                live=getattr(args, "live", False),
                matrix=getattr(args, "matrix", False),
                budget=getattr(args, "budget", None),
            )
        )
    elif args.command == "config":
        if getattr(args, "config_action", None) == "set":
            from synlynk import cmd_config_set
            cmd_config_set(args.key, args.value)
        elif getattr(args, "config_action", None) == "nudges":
            from synlynk import _update_config, load_config

            cfg = load_config()
            nudges_cfg = cfg.get(
                "nudges", {"enabled": True, "dismissed_ids": [], "last_shown": {}}
            )
            if args.state == "on":
                nudges_cfg["enabled"] = True
            elif args.state == "off":
                nudges_cfg["enabled"] = False
            elif args.state == "reset":
                nudges_cfg = {"enabled": True, "dismissed_ids": [], "last_shown": {}}
            _update_config({"nudges": nudges_cfg})
            print(f"  ✓ nudges {args.state}")
        else:
            config_parser.print_help()
    elif args.command == "sentinel":
        action = getattr(args, 'sentinel_action', None)
        if action == "clear":
            sentinel_clear(
                severity=getattr(args, 'severity', None),
                code=getattr(args, 'code', None),
            )
        else:
            sentinel_list()  # default: list
    elif args.command == "dispatch":
        _warn_deprecated_harness_flag(cli_tokens)
        known_agents = sorted(HARNESS_CAPABILITY_BASELINES)
        try:
            resolved_agent_id = None
            if getattr(args, "as_agent", None):
                from synlynk import agent_cli
                resolved_agent_id = agent_cli._resolve_or_exit(args.as_agent)
            if not args.agent and not resolved_agent_id:
                dispatch_parser.error("the following arguments are required: agent (unless --as-agent is given)")

            from synlynk.dispatch import _infer_task_type, _task_opens_pr, _task_requires_gh_write
            _effective_requires_gh_write = bool(
                getattr(args, "requires_gh_write", False)
                or _task_requires_gh_write(args.task, getattr(args, "task_type", None))
            )
            _effective_task_type = getattr(args, "task_type", None) or (
                _infer_task_type(args.task) if _effective_requires_gh_write else None
            )
            if _effective_task_type == "review" and not getattr(args, "task_type", None):
                print(
                    "  info: inferred task_type=review from task text "
                    "(pass --task-type explicitly to override)"
                )
            _explicit_gh_write_target_kind = getattr(args, "gh_write_target_kind", None)
            _resolved_gh_write_target_kind = _explicit_gh_write_target_kind or (
                "pr" if _effective_task_type == "review" or _task_opens_pr(args.task) else "issue"
            )

            if getattr(args, "dry_run", False):
                if not args.task or not args.task.strip():
                    raise ValueError(
                        "--task is empty or whitespace-only; refusing to dispatch (see #720)"
                    )
                from synlynk.dispatch import _render_dispatch_preview

                context_mode = getattr(args, "context_mode", "task")
                preview = _render_dispatch_preview(
                    args.agent or (known_agents[0] if not resolved_agent_id else None),
                    args.task, context_mode,
                    agent_id=resolved_agent_id,
                    story_id=getattr(args, "story_id", None),
                    force_agent=getattr(args, "force_agent", False),
                    requires_gh_write=_effective_requires_gh_write,
                    static_baseline=getattr(args, "static_baseline", False),
                    task_type=_effective_task_type,
                )
                print()
                print(f"agent:        {preview['agent']}")
                print(f"task ({preview['task_len']} chars):")
                print(f"  {preview['task']}")
                print(f"task_sha256:  {preview['task_sha256']}")
                print(f"context_mode: {preview['context_mode']}")
                if preview["context_digest"] is not None:
                    print(
                        f"context.md:   sha256={preview['context_digest']}  "
                        f"({preview['context_bytes']:,} bytes)"
                    )
                requires_gh_write = preview["requires_gh_write"]
                print(f"capabilities: requires_gh_write={'true' if requires_gh_write else 'false'}")
                print(f"capabilities: gh_write_target_kind={_resolved_gh_write_target_kind}")
                print()
                print("(dry run — no job, worktree, or cost entry created)")
                return

            job = dispatch_agent(args.agent or known_agents[0], args.task, story_id=args.story_id,
                                 agent_id=resolved_agent_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 static_baseline=getattr(args, "static_baseline", False),
                                 requires_gh_write=_effective_requires_gh_write,
                                 task_type=_effective_task_type,
                                 task_domain=getattr(args, "task_domain", None),
                                 criticality=getattr(args, "criticality", 1.0),
                                 gh_write_target_kind=_resolved_gh_write_target_kind,
                                 requires=getattr(args, "requires", []),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 base=getattr(args, "base", None),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 scope_paths=getattr(args, "scope_paths", []),
                                 session_id=getattr(args, "session_id", None),
                                 role=getattr(args, "role", None))
            if isinstance(job, dict) and job.get("status") == "blocked" and not job.get("pid"):
                print(f"Error: {job.get('reason')}")
                remediation = job.get("remediation")
                if remediation:
                    print(f"  {remediation}")
                sys.exit(1)
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {job.get('agent', args.agent or known_agents[0])} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
            if job.get("fence"):
                from synlynk.fencing import render_task_fence

                print(render_task_fence(job["fence"]))
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "agent":
        from synlynk import agent_cli
        if args.agent_action == "init":
            agent_cli.cmd_agent_init(args.role)
        elif args.agent_action == "list":
            agent_cli.cmd_agent_list()
        elif args.agent_action == "show":
            agent_cli.cmd_agent_show(args.id_or_alias)
        elif args.agent_action == "edit":
            agent_cli.cmd_agent_edit(args.id_or_alias, args.charter)
        elif args.agent_action == "sync-routing":
            agent_cli.cmd_agent_sync_routing(args.id_or_alias)
        elif args.agent_action == "disable":
            agent_cli.cmd_agent_disable(args.id_or_alias)
        else:
            help_parsers.get("agent", parser).print_help()
    elif args.command == "backfill-capability-ratings":
        cmd_backfill_capability_ratings()
    elif args.command == "charters":
        if getattr(args, "charters_action", None) == "adapt":
            cmd_charters_adapt(threshold=args.threshold, dry_run=not args.write_proposals)
        else:
            parser.parse_args(["charters", "--help"])
    elif args.command == "jobs":
        if getattr(args, "jobs_cmd", None) == "handoff":
            _warn_deprecated_harness_flag(cli_tokens)
            cmd_jobs_handoff(args.job_id, to_agent=getattr(args, "to_agent", None))
        elif getattr(args, "jobs_cmd", None) == "reap":
            raise SystemExit(
                cmd_jobs_reap(
                    apply=getattr(args, "apply", False),
                    all_projects=getattr(args, "all_projects", False),
                )
            )
        else:
            cmd_jobs(all_jobs=getattr(args, "all_jobs", False),
                     watch=getattr(args, "watch", False),
                     summary=getattr(args, "summary", None),
                     stalled=getattr(args, "stalled", False))
    elif args.command == "relay":
        action = getattr(args, "relay_action", None)
        if action == "start":
            if getattr(args, "daemon", False):
                from synlynk.relay import RelayServer
                from synlynk.daemon import _daemonize_via_reexec, _daemon_state_path
                _daemonize_via_reexec("synlynk.relay._relay_child_main", _daemon_state_path("relay.log"))
                print(f"relay started in background on port {args.port}")
            else:
                from synlynk.relay import RelayServer
                RelayServer(port=args.port).start(background=False)
        elif action == "status":
            from synlynk.relay import cmd_relay_status
            cmd_relay_status(args)
        elif action == "send":
            from synlynk.relay import cmd_relay_send
            cmd_relay_send(args)
        elif action == "tail":
            from synlynk.relay import cmd_relay_tail
            cmd_relay_tail(args)
        elif action == "broadcast":
            cmd_relay_broadcast(
                kind=getattr(args, "kind", "message"),
                body=args.body,
                relay_url=getattr(args, "relay_url", None),
            )
        else:
            relay_parser.print_help()
    elif args.command == "logs":
        cmd_logs(args.job_id, tail=getattr(args, "tail", 50))
    elif args.command == "shell":
        cmd_shell(story_id=getattr(args, "story_id", None))
    elif args.command == "open":
        cmd_launch(args.agent, story_id=getattr(args, "story_id", None))
    elif args.command == "launch":
        cmd_launch_ftue(
            dry_run=getattr(args, "dry_run", False),
            list_mode=getattr(args, "list_mode", False),
        )
    elif args.command == "run":
        action = getattr(args, "run_action", None)
        if action == "--trio":
            cmd_run_trio(args.task, story_id=getattr(args, "story_id", None))
        else:
            run_parser.print_help()
    elif args.command == "story":
        if args.story_action == "create":
            try:
                cmd_story_create(
                    args.title,
                    args.engg_domain,
                    args.org_domain,
                    args.phase,
                    org_domain_tags=getattr(args, "org_domain_tags", []),
                    estimated_tokens=getattr(args, "estimated_tokens", None),
                    stack_tags=getattr(args, "stack_tags", None),
                    discipline=getattr(args, "discipline", None),
                    role=getattr(args, "role", None),
                    stage=getattr(args, "stage", None),
                )
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.story_action == "list":
            cmd_story_list()
        elif args.story_action == "ready":
            cmd_story_ready(args.story_id, all_stories=getattr(args, "all_stories", False))
        elif args.story_action == "draft":
            cmd_story_draft(args.story_id)
        elif args.story_action == "done":
            cmd_story_done(args.story_id)
    elif args.command == "pm" and args.pm_command == "sweep":
        from synlynk.pm_agent import cmd_pm_sweep

        cmd_pm_sweep(dry_run=args.dry_run)
    elif args.command == "tpm" and args.tpm_command == "sweep":
        from synlynk.tpm_sweep import run_sweep_pass

        summary = run_sweep_pass(assignee=args.assignee)
        print(
            f"sweep pass: {summary['advanced']} advanced, "
            f"{summary['parked']} parked, {summary['failed']} failed"
        )
    elif args.command == "score":
        if args.score_action == "add":
            cmd_score_add(args.story_id, args.rating, note=args.note, rework=args.rework)
        elif args.score_action == "list":
            cmd_score_list(engg=args.engg, org=args.org, industry=args.industry)
        elif args.score_action == "attest":
            cmd_score_attest(args.story_id, args.model)
    elif args.command == "cost":
        if args.cost_action == "log":
            _warn_deprecated_harness_flag(cli_tokens)
            cmd_cost_log(
                args.harness,
                args.tokens_in,
                args.tokens_out,
                story_id=args.story_id,
                note=args.note,
            )
        elif args.cost_action == "true-up":
            from synlynk.costs import cmd_cost_true_up
            cmd_cost_true_up(month=args.month, harness=args.harness)
    elif args.command == "roadmap":
        if args.roadmap_action == "add":
            try:
                cmd_roadmap_add(
                    args.version,
                    title=args.title,
                    status=args.status,
                    target_date=args.target_date,
                    notes=args.notes,
                    phase_title=args.phase_title,
                    priority=args.priority,
                    story_id=args.story_id,
                    role=args.role,
                )
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
    elif args.command == "backlog":
        if args.backlog_action == "capture":
            from synlynk.backlog import stage_discovered_work
            res = stage_discovered_work(
                title=args.title,
                description=args.description,
                role=args.role,
                stage=args.stage,
                source_type=args.source_type,
                source_ref=args.source_ref,
                priority=args.priority,
                sync_gh=args.sync_gh,
                parent_issue=args.parent_issue,
            )
            if res.get("staged"):
                print(f"✓ Staged backlog item {res['story_id']}: '{res['title']}' (stage: {res['stage']}, role: {res['role']})")
                if res.get("gh_issue"):
                    print(f"  GitHub issue #{res['gh_issue']} created")
            else:
                print(f"  ⚠ Did not stage item: {res.get('reason')} (fingerprint: {res.get('fingerprint', '')})")
        elif args.backlog_action == "list":
            from synlynk.backlog import list_staged_backlog
            items = list_staged_backlog(stage=args.stage, unfiled_only=args.unfiled)
            if not items:
                print("No staged backlog items found.")
            else:
                print(f"{'STORY ID':<16} {'STAGE':<10} {'ROLE':<8} {'ISSUE':<8} {'TITLE'}")
                print("─" * 70)
                for it in items:
                    gh = f"#{it['gh_issue']}" if it.get("gh_issue") else "—"
                    print(f"{it['story_id']:<16} {it['stage']:<10} {it['role']:<8} {gh:<8} {it['title']}")
        elif args.backlog_action == "sync":
            from synlynk.backlog import sync_backlog_to_github
            synced = sync_backlog_to_github(dry_run=args.dry_run, parent_issue=args.parent_issue, stage=args.stage)
            if not synced:
                print("No unfiled backlog items to sync.")
            else:
                for it in synced:
                    action = it.get("action", "")
                    if action == "created_issue":
                        print(f"✓ Created issue #{it['gh_issue']} for {it['story_id']}: '{it['title']}'")
                    elif action == "dry_run_sync":
                        print(f"[dry-run] Would create issue for {it['story_id']}: '{it['title']}' (stage: {it['stage']}, role: {it['role']})")
                    else:
                        print(f"✗ Failed to sync {it['story_id']}: '{it['title']}'")
        elif args.backlog_action == "ingest":
            from synlynk.backlog import ingest_backlog
            res = ingest_backlog(
                sync_github=getattr(args, "sync_github", False),
                limit=getattr(args, "limit", 100),
            )
            print(f"✓ Ingested {res['ingested']} backlog items ({res['fetched']} fetched, {res['duplicates']} duplicates skipped).")
        elif args.backlog_action == "triage":
            from synlynk.backlog import triage_backlog
            triaged = triage_backlog(auto_promote=getattr(args, "auto_promote", False))
            if not triaged:
                print("No pending backlog items to triage.")
            else:
                print(f"✓ Triaged {len(triaged)} backlog items:")
                for item in triaged:
                    print(f"  - [{item.get('role', 'dev')}] {item.get('title')} (Tier {item.get('complexity_tier', 2)}, Goal: {item.get('goal_id', 'none')})")
        elif args.backlog_action == "auto-promote":
            from synlynk.backlog import auto_promote_backlog
            promoted = auto_promote_backlog(min_tier=getattr(args, "min_tier", 1))
            if not promoted:
                print("No backlog items eligible for auto-promotion.")
            else:
                print(f"✓ Promoted {len(promoted)} backlog items to ready stories:")
                for story in promoted:
                    print(f"  - {story.get('story_id')}: '{story.get('title')}' (role: {story.get('role')}, stage: {story.get('governs_stage')})")
    elif args.command == "policy" and args.policy_command == "show":
        sys.exit(cmd_policy_show())
    elif args.command == "policy" and args.policy_command == "check-merge":
        sys.exit(cmd_policy_check_merge(role=args.role))
    elif args.command == "policy" and args.policy_command == "sync-branch-protection":
        sys.exit(cmd_policy_sync_branch_protection(dry_run=args.dry_run))
    elif args.command == "credit":
        if args.credit_action == "grant":
            _warn_deprecated_harness_flag(cli_tokens)
            cmd_credit_grant(
                agent=args.harness,
                amount=args.amount,
                expires=args.expires,
                note=args.note,
            )
    elif args.command == "quota":
        if getattr(args, "tpm_view", False):
            cmd_quota_tpm_view()
        else:
            _warn_deprecated_harness_flag(cli_tokens)
            cmd_quota(
                agent=getattr(args, "harness", None),
                json_output=getattr(args, "json_output", False),
            )
    elif args.command == "schedule":
        cmd_schedule(execute=args.execute, max_stories=args.max_stories)
    elif args.command == "pr":
        if args.pr_action == "check":
            cmd_pr_check()
        elif args.pr_action == "gate-status":
            from synlynk.qa_gate import cmd_pr_gate_status
            cmd_pr_gate_status()
    elif args.command == "capability":
        if args.capability_action == "sweep":
            cmd_capability_sweep(cost_cap_override=getattr(args, "cost_cap", None))
    elif args.command == "instructions":
        action = getattr(args, "instructions_action", None)
        if action == "status" or action is None:
            cmd_instructions_status(pre_commit=getattr(args, "pre_commit", False))
        elif action == "diff":
            cmd_instructions_diff(getattr(args, "file", None))
        elif action == "update":
            cmd_instructions_update(getattr(args, "file", None))
        elif action == "register":
            cmd_instructions_register(getattr(args, "file", None))
        elif action == "ack":
            cmd_instructions_ack(args.file)
        else:
            help_parsers.get("instructions", parser).print_help()
    elif args.command == "harness":
        action = getattr(args, "harness_action", None)
        if action == "add":
            cmd_agent_add(args.name)
        elif action == "configure":
            cmd_agent_configure(args.name)
        elif action == "run":
            cmd_agent_run(
                args.name,
                dry_run=getattr(args, "dry_run", False),
                install_cron=getattr(args, "install_cron", False),
            )
        elif action == "list":
            cmd_agent_list()
        else:
            help_parsers.get("harness", parser).print_help()
    elif args.command == "ops":
        from synlynk.platform_ops import cmd_ops_report

        action = getattr(args, "ops_action", None)
        if action == "report" or action is None:
            code = cmd_ops_report(
                hours=getattr(args, "hours", 24) or 24,
                json_output=getattr(args, "json_output", False),
            )
            sys.exit(code)
        else:
            help_parsers.get("ops", parser).print_help()
    elif args.command == "start":
        from synlynk.coldstart import cmd_start
        cmd_start()
    elif args.command == "join":
        cmd_join()
    elif args.command == "team":
        action = getattr(args, "team_action", None)
        if action == "status" or action is None:
            cmd_team_status()
        else:
            help_parsers.get("team", parser).print_help()
    elif args.command == "decide":
        panel_members = [p.strip() for p in args.panel.split(",") if p.strip()]
        cmd_decide(args.topic, panel=panel_members, record=args.record, audit=args.audit)
    elif args.command == "heal":
        cmd_heal(args)
    elif args.command == "audit-docs":
        findings = cmd_audit_docs(json_output=args.json, fix=args.fix)
        if findings and not args.fix:
            sys.exit(1)
    elif args.command == "goal":
        from synlynk.db import cmd_goal_create, cmd_goal_list, cmd_goal_link, cmd_goal_status
        action = getattr(args, "goal_action", None)
        if action == "create":
            cmd_goal_create(args.outcome, args.criterion, deadline=args.deadline, role=args.role)
        elif action == "list":
            cmd_goal_list()
        elif action == "link":
            cmd_goal_link(args.story_id, args.goal_id, secondary=args.secondary)
        elif action == "status" or action is None:
            cmd_goal_status()
        else:
            help_parsers.get("goal", parser).print_help()
    elif args.command == "local":
        from synlynk.local_agent import cmd_local_doctor
        if args.local_action == "doctor":
            sys.exit(cmd_local_doctor())
        else:
            help_parsers.get("local", parser).print_help()
    elif args.command == "models":
        from synlynk.models import cmd_models_discover, cmd_models_list, cmd_models_show
        action = getattr(args, "models_action", None)
        if action == "list":
            cmd_models_list(json_output=args.json_output)
        elif action == "show":
            try:
                cmd_models_show(args.model_id, json_output=args.json_output)
            except ValueError as exc:
                print(f"Error: {exc}")
                sys.exit(1)
        elif action == "discover":
            cmd_models_discover(json_output=args.json_output)
        else:
            help_parsers.get("models", parser).print_help()
    elif args.command == "media":
        from synlynk.media import cmd_media_generate
        action = getattr(args, "media_action", None)
        if action == "generate":
            cmd_media_generate(
                media_type=getattr(args, "type", "all"),
                title=getattr(args, "title", "Autonomous Growth & Marketing Engine"),
                output=getattr(args, "output", None),
            )
        else:
            help_parsers.get("media", parser).print_help()
    elif args.command == "scan":
        cmd_scan(
            deep=getattr(args, "deep", False),
            status=getattr(args, "status", False),
            refresh=getattr(args, "refresh", False),
            add_path=getattr(args, "add_path", None),
            remove_path=getattr(args, "remove_path", None),
            dry_run=getattr(args, "dry_run", False),
            workspace_name=getattr(args, "workspace_name", None),
            no_tui=getattr(args, "no_tui", False),
        )
    elif args.command == "migrate":
        cmd_migrate(
            dry_run=getattr(args, "dry_run", False),
            recover=getattr(args, "recover", False),
            setup_dr=getattr(args, "setup_dr", False),
        )
    elif args.command == "rollback":
        from synlynk.rollback import cmd_rollback
        cmd_rollback(
            last=getattr(args, "last", False) or not (getattr(args, "op_id", None) or getattr(args, "clear", False)),
            op_id=getattr(args, "op_id", None),
            clear=getattr(args, "clear", False),
        )
    elif args.command == "probe":
        _warn_deprecated_harness_flag(cli_tokens)
        cmd_probe(agent=getattr(args, "harness", None))
    elif args.command == "doctor":
        sys.exit(cmd_doctor(args))
    elif args.command == "worktree":
        from synlynk.worktree import cmd_worktree_audit, cmd_worktree_clean
        action = getattr(args, "worktree_action", None)
        if action == "audit":
            cmd_worktree_audit(json_output=args.json_output)
        elif action == "clean":
            cmd_worktree_clean(apply=args.apply, json_output=args.json_output)
        else:
            help_parsers.get("worktree", parser).print_help()
    elif args.command == "notify":
        if getattr(args, "notify_command", None) == "slack":
            args.func(args)
        else:
            notify_parser.print_help()
    elif args.command == "roles":
        cmd_roles(fix=getattr(args, "fix", False))
    elif args.command == "release":
        cmd_release(
            dry_run=getattr(args, "dry_run", False),
            version=getattr(args, "version", None),
            minor=getattr(args, "minor", False),
            role=getattr(args, "role", "dev"),
            check_docs=getattr(args, "check_docs", False),
            waive=getattr(args, "waive", None),
        )
    elif args.command == "viz":
        cmd_viz(args)
    elif args.command == "exit":
        sys.exit(cmd_exit(dry_run=not args.confirm, remove_docs=args.remove_docs))
    elif args.command == "repair":
        sys.exit(cmd_repair(dry_run=not args.confirm))
    elif args.command == "sync":
        sys.exit(cmd_sync(dry_run=not args.confirm, repair_sops=getattr(args, "repair_sops", False)))
    elif args.command == "configure":
        if getattr(args, "configure_target", None) == "agent":
            flags = {}
            for item in args.flag or []:
                key, sep, val = item.partition("=")
                flags[key] = val if sep else True
            envs = dict(item.split("=", 1) for item in args.env) if args.env else {}
            cmd_configure_agent(args.name, flags=flags, envs=envs, network_deps=args.network_dep)
        else:
            help_parsers.get("configure", parser).print_help()
    elif args.command == "identity":
        action = getattr(args, "identity_action", None)
        if action == "init" or action is None:
            role = getattr(args, "role", None)
            if role:
                cmd_identity_init_role(role)
            else:
                cmd_identity_init()
        elif action == "list":
            cmd_identity_list()
        else:
            help_parsers.get("identity", parser).print_help()
    elif args.command == "events":
        action = getattr(args, "events_action", None)
        if action == "tail":
            cmd_events_tail(event_type=args.event_type, limit=args.limit)
        else:
            help_parsers.get("events", parser).print_help()
    elif args.command == "session":
        action = getattr(args, "session_action", None)
        from synlynk.db import (
            cmd_session_open, cmd_session_status, cmd_session_checkpoint, cmd_session_close,
        )
        if action == "open":
            cmd_session_open(args.title, goal_id=args.goal_id)
        elif action == "status":
            cmd_session_status()
        elif action == "checkpoint":
            cmd_session_checkpoint()
        elif action == "close":
            cmd_session_close(disposition=args.disposition, summary=args.summary)
        else:
            help_parsers.get("session", parser).print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
