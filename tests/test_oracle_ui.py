"""Tests for standalone Prompt Oracle Web UI."""

from pathlib import Path
import json

def test_oracle_ui_assets_exist():
    root = Path("website/index-oracle")
    assert (root / "index.html").exists(), "index.html missing"
    assert (root / "style.css").exists(), "style.css missing"
    assert (root / "app.js").exists(), "app.js missing"
    assert (root / "pack-latest.json").exists(), "pack-latest.json missing"


def test_oracle_pack_valid_json():
    pack_file = Path("website/index-oracle/pack-latest.json")
    if pack_file.exists():
        data = json.loads(pack_file.read_text(encoding="utf-8"))
        assert "schema_version" in data
        assert "matrix" in data
        assert "disciplines" in data
        assert "snapshot_metadata" in data


def test_oracle_html_contains_core_elements():
    html_file = Path("website/index-oracle/index.html")
    if html_file.exists():
        html = html_file.read_text(encoding="utf-8")
        assert 'id="prompt-input"' in html
        assert 'id="preference-slider"' in html
        assert 'id="classification-badge"' in html
        assert 'id="recommendations-container"' in html
        assert 'brew install synlynk' in html
