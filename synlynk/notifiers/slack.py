"""Minimal one-way Slack Incoming Webhook notifier - the reference BYOUX
consumer for uxcore.subscribe(). No bot token, no slash commands, no
interactive buttons, no per-channel routing, no OAuth: a webhook URL is the
only credential. Exists to force subscribe()'s event payloads to be genuinely
externally serializable before any other external consumer depends on the
contract."""
import json
import urllib.request

from synlynk import uxcore

NOTIFY_EVENT_TYPES = ["dispatch_complete", "pr_approved", "job_failed"]


def format_message(event: uxcore.Event) -> str:
    message = f"[{event.action}] {json.dumps(event.params)} -> {json.dumps(event.result)}"
    if event.action in ("job_completed", "job_failed"):
        job_id = event.result.get("job_id") or event.params.get("job_id")
        if job_id:
            message += f"\n<https://localhost:8420/#job-{job_id}|View live in Vizor> · "
    return message


def post_to_webhook(webhook_url: str, event: uxcore.Event) -> None:
    body = json.dumps({"text": format_message(event)}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url, data=body, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(request, timeout=5)


def run_once(webhook_url: str) -> None:
    for event in uxcore.subscribe(event_types=NOTIFY_EVENT_TYPES):
        post_to_webhook(webhook_url, event)


def main(webhook_url: str) -> None:
    run_once(webhook_url)
