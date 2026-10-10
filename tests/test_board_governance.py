"""Tests for synlynk.board_governance: Ed25519-signed Sovereign Board proposal ledger."""
import subprocess

import pytest

from synlynk.board_governance import (
    ProposalGate,
    ProposalStatus,
    create_proposal,
    load_proposal,
    sign_proposal,
    verify_proposal_receipt,
)


@pytest.fixture
def genesis_key(tmp_path):
    key_path = tmp_path / "identity.key"
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path), "-C", "synlynk-identity"],
        capture_output=True,
        check=True,
    )
    pub_path = str(key_path) + ".pub"
    return str(key_path), pub_path


def test_create_proposal_defaults_to_pending(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.MASTER_GOAL,
        title="v0.25.0 Local oMLX Fleet",
        description="Expand sovereign AI inference to Apple Silicon",
        budget_usd=150.0,
    )

    assert prop.status == ProposalStatus.PENDING
    assert prop.proposal_id.startswith("prop-")
    assert prop.receipt is None

    loaded = load_proposal(prop.proposal_id)
    assert loaded == prop


def test_sign_and_verify_proposal(tmp_path, genesis_key, monkeypatch):
    key_path, pub_path = genesis_key
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.BUDGET_TOPUP,
        title="API Top-up",
        budget_usd=50.0,
    )

    signed = sign_proposal(prop.proposal_id, key_path=key_path)

    assert signed.status == ProposalStatus.APPROVED
    assert signed.receipt is not None
    assert signed.signer_identity is not None
    assert signed.signed_at is not None

    assert verify_proposal_receipt(signed, pub_path)

    # verification also works against the persisted copy on disk
    reloaded = load_proposal(prop.proposal_id)
    assert verify_proposal_receipt(reloaded, pub_path)


def test_tampered_proposal_fails_verification(tmp_path, genesis_key, monkeypatch):
    key_path, pub_path = genesis_key
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.BUDGET_TOPUP,
        title="API Top-up",
        budget_usd=50.0,
    )
    signed = sign_proposal(prop.proposal_id, key_path=key_path)

    # Malicious budget edit after signing must invalidate the receipt.
    signed.budget_usd = 5000.0
    assert not verify_proposal_receipt(signed, pub_path)


def test_verify_rejects_wrong_key(tmp_path, genesis_key, monkeypatch):
    key_path, pub_path = genesis_key
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.RELEASE_TAG,
        title="v0.25.0 release",
        budget_usd=0.0,
    )
    signed = sign_proposal(prop.proposal_id, key_path=key_path)

    other_key_path = tmp_path / "other_identity.key"
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(other_key_path)],
        capture_output=True,
        check=True,
    )
    other_pub_path = str(other_key_path) + ".pub"

    assert not verify_proposal_receipt(signed, other_pub_path)


def test_verify_rejects_unsigned_proposal(tmp_path, genesis_key, monkeypatch):
    _, pub_path = genesis_key
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.SPEC_RATIFICATION,
        title="Unsigned spec",
        budget_usd=0.0,
    )

    assert not verify_proposal_receipt(prop, pub_path)


def test_sign_proposal_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    prop = create_proposal(
        gate=ProposalGate.BOARD_ADMISSION,
        title="New board member",
        budget_usd=0.0,
    )

    with pytest.raises(FileNotFoundError):
        sign_proposal(prop.proposal_id, key_path=str(tmp_path / "nonexistent.key"))


def test_sign_proposal_missing_proposal_raises(tmp_path, genesis_key, monkeypatch):
    key_path, _ = genesis_key
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        sign_proposal("prop-doesnotexist", key_path=key_path)
