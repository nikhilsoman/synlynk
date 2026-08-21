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
