from synlynk.dispatch_pipeline import spawn
from synlynk.harness_adapters.request import DispatchRequest


def test_spawn_stage_calls_adapter_build_cmd(monkeypatch):
    calls = []

    class FakeAdapter:
        def build_cmd(self, request):
            calls.append(request.agent)
            return ["echo", "hi"]

    def fake_popen(cmd, **kwargs):
        class FakeProc:
            def communicate(self, timeout=None):
                return (b"hi\n", None)

            returncode = 0

        return FakeProc()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    req = DispatchRequest(agent="codex", task="do a thing")
    result = spawn(req, FakeAdapter(), env={}, cwd=".")
    assert calls == ["codex"]
    assert result["exit_code"] == 0
    assert "hi" in result["raw_output"]
