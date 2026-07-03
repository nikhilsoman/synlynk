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

    def render_header(self, cycle_summary: dict, platform_expanded: bool, start_row: int) -> int:
        running = sum(item.get("running", 0) for item in cycle_summary.values())
        if not platform_expanded:
            self.buf.set_line(
                start_row,
                f"\033[38;5;75m▶ PLATFORM{RESET}  {running} active jobs  [p] expand",
            )
            return 1

        self.buf.set_line(start_row, f"\033[38;5;75m▼ PLATFORM HEALTH{RESET}  [p] collapse")
        self.buf.set_line(
            start_row + 1,
            "  agents: " + "  ".join(f"✓ {name}" for name in ("claude", "agy", "codex", "grok")),
        )
        self.buf.set_line(start_row + 2, f"  budget: {DIM}—{RESET}")
        self.buf.set_line(start_row + 3, f"  harness: {DIM}—{RESET}")
        self.buf.set_line(start_row + 4, "")
        return 5

    def render_sidebar(self, cycle_summary: dict, selected_cycle: str, start_row: int, col: int) -> int:
        prefix = " " * col
        row = start_row
        self.buf.set_line(row, f"{prefix}synlynk")
        row += 1
        for cycle in CYCLES:
            info = cycle_summary.get(cycle, {"running": 0, "ready": True})
            marker = "◀" if cycle == selected_cycle else " "
            if info["running"]:
                state = f"{info['running']} running"
            elif info["ready"]:
                state = "ready"
            else:
                state = "idle"
            color = CYCLE_COLOURS.get(cycle, RESET)
            self.buf.set_line(row, f"{prefix}{color}▌{RESET} {marker} {cycle.capitalize():<9} {state}")
            row += 1
        self.buf.set_line(row, f"{prefix}{DIM}[↑↓] cycle  [p] health{RESET}")
        self.buf.set_line(row + 1, f"{prefix}{DIM}[r] refresh [q] quit{RESET}")
        return row + 2 - start_row

    def render_right_panel(
        self,
        selected_cycle: str,
        active_jobs: list,
        recent_jobs: list,
        panel_col: int,
        start_row: int,
    ) -> None:
        prefix = " " * panel_col
        color = CYCLE_COLOURS.get(selected_cycle, RESET)
        row = start_row
        if active_jobs:
            self.buf.set_line(row, f"{prefix}{color}◉ {selected_cycle.upper()}{RESET} — {len(active_jobs)} running")
            row += 1
            for job in active_jobs:
                elapsed = job.get("elapsed_s", 0)
                mins, secs = divmod(elapsed, 60)
                elapsed_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
                self.buf.set_line(row, f"{prefix}{BOLD}{job.get('agent', '—')}{RESET}  {job.get('task', '—')}")
                self.buf.set_line(
                    row + 1,
                    f"{prefix}{DIM}{job.get('cycle', selected_cycle)}  {elapsed_str}  {job.get('status', '—')}{RESET}",
                )
                row += 3
        else:
            self.buf.set_line(row, f"{prefix}{DIM}no active jobs in this cycle{RESET}")
            self.buf.set_line(row + 1, f"{prefix}{DIM}run synlynk launch {selected_cycle} to start one{RESET}")
            row += 3

        self.buf.set_line(row, f"{prefix}{DIM}recent{RESET}")
        row += 1
        for job in recent_jobs[:3]:
            self.buf.set_line(
                row,
                f"{prefix}✓ {job.get('agent', '—')}  {job.get('task', '—')[:30]}",
            )
            row += 1


class LiveRenderer:
    """Compact live job stream."""

    def __init__(self, buf: FrameBuffer):
        self.buf = buf

    def render_error(self, message: str) -> None:
        HUDRenderer(self.buf).render_error(message)

    def render_narrow_warning(self, cols: int) -> None:
        HUDRenderer(self.buf).render_narrow_warning(cols)

    def render(self, active_jobs: list, show_all: bool) -> None:
        self.buf.clear()
        self.buf.set_line(
            0,
            f"\033[38;5;208m◉ synlynk watch --live{RESET}   {DIM}3s refresh  [q]quit [r]refresh [a]all cycles{RESET}",
        )
        row = 2
        if not active_jobs:
            self.buf.set_line(row, f"{DIM}no active jobs{RESET}")
            if not show_all:
                self.buf.set_line(row + 1, f"{DIM}[a] show all cycles  ·  synlynk watch for full HUD{RESET}")
        else:
            for job in active_jobs:
                color = CYCLE_COLOURS.get(job.get("cycle", "work"), RESET)
                elapsed = job.get("elapsed_s", 0)
                mins, secs = divmod(elapsed, 60)
                elapsed_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
                self.buf.set_line(row, f"{color}┌ {BOLD}{job.get('agent', '—')}{RESET}")
                self.buf.set_line(row + 1, f"│ {job.get('task', '—')}")
                self.buf.set_line(
                    row + 2,
                    f"{DIM}│ {job.get('cycle', 'work')}  ·  {elapsed_str}  ·  {job.get('status', '—')}{RESET}",
                )
                self.buf.set_line(row + 3, f"{color}└{'─' * 24}{RESET}")
                row += 5
        self.buf.set_line(self.buf.rows - 2, f"{DIM}{len(active_jobs)} running{RESET}")
        self.buf.set_line(self.buf.rows - 1, f"{DIM}synlynk watch for full workspace HUD{RESET}")
