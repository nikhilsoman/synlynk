"""Verifies since/expect_author/expect thread correctly through the two
terminal-status call sites that consult gh_write_verified (#659, #860).
"""

import synlynk.dispatch as dispatch_mod
import synlynk.jobs as jobs_mod


def test_check_job_stall_passes_since_and_expect_author_and_expect(monkeypatch, tmp_path):
    log_file = tmp_path / "job.log"
    log_file.write_text("running\n")
    import os

    old_time = os.path.getmtime(log_file) - 6000  # stale beyond default 90 min review timeout
    os.utime(log_file, (old_time, old_time))

    captured = {}

    def fake_verified(target, expect, timeout=10, since=None, expect_author=None):
        captured["target"] = target
        captured["expect"] = expect
        captured["since"] = since
        captured["expect_author"] = expect_author
        return True  # verified delivered -> stall check should NOT kill

    monkeypatch.setattr(dispatch_mod, "gh_write_verified", fake_verified)

    job = {
        "status": "running",
        "log_file": str(log_file),
        "agent": "grok",
        "task_type": "review",
        "requires_gh_write": True,
        "gh_write_target": "pr:1038",
        "gh_write_author": "synlynk-synlynk-dev[bot]",
        "gh_write_expect": "review_posted",
        "started_at": "2026-08-18T10:00:00",
        "id": "job-test-stall",
    }
    killed = dispatch_mod._check_job_stall(job, {}, str(tmp_path / "sentinel.md"))

    assert killed is False
    assert captured["target"] == "pr:1038"
    assert captured["expect"] == "review_posted"
    assert captured["since"] == "2026-08-18T10:00:00"
    assert captured["expect_author"] == "synlynk-synlynk-dev[bot]"


def test_apply_gh_write_verification_uses_data_driven_expect(monkeypatch):
    captured = {}

    def fake_verified(target, expect, timeout=10, since=None, expect_author=None):
        captured["expect"] = expect
        captured["since"] = since
        captured["expect_author"] = expect_author
        return False  # not delivered

    monkeypatch.setattr(jobs_mod, "gh_write_verified", fake_verified)

    class FakeConn:
        def execute(self, *a, **k):
            return None

    status, verified_str = jobs_mod._apply_gh_write_verification(
        FakeConn(), "job-test-apply", True, "pr:1038", "done",
        since="2026-08-18T10:00:00", expect_author="synlynk-synlynk-dev[bot]",
        expect="review_posted",
    )

    assert captured["expect"] == "review_posted"
    assert captured["since"] == "2026-08-18T10:00:00"
    assert status == "succeeded_gh_write_failed"
    assert verified_str == "false"


def test_apply_gh_write_verification_defaults_expect_to_closed(monkeypatch):
    captured = {}

    def fake_verified(target, expect, timeout=10, since=None, expect_author=None):
        captured["expect"] = expect
        return True

    monkeypatch.setattr(jobs_mod, "gh_write_verified", fake_verified)

    class FakeConn:
        def execute(self, *a, **k):
            return None

    status, verified_str = jobs_mod._apply_gh_write_verification(
        FakeConn(), "job-test-default", True, "issue:701", "done",
    )

    assert captured["expect"] == "closed"
    assert status == "done"
    assert verified_str == "true"
