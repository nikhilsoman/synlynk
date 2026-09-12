import json
import os
from pathlib import Path
import pytest

from synlynk.parity import (
    detect_project_stack,
    parse_directive_fences,
    inject_sop_fences,
    ensure_recursive_gitignore,
    generate_stack_policy,
)


def test_detect_project_stack_node(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"name": "my-app", "scripts": {"test": "vitest run"}}))
    stack = detect_project_stack(str(tmp_path))
    assert stack["language"] == "node"
    assert "vitest" in stack["test_cmd"]
    assert stack["package_manager"] in ("npm", "pnpm", "yarn", "bun")


def test_detect_project_stack_go(tmp_path):
    go_mod = tmp_path / "go.mod"
    go_mod.write_text("module github.com/example/my-go-app\n\ngo 1.22\n")
    stack = detect_project_stack(str(tmp_path))
    assert stack["language"] == "go"
    assert "go test" in stack["test_cmd"]


def test_detect_project_stack_python(tmp_path):
    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text("[project]\nname = 'my-py-app'\n")
    stack = detect_project_stack(str(tmp_path))
    assert stack["language"] == "python"
    assert "pytest" in stack["test_cmd"]


def test_detect_project_stack_mixed(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "frontend"}))
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'backend'\n")
    stack = detect_project_stack(str(tmp_path))
    assert stack["language"] in ("mixed", "node", "python")
    assert "languages" in stack
    assert "node" in stack["languages"]
    assert "python" in stack["languages"]


def test_parse_directive_fences_with_both_fences():
    sample = """# Custom Repository Guidelines
These are the sacred user domain rules.
Line 2 of rules.

<!-- synlynk:start version="0.18.0" tool="claude" -->
# Old synlynk start content
Do not delete
<!-- synlynk:end -->

Some middle text that should be preserved.

<!-- synlynk:harness v0.150.1 verified:2026-09-01T00:00:00Z -->
# Harness Instructions (synlynk-managed — do not edit)
Old harness content
<!-- /synlynk:harness -->

Footer user notes.
"""
    user_content, start_block, harness_block = parse_directive_fences(sample)
    assert "# Custom Repository Guidelines" in user_content
    assert "These are the sacred user domain rules." in user_content
    assert "Some middle text that should be preserved." in user_content
    assert "Footer user notes." in user_content
    assert "Old synlynk start content" not in user_content
    assert "Old harness content" not in user_content
    assert start_block is not None
    assert "synlynk:start" in start_block
    assert harness_block is not None
    assert "synlynk:harness" in harness_block


def test_parse_directive_fences_with_no_fences():
    sample = """# Pure User Instructions
Just domain knowledge.
No synlynk fences here.
"""
    user_content, start_block, harness_block = parse_directive_fences(sample)
    assert user_content.strip() == sample.strip()
    assert start_block is None
    assert harness_block is None


def test_inject_sop_fences_preserves_user_content():
    original = """# Project Foo
Architecture details: microservices on AWS.

<!-- synlynk:start version="0.10.0" tool="codex" -->
# Obsolete instructions
<!-- synlynk:end -->
"""
    new_start_body = "# Modern Codex Directives\nUpdated rules."
    new_harness_body = "## PR Review Discipline\nRun synlynk pr check."

    result = inject_sop_fences(
        content=original,
        tool="codex",
        version="0.20.1",
        start_body=new_start_body,
        harness_body=new_harness_body,
    )

    assert "# Project Foo" in result
    assert "Architecture details: microservices on AWS." in result
    assert "# Obsolete instructions" not in result
    assert '<!-- synlynk:start version="0.20.1" tool="codex" -->' in result
    assert "# Modern Codex Directives" in result
    assert "<!-- synlynk:end -->" in result
    assert "<!-- synlynk:harness" in result
    assert "## PR Review Discipline" in result
    assert "<!-- /synlynk:harness -->" in result


def test_ensure_recursive_gitignore(tmp_path):
    gi = tmp_path / ".gitignore"
    gi.write_text(".env\nnode_modules/\n.synlynk/*\n")
    modified = ensure_recursive_gitignore(str(tmp_path))
    assert modified is True
    content = gi.read_text()
    assert "**/.synlynk/*" in content
    assert "!**/.synlynk/policy.json" in content
    assert "!**/.synlynk/roles.yaml" in content


def test_generate_stack_policy_node(tmp_path):
    stack = {"language": "node", "test_cmd": "npm test"}
    policy = generate_stack_policy(repo_id="test-node-app", stack_info=stack)
    assert policy["schema_version"] == 1
    assert policy["repo_id"] == "test-node-app"
    overrides = policy["overrides"]
    assert "dev_authority" in overrides
    assert "merge_authority" in overrides
    task_alloc = overrides["dev_authority"]["task_allocation"]
    assert "implement" in task_alloc
    assert overrides["merge_authority"]["can_merge"] == ["qa"]


def test_run_parity_remediation_dry_run(tmp_path):
    import subprocess
    # Initialize mock git repository
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True, capture_output=True)

    claude_file = tmp_path / "CLAUDE.md"
    claude_file.write_text("# My Sacred Custom App\nDomain logic rules here.\n")
    (tmp_path / "package.json").write_text(json.dumps({"name": "drifted-app", "scripts": {"test": "echo test"}}))
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True, capture_output=True)

    from synlynk.parity import run_parity_remediation
    res = run_parity_remediation(str(tmp_path), dry_run=True)

    assert res["status"] == "DRY_RUN"
    assert "CLAUDE.md" in res["files_to_touch"]
    assert "GEMINI.md" in res["files_to_touch"]
    assert "AGENTS.md" in res["files_to_touch"]
    assert "GROK.md" in res["files_to_touch"]
    assert ".synlynk/policy.json" in res["files_to_touch"]


def test_run_parity_remediation_live(tmp_path):
    import subprocess
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True, capture_output=True)

    claude_file = tmp_path / "CLAUDE.md"
    claude_file.write_text("# My Sacred Custom App\nDomain logic rules here.\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'drifted-py-app'\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True, capture_output=True)

    from synlynk.parity import run_parity_remediation
    res = run_parity_remediation(str(tmp_path), dry_run=False, branch="feat/agy/test-parity")

    assert res["status"] == "SUCCESS"
    assert res["branch"] == "feat/agy/test-parity"
    wt_path = Path(res["worktree"])
    assert wt_path.exists()
    assert (wt_path / "CLAUDE.md").exists()
    assert (wt_path / "GEMINI.md").exists()
    assert (wt_path / "AGENTS.md").exists()
    assert (wt_path / "GROK.md").exists()
    assert (wt_path / ".synlynk" / "policy.json").exists()

    # Verify sacred user content preserved in worktree CLAUDE.md
    wt_claude = (wt_path / "CLAUDE.md").read_text()
    assert "# My Sacred Custom App" in wt_claude
    assert "Domain logic rules here." in wt_claude
    assert "<!-- synlynk:start" in wt_claude
    assert "<!-- synlynk:harness" in wt_claude


def test_check_fleet_parity_detects_drift(tmp_path):
    from synlynk.parity import check_fleet_parity
    res = check_fleet_parity(str(tmp_path))
    assert res["status"] == "WARN"
    assert "synlynk heal --parity" in res["remediation"]
    assert len(res["details"]["gaps"]) > 0


def test_doctor_hc_fleet_parity_runs():
    from synlynk.doctor import _hc_fleet_parity
    check = _hc_fleet_parity()
    assert check.name == "fleet_parity"
    assert check.status in ("ok", "warn")


