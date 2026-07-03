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
