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


def test_extract_synlynk_section_html_markers():
    from synlynk import _extract_synlynk_section
    content = 'Before\n<!-- synlynk:start version="0.4.1" tool="claude" -->\nmy block\n<!-- synlynk:end -->\nAfter'
    assert _extract_synlynk_section(content, "html") == "\nmy block\n"


def test_extract_synlynk_section_hash_markers():
    from synlynk import _extract_synlynk_section
    content = "Before\n# synlynk:start version=\"0.4.1\"\nmy block\n# synlynk:end\nAfter"
    assert _extract_synlynk_section(content, "hash") == "my block"


def test_extract_synlynk_section_none_marker_returns_whole():
    from synlynk import _extract_synlynk_section
    content = "entire file content"
    assert _extract_synlynk_section(content, "none") == content


def test_extract_synlynk_section_returns_none_when_absent():
    from synlynk import _extract_synlynk_section
    assert _extract_synlynk_section("no markers here", "html") is None


def test_compute_section_sha_is_deterministic():
    from synlynk import _compute_section_sha
    assert _compute_section_sha("hello") == _compute_section_sha("hello")
    assert _compute_section_sha("hello") != _compute_section_sha("world")
    assert len(_compute_section_sha("hello")) == 16
