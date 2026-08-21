from unittest.mock import patch
import json
import synlynk

from synlynk.qa_gate import _qa_gate_ci_status, _qa_gate_sentinel_health, qa_gate_verdict


def test_qa_gate_ci_status_green_when_ci_passes():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=True):
        assert _qa_gate_ci_status() is True


def test_qa_gate_ci_status_red_when_ci_fails():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=False):
        assert _qa_gate_ci_status() is False


def test_qa_gate_ci_status_none_when_undeterminable():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=None):
        assert _qa_gate_ci_status() is None


_SENTINEL_ISSUES_HIGH = json.dumps([
    {"title": "[support] sentinel_alerts: ⚠ FLATLINE: 3 consecutive exec failures", "number": 501},
])
_SENTINEL_ISSUES_MEDIUM_ONLY = json.dumps([
    {"title": "[support] sentinel_alerts: ⚠ slow response time observed", "number": 502},
])
_SENTINEL_ISSUES_NONE = json.dumps([])
_SENTINEL_ISSUES_UNRELATED = json.dumps([
    {"title": "[support] telemetry_anomaly: high failure rate", "number": 503},
])


def _mock_gh_issue_list(stdout, returncode=0):
    result = type("Result", (), {"returncode": returncode, "stdout": stdout, "stderr": ""})()
    return result


def test_qa_gate_sentinel_health_red_on_high_severity_open_issue():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_HIGH)):
        assert _qa_gate_sentinel_health("owner", "repo") is False


def test_qa_gate_sentinel_health_green_on_medium_only():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_MEDIUM_ONLY)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_green_on_no_open_issues():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_NONE)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_ignores_unrelated_support_issues():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_UNRELATED)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_none_when_gh_errors():
    with patch("subprocess.run", return_value=_mock_gh_issue_list("", returncode=1)):
        assert _qa_gate_sentinel_health("owner", "repo") is None


def test_qa_gate_sentinel_health_none_on_malformed_json():
    with patch("subprocess.run", return_value=_mock_gh_issue_list("not json")):
        assert _qa_gate_sentinel_health("owner", "repo") is None


def test_qa_gate_verdict_green_when_both_signals_healthy():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "green"
    assert verdict["ci_status"] is True
    assert verdict["sentinel_status"] is True


def test_qa_gate_verdict_red_when_ci_fails():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=False), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "CI" in verdict["reason"]


def test_qa_gate_verdict_red_when_sentinel_unhealthy():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=False):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "sentinel" in verdict["reason"].lower()


def test_qa_gate_verdict_fails_closed_when_ci_status_undeterminable():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=None), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "undeterminable" in verdict["reason"].lower()


def test_qa_gate_verdict_fails_closed_when_sentinel_status_undeterminable():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=None):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "undeterminable" in verdict["reason"].lower()


def test_load_config_defaults_qa_gate_mode_to_block_only(project_dir):
    config = synlynk.load_config()
    assert config["qa_gate_mode"] == "block-only"


def test_load_config_preserves_explicit_qa_gate_mode(project_dir):
    config_path = project_dir / ".synlynk" / "config.json"
    existing = json.loads(config_path.read_text()) if config_path.exists() else {}
    existing["qa_gate_mode"] = "block-only"
    config_path.write_text(json.dumps(existing))
    config = synlynk.load_config()
    assert config["qa_gate_mode"] == "block-only"
