"""Tests for harness-spec modularity and probe engine."""

import ast
import os
import pytest
from harness_spec.models import HarnessContract
from harness_spec.probe import probe_binary, probe_all_known


def test_modularity_zero_synlynk_imports():
    """Verify that packages/harness-spec/src contains ZERO imports of synlynk."""
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as pyfile:
                    tree = ast.parse(pyfile.read(), filename=fpath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert not alias.name.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {alias.name}"
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                assert not node.module.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {node.module}"


def test_probe_known_harnesses():
    """Verify probe_all_known returns contracts for core fleet."""
    contracts = probe_all_known()
    assert "claude" in contracts
    assert "agy" in contracts
    assert "codex" in contracts
    assert "grok" in contracts

    assert contracts["claude"].headless_prompt_flag == "-p"
    assert contracts["codex"].headless_prompt_flag == "-c"


def test_probe_nonexistent_binary():
    """Verify probing a nonexistent binary returns installed=False safely."""
    contract = probe_binary("nonexistent_binary_xyz_123")
    assert not contract.installed
    assert contract.version is None
