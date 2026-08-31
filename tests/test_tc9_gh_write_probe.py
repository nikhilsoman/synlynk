import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.probe import _run_tc9


def test_tc9_claude_supported(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/claude")
    res = _run_tc9("claude")
    assert res["passed"] is True
    assert res["can_gh_write"] is True
    assert res["mechanism"] == "direct_cli"


def test_tc9_codex_supported_with_flag(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/codex")
    res = _run_tc9("codex")
    assert res["passed"] is True
    assert res["can_gh_write"] is True
    assert res["mechanism"] == "requires_gh_write_flag"
    assert "requires-gh-write" in res["note"]


def test_tc9_grok_sandbox_denied(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/grok")
    res = _run_tc9("grok")
    assert res["passed"] is False
    assert res["can_gh_write"] is False
    assert res["mechanism"] == "sandbox_denied"
    assert "denies shell execution" in res["error"]


def test_tc9_agy_allow_rules(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/agy")

    # When TC-7 fails (missing allow rules)
    with patch("synlynk.doctor._run_tc7", return_value={"passed": False, "missing": ["command(gh pr review)"]}):
        res = _run_tc9("agy")
        assert res["passed"] is False
        assert res["can_gh_write"] is False
        assert res["mechanism"] == "missing_allow_rules"

    # When TC-7 passes
    with patch("synlynk.doctor._run_tc7", return_value={"passed": True, "missing": []}):
        res = _run_tc9("agy")
        assert res["passed"] is True
        assert res["can_gh_write"] is True
        assert res["mechanism"] == "verified_allow_rules"


def test_tc9_uninstalled_cli(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda bin_name: None)
    res = _run_tc9("nonexistent_agent")
    assert res["passed"] is False
    assert res["mechanism"] == "uninstalled"
