from synlynk import uxcore
from synlynk.notifiers.slack import format_message


def test_format_message_includes_vizor_link_on_job_completed():
    event = uxcore.Event(
        actor_id="local",
        action="job_completed",
        params={},
        timestamp="2026-08-08T00:00:00Z",
        result={"job_id": "job-42"},
    )

    message = format_message(event)

    assert "View live in Vizor" in message


def test_format_message_omits_link_on_job_started():
    event = uxcore.Event(
        actor_id="local",
        action="job_started",
        params={"job_id": "job-42"},
        timestamp="2026-08-08T00:00:00Z",
        result={},
    )

    message = format_message(event)

    assert "View live in Vizor" not in message
