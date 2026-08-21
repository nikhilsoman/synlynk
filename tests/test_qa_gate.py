from unittest.mock import patch

from synlynk.qa_gate import _qa_gate_ci_status


def test_qa_gate_ci_status_green_when_ci_passes():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=True):
        assert _qa_gate_ci_status() is True


def test_qa_gate_ci_status_red_when_ci_fails():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=False):
        assert _qa_gate_ci_status() is False


def test_qa_gate_ci_status_none_when_undeterminable():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=None):
        assert _qa_gate_ci_status() is None
