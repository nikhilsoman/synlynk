from pathlib import Path

import pytest

from synlynk import backup


def test_create_dr_package_stages_plaintext_temporarily(tmp_path, monkeypatch):
    source = tmp_path / "state.db"
    source.write_bytes(b"source")
    destination = tmp_path / "offline"
    seen = {}

    def fake_snapshot(source, output_dir, label):
        staging = Path(output_dir)
        snapshot = staging / f"{label}.db"
        snapshot.write_bytes(b"snapshot")
        seen["staging"] = staging
        return {"snapshot": str(snapshot), "sha256": "source-hash"}

    def fake_encrypt(snapshot, recipient, output_dir):
        encrypted = Path(output_dir) / "state.db.gpg"
        encrypted.parent.mkdir(parents=True, exist_ok=True)
        encrypted.write_bytes(b"encrypted")
        return {
            "encrypted_snapshot": str(encrypted),
            "encrypted_sha256": "encrypted-hash",
            "source_snapshot": snapshot,
            "recipient": recipient,
        }

    monkeypatch.setattr(backup, "create_snapshot", fake_snapshot)
    monkeypatch.setattr(backup, "encrypt_snapshot", fake_encrypt)

    result = backup.create_dr_package(
        source=source,
        output_dir=destination,
        label="state",
        recipient="dr@example.invalid",
    )

    assert result["plaintext_retained"] is False
    assert result["source_snapshot"] == "temporary plaintext removed after export"
    assert not seen["staging"].exists()
    assert (destination / "state.db.gpg").is_file()
    manifest = (destination / "state.db.json").read_text()
    assert "plaintext_retained" in manifest


def test_create_dr_package_requires_recipient(tmp_path):
    with pytest.raises(ValueError, match="GPG recipient"):
        backup.create_dr_package(source=tmp_path / "state.db")
