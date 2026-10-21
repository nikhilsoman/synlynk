from synlynk.daemon import SynlynkDaemon


def test_daemon_local_lifecycle_tick_calls_host_supervisor():
    calls = []

    class Manager:
        def tick(self):
            calls.append("tick")

    daemon = object.__new__(SynlynkDaemon)
    daemon.local_lifecycle_manager = Manager()
    daemon._local_lifecycle_tick()
    assert calls == ["tick"]
