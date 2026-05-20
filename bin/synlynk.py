#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import time
import json
import re
import urllib.request
from typing import Optional

VERSION = "0.2.0"


def get_username() -> str:
    """Resolves current user's GitHub login via gh CLI, falling back to git config."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True
        )
        login = result.stdout.strip()
        if login and result.returncode == 0:
            return login
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True
        )
        name = result.stdout.strip()
        return name.lower().replace(" ", "") if name else "unknown"
    except Exception:
        return "unknown"


def get_mode() -> str:
    """Returns 'single' or 'team' from project-docs/.synlynk_config.json."""
    config_path = "project-docs/.synlynk_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                return json.load(f).get("mode", "single")
        except (json.JSONDecodeError, IOError):
            pass
    return "single"


def load_config() -> dict:
    """Loads .synlynk/config.json with schema-v1 defaults."""
    defaults = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "watch_interval_seconds": 30,
        "org": None,
        "team": None,
        "sync_endpoint": None,
    }
    config_file = ".synlynk/config.json"
    if not os.path.exists(config_file):
        return defaults
    try:
        with open(config_file) as f:
            config = json.load(f)
        for key, val in defaults.items():
            if key not in config:
                config[key] = val
        for key, val in defaults["budget"].items():
            if key not in config.get("budget", {}):
                config.setdefault("budget", {})[key] = val
        return config
    except (json.JSONDecodeError, IOError):
        return defaults


def parse_costs_md() -> tuple:
    """Returns (total_usd, total_requests) by parsing costs.md column 6."""
    costs_file = "project-docs/costs.md"
    total_usd = 0.0
    total_requests = 0
    if not os.path.exists(costs_file):
        return total_usd, total_requests
    with open(costs_file) as f:
        for line in f:
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 8:
                continue
            cost_str = parts[5].lstrip("$")
            try:
                total_usd += float(cost_str)
                total_requests += 1
            except ValueError:
                continue
    return total_usd, total_requests

def set_state(state: str) -> None:
    """Writes synlynk state to .synlynk/state and updates terminal title."""
    icons = {"watching": "●", "active": "⚡", "stopped": "○"}
    state_file = ".synlynk/state"
    if not os.path.exists(".synlynk"):
        return
    with open(state_file, "w") as f:
        f.write(state)
    if sys.stdout.isatty():
        project = os.path.basename(os.getcwd())
        title = f"{icons.get(state, '○')} synlynk: {state}  ·  {project}"
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()

_SESSION_PROTOCOL = """\
## Session Start (every session, no exceptions)
1. Run: `git config user.name` — this is your @username for all attribution
2. Run: `synlynk watch status` — if stopped, run `synlynk watch start`
3. Read: `.synlynk/context.md` — your full project state snapshot
4. Check `.synlynk/sentinel.md` for any active alerts
5. Greet with 3 rows:
   - Row 1: Last task YOU completed [by @username] — from your devlog entry
   - Row 2: Your next active task — from project-docs/todo.md
   - Row 3 (team mode only): Last 1 entry per teammate from project-docs/devlogs/

## During the session
- Mark tasks `[x]` in project-docs/todo.md when complete — do NOT delete them
- Append decisions to project-docs/memory.md with [@username] attribution
- Run `synlynk checkpoint` at every task boundary
- In team mode: always `git pull` before editing any project-docs file
- Log costs in project-docs/costs.md after each significant AI operation

## At session end
- Append a summary entry to project-docs/devlogs/<username>.md
- Run `synlynk checkpoint` one final time
- Run `synlynk status` and include the output in your closing message
"""

TEMPLATES = {
    "roadmap.md": (
        "# synlynk Roadmap\n\n"
        "| Priority | Feature | Description | Status | Target Release | Owner |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| P0 | Project Setup | Initialize synlynk and project-docs. | In Progress | v0.1.0 | [Unassigned] |\n"
    ),
    "todo.md": (
        "# Project Todo List\n## Active Tasks\n"
        "- [ ] Initialize repository with synlynk <!-- id: 0 -->\n"
    ),
    "memory.md": (
        "# synlynk Memory\n\n## Decisions\n"
        "- **Structure:** Uses `/project-docs` for core records.\n\n"
        "## Conventions\n- **Session Protocol:** Use synlynk project-docs for context.\n"
    ),
    "costs.md": (
        "# synlynk Costs\n\n"
        "| Date | Type | Task/Command | Tokens (I/O) | Requests | Cost (USD) | Notes |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    ),
    "GEMINI.md": f"# synlynk Gemini Instructions\n\n{_SESSION_PROTOCOL}",
    "CLAUDE.md": f"# synlynk Claude Instructions\n\n{_SESSION_PROTOCOL}",
    "AI_INSTRUCTIONS.md": (
        "# synlynk Universal AI Instructions\n\n"
        "Apply the following as your system prompt or custom instructions "
        "before starting any session in this repository.\n\n"
        f"{_SESSION_PROTOCOL}"
    ),
    ".cursorrules": (
        "Read .synlynk/context.md at session start. "
        "Mark tasks [x] in project-docs/todo.md when done. "
        "Run `synlynk checkpoint` at task boundaries. "
        "Attribute all project-docs edits with [@username]."
    ),
    "config.json": json.dumps({
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "watch_interval_seconds": 30,
        "org": None,
        "team": None,
        "sync_endpoint": None,
    }, indent=2),
}

def log_telemetry_event(event: dict) -> None:
    """Appends a structured event to .synlynk/telemetry.json (capped at 100)."""
    telemetry_file = ".synlynk/telemetry.json"
    if not os.path.exists(".synlynk"):
        return
    data = []
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    data.append(event)
    data = data[-100:]
    with open(telemetry_file, "w") as f:
        json.dump(data, f, indent=2)


def _check_costs_freshness() -> None:
    """Warns if costs.md hasn't been updated in the current session (>1 hour)."""
    costs_file = "project-docs/costs.md"
    if not os.path.exists(costs_file):
        return
    if time.time() - os.path.getmtime(costs_file) > 3600:
        print("  ⚠ costs.md not updated this session — AI may have missed logging")

def check_flatline() -> None:
    """Detects 3 consecutive failures of the same command; injects alert into sentinel.md."""
    telemetry_file = ".synlynk/telemetry.json"
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(telemetry_file):
        return
    try:
        with open(telemetry_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    if len(data) < 3:
        return
    last_three = data[-3:]
    if not (all(e.get('exit_code', 0) != 0 for e in last_three) and
            all(e.get('command') == last_three[0].get('command') for e in last_three)):
        return
    cmd = last_three[0].get('command', 'unknown')
    user = get_username()
    alert = f"- [{time.strftime('%Y-%m-%d %H:%M')}] FLATLINE: `{cmd}` failed 3x in a row [@{user}]\n"
    print(f"\n⚠️  [Flatline Sentinel] Alert: 3 consecutive failures of '{cmd}'.")
    print("   Possible hallucination loop — consider manual intervention.")
    if not os.path.exists(".synlynk"):
        return
    existing = ""
    if os.path.exists(sentinel_file):
        with open(sentinel_file) as f:
            existing = f.read()
    if "# Sentinel Alerts" not in existing:
        existing = "# Sentinel Alerts\n"
    with open(sentinel_file, "w") as f:
        f.write(existing + alert)

def check_budgets() -> None:
    """Warns if cumulative spend from costs.md approaches config limits."""
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    limit_reqs = config["budget"]["limit_requests"]
    total_usd, _ = parse_costs_md()

    # Request count from telemetry exec events
    total_reqs = 0
    telemetry_file = ".synlynk/telemetry.json"
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
            total_reqs = sum(1 for e in data if e.get("type") == "exec")
        except (json.JSONDecodeError, IOError):
            pass

    if total_usd >= limit_usd:
        print(f"\n🛑 [Budget Alert] CRITICAL: Spent ${total_usd:.2f} / ${limit_usd:.2f}.")
    elif total_usd >= limit_usd * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of cost budget (${total_usd:.2f} / ${limit_usd:.2f}).")

    if total_reqs >= limit_reqs:
        print(f"\n🛑 [Budget Alert] CRITICAL: {total_reqs} / {limit_reqs} request limit.")
    elif total_reqs >= limit_reqs * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of request limit ({total_reqs} / {limit_reqs}).")

def _get_last_devlog_date(filepath: str) -> Optional[str]:
    """Returns the most recent ## YYYY-MM-DD heading from a devlog file."""
    if not os.path.exists(filepath):
        return None
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    last_date = None
    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                last_date = m.group(1)
    return last_date


def _write_recent_devlog_entries(out, filepath: str, cutoff: float) -> None:
    """Writes devlog ## sections newer than cutoff timestamp to out."""
    import calendar
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    current_lines = []
    in_section = False
    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                if in_section and current_lines:
                    out.writelines(current_lines)
                try:
                    ts = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%d"))
                    in_section = ts >= cutoff
                except ValueError:
                    in_section = False
                current_lines = [line]
            elif in_section:
                current_lines.append(line)
    if in_section and current_lines:
        out.writelines(current_lines)


def _write_last_devlog_section(out, filepath: str) -> None:
    """Writes only the last ## section from a devlog file."""
    if not os.path.exists(filepath):
        return
    pattern = re.compile(r'^## \d{4}-\d{2}-\d{2}')
    sections = []
    current = []
    with open(filepath) as f:
        for line in f:
            if pattern.match(line) and current:
                sections.append(current)
                current = [line]
            else:
                current.append(line)
    if current:
        sections.append(current)
    if sections:
        out.writelines(sections[-1])


def generate_context(scope: str = "full") -> None:
    """Aggregates project-docs into .synlynk/context.md (active items only)."""
    docs_dir = "project-docs"
    context_file = ".synlynk/context.md"
    sentinel_file = ".synlynk/sentinel.md"

    if not os.path.exists(docs_dir):
        return

    if scope != "full":
        # TODO(v1.3.0): implement task-scoped context slices for sub-agent routing
        print(f"  ⚠ scope='{scope}' not yet implemented, falling back to full context")
        scope = "full"

    if not os.path.exists(".synlynk"):
        os.makedirs(".synlynk")

    username = get_username()
    mode = get_mode()

    with open(context_file, "w") as out:
        out.write("# synlynk Context Snapshot\n\n")
        out.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} | User: @{username} | Mode: {mode}\n\n")

        # Sentinel alerts at top (omit section if empty)
        if os.path.exists(sentinel_file):
            content = open(sentinel_file).read().strip()
            lines = [l for l in content.splitlines() if l.startswith("- [")]
            if lines:
                out.write("# Sentinel Alerts\n")
                out.write("\n".join(lines) + "\n\n---\n\n")

        # Active tasks only ([ ] lines)
        todo_path = os.path.join(docs_dir, "todo.md")
        if os.path.exists(todo_path):
            out.write("## Active Tasks\n")
            with open(todo_path) as f:
                for line in f:
                    if "- [ ]" in line:
                        out.write(line)
            out.write("\n---\n\n")

        # Roadmap: header rows + In Progress rows only
        roadmap_path = os.path.join(docs_dir, "roadmap.md")
        if os.path.exists(roadmap_path):
            out.write("## Roadmap (active)\n")
            with open(roadmap_path) as f:
                for line in f:
                    if (line.startswith("| Priority") or "| :---" in line or
                            "In Progress" in line):
                        out.write(line)
            out.write("\n---\n\n")

        # Memory (decisions) — full, it's already curated
        memory_path = os.path.join(docs_dir, "memory.md")
        if os.path.exists(memory_path):
            out.write("## Decisions\n")
            out.write(open(memory_path).read())
            out.write("\n---\n\n")

        # Recent devlog (last 7 days)
        cutoff = time.time() - (7 * 24 * 3600)
        devlog_path = os.path.join(docs_dir, "devlogs", f"{username}.md")
        if os.path.exists(devlog_path):
            out.write(f"## Recent Devlog (@{username})\n")
            _write_recent_devlog_entries(out, devlog_path, cutoff)
            out.write("\n---\n\n")

        # Teammates (team mode): last 1 entry per teammate devlog
        if mode == "team":
            devlogs_dir = os.path.join(docs_dir, "devlogs")
            if os.path.exists(devlogs_dir):
                for fname in sorted(os.listdir(devlogs_dir)):
                    if (fname.endswith(".md") and
                            fname not in (f"{username}.md", "README.md")):
                        out.write(f"## Teammate Activity (@{fname[:-3]})\n")
                        _write_last_devlog_section(out, os.path.join(devlogs_dir, fname))
                        out.write("\n---\n\n")

    print(f"  ✓ Context saved to {context_file}")

def _archive_old_devlog_entries(devlog_path: str) -> None:
    """Moves devlog entries older than 30 days to devlogs/archive/YYYY-MM.md."""
    import calendar
    if not os.path.exists(devlog_path):
        return
    cutoff = time.time() - (30 * 24 * 3600)
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    sections = []
    current_lines, current_date = [], None
    with open(devlog_path) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                if current_lines:
                    sections.append((current_date, current_lines))
                current_date = m.group(1)
                current_lines = [line]
            else:
                current_lines.append(line)
    if current_lines:
        sections.append((current_date, current_lines))

    keep, archive_by_month = [], {}
    for date_str, lines in sections:
        if date_str is None:
            keep.append((date_str, lines))
            continue
        try:
            ts = calendar.timegm(time.strptime(date_str, "%Y-%m-%d"))
            if ts < cutoff:
                month_key = date_str[:7]
                archive_by_month.setdefault(month_key, []).extend(lines)
            else:
                keep.append((date_str, lines))
        except ValueError:
            keep.append((date_str, lines))

    if not archive_by_month:
        return

    archive_dir = os.path.join(os.path.dirname(devlog_path), "archive")
    os.makedirs(archive_dir, exist_ok=True)
    for month_key, lines in archive_by_month.items():
        with open(os.path.join(archive_dir, f"{month_key}.md"), "a") as f:
            f.writelines(lines)

    with open(devlog_path, "w") as f:
        for _, lines in keep:
            f.writelines(lines)

def checkpoint() -> None:
    """Archives done tasks, refreshes context, and emits a telemetry event."""
    set_state("active")
    username = get_username()
    todo_path = "project-docs/todo.md"
    devlog_path = f"project-docs/devlogs/{username}.md"

    # Collect completed tasks and remaining active lines
    completed, active_lines = [], []
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if re.match(r'\s*-\s*\[x\]', line, re.IGNORECASE):
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[x\]\s*', '', line, flags=re.IGNORECASE).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    completed.append({"id": id_m.group(1) if id_m else None, "text": text})
                else:
                    active_lines.append(line)

    # Append completed tasks to devlog
    if completed:
        os.makedirs(os.path.dirname(devlog_path), exist_ok=True)
        with open(devlog_path, "a") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d')}\n### Completed (checkpoint)\n")
            for task in completed:
                f.write(f"- {task['text']}\n")
        with open(todo_path, "w") as f:
            f.writelines(active_lines)

    _archive_old_devlog_entries(devlog_path)
    generate_context()

    completed_ids = [t["id"] for t in completed if t["id"]]
    log_telemetry_event({
        "type": "checkpoint",
        "schema_version": 1,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "user": username,
        "completed_task_count": len(completed),
        "completed_task_ids": completed_ids,
        "devlog_entry_appended": bool(completed),
    })

    total_usd, total_requests = parse_costs_md()
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    pct = (total_usd / limit_usd * 100) if limit_usd else 0

    daemon = WatchDaemon()
    set_state("watching" if daemon._is_running() else "stopped")

    print(f"\n✓ checkpoint [@{username}] — {len(completed)} tasks archived, context refreshed")
    if completed:
        names = "  ·  ".join(f'"{t["text"][:40]}"' for t in completed[:3])
        print(f"  Archived: {names}")
    print(f"  Budget: ${total_usd:.2f} / ${limit_usd:.2f} ({pct:.0f}%)  ·  {total_requests} requests")

def cmd_status(json_output: bool = False) -> None:
    """Displays project state dashboard. Exits 1 if sentinel active or budget exceeded."""
    username = get_username()
    mode = get_mode()

    # Active tasks
    active_tasks = []
    todo_path = "project-docs/todo.md"
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if "- [ ]" in line:
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[ \]\s*', '', line).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    active_tasks.append({"id": id_m.group(1) if id_m else None, "text": text})

    # Last checkpoint from telemetry
    last_checkpoint = None
    telemetry_file = ".synlynk/telemetry.json"
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                events = json.load(f)
            for e in reversed(events):
                if e.get("type") == "checkpoint":
                    last_checkpoint = e
                    break
        except (json.JSONDecodeError, IOError):
            pass

    # Sentinel alerts
    sentinel_alerts = []
    sentinel_file = ".synlynk/sentinel.md"
    if os.path.exists(sentinel_file):
        with open(sentinel_file) as f:
            for line in f:
                if line.startswith("- ["):
                    sentinel_alerts.append(line.strip())

    # Budget
    total_usd, total_requests = parse_costs_md()
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    limit_reqs = config["budget"]["limit_requests"]

    # Watcher
    daemon = WatchDaemon()
    watcher_running = daemon._is_running()
    last_trigger_file = None
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                events = json.load(f)
            for e in reversed(events):
                if e.get("type") == "watch_trigger":
                    last_trigger_file = e.get("changed_file")
                    break
        except (json.JSONDecodeError, IOError):
            pass

    # Teammates (team mode)
    teammates = []
    if mode == "team":
        devlogs_dir = "project-docs/devlogs"
        if os.path.exists(devlogs_dir):
            for fname in sorted(os.listdir(devlogs_dir)):
                if fname.endswith(".md") and fname not in (f"{username}.md", "README.md"):
                    fpath = os.path.join(devlogs_dir, fname)
                    teammates.append({
                        "user": fname[:-3],
                        "last_active": _get_last_devlog_date(fpath),
                    })

    has_alert = bool(sentinel_alerts) or total_usd >= limit_usd or total_requests >= limit_reqs

    if json_output:
        data = {
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "user": username,
            "mode": mode,
            "active_tasks": active_tasks,
            "last_checkpoint": last_checkpoint,
            "sentinel": {"alerts": sentinel_alerts},
            "budget": {
                "used_usd": round(total_usd, 4),
                "limit_usd": limit_usd,
                "requests": total_requests,
                "limit_requests": limit_reqs,
            },
            "watcher": {"running": watcher_running, "last_trigger_file": last_trigger_file},
            "teammates": teammates,
        }
        print(json.dumps(data, indent=2))
        sys.exit(1 if has_alert else 0)

    # Human output
    sep = "─" * 45
    print(sep)
    print(f" synlynk status · @{username} · {mode} mode")
    print(sep)
    print(f" ACTIVE TASKS ({len(active_tasks)})")
    for t in active_tasks:
        tid = f"#{t['id']}" if t['id'] else ""
        print(f"   [ ] {t['text']:<40} {tid}")
    print()
    print(" LAST CHECKPOINT")
    if last_checkpoint:
        print(f"   @{last_checkpoint.get('user')} · {last_checkpoint.get('timestamp')} · "
              f"{last_checkpoint.get('completed_task_count', 0)} tasks archived")
    else:
        print("   No checkpoints yet")
    print()
    print(" SENTINEL")
    if sentinel_alerts:
        for alert in sentinel_alerts:
            print(f"   ⚠ {alert}")
    else:
        print("   ✓ No alerts")
    print()
    pct = (total_usd / limit_usd * 100) if limit_usd else 0
    print(" BUDGET")
    print(f"   ${total_usd:.2f} / ${limit_usd:.2f} ({pct:.0f}%)  ·  {total_requests} / {limit_reqs} requests")
    print()
    icon = "●" if watcher_running else "○"
    state = "Running" if watcher_running else "Stopped"
    trigger = f"  ·  last trigger {last_trigger_file}" if last_trigger_file else ""
    print(f" WATCHER\n   {icon} {state}{trigger}")
    if mode == "team" and teammates:
        print()
        print(" TEAMMATES")
        for tm in teammates:
            print(f"   @{tm['user']:<12} · last active {tm['last_active']}")
    print(sep)
    sys.exit(1 if has_alert else 0)

class WatchDaemon:
    """Polls project-docs/ and regenerates context.md on change.

    Subclass and override on_change() for the v1.3.0 LCP JSON-RPC daemon.
    """

    def __init__(self):
        self.pidfile = ".synlynk/watch.pid"
        self.logfile = ".synlynk/watch.log"
        self.settle_seconds = 3

    def start(self) -> None:
        if self._is_running():
            print("  synlynk watch is already running.")
            return
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        if not hasattr(os, "fork"):
            print("  ⚠ watch daemon requires Unix (macOS/Linux). Not supported on Windows.")
            return
        pid = os.fork()
        if pid > 0:
            print("  ● synlynk watch started.")
            return
        os.setsid()
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        # Daemon process: redirect stdio to log
        sys.stdout.flush()
        sys.stderr.flush()
        with open(self.logfile, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
        with open(self.pidfile, "w") as f:
            f.write(str(os.getpid()))
        set_state("watching")
        self._run_loop()

    def stop(self) -> None:
        if not os.path.exists(self.pidfile):
            print("  synlynk watch is not running.")
            set_state("stopped")
            return
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)  # SIGTERM
            os.remove(self.pidfile)
            set_state("stopped")
            print("  ✓ synlynk watch stopped.")
        except (ProcessLookupError, ValueError):
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            set_state("stopped")
            print("  synlynk watch was not running (cleaned stale pidfile).")
        except OSError as e:
            print(f"  Error stopping watch daemon: {e}")

    def status(self) -> None:
        if self._is_running():
            with open(self.pidfile) as f:
                pid = f.read().strip()
            print(f"  ● synlynk watch running (PID {pid})")
            if os.path.exists(self.logfile):
                with open(self.logfile) as f:
                    lines = f.readlines()
                if lines:
                    print(f"    Last log: {lines[-1].strip()}")
        else:
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
            print("  ○ synlynk watch stopped")

    def _is_running(self) -> bool:
        if not os.path.exists(self.pidfile):
            return False
        try:
            with open(self.pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError, IOError, OSError):
            return False

    def _get_mtimes(self, directory: str) -> dict:
        mtimes = {}
        if not os.path.exists(directory):
            return mtimes
        for root, _, files in os.walk(directory):
            for fname in files:
                if fname.endswith((".md", ".json")):
                    path = os.path.join(root, fname)
                    try:
                        mtimes[path] = os.path.getmtime(path)
                    except OSError:
                        pass
        return mtimes

    def on_change(self, filepath: str) -> None:
        """Called when a project-docs file changes. Override in v1.3.0 LCP daemon."""
        generate_context()
        log_telemetry_event({
            "type": "watch_trigger",
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "user": get_username(),
            "changed_file": filepath,
        })

    def _run_loop(self) -> None:
        config = load_config()
        interval = config.get("watch_interval_seconds", 30)
        last_mtimes = self._get_mtimes("project-docs")
        while True:
            time.sleep(interval)
            current_mtimes = self._get_mtimes("project-docs")
            changed = [f for f in current_mtimes
                       if current_mtimes[f] != last_mtimes.get(f)]
            if changed:
                time.sleep(self.settle_seconds)
                set_state("active")
                self.on_change(changed[0])
                set_state("watching")
                last_mtimes = self._get_mtimes("project-docs")

def init(force: bool = False) -> None:
    print("Initializing synlynk in current directory...")

    docs_dir = "project-docs"
    devlogs_dir = os.path.join(docs_dir, "devlogs")
    synlynk_dir = ".synlynk"

    for d in [docs_dir, devlogs_dir, synlynk_dir]:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"  Created {d}/")

    for filename, content in TEMPLATES.items():
        if filename in ("GEMINI.md", "CLAUDE.md", "AI_INSTRUCTIONS.md", ".cursorrules"):
            file_path = filename
        elif filename == "config.json":
            file_path = os.path.join(synlynk_dir, filename)
        else:
            file_path = os.path.join(docs_dir, filename)

        if os.path.exists(file_path) and not force:
            print(f"  {file_path} already exists. Skipping (use --force to overwrite).")
        else:
            with open(file_path, "w") as f:
                f.write(content)
            action = "Updated" if os.path.exists(file_path) else "Created"
            print(f"  {action} {file_path}")

    set_state("stopped")
    print("\n💡 Next: run `synlynk watch start` to keep context fresh during sessions.")
    print("✓ synlynk initialized.")

def upgrade() -> None:
    """Checks GitHub releases for a newer version and prints upgrade instructions."""
    print(f"Checking for updates... (current: v{VERSION})")
    # Try gh CLI first — works for private repos and avoids unauthenticated rate limits.
    try:
        result = subprocess.run(
            ["gh", "api", "repos/nikhilsoman/synlynk/releases/latest", "--jq", ".tag_name"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            latest = result.stdout.strip().lstrip("v")
            if latest and latest != VERSION:
                print(f"  ✦ New version available: v{latest}")
                print("  Upgrade: curl -sSL https://raw.githubusercontent.com/"
                      "nikhilsoman/synlynk/main/install.sh | bash")
            else:
                print(f"  ✓ You are on the latest version (v{VERSION}).")
            return
    except Exception:
        pass
    # Fall back to unauthenticated GitHub API (works for public repos).
    url = "https://api.github.com/repos/nikhilsoman/synlynk/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"synlynk/{VERSION}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        latest = data.get("tag_name", "").lstrip("v")
        if latest and latest != VERSION:
            print(f"  ✦ New version available: v{latest}")
            print("  Upgrade: curl -sSL https://raw.githubusercontent.com/"
                  "nikhilsoman/synlynk/main/install.sh | bash")
        else:
            print(f"  ✓ You are on the latest version (v{VERSION}).")
    except Exception as e:
        print(f"  ⚠ Could not check for updates: {e}")
        print("  Check manually: https://github.com/nikhilsoman/synlynk/releases")

def exec_command(cmd_args: list) -> int:
    if not cmd_args:
        print("Error: No command provided to exec.")
        return

    generate_context()
    check_budgets()
    set_state("active")

    print(f"  Executing: {' '.join(cmd_args)}")
    start_time = time.time()
    exit_code = 0

    try:
        # Inherit stdio directly — interactive tools (Claude Code, Gemini) need a real TTY
        process = subprocess.Popen(cmd_args)
        process.wait()
        exit_code = process.returncode
    except FileNotFoundError:
        exit_code = 127
        print(f"  Error: Command '{cmd_args[0]}' not found.")
    except Exception as e:
        exit_code = 1
        print(f"  Error: {e}")
    finally:
        duration = time.time() - start_time
        print(f"\n  ✓ Execution finished in {duration:.2f}s")
        _check_costs_freshness()
        log_telemetry_event({
            "type": "exec",
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "user": get_username(),
            "command": ' '.join(cmd_args),
            "duration": round(duration, 2),
            "exit_code": exit_code,
        })
        check_flatline()
        daemon = WatchDaemon()
        set_state("watching" if daemon._is_running() else "stopped")
    return exit_code

def main() -> None:
    parser = argparse.ArgumentParser(
        description="synlynk: The Universal Context Switchboard for AI Devs"
    )
    parser.add_argument("--version", action="version", version=f"synlynk {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize synlynk in a repository")
    init_parser.add_argument("--force", action="store_true",
                             help="Overwrite existing template files")

    subparsers.add_parser("upgrade", help="Check for and apply updates")

    exec_parser = subparsers.add_parser("exec", help="Execute an AI CLI with synlynk context")
    exec_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to execute")

    watch_parser = subparsers.add_parser("watch", help="Manage the file watcher daemon")
    watch_parser.add_argument("action", choices=["start", "stop", "status"],
                              help="Daemon action")

    subparsers.add_parser("checkpoint",
                          help="Archive done tasks, refresh context, emit telemetry")

    status_parser = subparsers.add_parser("status", help="Show project state dashboard")
    status_parser.add_argument("--json", action="store_true", dest="json_output",
                               help="Output machine-readable JSON")

    args = parser.parse_args()

    if args.command == "init":
        init(force=args.force)
    elif args.command == "exec":
        sys.exit(exec_command(args.cmd))
    elif args.command == "upgrade":
        upgrade()
    elif args.command == "watch":
        daemon = WatchDaemon()
        if args.action == "start":
            daemon.start()
        elif args.action == "stop":
            daemon.stop()
        elif args.action == "status":
            daemon.status()
    elif args.command == "checkpoint":
        checkpoint()
    elif args.command == "status":
        cmd_status(json_output=args.json_output)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
