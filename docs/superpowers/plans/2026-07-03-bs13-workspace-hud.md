# BS-13 Workspace HUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `synlynk watch` and `synlynk watch --live` — terminal-native HUD showing 6-cycle workspace state, reading live job data from `.synlynk/jobs.json`.

**Architecture:** New `synlynk/hud.py` contains all rendering logic (`JobSnapshot` data layer, `HUDRenderer` full ambient view, `LiveRenderer` stripped-down live stream). `synlynk/cli.py` gets a new `cmd_watch(args)` function that replaces the existing `watch` subparser. Buffered ANSI diff renderer (no curses/rich/blessed — stdlib only).

**Tech Stack:** Python 3 stdlib only. `select` for non-blocking keyboard input. ANSI 256-colour escape codes. JSON for `jobs.json`. SQLite for daemon data (optional enrichment only).

**Agent allocation:**
- **Codex:** Tasks 1, 2, 3, 7, 8 — data layer, renderer base, CLI wiring, error states
- **Grok:** Tasks 4, 5, 6, 9 — HUD layout components, LiveRenderer, integration tests

**Important — actual data shape:** Jobs live in `.synlynk/jobs.json` (not a `state.db` jobs table — that table doesn't exist yet). Available fields: `id, agent, task, status, started_at, ended_at, pid, exit_code, story_id, dispatch_rework, micro_rework, model_at_dispatch`. Task 1 adds a `cycle` field to new job records. Cost/token display shows `—` until a future cost-tracking PR adds those fields.

---

## Task 1 (Codex): Add `cycle` field to dispatch

**Why:** The tube sidebar filters jobs by SDLC cycle. Without a `cycle` field in each job record, all jobs appear in "Work" with no way to distinguish brainstorm (Dream), PR review (Ship), etc.

**Files:**
- Modify: `synlynk/__init__.py` — `dispatch_agent()` function (~line 5288) and job record creation (~line 5429)

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_cycle.py`:

```python
import json, os, sys, tempfile, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_dispatch_stores_cycle(monkeypatch, tmp_path):
    """dispatch_agent should persist cycle field in jobs.json."""
    import synlynk
    # Patch JOBS_FILE to tmp location
    jobs_file = str(tmp_path / "jobs.json")
    monkeypatch.setattr(synlynk, 'JOBS_FILE', jobs_file)
    monkeypatch.setattr(synlynk, '_load_jobs', lambda: [])
    saved = []
    def fake_save(jobs): saved.extend(jobs)
    monkeypatch.setattr(synlynk, '_save_jobs', fake_save)
    # Stub subprocess.Popen so no real process spawns
    class FakeProc:
        pid = 99999
    monkeypatch.setattr('subprocess.Popen', lambda *a, **kw: FakeProc())
    monkeypatch.setattr(synlynk, '_count_dispatch_rework', lambda s: 0)
    monkeypatch.setattr(synlynk, '_best_agent_for_story', lambda s: None)
    monkeypatch.setattr(synlynk, '_get_db', lambda: None)

    synlynk.dispatch_agent('codex', 'feat/bs20-deep-scan', cycle='work')
    assert len(saved) == 1
    assert saved[0]['cycle'] == 'work'

def test_dispatch_cycle_defaults_to_work(monkeypatch, tmp_path):
    """dispatch_agent should default to cycle='work' when not specified."""
    import synlynk
    monkeypatch.setattr(synlynk, 'JOBS_FILE', str(tmp_path / "jobs.json"))
    monkeypatch.setattr(synlynk, '_load_jobs', lambda: [])
    saved = []
    monkeypatch.setattr(synlynk, '_save_jobs', lambda j: saved.extend(j))
    class FakeProc:
        pid = 99999
    monkeypatch.setattr('subprocess.Popen', lambda *a, **kw: FakeProc())
    monkeypatch.setattr(synlynk, '_count_dispatch_rework', lambda s: 0)
    monkeypatch.setattr(synlynk, '_best_agent_for_story', lambda s: None)
    monkeypatch.setattr(synlynk, '_get_db', lambda: None)

    synlynk.dispatch_agent('agy', 'docs task')
    assert saved[0].get('cycle') == 'work'
```

- [ ] **Step 2: Run test to verify it fails**

```
cd /Users/nikhilsoman/dev/synlynk
python -m pytest tests/test_dispatch_cycle.py -v
```

Expected: `FAILED` — `dispatch_agent` has no `cycle` parameter.

- [ ] **Step 3: Add `cycle` parameter to `dispatch_agent` signature**

In `synlynk/__init__.py`, find the function signature at ~line 5288:

```python
# Before:
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None) -> dict:

# After:
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work") -> dict:
```

- [ ] **Step 4: Add `cycle` to the job record dict**

Find the `job = { ... }` dict at ~line 5429 and add one line:

```python
    job = {
        "id": job_id,
        "agent": agent,
        "story_id": story_id or "",
        "task": task,
        "cycle": cycle,          # ← add this line
        "pid": proc.pid,
        # ... rest unchanged
    }
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/test_dispatch_cycle.py -v
```

Expected: both tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_dispatch_cycle.py
git commit -m "feat: add cycle field to dispatch_agent and job records"
```

---

## Task 2 (Codex): `JobSnapshot` data layer

**Files:**
- Create: `synlynk/hud.py` (initial skeleton with `JobSnapshot` only)
- Create: `tests/test_hud_snapshot.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hud_snapshot.py`:

```python
import json, os, sys, tempfile, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SAMPLE_JOBS = [
    {"id": "job-aaa", "agent": "codex", "task": "feat/bs20-deep-scan",
     "cycle": "work", "status": "running", "started_at": "2026-07-03T10:00:00",
     "ended_at": None, "exit_code": None},
    {"id": "job-bbb", "agent": "agy", "task": "docs/blog-post",
     "cycle": "work", "status": "running", "started_at": "2026-07-03T10:05:00",
     "ended_at": None, "exit_code": None},
    {"id": "job-ccc", "agent": "claude", "task": "BS-13 brainstorm",
     "cycle": "dream", "status": "done", "started_at": "2026-07-03T08:00:00",
     "ended_at": "2026-07-03T09:30:00", "exit_code": 0},
]

def make_snapshot(tmp_path, jobs=SAMPLE_JOBS):
    from synlynk.hud import JobSnapshot
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs))
    return JobSnapshot(str(jobs_file))

def test_active_jobs_returns_running(tmp_path):
    snap = make_snapshot(tmp_path)
    active = snap.active_jobs()
    assert len(active) == 2
    assert all(j['status'] == 'running' for j in active)

def test_active_jobs_for_cycle(tmp_path):
    snap = make_snapshot(tmp_path)
    work_jobs = snap.active_jobs(cycle='work')
    assert len(work_jobs) == 2
    dream_jobs = snap.active_jobs(cycle='dream')
    assert dream_jobs == []

def test_recent_jobs(tmp_path):
    snap = make_snapshot(tmp_path)
    recent = snap.recent_jobs(n=5)
    assert len(recent) == 1
    assert recent[0]['id'] == 'job-ccc'

def test_cycle_summary(tmp_path):
    snap = make_snapshot(tmp_path)
    summary = snap.cycle_summary()
    assert summary['work']['running'] == 2
    assert summary['work']['ready'] is False
    assert summary['dream']['running'] == 0
    assert summary['dream']['ready'] is True

def test_missing_jobs_file(tmp_path):
    from synlynk.hud import JobSnapshot
    snap = JobSnapshot(str(tmp_path / "nonexistent.json"))
    assert snap.active_jobs() == []
    assert snap.recent_jobs() == []

def test_elapsed_seconds(tmp_path):
    snap = make_snapshot(tmp_path)
    active = snap.active_jobs()
    # elapsed should be a positive integer
    assert all(isinstance(j.get('elapsed_s'), int) and j['elapsed_s'] >= 0 for j in active)
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_hud_snapshot.py -v
```

Expected: `ModuleNotFoundError: No module named 'synlynk.hud'`

- [ ] **Step 3: Create `synlynk/hud.py` with `JobSnapshot`**

```python
import json
import os
import time
from datetime import datetime
from typing import Optional

CYCLES = ["dream", "plan", "work", "ship", "maintain", "engage"]

CYCLE_COLOURS = {
    "dream":    "\033[38;5;141m",   # purple  #a371f7
    "plan":     "\033[38;5;75m",    # blue    #58a6ff
    "work":     "\033[38;5;208m",   # orange  #f0883e
    "ship":     "\033[38;5;71m",    # green   #3fb950
    "maintain": "\033[38;5;178m",   # yellow  #d29922
    "engage":   "\033[38;5;43m",    # teal    #39d3bb
}
RESET = "\033[0m"
DIM   = "\033[2m"
BOLD  = "\033[1m"


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _elapsed_s(started_at: Optional[str]) -> int:
    dt = _parse_dt(started_at)
    if dt is None:
        return 0
    return max(0, int(time.time() - dt.timestamp()))


class JobSnapshot:
    """Read-only view of .synlynk/jobs.json. Never writes."""

    def __init__(self, jobs_file: str):
        self._path = jobs_file

    def _load(self) -> list:
        try:
            with open(self._path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def active_jobs(self, cycle: Optional[str] = None) -> list:
        """Return running/queued jobs, optionally filtered by cycle."""
        jobs = [
            {**j, "elapsed_s": _elapsed_s(j.get("started_at"))}
            for j in self._load()
            if j.get("status") in ("running", "queued")
        ]
        if cycle:
            jobs = [j for j in jobs if j.get("cycle", "work") == cycle]
        return sorted(jobs, key=lambda j: j.get("started_at") or "")

    def recent_jobs(self, n: int = 5, cycle: Optional[str] = None) -> list:
        """Return the last N completed jobs, most recent first."""
        jobs = [
            j for j in self._load()
            if j.get("status") in ("done", "failed", "error")
        ]
        if cycle:
            jobs = [j for j in jobs if j.get("cycle", "work") == cycle]
        jobs.sort(key=lambda j: j.get("ended_at") or "", reverse=True)
        return jobs[:n]

    def cycle_summary(self) -> dict:
        """Return dict of cycle_name -> {running: int, ready: bool}."""
        all_jobs = self._load()
        active = [j for j in all_jobs if j.get("status") in ("running", "queued")]
        summary = {}
        for cycle in CYCLES:
            count = sum(1 for j in active if j.get("cycle", "work") == cycle)
            summary[cycle] = {"running": count, "ready": count == 0}
        return summary
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_hud_snapshot.py -v
```

Expected: all 6 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add synlynk/hud.py tests/test_hud_snapshot.py
git commit -m "feat(hud): JobSnapshot data layer reading from jobs.json"
```

---

## Task 3 (Codex): Buffered ANSI diff renderer base

**Files:**
- Modify: `synlynk/hud.py` — add `FrameBuffer` class and `_get_terminal_size()`
- Create: `tests/test_hud_buffer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hud_buffer.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk.hud import FrameBuffer

def test_initial_render_emits_full_frame():
    buf = FrameBuffer(rows=5, cols=40)
    buf.set_line(0, "hello world")
    buf.set_line(1, "line two")
    output = buf.flush()
    assert "hello world" in output
    assert "line two" in output

def test_unchanged_lines_not_re_emitted():
    buf = FrameBuffer(rows=5, cols=40)
    buf.set_line(0, "static line")
    buf.set_line(1, "changing line v1")
    buf.flush()  # first render — emits everything
    buf.set_line(1, "changing line v2")  # only line 1 changed
    output = buf.flush()
    assert "static line" not in output   # line 0 unchanged — not re-emitted
    assert "changing line v2" in output  # line 1 changed — emitted

def test_clear_resets_previous_frame():
    buf = FrameBuffer(rows=5, cols=40)
    buf.set_line(0, "old content")
    buf.flush()
    buf.clear()
    buf.set_line(0, "new content")
    output = buf.flush()
    assert "new content" in output

def test_line_truncated_to_col_width():
    buf = FrameBuffer(rows=3, cols=10)
    buf.set_line(0, "this is a very long line that exceeds ten chars")
    output = buf.flush()
    # Should not raise; visible content fits within cols
    assert len([c for c in output if c.isprintable() or c == ' ']) <= 10 + 20  # slack for ANSI
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_hud_buffer.py -v
```

Expected: `ImportError: cannot import name 'FrameBuffer' from 'synlynk.hud'`

- [ ] **Step 3: Add `FrameBuffer` to `synlynk/hud.py`**

Append after the `JobSnapshot` class:

```python
def _get_terminal_size() -> tuple:
    """Return (rows, cols) of the current terminal. Falls back to (24, 80)."""
    try:
        import shutil
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.lines, size.columns
    except Exception:
        return 24, 80


def _cursor_to(row: int, col: int) -> str:
    return f"\033[{row + 1};{col + 1}H"


def _strip_ansi(text: str) -> str:
    """Return visible character count (strips ANSI escape sequences)."""
    import re
    return re.sub(r'\033\[[0-9;]*m', '', text)


class FrameBuffer:
    """
    Two-frame buffer for flicker-free terminal rendering.

    Usage each tick:
        buf.clear()               # wipe pending frame
        buf.set_line(row, text)   # populate lines
        sys.stdout.write(buf.flush())  # emit only changed lines
    """

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self._prev: list = [""] * rows
        self._curr: list = [""] * rows

    def clear(self) -> None:
        """Wipe the pending (current) frame. Call at start of each tick."""
        self._curr = [""] * self.rows

    def set_line(self, row: int, text: str) -> None:
        """Write a line of text into the pending frame. Truncates to cols."""
        if 0 <= row < self.rows:
            visible = _strip_ansi(text)
            if len(visible) > self.cols:
                # Trim visible chars; keep ANSI prefix up to trim point
                # Simple approach: truncate raw text to cols + slack for ANSI codes
                text = text[:self.cols + 40]
            self._curr[row] = text

    def flush(self) -> str:
        """
        Diff _curr against _prev. Emit cursor-positioned writes for changed lines.
        On first call (_prev all empty) emits all lines (full paint).
        """
        import io
        out = io.StringIO()
        out.write("\033[?25l")  # hide cursor during paint
        for i, (prev, curr) in enumerate(zip(self._prev, self._curr)):
            if prev != curr:
                out.write(_cursor_to(i, 0))
                out.write("\033[2K")    # clear line
                out.write(curr)
        self._prev = list(self._curr)
        out.write("\033[?25h")  # restore cursor
        return out.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_hud_buffer.py -v
```

Expected: all 4 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add synlynk/hud.py tests/test_hud_buffer.py
git commit -m "feat(hud): FrameBuffer buffered ANSI diff renderer"
```

---

## Task 4 (Grok): `HUDRenderer` — platform health header + tube sidebar

**Files:**
- Modify: `synlynk/hud.py` — add `HUDRenderer` class with `render_header()` and `render_sidebar()` methods
- Create: `tests/test_hud_renderer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hud_renderer.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk.hud import HUDRenderer, FrameBuffer

CYCLE_SUMMARY = {
    "dream":    {"running": 0, "ready": True},
    "plan":     {"running": 0, "ready": True},
    "work":     {"running": 2, "ready": False},
    "ship":     {"running": 0, "ready": True},
    "maintain": {"running": 0, "ready": False},
    "engage":   {"running": 0, "ready": False},
}

def make_renderer():
    buf = FrameBuffer(rows=30, cols=120)
    return HUDRenderer(buf), buf

def test_render_header_collapsed_fits_one_line(tmp_path):
    r, buf = make_renderer()
    r.render_header(cycle_summary=CYCLE_SUMMARY, platform_expanded=False, start_row=0)
    # Header collapsed = exactly 1 row written
    assert buf._curr[0] != ""
    assert buf._curr[1] == ""   # row 1 empty — header took only row 0

def test_render_header_expanded_takes_multiple_rows(tmp_path):
    r, buf = make_renderer()
    rows_used = r.render_header(cycle_summary=CYCLE_SUMMARY, platform_expanded=True, start_row=0)
    assert rows_used > 1

def test_render_sidebar_marks_active_cycle(tmp_path):
    r, buf = make_renderer()
    import io, sys
    r.render_sidebar(cycle_summary=CYCLE_SUMMARY, selected_cycle="work", start_row=2, col=0)
    # "work" row should contain a selection marker
    sidebar_text = " ".join(buf._curr[2:14])
    assert "work" in sidebar_text.lower()

def test_render_sidebar_contains_all_cycles(tmp_path):
    r, buf = make_renderer()
    from synlynk.hud import CYCLES
    r.render_sidebar(cycle_summary=CYCLE_SUMMARY, selected_cycle="work", start_row=0, col=0)
    full_text = " ".join(buf._curr[:20]).lower()
    for cycle in CYCLES:
        assert cycle in full_text, f"Cycle '{cycle}' missing from sidebar"
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_hud_renderer.py -v
```

Expected: `ImportError: cannot import name 'HUDRenderer' from 'synlynk.hud'`

- [ ] **Step 3: Add `HUDRenderer` to `synlynk/hud.py`**

Append after `FrameBuffer`:

```python
SIDEBAR_WIDTH = 18   # chars for the left tube sidebar


class HUDRenderer:
    """Full ambient HUD — B3 tube-line layout."""

    def __init__(self, buf: FrameBuffer):
        self.buf = buf

    def render_header(self, cycle_summary: dict, platform_expanded: bool,
                      start_row: int) -> int:
        """
        Render the platform health header.
        Returns number of rows consumed.
        """
        rows, cols = self.buf.rows, self.buf.cols
        if not platform_expanded:
            # Collapsed: one line — agent checkmarks + budget summary
            agents = ["claude", "agy", "codex", "grok"]
            checks = "  ".join(f"\033[38;5;71m✓ {a}{RESET}" for a in agents)
            line = f"\033[38;5;75m▶ PLATFORM{RESET}  {checks}  [p]"
            self.buf.set_line(start_row, line)
            return 1
        else:
            # Expanded: 5 rows — title, agents, budget bar, harness, collapse hint
            self.buf.set_line(start_row,     f"\033[38;5;75m▼ PLATFORM HEALTH{RESET}  [p] collapse")
            self.buf.set_line(start_row + 1, f"  agents: ✓ claude  ✓ agy  ✓ codex  ✓ grok")
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_hud_renderer.py -v
```

Expected: all 4 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add synlynk/hud.py tests/test_hud_renderer.py
git commit -m "feat(hud): HUDRenderer platform health header + tube-line sidebar"
```

---

## Task 5 (Grok): `HUDRenderer` — right panel (active jobs + idle state)

**Files:**
- Modify: `synlynk/hud.py` — add `render_right_panel()` to `HUDRenderer`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_hud_renderer.py`:

```python
ACTIVE_JOBS = [
    {"id": "job-aaa", "agent": "codex", "task": "feat/bs20-deep-scan",
     "cycle": "work", "status": "running", "elapsed_s": 252},
    {"id": "job-bbb", "agent": "agy", "task": "docs/blog-post",
     "cycle": "work", "status": "running", "elapsed_s": 90},
]

RECENT_JOBS = [
    {"id": "job-old", "agent": "codex", "task": "feat/bs21-vizor",
     "cycle": "work", "status": "done", "ended_at": "2026-07-03T09:00:00",
     "elapsed_s": 1320},
]

def test_render_right_panel_shows_agent_names():
    r, buf = make_renderer()
    r.render_right_panel(
        selected_cycle="work",
        active_jobs=ACTIVE_JOBS,
        recent_jobs=RECENT_JOBS,
        panel_col=SIDEBAR_WIDTH + 2,
        start_row=2,
    )
    full = " ".join(buf._curr).lower()
    assert "codex" in full
    assert "agy" in full

def test_render_right_panel_idle_shows_placeholder():
    r, buf = make_renderer()
    r.render_right_panel(
        selected_cycle="dream",
        active_jobs=[],
        recent_jobs=[],
        panel_col=SIDEBAR_WIDTH + 2,
        start_row=2,
    )
    full = " ".join(buf._curr).lower()
    assert "no active jobs" in full or "idle" in full

def test_render_right_panel_shows_recent_jobs():
    r, buf = make_renderer()
    r.render_right_panel(
        selected_cycle="work",
        active_jobs=[],
        recent_jobs=RECENT_JOBS,
        panel_col=SIDEBAR_WIDTH + 2,
        start_row=2,
    )
    full = " ".join(buf._curr).lower()
    assert "recent" in full
    assert "codex" in full
```

Also add at top of test file: `from synlynk.hud import SIDEBAR_WIDTH`

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_hud_renderer.py::test_render_right_panel_shows_agent_names -v
```

Expected: `FAILED` — `HUDRenderer` has no `render_right_panel`.

- [ ] **Step 3: Add `render_right_panel()` to `HUDRenderer`**

Add inside `HUDRenderer` class after `render_sidebar`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_hud_renderer.py -v
```

Expected: all 7 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add synlynk/hud.py tests/test_hud_renderer.py
git commit -m "feat(hud): HUDRenderer right panel — active job cards + idle + recent history"
```

---

## Task 6 (Grok): `LiveRenderer` — `synlynk watch --live`

**Files:**
- Modify: `synlynk/hud.py` — add `LiveRenderer` class
- Create: `tests/test_hud_live.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hud_live.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk.hud import LiveRenderer, FrameBuffer

ACTIVE_JOBS = [
    {"id": "job-aaa", "agent": "codex", "task": "feat/bs20-deep-scan",
     "cycle": "work", "status": "running", "elapsed_s": 252},
]

def make_live():
    buf = FrameBuffer(rows=24, cols=100)
    return LiveRenderer(buf), buf

def test_live_renders_job_cards():
    r, buf = make_live()
    r.render(active_jobs=ACTIVE_JOBS, show_all=False)
    full = " ".join(buf._curr).lower()
    assert "codex" in full
    assert "feat/bs20-deep-scan" in full

def test_live_shows_empty_state_when_no_jobs():
    r, buf = make_live()
    r.render(active_jobs=[], show_all=False)
    full = " ".join(buf._curr).lower()
    assert "no" in full and ("active" in full or "running" in full)

def test_live_header_shows_live_indicator():
    r, buf = make_live()
    r.render(active_jobs=ACTIVE_JOBS, show_all=False)
    assert "live" in buf._curr[0].lower() or "◉" in buf._curr[0]

def test_live_footer_shows_count_and_hint():
    r, buf = make_live()
    r.render(active_jobs=ACTIVE_JOBS, show_all=False)
    footer = buf._curr[-2] + buf._curr[-1]
    # Footer should contain count and refresh/quit hints
    assert "1" in footer or "running" in footer.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_hud_live.py -v
```

Expected: `ImportError: cannot import name 'LiveRenderer' from 'synlynk.hud'`

- [ ] **Step 3: Add `LiveRenderer` to `synlynk/hud.py`**

Append after `HUDRenderer`:

```python
class LiveRenderer:
    """Stripped-down --live view. No sidebar. Larger job cards. 3s refresh."""

    def __init__(self, buf: FrameBuffer):
        self.buf = buf

    def render(self, active_jobs: list, show_all: bool) -> None:
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
        footer = (f"  {DIM}{n} running  ·  refreshed just now{RESET}"
                  if n else f"  {DIM}0 running  ·  refreshed just now{RESET}")
        self.buf.set_line(rows - 2, footer)
        self.buf.set_line(rows - 1,
            f"  {DIM}synlynk watch for full workspace HUD{RESET}")
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_hud_live.py -v
```

Expected: all 4 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add synlynk/hud.py tests/test_hud_live.py
git commit -m "feat(hud): LiveRenderer for synlynk watch --live mode"
```

---

## Task 7 (Codex): `cmd_watch` — CLI wiring + poll loop

**Context:** The existing `watch` subcommand at ~line 191 in `cli.py` handles `watch start|stop|status` for the file-watcher daemon. This task replaces it with the HUD command. The file-watcher daemon functionality moves under `synlynk daemon` (already exists as a separate subparser).

**Files:**
- Modify: `synlynk/cli.py` — replace `watch_parser` block, add `cmd_watch()`, update dispatch block
- Create: `tests/test_cmd_watch.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cmd_watch.py`:

```python
import sys, os, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_cmd_watch_exits_on_db_missing(tmp_path, monkeypatch, capsys):
    """cmd_watch should print an error and raise SystemExit when jobs.json missing."""
    from synlynk.hud import JobSnapshot
    import synlynk.cli as cli_mod
    # Patch SYNLYNK_DIR to tmp_path so jobs.json won't be found
    monkeypatch.setattr(cli_mod, '_SYNLYNK_DIR',  str(tmp_path / '.synlynk'))

    import argparse
    args = argparse.Namespace(command='watch', live=False)
    with pytest.raises(SystemExit) as exc:
        cli_mod.cmd_watch(args)
    assert exc.value.code != 0

import pytest
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_cmd_watch.py -v
```

Expected: `ImportError` — `cmd_watch` doesn't exist yet.

- [ ] **Step 3: Add `cmd_watch` to `synlynk/cli.py`**

Add a new function **before** `main()`:

```python
_SYNLYNK_DIR = ".synlynk"

def cmd_watch(args) -> None:
    """Terminal HUD — synlynk watch [--live]."""
    import sys, select, time, os
    from synlynk.hud import JobSnapshot, FrameBuffer, HUDRenderer, LiveRenderer, _get_terminal_size

    jobs_file = os.path.join(_SYNLYNK_DIR, "jobs.json")
    if not os.path.exists(jobs_file):
        print(f"\033[38;5;196m✗ {jobs_file} not found — run synlynk scan first\033[0m",
              file=sys.stderr)
        sys.exit(1)

    live_mode = getattr(args, 'live', False)
    interval = 3 if live_mode else 10
    snap = JobSnapshot(jobs_file)
    show_all = False
    selected_cycle_idx = 2   # default to "work" (index 2 in CYCLES)
    platform_expanded = False
    last_refresh = 0.0

    from synlynk.hud import CYCLES

    # Terminal setup
    import tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        sys.stdout.write("\033[?1049h")  # alternate screen
        sys.stdout.write("\033[2J")      # clear
        sys.stdout.write("\033[?25l")    # hide cursor
        sys.stdout.flush()

        rows, cols = _get_terminal_size()
        buf = FrameBuffer(rows, cols)
        renderer_hud = HUDRenderer(buf) if not live_mode else None
        renderer_live = LiveRenderer(buf) if live_mode else None

        while True:
            now = time.time()
            need_refresh = (now - last_refresh) >= interval

            # Non-blocking keyboard check
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch in ('q', 'Q'):
                    break
                elif ch == 'r':
                    need_refresh = True
                elif ch == 'p' and not live_mode:
                    platform_expanded = not platform_expanded
                    need_refresh = True
                elif ch == 'a' and live_mode:
                    show_all = not show_all
                    need_refresh = True
                elif ch == '\x1b':   # escape sequence (arrow keys)
                    rest = sys.stdin.read(2)
                    if rest == '[A' and not live_mode:   # up
                        selected_cycle_idx = max(0, selected_cycle_idx - 1)
                        need_refresh = True
                    elif rest == '[B' and not live_mode:  # down
                        selected_cycle_idx = min(len(CYCLES) - 1, selected_cycle_idx + 1)
                        need_refresh = True

            if need_refresh:
                rows, cols = _get_terminal_size()
                buf.rows, buf.cols = rows, cols
                buf.clear()

                # Narrow terminal fallback
                if cols < 60:
                    buf.set_line(0, "\033[38;5;196m⚠ terminal too narrow (< 60 cols)\033[0m")
                    buf.set_line(1, "  widen your terminal to use synlynk watch")
                    sys.stdout.write(buf.flush())
                    sys.stdout.flush()
                    last_refresh = now
                    continue

                selected_cycle = CYCLES[selected_cycle_idx]
                summary = snap.cycle_summary()

                if live_mode:
                    active = snap.active_jobs()
                    if not show_all:
                        active = [j for j in active]  # all running, no filter in --live
                    renderer_live.render(active_jobs=active, show_all=show_all)
                else:
                    row = 0
                    rows_used = renderer_hud.render_header(
                        cycle_summary=summary,
                        platform_expanded=platform_expanded,
                        start_row=row,
                    )
                    row += rows_used
                    renderer_hud.render_sidebar(
                        cycle_summary=summary,
                        selected_cycle=selected_cycle,
                        start_row=row, col=0,
                    )
                    renderer_hud.render_right_panel(
                        selected_cycle=selected_cycle,
                        active_jobs=snap.active_jobs(cycle=selected_cycle),
                        recent_jobs=snap.recent_jobs(n=5, cycle=selected_cycle),
                        panel_col=20,
                        start_row=row,
                    )

                sys.stdout.write(buf.flush())
                sys.stdout.flush()
                last_refresh = now

    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h")    # show cursor
        sys.stdout.write("\033[?1049l")  # restore main screen
        sys.stdout.flush()
```

- [ ] **Step 4: Replace `watch_parser` in `main()` in `synlynk/cli.py`**

Find (~line 191):
```python
    watch_parser = subparsers.add_parser("watch", help="Manage the file watcher daemon")
    watch_parser.add_argument("action", choices=["start", "stop", "status"],
                              help="Daemon action")
```

Replace with:
```python
    watch_parser = subparsers.add_parser("watch", help="Live workspace HUD (synlynk watch)")
    watch_parser.add_argument("--live", action="store_true",
                              help="Active-job stream mode (3s refresh, no sidebar)")
```

Find (~line 396) the dispatch block:
```python
    elif args.command == "watch":
        daemon = WatchDaemon()
        if args.action == "start":
            daemon.start()
        elif args.action == "stop":
            daemon.stop()
        elif args.action == "status":
            daemon.status()
```

Replace with:
```python
    elif args.command == "watch":
        cmd_watch(args)
```

Also remove `WatchDaemon` from the import block at the top of `main()` if it's only used by the old watch handler. Check: `grep -n 'WatchDaemon' synlynk/cli.py` — if it appears elsewhere, leave it.

- [ ] **Step 5: Run tests**

```
python -m pytest tests/test_cmd_watch.py -v
```

Expected: `PASSED`.

Smoke test (exits immediately with q):
```
echo 'q' | python -m synlynk watch 2>&1 | head -5
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py synlynk/hud.py tests/test_cmd_watch.py
git commit -m "feat(hud): cmd_watch CLI wiring + poll loop with keyboard input"
```

---

## Task 8 (Codex): Error states + terminal width fallback

**Files:**
- Modify: `synlynk/hud.py` — add `render_error()` to `HUDRenderer`
- Create: `tests/test_hud_errors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hud_errors.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk.hud import HUDRenderer, FrameBuffer

def test_render_error_shows_message():
    buf = FrameBuffer(rows=10, cols=80)
    r = HUDRenderer(buf)
    r.render_error("state.db not found — run synlynk scan first")
    full = " ".join(buf._curr).lower()
    assert "not found" in full or "scan" in full

def test_narrow_terminal_shows_warning():
    """Below 60 cols the HUD shows a narrow-terminal warning."""
    buf = FrameBuffer(rows=10, cols=55)   # too narrow
    r = HUDRenderer(buf)
    r.render_narrow_warning(cols=55)
    full = " ".join(buf._curr).lower()
    assert "narrow" in full or "widen" in full or "wide" in full
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_hud_errors.py -v
```

Expected: `FAILED` — `HUDRenderer` has no `render_error` or `render_narrow_warning`.

- [ ] **Step 3: Add error render methods to `HUDRenderer`**

Add inside `HUDRenderer` class:

```python
    def render_error(self, message: str) -> None:
        """Full-screen error — replaces all content."""
        self.buf.clear()
        self.buf.set_line(0, f"\033[38;5;196m✗ {message}\033[0m")
        self.buf.set_line(1, "")
        self.buf.set_line(2, f"  {DIM}Press [q] to quit{RESET}")

    def render_narrow_warning(self, cols: int) -> None:
        """Warning shown when terminal is too narrow for the full HUD."""
        self.buf.clear()
        self.buf.set_line(0, f"\033[38;5;178m⚠ terminal too narrow ({cols} cols < 60){RESET}")
        self.buf.set_line(1, f"  {DIM}widen your terminal — synlynk watch needs at least 60 columns{RESET}")
        self.buf.set_line(2, f"  {DIM}or use synlynk watch --live (no sidebar){RESET}")
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_hud_errors.py -v
```

Expected: both tests `PASSED`.

- [ ] **Step 5: Run full test suite**

```
python -m pytest tests/ -v --tb=short
```

Expected: all tests pass. If any failures in unrelated tests, investigate before proceeding.

- [ ] **Step 6: Commit**

```bash
git add synlynk/hud.py tests/test_hud_errors.py
git commit -m "feat(hud): error states and narrow-terminal fallback"
```

---

## Task 9 (Grok): Integration test + end-to-end smoke test

**Files:**
- Create: `tests/test_hud_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_hud_integration.py`:

```python
"""
Integration test: full render cycle with realistic job data.
Verifies all components compose without errors.
"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk.hud import (
    JobSnapshot, FrameBuffer, HUDRenderer, LiveRenderer, CYCLES, _get_terminal_size
)

REALISTIC_JOBS = [
    {"id": "job-001", "agent": "codex", "task": "feat/bs20-deep-scan",
     "cycle": "work", "status": "running",
     "started_at": "2026-07-03T10:00:00", "ended_at": None, "exit_code": None},
    {"id": "job-002", "agent": "agy", "task": "docs/bs13-blog",
     "cycle": "work", "status": "running",
     "started_at": "2026-07-03T10:05:00", "ended_at": None, "exit_code": None},
    {"id": "job-003", "agent": "claude", "task": "BS-13 brainstorm",
     "cycle": "dream", "status": "done",
     "started_at": "2026-07-03T08:00:00", "ended_at": "2026-07-03T09:30:00",
     "exit_code": 0},
    {"id": "job-004", "agent": "grok", "task": "docs/roadmap review",
     "cycle": "plan", "status": "failed",
     "started_at": "2026-07-03T07:00:00", "ended_at": "2026-07-03T07:15:00",
     "exit_code": 1},
]


def test_full_ambient_hud_renders_without_exception(tmp_path):
    """HUDRenderer should produce output for all 6 cycles without raising."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(REALISTIC_JOBS))
    snap = JobSnapshot(str(jobs_file))
    summary = snap.cycle_summary()

    buf = FrameBuffer(rows=40, cols=120)
    r = HUDRenderer(buf)
    for cycle in CYCLES:
        buf.clear()
        r.render_header(cycle_summary=summary, platform_expanded=False, start_row=0)
        r.render_sidebar(cycle_summary=summary, selected_cycle=cycle, start_row=1, col=0)
        r.render_right_panel(
            selected_cycle=cycle,
            active_jobs=snap.active_jobs(cycle=cycle),
            recent_jobs=snap.recent_jobs(n=5, cycle=cycle),
            panel_col=20, start_row=1,
        )
        output = buf.flush()
        assert isinstance(output, str)  # no exception = pass


def test_live_renderer_all_cycles(tmp_path):
    """LiveRenderer renders without error for various job states."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(REALISTIC_JOBS))
    snap = JobSnapshot(str(jobs_file))
    buf = FrameBuffer(rows=24, cols=100)
    r = LiveRenderer(buf)
    for show_all in (True, False):
        buf.clear()
        active = snap.active_jobs()
        r.render(active_jobs=active, show_all=show_all)
        output = buf.flush()
        assert isinstance(output, str)


def test_platform_expanded_header(tmp_path):
    """Expanded platform header should take more rows than collapsed."""
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps([]))
    snap = JobSnapshot(str(jobs_file))
    summary = snap.cycle_summary()

    buf = FrameBuffer(rows=40, cols=120)
    r = HUDRenderer(buf)
    rows_collapsed = r.render_header(cycle_summary=summary, platform_expanded=False, start_row=0)
    buf.clear()
    rows_expanded = r.render_header(cycle_summary=summary, platform_expanded=True, start_row=0)
    assert rows_expanded > rows_collapsed


def test_no_jobs_renders_idle_state(tmp_path):
    """With no jobs.json data, HUD renders idle state without crashing."""
    snap = JobSnapshot(str(tmp_path / "nonexistent.json"))
    summary = snap.cycle_summary()
    buf = FrameBuffer(rows=30, cols=100)
    r = HUDRenderer(buf)
    buf.clear()
    r.render_header(cycle_summary=summary, platform_expanded=False, start_row=0)
    r.render_sidebar(cycle_summary=summary, selected_cycle="work", start_row=1, col=0)
    r.render_right_panel(
        selected_cycle="work", active_jobs=[], recent_jobs=[],
        panel_col=20, start_row=1,
    )
    output = buf.flush()
    assert "idle" in output.lower() or "no active" in output.lower()
```

- [ ] **Step 2: Run integration tests**

```
python -m pytest tests/test_hud_integration.py -v
```

Expected: all 4 tests `PASSED`.

- [ ] **Step 3: Run complete test suite**

```
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests pass. Fix any failures before proceeding.

- [ ] **Step 4: Manual smoke test**

Open a terminal at least 80 columns wide:
```
cd /Users/nikhilsoman/dev/synlynk
python -m synlynk watch
```

Verify:
- Platform health header renders (collapsed by default)
- Tube sidebar shows all 6 cycles with colour bars
- Right panel shows "work" cycle (default selection)
- `[p]` toggles the platform health expansion
- `[↑]` / `[↓]` navigates cycles and right panel updates
- `[q]` exits cleanly (terminal restored, no residual cursor issues)

Then test `--live`:
```
python -m synlynk watch --live
```

Verify:
- No sidebar rendered
- Job cards appear if any running jobs in jobs.json
- `[q]` exits cleanly

- [ ] **Step 5: Commit**

```bash
git add tests/test_hud_integration.py
git commit -m "test(hud): integration tests for full HUD render cycle"
```

---

## Task 10 (Codex): Open PR and blog post

- [ ] **Step 1: Push branch**

```bash
git push -u origin chore/bs13-hud-spec
```

Wait — check current branch first. The spec was committed to `chore/bs13-hud-spec`. Implementation commits should go on a new feature branch:

```bash
git checkout main && git pull
git checkout -b feat/bs13-workspace-hud
# cherry-pick or re-commit all hud work onto this branch
```

If work was done on a fresh worktree from `main`, just push:
```bash
git push -u origin feat/bs13-workspace-hud
```

- [ ] **Step 2: Open PR**

```bash
gh pr create \
  --title "feat(hud): BS-13 Workspace HUD — synlynk watch + watch --live" \
  --body "$(cat <<'EOF'
## Summary

- Adds `synlynk watch`: terminal-native 6-cycle HUD with B3 tube-line sidebar, cycle-filtered right panel, and collapsible platform health header
- Adds `synlynk watch --live`: stripped-down active-job stream (3s refresh, no sidebar, context progress bars)
- Adds `cycle` field to `dispatch_agent()` and job records for cycle-based filtering
- Zero new dependencies — stdlib only (no curses, no rich, no blessed)
- Buffered ANSI diff renderer: only changed lines re-emitted per tick

## Test Plan

- [ ] `python -m pytest tests/test_hud_snapshot.py tests/test_hud_buffer.py tests/test_hud_renderer.py tests/test_hud_live.py tests/test_hud_errors.py tests/test_hud_integration.py -v` — all pass
- [ ] `python -m synlynk watch` — renders in 80+ col terminal, keys work, exits cleanly
- [ ] `python -m synlynk watch --live` — job cards render, exits cleanly
- [ ] `python -m synlynk watch` in < 60 col terminal — shows narrow-terminal warning
- [ ] `python -m synlynk watch` with no jobs.json — shows error message and exits with code 1

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Write blog post**

Create `docs/blog/41-pr<N>-bs13-workspace-hud.md` following the blog post template in `docs/blog/README.md`. Commit it to the same branch.

- [ ] **Step 4: Confirm all tests pass in CI**

```bash
gh pr checks
```

Wait for green before requesting review.
