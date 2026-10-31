"""Classification of Vizor's v0.26.7 write surfaces."""

WRITE_ROUTES = {
    "board/stage": "keep",
    "board/status": "keep",
    "note": "proxy",
    "roles/create": "hide",
    "dispatch": "hide",
    "approve": "hide",
    "kill": "hide",
    "worktrees/clean": "hide",
    "architect-map/view-pref": "hide",
    "graph/refresh": "hide",
    "tools/install": "hide",
}
