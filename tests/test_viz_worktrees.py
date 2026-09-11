from synlynk.viz import VizorHandler, generate_observatory_html, generate_viz_data


def test_observatory_renders_worktree_lifecycle_section():
    data = generate_viz_data()
    obs_snapshot = data.get("observatory") or {}
    obs_snapshot["worktrees"] = [
        {"path": "/tmp/wt1", "branch": "feat/wt1", "verdict": "safe", "reason": "merged to main"},
        {"path": "/tmp/wt2", "branch": "feat/wt2", "verdict": "needs-review", "reason": "unpushed commits"},
    ]
    rendered = generate_observatory_html(obs_snapshot)
    assert "Worktree Lifecycle &amp; Fleet Health" in rendered
    assert "SAFE" in rendered
    assert "Clean Safe Worktrees" in rendered


def test_handler_handle_worktree_clean(monkeypatch):
    monkeypatch.setattr(
        "synlynk.worktree.cmd_worktree_clean",
        lambda **kwargs: '{"dry_run": true, "would_remove": 2, "items": []}',
    )
    handler = VizorHandler.__new__(VizorHandler)
    result = handler._handle_worktree_clean({"dry_run": True})
    assert result["ok"] is True
    assert result["cleaned_count"] == 2
