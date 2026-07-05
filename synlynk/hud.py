"""Terminal HUD for live workspace monitoring."""

from __future__ import annotations

import io
import json
import re
import shutil
import time
from datetime import datetime
from typing import Optional

CYCLES = ["dream", "plan", "work", "ship", "maintain", "engage"]

CYCLE_COLOURS = {
    "dream": "\033[38;5;141m",
    "plan": "\033[38;5;75m",
    "work": "\033[38;5;208m",
    "ship": "\033[38;5;71m",
    "maintain": "\033[38;5;178m",
    "engage": "\033[38;5;43m",
}

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"

SIDEBAR_WIDTH = 18   # chars for the left tube sidebar

_ANSI_RE = re.compile(r"\033\[[0-9;?]*[A-Za-z]")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _elapsed_s(started_at: Optional[str]) -> int:
    dt = _parse_dt(started_at)
    if dt is None:
        return 0
    return max(0, int(time.time() - dt.timestamp()))


def _humanize_seconds(seconds: Optional[int]) -> str:
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _humanize_currency(amount: Optional[float]) -> str:
    if amount is None:
        return "—"
    return f"${amount:.2f}"


def _humanize_tokens(input_tokens: Optional[int], output_tokens: Optional[int]) -> str:
    total = (input_tokens or 0) + (output_tokens or 0)
    if total >= 1000:
        return f"{total/1000:.1f}k"
    return str(total)


def _get_terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.lines, size.columns


def _cursor_to(row: int, col: int) -> str:
    return f"\033[{row + 1};{col + 1}H"


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _truncate_visible(text: str, cols: int) -> str:
    if cols <= 0:
        return ""
    visible = 0
    parts: list[str] = []
    cursor = 0
    for match in _ANSI_RE.finditer(text):
        chunk = text[cursor:match.start()]
        for ch in chunk:
            if visible >= cols:
                return "".join(parts)
            parts.append(ch)
            visible += 1
        parts.append(match.group(0))
        cursor = match.end()
    tail = text[cursor:]
    for ch in tail:
        if visible >= cols:
            return "".join(parts)
        parts.append(ch)
        visible += 1
    return "".join(parts)


class JobSnapshot:
    """Read-only view of `.synlynk/jobs.json`."""

    def __init__(self, jobs_file: str):
        self._path = jobs_file

    def _load(self) -> list:
        try:
            with open(self._path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def active_jobs(self, cycle: Optional[str] = None) -> list:
        jobs = []
        for job in self._load():
            if job.get("status") not in ("running", "queued"):
                continue
            if cycle and job.get("cycle", "work") != cycle:
                continue
            jobs.append({**job, "elapsed_s": _elapsed_s(job.get("started_at"))})
        jobs.sort(key=lambda job: job.get("started_at") or "", reverse=True)
        return jobs

    def recent_jobs(self, n: int = 5, cycle: Optional[str] = None) -> list:
        jobs = []
        for job in self._load():
            if job.get("status") not in ("done", "failed", "error"):
                continue
            if cycle and job.get("cycle", "work") != cycle:
                continue
            jobs.append(job)
        jobs.sort(key=lambda job: job.get("ended_at") or "", reverse=True)
        return jobs[:n]

    def cycle_summary(self) -> dict:
        summary = {cycle: {"running": 0, "ready": True} for cycle in CYCLES}
        for job in self._load():
            if job.get("status") not in ("running", "queued"):
                continue
            cycle = job.get("cycle", "work")
            if cycle not in summary:
                continue
            summary[cycle]["running"] += 1
        for cycle, data in summary.items():
            data["ready"] = data["running"] == 0
        return summary


class HarnessSnapshot:
    """Read harness_status rows from state.db for the watch panel."""

    def __init__(self, db_path: str):
        self._path = db_path

    def load(self) -> dict:
        """Return {agent_name: row} or an empty dict on error."""
        try:
            import sqlite3 as _sq

            conn = _sq.connect(self._path, timeout=1.0)
            conn.row_factory = _sq.Row
            rows = conn.execute("SELECT * FROM harness_status").fetchall()
            conn.close()
            return {row["agent_name"]: dict(row) for row in rows}
        except Exception:
            return {}


class FrameBuffer:
    """Two-frame buffered ANSI renderer."""

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self._prev = [""] * rows
        self._curr = [""] * rows

    def clear(self) -> None:
        self._curr = [""] * self.rows

    def set_line(self, row: int, text: str) -> None:
        if 0 <= row < self.rows:
            self._curr[row] = _truncate_visible(text, self.cols)

    def flush(self) -> str:
        out = io.StringIO()
        out.write("\033[?25l")
        for idx, (prev, curr) in enumerate(zip(self._prev, self._curr)):
            if prev != curr:
                out.write(_cursor_to(idx, 0))
                out.write("\033[2K")
                out.write(curr)
        self._prev = list(self._curr)
        out.write("\033[?25h")
        return out.getvalue()


class HUDRenderer:
    """Ambient workspace HUD."""

    def __init__(self, buf: FrameBuffer):
        self.buf = buf

    def render_error(self, message: str) -> None:
        self.buf.clear()
        self.buf.set_line(0, f"\033[38;5;196m! {message}{RESET}")
        self.buf.set_line(1, "")
        self.buf.set_line(2, f"  {DIM}Press q to quit{RESET}")

    def render_narrow_warning(self, cols: int) -> None:
        self.buf.clear()
        self.buf.set_line(0, f"\033[38;5;178m! terminal too narrow ({cols} cols < 60){RESET}")
        self.buf.set_line(1, f"  {DIM}widen your terminal or use synlynk watch --live{RESET}")
        self.buf.set_line(2, f"  {DIM}Press q to quit{RESET}")

    def render_header(self, cycle_summary: dict, platform_expanded: bool,
                      start_row: int, harness_data: dict = None) -> int:
        """
        Render the platform health header.
        Returns number of rows consumed.
        """
        if harness_data is None:
            harness_data = {}
        rows, cols = self.buf.rows, self.buf.cols
        if not platform_expanded:
            # Collapsed: one line — agent checkmarks + budget summary
            agents = ["claude", "agy", "codex", "grok"]
            parts = []
            for a in agents:
                row = harness_data.get(a, {})
                attached = row.get("attach_point_in_time")
                if attached == 1:
                    parts.append(f"\033[38;5;71m✓ {a}{RESET}")
                elif attached == 0:
                    parts.append(f"\033[38;5;196m✗ {a}{RESET}")
                else:
                    parts.append(f"{DIM}? {a}{RESET}")
            checks = "  ".join(parts)
            line = f"\033[38;5;75m▶ PLATFORM{RESET}  {checks}  [p]"
            self.buf.set_line(start_row, line)
            return 1
        else:
            # Expanded: 5 rows — title, agents, budget bar, harness, collapse hint
            self.buf.set_line(start_row,     f"\033[38;5;75m▼ PLATFORM HEALTH{RESET}  [p] collapse")
            agent_parts = []
            for a in ["claude", "agy", "codex", "grok"]:
                row = harness_data.get(a, {})
                sym = "✓" if row.get("attach_point_in_time") == 1 else "✗"
                ver = row.get("installed_version") or "?"
                agent_parts.append(f"{sym} {a} {DIM}v{ver}{RESET}")
            self.buf.set_line(start_row + 1, "  agents: " + "   ".join(agent_parts))
            total_running = sum(v['running'] for v in cycle_summary.values())
            self.buf.set_line(start_row + 2, f"  budget: {DIM}$— / limit from .synlynk/config.json{RESET}")
            self.buf.set_line(start_row + 3, f"  harness: ✓ compliant  {DIM}· synlynk probe to recheck{RESET}")
            self.buf.set_line(start_row + 4, "")
            return 5

    def render_sidebar(self, cycle_summary: dict, selected_cycle: str,
                       start_row: int, col: int) -> int:
        """
        Render B3 tube-line sidebar. Returns number of rows consumed.
        Each cycle gets a coloured 1-char vertical bar on the left.
        """
        self.buf.set_line(start_row, f"\033[38;5;75m{'synlynk':>{SIDEBAR_WIDTH - 2}}{RESET}")
        row = start_row + 1
        for cycle in CYCLES:
            colour = CYCLE_COLOURS[cycle]
            info = cycle_summary.get(cycle, {"running": 0, "ready": True})
            count = info["running"]
            if count > 0:
                state_str = f"\033[38;5;208m◉ {count} running{RESET}"
            elif info["ready"]:
                state_str = f"{DIM}● ready{RESET}"
            else:
                state_str = f"{DIM}○ idle{RESET}"

            selected = cycle == selected_cycle
            bg = "\033[48;5;235m" if selected else ""
            marker = "◀" if selected else " "
            label = f"{BOLD}{colour}{cycle.capitalize()}{RESET}" if selected else f"{colour}{cycle.capitalize()}{RESET}"
            line = f"{bg}{colour}▌{RESET}{bg} {label} {marker}{RESET}"
            self.buf.set_line(row, line)
            self.buf.set_line(row + 1, f"  {state_str}")
            row += 2

        # Key hint at bottom of sidebar
        self.buf.set_line(row + 1, f"{DIM}  [↑↓] cycle  [p] health{RESET}")
        self.buf.set_line(row + 2, f"{DIM}  [r] refresh  [q] quit{RESET}")
        return row + 3 - start_row

    def render_right_panel(self, selected_cycle: str, active_jobs: list,
                           recent_jobs: list, panel_col: int, start_row: int) -> None:
        """Render cycle-filtered right panel starting at (start_row, panel_col)."""
        colour = CYCLE_COLOURS.get(selected_cycle, RESET)
        row = start_row

        # Panel header
        if active_jobs:
            header = (f"{colour}◉ {selected_cycle.upper()}{RESET} — "
                      f"{len(active_jobs)} running")
        else:
            header = f"{colour}● {selected_cycle.upper()}{RESET} — idle"
        self.buf.set_line(row, (" " * panel_col) + header)
        row += 1

        # Active job cards
        for job in active_jobs:
            elapsed = job.get("elapsed_s", 0)
            mins, secs = divmod(elapsed, 60)
            elapsed_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
            self.buf.set_line(row, (" " * panel_col) +
                f"{colour}┌ {BOLD}{job['agent']}{RESET}{colour} ─────────────────────────────{RESET}")
            self.buf.set_line(row + 1, (" " * panel_col) +
                f"│ {job.get('task', '—')}")
            self.buf.set_line(row + 2, (" " * panel_col) +
                f"{DIM}│ {elapsed_str}  ·  {job.get('status', '—')}{RESET}")
            self.buf.set_line(row + 3, (" " * panel_col) +
                f"{colour}└{'─' * 34}{RESET}")
            row += 4

        # Idle placeholder
        if not active_jobs:
            self.buf.set_line(row, (" " * panel_col) +
                f"{DIM}  no active jobs in this cycle{RESET}")
            self.buf.set_line(row + 1, (" " * panel_col) +
                f"{DIM}  synlynk launch {selected_cycle} to start one{RESET}")
            row += 2

        row += 1  # spacer

        # Readiness section
        self.buf.set_line(row, (" " * panel_col) + f"{DIM}── READINESS{'─' * 20}{RESET}")
        row += 1
        agents_for_cycle = ["claude", "agy", "codex", "grok"]
        line = (" " * panel_col) + "  " + "   ".join(
            f"\033[38;5;71m{a} ✓{RESET}" for a in agents_for_cycle
        )
        self.buf.set_line(row, line)
        row += 2

        # Recent history
        if recent_jobs:
            self.buf.set_line(row, (" " * panel_col) + f"{DIM}── RECENT{'─' * 23}{RESET}")
            row += 1
            for job in recent_jobs[:3]:
                elapsed = job.get("elapsed_s", 0)
                mins, _ = divmod(elapsed, 60)
                status_c = "\033[38;5;71m" if job.get("status") == "done" else "\033[38;5;196m"
                self.buf.set_line(row, (" " * panel_col) +
                    f"  {status_c}✓{RESET} {job['agent']}  {job.get('task','—')[:30]}  "
                    f"{DIM}{mins}m{RESET}")
                row += 1


class LiveRenderer:
    """Compact live job stream."""

    def __init__(self, buf: FrameBuffer):
        self.buf = buf

    def render_error(self, message: str) -> None:
        HUDRenderer(self.buf).render_error(message)

    def render_narrow_warning(self, cols: int) -> None:
        HUDRenderer(self.buf).render_narrow_warning(cols)

    def render(self, active_jobs: list, show_all: bool, refreshed_s: int = 0) -> None:
        """Render full --live frame into buf. Call buf.flush() to emit."""
        self.buf.clear()
        rows, cols = self.buf.rows, self.buf.cols
        row = 0

        # Header
        hint = "[q]quit  [r]refresh  [a]all cycles"
        title = f"\033[38;5;208m◉ synlynk watch --live{RESET}"
        self.buf.set_line(row, f"{title}   {DIM}3s refresh  {hint}{RESET}")
        row += 1
        self.buf.set_line(row, "")
        row += 1

        if not active_jobs:
            self.buf.set_line(row, f"  {DIM}no active jobs{RESET}")
            if not show_all:
                self.buf.set_line(row + 1,
                    f"  {DIM}[a] show all cycles  ·  synlynk watch for full HUD{RESET}")
        else:
            for job in active_jobs:
                elapsed = job.get("elapsed_s", 0)
                mins, secs = divmod(elapsed, 60)
                elapsed_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
                cycle_c = CYCLE_COLOURS.get(job.get("cycle", "work"), RESET)

                self.buf.set_line(row,
                    f"  {cycle_c}┌ {BOLD}{job['agent']}{RESET}{cycle_c} {'─' * 50}{RESET}")
                self.buf.set_line(row + 1,
                    f"  │ {job.get('task', '—')}")
                self.buf.set_line(row + 2,
                    f"  │ {DIM}cycle: {job.get('cycle','work')}  ·  {elapsed_str}  ·  {job.get('status','—')}{RESET}")
                self.buf.set_line(row + 3,
                    f"  {cycle_c}└{'─' * 52}{RESET}")
                row += 5

        # Footer
        n = len(active_jobs)
        footer = f"  {DIM}{n} running  ·  refreshed {refreshed_s}s ago{RESET}"
        self.buf.set_line(rows - 2, footer)
        self.buf.set_line(rows - 1,
            f"  {DIM}synlynk watch for full workspace HUD{RESET}")


def render_observatory_panel(buf: FrameBuffer, jobs: list, rollups: dict, cols: int, start_row: int = 0) -> int:
    """Render the live observatory job board into a framebuffer."""
    jobs = [job for job in jobs if isinstance(job, dict)]
    rollups = rollups or {}
    row = start_row

    header = (
        f"{BOLD}\033[38;5;75mOBSERVATORY{RESET}  "
        f"{_humanize_currency(rollups.get('total_cost'))} total  ·  "
        f"{rollups.get('active_count', 0)} active  ·  "
        f"{rollups.get('total_requests', 0)} reqs  ·  "
        f"{rollups.get('total_tokens', 0)} tokens{RESET}"
    )
    buf.set_line(row, header)
    row += 1

    if not jobs:
        buf.set_line(row, f"{DIM}  no live jobs in this workspace{RESET}")
        return row - start_row + 1

    repos: dict[str, dict[str, list[dict]]] = {}
    for job in jobs:
        repo = str(job.get("repo") or "unknown")
        stage = str(job.get("stage") or job.get("status") or "unknown")
        repos.setdefault(repo, {}).setdefault(stage, []).append(job)

    for repo_name in sorted(repos):
        repo_jobs = sum(len(items) for items in repos[repo_name].values())
        repo_cost = sum(float(job.get("cost_usd") or 0.0) for stage_jobs in repos[repo_name].values() for job in stage_jobs)
        buf.set_line(row, f"{BOLD}{repo_name}{RESET}  {DIM}{repo_jobs} jobs · {_humanize_currency(repo_cost)}{RESET}")
        row += 1
        for stage_name in sorted(repos[repo_name]):
            stage_jobs = repos[repo_name][stage_name]
            buf.set_line(row, f"  {DIM}{stage_name}{RESET}")
            row += 1
            for job in stage_jobs:
                job_id = str(job.get("id") or "—")
                short_id = job_id[-8:] if len(job_id) > 8 else job_id
                agent = str(job.get("agent") or "—")
                age = _humanize_seconds(job.get("runtime_seconds"))
                cost = _humanize_currency(job.get("cost_usd"))
                tokens = _humanize_tokens(job.get("input_tokens"), job.get("output_tokens"))
                line = (
                    f"  {short_id:<8} | {agent:<8} | {age:<8} | {cost:<8} | {tokens}"
                )
                buf.set_line(row, line)
                row += 1
        row += 1

    return row - start_row
