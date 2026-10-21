from synlynk.daemon import SynlynkDaemon


def test_daemon_local_lifecycle_tick_calls_host_supervisor_and_retries_outbox(monkeypatch):
    calls = []

    class Manager:
        def tick(self):
            calls.append("tick")

    daemon = object.__new__(SynlynkDaemon)
    daemon.local_lifecycle_manager = Manager()
    monkeypatch.setattr("synlynk.local_failure_reporter.retry_pending_local_failures",
                        lambda: calls.append("retry"))
    daemon._local_lifecycle_tick()
    assert calls == ["tick", "retry"]
