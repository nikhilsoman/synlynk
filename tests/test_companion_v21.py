# tests/test_companion_v21.py
import pytest
from synlynk import companion
from synlynk.fencing import FenceData, clear_hint_contributors, render_task_fence


def setup_function(_):
    companion.enable_companion(False)
    clear_hint_contributors()
    companion.clear_pinned_stage()


def teardown_function(_):
    companion.enable_companion(False)
    clear_hint_contributors()
    companion.clear_pinned_stage()


def test_companion_format_four_part_anatomy():
    msg = companion.format_companion_message(
        signal="QA verification completed on branch feat/genesis",
        context="Burn: $0.18 · 14/14 tests green",
        nudge="Goal 1 ready for DECIDE approval",
        deep_links=[("PR #5162", "https://github.com/nikhilsoman/synlynk/pull/5162")],
    )
    assert "[Signal]" in msg
    assert "[Context]" in msg
    assert "[Nudge]" in msg
    assert "[Deep Links]" in msg
    assert "feat/genesis" in msg
    assert "PR #5162" in msg


def test_companion_registers_as_hint_contributor():
    companion.enable_companion(True)
    companion.register_companion_seam()

    data = FenceData(
        command="dispatch",
        kind="task_complete",
        in_tokens=100,
        out_tokens=200,
        cost_usd=0.05,
        basis="actual",
        hints=[],
    )
    render_task_fence(data)
    assert len(data.hints) > 0
    assert any("[Signal]" in h or "Synlynk" in h or "tip:" in h for h in data.hints)


def test_companion_relationship_ladder_and_segments():
    assert "onboarding" in companion.RELATIONSHIP_STAGES
    assert "sounding_board" in companion.RELATIONSHIP_STAGES
    assert "champion" in companion.RELATIONSHIP_STAGES

    assert "novice" in companion.DEVELOPER_SEGMENTS
    assert "architect" in companion.DEVELOPER_SEGMENTS


def test_domain_vocab_substitution_template():
    text = "We should dispatch an agent to run the task."
    vocab = {"an agent": "a digital teammate", "dispatch": "orchestrate"}
    subbed = companion.apply_domain_vocab(text, vocab)
    assert "orchestrate a digital teammate" in subbed
