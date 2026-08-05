import io
import json
import os
import threading
import time as real_time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import synlynk.viz
from synlynk.viz import VizorHandler


class _DummyVizorHandler(VizorHandler):
    def send_error(self, code, message=None):
        self.errors.append((code, message))

    def send_response(self, code):
        self.responses.append(code)

    def send_header(self, key, value):
        self.headers_sent.append((key, value))

    def end_headers(self):
        self.ended_headers = True

    def log_message(self, format, *args):
        pass


def _make_handler(payload: bytes):
    handler = object.__new__(_DummyVizorHandler)
    handler.path = "/note"
    handler.rfile = io.BytesIO(payload)
    handler.wfile = io.BytesIO()
    handler.headers = {"Content-Length": str(len(payload))}
    handler.errors = []
    handler.responses = []
    handler.headers_sent = []
    handler.ended_headers = False
    return handler


def test_post_note_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/viz-cache", exist_ok=True)

    handler = _make_handler(
        json.dumps({"id": "story-bs21", "text": "needs work", "tags": ["redo"], "state": "action"}).encode()
    )
    VizorHandler.do_POST(handler)

    assert handler.responses == [200]
    assert handler.ended_headers is True
    assert json.loads(handler.wfile.getvalue()) == {"ok": True}
    assert os.path.exists(".synlynk/viz-notes.json")
    with open(".synlynk/viz-notes.json") as f:
        notes = json.load(f)
    assert "story-bs21" in notes
    assert notes["story-bs21"]["text"] == "needs work"
    assert notes["story-bs21"]["state"] == "action"


def test_post_note_merges_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/viz-cache", exist_ok=True)
    existing = {"other-id": {"text": "existing", "tags": [], "state": "info", "updated_at": "2026-07-01T00:00:00Z"}}
    with open(".synlynk/viz-notes.json", "w") as f:
        json.dump(existing, f)

    handler = _make_handler(json.dumps({"id": "new-id", "text": "new note", "tags": [], "state": "info"}).encode())
    VizorHandler.do_POST(handler)

    with open(".synlynk/viz-notes.json") as f:
        notes = json.load(f)
    assert "other-id" in notes  # existing note preserved
    assert "new-id" in notes    # new note added


def test_post_invalid_json_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/viz-cache", exist_ok=True)

    handler = _make_handler(b"not-json")
    VizorHandler.do_POST(handler)

    assert handler.errors == [(400, "Invalid JSON")]


def test_cmd_viz_serve_keeps_server_alive_and_shuts_down_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stop_signal = threading.Event()
    captured = {}
    errors = []

    class _FakeHTTPServer:
        def __init__(self, address, handler_class):
            self.server_address = address
            self.handler_class = handler_class
            self.shutdown_called = False
            self.server_close_called = False
            self.started = threading.Event()
            self.release = threading.Event()
            captured["server"] = self

        def serve_forever(self):
            self.started.set()
            self.release.wait()

        def shutdown(self):
            self.shutdown_called = True
            self.release.set()

        def server_close(self):
            self.server_close_called = True

    def fake_generate_viz_data():
        return {
            "workspace": {"name": "test", "updated_at": "2026-07-21T00:00:00Z", "repos": []},
            "goals": [],
            "dreams": [],
            "costs": {"total_usd": 0.0, "total_usd_estimated": 0.0, "by_agent": {}, "by_stage": {}},
            "agents": {},
            "workspace_map": {"edges": [], "edge_types": {}},
            "file_tree": {"name": ".", "dirs": {}, "files": []},
            "notes": {},
            "ecosystem": {},
            "observatory": {},
            "telemetry": {"recent": [], "sentinel_alerts": []},
            "journeys": [],
        }

    def fake_ftue_prompts(config):
        return config

    def fake_sleep(_seconds):
        if stop_signal.wait(0.05):
            raise KeyboardInterrupt

    monkeypatch.setattr(synlynk.viz, "generate_viz_data", fake_generate_viz_data)
    monkeypatch.setattr(synlynk.viz, "_ftue_prompts", fake_ftue_prompts)
    monkeypatch.setattr(synlynk.viz.http.server, "HTTPServer", _FakeHTTPServer)
    monkeypatch.setattr(synlynk.viz.time, "sleep", fake_sleep)

    args = SimpleNamespace(stop=False, open=False, generate=False, serve=True, port=8721)

    def run_cmd():
        try:
            synlynk.viz.cmd_viz(args)
        except BaseException as exc:  # pragma: no cover - captured for failure reporting
            errors.append(exc)

    thread = threading.Thread(target=run_cmd)
    thread.start()

    try:
        for _ in range(100):
            if "server" in captured and captured["server"].started.is_set():
                break
            real_time.sleep(0.05)
        assert "server" in captured
        assert captured["server"].started.is_set()
        assert thread.is_alive()
    finally:
        stop_signal.set()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert captured["server"].shutdown_called
    assert captured["server"].server_close_called
    assert not errors


def test_handle_dispatch_routes_through_uxcore():
    from synlynk.viz import VizorHandler

    handler = VizorHandler.__new__(VizorHandler)
    with patch("synlynk.uxcore.dispatch") as mock_dispatch:
        mock_dispatch.return_value = MagicMock(ok=True, message="", job_id="job-1")
        result = handler._handle_dispatch({"agent": "codex", "task": "fix bug"})
    mock_dispatch.assert_called_once_with(agent="codex", task="fix bug")
    assert result["ok"] is True
    assert result["job_id"] == "job-1"


def test_handle_approve_routes_through_uxcore():
    from synlynk.viz import VizorHandler

    handler = VizorHandler.__new__(VizorHandler)
    with patch("synlynk.uxcore.approve_pr") as mock_approve:
        mock_approve.return_value = MagicMock(ok=True, message="merged", job_id=None)
        result = handler._handle_approve({"pr_number": 715})
    mock_approve.assert_called_once_with(pr_number=715)
    assert result["ok"] is True


def test_handle_kill_routes_through_uxcore():
    from synlynk.viz import VizorHandler

    handler = VizorHandler.__new__(VizorHandler)
    with patch("synlynk.uxcore.kill_job") as mock_kill:
        mock_kill.return_value = MagicMock(ok=True, message="killed", job_id="job-1")
        result = handler._handle_kill({"job_id": "job-1"})
    mock_kill.assert_called_once_with(job_id="job-1")
    assert result["ok"] is True
