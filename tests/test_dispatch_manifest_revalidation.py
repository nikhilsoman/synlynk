import json
import os

from synlynk.dispatch import _preflight_dispatch


def test_missing_manifest_triggers_inline_discovery(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _preflight_dispatch(
        "claude", dispatch_flags=[], _task_hint="test task", permissions=[],
        db_conn=None, force_agent=False,
    )
    assert os.path.exists(os.path.join(".synlynk", "harnesses", "claude.json"))


def test_version_hash_mismatch_fails_closed_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    with open(".synlynk/harnesses/claude.json", "w") as f:
        json.dump({"harness": "claude", "cli_version_hash": "stale-hash-0000"}, f)
    result = _preflight_dispatch(
        "claude", dispatch_flags=[], _task_hint="test task", permissions=[],
        db_conn=None, force_agent=False,
    )
    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_MANIFEST_REVALIDATION_FAILED"


def test_version_hash_mismatch_passes_with_force_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    with open(".synlynk/harnesses/claude.json", "w") as f:
        json.dump({"harness": "claude", "cli_version_hash": "stale-hash-0000"}, f)
    result = _preflight_dispatch(
        "claude", dispatch_flags=[], _task_hint="test task", permissions=[],
        db_conn=None, force_agent=True,
    )
