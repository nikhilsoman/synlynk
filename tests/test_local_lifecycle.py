import json
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from synlynk.local_credentials import LocalCredentialStore
from synlynk.local_lifecycle import (
    LIFECYCLE_MODEL_ID,
    LifecycleError,
    OmlxClient,
    LocalLifecycleManager,
    HostMemorySnapshot,
    check_memory_admission,
    parse_memory_pressure,
    parse_swap_usage,
    parse_vm_stat,
)


class Credentials:
    def get(self):
        return "sk-do-not-leak"


def test_model_api_uses_authenticated_model_specific_paths(monkeypatch):
    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"data":[{"id":"Ornith-1.0-9B-4bit"}]}'

    def fake_urlopen(request, timeout=None):
        seen.append((request.full_url, request.get_method(), request.get_header("Authorization")))
        return Response()

    monkeypatch.setattr("synlynk.local_lifecycle.urllib.request.urlopen", fake_urlopen)
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    assert client.list_models() == [LIFECYCLE_MODEL_ID]
    client.load_model(LIFECYCLE_MODEL_ID)
    client.unload_model(LIFECYCLE_MODEL_ID)
    assert seen == [
        ("http://127.0.0.1:8000/v1/models", "GET", "Bearer sk-do-not-leak"),
        ("http://127.0.0.1:8000/v1/models/Ornith-1.0-9B-4bit/load", "POST", "Bearer sk-do-not-leak"),
        ("http://127.0.0.1:8000/v1/models/Ornith-1.0-9B-4bit/unload", "POST", "Bearer sk-do-not-leak"),
    ]


@pytest.mark.parametrize("status,reason", [(401, "authentication_failed"), (404, "unsupported_load_contract"), (507, "insufficient_memory")])
def test_api_errors_are_classified_without_echoing_credentials(monkeypatch, status, reason):
    def fail(*args, **kwargs):
        raise HTTPError("http://127.0.0.1:8000", status, "sk-do-not-leak rejected", {}, None)

    monkeypatch.setattr("synlynk.local_lifecycle.urllib.request.urlopen", fail)
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    with pytest.raises(LifecycleError) as error:
        client.load_model(LIFECYCLE_MODEL_ID)
    assert error.value.reason_code == reason
    assert "sk-do-not-leak" not in str(error.value)


def test_missing_persistent_settings_key_is_classified_without_network_request(monkeypatch):
    from synlynk.local_credentials import CredentialUnavailable

    class MissingSettingsCredential:
        def get(self):
            raise CredentialUnavailable("oMLX settings credential is unavailable")

    def unexpected_request(*args, **kwargs):
        raise AssertionError("request must not be sent without the persistent settings key")

    monkeypatch.setattr("synlynk.local_lifecycle.urllib.request.urlopen", unexpected_request)
    client = OmlxClient("http://127.0.0.1:8000", MissingSettingsCredential())
    with pytest.raises(LifecycleError) as error:
        client.list_models()
    assert error.value.reason_code == "credential_unavailable"
    assert error.value.phase == "authentication"


def test_model_allowlist_rejects_everything_except_ornith():
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    with pytest.raises(LifecycleError, match="approved Ornith model"):
        client.load_model("Qwen2.5-Coder-14B-Instruct-4bit")


def test_version_validation_accepts_only_verified_omlx_053():
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    assert client.validate_version("0.5.3") == "0.5.3"
    with pytest.raises(LifecycleError) as error:
        client.validate_version("0.6.0")
    assert error.value.reason_code == "unsupported_omlx_version"


def test_omlx_subprocess_does_not_receive_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-do-not-leak")
    seen = {}

    def run(args, **kwargs):
        seen.update(args=args, **kwargs)
        return Mock(returncode=0, stdout="0.5.3", stderr="")

    monkeypatch.setattr("synlynk.local_lifecycle.subprocess.run", run)
    client = OmlxClient("http://127.0.0.1:8000", Credentials())
    client.installed_version()
    assert "sk-do-not-leak" not in repr(seen["args"])
    assert "sk-do-not-leak" not in repr(seen["env"])


def test_foreground_server_launch_uses_sanitized_serve_process(monkeypatch):
    from synlynk.local_lifecycle import _start_omlx_foreground

    monkeypatch.setenv("OPENAI_API_KEY", "frontier-secret")
    monkeypatch.setenv("OMLX_API_KEY", "omlx-secret")
    monkeypatch.setattr("synlynk.local_lifecycle.shutil.which", lambda name: "/opt/homebrew/bin/omlx")
    seen = {}

    class Process:
        pid = 4321

    def popen(args, **kwargs):
        seen.update(args=args, **kwargs)
        return Process()

    monkeypatch.setattr("synlynk.local_lifecycle.subprocess.Popen", popen)
    monkeypatch.setattr("synlynk.local_lifecycle._process_start_identity", lambda pid: 1000.0)
    identity = _start_omlx_foreground()

    assert identity == (4321, 1000.0)
    assert seen["args"] == ["/opt/homebrew/bin/omlx", "serve", "--host", "127.0.0.1", "--port", "8000"]
    assert seen["shell"] is False
    assert seen["start_new_session"] is True
    assert seen["stdin"] is seen["stdout"] is seen["stderr"]
    assert "OPENAI_API_KEY" not in seen["env"]
    assert "OMLX_API_KEY" not in seen["env"]


def test_verified_process_termination_checks_start_identity(monkeypatch):
    from synlynk.local_lifecycle import _terminate_owned_process

    signals = []
    monkeypatch.setattr("synlynk.local_lifecycle._process_start_identity", lambda pid: 1000.0)
    monkeypatch.setattr("synlynk.local_lifecycle.os.kill", lambda pid, sig: signals.append((pid, sig)))
    assert _terminate_owned_process(4321, 1000.0)
    assert signals == [(4321, 15)]


def test_replaced_process_is_not_signaled(monkeypatch):
    from synlynk.local_lifecycle import _terminate_owned_process

    signals = []
    monkeypatch.setattr("synlynk.local_lifecycle._process_start_identity", lambda pid: 2000.0)
    monkeypatch.setattr("synlynk.local_lifecycle.os.kill", lambda pid, sig: signals.append((pid, sig)))
    assert not _terminate_owned_process(4321, 1000.0)
    assert signals == []


def test_memory_output_parsers_and_gate_fail_closed():
    vm_stat = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 100.\nPages inactive: 200.\nPages speculative: 10.\nPages purgeable: 5.\n"
    assert parse_vm_stat(vm_stat) == 315 * 16384
    assert parse_memory_pressure("System-wide memory free percentage: 45%") == "normal"
    assert parse_memory_pressure("System-wide memory free percentage: 4%") == "warning"
    assert parse_swap_usage("vm.swapusage: total = 2048.00M used = 1024.00M free = 1024.00M") == 1024 * 1024**2
    baseline = HostMemorySnapshot(24 * 1024**3, 9 * 1024**3, "normal", 100 * 1024**2)
    latest = HostMemorySnapshot(24 * 1024**3, 8 * 1024**3, "normal", 300 * 1024**2)
    check_memory_admission(baseline, latest)
    with pytest.raises(LifecycleError) as error:
        check_memory_admission(baseline, HostMemorySnapshot(24 * 1024**3, 7 * 1024**3, "normal", 100 * 1024**2))
    assert error.value.reason_code == "insufficient_memory"


def test_memory_gate_rejects_swap_growth_and_unavailable_signals():
    before = HostMemorySnapshot(24 * 1024**3, 9 * 1024**3, "normal", 100 * 1024**2)
    with pytest.raises(LifecycleError) as error:
        check_memory_admission(before, HostMemorySnapshot(24 * 1024**3, 9 * 1024**3, "normal", 357 * 1024**2))
    assert error.value.reason_code == "memory_pressure"
    with pytest.raises(LifecycleError):
        check_memory_admission(before, None)


class FakeRuntimeClient:
    def __init__(self, models=None):
        self.models = list(models or [])
        self.loads = []
        self.unloads = []
        self.versions = []

    def list_models(self):
        return list(self.models)

    def installed_version(self):
        self.versions.append(True)
        return "0.5.3"

    def load_model(self, model_id):
        self.loads.append(model_id)
        self.models.append(model_id)

    def unload_model(self, model_id):
        self.unloads.append(model_id)
        self.models.remove(model_id)


def make_manager(tmp_path, *, client=None, endpoint_probe=None, identity=None,
                 start_service=None, stop_service=None, now=None, alive=None,
                 memory_admission=None, current_process_identity=None):
    if endpoint_probe is None:
        probes = iter([False, True])
        endpoint_probe = lambda: next(probes, True)
    return LocalLifecycleManager(
        client=client or FakeRuntimeClient(),
        state_path=str(tmp_path / "local-runtime.json"),
        lock_path=str(tmp_path / "local-runtime.lock"),
        endpoint_probe=endpoint_probe,
        process_identity=identity or (lambda: (4321, 1000.0)),
        start_service=start_service or (lambda: (4321, 1000.0)),
        stop_service=stop_service or (lambda *_identity: None),
        clock=now or (lambda: 1000.0),
        process_identity_alive=alive or (lambda pid, started: True),
        memory_admission=memory_admission or (lambda: None),
        current_process_identity=current_process_identity or (lambda: (9999, 1000.0)),
    )


def test_manager_starts_absent_runtime_loads_ornith_and_persists_ownership(tmp_path):
    client = FakeRuntimeClient()
    starts = []
    manager = make_manager(tmp_path, client=client, start_service=lambda: (starts.append(True) or (4321, 1000.0)))
    result = manager.ensure_ready()
    assert result.ready and result.managed
    assert client.loads == [LIFECYCLE_MODEL_ID]
    assert starts == [True]
    state = json.loads((tmp_path / "local-runtime.json").read_text())
    assert state["ownership"]["pid"] == 4321
    assert state["ownership"]["process_start"] == 1000.0
    assert state["ownership"]["owner_kind"] == "synlynk_foreground"
    assert state["ownership"]["supervisor_label"] == "com.synlynk.daemon"
    assert "credential" not in json.dumps(state).lower()


def test_operator_owned_ornith_is_accepted_without_start_or_load(tmp_path):
    client = FakeRuntimeClient([LIFECYCLE_MODEL_ID])
    starts = []
    manager = make_manager(tmp_path, client=client, endpoint_probe=lambda: True,
                           start_service=lambda: (starts.append(True) or (4321, 1000.0)))
    result = manager.ensure_ready()
    assert result.ready and not result.managed
    assert client.loads == []
    assert starts == []


def test_operator_owned_runtime_without_ornith_is_left_untouched(tmp_path):
    client = FakeRuntimeClient(["Qwen2.5-Coder-14B-Instruct-4bit"])
    starts = []
    manager = make_manager(tmp_path, client=client, endpoint_probe=lambda: True,
                           start_service=lambda: (starts.append(True) or (4321, 1000.0)))
    with pytest.raises(LifecycleError) as error:
        manager.ensure_ready()
    assert error.value.reason_code == "operator_owned_model_missing"
    assert client.loads == []
    assert starts == []


def test_manual_stop_cannot_stop_operator_owned_omlx(tmp_path):
    client = FakeRuntimeClient([LIFECYCLE_MODEL_ID])
    stopped = []
    manager = make_manager(tmp_path, client=client, endpoint_probe=lambda: True,
                           stop_service=lambda *_identity: stopped.append(True))
    manager.ensure_ready()
    assert manager.stop_managed_service() is False
    assert stopped == []


def test_start_race_with_old_or_unidentifiable_process_fails_without_claiming_ownership(tmp_path):
    client = FakeRuntimeClient()
    identities = iter([None, (777, 10.0)])
    endpoints = iter([False, True])
    manager = make_manager(tmp_path, client=client,
                           endpoint_probe=lambda: next(endpoints),
                           identity=lambda: next(identities))
    with pytest.raises(LifecycleError) as error:
        manager.ensure_ready()
    assert error.value.reason_code == "ownership_ambiguous"
    assert client.loads == []
    assert not (tmp_path / "local-runtime.json").exists()


def test_bind_race_stops_only_its_child_and_does_not_claim_other_listener(tmp_path):
    client = FakeRuntimeClient()
    stopped = []
    endpoints = iter([False, True])
    manager = make_manager(
        tmp_path, client=client, endpoint_probe=lambda: next(endpoints),
        identity=lambda: (8888, 500.0),
        start_service=lambda: (stopped.append("started") or (4321, 1000.0)),
        stop_service=lambda pid, started: stopped.append((pid, started)),
    )
    with pytest.raises(LifecycleError) as error:
        manager.ensure_ready()
    assert error.value.reason_code == "ownership_ambiguous"
    assert stopped == ["started", (4321, 1000.0)]
    assert not (tmp_path / "local-runtime.json").exists()


def test_preexisting_legacy_ownership_record_is_not_control_authority(tmp_path):
    state_path = tmp_path / "local-runtime.json"
    state_path.write_text(json.dumps({"ownership": {"pid": 4321, "process_start": 1000.0}}))
    stopped = []
    manager = make_manager(
        tmp_path, client=FakeRuntimeClient([LIFECYCLE_MODEL_ID]),
        endpoint_probe=lambda: True, stop_service=lambda *args: stopped.append(args),
    )
    result = manager.ensure_ready()
    assert result.ready and not result.managed
    assert manager.stop_managed_service() is False
    assert stopped == []


def test_restart_reconciles_persisted_ownership_without_restarting(tmp_path):
    client = FakeRuntimeClient()
    manager = make_manager(tmp_path, client=client)
    manager.ensure_ready()
    starts = []
    restarted = make_manager(tmp_path, client=FakeRuntimeClient([LIFECYCLE_MODEL_ID]),
                             endpoint_probe=lambda: True,
                             start_service=lambda: (starts.append(True) or (4321, 1000.0)))
    result = restarted.ensure_ready()
    assert result.ready and result.managed
    assert starts == []


def test_active_job_reservation_prevents_idle_shutdown(tmp_path):
    client = FakeRuntimeClient()
    stopped = []
    manager = make_manager(tmp_path, client=client, stop_service=lambda *_identity: stopped.append(True))
    manager.ensure_ready()
    manager.record_reservation_started("dispatch-1")
    manager.tick(now=5000.0)
    assert stopped == []
    assert client.unloads == []


def test_owned_runtime_stops_only_after_900_idle_seconds(tmp_path):
    client = FakeRuntimeClient()
    stopped = []
    manager = make_manager(tmp_path, client=client, stop_service=lambda *_identity: stopped.append(True))
    manager.ensure_ready()
    manager.record_job_finished("job-1")
    manager.tick(now=1899.0)
    assert stopped == []
    manager.tick(now=1900.0)
    assert stopped == [True]
    assert client.unloads == [LIFECYCLE_MODEL_ID]


def test_active_job_lease_prevents_idle_shutdown(tmp_path):
    client = FakeRuntimeClient()
    stopped = []
    manager = make_manager(tmp_path, client=client, stop_service=lambda *_identity: stopped.append(True))
    manager.ensure_ready()
    manager.record_job_started("job-1")
    manager.tick(now=5000.0)
    assert stopped == []


def test_reservation_fails_closed_when_current_process_identity_is_unknown(tmp_path):
    manager = make_manager(tmp_path, current_process_identity=lambda: None)
    with pytest.raises(LifecycleError) as error:
        manager.record_reservation_started("dispatch-unknown")
    assert error.value.reason_code == "process_identity_unavailable"


def test_cli_status_reports_model_and_ownership_without_secret(capsys, tmp_path, monkeypatch):
    from synlynk.local_agent import cmd_local_lifecycle
    from synlynk import local_failure_reporter

    manager = make_manager(
        tmp_path,
        client=FakeRuntimeClient([LIFECYCLE_MODEL_ID]),
        endpoint_probe=lambda: True,
    )
    monkeypatch.setattr(local_failure_reporter, "outbox_status", lambda: {"pending": 2, "tracked": 3})
    assert cmd_local_lifecycle("status", manager=manager) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["running"] is True
    assert payload["model_loaded"] is True
    assert payload["managed"] is False
    assert payload["failure_reporting"] == {"pending": 2, "tracked": 3}
    assert "sk-do-not-leak" not in output


def test_prepare_local_pilot_retries_once_with_same_manager(monkeypatch):
    from synlynk import local_lifecycle

    class Manager:
        calls = 0

        def ensure_ready(self):
            self.calls += 1
            raise LifecycleError("omlx_unreachable", "safe failure")

    manager = Manager()
    monkeypatch.setattr(local_lifecycle, "LocalLifecycleManager", lambda: manager)
    monkeypatch.setattr("synlynk.local_failure_reporter.report_local_failure", lambda _error: False)
    with pytest.raises(LifecycleError):
        local_lifecycle.prepare_local_pilot("/repo", "dispatch-1", "test_summary")
    assert manager.calls == 2


def test_prepare_local_pilot_holds_reservation_until_dispatch(monkeypatch):
    from synlynk import local_lifecycle

    class Manager:
        reservation = None

        def ensure_ready(self):
            return local_lifecycle.LocalRuntimeResult(True, LIFECYCLE_MODEL_ID, True, 123)

        def record_reservation_started(self, reservation_id):
            self.reservation = reservation_id

    manager = Manager()
    monkeypatch.setattr(local_lifecycle, "LocalLifecycleManager", lambda: manager)
    result = local_lifecycle.prepare_local_pilot("/repo", "dispatch-1", "test_summary")
    assert result.ready
    import hashlib
    assert manager.reservation == hashlib.sha256(b"dispatch-1").hexdigest()


def test_local_failure_reporter_redacts_and_rate_limits(tmp_path):
    from synlynk.local_failure_reporter import report_local_failure

    secret_error = LifecycleError("authentication_failed", "token sk-secret refused")
    calls = []
    writer = lambda fingerprint, error, version: calls.append((fingerprint, error, version)) or False
    path = str(tmp_path / "outbox.json")
    assert report_local_failure(secret_error, path=path, now=1000, issue_writer=writer) is False
    assert report_local_failure(secret_error, path=path, now=2000, issue_writer=writer) is False
    payload = (tmp_path / "outbox.json").read_text()
    assert len(calls) == 1
    assert "sk-secret" not in payload
    assert "token" not in payload
    assert '"outbox": true' in payload


def test_local_failure_reporter_retries_pending_outbox(tmp_path):
    from synlynk.local_failure_reporter import report_local_failure, retry_pending_local_failures

    error = LifecycleError("omlx_unreachable", "safe failure")
    path = str(tmp_path / "outbox.json")
    assert not report_local_failure(error, path=path, now=1000, issue_writer=lambda *_: False)
    calls = []
    assert retry_pending_local_failures(
        path=path, now=5000,
        issue_writer=lambda fingerprint, err, version: calls.append((fingerprint, err, version)) or True,
    ) == 1
    assert len(calls) == 1
    assert retry_pending_local_failures(path=path, now=9000, issue_writer=lambda *_: True) == 0


def test_local_failure_reporter_scrubs_openai_key_from_gh(monkeypatch):
    from synlynk import local_failure_reporter

    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    seen = []

    class Result:
        returncode = 0
        stdout = "[]"
        stderr = ""

    def run(args, **kwargs):
        seen.append((args, kwargs))
        return Result()

    monkeypatch.setattr(local_failure_reporter.subprocess, "run", run)
    error = LifecycleError("omlx_unreachable", "safe failure")
    assert local_failure_reporter._write_issue("f" * 64, error, "0.5.3")
    assert seen
    assert all("OPENAI_API_KEY" not in item[1]["env"] for item in seen)
    assert all("sk-secret" not in repr(item) for item in seen)
