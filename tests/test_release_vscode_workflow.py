from pathlib import Path


WORKFLOW = Path(".github/workflows/release-vscode.yml")


def test_vscode_publish_installs_without_a_lockfile_and_reads_the_local_manifest():
    """gh:#2648 — npm ci has no lockfile, and the dependency check must use the step directory."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'tags:\n      - "v*"' in workflow
    assert "types: [published]" in workflow
    assert "run: npm ci" not in workflow
    assert "npm ci ||" not in workflow
    assert "run: npm install" in workflow
    assert "working-directory: clients/vscode" in workflow
    assert "require('./package.json')" in workflow
    assert "require('./clients/vscode/package.json')" not in workflow
    assert "gh:#2648" in workflow
    assert "Object.keys(pkg.dependencies || {}).length" in workflow
