import json

from synlynk.notifiers.slack import NOTIFY_EVENT_TYPES, _slack_webhook_url


def test_maintainer_promote_is_a_notify_event_type():
    assert "maintainer_promote" in NOTIFY_EVENT_TYPES


def test_slack_webhook_url_reads_from_config(tmp_path):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({
        "notifiers": {"slack_webhook_url": "https://hooks.slack.test/abc"}
    }))
    assert _slack_webhook_url(repo_root=str(tmp_path)) == "https://hooks.slack.test/abc"


def test_slack_webhook_url_returns_none_when_unconfigured(tmp_path):
    assert _slack_webhook_url(repo_root=str(tmp_path)) is None
