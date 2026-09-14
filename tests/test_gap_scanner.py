import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.gap_scanner import scan_workspace_gaps, generate_governs_goal


def test_scan_workspace_gaps_missing_tests(tmp_path):
    app_py = tmp_path / "app.py"
    app_py.write_text("def core_function(): pass\n")
    
    discovery = {"logical": {"routes": [{"method": "GET", "path": "/api"}]}}
    gaps = scan_workspace_gaps(discovery, str(tmp_path))
    assert len(gaps) >= 1
    assert gaps[0]["type"] == "missing_unit_tests"


def test_generate_governs_goal_compliance():
    gap = {"type": "missing_unit_tests", "target": "app.py"}
    goal = generate_governs_goal(gap)
    assert "--outcome" in goal["command"]
    assert "--criterion" in goal["command"]
    assert "Establish 100% test coverage" in goal["outcome"]


def test_scan_workspace_gaps_missing_health_check(tmp_path):
    (tmp_path / "test_app.py").write_text("def test_ok(): pass\n")
    discovery = {"logical": {"routes": [{"method": "GET", "path": "/items"}]}}
    gaps = scan_workspace_gaps(discovery, str(tmp_path))
    assert len(gaps) == 1
    assert gaps[0]["type"] == "missing_health_check"
    goal = generate_governs_goal(gaps[0])
    assert "health probe" in goal["outcome"]
    assert "200 OK" in goal["criterion"]
