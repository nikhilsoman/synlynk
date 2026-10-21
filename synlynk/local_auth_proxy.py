"""Per-job Unix-socket broker for authenticated, allowlisted oMLX inference."""

from __future__ import annotations

import http.client
import json
import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from synlynk.local_lifecycle import LIFECYCLE_MODEL_ID


MAX_REQUEST_BYTES = 32 * 1024 * 1024
MAX_MODEL_RESPONSE_BYTES = 4 * 1024 * 1024
UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 8000
INERT_AIDER_API_KEY = "synlynk-local-relay-only"
_HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "authorization",
}


class LocalAuthBroker:
    """Expose only model metadata and chat completions through a private UDS."""

    def __init__(self, socket_path: str, credential: str, *,
                 connection_factory=None, max_request_bytes: int = MAX_REQUEST_BYTES):
        self.socket_path = os.path.abspath(socket_path)
        self.credential = credential
        self.connection_factory = connection_factory or (
            lambda host, port, timeout: http.client.HTTPConnection(host, port, timeout=timeout)
        )
        self.max_request_bytes = max_request_bytes
        self._server = None
        self._thread = None
        self._owns_socket = False

    @classmethod
    def from_keychain(cls, socket_path: str, credential_store=None, **kwargs):
        from synlynk.local_credentials import LocalCredentialStore

        store = credential_store or LocalCredentialStore()
        return cls(socket_path, store.get(), **kwargs)

    def start(self) -> None:
        if not self.credential:
            raise RuntimeError("Local oMLX credential is unavailable")
        if len(os.fsencode(self.socket_path)) >= 100:
            raise RuntimeError("Local relay socket path is too long")
        os.makedirs(os.path.dirname(self.socket_path), mode=0o700, exist_ok=True)
        if os.path.exists(self.socket_path):
            raise RuntimeError("Local relay socket path is already in use")
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

        class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = Server(self.socket_path, Handler)
        self._owns_socket = True
        os.chmod(self.socket_path, 0o600)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

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

            handler.send_response(response.status, response.reason)
            self._copy_response_headers(handler, response)
            handler.end_headers()
            chunked = response.getheader("Content-Length") is None
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
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
        if self._owns_socket:
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
            self._owns_socket = False
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
