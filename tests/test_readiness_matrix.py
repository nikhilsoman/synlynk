import json
import os
import stat
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from synlynk.readiness import (
    evaluate_readiness_matrix,
    format_readiness_table,
    cmd_doctor_readiness,
    check_point_1_role_tokens,
    check_point_2_sandbox_egress,
    check_point_3_policy_authority,
    check_point_4_git_shim,
)


def test_point_1_role_tokens_missing(tmp_path):
    # No apps dir or tokens
    res = check_point_1_role_tokens(apps_dir=str(tmp_path / "apps"))
    assert res["status"] in ("WARN", "FAIL")
    assert "No role tokens found" in res["message"] or "missing" in res["message"].lower()


def test_point_1_role_tokens_valid(tmp_path):
    apps_dir = tmp_path / "apps"
    qa_dir = apps_dir / "qa"
    qa_dir.mkdir(parents=True)
    token_file = qa_dir / "qa.token.json"
    import time
    token_file.write_text(json.dumps({"token": "ghs_test123", "expires_at": time.time() + 3600}))

    res = check_point_1_role_tokens(apps_dir=str(apps_dir))
    assert res["status"] == "PASS"
    assert "qa" in res["details"]


def test_point_2_sandbox_egress_success():
    with patch("socket.create_connection") as mock_conn:
        mock_sock = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_sock
        res = check_point_2_sandbox_egress()
        assert res["status"] == "PASS"
        assert "Egress to api.github.com:443 verified" in res["message"]


def test_point_2_sandbox_egress_failure():
    with patch("socket.create_connection", side_effect=OSError("Network unreachable")):
        res = check_point_2_sandbox_egress()
        assert res["status"] == "FAIL"
        assert "unreachable" in res["message"].lower()


def test_point_3_policy_authority_missing(tmp_path):
    res = check_point_3_policy_authority(repo_path=str(tmp_path))
    assert res["status"] in ("WARN", "FAIL")
    assert "policy.json missing" in res["message"]


def test_point_3_policy_authority_valid(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    policy_file = synlynk_dir / "policy.json"
    policy_file.write_text(json.dumps({
        "version": 1,
        "qa_authority": {"can_approve": True, "can_merge": True},
        "task_allocation": {"default": "codex"}
    }))

    res = check_point_3_policy_authority(repo_path=str(tmp_path))
    assert res["status"] == "PASS"
    assert "Policy rules valid" in res["message"]


def test_point_4_git_shim_missing(tmp_path):
    shim_path = str(tmp_path / "gh")
    res = check_point_4_git_shim(shim_path=shim_path, env_path="")
    assert res["status"] == "WARN"
    assert "not installed" in res["message"].lower()


def test_point_4_git_shim_valid(tmp_path):
    shim_dir = tmp_path / "gh-shim"
    shim_dir.mkdir()
    shim_file = shim_dir / "gh"
    shim_file.write_text("#!/bin/sh\necho gh shim\n")
    shim_file.chmod(stat.S_IRWXU)

    res = check_point_4_git_shim(
        shim_path=str(shim_file),
        env_path=f"{shim_dir}:{os.environ.get('PATH', '')}"
    )
    assert res["status"] == "PASS"
    assert "Git shim active" in res["message"]


def test_evaluate_readiness_matrix():
    matrix = evaluate_readiness_matrix()
    assert "points" in matrix
    assert len(matrix["points"]) == 4
    point_keys = [p["key"] for p in matrix["points"]]
    assert point_keys == ["role_tokens", "sandbox_egress", "policy_authority", "git_shim"]
    assert "overall_status" in matrix
    assert matrix["overall_status"] in ("PASS", "WARN", "FAIL")


def test_format_readiness_table():
    matrix = {
        "overall_status": "PASS",
        "points": [
            {
                "key": "role_tokens",
                "name": "Point 1: Role Token Validity",
                "status": "PASS",
                "message": "Tokens active",
                "remediation": "synlynk daemon token refresh",
            },
            {
                "key": "sandbox_egress",
                "name": "Point 2: Sandbox Egress",
                "status": "PASS",
                "message": "Egress verified",
                "remediation": "Check network connection",
            },
            {
                "key": "policy_authority",
                "name": "Point 3: Policy Authority",
                "status": "PASS",
                "message": "Policy valid",
                "remediation": "synlynk policy sync",
            },
            {
                "key": "git_shim",
                "name": "Point 4: Git Shim Integrity",
                "status": "PASS",
                "message": "Shim active in PATH",
                "remediation": "eval $(synlynk gh --shim-env)",
            },
        ],
    }
    table = format_readiness_table(matrix)
    assert "SYNLYNK 4-POINT READINESS MATRIX" in table
    assert "Point 1: Role Token Validity" in table
    assert "PASS" in table


def test_cmd_doctor_readiness_returns_zero_when_pass():
    with patch("synlynk.readiness.evaluate_readiness_matrix") as mock_eval:
        mock_eval.return_value = {
            "overall_status": "PASS",
            "points": [
                {"key": "k", "name": "Point 1", "status": "PASS", "message": "ok", "remediation": ""}
            ]
        }
        ret = cmd_doctor_readiness()
        assert ret == 0
