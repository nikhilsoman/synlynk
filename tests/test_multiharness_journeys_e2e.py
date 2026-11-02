"""End-to-end 5-way cross-harness journey and parity verification matrix (v0.27.3).

Validates that all 5 supported agent harnesses (Claude, Codex, Agy, Grok, Muse)
pass independent fresh-project onboarding journeys from repo initialization
to command generation, model resolution, token accounting, and policy enforcement.
"""

import json
import subprocess
from pathlib import Path
import pytest

from synlynk.parity import run_parity_remediation, check_fleet_parity, generate_stack_policy
from synlynk.models import resolve_tier_model
from synlynk.costs import extract_tokens
from synlynk.harness_adapters.registry import get_adapter
from synlynk.harness_adapters.claude import ClaudeAdapter
from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.harness_adapters.agy import AgyAdapter
from synlynk.harness_adapters.grok import GrokAdapter
from synlynk.harness_adapters.muse import MuseAdapter


FIVE_HARNESSES = ["claude", "codex", "agy", "grok", "muse"]


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Harness"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test-harness@example.com"], cwd=path, check=True, capture_output=True)


def test_multiharness_fresh_project_sop_scaffolding(tmp_path):
    """Verify fresh project scaffolds SOPs and instructions for all core harnesses."""
    repo = tmp_path / "fresh-app"
    repo.mkdir()
    _init_git_repo(repo)

    (repo / "package.json").write_text(json.dumps({"name": "fresh-app", "scripts": {"test": "npm test"}}))
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init: initial commit"], cwd=repo, check=True, capture_output=True)

    # Run parity remediation to generate instruction directives
    res = run_parity_remediation(str(repo), dry_run=False, branch="feat/qa/fresh-parity")
    assert res["status"] == "SUCCESS"
    wt_path = Path(res["worktree"])

    assert (wt_path / "CLAUDE.md").exists()
    assert (wt_path / "AGENTS.md").exists()
    assert (wt_path / "GEMINI.md").exists()
    assert (wt_path / "GROK.md").exists()
    assert (wt_path / ".synlynk" / "policy.json").exists()

    # Verify policy enforces non-author QA merge authority
    policy = json.loads((wt_path / ".synlynk" / "policy.json").read_text())
    assert policy["overrides"]["merge_authority"]["can_merge"] == ["qa"]


@pytest.mark.parametrize("harness", FIVE_HARNESSES)
def test_multiharness_adapter_registration_and_model_resolution(harness):
    """Verify all 5 harnesses are registered in adapter registry and resolve models."""
    adapter = get_adapter(harness)
    assert adapter is not None

    for tier in ("fast", "standard", "heavy"):
        model = resolve_tier_model(tier, harness)
        assert model is not None
        assert isinstance(model, str)
        assert len(model) > 0


def test_multiharness_command_flags_and_permission_contracts():
    """Verify execution contracts across Claude, Codex, Agy, Grok, and Muse."""
    from synlynk.harness_adapters.request import DispatchRequest

    # 1. Claude
    claude = ClaudeAdapter()
    req = DispatchRequest(agent="claude", task="test task", permissions=["write:code"], read_only=False)
    claude_cmd = claude.build_cmd(req)
    assert any("claude" in str(x) for x in claude_cmd) or any("--allowedTools" in str(x) for x in claude_cmd)

    # 2. Codex
    codex = CodexAdapter()
    codex_flags = codex.translate_permissions(["run:shell"], read_only=True)
    assert "-s" in codex_flags
    assert "read-only" in codex_flags

    # 3. Agy
    agy = AgyAdapter()
    agy_flags = agy.translate_permissions(["run:shell"], read_only=False)
    assert "--sandbox" in agy_flags

    # 4. Grok
    grok = GrokAdapter()
    assert hasattr(grok, "build_cmd")

    # 5. Muse
    muse = MuseAdapter()
    req_muse = DispatchRequest(agent="muse", task="test task", permissions=["run:shell"], read_only=False)
    muse_cmd = muse.build_cmd(req_muse)
    assert "--approval-mode" in muse_cmd
    assert "never" in muse_cmd


def test_multiharness_cost_and_token_accounting_integrity():
    """Verify structured token extraction succeeds across all 5 harnesses without drift."""
    # Claude JSON output (stream-json format with result event)
    claude_out = json.dumps({"type": "result", "usage": {"input_tokens": 1200, "output_tokens": 450}})
    c_tokens = extract_tokens(claude_out, agent="claude")
    assert c_tokens.input_tokens == 1200
    assert c_tokens.output_tokens == 450

    # Agy JSON output
    agy_out = json.dumps({"status": "SUCCESS", "usage": {"input_tokens": 800, "output_tokens": 300, "thinking_tokens": 50}})
    a_tokens = extract_tokens(agy_out, agent="agy")
    assert a_tokens.input_tokens == 800
    assert a_tokens.output_tokens == 350

    # Grok JSON output
    grok_out = json.dumps({"usage": {"input_tokens": 950, "output_tokens": 420, "reasoning_tokens": 30}})
    g_tokens = extract_tokens(grok_out, agent="grok")
    assert g_tokens.input_tokens == 950
    assert g_tokens.output_tokens == 450

    # Muse JSON output
    muse_out = json.dumps({"usage": {"input_tokens": 1500, "output_tokens": 600}})
    m_tokens = extract_tokens(muse_out, agent="muse")
    assert m_tokens.input_tokens == 1500
    assert m_tokens.output_tokens == 600

    # Fallback generic structured pattern for Codex
    codex_out = 'Tokens used: 1,100 input, 350 output'
    cx_tokens = extract_tokens(codex_out, agent="codex")
    assert cx_tokens.input_tokens == 1100
    assert cx_tokens.output_tokens == 350


def test_multiharness_non_author_review_policy_enforcement():
    """Verify policy engine requires non-author review and blocks self-approval."""
    policy = generate_stack_policy(repo_id="journey-test", stack_info={"language": "python", "test_cmd": "pytest"})
    merge_auth = policy["overrides"]["merge_authority"]
    assert "qa" in merge_auth["can_merge"]
    assert "dev" not in merge_auth["can_merge"]
    assert "architect" not in merge_auth["can_merge"]
