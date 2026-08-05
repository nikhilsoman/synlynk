import curses

from synlynk import tui, uxcore


def test_render_fleet_panel_writes_agent_names():
    pad = curses.newpad(10, 80)
    fleet = {
        "codex": uxcore.AgentBucket(
            tasks_done=3, tasks_active=1, total_usd=1.5, success_rate=0.9, alert_count=0
        )
    }
    tui.render_fleet_panel(pad, fleet)
    line = pad.instr(0, 0, 79).decode("utf-8")
    assert "codex" in line


def test_render_jobs_panel_writes_recent_jobs():
    pad = curses.newpad(10, 80)
    jobs = [
        uxcore.JobRun(ts="2026-08-05T00:00:00Z", agent="codex", duration_s=12.5, exit_code=0, cost_usd=0.05)
    ]
    tui.render_jobs_panel(pad, jobs)
    line = pad.instr(0, 0, 79).decode("utf-8")
    assert "codex" in line


def test_render_costs_panel_writes_total():
    pad = curses.newpad(10, 80)
    costs = uxcore.Costs(total_usd=14.20, total_usd_estimated=2.0, by_agent={}, by_stage={})
    tui.render_costs_panel(pad, costs)
    line = pad.instr(0, 0, 79).decode("utf-8")
    assert "14.20" in line


def test_render_review_panel_writes_capability_denied_message():
    pad = curses.newpad(10, 80)
    caps = [uxcore.Capability(name="approve_pr", enabled=False)]
    tui.render_review_panel(pad, caps)
    line = pad.instr(0, 0, 79).decode("utf-8")
    assert "approve_pr" in line
