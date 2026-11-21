"""OpenRouter BYOK choices in the first-run harness wizard."""

import io

import synlynk


def test_zero_harnesses_can_configure_openrouter_byok(monkeypatch):
    """The no-local-CLI path offers BYOK and uses its verified gateway."""
    monkeypatch.setattr("sys.stdin", io.StringIO("o"))
    monkeypatch.setattr("getpass.getpass", lambda _: "test-openrouter-key")

    configured = []
    monkeypatch.setattr(
        "synlynk.registry.configure_openrouter",
        lambda: configured.append(True),
    )
    monkeypatch.setattr("synlynk.gateway.cmd_gateway_probe", lambda gateway: 0)

    assert synlynk._wiz_screen_harness({"harnesses": []}) == "openrouter"
    assert configured == [True]


def test_openrouter_option_is_available_alongside_local_harnesses(monkeypatch):
    """[O] selects a verified OpenRouter gateway over a detected local CLI."""
    monkeypatch.setattr("sys.stdin", io.StringIO("O"))
    monkeypatch.setattr("getpass.getpass", lambda _: "test-openrouter-key")
    monkeypatch.setattr("synlynk.registry.configure_openrouter", lambda: None)

    probe_calls = []
    monkeypatch.setattr(
        "synlynk.gateway.cmd_gateway_probe",
        lambda gateway: probe_calls.append(gateway) or 0,
    )
    scan = {
        "harnesses": [{"name": "claude", "version": "1", "path": "/bin/claude"}],
        "home_harness": "claude",
    }

    assert synlynk._wiz_screen_harness(scan) == "openrouter"
    assert probe_calls == ["openrouter"]


def test_openrouter_byok_does_not_become_home_when_probe_fails(monkeypatch):
    """A rejected key leaves the wizard without an unverified home harness."""
    monkeypatch.setattr("sys.stdin", io.StringIO("o"))
    monkeypatch.setattr("getpass.getpass", lambda _: "test-openrouter-key")
    monkeypatch.setattr("synlynk.registry.configure_openrouter", lambda: None)
    monkeypatch.setattr("synlynk.gateway.cmd_gateway_probe", lambda gateway: 1)

    assert synlynk._wiz_screen_harness({"harnesses": []}) == ""


def test_openrouter_byok_allows_blank_or_cancelled_key_without_configuring(monkeypatch):
    """An omitted key remains a safe no-home-harness choice."""
    monkeypatch.setattr("getpass.getpass", lambda _: "")
    assert synlynk._wiz_configure_openrouter_byok() == ""

    def cancel(_):
        raise EOFError

    monkeypatch.setattr("getpass.getpass", cancel)
    assert synlynk._wiz_configure_openrouter_byok() == ""


def test_openrouter_byok_handles_configuration_errors(monkeypatch):
    """Gateway configuration errors cannot select an unverified provider."""
    monkeypatch.setattr("getpass.getpass", lambda _: "test-openrouter-key")

    def fail_configuration():
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr("synlynk.registry.configure_openrouter", fail_configuration)
    assert synlynk._wiz_configure_openrouter_byok() == ""
