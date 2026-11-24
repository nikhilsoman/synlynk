"""Unit tests for Hetzner Cloud Swarm Runner Driver."""

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock
import pytest

from synlynk.runners.base import SwarmRunnerDriver
from synlynk.runners.hetzner import HetznerRunnerDriver, calculate_vertical_host_size
from synlynk.runners.manager import RunnerManager


class MockHTTPResponse:
    def __init__(self, data: dict, status: int = 200):
        self.raw = json.dumps(data).encode("utf-8")
        self.status = status

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_hetzner_driver_implements_interface():
    driver = HetznerRunnerDriver(config={"token": "test-token", "location": "fsn1"})
    assert isinstance(driver, SwarmRunnerDriver)
    assert driver.base_url == "https://api.hetzner.cloud/v1"
    assert driver.token == "test-token"
    assert driver.location == "fsn1"


def test_hetzner_driver_registered_in_manager():
    config = {
        "swarm_runners": {
            "enabled": ["local", "hetzner"],
            "hetzner": {"token": "mock-token", "location": "hel1"},
        }
    }
    manager = RunnerManager(config=config)
    driver = manager.driver("hetzner")
    assert isinstance(driver, HetznerRunnerDriver)
    assert driver.token == "mock-token"
    assert driver.location == "hel1"


def test_calculate_vertical_host_size():
    assert calculate_vertical_host_size(1) == "cpx21"
    assert calculate_vertical_host_size(3) == "cpx21"
    assert calculate_vertical_host_size(4) == "cpx31"
    assert calculate_vertical_host_size(8) == "cpx31"
    assert calculate_vertical_host_size(9) == "cpx51"
    assert calculate_vertical_host_size(24) == "cpx51"
    assert calculate_vertical_host_size(8, prefer_arm=True) == "cax41"


def test_provision_creates_server_and_arms_watchdog():
    captured_requests = []

    def mock_opener(req, timeout=30):
        captured_requests.append(req)
        resp_data = {
            "server": {
                "id": 987654,
                "name": "synlynk-test-node",
                "status": "initializing",
                "server_type": {"name": "cpx31"},
            }
        }
        return MockHTTPResponse(resp_data, 201)

    driver = HetznerRunnerDriver(
        config={"token": "fake-token", "timeout_seconds": 600},
        opener=mock_opener,
    )

    job_spec = {
        "runner_id": "synlynk-test-node",
        "task_count": 6,
        "epic_id": "epic-123",
        "command": ["echo", "running-epic"],
    }

    server_id = driver.provision(job_spec)
    assert server_id == "987654"
    assert "987654" in driver._watchdogs
    assert driver._watchdogs["987654"].is_alive()

    # Verify request payload
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.method == "POST"
    assert req.get_header("Authorization") == "Bearer fake-token"

    payload = json.loads(req.data.decode("utf-8"))
    assert payload["server_type"] == "cpx31"  # 6 tasks auto-sized to cpx31
    assert payload["labels"]["epic_id"] == "epic-123"
    assert "shutdown -h +10" in payload["user_data"]  # 600s = 10min watchdog

    # Clean up timer
    driver.destroy("987654")
    assert "987654" not in driver._watchdogs


def test_destroy_cancels_watchdog_and_issues_delete():
    deleted_urls = []

    def mock_opener(req, timeout=30):
        if req.method == "DELETE":
            deleted_urls.append(req.full_url)
            return MockHTTPResponse({}, 204)
        return MockHTTPResponse({"server": {"id": 111}}, 200)

    driver = HetznerRunnerDriver(
        config={"token": "fake-token"},
        opener=mock_opener,
    )

    # Arm a mock watchdog
    timer = MagicMock()
    driver._watchdogs["111"] = timer

    success = driver.destroy("111")
    assert success is True
    assert timer.cancel.called
    assert "111" not in driver._watchdogs
    assert deleted_urls == ["https://api.hetzner.cloud/v1/servers/111"]


def test_destroy_treats_missing_server_as_already_destroyed():
    def mock_opener(req, timeout=30):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, BytesIO(b"{}"))

    driver = HetznerRunnerDriver(config={"token": "fake-token"}, opener=mock_opener)
    timer = MagicMock()
    driver._watchdogs["111"] = timer

    assert driver.destroy("111") is True
    timer.cancel.assert_called_once_with()
    assert "111" not in driver._watchdogs


def test_collect_results_returns_structured_runtime_and_cost_receipt():
    def mock_opener(req, timeout=30):
        return MockHTTPResponse({
            "server": {
                "id": 998877,
                "name": "synlynk-lease-abc123",
                "status": "running",
                "created": "2026-11-23T08:00:00+00:00",
                "labels": {"epic_id": "epic-123", "lease_id": "lease-abc123"},
                "server_type": {"name": "cpx51", "cores": 16, "memory": 32},
            }
        })

    driver = HetznerRunnerDriver(
        config={"token": "fake-token", "location": "nbg1", "rate_eur_per_hour": 0.045},
        opener=mock_opener,
    )

    results = driver.collect_results("998877")

    assert results["event"] == "milestone_lease_completed"
    assert results["lease_id"] == "lease-abc123"
    assert results["epic_id"] == "epic-123"
    assert results["provider"] == "hetzner"
    assert results["server_id"] == 998877
    assert results["server_type"] == "cpx51"
    assert results["vcpus"] == 16
    assert results["ram_gb"] == 32
    assert results["location"] == "nbg1"
    assert results["active_seconds"] > 0
    assert results["raw_compute_cost_eur"] > 0


def test_api_error_handling():
    def mock_error_opener(req, timeout=30):
        fp = BytesIO(b'{"error":{"message":"Rate limit exceeded","code":"rate_limit_exceeded"}}')
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=fp,
        )

    driver = HetznerRunnerDriver(
        config={"token": "fake-token"},
        opener=mock_error_opener,
    )

    with pytest.raises(RuntimeError, match="Hetzner API error \\(429\\)"):
        driver.collect_results("server-999")
