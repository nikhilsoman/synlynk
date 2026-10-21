"""Opt-in Docker proof for the Local Pilot's host TCP relay topology."""

import json
import os
import shutil
import subprocess
import uuid

import pytest

from synlynk.local_auth_proxy import LocalAuthBroker


pytestmark = pytest.mark.skipif(
    os.environ.get("SYNLYNK_RUN_LOCAL_PILOT_RELAY_INTEGRATION") != "1",
    reason="set SYNLYNK_RUN_LOCAL_PILOT_RELAY_INTEGRATION=1 to run Docker integration",
)


class FakeResponse:
    status = 200
    reason = "OK"

    def __init__(self, body):
        self.body = body
        self.sent = False

    def getheader(self, name, default=None):
        if name.lower() == "content-length":
            return str(len(self.body))
        return default

    def getheaders(self):
        return [("Content-Type", "application/json"), ("Content-Length", str(len(self.body)))]

    def read(self, size=-1):
        if self.sent:
            return b""
        self.sent = True
        return self.body


class FakeConnection:
    def __init__(self, _host, _port, _timeout, *, capture):
        self.capture = capture

    def request(self, method, path, body=None, headers=None):
        self.capture.append((method, path, body, headers))

    def getresponse(self):
        if self.capture[-1][1] == "/v1/models":
            body = json.dumps({"data": [{"id": "Ornith-1.0-9B-4bit"}]}).encode()
        else:
            body = b'{"id":"fake-completion","choices":[]}'
        return FakeResponse(body)

    def close(self):
        pass


def _docker(argv, *, timeout=20, check=True):
    return subprocess.run(
        ["docker", *argv], capture_output=True, text=True, timeout=timeout, check=check
    )


def test_relay_routes_only_allowlisted_requests_and_aider_network_cannot_bypass_host(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker CLI is unavailable")
    try:
        _docker(["info"], timeout=8)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pytest.skip("Docker daemon is unavailable")

    repo = os.path.dirname(os.path.dirname(__file__))
    project = "pilot-relay-test-" + uuid.uuid4().hex[:10]
    env = dict(os.environ)
    env.update({
        "PILOT_UID": str(os.getuid()),
        "PILOT_GID": str(os.getgid()),
        "PILOT_WORKTREE": str(tmp_path),
    })
    calls = []
    broker = LocalAuthBroker(
        "integration-secret",
        connection_factory=lambda host, port, timeout: FakeConnection(
            host, port, timeout, capture=calls
        ),
    )
    port = broker.start()
    env["PILOT_RELAY_PORT"] = str(port)
    prefix = ["compose", "-f", os.path.join(repo, "docker", "local-pilot.compose.yaml"),
              "--project-name", project]

    def client(*args, check=True):
        return _docker(
            ["run", "--rm", "--network", project + "_local-pilot",
             "--entrypoint", "wget", "synlynk-local-pilot-relay:1", *args],
            timeout=8,
            check=check,
        )

    try:
        up = subprocess.run(
            ["docker", *prefix, "up", "--detach", "--build", "--wait",
             "--wait-timeout", "20", "omlx-relay"],
            env=env, capture_output=True, text=True, timeout=90, check=False,
        )
        assert up.returncode == 0, up.stdout + up.stderr

        models = client("-q", "-O", "-", "http://omlx:8000/v1/models")
        assert "Ornith-1.0-9B-4bit" in models.stdout
        payload = json.dumps({"model": "Ornith-1.0-9B-4bit", "messages": []})
        chat = client("-q", "-O", "-", "--header", "Content-Type: application/json",
                      "--post-data", payload, "http://omlx:8000/v1/chat/completions")
        assert "fake-completion" in chat.stdout
        assert "/v1/models" in [call[1] for call in calls]
        assert "/v1/chat/completions" in [call[1] for call in calls]
        assert all(call[3]["Authorization"] == "Bearer integration-secret" for call in calls)
        chats_before_denial = sum(call[1] == "/v1/chat/completions" for call in calls)

        denied_payload = json.dumps({"model": "not-approved", "messages": []})
        denied = client("-q", "-O", "/dev/null", "--header", "Content-Type: application/json",
                        "--post-data", denied_payload,
                        "http://omlx:8000/v1/chat/completions", check=False)
        assert denied.returncode != 0
        assert sum(call[1] == "/v1/chat/completions" for call in calls) == chats_before_denial

        bypass = client("-T", "2", "-q", "-O", "/dev/null",
                        f"http://host.docker.internal:{port}/v1/models", check=False)
        assert bypass.returncode != 0
        internet = client("-T", "2", "-q", "-O", "/dev/null", "http://1.1.1.1/", check=False)
        assert internet.returncode != 0
    finally:
        subprocess.run(["docker", *prefix, "down", "--remove-orphans"], env=env,
                       capture_output=True, text=True, timeout=30, check=False)
        broker.close()
