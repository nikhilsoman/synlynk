from unittest.mock import patch

from synlynk.sentinel import _extract_verified_by_ci


def _run_result(stdout="", stderr="", returncode=0):
    return type("Result", (), {"returncode": returncode, "stdout": stdout, "stderr": stderr})()


def _pr_checks_output(rows):
    """Build tab-separated `gh pr checks` stdout from (name, status) pairs."""
    lines = []
    for name, status in rows:
        lines.append("\t".join([name, status, "1m0s", "https://example.com/check"]))
    return "\n".join(lines) + "\n"


def _patch_gh(pr_checks_stdout, pr_checks_returncode=1, run_list_stdout=""):
    def _fake_run(cmd, **_kwargs):
        if len(cmd) >= 3 and cmd[:3] == ["gh", "pr", "checks"]:
            return _run_result(stdout=pr_checks_stdout, returncode=pr_checks_returncode)
        if len(cmd) >= 3 and cmd[:3] == ["gh", "run", "list"]:
            return _run_result(stdout=run_list_stdout, returncode=0)
        return _run_result(returncode=1)

    return patch("synlynk.sentinel.subprocess.run", side_effect=_fake_run)


def test_extract_verified_by_ci_ignores_pending_qa_gate_when_tests_pass():
    stdout = _pr_checks_output([
        ("test (3.8)", "pass"),
        ("test (3.10)", "pass"),
        ("test (3.12)", "pass"),
        ("qa-gate", "pending"),
    ])
    with _patch_gh(stdout, pr_checks_returncode=1):
        assert _extract_verified_by_ci(worktree_branch="feat/qa-gate-ci-workflow") is True


def test_extract_verified_by_ci_false_when_a_test_job_fails():
    stdout = _pr_checks_output([
        ("test (3.8)", "pass"),
        ("test (3.10)", "fail"),
        ("test (3.12)", "pass"),
        ("qa-gate", "pending"),
    ])
    with _patch_gh(stdout, pr_checks_returncode=1):
        assert _extract_verified_by_ci(worktree_branch="feat/qa-gate-ci-workflow") is False


def test_extract_verified_by_ci_none_when_a_test_job_is_pending():
    stdout = _pr_checks_output([
        ("test (3.8)", "pass"),
        ("test (3.10)", "pending"),
        ("test (3.12)", "pass"),
    ])
    with _patch_gh(stdout, pr_checks_returncode=1):
        assert _extract_verified_by_ci(worktree_branch="feat/qa-gate-ci-workflow") is None


def test_extract_verified_by_ci_falls_through_when_no_test_lines():
    stdout = _pr_checks_output([
        ("qa-gate", "pending"),
        ("lint", "pass"),
    ])
    with _patch_gh(stdout, pr_checks_returncode=1, run_list_stdout=""):
        assert _extract_verified_by_ci(worktree_branch="feat/qa-gate-ci-workflow") is None


def test_check_token_bloat_triggers_on_zero_files_with_high_tokens(tmp_path):
    from synlynk.sentinel import check_token_bloat

    sentinel_file = tmp_path / "sentinel.md"
    alerts = check_token_bloat(
        in_tokens=7_600_000,
        out_tokens=50_000,
        cost_usd=5.26,
        files_touched=0,
        job_id="job-cf837848",
        agent="codex",
        sentinel_path=str(sentinel_file),
    )

    assert len(alerts) == 2
    codes = {a["code"]: a for a in alerts}
    assert "TOKEN_BLOAT" in codes
    assert codes["TOKEN_BLOAT"]["severity"] == "CRITICAL"
    assert "7,650,000 tokens" in codes["TOKEN_BLOAT"]["message"]
    assert "0 files touched" in codes["TOKEN_BLOAT"]["message"]

    assert "COST_INFLATION" in codes
    assert codes["COST_INFLATION"]["severity"] == "CRITICAL"
    assert "$5.26" in codes["COST_INFLATION"]["message"]

    content = sentinel_file.read_text()
    assert "TOKEN_BLOAT" in content
    assert "COST_INFLATION" in content
    assert "job-cf837848" in content


def test_check_token_bloat_triggers_on_high_token_per_file_ratio(tmp_path):
    from synlynk.sentinel import check_token_bloat

    sentinel_file = tmp_path / "sentinel.md"
    alerts = check_token_bloat(
        in_tokens=2_100_000,
        out_tokens=10_000,
        cost_usd=2.50,
        files_touched=2,
        job_id="job-test",
        agent="agy",
        sentinel_path=str(sentinel_file),
    )

    assert len(alerts) == 1
    assert alerts[0]["code"] == "TOKEN_BLOAT"
    assert alerts[0]["severity"] == "CRITICAL"
    assert "1,055,000 tok/file" in alerts[0]["message"]

    content = sentinel_file.read_text()
    assert "TOKEN_BLOAT" in content
    assert "COST_INFLATION" not in content


def test_check_token_bloat_does_not_trigger_on_normal_usage(tmp_path):
    from synlynk.sentinel import check_token_bloat

    sentinel_file = tmp_path / "sentinel.md"
    alerts = check_token_bloat(
        in_tokens=50_000,
        out_tokens=2_000,
        cost_usd=0.20,
        files_touched=3,
        job_id="job-normal",
        agent="grok",
        sentinel_path=str(sentinel_file),
    )

    assert len(alerts) == 0
    assert not sentinel_file.exists()


def test_check_token_bloat_warn_cost_inflation(tmp_path):
    from synlynk.sentinel import check_token_bloat

    sentinel_file = tmp_path / "sentinel.md"
    alerts = check_token_bloat(
        in_tokens=100_000,
        out_tokens=5_000,
        cost_usd=3.50,
        files_touched=5,
        job_id="job-warn-cost",
        agent="claude",
        sentinel_path=str(sentinel_file),
    )

    assert len(alerts) == 1
    assert alerts[0]["code"] == "COST_INFLATION"
    assert alerts[0]["severity"] == "WARN"
    assert "$3.50" in alerts[0]["message"]


def test_check_token_bloat_scans_telemetry_file(tmp_path, monkeypatch):
    import json
    from synlynk.sentinel import check_token_bloat

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(parents=True, exist_ok=True)
    telemetry_file = tmp_path / ".synlynk" / "telemetry.json"
    telemetry_data = [
        {"type": "exec", "in_tokens": 10_000, "out_tokens": 1_000, "cost_usd": 0.05, "files_touched": 2},
        {"type": "job_terminal", "job_id": "job-cf837848", "in_tokens": 7_600_000, "out_tokens": 50_000, "cost_usd": 5.26, "files_touched": 0, "agent": "codex"},
    ]
    telemetry_file.write_text(json.dumps(telemetry_data))

    sentinel_file = tmp_path / ".synlynk" / "sentinel.md"
    alerts = check_token_bloat(sentinel_path=str(sentinel_file))

    assert len(alerts) == 2
    content = sentinel_file.read_text()
    assert "TOKEN_BLOAT" in content
    assert "COST_INFLATION" in content
    assert "job-cf837848" in content

