from pathlib import Path


WORKFLOW = Path(".github/workflows/marketing-pr-sync.yml")


def test_marketing_sync_uses_a_protected_branch_pr_flow():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request_target:" in workflow
    assert "ref: main" in workflow
    assert "MARKETING_BRANCH: automation/marketing-sync" in workflow
    assert 'git config --global user.name "synlynk-marketing[bot]"' in workflow
    assert 'git config --global user.email "marketing@synlynk.com"' in workflow
    assert "head.ref != 'automation/marketing-sync'" in workflow
    assert "git push origin \"$MARKETING_BRANCH\"" in workflow
    assert "gh pr create" in workflow
    assert "--base main" in workflow
    assert "Fixes #1666" in workflow
    assert "actions: write" in workflow
    assert "statuses: write" in workflow
    assert "gh workflow run test.yml" in workflow
    assert 'gh run watch "$dispatch_run"' in workflow
    assert 'repos/$GITHUB_REPOSITORY/statuses/$head_sha' in workflow
    assert "created_pr_url=$(gh pr create" in workflow
    assert 'marketing_pr="${created_pr_url##*/}"' in workflow
    assert workflow.count('--body "Automated post-merge marketing updates') == 1
    assert "git push origin main" not in workflow
    assert "[skip ci]" not in workflow


def test_marketing_sync_is_serialized_and_idempotent():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "group: marketing-pr-sync" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "gh pr list \\" in workflow
    assert '--head "$MARKETING_BRANCH"' in workflow
    assert '--head "$GITHUB_REPOSITORY_OWNER:$MARKETING_BRANCH"' not in workflow
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
