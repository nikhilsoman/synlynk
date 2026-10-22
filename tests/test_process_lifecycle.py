import signal

import pytest

from synlynk.process_lifecycle import capture_termination_domain, terminate_job_domain


def host_domain(**overrides):
    domain = {
        "version": 1,
        "kind": "host_process_group",
        "leader_pid": 4242,
        "pgid": 4242,
        "leader_identity": {"start_time": "launch"},
        "dispatcher_pgid": 99,
    }
    domain.update(overrides)
    return domain


def test_capture_domain_marks_already_exited_process_unverified():
    class ExitedProcess:
        pid = 4242

        def poll(self):
            return 0

    domain = capture_termination_domain(ExitedProcess())

    assert domain["version"] == 1
    assert domain["kind"] == "unknown"
    assert domain["reason_code"] == "leader_already_exited"


def test_capture_host_domain_binds_group_to_launch_identity(monkeypatch):
    import synlynk.process_lifecycle as lifecycle

    class RunningProcess:
        pid = 4242

        def poll(self):
            return None

    monkeypatch.setattr(
        lifecycle, "capture_process_identity",
        lambda pid, proc=None: {"start_time": "launch"},
    )
    monkeypatch.setattr(lifecycle.os, "getpgid", lambda pid: 4242)
    monkeypatch.setattr(lifecycle.os, "getpgrp", lambda: 99)

    domain = capture_termination_domain(RunningProcess(), parent_job_id="job-parent")

    assert domain == {
        "version": 1,
        "kind": "host_process_group",
        "leader_pid": 4242,
        "leader_identity": {"start_time": "launch"},
        "pgid": 4242,
        "dispatcher_pgid": 99,
        "parent_job_id": "job-parent",
    }


@pytest.mark.parametrize(
    "domain",
    [
        host_domain(leader_pid=0, pgid=0),
        host_domain(leader_pid=1, pgid=1),
        host_domain(pgid=99),
    ],
)
def test_terminate_domain_refuses_unsafe_process_groups(domain):
    signals = []

    result = terminate_job_domain(
        domain,
        inspect_process_group=lambda value: {"state": "running", "identity_match": True},
        signal_process_group=lambda pgid, sig: signals.append((pgid, sig)),
    )

    assert result.process_state == "cleanup_unverified"
    assert result.attempted is False
    assert signals == []


def test_terminate_domain_refuses_reused_or_unverifiable_identity():
    signals = []

    result = terminate_job_domain(
        host_domain(),
        inspect_process_group=lambda value: {
            "state": "identity_mismatch", "identity_match": False,
        },
        signal_process_group=lambda pgid, sig: signals.append((pgid, sig)),
    )

    assert result.process_state == "cleanup_unverified"
    assert result.reason_code == "leader_identity_mismatch"
    assert signals == []


def test_terminate_domain_escalates_and_verifies_group_death():
    observations = iter([
        {"state": "running", "identity_match": True},
        {"state": "running", "identity_match": True},
        {"state": "stopped", "identity_match": True},
    ])
    signals = []

    result = terminate_job_domain(
        host_domain(),
        grace_seconds=0,
        inspect_process_group=lambda value: next(observations),
        signal_process_group=lambda pgid, sig: signals.append((pgid, sig)),
    )

    assert signals == [(4242, signal.SIGTERM), (4242, signal.SIGKILL)]
    assert result.process_state == "stopped_verified"
    assert result.attempted is True
    assert result.method == "host_process_group"


def test_terminate_domain_accepts_verified_graceful_death():
    observations = iter([
        {"state": "running", "identity_match": True},
        {"state": "stopped", "identity_match": True},
    ])
    signals = []

    result = terminate_job_domain(
        host_domain(),
        grace_seconds=1,
        inspect_process_group=lambda value: next(observations),
        signal_process_group=lambda pgid, sig: signals.append((pgid, sig)),
        sleep=lambda seconds: None,
    )

    assert signals == [(4242, signal.SIGTERM)]
    assert result.process_state == "stopped_verified"


def test_cleanup_inspection_error_expires_to_unknown():
    signals = []

    result = terminate_job_domain(
        host_domain(),
        inspect_process_group=lambda value: {"state": "error", "reason": "ps_failed"},
        signal_process_group=lambda pgid, sig: signals.append((pgid, sig)),
    )

    assert result.process_state == "cleanup_unverified"
    assert result.reason_code == "inspection_error"
    assert signals == []


def test_non_posix_cleanup_is_explicitly_unverified():
    result = terminate_job_domain(
        host_domain(),
        platform_name="nt",
        inspect_process_group=lambda value: pytest.fail("must not inspect"),
        signal_process_group=lambda pgid, sig: pytest.fail("must not signal"),
    )

    assert result.process_state == "cleanup_unverified"
    assert result.reason_code == "unsupported_platform"


def test_container_domain_stops_runtime_not_client():
    observations = iter([
        {"state": "running"},
        {"state": "stopped"},
    ])
    stopped = []

    result = terminate_job_domain(
        {
            "version": 1,
            "kind": "container",
            "container_id": "container-123",
            "leader_pid": 777,
            "leader_identity": {"start_time": "launch"},
        },
        inspect_container=lambda container_id: next(observations),
        stop_container=lambda container_id, grace: stopped.append((container_id, grace)),
        signal_process_group=lambda pgid, sig: pytest.fail("must not signal docker client"),
    )

    assert stopped == [("container-123", 5.0)]
    assert result.process_state == "stopped_verified"
    assert result.method == "container"
