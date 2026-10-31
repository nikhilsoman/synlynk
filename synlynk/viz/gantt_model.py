"""GOVERNS-native Gantt drill model. Stages are columns; tasks are rows."""

COLUMN_PX = 120
LABEL_PX = 260
_STATES = {"done", "active", "blocked", "queued"}


def drill_grid(release: dict, stage_key: str | None = None) -> dict:
    # Callers pass the clicked stage; columns stay the full GOVERNS stage list.
    _ = stage_key
    stages = list(release.get("stages") or [])
    columns = [str(s.get("key") or "") for s in stages]
    rows = []
    wip = {key: 0 for key in columns}
    for stage in stages:
        key = str(stage.get("key") or "")
        for task in stage.get("tasks") or []:
            status = str(task.get("status") or "queued").strip().lower()
            if status == "active":
                wip[key] = wip.get(key, 0) + 1
            rows.append({
                "name": task.get("name") or "",
                "id": task.get("id") or "",
                "agent": task.get("agent") or "",
                "occupying": key,
                "cell_state": status if status in _STATES else "queued",
            })
    return {
        "columns": columns,
        "rows": rows,
        "column_width_px": COLUMN_PX,
        "label_width_px": LABEL_PX,
        "wip": wip,
        "target_date": release.get("target_date") or "",
        "target_date_is_chip": True,
    }
