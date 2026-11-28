import json

import pytest

from synlynk.runners.hetzner import HetznerRunnerDriver


def test_cloud_init_bootstraps_requested_ref_and_isolates_state():
    driver = HetznerRunnerDriver(
        config={
            "token": "test-token",
            "repo_url": "https://github.com/example/synlynk.git",
            "ssm_available": True,
        }
    )

    user_data = driver.build_cloud_init({"git_ref": "refs/tags/v0.39.1"})

    assert "git -C /opt/synlynk fetch --depth 1 origin refs/tags/v0.39.1" in user_data
    assert "/opt/synlynk-venv/bin/pip install --no-deps /opt/synlynk" in user_data
    assert "synlynk --version" in user_data
    assert "/opt/synlynk/VERSION" in user_data
    assert "state.db" not in user_data
    assert "amazon-ssm-agent" in user_data
    assert "ufw --force deny 22/tcp" in user_data


def test_cloud_init_defaults_to_origin_main():
    driver = HetznerRunnerDriver(config={"token": "test-token"})

    user_data = driver.build_cloud_init({})

    assert "git -C /opt/synlynk fetch --depth 1 origin main" in user_data


def test_cloud_init_requires_operator_cidr_when_ssm_is_unavailable():
    driver = HetznerRunnerDriver(
        config={
            "token": "test-token",
            "repo_url": "https://github.com/example/synlynk.git",
            "ssm_available": False,
        }
    )

    with pytest.raises(ValueError, match="operator_cidr"):
        driver.build_cloud_init({})


def test_provision_falls_back_to_cidr_restricted_ssh():
    requests = []

    class Response:
        def read(self):
            return json.dumps({"server": {"id": 42}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def opener(request, timeout=30):
        requests.append(request)
        return Response()

    driver = HetznerRunnerDriver(
        config={
            "token": "test-token",
            "repo_url": "https://github.com/example/synlynk.git",
            "ssm_available": False,
            "operator_cidr": "203.0.113.0/24",
        },
        opener=opener,
    )

    driver.provision({})
    payload = json.loads(requests[0].data.decode())
    assert "ufw allow from 203.0.113.0/24 to any port 22 proto tcp" in payload["user_data"]
    assert "ufw deny 22/tcp" not in payload["user_data"]
    driver.destroy("42")
