from unittest.mock import patch
import json

from synlynk.qa_gate import _qa_gate_ci_status, _qa_gate_sentinel_health


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
