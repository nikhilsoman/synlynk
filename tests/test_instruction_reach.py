# tests/test_instruction_reach.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))


def test_agy_baseline_replaces_gemini():
    from synlynk import AGENT_CAPABILITY_BASELINES
    assert "gemini" not in AGENT_CAPABILITY_BASELINES
    assert "agy" in AGENT_CAPABILITY_BASELINES


def test_gemini_md_template_has_no_transition_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import _build_templates
    templates = _build_templates()
    assert "2026-06-18" not in templates["GEMINI.md"]
    assert "agy-2.x" in templates["GEMINI.md"]
    assert "gemini-2.x" not in templates["GEMINI.md"]
