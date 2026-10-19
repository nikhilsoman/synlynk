"""Reload-tier SOP bodies: per-turn harnesses stay lean (gh:#2284).

Session-tier harnesses (Claude/Codex) get the full inlined SOP bodies;
per-turn harnesses (Agy/Grok) get a lean core plus a load-on-demand SOP
index. Both run_parity_remediation() and probe._repair_sops_only() must
resolve through the shared tier logic in synlynk.instructions so they never
re-inflate a deliberately lean file.
"""

from synlynk.instructions import (
    RELOAD_TIER_PER_TURN,
    RELOAD_TIER_SESSION,
    resolve_file_reload_tier,
    sop_body_for_file,
    sop_body_for_reload_tier,
)
from synlynk.probe import SOP_BLOCKS

FULL_BODY_MARKER = "Assign a non-authoring agent to review the PR"


def test_resolve_file_reload_tier():
    assert resolve_file_reload_tier("CLAUDE.md") == RELOAD_TIER_SESSION
    assert resolve_file_reload_tier("AGENTS.md") == RELOAD_TIER_SESSION
    assert resolve_file_reload_tier("GEMINI.md") == RELOAD_TIER_PER_TURN
    assert resolve_file_reload_tier("GROK.md") == RELOAD_TIER_PER_TURN
    assert resolve_file_reload_tier("claude") == RELOAD_TIER_SESSION
    assert resolve_file_reload_tier("codex") == RELOAD_TIER_SESSION
    assert resolve_file_reload_tier("agy") == RELOAD_TIER_PER_TURN
    assert resolve_file_reload_tier("grok") == RELOAD_TIER_PER_TURN
    # Unknown targets default to the session tier (pre-tiering behaviour).
    assert resolve_file_reload_tier("AI_INSTRUCTIONS.md") == RELOAD_TIER_SESSION
    assert resolve_file_reload_tier("something-new") == RELOAD_TIER_SESSION


def test_session_tier_body_is_full_sop():
    body = sop_body_for_reload_tier(RELOAD_TIER_SESSION)
    for block in SOP_BLOCKS:
        assert block.strip().splitlines()[0] in body
    assert FULL_BODY_MARKER in body


def test_per_turn_tier_body_is_lean_index():
    body = sop_body_for_reload_tier(RELOAD_TIER_PER_TURN)
    assert "## SOP Index (load on demand)" in body
    assert "AI_INSTRUCTIONS.md" in body
    for block in SOP_BLOCKS:
        assert block.strip().splitlines()[0] in body
    assert FULL_BODY_MARKER not in body
    assert len(body) < len(sop_body_for_reload_tier(RELOAD_TIER_SESSION))


def test_sop_body_for_file_tiers_by_target():
    assert "## SOP Index (load on demand)" in sop_body_for_file("GEMINI.md")
    assert "## SOP Index (load on demand)" in sop_body_for_file("GROK.md")
    assert "## SOP Index (load on demand)" in sop_body_for_file("agy")
    assert FULL_BODY_MARKER in sop_body_for_file("CLAUDE.md")
    assert FULL_BODY_MARKER in sop_body_for_file("AGENTS.md")


def _repair_cfg():
    return {
        "roles": {"agy": ["implement"], "codex": ["implement"]},
        "workgroup_agents": ["agy", "codex"],
    }


def test_repair_sops_only_keeps_per_turn_files_lean(tmp_path, monkeypatch):
    from synlynk.probe import _repair_sops_only

    monkeypatch.chdir(tmp_path)
    (tmp_path / "GEMINI.md").write_text("# Gemini\n")
    (tmp_path / "AGENTS.md").write_text("# Codex\n")

    _repair_sops_only(cfg=_repair_cfg(), dry_run=False)

    gemini = (tmp_path / "GEMINI.md").read_text()
    agents = (tmp_path / "AGENTS.md").read_text()
    assert "## SOP Index (load on demand)" in gemini
    assert FULL_BODY_MARKER not in gemini
    assert "<!-- synlynk:harness" in gemini
    assert FULL_BODY_MARKER in agents

    # Converged: a second run leaves both files byte-identical.
    before = {
        "GEMINI.md": gemini,
        "AGENTS.md": agents,
    }
    _repair_sops_only(cfg=_repair_cfg(), dry_run=False)
    for fname, content in before.items():
        assert (tmp_path / fname).read_text() == content


def test_repair_sops_only_converges_inflated_per_turn_file(tmp_path, monkeypatch):
    from synlynk.probe import _repair_sops_only

    monkeypatch.chdir(tmp_path)
    inflated = "# Gemini\n\n<!-- synlynk:harness v0.1 verified:2026-01-01T00:00:00Z -->\n"
    inflated += "# Harness Instructions (synlynk-managed — do not edit)\n\n"
    inflated += "\n\n".join(SOP_BLOCKS)
    inflated += "\n<!-- /synlynk:harness -->\n"
    (tmp_path / "GEMINI.md").write_text(inflated)

    _repair_sops_only(cfg=_repair_cfg(), harness_name="agy", dry_run=False)

    updated = (tmp_path / "GEMINI.md").read_text()
    assert "## SOP Index (load on demand)" in updated
    assert FULL_BODY_MARKER not in updated


def test_parity_remediation_injects_tiered_bodies(tmp_path):
    import subprocess
    from pathlib import Path

    from synlynk.parity import run_parity_remediation

    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True, capture_output=True
    )
    (tmp_path / "CLAUDE.md").write_text("# Custom\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'tiered-app'\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), check=True, capture_output=True)

    res = run_parity_remediation(str(tmp_path), dry_run=False, branch="feat/agy/test-tiering")
    assert res["status"] == "SUCCESS"
    wt_path = Path(res["worktree"])

    gemini = (wt_path / "GEMINI.md").read_text()
    grok = (wt_path / "GROK.md").read_text()
    claude = (wt_path / "CLAUDE.md").read_text()
    agents = (wt_path / "AGENTS.md").read_text()

    assert "## SOP Index (load on demand)" in gemini
    assert "## SOP Index (load on demand)" in grok
    assert FULL_BODY_MARKER not in gemini
    assert FULL_BODY_MARKER not in grok
    assert FULL_BODY_MARKER in claude
    assert FULL_BODY_MARKER in agents
