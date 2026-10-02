import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.autonomy import AutonomyMode, can_auto_advance, set_autonomy_mode
from synlynk.board_governance import ProposalGate, ProposalStatus, create_proposal
from synlynk.charters import load_charter
from synlynk.jev import evaluate_task_ast_features
from synlynk.addon import list_available_addons
from synlynk.registry import load_registry


def test_v024_full_stack_integration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # 1. Autonomy Dial
    mode = set_autonomy_mode(AutonomyMode.AUTONOMOUS)
    assert can_auto_advance("execute", mode)

    # 2. Board Governance
    prop = create_proposal(ProposalGate.RELEASE_TAG, "Release v0.24.0", budget_usd=0.0)
    assert prop.status == ProposalStatus.PENDING

    # 3. Charters
    charter = load_charter("architect")
    assert charter.role == "architect"

    # 4. Jev Decisioning
    decision = evaluate_task_ast_features(["synlynk/cli.py"], "cli fast path")
    assert decision.recommended_tier in ("fast", "pro", "reasoning")

    # 5. Addons & Registry
    addons = list_available_addons()
    assert len(addons) >= 3
    reg = load_registry()
    assert "supabase" in reg


def test_v024_cli_surface_registered():
    """Every v0.24.0 command group is wired into the real argparse CLI tree."""
    from synlynk.cli import build_parser
    from synlynk.taxonomy import COMMAND_TAXONOMY, iter_leaf_commands

    parser = build_parser()
    real_commands = set(iter_leaf_commands(parser))
    taxonomy_commands = {entry["command"] for entry in COMMAND_TAXONOMY}

    expected = {
        "autonomy show", "autonomy set",
        "board propose", "board sign", "board show",
        "concierge synthesize",
        "addon list", "addon install",
    }
    assert expected <= real_commands
    assert expected <= taxonomy_commands
