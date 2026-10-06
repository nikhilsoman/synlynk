"""GOVERNS linkage preflight is a warning until #1990's hard-fail ships."""

import synlynk as sl
import synlynk.dispatch as dispatch_mod

_WARNING = (
    "GOVERNS linkage missing — dispatch proceeding, but this will hard-fail once #1990 ships"
)


class _FakeProc:
    pid = 4242

    def poll(self):
        return None


def _quiet_unrelated_preflight(monkeypatch):
    """Keep probe and auth from failing the job before the GOVERNS check."""
    monkeypatch.setattr(dispatch_mod, "_read_harness_probe_row", lambda *a, **k: ("ok", "[]"))
    monkeypatch.setattr(dispatch_mod, "_preflight_auth_check", lambda *a, **k: None)
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **k: _FakeProc())


def test_dispatch_warns_and_proceeds_without_governs_linkage(project_dir, monkeypatch, capsys):
    _quiet_unrelated_preflight(monkeypatch)

    job = sl.dispatch_agent(
        "codex",
        "add a unit test for the helper",
        force_agent=True,
        context_mode="none",
    )

    captured = capsys.readouterr()
    assert _WARNING in captured.out
    sentinel = (project_dir / ".synlynk" / "sentinel.md").read_text()
    assert _WARNING in sentinel
    assert "GOVERNS_LINKAGE_MISSING" in sentinel
    assert job["id"].startswith("job-")
    assert job["pid"] == 4242
    assert job["status"] == "running"


def test_dispatch_with_linked_governs_story_is_unchanged(project_dir, monkeypatch, capsys):
    _quiet_unrelated_preflight(monkeypatch)
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion) VALUES (?, ?, ?)",
        ("goal-1", "ship the warning", "warning is live"),
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id) VALUES (?, ?, ?)",
        ("story-linked", "linked story", "goal-1"),
    )
    conn.commit()
    conn.close()

    job = sl.dispatch_agent(
        "codex",
        "add a unit test for the helper",
        story_id="story-linked",
        force_agent=True,
        context_mode="none",
    )

    captured = capsys.readouterr()
    assert _WARNING not in captured.out
    sentinel_path = project_dir / ".synlynk" / "sentinel.md"
    if sentinel_path.exists():
        assert _WARNING not in sentinel_path.read_text()
    assert job["status"] == "running"
    assert job["story_id"] == "story-linked"
    assert job["pid"] == 4242


def test_dispatch_explicit_unlinked_story_still_hard_fails(project_dir, monkeypatch, capsys):
    """A supplied --story that is not linked to a goal keeps the #2029 fail-closed gate."""
    import pytest

    _quiet_unrelated_preflight(monkeypatch)
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, goal_id) VALUES (?, ?, NULL)",
        ("story-bare", "unlinked story"),
    )
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="no linked GOVERNS goal"):
        sl.dispatch_agent(
            "codex",
            "add a unit test for the helper",
            story_id="story-bare",
            force_agent=True,
            context_mode="none",
        )

    captured = capsys.readouterr()
    assert _WARNING not in captured.out
