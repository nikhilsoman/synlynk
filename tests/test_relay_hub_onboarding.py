import json
from types import SimpleNamespace

import pytest

from synlynk import relay_hub as hub


def test_remote_device_uses_only_exported_credential(tmp_path, monkeypatch):
    from synlynk.cli import main
    import synlynk.relay as relay

    store = hub.DeviceCredentialStore("ws1", tmp_path / "admin")
    credential = store.add_device("remote")
    remote = tmp_path / "remote"
    remote.mkdir()
    exported = remote / "device.creds"
    exported.write_bytes((store.config_dir / (credential.device_id + ".creds")).read_bytes())
    exported.chmod(0o600)
    monkeypatch.chdir(remote)
    observed = {}

    class Server:
        def __init__(self, port):
            self.broker = object()
            self.httpd = SimpleNamespace(server_close=lambda: observed.update(closed=True))

        def start(self, background):
            assert observed["attached"]

    class Adapter:
        def __init__(self, broker, client, workspace, **options):
            assert workspace == "ws1"

        def attach(self):
            observed["attached"] = True

        def detach(self):
            observed["detached"] = True

    def transport(servers, **options):
        assert servers == ["nats://hub:4222"]
        assert options == {"user": credential.device_id, "password": credential.token}
        return object()

    monkeypatch.setattr(relay, "RelayServer", Server)
    monkeypatch.setattr(hub, "HubAdapter", Adapter)
    monkeypatch.setattr(hub, "NatsTransport", transport)
    main(["relay", "start", "--hub", "--credential-file", str(exported),
          "--workspace-id", "ws1", "--hub-url", "nats://hub:4222"])
    assert observed["closed"] and observed["detached"]
    assert not (remote / "devices.json").exists()


@pytest.mark.parametrize("change", ["scope", "device", "token", "revoked"])
def test_exported_credential_validation(tmp_path, change):
    store = hub.DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("remote")
    path = tmp_path / (cred.device_id + ".creds")
    raw = json.loads(path.read_text())
    if change == "scope":
        raw["subscribe_subjects"] = ["synlynk.other.>"]
    elif change == "device":
        raw["device_id"] = "../escape"
    elif change == "token":
        raw["token"] = ""
    else:
        raw["revoked"] = True
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        hub.load_device_credential(path, "ws1")


def test_cli_config_symlink_rejected(tmp_path):
    from synlynk.cli import main
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        main(["relay", "hub", "init", "--workspace-id", "ws1", "--config-dir", str(link)])
    assert list(target.iterdir()) == []
