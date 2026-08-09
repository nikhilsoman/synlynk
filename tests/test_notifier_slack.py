from unittest.mock import patch

from synlynk import uxcore
from synlynk.notifiers import slack


def test_format_message_for_dispatch():
    event = uxcore.Event(
        actor_id="local", action="dispatch",
        params={"agent": "codex", "task": "fix bug"},
        timestamp="2026-08-05T00:00:00Z",
        result={"ok": True, "job_id": "job-1"},
    )
    text = slack.format_message(event)
    assert "dispatch" in text
    assert "codex" in text


def test_post_to_webhook_sends_payload():
    event = uxcore.Event(
        actor_id="local", action="approve_pr", params={"pr_number": 715},
        timestamp="t1", result={"ok": True},
    )
    with patch("urllib.request.urlopen") as mock_urlopen:
        slack.post_to_webhook("https://hooks.slack.com/services/FAKE", event)
    mock_urlopen.assert_called_once()
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://hooks.slack.com/services/FAKE"


def test_run_once_posts_matching_events_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import json
    import os

    os.makedirs(".synlynk")
    with open(".synlynk/events.jsonl", "w") as f:
        f.write(json.dumps({
            "actor_id": "local", "action": "dispatch", "params": {},
            "timestamp": "t1", "result": {"ok": True},
        }) + "\n")
        f.write(json.dumps({
            "actor_id": "local", "action": "note_saved", "params": {},
            "timestamp": "t2", "result": {"ok": True},
        }) + "\n")
    with patch("synlynk.notifiers.slack.post_to_webhook") as mock_post:
        slack.run_once("https://hooks.slack.com/services/FAKE")
    assert mock_post.call_count == 1
