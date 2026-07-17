import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.instructions import render_trigger_phrase_section


def test_tier0_fixture_only_gets_tier0_and_gateway_phrases():
    section = render_trigger_phrase_section(current_tier=0)
    assert "let's build X" not in section
    assert "set up synlynk here" in section
    assert "where are we" in section


def test_tier2_fixture_gets_tier0_through_tier2_phrases():
    section = render_trigger_phrase_section(current_tier=2)
    assert "let's build X" in section
    assert "set up synlynk here" in section
    assert "rate this agent's output" not in section
