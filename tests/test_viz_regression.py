# tests/test_viz_regression.py
import pytest
from synlynk.viz import generate_viz_data, _KNOWN_AGENTS, generate_index_html

def test_muse_harness_registered():
    assert "muse" in _KNOWN_AGENTS

def test_index_contains_muse_css_variables():
    data = generate_viz_data()
    html = generate_index_html(data, 8721)
    assert "--ag-muse-bg" in html
    assert "--ag-muse-bd" in html

def test_sentinel_alerts_have_severity_parsing(tmp_path, monkeypatch):
    sentinel_file = tmp_path / "sentinel.md"
    sentinel_file.write_text("- [CRITICAL] [2026-09-11 12:00] TOKEN_BLOAT: critical failure\n- [INFO] [2026-09-11 12:01] RESOLVED: old alert [RESOLVED]\n")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "sentinel.md").write_text(sentinel_file.read_text())
    
    data = generate_viz_data()
    alerts = data["telemetry"]["sentinel_alerts"]
    assert any(a.get("severity") == "CRITICAL" for a in alerts)
