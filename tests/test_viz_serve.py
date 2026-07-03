import io
import json
import os

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
