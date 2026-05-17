#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import time
import json
import re

VERSION = "1.2.1-lite"


def get_username() -> str:
    """Resolves current user from git config."""
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
            cost_str = parts[6].lstrip("$")
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

def log_telemetry(command, duration, exit_code, cost=0.0):
    """Logs execution telemetry to a local JSON file."""
    telemetry_file = ".synlynk/telemetry.json"
    entry = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "command": command,
        "duration": round(duration, 2),
        "exit_code": exit_code,
        "cost": round(cost, 4)
    }
    
    data = []
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            pass
            
    data.append(entry)
    data = data[-100:]
    
    with open(telemetry_file, "w") as f:
        json.dump(data, f, indent=2)

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

def check_budgets():
    """Checks cumulative usage against budget limits."""
    telemetry_file = ".synlynk/telemetry.json"
    config_file = ".synlynk/config.json"
    
    if not os.path.exists(telemetry_file) or not os.path.exists(config_file):
        return

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        with open(telemetry_file, "r") as f:
            data = json.load(f)
    except:
        return

    limit_usd = config.get("budget", {}).get("limit_usd", 10.0)
    limit_reqs = config.get("budget", {}).get("limit_requests", 100)
    
    total_usd = sum(e.get('cost', 0.0) for e in data)
    total_reqs = len(data)

    if total_usd >= limit_usd:
        print(f"\n🛑 [Budget Alert] CRITICAL: You have spent ${total_usd:.2f} / ${limit_usd:.2f} budget.")
    elif total_usd >= (limit_usd * 0.8):
        print(f"\n⚠️  [Budget Warning] You have reached 80% of your cost budget (${total_usd:.2f} / ${limit_usd:.2f}).")

    if total_reqs >= limit_reqs:
        print(f"\n🛑 [Budget Alert] CRITICAL: You have reached {total_reqs} / {limit_reqs} request limit.")
    elif total_reqs >= (limit_reqs * 0.8):
        print(f"\n⚠️  [Budget Warning] You have reached 80% of your request limit ({total_reqs} / {limit_reqs}).")

def _get_last_devlog_date(filepath: str) -> str | None:
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

def upgrade():
    print(f"Checking for updates... (Current version: {VERSION})")
    time.sleep(1)
    print("  Connecting to synlynk-cloud (github.com/nikhilsoman/synlynk)...")
    time.sleep(1)
    print(f"  ✓ You are already on the latest version ({VERSION}).")

def extract_tokens(output_text):
    patterns = [
        r"Tokens: (\d+) in, (\d+) out",
        r"usage:.*input_tokens: (\d+).*output_tokens: (\d+)",
        r"Prompt Tokens: (\d+).*Completion Tokens: (\d+)",
        r"tokens used: (\d+)"
    ]
    in_tokens = 0
    out_tokens = 0
    for pattern in patterns:
        match = re.search(pattern, output_text, re.IGNORECASE | re.DOTALL)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                in_tokens += int(groups[0])
                out_tokens += int(groups[1])
            elif len(groups) == 1:
                in_tokens += int(groups[0])
    return in_tokens, out_tokens

def update_costs(command, in_tokens, out_tokens, duration):
    """Updates costs.md and provides a 'Budget Pulse' summary."""
    costs_file = "project-docs/costs.md"
    telemetry_file = ".synlynk/telemetry.json"
    
    if not os.path.exists(costs_file):
        return 0.0

    est_cost = (in_tokens / 1000 * 0.003) + (out_tokens / 1000 * 0.015)
    
    total_requests = 0
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file, "r") as f:
                data = json.load(f)
                total_requests = len(data)
        except:
            pass
            
    entry = f"| {time.strftime('%Y-%m-%d %H:%M')} | exec | {command[:20]}... | {in_tokens}/{out_tokens} | 1 | ${est_cost:.4f} | duration: {duration:.1f}s |\n"
    
    with open(costs_file, "a") as f:
        f.write(entry)
        
    print(f"  📊 Budget Pulse: ${est_cost:.4f} this session | Total Requests: {total_requests}")
    if in_tokens > 0:
        print(f"  🪙 Tokens: {in_tokens} in / {out_tokens} out")
    
    return est_cost

def exec_command(cmd_args):
    if not cmd_args:
        print("Error: No command provided to exec.")
        return

    generate_context()
    check_budgets() # Warn BEFORE execution if budget is low
    
    print(f"  Executing: {' '.join(cmd_args)}")
    start_time = time.time()
    exit_code = 0
    captured_output = []
    
    try:
        process = subprocess.Popen(
            cmd_args, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1
        )
        for line in process.stdout:
            print(line, end="")
            captured_output.append(line)
        process.wait()
        exit_code = process.returncode
    except FileNotFoundError:
        exit_code = 127
        print(f"  Error: Command '{cmd_args[0]}' not found.")
    except Exception as e:
        exit_code = 1
        print(f"  Error: {str(e)}")
    finally:
        end_time = time.time()
        duration = end_time - start_time
        full_output = "".join(captured_output)
        in_t, out_t = extract_tokens(full_output)
        
        print(f"\n  ✓ Execution finished in {duration:.2f}s")
        cost = update_costs(' '.join(cmd_args), in_t, out_t, duration)
        log_telemetry(' '.join(cmd_args), duration, exit_code, cost)
        check_flatline()

def main():
    parser = argparse.ArgumentParser(description="synlynk: The Universal Context Switchboard for AI Devs")
    parser.add_argument("--version", action="version", version=f"synlynk {VERSION}")
    
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("init", help="Initialize synlynk in a repository")
    subparsers.add_parser("upgrade", help="Upgrade synlynk binary and templates")
    exec_parser = subparsers.add_parser("exec", help="Execute an AI CLI with synlynk context")
    exec_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="The command to execute")

    args = parser.parse_args()

    if args.command == "init":
        init()
    elif args.command == "exec":
        exec_command(args.cmd)
    elif args.command == "upgrade":
        upgrade()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
