"""synlynk wizard: FTUE 8-screen onboarding TUI (synlynk init --wizard) and launch task picker."""

import json
import os
import select
import sys
import termios
import time
import tty
from typing import Tuple

from synlynk.taxonomy import entries_for_tier

def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)

_BOLD = "\033[1m"

_GREEN = "\033[32m"

_YELLOW = "\033[33m"

_CYAN = "\033[36m"

_DIM = "\033[2m"

_RESET = "\033[0m"

_RED = "\033[31m"

_MAGENTA = "\033[35m"

STAGE_KEYS = ["stack", "source", "complexity", "tests", "git", "arch"]

def cmd_launch_ftue(dry_run: bool = False, list_mode: bool = False) -> None:
    """FTUE task picker TUI - Screen 1 -> Screen 2 -> dispatch
    - dry_run: print selected tasks without TUI or dispatch
    - list_mode: print full template pool with trigger conditions
    """
    if list_mode:
        templates = _pkg("_launch_visible_templates")()
        core_ids = _pkg("CORE_TEMPLATE_IDS")
        print(f"\n  {_BOLD}synlynk launch - task template pool ({len(templates)} templates){_RESET}\n")
        for t in templates:
            cond = t.get("trigger_condition")
            cond_str = "always" if cond is None else "(scan condition)"
            marker = "●" if t["id"] in core_ids else "○"
            print(f"  {marker} {t['id']:<24}  {t['cycle']:<8}  {t['agent']:<8}  {cond_str}")
        print()
        return

    try:
        scan = _pkg("run_workspace_scan")(deep=False)
    except Exception:
        scan = {
            "workspace_name": os.path.basename(os.getcwd()) or "workspace",
            "topology": "single",
            "repos": [{"name": os.path.basename(os.getcwd()), "stack_labels": []}],
            "harnesses": [], "agents": [], "skills": [],
            "test_ratio": 1.0, "readme_word_count": 0,
            "has_ci": False, "has_docs": False,
            "has_type_hints": False, "has_orm": False,
        }

    tasks = _pkg("_select_launch_tasks")(scan)

    if dry_run:
        print(f"\n  {_BOLD}synlynk launch - dry run{_RESET}  "
              f"{_DIM}workspace: {scan.get('workspace_name', 'unknown')}{_RESET}\n")
        for i, t in enumerate(tasks, 1):
            est = t.get("est_hours", 1)
            est_str = f"~{int(est * 60)}m" if est < 1 else f"~{int(est)}h"
            print(f"  [{i}] {t['id']:<24} {t['cycle']:<8}  {t['agent']:<8}  {est_str}")
        print()
        return

    while True:
        chosen = _launch_screen_tasks(tasks, scan)
        if chosen is None:
            return

        confirmed, prompt = _launch_screen_preview(chosen, scan)
        if not confirmed:
            continue

        try:
            job = _pkg("dispatch_agent")(
                agent=chosen["agent"],
                task=prompt,
                story_id=None,
                force_agent=True,
                context_mode=chosen.get("context_mode", "full"),
            )
            job_id = job.get("job_id", "unknown") if isinstance(job, dict) else "dispatched"
            print(f"\n  {_GREEN}▶{_RESET} [{job_id}] {chosen['agent']} dispatched\n"
                  f"  {_DIM}Log: synlynk logs --job {job_id}{_RESET}\n")
        except Exception as exc:
            print(f"\n  {_YELLOW}⚠ Dispatch failed: {exc}{_RESET}\n")
        return

_WIZ_SYNAPTIC_BLURB = (
    "In the brain, a synaptic link is the tiny gap where one neuron passes\n"
    "  its signal to the next. Alone, neurons are just cells. Connected, they\n"
    "  produce thought. Your AI tools are the same — powerful in isolation,\n"
    "  transformative when they share a signal. synlynk is the gap that makes\n"
    "  them think together."
)

_WIZ_PRODUCT_BLURB = (
    "You already have great AI tools. The problem is they don't know about\n"
    "  each other — or your project. synlynk fixes that: it injects shared\n"
    "  context before every dispatch, routes tasks to the right agent, and\n"
    "  keeps score on what's working. Your fleet, finally coordinated."
)

def _wiz_clear() -> None:
    """Clear the terminal screen."""
    os.system("clear" if os.name != "nt" else "cls")

def _wiz_read_key() -> str:
    """Read a single keypress without requiring Enter.

    Falls back to input()[0] when stdin is not a TTY (e.g. tests, pipes).
    """
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line[0] if line else "\r"
    try:
        import tty as _tty
        import termios as _termios
        fd = sys.stdin.fileno()
        old = _termios.tcgetattr(fd)
        try:
            _tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old)
    except (ImportError, Exception):
        # Windows or no termios — fall back to Enter-terminated input
        line = input()
        return line[0] if line else "\r"

def _kbhit() -> bool:
    """Return True if a keypress is waiting on stdin without blocking."""
    import select as _select
    try:
        if not sys.stdin.isatty():
            return False
    except Exception:
        return False
    try:
        ready, _, _ = _select.select([sys.stdin], [], [], 0)
        return bool(ready)
    except Exception:
        return False

_STAGE_LABELS = ["STACK", "SOURCE", "COMPLEXITY", "TESTS", "GIT CHURN", "ARCHITECTURE"]

_STAGE_COLORS = [_GREEN, _CYAN, _YELLOW, _GREEN, _RED, _MAGENTA]

def _card_summary(key: str, data) -> Tuple[str, str]:
    """Return the two summary lines used in the stage cards."""
    if key == "stack":
        data = data or {}
        lang = str(data.get("language", "unknown")).capitalize()
        ver = str(data.get("version", "")).strip()
        frameworks = data.get("frameworks", []) or []
        framework_text = ", ".join(frameworks[:2]) or "no frameworks"
        dep_count = data.get("dep_count", {}) or {}
        prod = dep_count.get("prod", 0)
        dev = dep_count.get("dev", 0)
        ci = "CI ✓" if data.get("ci") else "no CI"
        lockfile = "fresh" if data.get("lockfile_fresh") else "stale"
        line1 = f"{lang} {ver}".strip()
        line2 = f"{framework_text} · {ci} · {prod} prod · {dev} dev · {lockfile}"
        return line1, line2
    if key == "source":
        source = data or []
        total_files = len(source)
        total_fns = sum(int(f.get("functions", 0) or 0) for f in source)
        typed_pct = 0
        if source:
            typed_pct = round(
                sum(float(f.get("typed_pct", 0) or 0) for f in source) / max(len(source), 1)
            )
        largest = source[0] if source else {}
        line1 = f"{total_files} files · {total_fns} fns · {typed_pct}% typed"
        line2 = ""
        if largest.get("path"):
            line2 = f"{largest['path']} · {int(largest.get('lines', 0) or 0):,} lines"
        return line1, line2
    if key == "complexity":
        complexity = data or {}
        hotspots = complexity.get("hotspots", []) or []
        todo_counts = complexity.get("todo_counts", {}) or {}
        marker_total = sum(int(v or 0) for v in todo_counts.values())
        line1 = f"{len(hotspots)} hotspots · {marker_total} markers"
        top = hotspots[0] if hotspots else {}
        if top.get("path"):
            label = top.get("fn") or os.path.basename(top["path"])
            line2 = f"{label} · {int(top.get('lines', 0) or 0):,} lines"
        else:
            parts = [f"{k}:{v}" for k, v in todo_counts.items() if v]
            line2 = " · ".join(parts[:3])
        return line1, line2
    if key == "tests":
        tests = data or {}
        ratio = float(tests.get("ratio", 0) or 0)
        gap_count = int(tests.get("gap_count", 0) or 0)
        line1 = f"{int(round(ratio * 100))}% covered · {gap_count} gaps"
        gaps = tests.get("gap_functions", []) or []
        names = [g.get("name", "?") for g in gaps[:2]]
        suffix = f" +{gap_count - 2}" if gap_count > 2 else ""
        line2 = f"{', '.join(names)}{suffix}".strip()
        return line1, line2
    if key == "git":
        git_data = data or {}
        churn = git_data.get("churn", []) or []
        total = int(git_data.get("total_commits_scanned", 0) or 0)
        if churn:
            line1 = f"{churn[0].get('path', '?')} · {int(churn[0].get('commits', 0) or 0)} commits"
        else:
            line1 = f"{total} commits scanned"
        line2 = ""
        warm = next((item for item in churn if item.get("temp") == "warm"), None)
        if warm:
            line2 = f"warm: {warm.get('path', '?')}"
        elif churn:
            line2 = f"hot files: {len(churn)}"
        return line1, line2
    if key == "arch":
        arch = data or {}
        pattern = arch.get("pattern", "unknown")
        entry_points = arch.get("entry_points", []) or []
        dead = arch.get("dead_candidates", []) or []
        public_api_count = int(arch.get("public_api_count", 0) or 0)
        line1 = f"{pattern} · {len(entry_points)} entry point{'s' if len(entry_points) != 1 else ''}"
        line2 = f"{len(dead)} dead candidates · {public_api_count} public API"
        return line1, line2
    return ("", "")

def _render_one_card(idx: int, results: dict) -> str:
    """Render a single stage card box."""
    key = STAGE_KEYS[idx]
    label = _STAGE_LABELS[idx]
    color = _STAGE_COLORS[idx]
    data = results.get(key)
    width = 34

    top = f"┌{'─' * width}┐"
    bottom = f"└{'─' * width}┘"

    def _line(text: str, style: str = "") -> str:
        text = (text or "")[:width]
        return f"│ {style}{text:<{width - 2}}{_RESET} │"

    if data is None:
        return "\n".join([
            f"{_DIM}{top}{_RESET}",
            _line(f"{label} ⟳", _DIM),
            _line("scanning...", _DIM),
            _line("", _DIM),
            f"{_DIM}{bottom}{_RESET}",
        ])

    if isinstance(data, dict) and data.get("error"):
        err = str(data.get("error", "error"))
        return "\n".join([
            f"{_RED}{top}{_RESET}",
            _line(f"{label} !", _RED),
            _line(err, _DIM),
            _line("", _DIM),
            f"{_RED}{bottom}{_RESET}",
        ])

    line1, line2 = _card_summary(key, data)
    done_icon = "✓"
    return "\n".join([
        f"{color}{top}{_RESET}",
        _line(f"{label} {done_icon}", color),
        _line(line1, ""),
        _line(line2, _DIM),
        f"{color}{bottom}{_RESET}",
    ])

def _render_expanded_card(key: str, results: dict) -> None:
    """Print a detail view below the grid for the expanded stage."""
    if key not in STAGE_KEYS:
        return
    idx = STAGE_KEYS.index(key)
    label = _STAGE_LABELS[idx]
    color = _STAGE_COLORS[idx]
    data = results.get(key)
    print(f"  {color}── {label} ─────────────────────────────────{_RESET}")
    if data is None:
        print(f"  {_DIM}still scanning...{_RESET}")
        return
    if isinstance(data, dict) and data.get("error"):
        print(f"  {_RED}{data['error']}{_RESET}")
        return
    if key == "stack":
        for field in ("language", "version", "package_manager", "ci", "ci_workflows", "lockfile_fresh"):
            print(f"  {_DIM}{field:<16}{_RESET} {data.get(field)}")
        frameworks = ", ".join(data.get("frameworks", []) or []) or "none"
        print(f"  {_DIM}{'frameworks':<16}{_RESET} {frameworks}")
        dep_count = data.get("dep_count", {}) or {}
        print(f"  {_DIM}{'deps':<16}{_RESET} prod={dep_count.get('prod', 0)} dev={dep_count.get('dev', 0)}")
    elif key == "source":
        for row in (data or [])[:5]:
            print(f"  {row.get('path', '?'):<36} {int(row.get('lines', 0) or 0):>6} lines  "
                  f"{int(row.get('functions', 0) or 0):>3} fns")
    elif key == "complexity":
        for hotspot in (data.get("hotspots", []) or [])[:5]:
            label_text = hotspot.get("fn") or os.path.basename(hotspot.get("path", "?"))
            print(f"  {_YELLOW}{label_text:<28}{_RESET} "
                  f"{int(hotspot.get('lines', 0) or 0)} lines  "
                  f"({hotspot.get('path', '?')}:{hotspot.get('lineno', '?')})")
        todo_counts = data.get("todo_counts", {}) or {}
        todo_line = " · ".join(f"{k}: {v}" for k, v in todo_counts.items() if v)
        if todo_line:
            print(f"  {_DIM}{todo_line}{_RESET}")
    elif key == "tests":
        for gap in (data.get("gap_functions", []) or [])[:8]:
            print(f"  {_DIM}✗ {gap.get('name', '?'):<28}{_RESET} "
                  f"{gap.get('file', '?')}:{gap.get('lineno', '?')}")
    elif key == "git":
        for item in (data.get("churn", []) or [])[:6]:
            icon = "🔥" if item.get("temp") == "hot" else ("⚡" if item.get("temp") == "warm" else "·")
            print(f"  {icon} {item.get('path', '?'):<34} {int(item.get('commits', 0) or 0):>3} commits")
    elif key == "arch":
        for entry in (data.get("entry_points", []) or [])[:5]:
            print(f"  {_CYAN}{entry.get('name', '?')}{_RESET}  "
                  f"{entry.get('file', '?')}:{entry.get('lineno', '?')}")
        if data.get("dead_candidates"):
            print(f"  {_DIM}Dead candidates: {', '.join(data.get('dead_candidates', [])[:4])}{_RESET}")
    print()

def _render_scan_cards(results: dict, expanded, elapsed: float) -> None:
    """Render the full Stage Cards TUI."""
    all_done = all(results.get(key) is not None for key in STAGE_KEYS)
    status = f"{_GREEN}✓ complete · {elapsed:.1f}s{_RESET}" if all_done else f"{_YELLOW}⟳ scanning…{_RESET}"
    workspace_name = results.get("workspace_name") or os.path.basename(os.getcwd()) or "workspace"
    print(f"\n  {_BOLD}{_CYAN}◆ synlynk scan{_RESET}  {_DIM}workspace: {workspace_name}{_RESET}  {status}\n")

    for row in range(3):
        left_idx = row * 2
        right_idx = left_idx + 1
        left_lines = _render_one_card(left_idx, results).splitlines()
        right_lines = _render_one_card(right_idx, results).splitlines() if right_idx < len(STAGE_KEYS) else []
        width = max(len(line) for line in left_lines) if left_lines else 0
        for i in range(max(len(left_lines), len(right_lines))):
            left = left_lines[i] if i < len(left_lines) else ""
            right = right_lines[i] if i < len(right_lines) else ""
            print(f"  {left:<{width}}  {right}")
        print()

    if expanded:
        _render_expanded_card(expanded, results)

    hints = "[1–6] expand card · [r] re-scan · [q] quit"
    if all_done:
        hints = f"[enter] {_CYAN}synlynk launch{_RESET} · {hints}"
    print(f"  {_DIM}{hints}{_RESET}\n")

def _run_scan_tui(results: dict, threads: list, primary_root: str = ".") -> None:
    """Poll stage results at 200ms, refresh the grid, and finish on Enter."""
    import json as _json
    import time as _time

    expanded = None
    started = _time.monotonic()
    while True:
        elapsed = _time.monotonic() - started
        _pkg("_wiz_clear")()
        _pkg("_render_scan_cards")(results, expanded, elapsed)

        if _pkg("_kbhit")():
            key = _pkg("_wiz_read_key")()
            if key in ("q", "\x03"):
                sys.exit(0)
            if key == "r":
                return
            if key.isdigit() and 1 <= int(key) <= len(STAGE_KEYS):
                next_expanded = STAGE_KEYS[int(key) - 1]
                expanded = None if expanded == next_expanded else next_expanded
            elif key in ("\r", "\n") and all(results.get(k) is not None for k in STAGE_KEYS):
                break

        if all(results.get(k) is not None for k in STAGE_KEYS) and not sys.stdin.isatty():
            break

        _time.sleep(0.2)

    for thread in threads or []:
        try:
            thread.join(timeout=0.1)
        except Exception:
            pass

    updated = _pkg("_write_scan_fences")(results, root=primary_root)
    if updated:
        print(f"\n  {_GREEN}── Agent fences updated ──────────────────{_RESET}")
        for path in updated:
            print(f"  {_GREEN}✓{_RESET} {path}  — codebase context written")

    scan_json = os.path.join(primary_root, ".synlynk", "scan-result.json")
    os.makedirs(os.path.dirname(scan_json), exist_ok=True)
    try:
        with open(scan_json, "w", encoding="utf-8") as fh:
            _json.dump(results, fh, indent=2, default=str)
        print(f"  {_DIM}.synlynk/scan-result.json saved{_RESET}")
    except OSError:
        pass

    if sys.stdin.isatty():
        print(f"\n  {_DIM}Press{_RESET} {_CYAN}[enter]{_RESET} {_DIM}to run{_RESET} "
              f"{_CYAN}synlynk launch{_RESET}  {_DIM}or [q] to quit{_RESET}")
        key = _pkg("_wiz_read_key")()
        if key in ("\r", "\n"):
            _pkg("cmd_launch_ftue")()
        elif key in ("q", "\x03"):
            sys.exit(0)
    else:
        _pkg("cmd_launch_ftue")()

def _wiz_header(step: int, total: int, sub_active: bool = False) -> None:
    """Print the wizard progress header.

    Active step shown as a wider pill. Sub-active steps use teal colour.
    """
    _TEAL = "\033[36m"
    dots = []
    for i in range(1, total + 1):
        if i < step:
            dots.append(f"{_CYAN}●{_RESET}")
        elif i == step:
            color = _TEAL if sub_active else _CYAN
            dots.append(f"{color}━━{_RESET}")
        else:
            dots.append(f"{_DIM}·{_RESET}")
    dot_str = "  ".join(dots)
    sub_note = " (multi-repo)" if sub_active else ""
    print(f"\n  step {_CYAN}{step}{_RESET}/{total}{sub_note}   {dot_str}\n")

def _wiz_prompt(hint: str, color: str = None) -> None:
    """Print the bottom prompt line."""
    c = color or _CYAN
    print(f"\n  {c}›{_RESET} {_DIM}{hint}{_RESET}")

def _wiz_screen_landing() -> None:
    """Landing screen — brand intro + synaptic link explainer. Waits for Enter."""
    _wiz_clear()
    print(f"\n  {_BOLD}{_CYAN}syn{_RESET}{_CYAN}l{_RESET}{_DIM}y{_RESET}"
          f"{_CYAN}n{_RESET}k  {_DIM}·  synaptic link for AI development{_RESET}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}")
    print(f"\n  {_BOLD}What is a synaptic link?{_RESET}")
    print(f"  {_DIM}{_WIZ_SYNAPTIC_BLURB}{_RESET}\n")
    print(f"  {_WIZ_PRODUCT_BLURB}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}")
    print(f"\n  {_GREEN}✦ One brain{_RESET}  {_DIM}Every agent works from the same project memory.{_RESET}")
    print(f"  {_GREEN}✦ 4× efficiency{_RESET}  {_DIM}Headless dispatch — no wasted tokens on chat.{_RESET}")
    print(f"  {_GREEN}✦ Always watching{_RESET}  {_DIM}Costs, drift, and jobs tracked automatically.{_RESET}")
    _wiz_prompt("press enter to start setup — takes about 2 minutes")
    _pkg("_wiz_read_key")()

def _wiz_screen_harness(scan: dict) -> str:
    """Screen 1 — choose home harness. Returns chosen harness name."""
    _wiz_clear()
    _wiz_header(step=1, total=6)
    print(f"  {_BOLD}Choose your home harness{_RESET}\n")
    print(f"  {_DIM}Your home harness is the AI CLI synlynk treats as primary —{_RESET}")
    print(f"  {_DIM}where it orchestrates jobs, reads costs, and runs health checks.{_RESET}")
    print(f"  {_DIM}You can dispatch to any agent regardless of this choice.{_RESET}\n")

    harnesses = scan.get("harnesses", [])
    home = scan.get("home_harness")

    if not harnesses:
        print(f"  {_YELLOW}⚠ No harnesses found on PATH.{_RESET}")
        print(f"  {_DIM}Install claude, gemini, or codex then re-run `synlynk scan`.{_RESET}")
        _wiz_prompt("press enter to continue with no home harness")
        _pkg("_wiz_read_key")()
        return ""

    print(f"  {_DIM}scan found:{_RESET}")
    for h in harnesses:
        marker = f"{_GREEN}●{_RESET}" if h["name"] == home else f"{_DIM}○{_RESET}"
        print(f"    {marker} {h['name']:12} {_DIM}{h['version']}  {h['path']}{_RESET}")
    print()

    for i, h in enumerate(harnesses, 1):
        default_note = "  (default)" if h["name"] == home else ""
        print(f"  {_CYAN}[{i}]{_RESET} {h['name']}{_DIM}{default_note}{_RESET}")

    _wiz_prompt("enter number to select · enter to use default")
    key = _pkg("_wiz_read_key")()

    if key in ("\r", "\n", ""):
        return home or (harnesses[0]["name"] if harnesses else "")
    try:
        idx = int(key) - 1
        if 0 <= idx < len(harnesses):
            return harnesses[idx]["name"]
    except ValueError:
        pass
    return home or (harnesses[0]["name"] if harnesses else "")

def _wiz_screen_topology(scan: dict) -> str:
    """Screen 2 — repo topology. Returns 'single', 'monorepo', or 'multi'."""
    _wiz_clear()
    _wiz_header(step=2, total=6)
    print(f"  {_BOLD}How are your repos arranged?{_RESET}\n")
    print(f"  {_DIM}synlynk organises your work into workspaces — named containers{_RESET}")
    print(f"  {_DIM}that share a context database, agent fleet, and budget.{_RESET}\n")

    repos = scan.get("repos", [])
    if repos:
        print(f"  {_DIM}scan found {len(repos)} git repo(s) nearby:{_RESET}")
        for r in repos[:5]:
            stack = ", ".join(r["stack_labels"]) or "unknown"
            print(f"    {_CYAN}●{_RESET} {r['name']:20} {_DIM}{stack}{_RESET}")
        if len(repos) > 5:
            print(f"    {_DIM}… and {len(repos) - 5} more{_RESET}")
        print()

    print(f"  {_CYAN}[1]{_RESET} Single repo  {_DIM}— just this repo{_RESET}")
    print(f"  {_CYAN}[2]{_RESET} Monorepo     {_DIM}— one repo with packages/ or apps/ sub-dirs{_RESET}")
    print(f"  {_CYAN}[3]{_RESET} Multi-repo   {_DIM}— multiple repos sharing one workspace{_RESET}")

    # Pre-select based on scan result
    auto = scan.get("topology", "single")
    auto_num = {"single": "1", "monorepo": "2", "multi": "3"}.get(auto, "1")
    _wiz_prompt(f"enter 1/2/3 · enter for auto-detected ({auto_num})")
    key = _pkg("_wiz_read_key")()

    if key in ("\r", "\n", ""):
        return auto
    mapping = {"1": "single", "2": "monorepo", "3": "multi"}
    return mapping.get(key, auto)

def _wiz_screen_workspace_name_pick(scan: dict) -> dict:
    """Screen 2ab — combined workspace name input + repo picker (multi-repo).

    Returns dict: {workspace_name: str, repos: list[dict]}
    """
    _TEAL = "\033[36m"
    _wiz_clear()
    _wiz_header(step=2, total=6, sub_active=True)
    print(f"  {_BOLD}Name & assemble your workspace{_RESET}\n")
    print(f"  {_DIM}All selected repos share one state.db, agent fleet, and budget.{_RESET}")
    print(f"  {_DIM}synlynk found these git roots nearby — include everything your{_RESET}")
    print(f"  {_DIM}agents need to see together.{_RESET}\n")

    # Workspace name
    suggested = scan.get("workspace_name", "my-workspace")
    print(f"  {_DIM}workspace name{_RESET}  [{_CYAN}{suggested}{_RESET}]  "
          f"{_DIM}(enter to accept, or type new name){_RESET}")
    _wiz_prompt("workspace name")

    if sys.stdin.isatty():
        import tty as _tty, termios as _termios
        # Restore normal line editing for text input
        fd = sys.stdin.fileno()
        try:
            old = _termios.tcgetattr(fd)
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old)
        except Exception:
            pass
    raw_name = input().strip()
    workspace_name = raw_name if raw_name else suggested

    # Repo picker
    repos = scan.get("repos", [])
    _DOTFILE_NAMES = {"dotfiles", ".dotfiles", "dotfile"}
    selected = [r["name"] not in _DOTFILE_NAMES for r in repos]

    print(f"\n  {_DIM}repos to include:{_RESET}  "
          f"{_DIM}(space to toggle, enter to confirm){_RESET}\n")
    for i, (r, sel) in enumerate(zip(repos, selected)):
        stack = ", ".join(r["stack_labels"]) or "unknown"
        check = f"{_TEAL}[✓]{_RESET}" if sel else f"{_DIM}[ ]{_RESET}"
        print(f"  {check} {i+1}. {r['name']:20} {_DIM}{stack}{_RESET}")

    print(f"\n  {_DIM}[a] add repo from another path{_RESET}")
    _wiz_prompt("number to toggle · a to add · enter to confirm")

    while True:
        key = _pkg("_wiz_read_key")()
        if key in ("\r", "\n", ""):
            break
        if key == "a":
            print(f"\n  {_DIM}path to repo:{_RESET} ", end="", flush=True)
            extra = input().strip()
            if extra and os.path.isdir(os.path.join(extra, ".git")):
                repos.append({
                    "path": os.path.abspath(extra),
                    "name": os.path.basename(extra),
                    "stack_labels": _pkg("fingerprint_stack")(extra),
                    "readme_excerpt": "",
                    "context_sections": {},
                })
                selected.append(True)
                print(f"  {_GREEN}✓{_RESET} added {os.path.basename(extra)}")
        try:
            idx = int(key) - 1
            if 0 <= idx < len(selected):
                selected[idx] = not selected[idx]
        except ValueError:
            pass

    chosen_repos = [r for r, s in zip(repos, selected) if s]
    return {"workspace_name": workspace_name, "repos": chosen_repos}

def _wiz_screen_workspace_confirm(workspace: dict) -> bool:
    """Screen 2c — confirm workspace structure.

    Returns True = confirmed (continue), False = go back to 2ab.
    """
    _TEAL = "\033[36m"
    _wiz_clear()
    _wiz_header(step=2, total=6, sub_active=True)
    print(f"  {_BOLD}Here's your workspace{_RESET}\n")

    ws_name = workspace.get("workspace_name", "workspace")
    repos = workspace.get("repos", [])
    print(f"  {_TEAL}{ws_name}/{_RESET}")
    print(f"  {_DIM}├─ state.db{_RESET}")
    print(f"  {_DIM}├─ config.json{_RESET}")
    print(f"  {_DIM}└─ repos{_RESET}")
    for r in repos:
        print(f"  {_GREEN}    ✓{_RESET} {r['name']:20} {_DIM}{r['path']}{_RESET}")

    print(f"\n  {_DIM}state lives at: ~/.synlynk/workspaces/{ws_name}/state.db{_RESET}")
    print(f"  {_DIM}add more later: synlynk scan --add ~/path/to/repo{_RESET}\n")

    print(f"  {_TEAL}[enter]{_RESET} Create workspace · "
          f"{_DIM}[e]{_RESET} Edit")
    _wiz_prompt("enter to create · e to edit")
    key = _pkg("_wiz_read_key")()
    return key not in ("e", "E")

def _wiz_screen_skills(scan: dict) -> None:
    """Screen 3 — skills/plugins education (no required choice)."""
    _wiz_clear()
    _wiz_header(step=3, total=6)
    print(f"  {_BOLD}synlynk and your skill packs work together{_RESET}\n")
    print(f"  {_DIM}synlynk injects project context before skills run — it never overrides{_RESET}")
    print(f"  {_DIM}them. If you use Superpowers or GStack, your skill routes stay intact.{_RESET}")
    print(f"  {_DIM}synlynk adds the layer below: shared state, dispatch coordination,{_RESET}")
    print(f"  {_DIM}cost tracking.{_RESET}\n")

    skills = scan.get("skills", [])
    if skills:
        print(f"  {_DIM}scan found:{_RESET}")
        for s in skills:
            print(f"    {_GREEN}●{_RESET} {s['name']:20} {_DIM}v{s['version']}  {s['path']}{_RESET}")
    else:
        print(f"  {_DIM}No skill packs found. You can install them later —{_RESET}")
        print(f"  {_DIM}synlynk works great without them.{_RESET}")

    _wiz_prompt("press enter to continue")
    _pkg("_wiz_read_key")()

_ROBOT_ASCII = "[~]"

def _wiz_screen_agents(scan: dict) -> None:
    """Screen 4 — agent fleet display (no required choice)."""
    _wiz_clear()
    _wiz_header(step=4, total=6)
    print(f"  {_BOLD}Your agent fleet{_RESET}\n")
    print(f"  {_DIM}Each agent has different strengths. synlynk's dispatch command routes{_RESET}")
    print(f"  {_DIM}tasks to the right agent and tracks what they cost you.{_RESET}\n")

    agents = [a for a in scan.get("agents", []) if a.get("functional")]
    if agents:
        print(f"  {_DIM}installed agents:{_RESET}\n")
        for a in agents:
            caps = ", ".join((a.get("capabilities") or a.get("roles") or [])[:3])
            print(f"  {_CYAN}{_ROBOT_ASCII}{_RESET}  {_BOLD}{a['name']:12}{_RESET}"
                  f"  {_DIM}{a.get('version', 'unknown'):10}{_RESET}  {caps}")
    else:
        print(f"  {_YELLOW}No functional agents found.{_RESET}")
        print(f"  {_DIM}Install claude, gemini, or codex to form your agent fleet.{_RESET}")

    _wiz_prompt("press enter to continue")
    _pkg("_wiz_read_key")()

def _wiz_screen_roles(scan: dict) -> dict:
    """Screen 5 — agent role assignment.

    Returns dict: {harness_name: role_description}
    """
    _wiz_clear()
    _wiz_header(step=5, total=6)
    print(f"  {_BOLD}Who does what?{_RESET}\n")
    print(f"  {_DIM}Consistent role assignment stops agents stomping on each other's work.{_RESET}")
    print(f"  {_DIM}synlynk writes a role block into each agent's directive file so every{_RESET}")
    print(f"  {_DIM}agent knows its lane from token one.{_RESET}\n")

    agents = [a for a in scan.get("agents", []) if a.get("functional")]
    roles = {}
    for a in agents:
        name = a["name"]
        default_roles = _pkg("_default_roles_for_agent")(name) or []
        if default_roles:
            existing = " · ".join(default_roles)
        else:
            existing = ", ".join(a.get("roles", [])) or "general"
        roles[name] = existing
        print(f"  {_CYAN}{name:12}{_RESET} {_DIM}→{_RESET}  {existing}")

    print()
    print(f"  {_CYAN}[enter]{_RESET} use these roles  "
          f"{_DIM}[e]{_RESET} edit (opens per-agent prompts)")
    _wiz_prompt("enter to accept · e to edit")
    key = _pkg("_wiz_read_key")()

    if key in ("e", "E"):
        for name in list(roles.keys()):
            print(f"\n  {name} role [{roles[name]}]: ", end="", flush=True)
            entered = input().strip()
            if entered:
                roles[name] = entered

    return roles

def _wiz_screen_launch(workspace: dict, scan: dict, auto_launch: bool = False) -> None:
    """Screen 6 — launch cheat sheet. Final screen."""
    _wiz_clear()
    _wiz_header(step=6, total=6)
    ws_name = workspace.get("workspace_name", "workspace")
    home_h = workspace.get("home_harness") or scan.get("home_harness") or "claude"
    print(f"  {_BOLD}{_GREEN}You're set up.{_RESET}  "
          f"{_DIM}workspace: {ws_name}{_RESET}\n")
    print(f"  {_DIM}{'─' * 52}{_RESET}\n")
    cheat_sheet = []
    seen = set()
    for entry in entries_for_tier(0):
        if entry["prominence"] == "primary" and not entry["orientation_gateway"]:
            cheat_sheet.append(entry)
            seen.add(entry["command"])
    for entry in entries_for_tier(0):
        if entry["orientation_gateway"] and entry["command"] not in seen:
            cheat_sheet.append(entry)
            seen.add(entry["command"])

    for entry in cheat_sheet:
        trigger = entry["trigger_phrases"][0] if entry["trigger_phrases"] else "launch from synlynk"
        print(f"  {_CYAN}synlynk {entry['command']}{_RESET}  {_DIM}{trigger}{_RESET}")
    print(f"\n  {_DIM}{'─' * 52}{_RESET}")
    _wiz_prompt("done · run `synlynk launch` to pick your first task")
    _pkg("_wiz_read_key")()
    if auto_launch:
        _pkg("cmd_launch_ftue")()

def _launch_screen_cycles() -> None:
    """Screen 3 — cycles explainer. Any key returns to Screen 1."""
    _wiz_clear()
    cycle_ansi = {
        "Dream":   "\033[38;5;141m",
        "Design":  "\033[38;5;117m",
        "Plan":    "\033[38;5;120m",
        "Build":   "\033[38;5;221m",
        "Ship":    "\033[38;5;210m",
        "Sustain": "\033[38;5;246m",
    }
    print(f"\n  {_BOLD}{_CYAN}◆ The 6 cycles — your multi-agent SDLC{_RESET}\n")
    cycle_agents = {
        "Dream":   "→ claude",
        "Design":  "→ claude",
        "Plan":    "→ claude",
        "Build":   "→ agy · codex · grok",
        "Ship":    "→ claude",
        "Sustain": "→ all agents",
    }
    for name, desc in [
        ("Dream",   "What's worth building? Ideate, assess, identify opportunities."),
        ("Design",  "Brainstorm → spec → UX. Turn ideas into a concrete brief."),
        ("Plan",    "Implementation plan, story breakdown, agent wave schedule."),
        ("Build",   "Dispatch agents, run jobs, iterate on diffs."),
        ("Ship",    "Cut release, changelog, publish."),
        ("Sustain", "Monitor, patch, community, docs, support."),
    ]:
        color = cycle_ansi.get(name, "")
        agents = cycle_agents.get(name, "")
        print(f"  {color}{_BOLD}{name:<8}{_RESET}  {_DIM}{desc}  {agents}{_RESET}")
    print(f"\n  {_DIM}Tasks in synlynk launch are tagged to the cycle they open.")
    print(f"  Any cycle can dispatch any agent.{_RESET}\n")
    print(f"  {_DIM}[any key] back to tasks{_RESET}\n")
    _pkg("_wiz_read_key")()

def _launch_screen_preview(task: dict, scan: dict) -> tuple:
    """Screen 2 — dispatch preview.
    Returns (confirmed: bool, prompt: str).
    [enter/space] → (True, prompt); [e] → edit prompt inline; [esc/q] → (False, prompt)
    """
    prompt = _pkg("_render_prompt")(task, scan)

    while True:
        _wiz_clear()
        cycle = task.get("cycle", "dream")
        agent = task.get("agent", "claude")
        est = task.get("est_hours", 1)
        est_str = f"~{int(est * 60)}m" if est < 1 else f"~{int(est)}h"
        r = task.get("r_tokens", 0)
        w = task.get("w_tokens", 0)
        t = task.get("tool_calls", 0)
        r_str = f"{r // 1000}K" if r >= 1000 else str(r)
        w_str = f"{w // 1000}K" if w >= 1000 else str(w)

        cycle_ansi = {
            "dream":   "\033[38;5;141m",
            "design":  "\033[38;5;117m",
            "plan":    "\033[38;5;120m",
            "build":   "\033[38;5;221m",
            "ship":    "\033[38;5;210m",
            "sustain": "\033[38;5;246m",
        }
        cycle_color = cycle_ansi.get(cycle, "")

        print(f"\n  {_BOLD}{_CYAN}◆ Dispatch preview{_RESET}\n")
        print(f"  {_DIM}{'agent':<8}{_RESET}{agent}")
        print(f"  {_DIM}{'cycle':<8}{_RESET}{cycle_color}{cycle.capitalize()}{_RESET}")
        print(f"  {_DIM}{'mode':<8}{_RESET}{task.get('context_mode', 'full')} context")
        print(f"  {_DIM}{'est.':<8}{_RESET}{est_str}  │  "
              f"\033[38;5;117mR\033[0m {r_str} · "
              f"\033[38;5;120mW\033[0m {w_str} · "
              f"\033[38;5;221mT\033[0m {t}\n")
        print(f"  {_DIM}task prompt:{_RESET}")

        # Wrap prompt at 56 chars for the box
        words = prompt.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > 56:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)

        print(f"  ┌{'─' * 58}┐")
        for line in lines:
            print(f"  │ {line:<56} │")
        print(f"  └{'─' * 58}┘\n")
        print(f"  {_DIM}[enter] dispatch now   [e] edit prompt   [esc] back to tasks{_RESET}\n")

        key = _pkg("_wiz_read_key")()

        if key in ("\r", "\n", " "):
            return True, prompt
        if key in ("\x1b", "q"):
            return False, prompt
        if key in ("e", "E"):
            print(f"\n  Edit prompt (press Enter to confirm):\n  > ", end="", flush=True)
            try:
                edited = input().strip()
                if edited:
                    prompt = edited
            except (EOFError, KeyboardInterrupt):
                pass
            continue

def _launch_screen_tasks(tasks: list, scan: dict):
    """Screen 1 — task selection TUI. Returns chosen template dict or None if user skips."""
    while True:
        _wiz_clear()
        ws_name = scan.get("workspace_name", "workspace")
        repos = scan.get("repos", [])
        primary = repos[0] if repos else {}
        stack = ", ".join(primary.get("stack_labels", [])) or "unknown"
        topology = scan.get("topology", "single")
        harnesses = scan.get("harnesses", [])
        agent_names = ", ".join(h["name"] for h in harnesses) or "none"

        print(f"\n  {_BOLD}{_CYAN}◆ synlynk launch{_RESET}")
        print(f"  {_DIM}{ws_name} · {stack} · {topology} repo · {agent_names}{_RESET}\n")
        print(f"  Where do you want to start?\n")

        cycle_ansi = {
            "dream":   "\033[38;5;141m",
            "design":  "\033[38;5;117m",
            "plan":    "\033[38;5;120m",
            "build":   "\033[38;5;221m",
            "ship":    "\033[38;5;210m",
            "sustain": "\033[38;5;246m",
        }

        for i, task in enumerate(tasks, 1):
            cycle = task.get("cycle", "dream")
            cycle_color = cycle_ansi.get(cycle, "")
            cycle_tag = f"{cycle_color}[{cycle.capitalize()}]{_RESET}"
            num_color = cycle_ansi.get(cycle, _CYAN)
            print(f"  {num_color}[{i}]{_RESET} {_BOLD}{task['title']}{_RESET}  {cycle_tag}")
            if task.get("trigger_condition") is not None:
                print(f"     {_YELLOW}⚡ scan found: {task['description']}{_RESET}")
            else:
                print(f"     {_DIM}{task['description']}{_RESET}")
            est = task.get("est_hours", 1)
            est_str = f"~{int(est * 60)}m" if est < 1 else f"~{int(est)}h"
            r = task.get("r_tokens", 0)
            w = task.get("w_tokens", 0)
            t = task.get("tool_calls", 0)
            r_str = f"{r // 1000}K" if r >= 1000 else str(r)
            w_str = f"{w // 1000}K" if w >= 1000 else str(w)
            print(f"     {_DIM}{est_str}  │  "
                  f"\033[38;5;117mR\033[0m {r_str} · "
                  f"\033[38;5;120mW\033[0m {w_str} · "
                  f"\033[38;5;221mT\033[0m {t}{_RESET}")
            print()

        print(f"  {_DIM}{'─' * 52}{_RESET}")
        print(f"  {_DIM}\033[38;5;117mR\033[0m{_DIM} read · "
              f"\033[38;5;120mW\033[0m{_DIM} write · "
              f"\033[38;5;221mT\033[0m{_DIM} tool calls · estimates based on task template{_RESET}")
        valid_keys = "".join(str(i) for i in range(1, len(tasks) + 1))
        print(f"  {_DIM}[{valid_keys}] pick   [?] cycles   [s] skip{_RESET}\n")

        key = _pkg("_wiz_read_key")()

        if key in ("s", "q", "\x03"):
            return None
        if key == "?":
            _launch_screen_cycles()
            continue
        if key.isdigit() and 1 <= int(key) <= len(tasks):
            return tasks[int(key) - 1]

def wizard_init(scan: dict = None, dry_run: bool = False) -> None:
    """Run the FTUE wizard. All state is held in memory until Screen 6.

    scan: pre-built ScanResult dict (used by tests and when called from init()).
          If None, runs run_workspace_scan() automatically (Phase 0).
    dry_run: if True, skip writing workspace config + context.md at the end.
    """
    # ── Phase 0: silent scan (skipped if scan provided) ───────────────────
    if scan is None:
        print(f"\n  {_CYAN}›{_RESET} scanning your environment...")
        try:
            scan = _pkg("run_workspace_scan")(deep=False)
            repo_names = ", ".join(r["name"] for r in scan["repos"])
            harness_names = ", ".join(h["name"] for h in scan["harnesses"]) or "none"
            stacks = sorted({l for r in scan["repos"] for l in r["stack_labels"]})
            print(f"  repos found: {len(scan['repos'])}  ·  "
                  f"harnesses: {harness_names}  ·  "
                  f"stacks: {', '.join(stacks) or 'unknown'}\n")
        except Exception as e:
            print(f"  {_YELLOW}⚠ Scan failed: {e}. Continuing with empty scan.{_RESET}")
            scan = {"workspace_name": "my-workspace", "topology": "single",
                    "repos": [], "harnesses": [], "agents": [], "skills": [],
                    "home_harness": None, "scanned_at": ""}

    # ── Landing ────────────────────────────────────────────────────────────
    _pkg("_wiz_screen_landing")()

    # ── Screen 1: Home harness ─────────────────────────────────────────────
    home_harness = _pkg("_wiz_screen_harness")(scan)

    # ── Screen 2: Topology ────────────────────────────────────────────────
    topology = _pkg("_wiz_screen_topology")(scan)

    # ── Screens 2ab + 2c (multi-repo sub-flow) ────────────────────────────
    if topology == "multi":
        while True:
            workspace_pick = _pkg("_wiz_screen_workspace_name_pick")(scan)
            workspace = {
                "workspace_name": workspace_pick["workspace_name"],
                "repos": workspace_pick["repos"],
                "topology": "multi",
                "home_harness": home_harness,
            }
            if _pkg("_wiz_screen_workspace_confirm")(workspace):
                break
    else:
        workspace = {
            "workspace_name": scan.get("workspace_name", "my-workspace"),
            "repos": scan.get("repos", []),
            "topology": topology,
            "home_harness": home_harness,
        }

    # ── Screen 3: Skills ──────────────────────────────────────────────────
    _pkg("_wiz_screen_skills")(scan)

    # ── Screen 4: Agents ─────────────────────────────────────────────────
    _pkg("_wiz_screen_agents")(scan)

    # ── Screen 5: Roles ───────────────────────────────────────────────────
    roles = _pkg("_wiz_screen_roles")(scan)
    workspace["agent_roles"] = roles

    # ── Screen 6: Launch cheat sheet ─────────────────────────────────────
    cfg = _pkg("load_config")()
    _pkg("_wiz_screen_launch")(workspace, scan,
                                auto_launch=cfg.get("auto_launch_after_wizard", True))

    # ── Commit-on-complete: write all state ───────────────────────────────
    if not dry_run:
        ws_name = workspace["workspace_name"]
        config_path = _pkg("write_workspace_config")(workspace, ws_name)
        _pkg("generate_structured_context")({**scan, **workspace})
        print(f"\n  {_GREEN}✓{_RESET} workspace config → {config_path}")

        # Write role blocks into agent directive files
        for harness_name, role_desc in roles.items():
            fname_map = {"claude": "CLAUDE.md", "agy": "GEMINI.md",
                         "grok": "GROK.md", "codex": "AGENTS.md"}
            fname = fname_map.get(harness_name)
            if fname and os.path.exists(fname):
                try:
                    _pkg("_upsert_harness_fence")(
                        fname,
                        harness_version="wizard",
                        body=f"## Your Role\n{role_desc}\n",
                    )
                    print(f"  {_GREEN}✓{_RESET} wrote role to {fname}")
                except Exception:
                    pass
