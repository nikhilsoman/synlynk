"""Classification of Vizor's v0.26.7 write surfaces."""

WRITE_ROUTES = {
    "board/stage": "keep",
    "board/status": "keep",
    "roadmap_studio/approve": "keep",
    "roadmap_studio/hold": "keep",
    "roadmap_studio/revise": "keep",
    "roadmap_studio/drop": "keep",
    "roadmap_studio/reorder": "keep",
    "roadmap_studio/pin": "keep",
    "note": "proxy",
    "sentinel/ack": "keep",
    "sentinel/issue": "keep",
    "roles/create": "keep",
    "roles/charter/update": "keep",
    "dispatch": "hide",
    "approve": "hide",
    "kill": "hide",
    "worktrees/clean": "hide",
    "architect-map/view-pref": "hide",
    "graph/refresh": "hide",
    "tools/install": "hide",
}
