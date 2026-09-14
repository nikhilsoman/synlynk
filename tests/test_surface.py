import sys
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.surface import detect_developer_surfaces, bind_surface_rules


def test_detect_developer_surfaces_cursor_and_vscode(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".vscode").mkdir()
    surfaces = detect_developer_surfaces(str(tmp_path))
    assert "cursor" in surfaces
    assert "vscode" in surfaces


def test_detect_developer_surfaces_warp_replit_emergent(tmp_path):
    (tmp_path / ".replit").write_text("run = 'python main.py'")
    (tmp_path / ".emergent").mkdir()
    with patch.dict(os.environ, {"TERM_PROGRAM": "WarpTerminal"}):
        surfaces = detect_developer_surfaces(str(tmp_path))
        assert "warp" in surfaces
        assert "replit" in surfaces
        assert "emergent" in surfaces


def test_bind_surface_rules_generates_cursor_mdc(tmp_path):
    bind_surface_rules(str(tmp_path), ["cursor"])
    mdc_file = tmp_path / ".cursor" / "rules" / "synlynk.mdc"
    assert mdc_file.exists()
    content = mdc_file.read_text()
    assert "description: synlynk project protocol" in content
    assert "alwaysApply: true" in content
    assert "Home Conductor" in content


def test_bind_surface_rules_generates_warp_replit_emergent_antigravity(tmp_path):
    bind_surface_rules(str(tmp_path), ["warp", "replit", "emergent", "antigravity"])

    # Warp
    warp_yaml = tmp_path / ".warp" / "workflows" / "synlynk.yaml"
    assert warp_yaml.exists()
    assert "synlynk start" in warp_yaml.read_text()

    # Replit
    replit_rules = tmp_path / ".replitrules"
    assert replit_rules.exists()
    assert "Home Conductor" in replit_rules.read_text()

    # Emergent
    emergent_json = tmp_path / ".emergent" / "synlynk.json"
    assert emergent_json.exists()
    assert "mcp_gateway" in emergent_json.read_text()

    # Antigravity
    gemini_md = tmp_path / "GEMINI.md"
    assert gemini_md.exists()
    assert "AntiGravity Instructions" in gemini_md.read_text()
