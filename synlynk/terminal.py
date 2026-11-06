"""Terminal detection and formatting primitives, including OSC 8 hyperlinks."""

from __future__ import annotations

import os
import sys
from typing import Optional, TextIO

_OSC8_SUPPORTED_PROGRAMS = {
    "iterm.app",
    "wezterm",
    "vscode",
    "hyper",
    "mintty",
    "apple_terminal",
}

_OSC8_SUPPORTED_TERMS = {
    "xterm-kitty",
    "alacritty",
}


def supports_hyperlinks(stream: Optional[TextIO] = None) -> bool:
    """Return True if the output stream and terminal emulator support OSC 8 hyperlinks."""
    force = os.environ.get("FORCE_HYPERLINK", "").strip().lower()
    if force in ("1", "true", "yes", "on"):
        return True
    if force in ("0", "false", "no", "off"):
        return False

    if os.environ.get("NO_COLOR"):
        return False

    out = stream if stream is not None else sys.stdout
    if not hasattr(out, "isatty") or not out.isatty():
        return False

    if "DOMTERM" in os.environ:
        return True
    if "WT_SESSION" in os.environ:
        return True
    if "KONSOLE_VERSION" in os.environ:
        return True

    vte = os.environ.get("VTE_VERSION")
    if vte:
        try:
            if int(vte) >= 5000:
                return True
        except ValueError:
            pass

    prog = os.environ.get("TERM_PROGRAM", "").strip().lower()
    if prog in _OSC8_SUPPORTED_PROGRAMS:
        return True

    term = os.environ.get("TERM", "").strip().lower()
    if term in _OSC8_SUPPORTED_TERMS:
        return True

    return False


def hyperlink(
    url: str,
    text: Optional[str] = None,
    stream: Optional[TextIO] = None,
) -> str:
    """Format a clickable hyperlink using OSC 8 escape sequences, or plain text fallback."""
    if supports_hyperlinks(stream):
        label = text if text is not None else url
        return f"\033]8;;{url}\033\\{label}\033]8;;\033\\"

    if text and text != url:
        return f"{text} ({url})"
    return url
