"""Minimal one-way Slack Incoming Webhook notifier - the reference BYOUX
consumer for uxcore.subscribe(). No bot token, no slash commands, no
interactive buttons, no per-channel routing, no OAuth: a webhook URL is the
only credential. Exists to force subscribe()'s event payloads to be genuinely
externally serializable before any other external consumer depends on the
contract."""
import json
import urllib.request

from synlynk import uxcore
from synlynk.viz import DEFAULT_PORT

NOTIFY_EVENT_TYPES = [
    "dispatch",
    "approve_pr",
    "pr_approve",
    "pr_approved",
    "kill_job",
    "job_kill",
    "job_killed",
]


def _normalize_action(action: str) -> str:
    return (action or "").strip().lower().replace("-", "_")


def _vizor_port() -> int:
    try:
        with open(".synlynk/config.json") as config_file:
            config = json.load(config_file)
        configured = (config.get("vizor") or {}).get("port")
        if configured:
            return int(configured)
    except (AttributeError, OSError, TypeError, ValueError):
        pass

    try:
        from synlynk import vizor_daemon
        live_port = vizor_daemon._read_port()
        if live_port:
            return int(live_port)
    except Exception:
        pass

    return DEFAULT_PORT


def format_message(event: uxcore.Event) -> str:
    message = f"[{event.action}] {json.dumps(event.params)} -> {json.dumps(event.result)}"
    action = _normalize_action(event.action)
    if action in NOTIFY_EVENT_TYPES:
        job_id = event.result.get("job_id") or event.params.get("job_id")
        if job_id:
            message += f"\n<http://localhost:{_vizor_port()}/#job-{job_id}|View live in Vizor>"
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
