import json
import os
import socket
import threading
import shutil
import tempfile

import pytest

from synlynk.local_auth_proxy import LocalAuthBroker, ensure_inert_aider_key


@pytest.fixture
def short_socket_dir():
    directory = tempfile.mkdtemp(prefix="synlynk-relay-", dir="/private/tmp")
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


class FakeResponse:
    status = 200
    reason = "OK"
    headers = [("Content-Type", "application/json")]

    def __init__(self, body):
        self.body = body
        self.sent = 0

    def getheader(self, name, default=None):
        if name.lower() == "content-length":
            return str(len(self.body))
        return default

    def getheaders(self):
        return self.headers + [("Content-Length", str(len(self.body)))]

    def read(self, size=-1):
        if self.sent:
            return b""
        self.sent = 1
        return self.body


class FakeConnection:
    def __init__(self, host, port, timeout, *, result=None, error=None, capture=None):
        self.capture = capture
        self.result = result or FakeResponse(b'{"data":[]}')
        self.error = error

    def request(self, method, path, body=None, headers=None):
        if self.capture is not None:
            self.capture.update(method=method, path=path, body=body, headers=headers)
        if self.error:
            raise self.error

    def getresponse(self):
        return self.result

    def close(self):
        pass


def send_unix_request(path, request):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(path)
    client.sendall(request)
    chunks = []
    while True:
        chunk = client.recv(8192)
        if not chunk:
            break
        chunks.append(chunk)
    client.close()
    return b"".join(chunks)


def test_broker_injects_key_to_fixed_upstream_and_filters_model_inventory(short_socket_dir):
    capture = {}
    body = json.dumps({"data": [
        {"id": "Ornith-1.0-9B-4bit"},
        {"id": "Qwen2.5-Coder-14B-Instruct-4bit"},
    ]}).encode()
    broker = LocalAuthBroker(
        os.path.join(short_socket_dir, "relay.sock"), "host-secret",
        connection_factory=lambda host, port, timeout: FakeConnection(
            host, port, timeout, result=FakeResponse(body), capture=capture),
    )
    broker.start()
    try:
        response = send_unix_request(
            broker.socket_path,
            b"GET /v1/models HTTP/1.1\r\nHost: relay\r\nAuthorization: Bearer inert-placeholder\r\nConnection: close\r\n\r\n",
        )
    finally:
        broker.close()
    assert capture["method"] == "GET"
    assert capture["path"] == "/v1/models"
    assert capture["headers"]["Authorization"] == "Bearer host-secret"
    assert "inert-placeholder" not in str(capture["headers"])
    assert b"Ornith-1.0-9B-4bit" in response
    assert b"Qwen2.5" not in response


def test_broker_allows_only_ornith_chat_completion_and_rewrites_provider_prefix(short_socket_dir):
    capture = {}
    broker = LocalAuthBroker(
        os.path.join(short_socket_dir, "relay.sock"), "host-secret",
        connection_factory=lambda host, port, timeout: FakeConnection(
            host, port, timeout, capture=capture),
    )
    broker.start()
    try:
        payload = json.dumps({"model": "openai/Ornith-1.0-9B-4bit", "messages": []}).encode()
        response = send_unix_request(
            broker.socket_path,
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: relay\r\nAuthorization: Bearer inert-placeholder\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(payload)).encode() + b"\r\nConnection: close\r\n\r\n" + payload,
        )
    finally:
        broker.close()
    assert b"200 OK" in response
    assert json.loads(capture["body"])["model"] == "Ornith-1.0-9B-4bit"


@pytest.mark.parametrize("path", [
    "/v1/models/Ornith-1.0-9B-4bit/load",
    "/admin/settings",
    "http://example.com/v1/chat/completions",
    "/v1/chat/completions?url=http://example.com",
])
def test_broker_denies_management_arbitrary_and_ambiguous_paths(short_socket_dir, path):
    calls = []
    broker = LocalAuthBroker(
        os.path.join(short_socket_dir, "relay.sock"), "host-secret",
        connection_factory=lambda *args: calls.append(args),
    )
    broker.start()
    try:
        request = f"GET {path} HTTP/1.1\r\nHost: relay\r\nConnection: close\r\n\r\n".encode()
        response = send_unix_request(broker.socket_path, request)
    finally:
        broker.close()
    assert b"403 Forbidden" in response
    assert calls == []


def test_broker_bounds_request_body_and_rejects_unapproved_model(short_socket_dir):
    calls = []
    broker = LocalAuthBroker(
        os.path.join(short_socket_dir, "relay.sock"), "host-secret", max_request_bytes=32,
        connection_factory=lambda *args: calls.append(args),
    )
    broker.start()
    try:
        payload = b"x" * 33
        response = send_unix_request(
            broker.socket_path,
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: relay\r\nContent-Length: 33\r\nConnection: close\r\n\r\n" + payload,
        )
    finally:
        broker.close()
    assert b" 413 " in response
    assert calls == []

    broker = LocalAuthBroker(os.path.join(short_socket_dir, "r2.sock"), "host-secret",
                             connection_factory=lambda *args: calls.append(args))
    broker.start()
    try:
        payload = b'{"model":"openai/Qwen2.5-Coder-14B-Instruct-4bit"}'
        response = send_unix_request(
            broker.socket_path,
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: relay\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(payload)).encode() + b"\r\nConnection: close\r\n\r\n" + payload,
        )
    finally:
        broker.close()
    assert b"403 Forbidden" in response
    assert calls == []


def test_broker_sanitizes_upstream_errors_and_removes_socket_on_close(short_socket_dir):
    broker = LocalAuthBroker(
        os.path.join(short_socket_dir, "relay.sock"), "host-secret",
        connection_factory=lambda *args: FakeConnection(*args, error=RuntimeError("host-secret")),
    )
    broker.start()
    socket_path = broker.socket_path
    response = send_unix_request(
        socket_path,
        b"GET /v1/models HTTP/1.1\r\nHost: relay\r\nConnection: close\r\n\r\n",
    )
    broker.close()
    assert b"502 Bad Gateway" in response
    assert b"host-secret" not in response
    assert not os.path.exists(socket_path)
    assert broker.credential == ""


def test_aider_gets_only_an_inert_local_placeholder():
    assert ensure_inert_aider_key(["--model", "openai/ornith"]) == [
        "--model", "openai/ornith", "--openai-api-key", "synlynk-local-relay-only"
    ]
    with pytest.raises(ValueError, match="API credentials"):
        ensure_inert_aider_key(["--openai-api-key", "real-secret"])
