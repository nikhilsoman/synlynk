import json
import os

from synlynk.version_policy import check_version_policy


def test_check_version_policy_reads_min_version_from_workspace_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "workspace.json", "w", encoding="utf-8") as f:
        json.dump({"version_policy": {"min_version": "0.20.0"}}, f)
    ok, reason = check_version_policy(str(tmp_path), "0.10.0")
    assert ok is False
    assert "0.20.0" in reason


def test_check_version_policy_falls_back_to_legacy_config_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "config.json", "w", encoding="utf-8") as f:
        json.dump({"version_policy": {"min_version": "0.15.0"}}, f)
    ok, reason = check_version_policy(str(tmp_path), "0.30.0")
    assert ok is True


def test_check_version_policy_no_files_present(tmp_path):
    ok, reason = check_version_policy(str(tmp_path), "1.0.0")
    assert ok is True
    assert reason == "No version policy defined"
