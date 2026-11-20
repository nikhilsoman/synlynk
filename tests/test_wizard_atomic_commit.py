"""Regression coverage for the wizard's all-or-nothing completion boundary."""

import pytest

import synlynk
from synlynk import wizard


def test_wizard_dispatch_failure_preserves_confirmed_workspace_and_writes_nothing(
    monkeypatch, tmp_path
):
    """A failed auto-launch must abort before any configuration-side effect."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    confirmed = {
        "workspace_name": "confirmed-workspace",
        "topology": "multi",
        "repos": [{"name": "api"}, {"name": "web"}],
        "harnesses": [],
        "agents": [],
        "skills": [],
        "home_harness": "claude",
    }
    chosen = {
        "id": "first-win",
        "title": "First win",
        "agent": "codex",
        "cycle": "Build",
        "context_mode": "full",
    }
    selected_from = {}

    monkeypatch.setattr(synlynk, "_wiz_screen_landing", lambda: None)
    monkeypatch.setattr(synlynk, "_wiz_screen_harness", lambda scan: "claude")
    monkeypatch.setattr(synlynk, "_wiz_screen_topology", lambda scan: "multi")
    monkeypatch.setattr(
        synlynk,
        "_wiz_screen_workspace_name_pick",
        lambda scan: {key: confirmed[key] for key in ("workspace_name", "repos")},
    )
    monkeypatch.setattr(synlynk, "_wiz_screen_workspace_confirm", lambda workspace: True)
    monkeypatch.setattr(synlynk, "_wiz_screen_skills", lambda scan: None)
    monkeypatch.setattr(synlynk, "_wiz_screen_agents", lambda scan: None)
    monkeypatch.setattr(synlynk, "_wiz_screen_roles", lambda scan: {})
    monkeypatch.setattr(synlynk, "_wiz_read_key", lambda: "\r")
    monkeypatch.setattr(synlynk, "load_config", lambda: {"auto_launch_after_wizard": True})
    monkeypatch.setattr(
        synlynk,
        "run_workspace_scan",
        lambda **kwargs: pytest.fail("launch must use the confirmed wizard workspace"),
    )
    def select_tasks(scan):
        selected_from.update(scan)
        return [chosen]

    monkeypatch.setattr(synlynk, "_select_launch_tasks", select_tasks)
    monkeypatch.setattr(wizard, "_launch_screen_tasks", lambda tasks, scan: chosen)
    monkeypatch.setattr(wizard, "_launch_screen_preview", lambda task, scan: (True, "do it"))

    def fail_dispatch(**kwargs):
        raise RuntimeError("dispatcher unavailable")

    monkeypatch.setattr(synlynk, "dispatch_agent", fail_dispatch)
    monkeypatch.setattr(wizard, "guard_dirty_worktree", lambda: pytest.fail("must not stash"))
    monkeypatch.setattr(
        synlynk, "write_workspace_config", lambda *args: pytest.fail("must not write config")
    )
    monkeypatch.setattr(
        synlynk, "generate_structured_context", lambda *args: pytest.fail("must not write context")
    )
    monkeypatch.setattr(
        synlynk, "_upsert_harness_fence", lambda *args: pytest.fail("must not write role fences")
    )

    wizard.wizard_init(scan=confirmed, dry_run=False)

    assert {key: selected_from[key] for key in ("workspace_name", "topology", "repos")} == {
        "workspace_name": "confirmed-workspace",
        "topology": "multi",
        "repos": [{"name": "api"}, {"name": "web"}],
    }
    assert list(tmp_path.iterdir()) == []
