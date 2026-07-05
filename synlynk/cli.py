import argparse
import os
import sys

_SYNLYNK_DIR = ".synlynk"

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
    selected_cycle_idx = CYCLES.index("work")
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

def main() -> None:
    from synlynk import (
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
        cmd_agent_configure,
        cmd_agent_list,
        cmd_agent_run,
        cmd_decide,
        cmd_doctor,
        cmd_exit,
        cmd_identity_init,
        cmd_instructions_ack,
        cmd_instructions_diff,
        cmd_instructions_status,
        cmd_instructions_update,
        cmd_jobs,
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
        cmd_score_add,
        cmd_score_attest,
        cmd_score_list,
        cmd_shell,
        cmd_status as cmd_project_status,
        cmd_story_create,
        cmd_story_list,
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
    from synlynk.status import cmd_status as cmd_ecosystem_status
    from synlynk.viz import cmd_viz
    _reconcile_jobs()
    parser = argparse.ArgumentParser(
        description="synlynk: The Universal Context Switchboard for AI Devs"
    )
    parser.add_argument("--version", action="version", version=f"synlynk {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize synlynk in a repository")
    init_parser.add_argument("--force", action="store_true",
                             help="Overwrite existing template files")
    init_parser.add_argument("--agents", default="claude,agy,codex,grok",
                             help="Comma-separated agent set to generate files for (claude,agy,codex,grok)")
    init_parser.add_argument("--mode", choices=["solo", "team"], default="solo",
                             help="Project mode written to project-docs/.synlynk_config.json")
    init_parser.add_argument("--org", default=None,
                             help="GitHub organization name (stored in .synlynk/config.json)")
    init_parser.add_argument("--repo", default=None,
                             help="GitHub repository name (stored in .synlynk/config.json)")
    init_parser.add_argument("--project-id", default=None, dest="project_id",
                             help="GitHub Projects v2 node ID (fills TODO: PROJECT_ID in agent files)")
    init_parser.add_argument("--docs-dir", default=None, dest="docs_dir",
                             help="Directory for project docs (default: project-docs). "
                                  "Use '.' for repos that keep docs at the repo root.")
    init_parser.add_argument("--wizard", action="store_true",
                             help="Run the FTUE guided setup wizard")

    subparsers.add_parser("upgrade", help="Check for and apply updates")

    subparsers.add_parser("join", help="Onboard as a new member to an existing project")

    team_parser = subparsers.add_parser("team", help="Team status and management")
    team_sub = team_parser.add_subparsers(dest="team_action")
    team_sub.add_parser("status", help="Show team digest: members, stories, budget")

    decide_parser = subparsers.add_parser(
        "decide", help="Convene a multi-agent panel and optionally record a Decision"
    )
    decide_parser.add_argument("topic", help="Decision topic (quoted string)")
    decide_parser.add_argument(
        "--panel", required=True,
        help="Comma-separated agent names, e.g. claude,agy,codex"
    )
    decide_parser.add_argument(
        "--record", action="store_true",
        help="Write the Decision record to project-docs/decisions/"
    )

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

    probe_parser = subparsers.add_parser(
        "probe", help="Probe agent harness capability and record compatibility"
    )
    probe_parser.add_argument("--agent", default=None,
                              help="Probe a single agent instead of all known agents")

    subparsers.add_parser("doctor", help="Run health checks on your synlynk installation")

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
    identity_sub.add_parser("init", help="Create local Ed25519 identity key")

    agent_parser = subparsers.add_parser("agent", help="Manage and run autopilot agents")
    agent_sub = agent_parser.add_subparsers(dest="agent_action")
    agent_configure_parser = agent_sub.add_parser(
        "configure", help="Interactively write .agents/<name>.json context profile"
    )
    agent_configure_parser.add_argument("name", help="Agent name: claude, agy, codex, grok")
    agent_run_parser = agent_sub.add_parser("run", help="Run a named agent once")
    agent_run_parser.add_argument("name", help="Agent name (matches .agents/<name>.json)")
    agent_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                  help="Collect signals and print findings; no dispatch/issue/PR")
    agent_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron",
                                  help="Install local crontab entry for this agent")
    agent_sub.add_parser("list", help="List .agents/ configs and last run status")

    exec_parser = subparsers.add_parser("exec", help="Execute an AI CLI with synlynk context")
    exec_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute")
    exec_parser.add_argument("--force", action="store_true",
                             help="Bypass CRITICAL sentinel gate")

    watch_parser = subparsers.add_parser("watch", help="Live workspace HUD (synlynk watch)")
    watch_parser.add_argument("--live", action="store_true",
                              help="Active-job stream mode (3s refresh, no sidebar)")

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

    subparsers.add_parser("checkpoint",
                          help="Archive done tasks, refresh context, emit telemetry")

    status_parser = subparsers.add_parser("status", help="Show project state dashboard")
    status_parser.add_argument("--json", action="store_true", dest="json_output",
                               help="Output machine-readable JSON")
    status_parser.add_argument("--platform", action="store_true", dest="platform",
                               help="Show legacy project dashboard instead of ecosystem status")

    config_parser = subparsers.add_parser("config", help="Manage synlynk config")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_set_parser = config_sub.add_parser("set", help="Set a config key")
    config_set_parser.add_argument("key")
    config_set_parser.add_argument("value")

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
        "dispatch", help="Dispatch an agent to run a task in the background")
    dispatch_parser.add_argument("agent",
        help="Agent name: claude, agy, codex")
    dispatch_parser.add_argument("--task", required=True,
        help="Task description for the agent")
    dispatch_parser.add_argument("--story", default=None, dest="story_id",
        help="Story/task ID for context labelling")
    dispatch_parser.add_argument("--force-agent", action="store_true", dest="force_agent",
        help="Bypass capability routing — dispatch to the exact agent specified")
    dispatch_parser.add_argument(
        "--context-mode", choices=["none", "task", "full"], default="task",
        dest="context_mode", help="Context injection mode"
    )
    dispatch_parser.add_argument(
        "--skip-preflight", action="store_true", dest="skip_preflight",
        help="Bypass harness preflight checks"
    )

    jobs_parser = subparsers.add_parser("jobs", help="List dispatched background jobs")
    jobs_parser.add_argument("--all", action="store_true", dest="all_jobs",
        help="Include completed and failed jobs")
    jobs_parser.add_argument("--summary", metavar="JOB_ID")
    jobs_parser.add_argument("--watch", action="store_true",
        help="Refresh table every 2 seconds until Ctrl-C")

    relay_parser = subparsers.add_parser("relay", help="Relay event broker commands")
    relay_sub = relay_parser.add_subparsers(dest="relay_action")

    relay_start_p = relay_sub.add_parser("start", help="Start relay broker (foreground)")
    relay_start_p.add_argument("--port", type=int, default=None,
        help=f"Port to listen on (default: {SynlynkRelay.RELAY_PORT})")

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

    shell_parser = subparsers.add_parser(
        "shell", help="Spawn a subshell with synlynk context injected")
    shell_parser.add_argument("--story", default=None, dest="story_id",
        help="Story ID to label the shell session")

    open_parser = subparsers.add_parser(
        "open", help="Open an agent CLI interactively with pre-loaded context")
    open_parser.add_argument("agent", help="Agent name: claude, agy, codex, grok")
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
    story_create_parser.add_argument("--engg", default="unknown", dest="engg_domain")
    story_create_parser.add_argument("--org", default="unknown", dest="org_domain")
    story_create_parser.add_argument("--phase", default="build")
    story_create_parser.add_argument("--org-tags", nargs="*", default=[],
                                      dest="org_domain_tags",
                                      help="Secondary org domain tags (Tokq discoverability only)")
    story_create_parser.add_argument(
        "--tokens", type=int, default=None, dest="estimated_tokens",
        help="Estimated token budget (set by AI planner)"
    )
    story_sub.add_parser("list", help="List all stories")

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
    attest_parser = score_sub.add_parser("attest", help="Retroactively attest model version")
    attest_parser.add_argument("story_id")
    attest_parser.add_argument("--model", required=True)

    pr_parser = subparsers.add_parser("pr", help="PR workflow commands")
    pr_sub = pr_parser.add_subparsers(dest="pr_action")
    pr_sub.add_parser("check", help="Block PR if model versions are unattested")

    instructions_parser = subparsers.add_parser(
        "instructions", help="Manage synlynk instruction files across AI tools"
    )
    instructions_sub = instructions_parser.add_subparsers(dest="instructions_action")
    instructions_sub.add_parser("status", help="Show status of all tracked instruction files")
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
    instr_ack_parser = instructions_sub.add_parser(
        "ack", help="Acknowledge an INSTRUCTION_DRIFT sentinel event"
    )
    instr_ack_parser.add_argument("file", help="File to acknowledge drift for")

    roles_parser = subparsers.add_parser(
        "roles", help="Show agent role table and directive file fence status")
    roles_parser.add_argument(
        "--fix", action="store_true",
        help="Write missing role fences into agent directive files")

    release_parser = subparsers.add_parser('release', help='Cut a named release')
    release_parser.add_argument('--dry-run', action='store_true')
    release_parser.add_argument('--version', help='Explicit version string e.g. 0.11.0')
    release_parser.add_argument('--minor', action='store_true', help='Bump minor instead of patch')

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

    args = parser.parse_args()

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
                 org=args.org, repo=args.repo, project_id=args.project_id)
    elif args.command == "exec":
        force = getattr(args, 'force', False)
        sys.exit(exec_command(args.cmd, force=force))
    elif args.command == "upgrade":
        upgrade()
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "daemon":
        d = SynlynkDaemon()
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
    elif args.command == "config":
        if getattr(args, "config_action", None) == "set":
            from synlynk import cmd_config_set
            cmd_config_set(args.key, args.value)
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
        try:
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False))
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {args.agent} dispatched  PID {job['pid']}")
            print(f"  Log:  {_CYAN}synlynk logs --job {job['id']}{_RESET}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "jobs":
        cmd_jobs(all_jobs=getattr(args, "all_jobs", False),
                 watch=getattr(args, "watch", False),
                 summary=getattr(args, "summary", None))
    elif args.command == "relay":
        action = getattr(args, "relay_action", None)
        if action == "start":
            cmd_relay_start(port=getattr(args, "port", None))
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
            cmd_story_create(args.title, args.engg_domain, args.org_domain, args.phase,
                             org_domain_tags=getattr(args, "org_domain_tags", []),
                             estimated_tokens=getattr(args, "estimated_tokens", None))
        elif args.story_action == "list":
            cmd_story_list()
    elif args.command == "score":
        if args.score_action == "add":
            cmd_score_add(args.story_id, args.rating, note=args.note, rework=args.rework)
        elif args.score_action == "list":
            cmd_score_list(engg=args.engg, org=args.org, industry=args.industry)
        elif args.score_action == "attest":
            cmd_score_attest(args.story_id, args.model)
    elif args.command == "pr":
        if args.pr_action == "check":
            cmd_pr_check()
    elif args.command == "instructions":
        action = getattr(args, "instructions_action", None)
        if action == "status" or action is None:
            cmd_instructions_status()
        elif action == "diff":
            cmd_instructions_diff(getattr(args, "file", None))
        elif action == "update":
            cmd_instructions_update(getattr(args, "file", None))
        elif action == "ack":
            cmd_instructions_ack(args.file)
        else:
            instructions_parser.print_help()
    elif args.command == "agent":
        action = getattr(args, "agent_action", None)
        if action == "configure":
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
            agent_parser.print_help()
    elif args.command == "join":
        cmd_join()
    elif args.command == "team":
        action = getattr(args, "team_action", None)
        if action == "status" or action is None:
            cmd_team_status()
        else:
            team_parser.print_help()
    elif args.command == "decide":
        panel_members = [p.strip() for p in args.panel.split(",") if p.strip()]
        cmd_decide(args.topic, panel=panel_members, record=args.record)
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
    elif args.command == "probe":
        cmd_probe(agent=getattr(args, "agent", None))
    elif args.command == "doctor":
        sys.exit(cmd_doctor())
    elif args.command == "roles":
        cmd_roles(fix=getattr(args, "fix", False))
    elif args.command == "release":
        cmd_release(
            dry_run=getattr(args, "dry_run", False),
            version=getattr(args, "version", None),
            minor=getattr(args, "minor", False),
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
            flags = dict(item.split("=", 1) for item in args.flag) if args.flag else {}
            envs = dict(item.split("=", 1) for item in args.env) if args.env else {}
            cmd_configure_agent(args.name, flags=flags, envs=envs, network_deps=args.network_dep)
        else:
            configure_parser.print_help()
    elif args.command == "identity":
        action = getattr(args, "identity_action", None)
        if action == "init" or action is None:
            cmd_identity_init()
        else:
            identity_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
