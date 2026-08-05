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


def render_jobs_panel(win, jobs: list) -> None:
    win.erase()
    row = 0
    win.addstr(row, 0, "JOBS")
    if jobs:
        win.addstr(row, 5, f" {jobs[0].agent}")
    row += 1
    for job in jobs:
        status = "ok" if job.exit_code == 0 else f"exit={job.exit_code}"
        win.addstr(row, 0, f"{job.ts}  {job.agent:<10} {status:<10} {job.duration_s:.1f}s  ${job.cost_usd:.2f}")
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


def _main(stdscr) -> None:
    curses.curs_set(0)
    actor = uxcore.DEFAULT_ACTOR
    current = "1"
    stdscr.nodelay(False)
    while True:
        _, render = PANELS[current]
        render(stdscr, actor)
        stdscr.addstr(
            curses.LINES - 1, 0,
            "[1]Fleet [2]Jobs [3]Costs [4]Review  [q]uit",
        )
        stdscr.refresh()
        key = stdscr.getkey()
        if key == "q":
            break
        if key in PANELS:
            current = key


def main() -> None:
    curses.wrapper(_main)


if __name__ == "__main__":
    main()
