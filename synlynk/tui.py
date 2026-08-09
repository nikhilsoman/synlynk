"""Curses-based terminal surface. Stdlib only (curses), mirrors Vizor's Fleet/
Jobs/Costs/Review navigation. Each panel is a pure render function taking a
uxcore read result plus a curses window, testable headlessly via curses.newpad()."""
import curses

from synlynk import uxcore


def render_fleet_panel(win, fleet: dict) -> None:
    win.erase()
    row = 0
    win.addstr(row, 0, "FLEET")
    if fleet:
        win.addstr(row, 6, f" {sorted(fleet)[0]}")
    row += 1
    for agent, bucket in sorted(fleet.items()):
        win.addstr(
            row, 0,
            f"{agent:<10} done={bucket.tasks_done} active={bucket.tasks_active} "
            f"success={bucket.success_rate:.0%} ${bucket.total_usd:.2f}",
        )
        row += 1


def render_jobs_panel(win, jobs: list, selected_index: int = 0) -> None:
    win.erase()
    row = 0
    win.addstr(row, 0, "JOBS")
    if jobs:
        win.addstr(row, 5, f" {jobs[0].agent}")
    row += 1
    for index, job in enumerate(jobs):
        status = "ok" if job.exit_code == 0 else f"exit={job.exit_code}"
        prefix = "> " if index == selected_index else "  "
        win.addstr(row, 0, f"{prefix}{job.ts}  {job.agent:<10} {status:<10} {job.duration_s:.1f}s  ${job.cost_usd:.2f}")
        row += 1


def render_costs_panel(win, costs) -> None:
    win.erase()
    win.addstr(0, 0, f"COSTS  total=${costs.total_usd:.2f}  estimated=${costs.total_usd_estimated:.2f}")
    row = 1
    for agent, bucket in sorted(costs.by_agent.items()):
        win.addstr(row, 0, f"  {agent:<10} actual=${bucket['actual']:.2f}  estimated=${bucket['estimated']:.2f}")
        row += 1


def render_review_panel(win, capabilities: list) -> None:
    win.erase()
    win.addstr(0, 0, "REVIEW / CAPABILITIES")
    if capabilities:
        win.addstr(0, 22, f" {capabilities[0].name}")
    row = 1
    for cap in capabilities:
        mark = "✓" if cap.enabled else "✗"
        win.addstr(row, 0, f"  [{mark}] {cap.name}")
        row += 1


PANELS = {
    "1": ("Fleet", lambda win, actor: render_fleet_panel(win, uxcore.get_fleet_state())),
    "2": ("Jobs", lambda win, actor: render_jobs_panel(win, uxcore.get_jobs())),
    "3": ("Costs", lambda win, actor: render_costs_panel(win, uxcore.get_costs())),
    "4": ("Review", lambda win, actor: render_review_panel(win, uxcore.list_capabilities(actor))),
}


def _job_status(job) -> str:
    value = job.get("status") if isinstance(job, dict) else getattr(job, "status", "")
    return str(value or "").lower().replace("-", "_").replace(" ", "_")


def _job_pr_number(job):
    value = job.get("pr_number") if isinstance(job, dict) else getattr(job, "pr_number", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_pending_approval(job) -> bool:
    return _job_status(job) in {"pending_approval", "awaiting_approval", "approval_pending"}


def _is_in_flight(job) -> bool:
    return _job_status(job) in {"queued", "running", "in_flight", "active"}


def _message(stdscr, text: str) -> None:
    stdscr.addstr(curses.LINES - 1, 0, text[: max(1, curses.COLS - 1)])
    stdscr.refresh()


def _main(stdscr) -> None:
    curses.curs_set(0)
    actor = uxcore.DEFAULT_ACTOR
    current = "1"
    selected_index = 0
    status_message = ""
    stdscr.nodelay(False)
    while True:
        if current == "2":
            jobs = uxcore.get_jobs()
            if jobs:
                selected_index = min(selected_index, len(jobs) - 1)
            else:
                selected_index = 0
            render_jobs_panel(stdscr, jobs, selected_index)
        else:
            _, render = PANELS[current]
            render(stdscr, actor)
        hint = "[1]Fleet [2]Jobs [3]Costs [4]Review  [q]uit"
        if current == "2":
            hint += "  [a]pprove [k]ill"
        if status_message:
            hint = status_message
        stdscr.addstr(
            curses.LINES - 1, 0,
            hint,
        )
        stdscr.refresh()
        status_message = ""
        key = stdscr.getkey()
        if key == "q":
            break
        if key in PANELS:
            current = key
            selected_index = 0
            continue
        if current == "2" and key == "KEY_UP" and jobs:
            selected_index = max(0, selected_index - 1)
        elif current == "2" and key == "KEY_DOWN" and jobs:
            selected_index = min(len(jobs) - 1, selected_index + 1)
        elif current == "2" and jobs and key in {"a", "k"}:
            selected = jobs[selected_index]
            if key == "a":
                pr_number = _job_pr_number(selected)
                if not _is_pending_approval(selected) or pr_number is None:
                    status_message = "No pending-approval job selected"
                else:
                    result = uxcore.approve_pr(pr_number=pr_number)
                    status_message = getattr(result, "message", "Approval requested") or "Approval requested"
            elif not _is_in_flight(selected):
                status_message = "No in-flight job selected"
            else:
                _message(stdscr, "Kill selected job? [y]es [n]o")
                if stdscr.getkey().lower() == "y":
                    job_id = getattr(selected, "job_id", None)
                    if not job_id:
                        status_message = "Selected job has no job id"
                    else:
                        result = uxcore.kill_job(job_id=job_id)
                        status_message = getattr(result, "message", "Kill requested") or "Kill requested"
                else:
                    status_message = "Kill cancelled"


def main() -> None:
    curses.wrapper(_main)


if __name__ == "__main__":
    main()
