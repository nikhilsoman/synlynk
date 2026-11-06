import io
import sys

from synlynk import terminal


def test_supports_hyperlinks_forced(monkeypatch):
    monkeypatch.setenv("FORCE_HYPERLINK", "1")
    assert terminal.supports_hyperlinks() is True


def test_supports_hyperlinks_disabled_on_no_color(monkeypatch):
    monkeypatch.setenv("FORCE_HYPERLINK", "")
    monkeypatch.setenv("NO_COLOR", "1")
    assert terminal.supports_hyperlinks() is False


def test_supports_hyperlinks_disabled_on_non_tty(monkeypatch):
    monkeypatch.delenv("FORCE_HYPERLINK", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    fake_stream = io.StringIO()
    assert terminal.supports_hyperlinks(stream=fake_stream) is False


def test_supports_hyperlinks_for_supported_term_programs(monkeypatch):
    monkeypatch.delenv("FORCE_HYPERLINK", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    class FakeTTY(io.StringIO):
        def isatty(self):
            return True

    fake_stream = FakeTTY()

    for term_prog in ["iTerm.app", "WezTerm", "vscode"]:
        monkeypatch.setenv("TERM_PROGRAM", term_prog)
        assert terminal.supports_hyperlinks(stream=fake_stream) is True

    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.setenv("TERM", "xterm-kitty")
    assert terminal.supports_hyperlinks(stream=fake_stream) is True


def test_hyperlink_formatting_with_osc8(monkeypatch):
    monkeypatch.setenv("FORCE_HYPERLINK", "1")
    url = "http://localhost:33333/w/synlynk/overview.html"
    text = "Vizor Overview"

    rendered = terminal.hyperlink(url, text)
    assert rendered == f"\033]8;;{url}\033\\{text}\033]8;;\033\\"

    # Default text to url
    assert terminal.hyperlink(url) == f"\033]8;;{url}\033\\{url}\033]8;;\033\\"


def test_hyperlink_fallback_plain_text(monkeypatch):
    monkeypatch.delenv("FORCE_HYPERLINK", raising=False)
    fake_stream = io.StringIO()
    url = "http://localhost:33333/w/synlynk/overview.html"
    text = "Vizor Overview"

    rendered = terminal.hyperlink(url, text, stream=fake_stream)
    assert rendered == f"{text} ({url})"

    assert terminal.hyperlink(url, stream=fake_stream) == url
