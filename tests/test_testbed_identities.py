"""Tests for synlynk.testbed.identities."""
from unittest.mock import MagicMock
import pytest

from synlynk.testbed.driver import ExecResult
from synlynk.testbed.identities import (
    STANDARD_IDENTITIES,
    SyntheticIdentity,
    provision_node_identity,
    get_identity_for_node,
)


def test_synthetic_identity_attribution_tag():
    ident = SyntheticIdentity(
        username="alice",
        email="alice@test.synlynk",
        role="dev",
        harness="codex",
        api_keys={"OPENAI_API_KEY": "test-key-123"},
    )
    assert ident.attribution_tag == "<@alice, dev, codex>"


def test_standard_identities_matrix():
    alice = STANDARD_IDENTITIES["node-1"]
    assert alice.username == "alice"
    assert alice.role == "dev"
    assert alice.harness == "codex"

    bob = STANDARD_IDENTITIES["node-2"]
    assert bob.username == "bob"
    assert bob.role == "architect"
    assert bob.harness == "agy"

    charlie = STANDARD_IDENTITIES["node-3"]
    assert charlie.username == "charlie"
    assert charlie.role == "qa"
    assert charlie.harness == "grok"


def test_provision_node_identity():
    mock_driver = MagicMock()
    mock_driver.exec_command.return_value = ExecResult(returncode=0, stdout="", stderr="")

    alice = STANDARD_IDENTITIES["node-1"]
    ok = provision_node_identity(mock_driver, "testbed-node-1", alice)
    assert ok is True
    assert mock_driver.exec_command.call_count >= 2
