import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest

from synlynk import backup as backup_module
from synlynk.backup import (
    create_snapshot,
    encrypt_snapshot,
    verify_encrypted_snapshot,
    verify_snapshot,
)


@pytest.fixture
def gpg_recipient(tmp_path, monkeypatch):
    gpg = shutil.which("gpg")
    if not gpg:
        pytest.skip("gpg is unavailable")
    home = Path(tempfile.mkdtemp(prefix="gpg-", dir="/tmp"))
    os.chmod(home, 0o700)
    monkeypatch.setenv("GNUPGHOME", str(home))
    try:
        subprocess.run(
            [
                gpg,
                "--batch",
                "--pinentry-mode",
                "loopback",
                "--passphrase",
                "",
                "--quick-gen-key",
                "Synlynk DR Test <dr-test@synlynk.invalid>",
                "rsa2048",
                "encrypt",
                "1d",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        pytest.skip(f"gpg key generation unavailable: {error.stderr.strip()}")
    keys = subprocess.run(
        [gpg, "--batch", "--list-keys", "--with-colons"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout
    return next(line.split(":")[9] for line in keys.splitlines() if line.startswith("fpr:"))


def test_create_snapshot_uses_online_backup_and_writes_manifest(tmp_path):
    source = tmp_path / "state.db"
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, body TEXT)")
    conn.execute("INSERT INTO events (body) VALUES ('kept')")
    conn.commit()
    conn.close()

    result = create_snapshot(source=source, output_dir=tmp_path / "backups")
    snapshot_path = tmp_path / "backups" / result["snapshot"].split("/")[-1]
    manifest_path = snapshot_path.with_suffix(".json")

    assert snapshot_path.exists()
    assert manifest_path.exists()
    assert not list((tmp_path / "backups").glob(".*.tmp-wal"))
    assert not list((tmp_path / "backups").glob(".*.tmp-shm"))
    assert result["integrity_check"] == "ok"
    assert result["row_counts"]["events"] == 1
    assert json.loads(manifest_path.read_text())["sha256"] == result["sha256"]
    assert verify_snapshot(snapshot_path)["integrity_check"] == "ok"


def test_verify_snapshot_rejects_corruption(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not sqlite")

    try:
        verify_snapshot(path)
    except sqlite3.DatabaseError:
        pass
    else:
        raise AssertionError("corrupt snapshot unexpectedly verified")


def test_encrypt_and_verify_snapshot_without_leaving_plaintext(tmp_path, gpg_recipient):
    source = tmp_path / "state.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, body TEXT)")
    conn.execute("INSERT INTO events (body) VALUES ('secret')")
    conn.commit()
    conn.close()
    snapshot_dir = tmp_path / "snapshots"
    snapshot = create_snapshot(source=source, output_dir=snapshot_dir)
    snapshot_path = snapshot_dir / Path(snapshot["snapshot"]).name
    export_dir = tmp_path / "off-machine"

    encrypted = encrypt_snapshot(snapshot_path, gpg_recipient, output_dir=export_dir)
    encrypted_path = export_dir / Path(encrypted["encrypted_snapshot"]).name
    assert encrypted_path.exists()
    assert b"secret" not in encrypted_path.read_bytes()
    assert verify_encrypted_snapshot(encrypted_path)["integrity_check"] == "ok"
    assert not list(export_dir.glob("*.db"))
    assert not list(tmp_path.glob("synlynk-dr-verify-*"))


def test_encrypt_requires_recipient(tmp_path):
    source = tmp_path / "state.db"
    sqlite3.connect(source).close()
    with pytest.raises(ValueError, match="recipient"):
        encrypt_snapshot(source, "")


def test_verify_encrypted_snapshot_can_use_keychain_passphrase(
    tmp_path, gpg_recipient, monkeypatch
):
    source = tmp_path / "state.db"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE marker (value TEXT)")
    conn.execute("INSERT INTO marker VALUES ('keychain')")
    conn.commit()
    conn.close()
    snapshot_dir = tmp_path / "snapshots"
    snapshot = create_snapshot(source=source, output_dir=snapshot_dir)
    snapshot_path = snapshot_dir / Path(snapshot["snapshot"]).name
    encrypted = encrypt_snapshot(snapshot_path, gpg_recipient, output_dir=tmp_path / "export")

    calls = []
    monkeypatch.setattr(
        backup_module,
        "_keychain_passphrase",
        lambda service: calls.append(service) or "",
    )
    evidence = verify_encrypted_snapshot(
        encrypted["encrypted_snapshot"], keychain_service="com.example.dr"
    )
    assert evidence["integrity_check"] == "ok"
    assert calls == ["com.example.dr"]


def test_verify_encrypted_snapshot_allows_gpg_agent_pinentry(
    tmp_path, gpg_recipient, monkeypatch
):
    source = tmp_path / "state.db"
    sqlite3.connect(source).close()
    snapshot = create_snapshot(source=source, output_dir=tmp_path / "snapshots")
    encrypted = encrypt_snapshot(
        snapshot["snapshot"], gpg_recipient, output_dir=tmp_path / "export"
    )

    original_run = backup_module.subprocess.run
    commands = []

    def run(command, *args, **kwargs):
        if command[0] == shutil.which("gpg") and "--decrypt" in command:
            commands.append(command)
            assert "--batch" not in command
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(backup_module.subprocess, "run", run)
    assert verify_encrypted_snapshot(encrypted["encrypted_snapshot"])["integrity_check"] == "ok"
    assert len(commands) == 1
