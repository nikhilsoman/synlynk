# tests/test_crypto_sovereign_identity.py
from pathlib import Path
import pytest

from synlynk import crypto


def test_generate_sovereign_identity():
    ident = crypto.generate_sovereign_identity()
    assert "identity_id" in ident
    assert ident["identity_id"].startswith("syn-sov-")
    assert "public_key" in ident
    assert "mnemonic" in ident
    words = ident["mnemonic"].split()
    assert len(words) == 12


def test_sign_and_verify_message():
    ident = crypto.generate_sovereign_identity()
    msg = "Approve Policy Amendment 2026-11-07"
    sig = crypto.sign_message(ident["private_key"], msg)
    assert isinstance(sig, str)
    assert len(sig) == 64

    # Verify pass
    assert crypto.verify_signature(ident["public_key"], msg, sig) is True

    # Tampered message fails
    assert crypto.verify_signature(ident["public_key"], msg + " (tampered)", sig) is False


def test_recover_identity_from_mnemonic():
    ident = crypto.generate_sovereign_identity()
    recovered = crypto.recover_from_mnemonic(ident["mnemonic"])
    assert recovered["identity_id"] == ident["identity_id"]
    assert recovered["public_key"] == ident["public_key"]
    assert recovered["private_key"] == ident["private_key"]


def test_save_and_load_sovereign_identity(tmp_path):
    ident = crypto.generate_sovereign_identity()
    id_file = tmp_path / "sovereign.json"
    crypto.save_identity(ident, id_file)

    assert id_file.is_file()
    # Check permissions 0o600
    assert (id_file.stat().st_mode & 0o777) == 0o600

    loaded = crypto.load_identity(id_file)
    assert loaded["identity_id"] == ident["identity_id"]
    assert loaded["public_key"] == ident["public_key"]
    # Private key should be preserved
    assert loaded["private_key"] == ident["private_key"]
