from pathlib import Path


WORKFLOW = Path(".github/workflows/marketing-pr-sync.yml")


def test_marketing_sync_uses_a_protected_branch_pr_flow():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request_target:" in workflow
    assert "ref: main" in workflow
    assert "MARKETING_BRANCH: automation/marketing-sync" in workflow
    assert "head.ref != 'automation/marketing-sync'" in workflow
    assert "git push origin \"$MARKETING_BRANCH\"" in workflow
    assert "gh pr create" in workflow
    assert "--base main" in workflow
    assert "Fixes #1666" in workflow
    assert "actions: write" in workflow
    assert "gh workflow run test.yml" in workflow
    assert "git push origin main" not in workflow
    assert "[skip ci]" not in workflow


def test_marketing_sync_is_serialized_and_idempotent():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "group: marketing-pr-sync" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "gh pr list \\" in workflow
    assert "--state open" in workflow
    assert "Reused existing marketing PR" in workflow


def test_required_checks_support_automation_branch_dispatch():
    workflow = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch: {}" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow

def test_marketing_sync_stages_blog_and_social_draft_outputs():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "git add docs/blog/" in workflow
    assert "git add -f .synlynk/social_drafts.json" in workflow
