import json

from synlynk.viz.gantt import generate_gantt_html
from synlynk.viz.server import save_viz_note


def test_save_viz_note_roundtrip(tmp_path):
    path = tmp_path / "viz-notes.json"
    save_viz_note(path, {"id": "rel-1", "text": "hi", "tags": [], "state": "info"})
    data = json.loads(path.read_text())
    assert data["rel-1"]["text"] == "hi"
    assert data["rel-1"]["state"] == "info"


def test_save_viz_note_requires_id(tmp_path):
    path = tmp_path / "viz-notes.json"
    try:
        save_viz_note(path, {"text": "nope"})
    except ValueError as exc:
        assert "id" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_gantt_js_posts_relative_api_note():
    html = generate_gantt_html(
        {
            "workspace": {"name": "synlynk"},
            "releases": [],
            "dreams": [],
            "goals": [],
            "spec_verifications": [],
            "product_id": "synlynk",
            "notes": {},
        },
        33333,
    )
    assert "fetch('/note'" not in html
    assert "fetch('api/note'" in html
