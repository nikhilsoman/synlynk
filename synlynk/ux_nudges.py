"""Terminal UX nudges for underused workspace surfaces."""

TUI_TIP_ID = "ux-tip-tui-watch-live"


def pending_ux_tip():
    """Return the pending TUI tip when enough jobs are active."""
    from synlynk import _get_db, load_config
    from synlynk.fencing import NudgeData

    config = load_config()
    nudges = config.get("nudges", {})
    if not nudges.get("enabled", True):
        return None
    if TUI_TIP_ID in nudges.get("dismissed_ids", []):
        return None

    db = _get_db()
    running_count = db.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE status=?", ("running",)
    ).fetchone()[0]
    if running_count < 2:
        return None

    return NudgeData(
        nudge_id=TUI_TIP_ID,
        title="Underused surface",
        message=f"{running_count} jobs running -- watch them live: synlynk tui",
        follow_up="synlynk tui",
    )
