from pathlib import Path


WORKFLOW = Path(".github/workflows/marketing-pr-sync.yml")


def test_marketing_sync_does_not_fail_on_the_stale_marketing_pr():
    """gh:#2646 — a merged PR must not be gated by automation/marketing-sync."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request_target:" in workflow
    assert "head.ref != 'automation/marketing-sync'" in workflow
    assert "Per-PR marketing sync is retired" in workflow
    assert "gh:#2646" in workflow
    assert "gh pr list" not in workflow
    assert "gh pr create" not in workflow
    assert "gh workflow run test.yml" not in workflow
    assert "Required Tests checks failed" not in workflow
    assert "git push origin" not in workflow
    assert "actions: write" not in workflow
    assert "statuses: write" not in workflow
    assert "contents: read" in workflow


def test_marketing_sync_is_serialized():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "group: marketing-pr-sync" in workflow
    assert "cancel-in-progress: false" in workflow


def test_marketing_sync_does_not_merge_or_regenerate_the_stale_branch():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "git merge --no-edit -X theirs origin/main" not in workflow
    assert "automation/marketing-sync" in workflow
    assert "Not reusing automation/marketing-sync" in workflow


def test_required_checks_support_automation_branch_dispatch():
    workflow = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch: {}" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow


def test_release_docs_runs_for_pull_requests_dispatch_or_version_tags():
    workflow = Path(".github/workflows/test.yml").read_text(encoding="utf-8")
    release_docs = workflow.split("  release-docs:", 1)[1]

    assert "github.event_name == 'workflow_dispatch'" in release_docs
    assert "startsWith(github.ref, 'refs/tags/v')" in release_docs
    assert "github.event_name == 'pull_request'" in release_docs
    assert "github.event_name == 'pull_request' && '--pr-mode'" in release_docs
    assert "fetch-depth: 0" in release_docs

def test_test_workflow_scopes_bookkeeping_and_pr_matrix():
    """Required checks stay present while PRs run Linux 3.10 and 3.12."""
    workflow = Path(".github/workflows/test.yml").read_text(encoding="utf-8")

    assert "is_bookkeeping_only" in workflow
    assert "bookkeeping_only" in workflow
    # matrix.* is illegal in a job-level if (evaluated before expansion).
    # matrix-plan emits the PR legs or the full matrix before test starts.
    assert "matrix-plan:" in workflow
    assert "fromJson(needs.matrix-plan.outputs.matrix)" in workflow
    compact = workflow.replace(" ", "")
    assert '{"os":["ubuntu-latest"],"python-version":["3.10","3.12"]}' in compact
    assert '{"os":["ubuntu-latest"],"python-version":["3.12"]}' not in compact
    assert "macos-latest" in workflow
    assert "3.10" in workflow
    # Legal in a job name or a step if. Illegal as the job-level matrix filter
    # GitHub reported: matrix is not in scope until the matrix is expanded.
    assert "matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'" not in workflow
    assert 'tags: ["v*"]' in workflow
    assert "\n  qa-gate:" in workflow
    assert "\n  release-docs:" in workflow
    assert "format('test ({0})', matrix.python-version)" in workflow
    assert "grep -qvE '^(docs/|project-docs/|.*\\.md$)'" not in workflow
    # Trigger-level filters would skip qa-gate and release-docs on bookkeeping PRs.
    header = workflow.split("\njobs:", 1)[0]
    assert "paths-ignore:" not in header


def test_marketing_sync_does_not_stage_blog_or_social_drafts():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "git add docs/blog/" not in workflow
    assert "social_drafts.json" not in workflow
