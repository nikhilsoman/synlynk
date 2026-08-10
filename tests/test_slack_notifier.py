from synlynk import uxcore
from synlynk.notifiers import slack
from synlynk.notifiers.slack import format_message


def test_format_message_includes_vizor_link_for_kill_job():
    event = uxcore.Event(
        actor_id="local",
        action="kill_job",
        params={"job_id": "job-42"},
        timestamp="2026-08-08T00:00:00Z",
        result={"job_id": "job-42"},
    )

    message = format_message(event)

    assert "View live in Vizor" in message


def test_format_message_omits_link_on_unsubscribed_action():
    event = uxcore.Event(
        actor_id="local",
        action="note_saved",
        params={"job_id": "job-42"},
        timestamp="2026-08-08T00:00:00Z",
        result={},
    )

    message = format_message(event)

    assert "View live in Vizor" not in message


def test_format_message_uses_configured_vizor_port(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".synlynk"
    config_dir.mkdir()
    (config_dir / "config.json").write_text('{"vizor": {"port": 9001}}')
    event = uxcore.Event("local", "dispatch", {"job_id": "job-42"}, "t", {})

    assert "https://localhost:9001/#job-job-42" in format_message(event)


def test_format_message_uses_default_vizor_port_without_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    event = uxcore.Event("local", "dispatch", {"job_id": "job-42"}, "t", {})

    assert f"https://localhost:{slack.DEFAULT_PORT}/#job-job-42" in format_message(event)
