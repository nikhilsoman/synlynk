import pytest
import json

from synlynk.local_credentials import (
    CredentialUnavailable,
    LocalCredentialStore,
    UnsupportedCredentialPlatform,
)
from synlynk.local_agent import cmd_local_credentials


class MemoryKeychain:
    def __init__(self):
        self.value = None

    def add(self, service, account, value, accessibility):
        if self.value is not None:
            raise FileExistsError
        self.value = value

    def update(self, service, account, value, accessibility):
        if self.value is None:
            raise FileNotFoundError
        self.value = value

    def get(self, service, account):
        if self.value is None:
            raise FileNotFoundError
        return self.value.decode("utf-8") if isinstance(self.value, bytes) else self.value

    def delete(self, service, account):
        if self.value is None:
            raise FileNotFoundError
        self.value = None


def test_import_retrieve_replace_and_delete_keychain_secret():
    adapter = MemoryKeychain()
    store = LocalCredentialStore(adapter=adapter, platform="darwin")

    store.import_from_environment({"OPENAI_API_KEY": "secret-one"})
    assert adapter.value == b"secret-one"
    with pytest.raises(CredentialUnavailable):
        store.import_from_environment({"OPENAI_API_KEY": "secret-two"})
    store.import_from_environment({"OPENAI_API_KEY": "secret-two"}, replace=True)
    assert adapter.value == b"secret-two"
    store.delete()
    assert adapter.value is None


def test_settings_keychain_state_does_not_override_active_omlx_settings(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"auth":{"api_key":"persistent-key"}}')
    adapter = MemoryKeychain()
    store = LocalCredentialStore(adapter=adapter, platform="darwin", settings_path=str(settings))
    adapter.value = "stale-keychain-key"
    assert store.get() == "persistent-key"

    def locked(*args):
        raise PermissionError("keychain locked")

    adapter.get = locked
    assert store.get() == "persistent-key"


def test_missing_settings_credential_is_classified_and_redacted(tmp_path):
    store = LocalCredentialStore(settings_path=str(tmp_path / "missing.json"))
    with pytest.raises(CredentialUnavailable) as missing:
        store.get()
    assert "secret" not in str(missing.value).lower()


def test_legacy_keychain_import_remains_macos_only():
    store = LocalCredentialStore(adapter=MemoryKeychain(), platform="linux")
    with pytest.raises(UnsupportedCredentialPlatform):
        store.import_from_environment({"OPENAI_API_KEY": "secret"})


def _write_settings(base, key="persistent-omlx-key"):
    base.mkdir(parents=True, exist_ok=True)
    (base / "settings.json").write_text(json.dumps({"auth": {"api_key": key}}))


def test_settings_credential_prefers_nonempty_app_bootstrap_over_environment(tmp_path):
    env_base = tmp_path / "env-base"
    bootstrap_base = tmp_path / "bootstrap-base"
    _write_settings(env_base, "env-key")
    _write_settings(bootstrap_base, "bootstrap-key")
    bootstrap = tmp_path / "base-path"
    bootstrap.write_text(str(bootstrap_base))

    store = LocalCredentialStore(
        settings_path=None,
        environ={"OMLX_BASE_PATH": str(env_base), "OPENAI_API_KEY": "frontier-key-must-not-win"},
        home=str(tmp_path), bootstrap_path=str(bootstrap),
    )
    assert store.get() == "bootstrap-key"


def test_settings_credential_uses_environment_when_bootstrap_is_missing(tmp_path):
    env_base = tmp_path / "env-base"
    _write_settings(env_base, "env-key")
    store = LocalCredentialStore(
        environ={"OMLX_BASE_PATH": str(env_base)}, home=str(tmp_path),
        bootstrap_path=str(tmp_path / "missing"),
    )
    assert store.get() == "env-key"


def test_settings_credential_uses_app_bootstrap_before_default_home(tmp_path):
    bootstrap_base = tmp_path / "bootstrap-base"
    default_base = tmp_path / ".omlx"
    _write_settings(bootstrap_base, "bootstrap-key")
    _write_settings(default_base, "default-key")
    bootstrap = tmp_path / "base-path"
    bootstrap.write_text(str(bootstrap_base))

    store = LocalCredentialStore(
        environ={}, home=str(tmp_path), bootstrap_path=str(bootstrap),
    )
    assert store.get() == "bootstrap-key"


def test_settings_credential_falls_back_to_default_home(tmp_path):
    base = tmp_path / ".omlx"
    _write_settings(base, "default-key")
    store = LocalCredentialStore(environ={}, home=str(tmp_path), bootstrap_path=str(tmp_path / "missing"))
    assert store.get() == "default-key"


@pytest.mark.parametrize("payload", [None, {}, {"auth": {"api_key": ""}}])
def test_settings_credential_missing_or_empty_fails_closed(tmp_path, payload):
    base = tmp_path / "omlx"
    base.mkdir()
    path = base / "settings.json"
    if payload is not None:
        path.write_text(json.dumps(payload))
    store = LocalCredentialStore(settings_path=str(path))
    with pytest.raises(CredentialUnavailable):
        store.get()
    assert not store.is_configured()


def test_malformed_settings_are_redacted(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"auth":')
    store = LocalCredentialStore(settings_path=str(path))
    with pytest.raises(CredentialUnavailable) as error:
        store.get()
    assert "{" not in str(error.value)
    assert not store.is_configured()


def test_settings_permission_error_is_classified_and_redacted(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text('{"auth":{"api_key":"not-for-errors"}}')
    store = LocalCredentialStore(settings_path=str(path))
    original_open = type(path).open

    def deny_settings(file, *args, **kwargs):
        if file == path:
            raise PermissionError("not-for-errors")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(type(path), "open", deny_settings)
    with pytest.raises(CredentialUnavailable) as error:
        store.get()
    assert "not-for-errors" not in str(error.value)
    assert not store.is_configured()


def test_cli_import_requires_tty_and_never_prints_credential(capsys):
    adapter = MemoryKeychain()
    store = LocalCredentialStore(adapter=adapter, platform="darwin")
    assert cmd_local_credentials(
        "import", environ={"OPENAI_API_KEY": "secret-never-print"},
        interactive=False, store=store,
    ) == 1
    assert "secret-never-print" not in capsys.readouterr().out

    assert cmd_local_credentials(
        "import", environ={"OPENAI_API_KEY": "secret-never-print"},
        interactive=True, store=store,
    ) == 0
    output = capsys.readouterr().out
    assert "stored" in output
    assert "secret-never-print" not in output
