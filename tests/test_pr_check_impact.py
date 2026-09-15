import pytest
from synlynk.pr_check import check_pr_impact_attestation


def test_pr_check_fails_when_affected_symbol_has_no_tests(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synlynk.pr_check._get_modified_symbols_from_diff",
        lambda root: ["critical_auth_function"]
    )
    monkeypatch.setattr(
        "synlynk.impact.calculate_impact",
        lambda root, sym: {"associated_tests": []}
    )

    result = check_pr_impact_attestation(str(tmp_path))
    assert result["passed"] is False
    assert "critical_auth_function has no associated test coverage" in result["error"]


def test_pr_check_passes_when_all_symbols_have_tests(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synlynk.pr_check._get_modified_symbols_from_diff",
        lambda root: ["login"]
    )
    monkeypatch.setattr(
        "synlynk.impact.calculate_impact",
        lambda root, sym: {"associated_tests": [{"label": "test_login", "file": "tests/test_auth.py"}]}
    )

    result = check_pr_impact_attestation(str(tmp_path))
    assert result["passed"] is True
    assert result.get("untested_symbols") == []


def test_pr_check_passes_when_no_modified_symbols(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "synlynk.pr_check._get_modified_symbols_from_diff",
        lambda root: []
    )
    result = check_pr_impact_attestation(str(tmp_path))
    assert result["passed"] is True
