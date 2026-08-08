def _insert_running_jobs():
    from synlynk import _get_db

    db = _get_db()
    db.executemany(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("ux-job-1", "codex", "first task", "running", "2026-08-08T00:00:00Z"),
            ("ux-job-2", "codex", "second task", "running", "2026-08-08T00:00:00Z"),
        ],
    )
    db.commit()


def test_pending_ux_tip_suggests_tui_when_never_used(project_dir):
    from synlynk.ux_nudges import pending_ux_tip

    _insert_running_jobs()

    tip = pending_ux_tip()

    assert tip is not None
    assert "synlynk tui" in tip.message


def test_pending_ux_tip_none_when_no_active_jobs(project_dir):
    from synlynk.ux_nudges import pending_ux_tip

    assert pending_ux_tip() is None


def test_pending_ux_tip_respects_dismissed_ids(project_dir):
    from synlynk import _update_config
    from synlynk.ux_nudges import pending_ux_tip

    _insert_running_jobs()
    _update_config(
        {
            "nudges": {
                "enabled": True,
                "dismissed_ids": ["ux-tip-tui-watch-live"],
                "last_shown": {},
            }
        }
    )

    assert pending_ux_tip() is None
