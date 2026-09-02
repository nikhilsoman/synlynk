"""Local cross-harness event relay.

The relay deliberately uses only the Python standard library: it is small enough
to run beside a worker and durable enough to recover events from SQLite.
"""

from __future__ import annotations

import json
import queue
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from synlynk.events import ActorIdentifier, EventEnvelope


def _db():
    from synlynk import _get_db
    return _get_db()


def _recipient_key(actor: ActorIdentifier | dict | str) -> str:
    if isinstance(actor, str):
        return actor
    if isinstance(actor, dict):
        actor = ActorIdentifier.from_dict(actor)
    return ":".join((actor.workspace_id, actor.member_id, actor.agent_role, actor.harness, actor.job_id))


class RelayBroker:
    """Thread-safe publisher and JSON-RPC method dispatcher."""

    def __init__(self):
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.RLock()

    def subscribe(self) -> queue.Queue:
        subscriber = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber):
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, envelope: EventEnvelope) -> int:
        data = envelope.to_json()
        conn = _db()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO relay_events "
                "(event_id,event_type,timestamp,sender_json,recipient_json,payload_json,envelope_json) "
                "VALUES (?,?,?,?,?,?,?)",
                (envelope.event_id, envelope.event_type, envelope.timestamp,
                 json.dumps(envelope.sender.to_dict()),
                 json.dumps(envelope.recipient.to_dict()) if envelope.recipient else None,
                 json.dumps(envelope.payload), data),
            )
            if envelope.recipient:
                conn.execute(
                    "INSERT OR IGNORE INTO relay_mailbox(event_id,recipient_key,envelope_json) VALUES (?,?,?)",
                    (envelope.event_id, _recipient_key(envelope.recipient), data),
                )
            conn.commit()
        finally:
            conn.close()
        delivered = 0
        with self._lock:
            for subscriber in list(self._subscribers):
                try:
                    subscriber.put_nowait(data)
                    delivered += 1
                except queue.Full:
                    self._subscribers.discard(subscriber)
        return delivered

    def rpc(self, method: str, params: dict) -> dict:
        sender_data = params.get("sender") or params.get("actor")
        if not sender_data:
            sender_data = {"workspace_id": params.get("workspace_id", "local"),
                           "member_id": params.get("member_id", "local"),
                           "agent_role": params.get("agent_role", "unknown"),
                           "harness": params.get("harness", "cli"),
                           "job_id": params.get("job_id", "local")}
        sender = sender_data if isinstance(sender_data, ActorIdentifier) else ActorIdentifier.from_dict(sender_data)
        recipient_data = params.get("recipient") or params.get("target_agent_id")
        if isinstance(recipient_data, str):
            recipient_data = {**sender.to_dict(), "agent_role": recipient_data, "job_id": params.get("target_job_id", "")}
        recipient = ActorIdentifier.from_dict(recipient_data) if recipient_data else None
        if method in ("relay.send_message", "send_message"):
            event_type, payload = "task_progress", {"message": params.get("message", ""), **(params.get("payload") or {})}
        elif method in ("relay.inject_steering", "inject_steering"):
            event_type, payload = "steering_injected", {"job_id": params.get("job_id"), "prompt_delta": params.get("prompt_delta", "")}
        elif method in ("relay.request_review", "request_review"):
            event_type, payload = "review_requested", {"pr_url": params.get("pr_url"), "diff_summary": params.get("diff_summary", "")}
        elif method in ("relay.broadcast", "broadcast"):
            event_type, payload, recipient = "task_progress", params.get("payload") or {"topic": params.get("topic"), "message": params.get("message", "")}, None
        else:
            raise ValueError(f"method not found: {method}")
        envelope = EventEnvelope.create(sender, event_type, payload, recipient)
        return {"event_id": envelope.event_id, "subscribers": self.publish(envelope), "event": envelope.to_dict()}


class RelayHandler(BaseHTTPRequestHandler):
    broker: RelayBroker = None

    def log_message(self, *_args):
        return

    def _json(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path != "/events":
            self._json(404, {"error": "not found"})
            return
        subscriber = self.broker.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                try:
                    value = subscriber.get(timeout=20)
                    self.wfile.write(f"event: relay\\ndata: {value}\\n\\n".encode())
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.broker.unsubscribe(subscriber)

    def do_POST(self):
        if urlparse(self.path).path != "/rpc":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
            result = self.broker.rpc(request.get("method", ""), request.get("params") or {})
            self._json(200, {"jsonrpc": "2.0", "id": request.get("id"), "result": result})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": str(exc)}})


class RelayServer:
    def __init__(self, host="127.0.0.1", port=7432, broker=None):
        self.broker = broker or RelayBroker()
        handler = type("BoundRelayHandler", (RelayHandler,), {"broker": self.broker})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.thread = None

    @property
    def address(self):
        return self.httpd.server_address

    def start(self, background=True):
        if background:
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
        else:
            self.httpd.serve_forever()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


ThreadingRelayServer = RelayServer


def _relay_child_main():
    RelayServer(port=7432).start(background=False)


def iter_sse_events(response):
    """Yield decoded JSON payloads from an SSE response."""
    for raw_line in response:
        line = raw_line.decode(errors="replace").strip()
        if line.startswith("data: "):
            yield json.loads(line[6:])


def relay_url(args=None):
    return getattr(args, "relay_url", None) or "http://127.0.0.1:7432"


def cmd_relay_status(args):
    try:
        with urllib.request.urlopen(relay_url(args) + "/events", timeout=1) as response:
            print(f"relay running ({response.status}) at {relay_url(args)}")
    except Exception:
        print(f"relay stopped at {relay_url(args)}")


def cmd_relay_send(args):
    params = {"message": args.message, "target_agent_id": args.to_agent}
    request = urllib.request.Request(
        relay_url(args) + "/rpc",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "relay.send_message", "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.loads(response.read())
    if "error" in result:
        raise RuntimeError(result["error"].get("message", "relay RPC failed"))
    print(result["result"]["event_id"])


def cmd_relay_tail(args):
    with urllib.request.urlopen(relay_url(args) + "/events", timeout=None) as response:
        for raw_line in response:
            line = raw_line.decode(errors="replace").rstrip()
            if line.startswith("data: "):
                print(line[6:], flush=True)
