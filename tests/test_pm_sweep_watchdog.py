import json
import os
import textwrap
from unittest.mock import MagicMock, patch
import pytest

from synlynk.pm_agent import (
    extract_radar_opportunities,
    save_radar_opportunities,
    cmd_pm_sweep,
    RADAR_OUTPUT_PATH,
    PM_RADAR_DOC_PATH,
)
from synlynk.doctor import (
    _hc_spof_audit,
    _hc_memory_leak,
    HEALTH_CHECKS,
)


def test_extract_radar_opportunities_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    radar = extract_radar_opportunities(
        landscape_path=str(tmp_path / "missing.md"),
        config_path=str(tmp_path / "missing.json"),
    )
    assert radar["ring"] == "Ring 3 (Ecosystem & Competitor Frontier)"
    assert radar["total_opportunities"] >= 2
    assert len(radar["opportunities"]) >= 2
    for opp in radar["opportunities"]:
        assert opp["ring"] == 3
        assert opp["id"].startswith("opp-r3-")
        assert opp["fit_score"] > 0


def test_save_radar_opportunities(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    radar = extract_radar_opportunities(
        landscape_path=str(tmp_path / "missing.md"),
        config_path=str(tmp_path / "missing.json"),
    )
    json_path = str(tmp_path / ".synlynk" / "radar.json")
    doc_path = str(tmp_path / "docs" / "pm" / "opportunities-radar.md")

    out_json, out_doc = save_radar_opportunities(radar, json_path=json_path, doc_path=doc_path)
    assert os.path.exists(out_json)
    assert os.path.exists(out_doc)

    with open(out_json) as f:
        loaded = json.load(f)
        assert loaded["total_opportunities"] == radar["total_opportunities"]

    doc_text = open(out_doc).read()
    assert "PM Opportunities Radar" in doc_text
    assert "Ring 3 (Ecosystem & Competitor Frontier)" in doc_text


def test_cmd_pm_sweep_radar_integration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("docs/strategy", exist_ok=True)
    with open("docs/strategy/competitive-config.json", "w") as f:
        f.write(textwrap.dedent("""\
            {
              "segments": [{"name": "solo indie devs", "competitors": ["Superpowers"]}],
              "decide_panel": "claude,codex",
              "research_issue_labels": ["competitive-research"],
              "proposal_issue_labels": ["feature-proposal"]
            }
        """))

    with patch("synlynk.pm_agent.subprocess.run") as mock_run:
        summary = cmd_pm_sweep(dry_run=True, radar=True)
        mock_run.assert_not_called()
        assert summary is None
        assert os.path.exists(".synlynk/radar.json")
        assert os.path.exists("docs/pm/opportunities-radar.md")


def test_hc_spof_audit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # 1. Missing config
    hc_missing = _hc_spof_audit()
    assert hc_missing.status == "warn"

    # 2. Single agent (SPOF)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"agents": {"claude": {"role": "all"}}}, f)

    hc_spof = _hc_spof_audit()
    assert hc_spof.status == "warn"
    assert "Single harness configured" in hc_spof.message

    # 3. Multi-agent redundant fleet
    with open(".synlynk/config.json", "w") as f:
        json.dump({"agents": {"claude": {}, "codex": {}, "agy": {}, "grok": {}}}, f)

    hc_ok = _hc_spof_audit()
    assert hc_ok.status == "ok"
    assert "redundancy verified" in hc_ok.message


def test_hc_memory_leak():
    hc = _hc_memory_leak()
    assert hc.status in ("ok", "warn")
    assert "Process RSS memory" in hc.message or "Elevated" in hc.message


def test_doctor_health_checks_includes_spof_and_memory():
    names = [fn.__name__ for fn in HEALTH_CHECKS]
    assert "_hc_spof_audit" in names
    assert "_hc_memory_leak" in names
