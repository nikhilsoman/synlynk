"""Regression coverage for the conservative onboarding incident repair."""

import json

from synlynk.onboard_repair import repair_onboarding


def test_dry_run_reports_known_artifacts_without_changing_them(tmp_path):
    home = tmp_path / "home"
    context = home / ".synlynk" / "context.md"
    context.parent.mkdir(parents=True)
    context.write_text("orphaned wizard context", encoding="utf-8")
    workspace = home / ".synlynk" / "workspaces" / "roku" / "config.json"
    workspace.parent.mkdir(parents=True)
    workspace.write_text(
        json.dumps({"repos": [str(tmp_path / "missing-repo"), {"path": str(tmp_path / "missing-object-repo")}]}), encoding="utf-8"
    )

    report = repair_onboarding(repo_root=tmp_path, home=home, apply=False)

    assert context.exists()
    assert report.applied == []
    assert any(action.kind == "remove-orphan-context" for action in report.actions)
    invalid_repos = [action for action in report.actions if action.kind == "workspace-invalid-repo"]
    assert len(invalid_repos) == 2


def test_apply_removes_only_known_orphaned_home_context(tmp_path):
    home = tmp_path / "home"
    context = home / ".synlynk" / "context.md"
    context.parent.mkdir(parents=True)
    context.write_text("orphaned wizard context", encoding="utf-8")
    unrelated = home / ".synlynk" / "keep.md"
    unrelated.write_text("keep", encoding="utf-8")

    report = repair_onboarding(repo_root=tmp_path, home=home, apply=True)

    assert not context.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert [action.kind for action in report.applied] == ["remove-orphan-context"]


def test_repair_only_restores_tool_checkout_files_with_managed_fence_diff(
    tmp_path, monkeypatch
):
    instruction = tmp_path / "AGENTS.md"
    instruction.write_text("managed fence", encoding="utf-8")
    monkeypatch.setattr("synlynk.onboard_repair._is_synlynk_source_checkout", lambda _: True)
    monkeypatch.setattr("synlynk.onboard_repair._has_managed_fence_only_diff", lambda _: True)
    monkeypatch.setattr("synlynk.onboard_repair._restore_from_head", lambda path: path.unlink())

    report = repair_onboarding(repo_root=tmp_path, home=tmp_path / "home", apply=True)

    assert not instruction.exists()
    assert [action.kind for action in report.applied] == ["restore-managed-fence"]
