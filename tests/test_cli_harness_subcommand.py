import json
import subprocess
import sys


def test_harness_onboard_writes_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "synlynk.cli", "harness", "onboard", "--harness", "claude"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".synlynk" / "harnesses" / "claude.json").exists()


def test_harness_probe_without_discover_reads_existing_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest_dir = tmp_path / ".synlynk" / "harnesses"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "claude.json").write_text(
        json.dumps({"harness": "claude", "cli_version_hash": "abc123"})
    )
    result = subprocess.run(
        [sys.executable, "-m", "synlynk.cli", "harness", "probe", "--harness", "claude"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "abc123" in result.stdout
