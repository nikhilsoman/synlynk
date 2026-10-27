"""Verification tests for test suite performance remediation (story-057d4312).

Tests:
1. Lazy DB_PATH and _INITIAL_GIT_WORKTREE evaluation
2. Selftest probe cascade mocking fixture behavior
3. Pytest-xdist configuration in pytest.ini
4. EOL Python 3.8 retirement in contribution templates
"""

import os
from pathlib import Path
import pytest
import synlynk
from synlynk import _LazyValue


def test_lazy_value_evaluates_only_on_access():
    calls = []

    def compute():
        calls.append(1)
        return "computed-path"

    lazy = _LazyValue(compute)
    assert len(calls) == 0
    assert not lazy._computed

    # Accessing str should evaluate
    assert str(lazy) == "computed-path"
    assert len(calls) == 1
    assert lazy._computed

    # Subsequent access does not recompute
    assert bool(lazy) is True
    assert lazy == "computed-path"
    assert os.fspath(lazy) == "computed-path"
    assert len(calls) == 1


def test_lazy_value_attribute_forwarding():
    lazy = _LazyValue(lambda: "hello_world")
    assert lazy.startswith("hello")
    assert lazy.upper() == "HELLO_WORLD"


def test_pytest_ini_contains_xdist_configuration():
    ini_path = Path(__file__).resolve().parent.parent / "pytest.ini"
    content = ini_path.read_text(encoding="utf-8")
    assert "addopts" in content
    assert "-n auto" in content


def test_pr_template_and_contributing_drop_python_38():
    root = Path(__file__).resolve().parent.parent
    pr_template = (root / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "Python 3.8" not in pr_template
    assert "Python 3.10+" in pr_template
    assert "Python 3.8" not in contributing
    assert "Python 3.10+" in contributing


def test_selftest_probe_mocking_fixture(monkeypatch):
    import synlynk.selftest as selftest_mod

    # Under mock_selftest_probe_cascade, _provision_probe_metadata returns 0
    # without running cmd_probe
    res = selftest_mod._provision_probe_metadata(Path("/tmp"))
    assert res == 0
