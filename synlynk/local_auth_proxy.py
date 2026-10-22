"""Per-job loopback TCP broker for authenticated, allowlisted oMLX inference."""

from __future__ import annotations

import http.client
import json
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from synlynk.local_lifecycle import LIFECYCLE_MODEL_ID


MAX_REQUEST_BYTES = 32 * 1024 * 1024
MAX_MODEL_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_CHAT_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_UPSTREAM_RESPONSE_SECONDS = 300
UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 8000
INERT_AIDER_API_KEY = "synlynk-local-relay-only"
_HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "authorization",
}


class LocalAuthBroker:
    """Expose only model metadata and chat completions on host loopback."""

    def __init__(self, credential: str, *, host: str = "127.0.0.1", port: int = 0,
                 connection_factory=None, max_request_bytes: int = MAX_REQUEST_BYTES,
                 max_response_bytes: int = MAX_CHAT_RESPONSE_BYTES,
                 response_timeout_seconds: int = MAX_UPSTREAM_RESPONSE_SECONDS):
        if host != "127.0.0.1":
            raise ValueError("Local auth broker must bind to 127.0.0.1")
        self.host = host
        self.port = port
        self.address = None
        self.credential = credential
        self.connection_factory = connection_factory or (
            lambda host, port, timeout: http.client.HTTPConnection(host, port, timeout=timeout)
        )
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.response_timeout_seconds = response_timeout_seconds
        self._server = None
        self._thread = None
        self._owns_socket = False

    @classmethod
    def from_settings(cls, credential_store=None, **kwargs):
        from synlynk.local_credentials import LocalCredentialStore

        store = credential_store or LocalCredentialStore()
        return cls(store.get(), **kwargs)

    @classmethod
    def from_keychain(cls, credential_store=None, **kwargs):
        """Compatibility alias; lifecycle credentials now come from oMLX settings."""
        return cls.from_settings(credential_store, **kwargs)

    def start(self) -> int:
        if not self.credential:
            raise RuntimeError("Local oMLX credential is unavailable")
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, _format, *_args):
                return

            def do_GET(self):
                owner._handle(self)

            def do_POST(self):
                owner._handle(self)

            def _error(self, code: int, label: str):
                body = json.dumps({"error": label}, separators=(",", ":")).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = Server((self.host, self.port), Handler)
        self.address = self._server.server_address
        self.port = self.address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlsplit(handler.path)
        allowed = (
            (handler.command == "GET" and parsed.path == "/v1/models")
            or (handler.command == "POST" and parsed.path == "/v1/chat/completions")
        )
        if not allowed or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            handler._error(403, "Local relay path is not allowed")
            return
        if handler.command == "POST":
            try:
                length = int(handler.headers.get("Content-Length", "-1"))
            except (TypeError, ValueError):
                handler._error(400, "Invalid request length")
                return
            if length < 0:
                handler._error(411, "Request length is required")
                return
            if length > self.max_request_bytes:
                handler._error(413, "Payload Too Large")
                return
            body = handler.rfile.read(length)
            if len(body) != length:
                handler._error(400, "Incomplete request body")
                return
            try:
                payload = json.loads(body)
                model = payload.get("model")
                if model not in {LIFECYCLE_MODEL_ID, f"openai/{LIFECYCLE_MODEL_ID}"}:
                    handler._error(403, "Model is not allowed")
                    return
                payload["model"] = LIFECYCLE_MODEL_ID
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                handler._error(400, "Invalid chat request")
                return
        else:
            body = None

        connection = None
        try:
            connection = self.connection_factory(UPSTREAM_HOST, UPSTREAM_PORT, timeout=120)
            headers = {
                "Authorization": "Bearer " + self.credential,
                "Accept": handler.headers.get("Accept", "application/json"),
                "Connection": "close",
            }
            for name in ("Content-Type", "User-Agent"):
                value = handler.headers.get(name)
                if value:
                    headers[name] = value
            if body is not None:
                headers["Content-Length"] = str(len(body))
            connection.request(handler.command, parsed.path, body=body, headers=headers)
            response = connection.getresponse()
            if parsed.path == "/v1/models" and response.status == 200:
                output = response.read(MAX_MODEL_RESPONSE_BYTES + 1)
                if len(output) > MAX_MODEL_RESPONSE_BYTES:
                    handler._error(502, "Local model inventory response exceeded limit")
                    return
                output = self._filtered_model_inventory(output)
                handler.send_response(response.status, response.reason)
                self._copy_response_headers(handler, response, length=len(output))
                handler.end_headers()
                handler.wfile.write(output)
                handler.close_connection = True
                return

            try:
                content_length_header = response.getheader("Content-Length")
                content_length = (
                    int(content_length_header) if content_length_header is not None else None
                )
            except (TypeError, ValueError):
                handler._error(502, "Local relay upstream response was invalid")
                return
            if content_length is not None and content_length > self.max_response_bytes:
                handler._error(502, "Local relay response exceeded limit")
                return

            handler.send_response(response.status, response.reason)
            self._copy_response_headers(handler, response)
            handler.end_headers()
            chunked = response.getheader("Content-Length") is None
            bytes_sent = 0
            deadline = time.monotonic() + self.response_timeout_seconds
            while True:
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    handler.close_connection = True
                    return
                upstream_socket = getattr(connection, "sock", None)
                if upstream_socket is not None:
                    upstream_socket.settimeout(min(120, remaining_time))
                remaining_bytes = self.max_response_bytes - bytes_sent
                chunk = response.read(min(64 * 1024, remaining_bytes + 1))
                if not chunk:
                    break
                if len(chunk) > remaining_bytes:
                    handler.close_connection = True
                    return
                bytes_sent += len(chunk)
                if chunked:
                    handler.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                    handler.wfile.write(chunk + b"\r\n")
                else:
                    handler.wfile.write(chunk)
            if chunked:
                handler.wfile.write(b"0\r\n\r\n")
                handler.wfile.write(chunk)
            handler.close_connection = True
        except Exception:
            try:
                handler._error(502, "Local relay upstream failed")
            except Exception:
                pass
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    @staticmethod
    def _filtered_model_inventory(raw: bytes) -> bytes:
        try:
            payload = json.loads(raw)
            entries = payload.get("data")
            if not isinstance(entries, list):
                raise ValueError
            payload["data"] = [
                item for item in entries
                if isinstance(item, dict) and item.get("id") == LIFECYCLE_MODEL_ID
            ]
            return json.dumps(payload, separators=(",", ":")).encode("utf-8")
        except Exception:
            raise ValueError("malformed oMLX inventory") from None

    @staticmethod
    def _copy_response_headers(handler, response, *, length=None):
        content_length = length
        if content_length is None:
            try:
                value = response.getheader("Content-Length")
                content_length = int(value) if value is not None else None
            except (TypeError, ValueError):
                content_length = None
        for name, value in response.getheaders():
            if name.lower() in _HOP_BY_HOP_HEADERS or name.lower() == "content-length":
                continue
            handler.send_header(name, value)
        if content_length is not None:
            handler.send_header("Content-Length", str(content_length))
        else:
            handler.send_header("Transfer-Encoding", "chunked")
        handler.send_header("Connection", "close")

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self.address = None
        self.credential = ""


def ensure_inert_aider_key(args: list[str]) -> list[str]:
    """Supply Aider's required OpenAI client value without exposing the key."""
    result = []
    index = 0
    while index < len(args):
        item = args[index]
        if item == "--openai-api-key":
            value = args[index + 1] if index + 1 < len(args) else ""
            if value != INERT_AIDER_API_KEY:
                raise ValueError("Local pilot does not accept caller-supplied API credentials")
            index += 2
            continue
        if item.startswith("--openai-api-key="):
            if item.split("=", 1)[1] != INERT_AIDER_API_KEY:
                raise ValueError("Local pilot does not accept caller-supplied API credentials")
            index += 1
            continue
        if item == "--api-key" or item.startswith("--api-key="):
            raise ValueError("Local pilot does not accept caller-supplied API credentials")
        result.append(item)
        index += 1
    result.extend(["--openai-api-key", INERT_AIDER_API_KEY])
    return result
