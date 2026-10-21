import pytest

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
    assert store.is_configured()
    assert store.get() == "secret-one"
    with pytest.raises(CredentialUnavailable):
        store.import_from_environment({"OPENAI_API_KEY": "secret-two"})
    store.import_from_environment({"OPENAI_API_KEY": "secret-two"}, replace=True)
    assert store.get() == "secret-two"
    store.delete()
    assert not store.is_configured()


def test_missing_or_locked_keychain_is_classified_and_secret_is_not_in_error():
    adapter = MemoryKeychain()
    store = LocalCredentialStore(adapter=adapter, platform="darwin")
    with pytest.raises(CredentialUnavailable) as missing:
        store.get()
    assert "secret" not in str(missing.value).lower()

    def locked(*args):
        raise PermissionError("keychain locked")

    adapter.get = locked
    with pytest.raises(CredentialUnavailable, match="unavailable"):
        store.get()


def test_non_macos_store_fails_closed():
    store = LocalCredentialStore(adapter=MemoryKeychain(), platform="linux")
    with pytest.raises(UnsupportedCredentialPlatform):
        store.get()


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
